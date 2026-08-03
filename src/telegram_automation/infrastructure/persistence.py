import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from telegram_automation.domain.models import OperationStatus


class Base(DeclarativeBase):
    pass


class ExecutionRecord(Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationRecord(Base):
    __tablename__ = "operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"), index=True)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_json: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OperationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def create_execution(
        self, workflow_name: str, account: str, definition: dict[str, Any]
    ) -> UUID:
        execution_id = uuid4()
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            session.add(
                ExecutionRecord(
                    id=str(execution_id),
                    workflow_name=workflow_name,
                    account=account,
                    status=OperationStatus.RUNNING,
                    definition_json=json.dumps(definition),
                    created_at=now,
                )
            )
        return execution_id

    async def create_operation(self, execution_id: UUID, action_id: str, action_type: str) -> UUID:
        operation_id = uuid4()
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            session.add(
                OperationRecord(
                    id=str(operation_id),
                    execution_id=str(execution_id),
                    action_id=action_id,
                    action_type=action_type,
                    status=OperationStatus.PENDING,
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )
        return operation_id

    async def update_operation(
        self,
        operation_id: UUID,
        status: OperationStatus,
        *,
        attempts: int,
        output: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        async with self._sessions.begin() as session:
            record = await session.get(OperationRecord, str(operation_id))
            if record is None:
                raise KeyError(f"operation {operation_id} not found")
            record.status, record.attempts, record.updated_at = status, attempts, datetime.now(UTC)
            record.output_json = json.dumps(output) if output is not None else None
            record.error_code, record.error_detail = error_code, error_detail

    async def finish_execution(self, execution_id: UUID, status: OperationStatus) -> None:
        async with self._sessions.begin() as session:
            record = await session.get(ExecutionRecord, str(execution_id))
            if record is None:
                raise KeyError(f"execution {execution_id} not found")
            record.status, record.completed_at = status, datetime.now(UTC)

    async def mark_execution_running(self, execution_id: UUID) -> None:
        async with self._sessions.begin() as session:
            record = await session.get(ExecutionRecord, str(execution_id))
            if record is None:
                raise KeyError(f"execution {execution_id} not found")
            record.status, record.completed_at = OperationStatus.RUNNING, None

    async def action_statuses(self, execution_id: UUID) -> dict[str, OperationStatus]:
        """Return the latest status for each action in an execution."""
        async with self._sessions() as session:
            statement = (
                select(OperationRecord)
                .where(OperationRecord.execution_id == str(execution_id))
                .order_by(OperationRecord.updated_at.desc())
            )
            records = list((await session.scalars(statement)).all())
        latest: dict[str, OperationStatus] = {}
        for record in records:
            latest.setdefault(record.action_id, OperationStatus(record.status))
        return latest

    async def operation_statuses(self, execution_id: UUID) -> list[OperationStatus]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(OperationRecord.status).where(
                    OperationRecord.execution_id == str(execution_id)
                )
            )
            return [OperationStatus(status) for status in rows]


def build_engine(database_url: str) -> AsyncEngine:
    if database_url.startswith("sqlite"):
        database_path = database_url.removeprefix("sqlite+aiosqlite:///")
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(database_url, pool_pre_ping=True)


async def initialize_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
