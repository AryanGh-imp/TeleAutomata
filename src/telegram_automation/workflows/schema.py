from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

ActionType = Literal[
    "create_group",
    "create_channel",
    "update_entity",
    "send_message",
    "resolve_target",
    "pin_message",
    "unpin_message",
    "edit_message",
    "delete_message",
    "forward_message",
    "reply_message",
    "mark_read",
    "archive_chat",
    "mark_unread",
    "mute_dialog",
    "unmute_dialog",
    "pin_dialog",
    "unpin_dialog",
    "join_channel",
    "leave_channel",
    "join_group",
    "leave_group",
    "add_members",
    "remove_members",
    "ban_members",
    "unban_members",
    "mute_members",
    "unmute_members",
    "restrict_members",
]


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=1.0, ge=0.1, le=300)
    max_delay_seconds: float = Field(default=60.0, ge=0.1, le=3600)

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> "RetryPolicy":
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be >= initial_delay_seconds")
        return self


class ActionDefinition(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    type: ActionType
    with_: dict[str, Any] = Field(alias="with", default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    continue_on_error: bool = False
    retry: RetryPolicy | None = None


class WorkflowDefinition(BaseModel):
    version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    account: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    dry_run: bool = False
    actions: list[ActionDefinition] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "WorkflowDefinition":
        ids = [action.id for action in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("action IDs must be unique")
        known = set(ids)
        for action in self.actions:
            missing = set(action.depends_on) - known
            if missing:
                raise ValueError(
                    f"action '{action.id}' has unknown dependencies: {sorted(missing)}"
                )
            if action.id in action.depends_on:
                raise ValueError(f"action '{action.id}' cannot depend on itself")
        self._assert_acyclic()
        return self

    @cached_property
    def actions_by_id(self) -> dict[str, ActionDefinition]:
        """Index actions by id for O(1) lookup during execution and reporting."""
        return {action.id: action for action in self.actions}

    def _assert_acyclic(self) -> None:
        dependencies = {a.id: set(a.depends_on) for a in self.actions}
        resolved: set[str] = set()
        while dependencies:
            ready = {name for name, deps in dependencies.items() if deps <= resolved}
            if not ready:
                raise ValueError("workflow dependencies contain a cycle")
            resolved |= ready
            for name in ready:
                del dependencies[name]


def load_workflow(path: Path) -> WorkflowDefinition:
    """Load and validate a workflow YAML file without allowing arbitrary YAML objects."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow root must be a mapping")
    return WorkflowDefinition.model_validate(data)
