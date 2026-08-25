# Extending TeleAutomata

The action registry is the framework's main extension point. Every Telegram
capability is a workflow action, and adding one is a mechanical walk through five
small layers. This guide explains that path and, just as importantly, *why* it is
shaped this way — the structure is what keeps the engine, the dry-run guard, and
the type checker honest as the action library grows.

## Why five layers

An action is defined once as a name and implemented in four places, each with a
single job:

| Layer | File | Responsibility |
| --- | --- | --- |
| Schema | `workflows/schema.py` | Declare the action name in the `ActionType` literal. |
| Port | `domain/ports.py` | Declare the gateway method signature (the contract). |
| Registry | `application/actions.py` | Validate arguments and dispatch to the gateway. |
| Adapter | `infrastructure/telegram.py` | Perform the real MTProto call via Telethon. |
| Guard | `infrastructure/null_gateway.py` | Refuse to run during dry runs. |

The separation is deliberate. The **port** is a `Protocol`, so both the real
adapter and the dry-run guard are checked against one signature — mypy fails if
either drifts. The **registry** holds all argument validation, so business rules
never leak into the Telethon adapter and the adapter stays a thin, replaceable
boundary. The **null gateway** exists so `dry_run: true` can inspect a plan with
no credentials and no network: if any code path ever reaches it, it raises
instead of silently touching Telegram.

Two invariants make this safe to extend:

- **The drift guard.** `application/actions.py` calls
  `registry.assert_consistent_with_schema()` at import time. If the registry and
  the `ActionType` literal ever disagree — a handler without a schema entry, or
  vice versa — the import fails loudly. You cannot half-add an action.
- **Error translation.** The adapter's `_raise_translated` maps Telethon
  exceptions to domain errors: `FloodWaitError` → `RateLimitError`, server and
  connection faults → `TransientActionError`, and other RPC rejections →
  `PermanentActionError`. The engine's retry and flood-wait logic keys off these
  domain types, so a new action inherits correct pacing for free — as long as it
  routes failures through `_raise_translated`.

## Worked example: a single-target action

Most actions take one `target` and call one Telethon method. `archive_chat` is
the reference shape; follow it end to end.

**1. Schema** — add the name to the literal in `workflows/schema.py`:

```python
ActionType = Literal[
    ...,
    "archive_chat",
]
```

**2. Port** — add the method to the `TelegramGateway` protocol in
`domain/ports.py`:

```python
async def archive_chat(self, target: str) -> dict[str, Any]: ...
```

**3. Registry** — validate arguments and dispatch in `application/actions.py`.
The `_string` helper rejects missing or blank values with a
`PermanentActionError`, so a malformed workflow fails fast and is never retried:

```python
@registry.register("archive_chat")
async def _archive_chat(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.archive_chat(_string(arguments, "target"))
```

**4. Adapter** — perform the real call in `infrastructure/telegram.py`, wrapping
every Telethon call so failures are translated:

```python
async def archive_chat(self, target: str) -> dict[str, Any]:
    try:
        await self._client.edit_folder(target, folder=1)
        return {"target": target, "archived": True}
    except Exception as exc:
        self._raise_translated(exc)
```

**5. Guard** — forbid it during dry runs in `infrastructure/null_gateway.py`:

```python
async def archive_chat(self, target: str) -> dict[str, Any]:
    return self._forbid("archive_chat")
```

That is a complete action. The drift guard now passes because the schema and
registry agree, and mypy passes because both gateways satisfy the port.

## Validating richer arguments

Validation lives entirely in the registry handler, using small typed helpers in
`application/actions.py`:

- `_string` / `_optional_string` — required and optional non-empty strings.
- `_string_list` — a non-empty list of non-empty strings.
- `_integer` — an `int` that is not a `bool` (so `true` is not read as `1`).
- `_user_targets` — merges an inline `users` list with an optional `users_csv`
  file and de-duplicates, giving every member action the same targeting model.

`restrict_members` shows the pattern for a constrained mapping: it accepts a
`permissions` dict, checks each key against a known set of rights and each value
for being a real bool, and raises `PermanentActionError` otherwise. Keep this
kind of rule in the handler — never in the adapter.

## Batch actions and partial failure

Actions that act on many users (add, remove, ban, mute, …) run through the
adapter's `_for_each_user` helper. It isolates *permanent* per-user failures —
one unresolvable username is recorded under `failed` and the batch continues —
while letting *rate-limit and transient* errors propagate so the engine's
flood-wait handling governs the whole action. Reuse this helper rather than
looping by hand, so every batch action reports results the same way.

## Testing

Tests do not touch Telegram. `tests/test_actions.py` defines a `RecordingGateway`
that records the arguments each action was dispatched with; add your method to it
and assert the handler forwards the right values. Cover, at minimum:

- the happy path (arguments reach the gateway unchanged);
- each validation rule you added (missing target, bad types, unknown keys);
- for batch actions, that de-duplication and the `users_csv` path work.

The suite also runs `test_registry_matches_action_type_schema`, which fails if
the registry and the literal drift — the same guarantee the import-time guard
gives, asserted in CI.

## Before you commit

Run the full quality gate and keep it green — the exact commands are in
[Contributing → Quality gate](../CONTRIBUTING.md#quality-gate).

Then add an example workflow under `examples/workflows/` using `dry_run: true`.
Actions that map to an MTProto call another action already makes should not be
duplicated — document the alias instead (for example `kick` folds into
`remove_members`, and `restore` into `unban_members`, since each issues the same
MTProto call). API stability and a small, coherent library matter more than raw
action count.
