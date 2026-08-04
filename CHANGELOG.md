# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-04

First stable release. The public API is now frozen under Semantic Versioning;
see [PUBLIC_API.md](PUBLIC_API.md).

### Added

- A top-level public API: `WorkflowEngine`, `load_workflow`, the workflow/action
  schema models, the `TelegramGateway` port, the result/status read models, and
  the error taxonomy are now importable directly from `teleautomata` (and the
  exceptions from `teleautomata.errors`). These shallow paths are the stable
  contract; the internal `domain` / `application` / `workflows` subpackages they
  re-export from are no longer part of the public API and may be reorganized.
- Member restriction actions: `mute_members`, `unmute_members`, and
  `restrict_members`. `restrict_members` takes a validated `permissions` mapping
  of Telegram rights to booleans (`false` removes a right); `view_messages` is
  rejected since a full ban is owned by `ban_members`. All three share the
  multi-target input and per-user failure isolation of the other member actions.
- `unpin_message` now accepts an optional `message_id` to unpin a single
  message; omitting it still unpins every pinned message.

- `list`, `history`, and `status` CLI commands for read-only introspection of
  workflow files and recorded executions.
- `ExecutionRecordView` and `OperationRecordView` read models, backed by
  `list_executions`, `get_execution`, and `operations` repository queries.
- `NullGateway`, a guard gateway used for dry runs that raises if any Telegram
  action is attempted.
- `continue_on_error` on actions: a tolerated failure no longer blocks the
  workflow, while still being reported in the per-action failure count.
- Cross-field validation on `RetryPolicy` ensuring
  `max_delay_seconds >= initial_delay_seconds`.
- Project documentation: `LICENSE` (MIT), `CONTRIBUTING.md`, this changelog, and
  `docs/` topics for the workflow engine, Telegram integration, security,
  testing, and troubleshooting.
- `SECURITY.md` and `CODE_OF_CONDUCT.md` governance files, and a `py.typed`
  marker so the package ships its type information (PEP 561).
- Packaging metadata for PyPI: trove classifiers and keywords.
- Substantially expanded test suite covering action dispatch and validation,
  persistence lifecycle and resume queries, scheduling/backoff, schema
  validation, flood-wait handling, resume idempotency, and the CLI.

### Changed

- **Breaking:** renamed the base exception `TelegramAutomationError` to
  `TeleAutomataError`, matching the package name. Code that catches the base
  class must update the import; the `PermanentActionError` /
  `TransientActionError` / `RateLimitError` subclasses are unchanged.
- **Breaking:** the `edit_message` action's body argument is now `message`
  (was `text`), consistent with `send_message` and `reply_message`.
- Dry runs no longer require Telegram credentials or a live session; a plan can
  be inspected entirely offline.
- `run` and `resume` now exit non-zero only when the run failed as a whole (an
  untolerated action failed). A failure tolerated by `continue_on_error` is
  reported in the summary counts but no longer forces a non-zero exit.
- Adopted `ruff format` across the codebase and resolved all lint and strict
  `mypy` findings.

## [0.1.0]

### Added

- Initial safety-first, workflow-driven Telegram automation framework: ports and
  adapters architecture, async workflow engine with DAG dependency ordering,
  per-action retry with exponential backoff and jitter, flood-wait handling,
  dry-run and resume support, per-account rate limiting, durable SQLAlchemy
  persistence, a Telethon gateway adapter, structured logging, and a Typer CLI.
