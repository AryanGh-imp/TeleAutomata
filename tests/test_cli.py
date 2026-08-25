import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from rich.console import Console, RenderableType
from typer.testing import CliRunner

import teleautomata.cli.main as main
from teleautomata.cli import presentation as ui
from teleautomata.cli.main import app
from teleautomata.domain.models import (
    ExecutionRecordView,
    ExecutionSummary,
    OperationStatus,
)
from teleautomata.workflows.schema import WorkflowDefinition

runner = CliRunner()

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Strip ANSI styling from captured CLI output.

    Rich colourises option switches — ``--yes`` renders with an escape sequence
    between its two dashes — so a naive ``"--yes" in output`` check fails when
    colour is forced on, as it is in CI. Stripping styles matches what a reader
    sees on screen and keeps help-text assertions colour-independent.
    """
    return _ANSI_RE.sub("", text)


DRY_RUN_WORKFLOW = """
version: 1
name: sample-dry-run
account: primary
dry_run: true
actions:
  - id: create_channel
    type: create_channel
    with:
      title: "Announcements"
      about: "Updates"
      broadcast: true
  - id: verify_channel
    type: resolve_target
    depends_on: [create_channel]
    with:
      target: "@somewhere"
"""

LIVE_WORKFLOW = """
version: 1
name: live-flow
account: primary
dry_run: false
actions:
  - id: resolve
    type: resolve_target
    with:
      target: "@somewhere"
"""


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate settings so tests never read the developer's real .env or data."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/test.sqlite3")
    monkeypatch.setenv("SESSION_DIR", "./sessions")
    return tmp_path


def _write_workflow(
    directory: Path, content: str = DRY_RUN_WORKFLOW, name: str = "workflow.yaml"
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def _extract_execution_id(text: str) -> str:
    match = _UUID_RE.search(text)
    assert match is not None, f"no execution id in output:\n{text}"
    return match.group(0)


# --------------------------------------------------------------------------- #
# Top-level: version, help, information architecture
# --------------------------------------------------------------------------- #


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.stdout


def test_help_lists_every_command_in_groups() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("init", "auth", "validate", "run", "resume", "list", "history", "status"):
        assert command in result.stdout
    # Commands are organised into help panels for readability.
    for group in ("Setup", "Workflows", "Inspection"):
        assert group in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # A bare invocation prints usage rather than doing anything (Typer usage exit).
    assert result.exit_code == 2
    assert "Usage" in result.stdout
    assert "run" in result.stdout


def test_run_help_documents_yes_option() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    help_text = _plain(result.stdout)
    assert "--yes" in help_text
    assert "workflow" in help_text


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #


def test_validate_reports_workflow_details(workspace: Path) -> None:
    path = _write_workflow(workspace)
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 0
    assert "sample-dry-run" in result.stdout
    assert "Workflow valid" in result.stdout
    assert "2" in result.stdout  # action count


def test_validate_invalid_workflow_reports_field_on_stderr(workspace: Path) -> None:
    path = workspace / "bad.yaml"
    path.write_text("version: 1\nname: ''\naccount: primary\nactions: []\n", encoding="utf-8")
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 1
    assert "Invalid workflow" in result.stderr
    # The concrete offending field is named, not a raw traceback.
    assert "name" in result.stderr
    assert "Traceback" not in result.stderr


def test_validate_missing_file_is_usage_error(workspace: Path) -> None:
    result = runner.invoke(app, ["validate", str(workspace / "nope.yaml")])
    assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# list
# --------------------------------------------------------------------------- #


def test_list_reports_valid_and_invalid(workspace: Path) -> None:
    directory = workspace / "flows"
    _write_workflow(directory)
    (directory / "broken.yaml").write_text("name: 3\nnot valid", encoding="utf-8")
    result = runner.invoke(app, ["list", str(directory)])
    assert result.exit_code == 0
    assert "sample-dry-run" in result.stdout
    assert "valid" in result.stdout  # the good file is marked valid
    assert "invalid" in result.stdout  # the broken file is flagged, not fatal


def test_list_marks_dry_run_workflows(workspace: Path) -> None:
    directory = workspace / "flows"
    _write_workflow(directory)
    result = runner.invoke(app, ["list", str(directory)])
    assert result.exit_code == 0
    assert "Dry run" in result.stdout  # column header present
    assert "yes" in result.stdout


def test_list_empty_directory(workspace: Path) -> None:
    directory = workspace / "empty"
    directory.mkdir()
    result = runner.invoke(app, ["list", str(directory)])
    assert result.exit_code == 0
    assert "No workflow files found" in result.stdout


# --------------------------------------------------------------------------- #
# run (dry) — the headline safety path
# --------------------------------------------------------------------------- #


def test_dry_run_executes_without_credentials(workspace: Path) -> None:
    path = _write_workflow(workspace)
    result = runner.invoke(app, ["run", str(path)])
    assert result.exit_code == 0, result.stdout
    assert "succeeded" in result.stdout
    assert "2 skipped" in result.stdout
    assert _UUID_RE.search(result.stdout) is not None


def test_run_failed_status_exits_nonzero(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit code 1 is driven by the run's overall status."""
    path = _write_workflow(workspace)
    failed = ExecutionSummary(
        execution_id=uuid4(), status=OperationStatus.FAILED, succeeded=1, failed=1, skipped=0
    )
    monkeypatch.setattr(main, "_run_workflow", lambda *a, **k: failed)
    result = runner.invoke(app, ["run", str(path)])
    assert result.exit_code == 1
    assert "failed" in result.stdout


def test_run_tolerated_failures_still_exit_zero(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A continue_on_error workflow that finishes SUCCEEDED exits 0 despite failed counts."""
    path = _write_workflow(workspace)
    tolerated = ExecutionSummary(
        execution_id=uuid4(), status=OperationStatus.SUCCEEDED, succeeded=1, failed=2, skipped=0
    )
    monkeypatch.setattr(main, "_run_workflow", lambda *a, **k: tolerated)
    result = runner.invoke(app, ["run", str(path)])
    assert result.exit_code == 0
    assert "2 failed" in result.stdout


def test_run_unexpected_error_shows_panel_without_debug(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_workflow(workspace)

    def boom(*args: object, **kwargs: object) -> ExecutionSummary:
        raise RuntimeError("boom-xyz")

    monkeypatch.setattr(main, "_run_workflow", boom)
    result = runner.invoke(app, ["run", str(path)])
    assert result.exit_code == 1
    assert "Unexpected error" in result.stderr
    assert "boom-xyz" in result.stderr
    assert "--debug" in result.stderr


def test_run_debug_reraises_unexpected_error(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_workflow(workspace)

    def boom(*args: object, **kwargs: object) -> ExecutionSummary:
        raise RuntimeError("boom-xyz")

    monkeypatch.setattr(main, "_run_workflow", boom)
    result = runner.invoke(app, ["--debug", "run", str(path)])
    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)


# --------------------------------------------------------------------------- #
# Live-run confirmation
# --------------------------------------------------------------------------- #


def test_live_run_requires_confirmation_when_interactive(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_workflow(workspace, content=LIVE_WORKFLOW)
    monkeypatch.setattr(main, "_stdin_is_tty", lambda: True)
    result = runner.invoke(app, ["run", str(path)], input="n\n")
    assert result.exit_code == 1
    assert "live account 'primary'" in result.stdout  # the prompt was shown


def test_live_run_yes_flag_skips_confirmation(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--yes bypasses the prompt; the run then fails cleanly on missing credentials."""
    path = _write_workflow(workspace, content=LIVE_WORKFLOW)
    monkeypatch.setattr(main, "_stdin_is_tty", lambda: True)
    result = runner.invoke(app, ["run", str(path), "--yes"])
    assert result.exit_code == 1
    assert "TELEGRAM_API_ID" in result.stderr
    assert "y/N" not in result.stdout  # no prompt was shown


def test_live_run_non_interactive_proceeds_without_prompt(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pipes/CI must not hang on a prompt; they proceed as before (here: missing creds)."""
    path = _write_workflow(workspace, content=LIVE_WORKFLOW)
    monkeypatch.setattr(main, "_stdin_is_tty", lambda: False)
    result = runner.invoke(app, ["run", str(path)])
    assert result.exit_code == 1
    assert "TELEGRAM_API_ID" in result.stderr


# --------------------------------------------------------------------------- #
# history / status
# --------------------------------------------------------------------------- #


def test_history_empty_database(workspace: Path) -> None:
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "No executions recorded yet." in result.stdout


def test_history_and_status_reflect_a_dry_run(workspace: Path) -> None:
    path = _write_workflow(workspace)
    run_result = runner.invoke(app, ["run", str(path)])
    assert run_result.exit_code == 0, run_result.stdout
    execution_id = _extract_execution_id(run_result.stdout)

    history = runner.invoke(app, ["history"])
    assert history.exit_code == 0
    assert "sample-dry-run" in history.stdout
    assert execution_id in history.stdout  # full id is never truncated

    status = runner.invoke(app, ["status", execution_id])
    assert status.exit_code == 0
    assert "create_channel" in status.stdout
    assert "verify_channel" in status.stdout
    assert "skipped" in status.stdout


def test_status_unknown_execution_exits_nonzero(workspace: Path) -> None:
    result = runner.invoke(app, ["status", "00000000-0000-0000-0000-000000000000"])
    assert result.exit_code == 1
    assert "No execution found" in result.stderr


def test_resume_reports_summary_for_completed_dry_run(workspace: Path) -> None:
    path = _write_workflow(workspace)
    run_result = runner.invoke(app, ["run", str(path)])
    execution_id = _extract_execution_id(run_result.stdout)
    result = runner.invoke(app, ["resume", str(path), execution_id])
    assert result.exit_code == 0
    assert execution_id in result.stdout


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #


def test_init_creates_runtime_and_reports_success(workspace: Path) -> None:
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Initialized" in result.stdout
    assert (workspace / "sessions").is_dir()


# --------------------------------------------------------------------------- #
# Presentation layer (formatting is independent of a terminal)
# --------------------------------------------------------------------------- #


def _render(renderable: RenderableType, width: int = 200) -> str:
    """Render as the CLI would: the module theme, wide, no ANSI (as when piped)."""
    buffer = StringIO()
    console = Console(file=buffer, width=width, force_terminal=False, no_color=True, theme=ui.THEME)
    console.print(renderable)
    return buffer.getvalue()


def test_execution_summary_panel_contains_id_and_counts() -> None:
    summary = ExecutionSummary(
        execution_id=uuid4(), status=OperationStatus.SUCCEEDED, succeeded=3, failed=0, skipped=1
    )
    rendered = _render(ui.execution_summary_panel(_definition_for_tests(), summary))
    assert str(summary.execution_id) in rendered
    assert "3 succeeded" in rendered
    assert "1 skipped" in rendered
    assert "completed" in rendered


def test_history_table_preserves_full_execution_id() -> None:
    execution = ExecutionRecordView(
        execution_id=uuid4(),
        workflow_name="demo",
        account="primary",
        status=OperationStatus.SUCCEEDED,
        created_at=datetime(2026, 8, 24, 12, 0, tzinfo=UTC),
        completed_at=datetime(2026, 8, 24, 12, 1, tzinfo=UTC),
    )
    rendered = _render(ui.history_table([execution]))
    assert str(execution.execution_id) in rendered  # not truncated by the table
    assert "demo" in rendered
    assert "succeeded" in rendered


def test_status_text_uses_outcome_glyphs() -> None:
    assert "✓" in _render(ui.status_text(OperationStatus.SUCCEEDED))
    assert "✗" in _render(ui.status_text(OperationStatus.FAILED))


def test_workflow_list_table_flags_invalid_rows() -> None:
    rows: list[tuple[str, WorkflowDefinition | None, str | None]] = [
        ("broken.yaml", None, "name: bad")
    ]
    rendered = _render(ui.workflow_list_table(rows))
    assert "broken.yaml" in rendered
    assert "invalid" in rendered
    assert "name: bad" in rendered


def _definition_for_tests() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "version": 1,
            "name": "demo",
            "account": "primary",
            "dry_run": True,
            "actions": [{"id": "a", "type": "resolve_target", "with": {"target": "@x"}}],
        }
    )
