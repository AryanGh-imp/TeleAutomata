# Roadmap

TeleAutomata's foundation phase is complete: ports-and-adapters architecture,
async workflow engine, persistence, CLI, tests, and baseline docs. This roadmap
tracks the remaining work toward the first stable production release.

**Working principle:** every new capability is a new workflow action or a new
engine feature — never special-case code that bypasses the engine. The
architecture is stable and is not redesigned. Work lands in small, verified
increments (each green across `ruff`, `ruff format`, `mypy`, `pytest`, `build`)
with logical commits.

## Status legend

- `[x]` done · `[~]` in progress · `[ ]` not started

## Phase 2 — Action library

The action dispatcher is a typed **registry** (`application/actions.py`): each
action registers a handler; a runtime guard asserts the registry matches the
`ActionType` literal so the two never drift. Adding an action means: extend the
literal, register a validated handler, add a gateway method on both
`TelethonGateway` and `NullGateway`, and test it.

Implemented so far:

- [x] create_group, create_channel, update_entity, send_message, resolve_target
- [x] pin_message, unpin_message, edit_message, delete_message
- [x] forward_message, reply_message, mark_read, archive_chat
- [x] Dialogs: mark_unread, mute_dialog, unmute_dialog, pin_dialog, unpin_dialog
- [x] Membership: join_channel, leave_channel, join_group, leave_group

Planned (grouped as in the spec). Some entries are marked **N/A** because the
account-level MTProto API does not support them and the framework will not fake
them:

- [ ] Group: migrate_group_to_supergroup, export_group_information;
      delete_group **N/A** (no account-level API), clone_group_settings /
      archive_group map to existing update/archive; join_group / leave_group
      **done** (see above)
- [ ] Channel: update_channel, clone_channel_settings; delete_channel is
      `channels.DeleteChannel` (creator only); join_channel / leave_channel
      **done** (see above)
- [ ] Chat settings: update_username, update_photo, remove_photo,
      update_invite_link, revoke_invite_link, enable/disable_join_requests,
      update_default_permissions, slow_mode, reactions, signatures,
      linked_discussion
- [ ] Members: add/remove/ban/unban/kick/mute/unmute/restrict/restore, with
      single / multiple / CSV / YAML-list / username / id targeting
- [ ] Admins: promote_admin, demote_admin, update_admin_permissions,
      transfer_ownership (Telegram permits only with 2FA + constraints)
- [ ] Messages: send_multiple, schedule, delete_multiple, copy, send_media/album/
      document/voice/video/animation/poll/location/contact
- [ ] History: export_messages, search_messages, download_media, delete_history
- [ ] Folders: create/update/delete/move_chat_to_folder
- [ ] Profile: update_profile_name, update_bio, update_username, update_profile_photo
- [ ] Sessions: list_sessions, revoke_session, logout
- [ ] Contacts: add/remove/import/export
- [ ] Dialogs: mark_unread, mute/unmute, pin/unpin dialog **done** (see above)

## Phase 3 — Engine enhancements

- [ ] variables, parameters, action/workflow outputs, workflow context
- [ ] control flow: if/else, foreach, parallel/sequential blocks
- [ ] reusable templates, includes, nested workflows, versioning, tags/labels

## Phase 4 — Multi-account

- [ ] account registry, aliases, pools, rotation, selection rules, health,
      locking, concurrent execution, reconnect; per-workflow account/group/strategy

## Phase 5 — Scheduler

- [ ] persistent scheduler: delayed, recurring, cron, interval, calendar,
      timezone, pause/resume/cancel, priorities

## Phase 6 — Observability

- [ ] execution timeline, workflow/action/retry/rate-limit statistics, audit log,
      log export (structured JSON logging already present)

## Phase 7 — Database

- [ ] PostgreSQL parity, committed migration baseline, indexes, cleanup jobs
      (SQLite + async SQLAlchemy already present)

## Phase 8 — Reliability

- [ ] checkpoints, crash recovery, auto-resume, transactional execution,
      cancellation tokens, graceful shutdown, timeouts, dead-letter queue,
      duplicate-execution protection (retry policy + resume already present)

## Phase 9 — Security

- [ ] encrypted secrets, secret providers, session encryption, secret redaction,
      config validation (env-only secrets + gitignored sessions already present)

## Phase 10 — CLI

- [ ] accounts, workflows, actions, plan, schedule, logs, cancel, retry, doctor,
      export, import (init/auth/validate/run/resume/list/history/status present)

## Phase 11 — Documentation

- [x] README, CONTRIBUTING, CHANGELOG, LICENSE, SECURITY, CODE_OF_CONDUCT, ROADMAP
- [x] docs/: architecture, workflow-engine, telegram-integration, configuration,
      security, testing, development, troubleshooting
- [ ] ACTIONS.md action catalog, CLI.md, API.md, FAQ.md, deployment,
      extension/plugin guides, Mermaid diagrams

## Phase 12 — Testing

- [ ] reach 90%+ coverage; add integration, performance, and recovery suites

## Phase 13 — CI/CD

- [ ] coverage gate and release validation in CI; automated GitHub Releases
      (ruff/mypy/pytest/build already in CI)

## Phase 14 — Packaging

- [x] hatchling wheel + sdist build; pip/editable installs
- [ ] validate full package metadata for PyPI

## Phase 15 — Performance

- [ ] profile critical paths: startup, DB access, concurrency, scheduling

## Phase 16 — Final review

- [ ] remove dead code / TODOs / placeholders; naming, comments, typing, error
      messages, and docs pass before tagging the first stable release
