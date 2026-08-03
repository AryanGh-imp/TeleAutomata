# Configuration and security

Copy `.env.example` to `.env` for local development. Environment variables take precedence.

| Setting | Meaning |
| --- | --- |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Private Telegram developer credentials |
| `DATABASE_URL` | Async SQLAlchemy URL; SQLite locally, PostgreSQL in production |
| `SESSION_DIR` | Ignored private directory containing Telegram session files |
| `MIN_REQUEST_INTERVAL_SECONDS` | Minimum spacing between requests from one account |
| `MAX_RETRIES` | Retries after the initial attempt for temporary failures |
| `MAX_FLOOD_WAIT_SECONDS` | Largest server-requested wait accepted automatically |

Never store credentials in YAML, source control, logs, command-line arguments, or the operation database. Session files are account access material: encrypt disks/backups and limit them to the worker identity. Telegram permissions depend on the entity and acting account; a workflow cannot grant missing permissions.
