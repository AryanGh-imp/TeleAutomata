# Roadmap

TeleAutomata is an open-source Telegram automation framework built on a
ports-and-adapters core with a typed workflow engine. This roadmap is a planning
document, not a contract: scope is chosen to make each release coherent and
polished rather than exhaustive.

**Guiding principle:** the architecture is the product, not the number of
actions. A representative, well-designed action library that shows how to add
more is worth more than an exhaustive one. Simplicity, maintainability, and
readability come before feature count. Work lands in small verified increments
(green across `ruff`, `ruff format`, `mypy`, `pytest`, `build`) with logical
commits.

## Status

Version 1.0 is the first stable release. The core is complete and the public API
is frozen under [Semantic Versioning](https://semver.org/) — see
[PUBLIC_API.md](PUBLIC_API.md) for the stability contract. Everything below the
"Shipped in 1.0" section is intentionally deferred: each item builds on a
baseline that already exists and is sufficient for 1.0, so postponing it costs
nothing now.

## Shipped in 1.0

- **Architecture** — ports and adapters; dependencies point inward, so the real
  Telethon adapter is swappable for a fake gateway in tests.
- **Engine** — async workflow engine with DAG dependency ordering, per-action
  retry with exponential backoff and jitter, flood-wait handling, dry-run, and
  resume.
- **Persistence** — durable async SQLAlchemy (SQLite) execution/operation
  records; per-account rate limiting.
- **Registry** — typed action registry with an import-time drift guard that
  keeps the registry and the `ActionType` schema in lockstep.
- **Actions** — 29 actions across five categories (entity management, messaging,
  dialogs, membership, member management), **frozen** as a representative set
  with multi-target input and per-user failure isolation.
- **CLI** — Typer commands: `init`, `auth`, `validate`, `run`, `resume`, `list`,
  `history`, `status`.
- **Public API** — a small top-level facade (`teleautomata` and
  `teleautomata.errors`); PEP 561 typed (`py.typed`).
- **Documentation** — README plus `docs/`: architecture, API, workflow engine,
  actions, CLI, Telegram integration, configuration, security, testing,
  development, extending, FAQ, troubleshooting.
- **Governance** — LICENSE (MIT), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT,
  CHANGELOG, PUBLIC_API.
- **CI** — `ruff`, `ruff format --check`, `mypy`, `pytest`, and `build` on every
  push and pull request; hatchling wheel + sdist.

## Planned for v1.1

Useful, non-breaking, and additive on top of the stable 1.0 foundation.

- A few more action categories as demonstrations: chat settings
  (title/description/username/photo), admin promote/demote, profile updates.
- CLI conveniences: `doctor`, `plan`, richer `history` filtering.
- Observability: execution timeline and retry/rate-limit statistics views
  (structured JSON logging already present).

## Future (post-1.0, major subsystems)

Larger subsystems that materially increase complexity. These define the
post-release direction and community roadmap; several make ideal contributions.

- **Plugin system** — external packages registering actions via entry points
  (the registry is already the seam; it is kept plugin-friendly).
- **Engine control flow** — variables/outputs, if/else, foreach, templates,
  nested workflows.
- **Multi-account** — registry, pools, rotation, health, concurrent execution.
- **Scheduler** — delayed, recurring, cron, interval; pause/resume/cancel.
- **Database** — PostgreSQL parity, Alembic migration baseline, cleanup jobs.
- **Reliability** — checkpoints, crash recovery, dead-letter queue, graceful
  shutdown (retry + resume already present).
- **Security** — encrypted secrets and providers, session encryption (env-only
  secrets + gitignored sessions already present).
- **Extended action library** — history/export, folders, sessions, contacts,
  media/album/poll messaging.

## Contributing to the roadmap

New action categories and CLI conveniences make ideal first contributions: the
five-layer pattern (schema → port → registry handler → Telethon adapter → null
gateway) is documented end to end in the [extension guide](docs/extending.md),
and the drift guard keeps additions honest. Larger subsystems above are best
discussed in an issue first so the design stays coherent with the core.
