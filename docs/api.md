# API and public interfaces

This page is the interface reference for embedding TeleAutomata or driving it
from your own Python: the public types, the engine's signature, and how to wire a
run yourself. Read [architecture.md](architecture.md) first for the layers, the
[package layout](architecture.md#package-layout), and the dependency direction;
see [../PUBLIC_API.md](../PUBLIC_API.md) for which of these names the stability
contract covers.

## Domain

**`domain/models.py`** — immutable, framework-agnostic value types:

- `OperationStatus` (`StrEnum`): `pending`, `running`, `succeeded`, `failed`,
  `retry_scheduled`, `skipped`.
- `ActionResult` — an action's status, `output` dict, and optional `error_code`.
- `ExecutionSummary` — a run's outcome: `execution_id`, `status`, and
  `succeeded` / `failed` / `skipped` counts. `status` is `FAILED` only when an
  untolerated action failed; the counts still report every failure.
- `ExecutionRecordView` / `OperationRecordView` — read models for reporting.

**`domain/errors.py`** — the error taxonomy the engine dispatches on:
`TeleAutomataError` (base), `PermanentActionError`, `TransientActionError`,
and `RateLimitError(retry_after_seconds)`.

**`domain/ports.py`** — `TelegramGateway`, a `Protocol` with one method per
action. Both `TelethonGateway` and `NullGateway` satisfy it structurally, so
adding an action means extending this contract and implementing it on both.

## Application

**`application/engine.py`** — `WorkflowEngine`, the orchestrator.

```python
WorkflowEngine(
    repository: OperationRepository,
    gateway: TelegramGateway,
    limiter: AccountRateLimiter,
    *,
    max_concurrency: int,
    max_flood_wait_seconds: int,
    default_retry: RetryPolicy,
)

async def run(
    workflow: WorkflowDefinition, resume_execution_id: UUID | None = None
) -> ExecutionSummary
```

`run` persists the execution, then repeatedly dispatches the actions whose
dependencies have completed, honouring the DAG. Each action is retried per its
`RetryPolicy`: `RateLimitError` waits out the flood (unless it exceeds
`max_flood_wait_seconds`), `TransientActionError` backs off, and
`PermanentActionError` fails immediately. A failed or skipped dependency skips
its descendants unless the dependency set `continue_on_error`. Passing
`resume_execution_id` reloads prior per-action statuses and re-runs only what did
not already succeed. Dry runs force concurrency to 1 and skip every action as
planned-but-not-run.

**`application/actions.py`** — the action registry.

- `registry` — the process-wide `ActionRegistry`; handlers register with
  `@registry.register("<action_type>")`.
- `execute_action(gateway, action) -> dict` — validates an action's arguments
  and dispatches to the gateway.
- `registry.assert_consistent_with_schema()` runs at import time and fails if the
  registry and the `ActionType` literal drift.

See the [extension guide](extending.md) for adding an action.

## Workflows

**`workflows/schema.py`** — the validated workflow model:

- `ActionType` — the literal of all valid action names.
- `ActionDefinition` — one action: `id`, `type`, `with` arguments, `depends_on`,
  `continue_on_error`, optional `retry`.
- `RetryPolicy` — `max_attempts`, `initial_delay_seconds`, `max_delay_seconds`.
- `WorkflowDefinition` — `version`, `name`, `account`, `dry_run`, `actions`;
  validates unique ids, known dependencies, and acyclicity.
- `load_workflow(path) -> WorkflowDefinition` — safe-loads and validates a YAML
  file.

## Infrastructure

- **`infrastructure/telegram.py`** — `TelethonGateway`, the real adapter, and
  `connect_gateway(...)`, which opens an authenticated session. It translates
  Telethon exceptions into domain errors at a single boundary; the mapping is in
  [telegram-integration.md](telegram-integration.md#anti-corruption-boundary).
- **`infrastructure/null_gateway.py`** — `NullGateway`, used for dry runs; every
  method raises, so a plan can be inspected without credentials or network.
- **`infrastructure/persistence.py`** — `OperationRepository` (execution and
  operation records, resume queries) with `build_engine(database_url)` and
  `initialize_database(engine)`.
- **`infrastructure/scheduling.py`** — `AccountRateLimiter`, the per-account
  spacing primitive, and `retry_delay(...)` for backoff.

## Configuration

**`config/settings.py`** — `Settings` (pydantic-settings) reads the environment
and `.env`. Public surface used across the app includes `database_url`,
`session_dir`, `log_level`, the pacing/concurrency fields, and
`require_telegram_credentials()`, which returns `(api_id, api_hash)` or raises if
unset. Credentials are never persisted by the framework. See
[configuration](configuration.md) for the full field list.

## Embedding the engine

The CLI is a thin wrapper; the same wiring embeds anywhere:

```python
settings = Settings()
db = build_engine(settings.database_url)
await initialize_database(db)
repository = OperationRepository(async_sessionmaker(db, expire_on_commit=False))
engine = WorkflowEngine(
    repository,
    gateway,
    AccountRateLimiter(settings.min_request_interval_seconds),
    max_concurrency=settings.max_concurrency,
    max_flood_wait_seconds=settings.max_flood_wait_seconds,
    default_retry=RetryPolicy(max_attempts=settings.max_retries + 1),
)
summary = await engine.run(load_workflow(path))
```

Use `NullGateway()` for a dry run, or `connect_gateway(...)` for a real session.
