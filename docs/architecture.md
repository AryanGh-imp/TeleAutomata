# Architecture

The system uses ports and adapters. `application` owns workflow execution, retries, dependency ordering, and outcome rules. `domain` holds operation states, errors, and the `TelegramGateway` contract. `infrastructure` provides Telethon, SQLAlchemy, and pacing adapters. This separation makes the real client replaceable by a fake gateway in tests.

Each execution and action is persisted before it runs. An action transitions from `pending` to `running`, then to `succeeded`, `failed`, `skipped`, or `retry_scheduled`. Dependency failures skip descendants so workflows do not continue with unsafe assumptions.

Telegram exceptions cross a single anti-corruption boundary. Flood waits become `RateLimitError`, temporary service and connection errors become `TransientActionError`, and RPC/permission errors become `PermanentActionError`. The engine alone decides whether a retry is appropriate.

The in-process rate limiter serializes and spaces calls per account. Production topology must preserve the one-worker-per-account invariant. For larger deployments, replace it with a leased queue while retaining the application/domain boundaries; never distribute the same Telegram session across workers.
