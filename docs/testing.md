# Testing

The suite is designed to run fast, offline, and without credentials. Tests use
in-memory SQLite and fake gateways; none contact Telegram.

## Running

```bash
pytest              # whole suite
pytest tests/test_engine.py           # one module
pytest -k resume    # by keyword
```

`pytest` is configured with `asyncio_mode = "auto"` (see `pyproject.toml`), so
`async def` tests run without a per-test marker.

## Layout

| Module | Focus |
| --- | --- |
| `test_engine.py` | Retry, dependency skipping, `continue_on_error`, dry run, flood-wait budget, resume idempotency |
| `test_actions.py` | Argument validation and gateway dispatch for every action type |
| `test_persistence.py` | Repository lifecycle, status queries, and execution/operation read views |
| `test_scheduling.py` | Backoff ceiling and jitter bounds, per-account rate-limiter pacing |
| `test_schema.py` | Dependency, self-dependency, duplicate-id, and account validation; `load_workflow`; `actions_by_id` |
| `test_settings.py` | Settings validation and credential requirements |
| `test_cli.py` | End-to-end CLI runs against an isolated database with no credentials |

## Test doubles

Prefer a fake gateway over patching. The `TelegramGateway` protocol makes this
straightforward: implement the coroutine methods a test needs and record or
script their behavior. Existing fakes:

- `FakeGateway` (engine tests) supports scripted transient, permanent, and
  one-shot failures per target.
- `FloodGateway` (engine tests) raises `RateLimitError` a fixed number of times
  to exercise flood-wait paths.
- `RecordingGateway` (action tests) records the arguments each call received.

## Determinism

`retry_delay` uses `random.uniform`; where a test asserts the backoff ceiling it
temporarily replaces `random.uniform` to sample the upper bound, then restores
it. Retry policies in tests use sub-second delays (`max_delay_seconds` floors at
0.1) so retry paths run quickly.

## Isolation

CLI tests change into a `tmp_path` working directory and clear
`TELEGRAM_API_ID`/`TELEGRAM_API_HASH` so they never read the developer's real
`.env` or data. Follow the same pattern for any test that touches settings or
the filesystem.

## Before committing

Run the full quality gate — the exact commands are in
[Contributing → Quality gate](../CONTRIBUTING.md#quality-gate). CI runs the same
checks except `ruff format --check`, so run the formatter locally before you
commit.
