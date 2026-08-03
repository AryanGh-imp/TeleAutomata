# Public API

This document defines what TeleAutomata considers its **public API** — the
surface that follows [Semantic Versioning](https://semver.org/) from v1.0
onward. Anything listed under **Stable API** will not change in a
backward-incompatible way without a major-version bump. Anything listed under
**Internal API** may change at any time, including in patch releases.

If you depend only on the Stable API, upgrading within a major version is safe.

## Stability at a glance

| Surface | Stability | Import path / location |
| --- | --- | --- |
| CLI commands, arguments, exit codes | Stable | `teleautomata` executable |
| Workflow YAML schema | Stable | `*.yml` / `*.yaml` files |
| Action names, arguments, result keys | Stable | workflow `actions:` |
| Configuration environment variables | Stable | env / `.env` |
| Error taxonomy | Stable | `teleautomata.domain.errors` |
| Workflow/action models | Stable | `teleautomata.workflows.schema` |
| Domain models & gateway port | Stable | `teleautomata.domain` |
| Engine & action registry | Stable | `teleautomata.application` |
| Telethon / persistence / scheduling adapters | Internal | `teleautomata.infrastructure`, `.observability` |

---

## Stable API

### 1. Command-line interface

The `teleautomata` executable is the primary public interface. Command names,
their positional arguments and options, and their **exit codes** are stable.

| Command | Signature |
| --- | --- |
| `init` | `teleautomata init` |
| `auth` | `teleautomata auth <account>` |
| `validate` | `teleautomata validate <workflow.yaml>` |
| `run` | `teleautomata run <workflow.yaml>` |
| `resume` | `teleautomata resume <workflow.yaml> <execution_id>` |
| `list` | `teleautomata list [directory]` |
| `history` | `teleautomata history [--limit N]` |
| `status` | `teleautomata status <execution_id>` |

Exit codes (stable contract):

- `0` — success.
- `1` — the run failed as a whole (`run`, `resume`), or no matching execution
  was found (`status`). A failure tolerated by `continue_on_error` does **not**
  set this code.
- `2` — usage or argument error (missing file, malformed account name).

The exact wording of human-readable output (summaries, table columns) is **not**
part of the contract; parse execution state via the database read models or the
`status` command's structured fields, not by scraping prose.

See [docs/cli.md](docs/cli.md) for full descriptions.

### 2. Workflow YAML schema

The workflow file format is stable and versioned by its own `version` field
(currently `1`). Its shape is defined by `teleautomata.workflows.schema`:

```yaml
version: 1                 # literal 1
name: "My workflow"        # 1–120 chars
account: "myaccount"       # [a-zA-Z][a-zA-Z0-9_-]{0,63}
dry_run: false             # optional, default false
actions:                   # 1–500 actions
  - id: announce           # [a-zA-Z][a-zA-Z0-9_-]{0,63}, unique
    type: send_message     # one of the 29 action types
    with:                  # action arguments (see below)
      target: "@channel"
      message: "Hello"
    depends_on: []         # optional list of action ids
    continue_on_error: false
    retry:                 # optional per-action override
      max_attempts: 3            # 1–10
      initial_delay_seconds: 1.0 # 0.1–300
      max_delay_seconds: 60.0    # 0.1–3600, >= initial
```

Validation guarantees (stable): action ids are unique, `depends_on` references
resolve, the dependency graph is acyclic, and every argument is type-checked
before any network call.

### 3. Actions

The **29 action names**, their **argument names**, and their **result dict
keys** are stable. The library is intentionally a representative, frozen set;
new actions may be *added* in minor releases, but existing action signatures
will not change incompatibly. The full catalog — arguments, defaults,
validation, and result keys — is documented in
[docs/actions.md](docs/actions.md).

Note the naming convention that the v1.0 API freeze standardized: every action
that sends a text body names that argument **`message`** — including
`send_message`, `reply_message`, and `edit_message`.

### 4. Configuration

Configuration is read from environment variables and `.env`. The following
variable names and their meanings are stable:

- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` — credentials (never persisted).
- `DATABASE_URL` — SQLAlchemy async URL (default
  `sqlite+aiosqlite:///./data/teleautomata.sqlite3`).
- `SESSION_DIR` — directory for Telethon session files.
- `LOG_LEVEL` — structlog level.
- `MAX_CONCURRENCY`, `MIN_REQUEST_INTERVAL_SECONDS`, `MAX_RETRIES`,
  `MAX_FLOOD_WAIT_SECONDS` — pacing and retry bounds.

See [docs/configuration.md](docs/configuration.md).

### 5. Error taxonomy — `teleautomata.domain.errors`

The exception hierarchy is stable. Catch the base class to handle any framework
error:

```python
from teleautomata.domain.errors import TeleAutomataError
```

- `TeleAutomataError` — base of every framework exception.
  - `PermanentActionError` — cannot succeed by retrying (bad input, rejection).
  - `TransientActionError` — temporary service/network failure; retried.
    - `RateLimitError(retry_after_seconds)` — Telegram flood-wait; the engine
      waits and retries.

### 6. Domain layer — `teleautomata.domain`

Stable value types used in return structures and read models:

- `teleautomata.domain.models` — `OperationStatus` (StrEnum), `ActionResult`,
  `ExecutionSummary`, `ExecutionRecordView`, `OperationRecordView`.
- `teleautomata.domain.ports` — `TelegramGateway`, the `Protocol` every adapter
  satisfies. This is the **extension point** for custom gateways: implement the
  protocol to target a different backend or a fake for testing.

`ExecutionSummary.status` is `OperationStatus.FAILED` only when an *untolerated*
action failed; the `succeeded` / `failed` / `skipped` counts always report every
action regardless of `continue_on_error`.

### 7. Application layer — `teleautomata.application`

- `teleautomata.application.engine.WorkflowEngine` — constructs and runs a
  workflow (DAG batching, retry/backoff, dry-run). Its constructor parameters
  are stable.
- `teleautomata.application.actions` — `execute_action`, and `registry`, the
  typed action registry. The `@registry.register("<action_type>")` decorator is
  the **extension point** for adding actions; `registry.action_types` and
  `registry.assert_consistent_with_schema()` are stable.

### 8. Workflow schema models — `teleautomata.workflows.schema`

`ActionType`, `RetryPolicy`, `ActionDefinition`, `WorkflowDefinition`, and
`load_workflow` are stable and safe to import (e.g. to build or validate
workflows programmatically).

---

## Internal API

These modules are implementation details. **Do not import them** from outside
the package; they may change or be removed in any release without notice.

- `teleautomata.infrastructure.*` — the Telethon gateway (`telegram.py`), the
  dry-run guard (`null_gateway.py`), persistence (`persistence.py`,
  `OperationRepository`, `build_engine`, `initialize_database`), and rate
  limiting (`scheduling.py`). Depend on the `TelegramGateway` port instead of
  the concrete `TelethonGateway`.
- `teleautomata.observability.*` — structured-logging configuration.
- `teleautomata.config.settings.Settings` — the concrete pydantic-settings
  model is internal; the **environment variable names** it reads (§4) are the
  stable contract, not the class.
- The **database schema** and Alembic migrations — internal. Query recorded
  executions through the CLI (`history`, `status`) or the domain read models,
  never by reading tables directly.
- Any module-private name (leading underscore), such as the argument-coercion
  helpers in `application.actions` (`_string`, `_integer`, …).

---

## Extending TeleAutomata

The two supported extension points, both on the Stable API:

1. **Add an action** — register a handler with
   `@registry.register("<name>")`, add the name to the `ActionType` literal, and
   implement the method on every `TelegramGateway`. The import-time drift guard
   (`registry.assert_consistent_with_schema()`) enforces that the registry and
   schema stay in lockstep. See [docs/extending.md](docs/extending.md).
2. **Add a gateway** — implement the `TelegramGateway` protocol to target a
   different backend or provide a fake for testing.

Everything else — engine internals, persistence, logging — is intentionally not
an extension surface.
