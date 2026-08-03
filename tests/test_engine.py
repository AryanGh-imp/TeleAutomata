from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from telegram_automation.application.engine import WorkflowEngine
from telegram_automation.domain.errors import TransientActionError
from telegram_automation.domain.models import OperationStatus
from telegram_automation.infrastructure.persistence import (
    OperationRepository,
    build_engine,
    initialize_database,
)
from telegram_automation.infrastructure.scheduling import AccountRateLimiter
from telegram_automation.workflows.schema import RetryPolicy, WorkflowDefinition


class FakeGateway:
    def __init__(self, fail_once: bool = False) -> None:
        self.calls = 0
        self.fail_once = fail_once

    async def resolve_target(self, target: str) -> dict[str, Any]:
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise TransientActionError("network")
        return {"target": target, "entity_id": 1}

    async def create_group(self, title: str, users: list[str]) -> dict[str, Any]:
        raise AssertionError

    async def create_channel(self, title: str, about: str, broadcast: bool) -> dict[str, Any]:
        raise AssertionError

    async def update_entity(
        self, target: str, title: str | None, about: str | None
    ) -> dict[str, Any]:
        raise AssertionError

    async def send_message(self, target: str, message: str) -> dict[str, Any]:
        raise AssertionError


@pytest.fixture
async def repository() -> AsyncGenerator[OperationRepository, None]:
    engine = build_engine("sqlite+aiosqlite:///:memory:")
    await initialize_database(engine)
    yield OperationRepository(async_sessionmaker(engine, expire_on_commit=False))
    await engine.dispose()


@pytest.mark.asyncio
async def test_retries_temporary_failure(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "retry",
            "account": "a",
            "actions": [
                {
                    "id": "resolve",
                    "type": "resolve_target",
                    "with": {"target": "@telegram"},
                    "retry": {
                        "max_attempts": 2,
                        "initial_delay_seconds": 0.1,
                        "max_delay_seconds": 0.1,
                    },
                },
            ],
        }
    )
    gateway = FakeGateway(fail_once=True)
    result = await WorkflowEngine(
        repository,
        gateway,
        AccountRateLimiter(0.1),
        max_concurrency=2,
        max_flood_wait_seconds=5,
        default_retry=RetryPolicy(),
    ).run(workflow)
    assert result.status == OperationStatus.SUCCEEDED
    assert result.succeeded == 1
    assert gateway.calls == 2


@pytest.mark.asyncio
async def test_dry_run_never_calls_gateway(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "dry",
            "account": "a",
            "dry_run": True,
            "actions": [
                {"id": "resolve", "type": "resolve_target", "with": {"target": "@telegram"}},
            ],
        }
    )
    gateway = FakeGateway()
    result = await WorkflowEngine(
        repository,
        gateway,
        AccountRateLimiter(0.1),
        max_concurrency=2,
        max_flood_wait_seconds=5,
        default_retry=RetryPolicy(),
    ).run(workflow)
    assert result.status == OperationStatus.SUCCEEDED
    assert result.skipped == 1
    assert gateway.calls == 0
