# Development guide

Install the editable project with development dependencies and run Ruff, mypy, and pytest as shown in the README. Tests use in-memory SQLite and a fake gateway; they do not contact Telegram or require credentials.

To add an action, walk the five layers — schema, port, registry handler, Telethon adapter, and null gateway — as described in the [extending guide](extending.md). In short: keep argument validation in the registry handler, keep Telegram imports inside the infrastructure adapter, route failures through `_raise_translated`, and test the normal, temporary, and permanent error paths.

Production schema changes are versioned under `alembic/versions`. Set `DATABASE_URL` and run `alembic upgrade head` as a deployment step; review generated migrations before applying them. Local `telegram-automation init` creates the current schema for a fresh developer database.
