# Development guide

Install the editable project with development dependencies and run Ruff, mypy, and pytest as shown in the README. Tests use in-memory SQLite and a fake gateway; they do not contact Telegram or require credentials.

To add an action, walk the five layers — schema, port, registry handler, Telethon adapter, and null gateway — as described in the [extending guide](extending.md). In short: keep argument validation in the registry handler, keep Telegram imports inside the infrastructure adapter, route failures through `_raise_translated`, and test the normal, temporary, and permanent error paths.

Production schema changes are versioned under `alembic/versions`. Set `DATABASE_URL` and run `alembic upgrade head` as a deployment step; review generated migrations before applying them. Local `teleautomata init` creates the current schema for a fresh developer database.

## IDE note: Telethon "unresolved reference" warnings

PyCharm may flag imports from `telethon.tl.types` and `telethon.tl.functions` (for example `Channel`, `Chat`, `InputNotifyPeer`) as *unresolved references*. These are false positives: the classes exist and the imports work at runtime and under mypy. Telethon generates each of these modules as a single very large file (`telethon/tl/types/__init__.py` is ~2.7 MB), which exceeds PyCharm's default `idea.max.intellisense.filesize` of 2560 KB, so the IDE stops indexing the file and cannot see the definitions.

To restore resolution, raise the limit via **Help → Edit Custom Properties** and add `idea.max.intellisense.filesize=4096`, then restart. This is a local IDE preference only — do not change the imports or add `# type: ignore` to satisfy the IDE. A genuinely missing Telethon symbol shows up as a runtime `AttributeError`/`ImportError` and a failing test, not merely an IDE warning.

