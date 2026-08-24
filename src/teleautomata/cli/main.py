import asyncio
import contextlib
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from telethon import TelegramClient

from teleautomata import __version__
from teleautomata.application.engine import WorkflowEngine
from teleautomata.cli import presentation as ui
from teleautomata.config.settings import Settings
from teleautomata.domain.errors import TeleAutomataError
from teleautomata.domain.models import (
    ExecutionRecordView,
    ExecutionSummary,
    OperationRecordView,
    OperationStatus,
)
from teleautomata.domain.ports import TelegramGateway
from teleautomata.infrastructure.null_gateway import NullGateway
from teleautomata.infrastructure.persistence import (
    OperationRepository,
    build_engine,
    initialize_database,
)
from teleautomata.infrastructure.scheduling import AccountRateLimiter
from teleautomata.infrastructure.telegram import connect_gateway
from teleautomata.observability.logging import configure_logging
from teleautomata.workflows.schema import RetryPolicy, WorkflowDefinition, load_workflow

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


class _State:
    """Invocation-scoped flags set by the top-level callback."""

    debug: bool = False


_state = _State()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"teleautomata {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the version and exit.",
            is_eager=True,
            callback=_version_callback,
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Show full tracebacks instead of concise error panels."),
    ] = False,
) -> None:
    """Safety-first, workflow-driven Telegram automation."""
    _state.debug = debug
    ui.configure(interactive=sys.stdout.isatty())


def _validate_account_name(account: str) -> str:
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", account):
        raise typer.BadParameter("must match [a-zA-Z][a-zA-Z0-9_-]{0,63}")
    return account


def _short_error(exc: Exception) -> str:
    """A concise, single-line rendering of a validation failure for tables/panels."""
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        first = errors[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "(root)"
        summary = f"{location}: {first.get('msg', '')}"
        extra = len(errors) - 1
        return summary if extra == 0 else f"{summary} (+{extra} more)"
    return str(exc)


@contextlib.contextmanager
def _guard() -> Iterator[None]:
    """Turn expected failures into concise error panels with a non-zero exit.

    Typer's own control-flow exceptions pass through unchanged. Validation,
    configuration, and gateway errors become actionable panels on stderr. Any
    other exception is reported the same way unless ``--debug`` is set, in which
    case the original traceback is preserved for diagnosis.
    """
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except ValidationError as exc:
        ui.err_console.print(
            ui.error_panel(
                "Invalid workflow",
                _short_error(exc),
                hint="Fix the reported field and re-run. See docs/workflow-schema.md.",
            )
        )
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        ui.err_console.print(ui.error_panel("Invalid input", str(exc)))
        raise typer.Exit(code=1) from None
    except TeleAutomataError as exc:
        ui.err_console.print(ui.error_panel(type(exc).__name__, str(exc)))
        raise typer.Exit(code=1) from None
    except Exception as exc:
        if _state.debug:
            raise
        ui.err_console.print(
            ui.error_panel(
                "Unexpected error",
                f"{type(exc).__name__}: {exc}",
                hint="Re-run with --debug to see the full traceback.",
            )
        )
        raise typer.Exit(code=1) from None


def _build_repository(database_engine: AsyncEngine) -> OperationRepository:
    return OperationRepository(async_sessionmaker(database_engine, expire_on_commit=False))


def _build_engine(
    settings: Settings, repository: OperationRepository, gateway: TelegramGateway
) -> WorkflowEngine:
    return WorkflowEngine(
        repository,
        gateway,
        AccountRateLimiter(settings.min_request_interval_seconds),
        max_concurrency=settings.max_concurrency,
        max_flood_wait_seconds=settings.max_flood_wait_seconds,
        default_retry=RetryPolicy(max_attempts=settings.max_retries + 1),
    )


async def _execute(
    settings: Settings,
    definition: WorkflowDefinition,
    resume_execution_id: UUID | None,
) -> ExecutionSummary:
    """Run (or resume) a workflow and always release resources.

    A dry run never touches Telegram, so it needs neither credentials nor a
    live session; it runs against a :class:`NullGateway` that raises if any
    action is unexpectedly attempted. A real run connects an authenticated
    Telethon session.
    """
    database_engine = build_engine(settings.database_url)
    await initialize_database(database_engine)
    repository = _build_repository(database_engine)

    if definition.dry_run:
        try:
            engine = _build_engine(settings, repository, NullGateway())
            return await engine.run(definition, resume_execution_id=resume_execution_id)
        finally:
            await database_engine.dispose()

    api_id, api_hash = settings.require_telegram_credentials()
    client, gateway = await connect_gateway(
        api_id, api_hash, settings.session_dir, definition.account
    )
    try:
        engine = _build_engine(settings, repository, gateway)
        return await engine.run(definition, resume_execution_id=resume_execution_id)
    finally:
        await client.disconnect()
        await database_engine.dispose()


def _stdin_is_tty() -> bool:
    return sys.stdin.isatty()


def _confirm_live_run(definition: WorkflowDefinition, *, assume_yes: bool) -> None:
    """Prompt before a live run performs real Telegram actions.

    Skipped for dry runs, when ``--yes`` is given, and in non-interactive
    contexts (pipes, CI) where a prompt would hang — those proceed unchanged so
    existing automation keeps working.
    """
    if definition.dry_run or assume_yes or not _stdin_is_tty():
        return
    typer.confirm(
        f"Run '{definition.name}' against live account '{definition.account}'? "
        "This performs real Telegram actions.",
        abort=True,
    )


def _run_workflow(
    settings: Settings, definition: WorkflowDefinition, *, resume_execution_id: UUID | None
) -> ExecutionSummary:
    """Execute the workflow, showing a spinner for the slow, live path only."""
    if definition.dry_run:
        return asyncio.run(_execute(settings, definition, resume_execution_id))
    with ui.out_console.status(
        f"Running '{definition.name}' on account '{definition.account}'…", spinner="dots"
    ):
        return asyncio.run(_execute(settings, definition, resume_execution_id))


@app.command(rich_help_panel="Setup")
def init() -> None:
    """Create local runtime directories and initialize the database."""
    settings = Settings()

    async def command() -> None:
        settings.session_dir.mkdir(parents=True, exist_ok=True)
        engine = build_engine(settings.database_url)
        await initialize_database(engine)
        await engine.dispose()

    with _guard():
        with ui.out_console.status("Initializing runtime directories and database…"):
            asyncio.run(command())
    ui.out_console.print(ui.message("success", "Initialized runtime directories and database."))


@app.command(rich_help_panel="Setup")
def auth(
    account: Annotated[str, typer.Argument(help="Local session name, not a phone number.")],
) -> None:
    """Interactively authenticate an account; secrets and 2FA are never stored by this app."""
    account = _validate_account_name(account)
    settings = Settings()

    with _guard():
        api_id, api_hash = settings.require_telegram_credentials()

        async def command() -> None:
            settings.session_dir.mkdir(parents=True, exist_ok=True)
            client = TelegramClient(str(settings.session_dir / account), api_id, api_hash)
            await client.start(
                phone=lambda: typer.prompt("Phone number"),
                password=lambda: typer.prompt("2FA password", hide_input=True),
            )
            await client.disconnect()

        asyncio.run(command())
    ui.out_console.print(
        ui.message("success", f"Authenticated session '{account}'. Keep its file private.")
    )


@app.command(rich_help_panel="Workflows")
def validate(
    workflow: Annotated[
        Path, typer.Argument(exists=True, readable=True, help="Workflow YAML to validate.")
    ],
) -> None:
    """Validate a workflow without connecting to Telegram."""
    with _guard():
        definition = load_workflow(workflow)
        ui.out_console.print(ui.validation_panel(definition))


@app.command(rich_help_panel="Workflows")
def run(
    workflow: Annotated[
        Path, typer.Argument(exists=True, readable=True, help="Workflow YAML to execute.")
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt for a live run."),
    ] = False,
) -> None:
    """Run a validated workflow. Set [bold]dry_run: true[/] in the YAML to inspect intent safely."""
    settings = Settings()
    configure_logging(settings.log_level)
    with _guard():
        definition = load_workflow(workflow)
        _confirm_live_run(definition, assume_yes=yes)
        summary = _run_workflow(settings, definition, resume_execution_id=None)
        ui.out_console.print(ui.execution_summary_panel(definition, summary))
        if summary.status == OperationStatus.FAILED:
            raise typer.Exit(code=1)


@app.command(rich_help_panel="Workflows")
def resume(
    workflow: Annotated[
        Path, typer.Argument(exists=True, readable=True, help="The same workflow YAML as the run.")
    ],
    execution_id: Annotated[UUID, typer.Argument(help="Execution ID returned by a previous run.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt for a live run."),
    ] = False,
) -> None:
    """Retry unfinished actions, preserving previously successful actions."""
    settings = Settings()
    configure_logging(settings.log_level)
    with _guard():
        definition = load_workflow(workflow)
        _confirm_live_run(definition, assume_yes=yes)
        summary = _run_workflow(settings, definition, resume_execution_id=execution_id)
        ui.out_console.print(ui.execution_summary_panel(definition, summary))
        if summary.status == OperationStatus.FAILED:
            raise typer.Exit(code=1)


@app.command(name="list", rich_help_panel="Workflows")
def list_workflows(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)] = Path(
        "examples/workflows"
    ),
) -> None:
    """List and validate every workflow YAML in a directory."""
    with _guard():
        paths = sorted(directory.glob("*.y*ml"))
        if not paths:
            ui.out_console.print(ui.message("info", f"No workflow files found in {directory}."))
            return
        rows: list[tuple[str, WorkflowDefinition | None, str | None]] = []
        for path in paths:
            try:
                rows.append((path.name, load_workflow(path), None))
            except Exception as exc:  # noqa: BLE001 - surface any validation error per file
                rows.append((path.name, None, _short_error(exc)))
        ui.out_console.print(ui.workflow_list_table(rows))


@app.command(rich_help_panel="Inspection")
def history(
    limit: Annotated[int, typer.Option(min=1, max=200, help="Maximum executions to show.")] = 20,
) -> None:
    """Show recent workflow executions from the operation database."""
    settings = Settings()

    async def command() -> list[ExecutionRecordView]:
        database_engine = build_engine(settings.database_url)
        await initialize_database(database_engine)
        try:
            repository = _build_repository(database_engine)
            return await repository.list_executions(limit=limit)
        finally:
            await database_engine.dispose()

    with _guard():
        executions = asyncio.run(command())
        if not executions:
            ui.out_console.print(ui.message("info", "No executions recorded yet."))
            return
        ui.out_console.print(ui.history_table(executions))


@app.command(rich_help_panel="Inspection")
def status(
    execution_id: Annotated[UUID, typer.Argument(help="Execution ID from run/history.")],
) -> None:
    """Show the per-action status of a single execution."""
    settings = Settings()

    async def command() -> tuple[ExecutionRecordView | None, list[OperationRecordView]]:
        database_engine = build_engine(settings.database_url)
        await initialize_database(database_engine)
        try:
            repository = _build_repository(database_engine)
            execution = await repository.get_execution(execution_id)
            operations = await repository.operations(execution_id) if execution else []
            return execution, operations
        finally:
            await database_engine.dispose()

    with _guard():
        execution, operations = asyncio.run(command())
        if execution is None:
            ui.err_console.print(
                ui.error_panel(
                    "Execution not found",
                    f"No execution found with id {execution_id}.",
                    hint="List recent executions with 'teleautomata history'.",
                )
            )
            raise typer.Exit(code=1)
        ui.out_console.print(ui.status_report(execution, operations))


if __name__ == "__main__":
    app()
