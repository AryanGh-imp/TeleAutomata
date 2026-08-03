# Development guide

Install the editable project with development dependencies and run Ruff, mypy, and pytest as shown in the README. Tests use in-memory SQLite and a fake gateway; they do not contact Telegram or require credentials.

To add an action, add its type to `workflows/schema.py`, validate its arguments in `application/actions.py`, add a typed method to the gateway contract and Telethon adapter, test normal/temporary/permanent error paths, and document authorization plus pacing expectations. Keep Telegram imports inside the infrastructure adapter.

Production schema changes are versioned under `alembic/versions`. Set `DATABASE_URL` and run `alembic upgrade head` as a deployment step; review generated migrations before applying them. Local `telegram-automation init` creates the current schema for a fresh developer database.
