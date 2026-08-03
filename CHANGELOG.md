# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
- Substantially expanded test suite covering action dispatch and validation,
  persistence lifecycle and resume queries, scheduling/backoff, schema
  validation, flood-wait handling, resume idempotency, and the CLI.

### Changed

- Dry runs no longer require Telegram credentials or a live session; a plan can
  be inspected entirely offline.
- Adopted `ruff format` across the codebase and resolved all lint and strict
  `mypy` findings.

## [0.1.0]

### Added

- Initial safety-first, workflow-driven Telegram automation framework: ports and
  adapters architecture, async workflow engine with DAG dependency ordering,
  per-action retry with exponential backoff and jitter, flood-wait handling,
  dry-run and resume support, per-account rate limiting, durable SQLAlchemy
  persistence, a Telethon gateway adapter, structured logging, and a Typer CLI.
