# Configuration

TeleAutomata is configured entirely through environment variables, read on
startup by a pydantic-settings model. For local development, copy `.env.example`
to `.env` and fill it in; values in the real environment take precedence over
`.env`, and unknown variables are ignored. Credentials are read **only** from the
environment or `.env` and are never written to YAML, logs, command-line
arguments, or the operation database.

## Settings

| Variable | Default | Bounds / format | Meaning |
| --- | --- | --- | --- |
| `TELEGRAM_API_ID` | *(unset)* | positive integer | Telegram developer app id from [my.telegram.org](https://my.telegram.org). Required only for live runs. |
| `TELEGRAM_API_HASH` | *(unset)* | secret string | Telegram developer app hash. Required only for live runs. Held as a secret and never printed. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/teleautomata.sqlite3` | async SQLAlchemy URL | The operation database. SQLite locally; PostgreSQL (`postgresql+asyncpg://…`) in production. |
| `SESSION_DIR` | `./sessions` | directory path | Where Telethon session files are stored. Git-ignored; treat as account access material. |
| `LOG_LEVEL` | `INFO` | a Python logging level name | Verbosity of structured (structlog) output. |
| `MAX_CONCURRENCY` | `2` | 1–20 | Maximum number of actions run at once within a workflow's dependency batches. |
| `MIN_REQUEST_INTERVAL_SECONDS` | `1.0` | 0.1–300.0 | Minimum spacing between requests from a single account. |
| `MAX_RETRIES` | `3` | 0–10 | Retries **after** the initial attempt for transient failures, when an action has no `retry:` block of its own. |
| `MAX_FLOOD_WAIT_SECONDS` | `3600` | 1–86400 | Largest server-requested flood wait accepted automatically; a longer wait fails the action instead of sleeping. |

Values outside the stated bounds are rejected at startup, and `TELEGRAM_API_ID`
must be positive. Only `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` gate live runs;
a dry run needs neither. When they are required but absent, the framework raises
`TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured` rather than proceeding.

### How `MAX_RETRIES` relates to a workflow's `retry`

`MAX_RETRIES` sets the engine's *default* retry policy for any action that does
not declare its own `retry:` block. The default policy's total attempt count is
`MAX_RETRIES + 1` (the initial attempt plus the retries), so the default of `3`
means up to four attempts. An action's own `retry.max_attempts` overrides this
entirely — see [workflows.md](workflows.md#retry-policies). Only transient and
flood-wait failures are retried; permanent errors are not (see
[workflow-engine.md](workflow-engine.md#retries-and-error-classes)).

## Local development vs. production

- **Database.** The SQLite default needs no setup and is ideal for local use and
  dry runs. In production, point `DATABASE_URL` at PostgreSQL and apply schema
  migrations as a deploy step (`alembic upgrade head`); see
  [development.md](development.md). A local `teleautomata init` creates the
  current schema for a fresh developer database.
- **Pacing.** The shipped `MAX_CONCURRENCY`, `MIN_REQUEST_INTERVAL_SECONDS`, and
  flood-wait defaults are deliberately conservative. Raise them only after
  observing normal operation for your accounts, and keep one worker per account
  session (see [architecture.md](architecture.md#concurrency-and-pacing)).

## Security

Credentials and session files are the sensitive material here, and their
handling is a first-class concern. In short: never commit `.env` or `sessions/`,
treat a session file as password-equivalent, and prefer dry runs until you have
deliberately chosen to go live. The authoritative guidance — including CI and
threat considerations — is in [security.md](security.md) and the repository's
[SECURITY.md](../SECURITY.md); this page only sets the values they discuss.
