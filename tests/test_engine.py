from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from telegram_automation.application.engine import WorkflowEngine
from telegram_automation.domain.errors import PermanentActionError, TransientActionError
from telegram_automation.domain.models import OperationStatus
from telegram_automation.infrastructure.persistence import (
    OperationRepository,
    build_engine,
    initialize_database,
)
from telegram_automation.infrastructure.scheduling import AccountRateLimiter
from telegram_automation.workflows.schema import RetryPolicy, WorkflowDefinition


class FakeGateway:
    """In-memory gateway whose behaviour is scripted per test."""

    def __init__(
        self,
        fail_once: bool = False,
        *,
        permanent_fail_for: set[str] | None = None,
        transient_fail_for: set[str] | None = None,
    ) -> None:
        self.calls = 0
        self.fail_once = fail_once
        self._permanent_fail_for = permanent_fail_for or set()
        self._transient_fail_for = transient_fail_for or set()

    async def resolve_target(self, target: str) -> dict[str, Any]:
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise TransientActionError("network")
        if target in self._permanent_fail_for:
            raise PermanentActionError(f"permanent failure for {target}")
        if target in self._transient_fail_for:
            raise TransientActionError(f"transient failure for {target}")
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


def _engine(
    repository: OperationRepository, gateway: FakeGateway, *, concurrency: int = 2
) -> WorkflowEngine:
    return WorkflowEngine(
        repository,
        gateway,
        AccountRateLimiter(0.1),
        max_concurrency=concurrency,
        max_flood_wait_seconds=5,
        default_retry=RetryPolicy(),
    )


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
    result = await _engine(repository, gateway).run(workflow)
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
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.SUCCEEDED
    assert result.skipped == 1
    assert gateway.calls == 0


@pytest.mark.asyncio
async def test_permanent_error_is_terminal(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "permanent",
            "account": "a",
            "actions": [
                {
                    "id": "resolve",
                    "type": "resolve_target",
                    "with": {"target": "@forbidden"},
                    "retry": {"max_attempts": 3},
                },
            ],
        }
    )
    gateway = FakeGateway(permanent_fail_for={"@forbidden"})
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.FAILED
    assert result.failed == 1
    assert result.succeeded == 0
    assert gateway.calls == 1  # never retried


@pytest.mark.asyncio
async def test_transient_error_exhausts_retries(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "transient",
            "account": "a",
            "actions": [
                {
                    "id": "resolve",
                    "type": "resolve_target",
                    "with": {"target": "@flaky"},
                    "retry": {
                        "max_attempts": 3,
                        "initial_delay_seconds": 0.1,
                        "max_delay_seconds": 0.1,
                    },
                },
            ],
        }
    )
    gateway = FakeGateway(transient_fail_for={"@flaky"})
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.FAILED
    assert result.failed == 1
    assert gateway.calls == 3


@pytest.mark.asyncio
async def test_dependency_failure_skips_descendants(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "chain",
            "account": "a",
            "actions": [
                {"id": "first", "type": "resolve_target", "with": {"target": "@bad"}},
                {
                    "id": "second",
                    "type": "resolve_target",
                    "depends_on": ["first"],
                    "with": {"target": "@good"},
                },
            ],
        }
    )
    gateway = FakeGateway(permanent_fail_for={"@bad"})
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.FAILED
    assert result.failed == 1
    assert result.skipped == 1
    assert gateway.calls == 1  # the descendant never ran


@pytest.mark.asyncio
async def test_continue_on_error_allows_descendants(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "tolerated",
            "account": "a",
            "actions": [
                {
                    "id": "optional",
                    "type": "resolve_target",
                    "with": {"target": "@optional"},
                    "continue_on_error": True,
                },
                {
                    "id": "followup",
                    "type": "resolve_target",
                    "depends_on": ["optional"],
                    "with": {"target": "@good"},
                },
            ],
        }
    )
    gateway = FakeGateway(permanent_fail_for={"@optional"})
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.SUCCEEDED
    assert result.failed == 1  # tolerated failure is still recorded
    assert result.succeeded == 1
    assert gateway.calls == 2  # both targets were attempted


@pytest.mark.asyncio
async def test_skipped_dependency_still_skips_descendants(repository: OperationRepository) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "skipped_chain",
            "account": "a",
            "actions": [
                {"id": "first", "type": "resolve_target", "with": {"target": "@bad"}},
                {
                    "id": "second",
                    "type": "resolve_target",
                    "depends_on": ["first"],
                    "with": {"target": "@good"},
                },
            ],
        }
    )
    gateway = FakeGateway(permanent_fail_for={"@bad"})
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.FAILED
    assert result.failed == 1
    assert result.skipped == 1
    assert gateway.calls == 1


@pytest.mark.asyncio
async def test_continue_on_error_does_not_skip_grandchildren(
    repository: OperationRepository,
) -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "tolerated_chain",
            "account": "a",
            "actions": [
                {"id": "first", "type": "resolve_target", "with": {"target": "@good"}},
                {
                    "id": "second",
                    "type": "resolve_target",
                    "depends_on": ["first"],
                    "with": {"target": "@optional"},
                    "continue_on_error": True,
                },
                {
                    "id": "third",
                    "type": "resolve_target",
                    "depends_on": ["second"],
                    "with": {"target": "@good2"},
                },
            ],
        }
    )
    gateway = FakeGateway(permanent_fail_for={"@optional"})
    result = await _engine(repository, gateway).run(workflow)
    assert result.status == OperationStatus.SUCCEEDED
    assert result.succeeded == 2
    assert result.failed == 1
