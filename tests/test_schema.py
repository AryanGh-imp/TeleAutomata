import pytest
from pydantic import ValidationError

from telegram_automation.workflows.schema import WorkflowDefinition


def test_rejects_dependency_cycle() -> None:
    with pytest.raises(ValidationError, match="cycle"):
        WorkflowDefinition.model_validate(
            {
                "name": "test",
                "account": "a",
                "actions": [
                    {
                        "id": "one",
                        "type": "resolve_target",
                        "depends_on": ["two"],
                        "with": {"target": "a"},
                    },
                    {
                        "id": "two",
                        "type": "resolve_target",
                        "depends_on": ["one"],
                        "with": {"target": "b"},
                    },
                ],
            }
        )


def test_accepts_valid_definition() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "test",
            "account": "a",
            "actions": [
                {"id": "one", "type": "resolve_target", "with": {"target": "@telegram"}},
            ],
        }
    )
    assert workflow.actions[0].id == "one"


def test_rejects_max_delay_below_initial_delay() -> None:
    with pytest.raises(ValidationError, match="max_delay_seconds must be >= initial_delay_seconds"):
        WorkflowDefinition.model_validate(
            {
                "name": "test",
                "account": "a",
                "actions": [
                    {
                        "id": "one",
                        "type": "resolve_target",
                        "with": {"target": "@telegram"},
                        "retry": {
                            "max_attempts": 2,
                            "initial_delay_seconds": 30,
                            "max_delay_seconds": 5,
                        },
                    },
                ],
            }
        )


def test_allows_subsecond_delays_for_fast_testing() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "test",
            "account": "a",
            "actions": [
                {
                    "id": "one",
                    "type": "resolve_target",
                    "with": {"target": "@telegram"},
                    "retry": {
                        "max_attempts": 2,
                        "initial_delay_seconds": 0.1,
                        "max_delay_seconds": 0.2,
                    },
                },
            ],
        }
    )
    assert workflow.actions[0].retry is not None
    assert workflow.actions[0].retry.max_attempts == 2
