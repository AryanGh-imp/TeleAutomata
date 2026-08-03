# Roadmap

TeleAutomata is an open-source Telegram automation framework built on a
ports-and-adapters core with a typed workflow engine. This roadmap is a
planning document, not a contract: scope is chosen to make the first stable
release coherent and polished rather than exhaustive.

**Guiding principle for v1.0:** the architecture is the product, not the number
of actions. A representative, well-designed action library that shows how to add
more is worth more than an exhaustive one. Simplicity, maintainability, and
readability come before feature count. Work lands in small verified increments
(green across `ruff`, `ruff format`, `mypy`, `pytest`, `build`) with logical
commits.

## What is done

- Ports-and-adapters architecture; async workflow engine with DAG ordering,
  per-action retry with backoff + jitter, flood-wait handling, dry-run, resume.
- Durable SQLAlchemy (async SQLite) persistence; per-account rate limiting.
- Typed action registry with an import-time drift guard against the schema.
- 29 actions across five categories: entity creation, messaging, dialogs,
  membership, and member management.
- Typer CLI: init, auth, validate, run, resume, list, history, status.
- Baseline docs and CI (ruff/mypy/pytest/build); hatchling wheel + sdist.

## Status legend

- `[x]` done · `[~]` in progress · `[ ]` not started

## Required before v1.0

These make the release complete, coherent, and pleasant to adopt and extend.

### Action library — frozen as representative

The five implemented categories demonstrate the full pattern (schema → port →
registry handler → Telethon adapter → null gateway, with validation and per-user
failure isolation). The library is **frozen** for v1.0. Actions that map to the
same MTProto call are consolidated, not duplicated (e.g. `kick` →
`remove_members`, `restore` → `unban_members`). New categories are Nice to
have / Future and make ideal first community contributions.

- [x] Entity: create_group, create_channel, update_entity, resolve_target
- [x] Messaging: send/pin/unpin/edit/delete/forward/reply, mark_read, archive_chat
- [x] Dialogs: mark_unread, mute/unmute, pin/unpin
- [x] Membership: join/leave channel, join/leave group
- [x] Members: add/remove/ban/unban/mute/unmute/restrict (multi-target + CSV)

### Documentation — the showcase surface

- [x] README, CONTRIBUTING, CHANGELOG, LICENSE, SECURITY, CODE_OF_CONDUCT
- [x] docs/: architecture, workflow-engine, telegram-integration, configuration,
      security, testing, development, troubleshooting
- [ ] `docs/actions.md` — action reference generated in spirit from the registry:
      every action, its arguments, validation rules, and result shape
- [ ] `docs/cli.md` — command reference for the shipped Typer commands
- [ ] `docs/extending.md` — the flagship guide: add an action across the five
      layers, with the drift guard and testing pattern; explains *why* the
      registry and null gateway exist, not only how
- [ ] `docs/faq.md` — safety model, credentials, dry-run, resume, rate limits

### Quality gate

- [ ] Confirm meaningful coverage on the engine, registry, persistence, and
      flood-wait paths (raise numbers naturally, do not chase a target)
- [ ] Validate full package metadata for PyPI (classifiers, URLs, readme render)

## Nice to have (v1.1)

Useful, non-blocking, and mostly additive on top of stable foundations.

- [ ] A few more action categories as demonstrations: chat settings
      (title/description/username/photo), admin promote/demote, profile updates
- [ ] CLI conveniences: `doctor`, `plan`, richer `history` filtering
- [ ] Observability: execution timeline and retry/rate-limit statistics views
      (structured JSON logging already present)

## Future (post-v1.0)

Large subsystems that materially increase complexity. Each builds on a baseline
that already exists and is sufficient for v1.0, so deferring them costs nothing
now. These define the post-release roadmap and community direction.

- [ ] Plugin system: external packages registering actions via entry points
      (the registry is already the seam; keep it plugin-friendly)
- [ ] Engine control flow: variables/outputs, if/else, foreach, templates,
      nested workflows
- [ ] Multi-account: registry, pools, rotation, health, concurrent execution
- [ ] Scheduler: delayed, recurring, cron, interval; pause/resume/cancel
- [ ] Database: PostgreSQL parity, migration baseline, cleanup jobs
- [ ] Reliability: checkpoints, crash recovery, dead-letter queue, graceful
      shutdown (retry + resume already present)
- [ ] Security: encrypted secrets and providers, session encryption
      (env-only secrets + gitignored sessions already present)
- [ ] Extended action library: history/export, folders, sessions, contacts,
      media/album/poll messaging — natural first community contributions

## Release checklist for v1.0

- [ ] All "Required before v1.0" items complete
- [ ] Quality gate green; example workflows validate and dry-run
- [ ] No dead code, TODOs, or placeholders; naming and error messages reviewed
- [ ] CHANGELOG finalized; version tagged
