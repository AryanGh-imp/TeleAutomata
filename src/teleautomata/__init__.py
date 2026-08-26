"""Workflow-driven Telegram automation with explicit safety controls.

This module is the public API. Import the stable surface from here (or from
:mod:`teleautomata.errors` for the exception family) rather than from the
internal ``domain`` / ``application`` / ``workflows`` subpackages, whose layout
may change between releases. See ``PUBLIC_API.md`` for the stability contract.
"""

from teleautomata.application.actions import execute_action, registry
from teleautomata.application.engine import WorkflowEngine
from teleautomata.domain.errors import (
    PermanentActionError,
    RateLimitError,
    TeleAutomataError,
    TransientActionError,
)
from teleautomata.domain.models import (
    ActionResult,
    ExecutionRecordView,
    ExecutionSummary,
    OperationRecordView,
    OperationStatus,
)
from teleautomata.domain.ports import TelegramGateway
from teleautomata.workflows.schema import (
    ActionDefinition,
    ActionType,
    RetryPolicy,
    WorkflowDefinition,
    load_workflow,
)

__version__ = "1.0.2"

__all__ = [
    "__version__",
    # Workflow authoring and validation.
    "load_workflow",
    "WorkflowDefinition",
    "ActionDefinition",
    "RetryPolicy",
    "ActionType",
    # Execution.
    "WorkflowEngine",
    "execute_action",
    "registry",
    # Gateway port — the extension point for custom backends.
    "TelegramGateway",
    # Results and status read models.
    "OperationStatus",
    "ActionResult",
    "ExecutionSummary",
    "ExecutionRecordView",
    "OperationRecordView",
    # Error taxonomy (also grouped in teleautomata.errors).
    "TeleAutomataError",
    "PermanentActionError",
    "TransientActionError",
    "RateLimitError",
]
