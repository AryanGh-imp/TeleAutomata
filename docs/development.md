# Development guide

Setup and the quality gate live in [CONTRIBUTING.md](../CONTRIBUTING.md): install
with `pip install -e ".[dev]"`, then run the
[quality gate](../CONTRIBUTING.md#quality-gate) before every change. Tests use
in-memory SQLite and a fake gateway, so they never contact Telegram or need
credentials — see [testing.md](testing.md) for how the suite is structured.

This page collects the environment specifics that don't belong in those
overviews.

## Adding an action

Adding a Telegram capability is a mechanical walk through five layers — schema,
port, registry handler, Telethon adapter, and null gateway. The full worked
example, the argument-validation helpers, and the batch/partial-failure pattern
are in the [extension guide](extending.md). In short: keep argument validation in
the registry handler, keep Telethon imports inside the infrastructure adapter,
route failures through the anti-corruption boundary, and test the normal,
transient, and permanent error paths.

## Database migrations

The operation database schema is versioned with Alembic under `alembic/versions`.
For a fresh local database, `teleautomata init` creates the current schema
directly. For production schema changes, set `DATABASE_URL` and run
`alembic upgrade head` as a deployment step, reviewing generated migrations
before applying them.

## IDE note: Telethon "unresolved reference" warnings

PyCharm may flag imports from `telethon.tl.types` and `telethon.tl.functions` (for
example `Channel`, `Chat`, `InputNotifyPeer`) as *unresolved references*. These
are false positives: the classes exist and the imports work at runtime and under
mypy. Telethon generates each of these modules as a single very large file
(`telethon/tl/types/__init__.py` is ~2.7 MB), which exceeds PyCharm's default
`idea.max.intellisense.filesize` of 2560 KB, so the IDE stops indexing the file
and cannot see the definitions.

To restore resolution, raise the limit via **Help → Edit Custom Properties** and
add `idea.max.intellisense.filesize=4096`, then restart. This is a local IDE
preference only — do not change the imports or add `# type: ignore` to satisfy the
IDE. A genuinely missing Telethon symbol shows up as a runtime
`AttributeError`/`ImportError` and a failing test, not merely an IDE warning.
