# Troubleshooting

## "TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured"

A non-dry-run workflow needs credentials. Copy `.env.example` to `.env` and set
both values from https://my.telegram.org, or export them in the environment. Dry
runs (`dry_run: true`) do not need credentials — if you hit this on a dry run,
confirm the workflow really has `dry_run: true`.

## "account '<name>' is not authenticated; run the auth command first"

The session for that account does not exist or is not authorized. Run
`telegram-automation auth <account>` and complete the interactive phone/2FA
prompt. The `account` field in the workflow selects which session under
`SESSION_DIR` is used.

## A run fails with "flood_wait_too_long"

Telegram requested a wait longer than `MAX_FLOOD_WAIT_SECONDS`. This is a safety
stop, not a bug. Wait and retry later, reduce how much the workflow does at once,
or raise `MAX_FLOOD_WAIT_SECONDS` only if you understand the consequences.
Persistent flood waits mean you are pacing too aggressively — increase
`MIN_REQUEST_INTERVAL_SECONDS`.

## An action is "skipped" and never ran

Its dependency did not succeed. A `skipped` or `failed` dependency skips
descendants unless the failing dependency is marked `continue_on_error: true`.
Use `telegram-automation status <execution-id>` to see which upstream action
failed and why.

## "permanent_error" on an action

The request cannot succeed by retrying — typically missing permissions, a
privacy restriction, an invalid target, or an unauthorized account. Fix the
underlying condition (permissions, target, or account) rather than retrying. A
workflow cannot grant permissions the account lacks.

## Resume re-ran or duplicated an action

Resume skips actions already recorded as `succeeded` and retries the rest. If an
action's effect appeared twice, it was likely non-idempotent (for example,
`send_message`) and Telegram had accepted the request before an interruption was
observed. Review `status` output before resuming non-idempotent workflows.

## Validation error before anything runs

`validate` and `run` reject unsound workflows: unknown or self dependencies,
duplicate action IDs, dependency cycles, an invalid `account` name pattern, or a
`max_delay_seconds` below `initial_delay_seconds`. The error message names the
offending action or field.

## "workflow root must be a mapping"

The YAML file parsed to something other than a mapping (for example, a bare list
or scalar). Ensure the top level has `name`, `account`, and `actions` keys.

## `mypy` complains about Telethon types

Telethon ships without type information. It is intentionally isolated via a
per-module override in `pyproject.toml`; keep all `telethon` imports inside
`infrastructure/` so the rest of the project stays strict-clean.

## Database questions

Local `telegram-automation init` creates the current schema for a fresh SQLite
database. For production schema changes, set `DATABASE_URL` and run
`alembic upgrade head`; review generated migrations before applying them.
