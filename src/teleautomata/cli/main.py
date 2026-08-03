import asyncio
import re
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from telethon import TelegramClient

from teleautomata.application.engine import WorkflowEngine
from teleautomata.config.settings import Settings
from teleautomata.domain.models import ExecutionSummary
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

app = typer.Typer(help="Safety-first, workflow-driven Telegram automation.", no_args_is_help=True)


def _validate_account_name(account: str) -> str:
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", account):
        raise typer.BadParameter("must match [a-zA-Z][a-zA-Z0-9_-]{0,63}")
    return account


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


def _echo_summary(summary: ExecutionSummary) -> None:
    typer.echo(
        f"Execution {summary.execution_id}: {summary.status}; "
        f"succeeded={summary.succeeded}, failed={summary.failed}, "
        f"skipped={summary.skipped}"
    )


@app.command()
def init() -> None:
    """Create local runtime directories and initialize the database."""
    settings = Settings()

    async def command() -> None:
        settings.session_dir.mkdir(parents=True, exist_ok=True)
        engine = build_engine(settings.database_url)
        await initialize_database(engine)
        await engine.dispose()

    asyncio.run(command())
    typer.echo("Initialized runtime directories and database.")


@app.command()
def validate(
    workflow: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Validate a workflow without connecting to Telegram."""
    definition = load_workflow(workflow)
    typer.echo(f"Valid workflow '{definition.name}' with {len(definition.actions)} action(s).")


@app.command()
def auth(
    account: Annotated[str, typer.Argument(help="Local session name, not a phone number.")],
) -> None:
    """Interactively authenticate an account; secrets and 2FA are never stored by this app."""
    account = _validate_account_name(account)
    settings = Settings()
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
    typer.echo(f"Authenticated session '{account}'. Keep its file private.")


@app.command()
def run(
    workflow: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Run a validated workflow. Use dry_run: true in the YAML to inspect intent safely."""
    settings = Settings()
    configure_logging(settings.log_level)
    definition = load_workflow(workflow)
    summary = asyncio.run(_execute(settings, definition, resume_execution_id=None))
    _echo_summary(summary)
    if summary.failed:
        raise typer.Exit(code=1)


@app.command()
def resume(
    workflow: Annotated[Path, typer.Argument(exists=True, readable=True)],
    execution_id: Annotated[UUID, typer.Argument(help="Execution ID returned by a previous run.")],
) -> None:
    """Retry unfinished actions, preserving previously successful actions."""
    settings = Settings()
    configure_logging(settings.log_level)
    definition = load_workflow(workflow)
    summary = asyncio.run(_execute(settings, definition, resume_execution_id=execution_id))
    _echo_summary(summary)
    if summary.failed:
        raise typer.Exit(code=1)


@app.command(name="list")
def list_workflows(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)] = Path(
        "examples/workflows"
    ),
) -> None:
    """List and validate every workflow YAML in a directory."""
    paths = sorted(p for p in directory.glob("*.y*ml"))
    if not paths:
        typer.echo(f"No workflow files found in {directory}.")
        return
    for path in paths:
        try:
            definition = load_workflow(path)
        except Exception as exc:  # noqa: BLE001 - surface any validation error per file
            typer.echo(f"{path.name}: INVALID ({type(exc).__name__})")
            continue
        dry = " [dry_run]" if definition.dry_run else ""
        typer.echo(
            f"{path.name}: '{definition.name}' account={definition.account} "
            f"actions={len(definition.actions)}{dry}"
        )


@app.command()
def history(
    limit: Annotated[int, typer.Option(min=1, max=200, help="Maximum executions to show.")] = 20,
) -> None:
    """Show recent workflow executions from the operation database."""
    settings = Settings()

    async def command() -> None:
        database_engine = build_engine(settings.database_url)
        await initialize_database(database_engine)
        try:
            repository = _build_repository(database_engine)
            executions = await repository.list_executions(limit=limit)
        finally:
            await database_engine.dispose()
        if not executions:
            typer.echo("No executions recorded yet.")
            return
        for record in executions:
            completed = record.completed_at.isoformat() if record.completed_at else "-"
            typer.echo(
                f"{record.execution_id}  {record.status:<9}  {record.workflow_name}  "
                f"account={record.account}  started={record.created_at.isoformat()}  "
                f"completed={completed}"
            )

    asyncio.run(command())


@app.command()
def status(
    execution_id: Annotated[UUID, typer.Argument(help="Execution ID from run/history.")],
) -> None:
    """Show the per-action status of a single execution."""
    settings = Settings()

    async def command() -> None:
        database_engine = build_engine(settings.database_url)
        await initialize_database(database_engine)
        try:
            repository = _build_repository(database_engine)
            execution = await repository.get_execution(execution_id)
            operations = await repository.operations(execution_id) if execution else []
        finally:
            await database_engine.dispose()
        if execution is None:
            typer.echo(f"No execution found with id {execution_id}.")
            raise typer.Exit(code=1)
        typer.echo(
            f"Execution {execution.execution_id}: {execution.status} "
            f"(workflow '{execution.workflow_name}', account={execution.account})"
        )
        for op in operations:
            detail = f" error={op.error_code}" if op.error_code else ""
            typer.echo(
                f"  {op.action_id:<20} {op.action_type:<16} {op.status:<10} "
                f"attempts={op.attempts}{detail}"
            )

    asyncio.run(command())


if __name__ == "__main__":
    app()
