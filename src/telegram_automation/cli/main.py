import asyncio
import re
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from telethon import TelegramClient

from telegram_automation.application.engine import WorkflowEngine
from telegram_automation.config.settings import Settings
from telegram_automation.infrastructure.persistence import (
    OperationRepository,
    build_engine,
    initialize_database,
)
from telegram_automation.infrastructure.scheduling import AccountRateLimiter
from telegram_automation.infrastructure.telegram import connect_gateway
from telegram_automation.observability.logging import configure_logging
from telegram_automation.workflows.schema import RetryPolicy, load_workflow

app = typer.Typer(help="Safety-first, workflow-driven Telegram automation.", no_args_is_help=True)


def _validate_account_name(account: str) -> str:
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", account):
        raise typer.BadParameter("must match [a-zA-Z][a-zA-Z0-9_-]{0,63}")
    return account


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
    api_id, api_hash = settings.require_telegram_credentials()

    async def command() -> None:
        database_engine = build_engine(settings.database_url)
        await initialize_database(database_engine)
        client, gateway = await connect_gateway(
            api_id, api_hash, settings.session_dir, definition.account
        )
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            repository = OperationRepository(
                async_sessionmaker(database_engine, expire_on_commit=False)
            )
            engine = WorkflowEngine(
                repository,
                gateway,
                AccountRateLimiter(settings.min_request_interval_seconds),
                max_concurrency=settings.max_concurrency,
                max_flood_wait_seconds=settings.max_flood_wait_seconds,
                default_retry=RetryPolicy(max_attempts=settings.max_retries + 1),
            )
            summary = await engine.run(definition)
            typer.echo(
                f"Execution {summary.execution_id}: {summary.status}; "
                f"succeeded={summary.succeeded}, failed={summary.failed}, "
                f"skipped={summary.skipped}"
            )
            if summary.failed:
                raise typer.Exit(code=1)
        finally:
            await client.disconnect()
            await database_engine.dispose()

    asyncio.run(command())


@app.command()
def resume(
    workflow: Annotated[Path, typer.Argument(exists=True, readable=True)],
    execution_id: Annotated[UUID, typer.Argument(help="Execution ID returned by a previous run.")],
) -> None:
    """Retry unfinished actions, preserving previously successful actions."""
    settings = Settings()
    configure_logging(settings.log_level)
    definition = load_workflow(workflow)
    api_id, api_hash = settings.require_telegram_credentials()

    async def command() -> None:
        database_engine = build_engine(settings.database_url)
        await initialize_database(database_engine)
        client, gateway = await connect_gateway(
            api_id, api_hash, settings.session_dir, definition.account
        )
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            repository = OperationRepository(
                async_sessionmaker(database_engine, expire_on_commit=False)
            )
            runner = WorkflowEngine(
                repository,
                gateway,
                AccountRateLimiter(settings.min_request_interval_seconds),
                max_concurrency=settings.max_concurrency,
                max_flood_wait_seconds=settings.max_flood_wait_seconds,
                default_retry=RetryPolicy(max_attempts=settings.max_retries + 1),
            )
            summary = await runner.run(definition, resume_execution_id=execution_id)
            typer.echo(f"Execution {summary.execution_id}: {summary.status}")
            if summary.failed:
                raise typer.Exit(code=1)
        finally:
            await client.disconnect()
            await database_engine.dispose()

    asyncio.run(command())


if __name__ == "__main__":
    app()
