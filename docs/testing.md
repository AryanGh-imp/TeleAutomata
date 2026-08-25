# Testing

The test suite is designed to run **fast, offline, and without credentials**. It
never contacts Telegram or opens a network connection: persistence runs against
in-memory SQLite, the Telegram boundary is replaced by in-process fakes, and the
one module that imports Telethon drives a fake client. A fresh checkout runs the
whole suite green with no `.env`, no session file, and no API keys.

## Running

```bash
pytest                          # whole suite
pytest tests/test_engine.py     # one module
pytest -k resume                # by keyword
pytest -q                       # quiet
```

`pytest` is configured in `pyproject.toml` with `asyncio_mode = "auto"` and
`testpaths = ["tests"]`, so `async def` tests run without a per-test marker and a
bare `pytest` discovers the suite from the repository root. The only requirement
beyond the runtime package is the `dev` extra (`pip install -e ".[dev]"`), which
adds `pytest` and `pytest-asyncio`.

## Layout

The suite mirrors the architecture — one module per unit of behavior, from the
pure domain outward to the CLI and the shipped examples.

| Module | Focus |
| --- | --- |
| `test_engine.py` | `WorkflowEngine` orchestration: transient-failure retry, permanent errors as terminal, retry exhaustion, dependency-failure skipping, `continue_on_error`, dry runs skipping the gateway, the flood-wait budget, and resume idempotency |
| `test_actions.py` | The action dispatch layer: argument forwarding, defaulting, and validation for every action type; CSV member-list merge and dedupe; permission checks; and registry ↔ `ActionType` consistency |
| `test_persistence.py` | `OperationRepository` against in-memory SQLite: execution/operation lifecycle, status queries, error recording, and read views |
| `test_scheduling.py` | `retry_delay` full-jitter bounds (never exceeds the ceiling; exponential growth) and `AccountRateLimiter` pacing — per-account spacing with cross-account independence |
| `test_schema.py` | `WorkflowDefinition` / `load_workflow` validation: dependency cycles, unknown/self/duplicate ids, invalid accounts, retry bounds, and YAML loading |
| `test_settings.py` | `Settings` validation and the credential-requirement error raised for live runs |
| `test_cli.py` | End-to-end CLI (Typer `CliRunner`): every command, the exit-code contract, dry-run-without-credentials, error vs. `--debug` output, and live-run confirmation |
| `test_public_api.py` | The public surface pinned by `__all__`: importable names, error re-export identity, and that importing the package does not import Telethon |
| `test_telegram_helpers.py` | The Telethon adapter in isolation: invite-hash parsing and that `update_entity` issues the expected MTProto request, driven by a fake client |
| `test_examples.py` | A static contract over the shipped `examples/` — every workflow, sample CSV, and GitHub Actions template — verified without running anything live |

## Running offline, without credentials

Nothing in the suite needs a network, a Telegram account, or API keys. That is a
deliberate property of the design, not after-the-fact mocking:

- **In-memory SQLite.** Repository and engine tests open an in-memory database,
  so persistence is exercised for real while nothing touches disk or a server.
- **Fakes at the gateway boundary.** The engine and actions depend only on the
  `TelegramGateway` protocol, so tests supply in-process fakes (below) instead of
  Telethon. No socket is ever opened.
- **Dry runs use the production null gateway.** A `dry_run: true` run wires in
  `NullGateway` — the same code path production uses — which needs no credentials
  and performs no I/O; every action is recorded as `skipped`. Both the engine and
  the CLI tests take this path.
- **Isolated CLI runs.** `test_cli.py` changes into a `tmp_path`, clears
  `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`, and points `DATABASE_URL` and
  `SESSION_DIR` at that directory, so a run can never read the developer's real
  `.env`, database, or sessions.
- **No accidental Telethon import.** `test_public_api.py` spawns a subprocess
  that imports `teleautomata` and asserts `telethon` is *not* among the loaded
  modules — proving the import-time boundary holds and the package is usable
  without the network stack loaded.

## Test doubles

Prefer a fake gateway over patching. The `TelegramGateway` protocol makes this
straightforward — implement only the coroutine methods a test needs, and record
or script their behavior:

- **`FakeGateway`** (engine tests) scripts transient, permanent, and one-shot
  failures per target.
- **`FloodGateway`** (engine tests) raises `RateLimitError` a fixed number of
  times to exercise the flood-wait path.
- **`RecordingGateway`** (action tests) records the arguments each call received,
  so a test can assert exactly what the handler forwarded.
- **`_FakeClient`** (`test_telegram_helpers.py`) stands in for the Telethon
  client so the adapter can be tested without a connection.

`NullGateway` is **not** a test double — it is production code (every method
raises `PermanentActionError`) used for dry runs. Tests exercise it through the
real dry-run path rather than importing it directly.

## Conventions

These are enforced by the project's configuration and followed across the suite:

- **Async without markers.** `asyncio_mode = "auto"` means an `async def test_…`
  runs directly; no `@pytest.mark.asyncio` is required.
- **Parametrize the matrix.** Action, example, and helper tests lean on
  `@pytest.mark.parametrize`, so each case is a separate named result —
  `test_actions.py` and `test_examples.py` expand well beyond their function
  count.
- **Determinism over randomness.** `retry_delay` uses `random.uniform`; tests
  that assert the jitter ceiling temporarily replace `random.uniform` to sample
  the upper bound and restore it in a `finally`. Retry policies in tests use
  sub-second delays (`max_delay_seconds` floors at `0.1`) so retry paths run
  quickly.
- **Isolate settings and the filesystem.** A test that touches settings or files
  changes into `tmp_path` and clears or overrides the relevant environment
  variables, as `test_cli.py` does. Follow that pattern for anything new.
- **No `conftest.py`.** Fixtures are module-local; where a fake is shared it is
  imported directly from its sibling module (for example `test_examples.py`
  reuses `RecordingGateway` from `test_actions.py`).
- **Tests are held to `src` standards, minus line length.** `mypy` runs on `src`
  only, and `ruff` ignores `E501` under `tests/*` so fixtures can be laid out as
  compact tables. Every other `ruff` rule (imports, bugbear, pyupgrade) still
  applies to tests.

## The example contract

`test_examples.py` guards the repository's `examples/` as living documentation,
statically and offline:

- every workflow in `examples/workflows/` loads and validates, is `dry_run:
  true`, uses only registered action types, and has dependencies that resolve to
  real action ids;
- every action's arguments pass the same handler validation the engine uses (via
  `RecordingGateway`), and any referenced member CSV exists;
- no example contains a hard-coded API hash or phone number; and
- the GitHub Actions templates under `examples/github-actions/` are valid YAML
  with a `jobs:` block, only ever read credentials from `secrets.`, and their
  companion docs exist.

Adding or changing an example therefore updates a tested contract — a broken or
unsafe example fails the suite.

## Before committing

Run the full quality gate — the exact commands are the single source of truth in
[Contributing → Quality gate](../CONTRIBUTING.md#quality-gate). CI
(`.github/workflows/ci.yml`) runs that **identical** gate on every push and pull
request, `ruff format --check` included, so format locally with `ruff format .`
before you commit.
