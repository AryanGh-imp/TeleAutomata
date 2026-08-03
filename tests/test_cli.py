import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from telegram_automation.cli.main import app

runner = CliRunner()

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


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate settings so tests never read the developer's real .env or data."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/test.sqlite3")
    monkeypatch.setenv("SESSION_DIR", "./sessions")
    return tmp_path


def _write_workflow(directory: Path, name: str = "workflow.yaml") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(DRY_RUN_WORKFLOW, encoding="utf-8")
    return path


def test_validate_reports_action_count(workspace: Path) -> None:
    path = _write_workflow(workspace)
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 0
    assert "sample-dry-run" in result.stdout
    assert "2 action(s)" in result.stdout


def test_list_reports_dry_run_flag(workspace: Path) -> None:
    directory = workspace / "flows"
    _write_workflow(directory)
    result = runner.invoke(app, ["list", str(directory)])
    assert result.exit_code == 0
    assert "sample-dry-run" in result.stdout
    assert "[dry_run]" in result.stdout


def test_list_flags_invalid_workflow(workspace: Path) -> None:
    directory = workspace / "flows"
    directory.mkdir(parents=True)
    (directory / "broken.yaml").write_text("name: 3\nnot valid", encoding="utf-8")
    result = runner.invoke(app, ["list", str(directory)])
    assert result.exit_code == 0
    assert "INVALID" in result.stdout


def test_dry_run_executes_without_credentials(workspace: Path) -> None:
    """The headline safety property: inspecting a plan needs no Telegram login."""
    path = _write_workflow(workspace)
    result = runner.invoke(app, ["run", str(path)])
    assert result.exit_code == 0, result.stdout
    assert "succeeded" in result.stdout
    assert "skipped=2" in result.stdout


def test_history_and_status_reflect_a_dry_run(workspace: Path) -> None:
    path = _write_workflow(workspace)
    run_result = runner.invoke(app, ["run", str(path)])
    assert run_result.exit_code == 0, run_result.stdout

    history = runner.invoke(app, ["history"])
    assert history.exit_code == 0
    assert "sample-dry-run" in history.stdout

    match = re.search(r"Execution ([0-9a-f-]{36})", run_result.stdout)
    assert match is not None
    execution_id = match.group(1)

    status = runner.invoke(app, ["status", execution_id])
    assert status.exit_code == 0
    assert "create_channel" in status.stdout
    assert "verify_channel" in status.stdout
    assert "skipped" in status.stdout


def test_history_empty_database(workspace: Path) -> None:
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "No executions recorded yet." in result.stdout


def test_status_unknown_execution_exits_nonzero(workspace: Path) -> None:
    result = runner.invoke(app, ["status", "00000000-0000-0000-0000-000000000000"])
    assert result.exit_code == 1
    assert "No execution found" in result.stdout
