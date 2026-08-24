"""Terminal presentation layer for the CLI.

This module owns everything about *how* CLI output looks: the Rich consoles, the
colour theme, and pure functions that turn domain read models into Rich
renderables. Command logic in :mod:`teleautomata.cli.main` stays free of styling
and simply prints what these functions return.

Two design rules keep scripted and non-interactive use reliable:

* Output is written through two module-level consoles (``out_console`` for
  results, ``err_console`` for errors). :func:`configure` rebinds them for the
  current invocation so that a real terminal keeps auto-detected width and
  colour, while pipes, CI, and tests get a wide, colourless console — Rich never
  truncates an execution ID and no ANSI leaks into captured output.
* Data tables drop their borders when not interactive, so piped output is clean,
  column-aligned text. The values a caller needs (execution IDs, statuses,
  counts) are always present regardless of styling.
"""

from collections.abc import Sequence
from datetime import datetime

from rich.box import ROUNDED, SIMPLE_HEAVY, Box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from teleautomata.domain.models import (
    ExecutionRecordView,
    ExecutionSummary,
    OperationRecordView,
    OperationStatus,
)
from teleautomata.workflows.schema import WorkflowDefinition

# Semantic styles, prefixed to avoid clashing with Rich's built-in style names.
# Exported so callers that build their own Console (e.g. tests) resolve the same
# ``ta.*`` names these render functions embed.
THEME = Theme(
    {
        "ta.success": "bold green",
        "ta.error": "bold red",
        "ta.warning": "yellow",
        "ta.info": "cyan",
        "ta.muted": "dim",
        "ta.label": "bold",
        "ta.title": "bold",
    }
)

_STATUS_STYLE: dict[OperationStatus, str] = {
    OperationStatus.SUCCEEDED: "ta.success",
    OperationStatus.FAILED: "ta.error",
    OperationStatus.SKIPPED: "ta.muted",
    OperationStatus.RUNNING: "ta.info",
    OperationStatus.PENDING: "ta.muted",
    OperationStatus.RETRY_SCHEDULED: "ta.warning",
}

_STATUS_GLYPH: dict[OperationStatus, str] = {
    OperationStatus.SUCCEEDED: "✓",
    OperationStatus.FAILED: "✗",
    OperationStatus.SKIPPED: "○",
    OperationStatus.RUNNING: "•",
    OperationStatus.PENDING: "·",
    OperationStatus.RETRY_SCHEDULED: "↻",
}

_MESSAGE_GLYPH = {"success": "✓", "warning": "⚠", "error": "✗", "info": "•"}

# Wide enough that multi-column tables (notably 36-char execution IDs) never
# truncate when Rich cannot detect a real terminal width.
_NONINTERACTIVE_WIDTH = 200

out_console = Console(theme=THEME)
err_console = Console(theme=THEME, stderr=True)
_interactive = True


def configure(*, interactive: bool) -> None:
    """Rebind the module consoles for the current invocation.

    Called once per command from the CLI callback. ``interactive`` should be the
    stdout TTY state: interactive terminals keep auto width and colour, while
    everything else gets a wide, borderless, colourless presentation.
    """
    global out_console, err_console, _interactive
    _interactive = interactive
    width = None if interactive else _NONINTERACTIVE_WIDTH
    out_console = Console(theme=THEME, width=width)
    err_console = Console(theme=THEME, width=width, stderr=True)


def format_timestamp(value: datetime | None) -> str:
    """Render a stored UTC timestamp compactly, or an em dash when absent."""
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M:%S")


def status_text(status: OperationStatus) -> Text:
    """A status value with its glyph, coloured by outcome."""
    glyph = _STATUS_GLYPH.get(status, "•")
    return Text(f"{glyph} {status.value}", style=_STATUS_STYLE.get(status, "ta.info"))


def message(kind: str, text: str) -> Text:
    """A single status line, e.g. ``✓ Initialized …`` (kind: success/warning/error/info)."""
    glyph = _MESSAGE_GLYPH.get(kind, "•")
    return Text.assemble((f"{glyph} ", f"ta.{kind}"), text)


def _table_box() -> Box | None:
    return SIMPLE_HEAVY if _interactive else None


def _kv_table() -> Table:
    """A borderless two-column grid for panel bodies (label → value)."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="ta.label", justify="right")
    grid.add_column()
    return grid


def _data_table() -> Table:
    """An empty data table styled for the current interactivity; add columns to it."""
    return Table(box=_table_box(), header_style="ta.label", expand=False, pad_edge=False)


def validation_panel(definition: WorkflowDefinition) -> Panel:
    edges = sum(len(action.depends_on) for action in definition.actions)
    body = _kv_table()
    body.add_row("Name", definition.name)
    body.add_row("Account", definition.account)
    body.add_row("Actions", str(len(definition.actions)))
    body.add_row("Dependencies", str(edges))
    body.add_row("Mode", "dry run" if definition.dry_run else "live")
    return Panel(
        body,
        title=Text("✓ Workflow valid", style="ta.success"),
        border_style="ta.success",
        box=ROUNDED,
        expand=False,
    )


def _summary_counts(summary: ExecutionSummary) -> Text:
    return Text.assemble(
        (f"{summary.succeeded} succeeded", "ta.success" if summary.succeeded else "ta.muted"),
        ("  ·  ", "ta.muted"),
        (f"{summary.failed} failed", "ta.error" if summary.failed else "ta.muted"),
        ("  ·  ", "ta.muted"),
        (f"{summary.skipped} skipped", "ta.warning" if summary.skipped else "ta.muted"),
    )


def execution_summary_panel(definition: WorkflowDefinition, summary: ExecutionSummary) -> Panel:
    if summary.status == OperationStatus.FAILED:
        glyph, word, style = "✗", "failed", "ta.error"
    elif summary.status == OperationStatus.SUCCEEDED:
        glyph, word, style = "✓", "completed", "ta.success"
    else:
        glyph, word, style = "•", summary.status.value, "ta.info"
    body = _kv_table()
    body.add_row("Workflow", definition.name)
    body.add_row("Account", definition.account)
    body.add_row("Execution", str(summary.execution_id))
    body.add_row("Result", _summary_counts(summary))
    if definition.dry_run:
        body.add_row("Mode", "dry run")
    return Panel(
        body,
        title=Text(f"{glyph} Workflow {word}", style=style),
        border_style=style,
        box=ROUNDED,
        expand=False,
    )


def history_table(executions: Sequence[ExecutionRecordView]) -> Table:
    table = _data_table()
    table.add_column("Started", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Workflow", overflow="fold")
    table.add_column("Account", overflow="fold")
    table.add_column("Execution ID", no_wrap=True)
    table.add_column("Completed", no_wrap=True)
    for record in executions:
        table.add_row(
            format_timestamp(record.created_at),
            status_text(record.status),
            record.workflow_name,
            record.account,
            str(record.execution_id),
            format_timestamp(record.completed_at),
        )
    return table


def status_report(
    execution: ExecutionRecordView, operations: Sequence[OperationRecordView]
) -> Group:
    header = _kv_table()
    header.add_row("Execution", str(execution.execution_id))
    header.add_row("Workflow", execution.workflow_name)
    header.add_row("Account", execution.account)
    header.add_row("Status", status_text(execution.status))
    header.add_row("Started", format_timestamp(execution.created_at))
    header.add_row("Completed", format_timestamp(execution.completed_at))
    panel = Panel(
        header,
        title=Text("Execution detail", style="ta.title"),
        border_style="ta.info",
        box=ROUNDED,
        expand=False,
    )
    if not operations:
        return Group(panel, message("info", "This execution has no recorded actions."))
    table = _data_table()
    table.add_column("Action", overflow="fold")
    table.add_column("Type", overflow="fold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Attempts", justify="right", no_wrap=True)
    table.add_column("Error", overflow="fold")
    for op in operations:
        table.add_row(
            op.action_id,
            op.action_type,
            status_text(op.status),
            str(op.attempts),
            op.error_code or "—",
        )
    return Group(panel, table)


def workflow_list_table(
    rows: Sequence[tuple[str, WorkflowDefinition | None, str | None]],
) -> Table:
    table = _data_table()
    table.add_column("File", overflow="fold")
    table.add_column("Name", overflow="fold")
    table.add_column("Account", overflow="fold")
    table.add_column("Actions", justify="right", no_wrap=True)
    table.add_column("Dry run", no_wrap=True)
    table.add_column("Status", overflow="fold")
    for filename, definition, error in rows:
        if definition is None:
            table.add_row(filename, "—", "—", "—", "—", Text(f"invalid: {error}", style="ta.error"))
        else:
            table.add_row(
                filename,
                definition.name,
                definition.account,
                str(len(definition.actions)),
                "yes" if definition.dry_run else "no",
                Text("valid", style="ta.success"),
            )
    return table


def error_panel(title: str, detail: str, *, hint: str | None = None) -> Panel:
    body: RenderableType = Text(detail)
    if hint:
        body = Group(Text(detail), Text.assemble(("\nHint: ", "ta.info"), (hint, "ta.muted")))
    return Panel(
        body,
        title=Text(f"✗ {title}", style="ta.error"),
        border_style="ta.error",
        box=ROUNDED,
        expand=False,
    )
