# Telegram integration

All Telegram access lives behind the `TelegramGateway` protocol
(`domain/ports.py`). Two implementations exist: `TelethonGateway`, the real
adapter over Telethon, and `NullGateway`, a guard used for dry runs. Nothing
outside `infrastructure/` imports Telethon.

## The gateway contract

`TelegramGateway` exposes one typed coroutine per supported operation:
`create_group`, `create_channel`, `update_entity`, `send_message`, and
`resolve_target`. Each returns a plain `dict[str, Any]` result. The engine and
action dispatcher depend only on this protocol, which is what lets tests
substitute an in-memory fake.

## Anti-corruption boundary

`TelethonGateway` wraps every client call and funnels failures through
`_raise_translated`, converting Telethon exceptions into domain errors:

| Telethon condition | Domain error |
| --- | --- |
| `FloodWaitError` | `RateLimitError(seconds)` |
| `ServerError`, `RpcCallFailError`, `TimeoutError`, `ConnectionError`, `OSError` | `TransientActionError` |
| Other `RPCError` (invalid request, permissions, privacy) | `PermanentActionError` |
| Anything unexpected | `TransientActionError` |

This is the single place Telegram's error vocabulary enters the system. The
engine then decides retry behavior purely from the domain error type, keeping
retry policy independent of the client library.

## Authentication

Authentication is interactive and handled only by the `auth` CLI command, which
calls `TelegramClient.start` and prompts for phone and 2FA. Credentials and 2FA
input are never written to a workflow, log, or the operation database. `auth`
persists a session file under `SESSION_DIR`; treat that file as account access
material.

`connect_gateway` opens an existing session for a run and refuses to proceed if
the account is not already authorized — it raises `PermanentActionError` rather
than prompting mid-run. A dry run skips `connect_gateway` entirely and uses
`NullGateway`, so no credentials or session are required to inspect a plan.

## Adding an operation

See [development.md](development.md) and [../CONTRIBUTING.md](../CONTRIBUTING.md).
In short: extend the `ActionType` literal, validate arguments in
`application/actions.py`, add the method to `TelegramGateway`, and implement it
on both `TelethonGateway` and `NullGateway`. The engine, scheduler, persistence,
and retry policy stay unchanged.

## Rate limiting

`AccountRateLimiter` serializes and spaces calls per account using one lock per
account name, enforcing `MIN_REQUEST_INTERVAL_SECONDS` between requests from the
same account. It is in-process only: run one worker per account session and
never share a session across workers. For distributed deployments, replace the
limiter with a leased queue while preserving the one-worker-per-account
invariant.
