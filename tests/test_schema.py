import pytest
from pydantic import ValidationError

from telegram_automation.workflows.schema import WorkflowDefinition


def test_rejects_dependency_cycle() -> None:
    with pytest.raises(ValidationError, match="cycle"):
        WorkflowDefinition.model_validate({"name": "test", "account": "a", "actions": [
            {"id": "one", "type": "resolve_target", "depends_on": ["two"], "with": {"target": "a"}},
            {"id": "two", "type": "resolve_target", "depends_on": ["one"], "with": {"target": "b"}},
        ]})


def test_accepts_valid_definition() -> None:
    workflow = WorkflowDefinition.model_validate({"name": "test", "account": "a", "actions": [
        {"id": "one", "type": "resolve_target", "with": {"target": "@telegram"}},
    ]})
    assert workflow.actions[0].id == "one"
