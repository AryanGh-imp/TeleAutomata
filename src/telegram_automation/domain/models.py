from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ActionResult:
    status: OperationStatus
    output: dict[str, Any]
    error_code: str | None = None
    retry_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    """Outcome of a workflow run.

    ``status`` is ``FAILED`` only when an action failed without
    ``continue_on_error``; ``failed`` counts every failed action, including
    tolerated ones, so reporting stays faithful to what actually happened.
    """

    execution_id: UUID
    status: OperationStatus
    succeeded: int
    failed: int
    skipped: int
