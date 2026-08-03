import pytest
from pydantic import ValidationError

from teleautomata.workflows.schema import WorkflowDefinition, load_workflow


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


def test_rejects_unknown_dependency() -> None:
    with pytest.raises(ValidationError, match="unknown dependencies"):
        WorkflowDefinition.model_validate(
            {
                "name": "test",
                "account": "a",
                "actions": [
                    {
                        "id": "one",
                        "type": "resolve_target",
                        "depends_on": ["ghost"],
                        "with": {"target": "@a"},
                    },
                ],
            }
        )


def test_rejects_self_dependency() -> None:
    with pytest.raises(ValidationError, match="cannot depend on itself"):
        WorkflowDefinition.model_validate(
            {
                "name": "test",
                "account": "a",
                "actions": [
                    {
                        "id": "one",
                        "type": "resolve_target",
                        "depends_on": ["one"],
                        "with": {"target": "@a"},
                    },
                ],
            }
        )


def test_rejects_duplicate_action_ids() -> None:
    with pytest.raises(ValidationError, match="action IDs must be unique"):
        WorkflowDefinition.model_validate(
            {
                "name": "test",
                "account": "a",
                "actions": [
                    {"id": "dup", "type": "resolve_target", "with": {"target": "@a"}},
                    {"id": "dup", "type": "resolve_target", "with": {"target": "@b"}},
                ],
            }
        )


def test_rejects_invalid_account_name() -> None:
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate(
            {
                "name": "test",
                "account": "1-bad-start",
                "actions": [
                    {"id": "one", "type": "resolve_target", "with": {"target": "@a"}},
                ],
            }
        )


def test_actions_by_id_indexes_every_action() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "test",
            "account": "a",
            "actions": [
                {"id": "one", "type": "resolve_target", "with": {"target": "@a"}},
                {
                    "id": "two",
                    "type": "resolve_target",
                    "depends_on": ["one"],
                    "with": {"target": "@b"},
                },
            ],
        }
    )
    index = workflow.actions_by_id
    assert set(index) == {"one", "two"}
    assert index["two"].depends_on == ["one"]


def test_load_workflow_reads_valid_file(tmp_path) -> None:
    path = tmp_path / "wf.yaml"
    path.write_text(
        "version: 1\n"
        "name: from-disk\n"
        "account: primary\n"
        "actions:\n"
        "  - id: one\n"
        "    type: resolve_target\n"
        "    with:\n"
        "      target: '@telegram'\n",
        encoding="utf-8",
    )
    workflow = load_workflow(path)
    assert workflow.name == "from-disk"
    assert workflow.actions[0].id == "one"


def test_load_workflow_rejects_non_mapping_root(tmp_path) -> None:
    path = tmp_path / "wf.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be a mapping"):
        load_workflow(path)


def test_load_workflow_surfaces_validation_errors(tmp_path) -> None:
    path = tmp_path / "wf.yaml"
    path.write_text("name: x\naccount: primary\nactions: []\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_workflow(path)
