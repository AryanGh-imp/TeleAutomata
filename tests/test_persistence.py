from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from telegram_automation.domain.models import OperationStatus
from telegram_automation.infrastructure.persistence import (
    OperationRepository,
    build_engine,
    initialize_database,
)


@pytest.fixture
async def repository() -> AsyncGenerator[OperationRepository, None]:
    engine = build_engine("sqlite+aiosqlite:///:memory:")
    await initialize_database(engine)
    yield OperationRepository(async_sessionmaker(engine, expire_on_commit=False))
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_execution_starts_running(repository: OperationRepository) -> None:
    execution_id = await repository.create_execution("wf", "acct", {"name": "wf"})
    view = await repository.get_execution(execution_id)
    assert view is not None
    assert view.status == OperationStatus.RUNNING
    assert view.workflow_name == "wf"
    assert view.account == "acct"
    assert view.completed_at is None


@pytest.mark.asyncio
async def test_get_unknown_execution_returns_none(repository: OperationRepository) -> None:
    assert await repository.get_execution(uuid4()) is None


@pytest.mark.asyncio
async def test_operation_lifecycle_and_views(repository: OperationRepository) -> None:
    execution_id = await repository.create_execution("wf", "acct", {})
    operation_id = await repository.create_operation(execution_id, "step", "resolve_target")
    await repository.update_operation(
        operation_id,
        OperationStatus.SUCCEEDED,
        attempts=2,
        output={"entity_id": 1},
    )
    operations = await repository.operations(execution_id)
    assert len(operations) == 1
    op = operations[0]
    assert op.action_id == "step"
    assert op.action_type == "resolve_target"
    assert op.status == OperationStatus.SUCCEEDED
    assert op.attempts == 2
    assert op.error_code is None


@pytest.mark.asyncio
async def test_update_operation_records_error(repository: OperationRepository) -> None:
    execution_id = await repository.create_execution("wf", "acct", {})
    operation_id = await repository.create_operation(execution_id, "step", "resolve_target")
    await repository.update_operation(
        operation_id,
        OperationStatus.FAILED,
        attempts=1,
        error_code="permanent_error",
        error_detail="nope",
    )
    op = (await repository.operations(execution_id))[0]
    assert op.status == OperationStatus.FAILED
    assert op.error_code == "permanent_error"
    assert op.error_detail == "nope"


@pytest.mark.asyncio
async def test_update_missing_operation_raises(repository: OperationRepository) -> None:
    with pytest.raises(KeyError):
        await repository.update_operation(uuid4(), OperationStatus.SUCCEEDED, attempts=1)


@pytest.mark.asyncio
async def test_finish_missing_execution_raises(repository: OperationRepository) -> None:
    with pytest.raises(KeyError):
        await repository.finish_execution(uuid4(), OperationStatus.SUCCEEDED)


@pytest.mark.asyncio
async def test_finish_execution_sets_completed_at(repository: OperationRepository) -> None:
    execution_id = await repository.create_execution("wf", "acct", {})
    await repository.finish_execution(execution_id, OperationStatus.SUCCEEDED)
    view = await repository.get_execution(execution_id)
    assert view is not None
    assert view.status == OperationStatus.SUCCEEDED
    assert view.completed_at is not None


@pytest.mark.asyncio
async def test_mark_execution_running_clears_completion(repository: OperationRepository) -> None:
    execution_id = await repository.create_execution("wf", "acct", {})
    await repository.finish_execution(execution_id, OperationStatus.FAILED)
    await repository.mark_execution_running(execution_id)
    view = await repository.get_execution(execution_id)
    assert view is not None
    assert view.status == OperationStatus.RUNNING
    assert view.completed_at is None


@pytest.mark.asyncio
async def test_action_statuses_returns_latest_per_action(
    repository: OperationRepository,
) -> None:
    execution_id = await repository.create_execution("wf", "acct", {})
    operation_id = await repository.create_operation(execution_id, "step", "resolve_target")
    await repository.update_operation(operation_id, OperationStatus.RUNNING, attempts=1)
    await repository.update_operation(operation_id, OperationStatus.SUCCEEDED, attempts=1)
    statuses = await repository.action_statuses(execution_id)
    assert statuses == {"step": OperationStatus.SUCCEEDED}


@pytest.mark.asyncio
async def test_list_executions_orders_newest_first(repository: OperationRepository) -> None:
    first = await repository.create_execution("first", "acct", {})
    second = await repository.create_execution("second", "acct", {})
    listed = await repository.list_executions(limit=10)
    ids = [view.execution_id for view in listed]
    assert set(ids) == {first, second}
    assert listed[0].created_at >= listed[-1].created_at


@pytest.mark.asyncio
async def test_list_executions_respects_limit(repository: OperationRepository) -> None:
    for index in range(3):
        await repository.create_execution(f"wf{index}", "acct", {})
    listed = await repository.list_executions(limit=2)
    assert len(listed) == 2


@pytest.mark.asyncio
async def test_operations_ordered_by_creation(repository: OperationRepository) -> None:
    execution_id = await repository.create_execution("wf", "acct", {})
    await repository.create_operation(execution_id, "first", "resolve_target")
    await repository.create_operation(execution_id, "second", "resolve_target")
    operations = await repository.operations(execution_id)
    assert [op.action_id for op in operations] == ["first", "second"]
