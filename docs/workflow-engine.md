# Workflow engine

The engine (`application/engine.py`) runs a validated `WorkflowDefinition` to
completion and returns an `ExecutionSummary`. It owns dependency ordering,
retries, outcome rules, and persistence of every state transition.

## Execution model

A workflow is a directed acyclic graph of actions. Validation in
`workflows/schema.py` rejects unknown dependencies, self-dependencies, duplicate
IDs, and cycles before the engine runs, so execution can assume a sound graph.

The engine repeatedly selects the set of actions whose dependencies have all
produced a result and runs that batch concurrently, bounded by
`MAX_CONCURRENCY`. A dry run forces concurrency to one so the planned order
reads clearly. Each action is persisted as `pending` before it runs and moves
through `running` to a terminal `succeeded`, `failed`, or `skipped` — with
`retry_scheduled` recorded between attempts.

## Dependency outcomes

`_dependency_blocks` decides whether a dependency's result should skip its
descendants:

- A `skipped` dependency never produced a usable result, so it always
  propagates: descendants are skipped.
- A `failed` dependency skips descendants unless it was marked
  `continue_on_error`, which lets an optional step fail without abandoning the
  rest of the workflow.
- Any other outcome (`succeeded`) does not block.

## Retries and error classes

Each action uses its own `retry` policy or the engine default. The gateway
raises only domain errors, and the engine maps them to behavior:

- `RateLimitError` (flood wait): if the requested wait exceeds
  `MAX_FLOOD_WAIT_SECONDS`, the action fails immediately
  (`flood_wait_too_long`) rather than sleeping. Otherwise the engine waits the
  requested time and retries until attempts are exhausted
  (`flood_wait_retry_exhausted`).
- `TransientActionError`: retried with exponential backoff and full jitter
  (`retry_delay`) until attempts are exhausted (`transient_error`).
- `PermanentActionError`: terminal on the first occurrence
  (`permanent_error`); never retried.

Backoff is `random.uniform(0, min(maximum, initial * 2 ** (attempt - 1)))`: the
ceiling doubles each attempt up to `max_delay_seconds`, and full jitter spreads
retries to avoid synchronized bursts.

## Run status vs. per-action counts

`ExecutionSummary.status` is `FAILED` only when an action failed *without*
`continue_on_error`. The `failed` count reports every failed action, including
tolerated ones, so reporting stays faithful to what actually happened. A
workflow whose only failure was tolerated has `status == SUCCEEDED` and
`failed >= 1`.

## Resume and idempotency

`resume` re-runs an existing execution by ID. The engine loads the latest status
per action; actions already `succeeded` are treated as done and skipped, and
only unfinished actions run again. Resuming a fully succeeded workflow executes
nothing.

Resume is safe for idempotent operations. For non-idempotent actions (for
example, sending a message), review recorded outcomes first: Telegram may have
accepted a request before a network interruption was observed, so a blind resume
could repeat a visible side effect.
