# TeleAutomata 1.0.0

TeleAutomata is a safety-first, workflow-driven framework for automating
Telegram groups and channels. It treats Telegram's responses, permissions, and
rate limits as authoritative, and models work as durable, declarative workflows
rather than fire-and-forget scripts.

This is the first stable release. The public API is frozen under
[Semantic Versioning](https://semver.org/); see [PUBLIC_API.md](PUBLIC_API.md).

## Why this release

The goal of 1.0 is not the largest possible feature set — it is a small,
coherent, well-documented foundation that is pleasant to understand, extend, and
contribute to. The architecture is the product; the action library is a
representative, frozen set that demonstrates how to add more.

## What's included

- **Ports-and-adapters architecture.** A pure `domain` core (models, errors, the
  `TelegramGateway` port), an `application` layer (engine + typed action
  registry), and swappable `infrastructure` adapters. Dependencies point inward,
  so the real Telethon adapter is replaced by a fake gateway in tests.
- **Async workflow engine.** DAG dependency ordering, per-action retry with
  exponential backoff and jitter, flood-wait handling, `dry_run`, and `resume`
  of only the actions that did not previously succeed.
- **29 actions across five categories** — entity management, messaging, dialogs,
  membership, and member management — with argument validation, multi-target
  input (inline + CSV), and per-user failure isolation. Documented in full in
  [docs/actions.md](docs/actions.md).
- **Typed action registry** with an import-time drift guard that keeps the
  registry and the `ActionType` schema in lockstep — you cannot half-add an
  action.
- **Durable persistence.** Async SQLAlchemy (SQLite by default, PostgreSQL
  supported) records every execution and action for history, status, and resume.
- **Per-account rate limiting** and conservative safety defaults.
- **Typer CLI** — `init`, `auth`, `validate`, `run`, `resume`, `list`,
  `history`, `status` — with stable exit codes.
- **A small, typed public API.** Import the stable surface from the top-level
  `teleautomata` package (and `teleautomata.errors`); the package ships
  `py.typed`.

## Capabilities at a glance

- Declarative `version: 1` workflow YAML with dependencies, per-action retry
  policies, and `continue_on_error`.
- Offline validation and dry-run planning that require no credentials or network.
- Structured logging that never records credentials or message content.

## Quality

- **Tests:** 123 tests covering action dispatch and validation, the engine's DAG
  and retry/flood-wait paths, persistence and resume queries, scheduling/backoff,
  schema validation, the CLI, and the public API facade. Tests never contact
  Telegram.
- **Static analysis:** `ruff`, `ruff format`, and strict `mypy` are clean;
  Telethon's untyped surface is isolated at the adapter boundary.
- **CI:** the full gate (`ruff`, `ruff format --check`, `mypy`, `pytest`,
  `build`) runs on every push and pull request.

## Breaking changes since pre-1.0

Version 1.0 required a few breaking changes to freeze a clean API. See
[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for details and fixes:

- Package/CLI/distribution renamed `telegram_automation` → `teleautomata`.
- Public API is now the top-level `teleautomata` facade; internal subpackages are
  no longer part of the contract.
- Base exception renamed `TelegramAutomationError` → `TeleAutomataError`.
- `edit_message` body argument renamed `text` → `message`.
- `run` / `resume` exit non-zero only when the run fails as a whole.

## Known limitations (intentional)

These are deliberately out of scope for 1.0 and tracked on the
[roadmap](ROADMAP.md):

- Single-account per worker; no built-in multi-account pooling or rotation.
- No engine control flow (variables, conditionals, loops, templates).
- No built-in scheduler (delayed/recurring runs); trigger runs externally.
- No plugin/entry-point loading yet — actions are added in-tree via the
  documented five-layer pattern.
- The action library is intentionally representative, not exhaustive.

## Getting started

See the [README](README.md) quick start. Requires Python 3.12+.

```bash
pip install teleautomata
teleautomata init
teleautomata validate examples/workflows/create-channel.yaml
```

## Thanks

Contributions are welcome — the [extension guide](docs/extending.md) walks
through adding an action end to end, and new action categories make ideal first
contributions.
