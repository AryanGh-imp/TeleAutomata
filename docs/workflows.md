# Workflows

A workflow is a YAML file that describes a set of Telegram actions and the order
they run in. You author it declaratively; the engine handles dependency ordering,
retries, flood-wait handling, persistence, and resume. This page is the reference
for the **file format** — what every field means and how to write a sound
workflow. For how the engine *executes* what you write, see
[workflow-engine.md](workflow-engine.md); for the actions you can use, see
[actions.md](actions.md).

## A complete example

```yaml
version: 1
name: update-project-channel
account: primary
dry_run: true
actions:
  - id: check_target
    type: resolve_target
    with:
      target: "@my_project"

  - id: update_description
    type: update_entity
    depends_on: [check_target]
    with:
      target: "@my_project"
      about: "A current project description"
    retry:
      max_attempts: 3
      initial_delay_seconds: 2
      max_delay_seconds: 60

  - id: announce
    type: send_message
    depends_on: [update_description]
    continue_on_error: true
    with:
      target: "@my_project"
      message: "Description updated."
```

This validates and dry-runs with no credentials. `announce` runs only after
`update_description` succeeds, and its `continue_on_error: true` means a failure
there is recorded but does not fail the run.

## Top-level fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `version` | integer | no | Must be `1`. Defaults to `1`. The format is versioned by this field. |
| `name` | string | **yes** | 1–120 characters. A human label shown in listings, history, and status. |
| `account` | string | **yes** | Matches `^[a-zA-Z][a-zA-Z0-9_-]{0,63}$`. The **local session name** to run against — not a phone number. It selects a session file under `SESSION_DIR` and is the name you pass to `teleautomata auth`. |
| `dry_run` | boolean | no | Defaults to `false`. When `true`, the run plans without contacting Telegram (see [Dry-run](#dry-run)). |
| `actions` | list | **yes** | 1–500 actions. Executed as a dependency graph, not necessarily top to bottom. |

## Action fields

Each entry under `actions:` is one action:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | string | **yes** | Matches `^[a-zA-Z][a-zA-Z0-9_-]{0,63}$` and is **unique** within the workflow. Referenced by `depends_on` and shown in status output. |
| `type` | string | **yes** | One of the 29 [action types](actions.md). |
| `with` | mapping | depends on action | The action's arguments. Optional in the schema (defaults to `{}`), but most actions require specific keys — see [actions.md](actions.md). |
| `depends_on` | list of ids | no | Ids of actions that must finish before this one starts. Defaults to `[]`. |
| `continue_on_error` | boolean | no | Defaults to `false`. See [continue_on_error](#continue_on_error). |
| `retry` | mapping | no | Per-action retry override. Omit to use the engine default. See [Retry policies](#retry-policies). |

## Dependencies and execution order

`depends_on` turns the action list into a directed acyclic graph (DAG). The
engine repeatedly runs the set of actions whose dependencies have all completed,
so **independent actions in the same layer run concurrently** (bounded by
`MAX_CONCURRENCY`), and order within the file does not imply order of execution —
only `depends_on` does. If an action has no dependencies it is eligible from the
start.

```yaml
actions:
  - id: a
    type: resolve_target
    with: {target: "@one"}
  - id: b
    type: resolve_target
    with: {target: "@two"}          # a and b run together (no dependency)
  - id: c
    type: send_message
    depends_on: [a, b]              # c waits for both (fan-in)
    with: {target: "@one", message: "ready"}
```

If a dependency is `skipped` or `failed` (and not tolerated), its descendants are
skipped rather than run on an unsafe assumption. The exact rules are in
[workflow-engine.md](workflow-engine.md#dependency-outcomes).

## Retry policies

Every action is attempted under a `RetryPolicy` — either its own `retry:` block or
the engine default. The fields and their bounds:

| Field | Default | Bounds | Meaning |
| --- | --- | --- | --- |
| `max_attempts` | 3 | 1–10 | Total attempts **including the first**. `1` disables retries. |
| `initial_delay_seconds` | 1.0 | 0.1–300 | Base backoff before the first retry. |
| `max_delay_seconds` | 60.0 | 0.1–3600 | Ceiling for backoff. Must be `>= initial_delay_seconds`. |

The defaults above apply to fields you omit inside a `retry:` block. An action
with **no** `retry:` block instead uses the engine default, derived from
`MAX_RETRIES` (`max_attempts = MAX_RETRIES + 1`; see
[configuration.md](configuration.md)). Only transient and flood-wait failures are
retried; a permanent error (bad input, Telegram rejection) fails on the first
attempt regardless of `max_attempts`. The backoff formula and flood-wait handling
are documented in [workflow-engine.md](workflow-engine.md#retries-and-error-classes).

## continue_on_error

By default a failed action fails the run as a whole and skips everything
downstream. Setting `continue_on_error: true` on an action changes both:

- the run is **not** marked failed because of it, and
- its dependants are **not** skipped — they run as if it had succeeded.

The failure is still counted and recorded, so reporting stays honest: a workflow
whose only failure was tolerated finishes with status `succeeded` and a non-zero
`failed` count. Use it for genuinely optional steps. Details:
[workflow-engine.md](workflow-engine.md#run-status-vs-per-action-counts).

## Dry-run

Dry-run is a **property of the workflow file** — the `dry_run: true` field — not a
command-line flag. There is no `--dry-run` option.

When `dry_run: true`, the engine runs against a guard gateway (`NullGateway`) that
refuses every Telegram call. It records a planned execution, marks each action
`skipped`, and returns a normal summary — all with **no credentials and no
network**. Dry-run forces concurrency to 1 so the planned order reads clearly.

What dry-run does and does not check:

- ✅ The file parses, the schema is valid, and the dependency graph is sound.
- ❌ It does **not** validate the contents of each action's `with:` arguments.
  Those are checked by the action handler when it actually runs, so a passing
  dry-run proves the plan is well-formed, not that every argument is correct for
  its target.

Dry-run is the safe default for trying a workflow. To go live, set
`dry_run: false` (or remove the line — `false` is the default), authenticate the
account, and run. All shipped [examples](examples.md) use `dry_run: true`.

## Validation

`teleautomata validate <file>` and `load_workflow(path)` check a workflow without
running anything or connecting to Telegram. Validation enforces:

- the top-level structure and every field rule in the tables above;
- unique action ids;
- that every `depends_on` id refers to a real action in the file;
- that no action depends on itself;
- that the dependency graph is acyclic;
- `max_delay_seconds >= initial_delay_seconds` in any retry policy.

A validation error names the offending action or field and exits non-zero, which
makes `validate` a good CI gate (see [github-actions.md](github-actions.md)). As
with dry-run, validation does not check `with:` argument contents.

## Resume

Every execution and action is persisted as it runs, so an interrupted or
partially failed run can be continued with
`teleautomata resume <file> <execution_id>`. Only actions not already recorded as
`succeeded` are attempted again. Resume is safe for idempotent actions; for
non-idempotent ones (for example `send_message`), review recorded outcomes first,
because Telegram may have accepted a request before an interruption was observed.
See [workflow-engine.md](workflow-engine.md#resume-and-idempotency) and
[cli.md](cli.md#resume).

## Common mistakes

- **Expecting file order to be execution order.** Only `depends_on` orders
  actions; siblings run concurrently. Add a dependency if one action must follow
  another (for example, pin only after send).
- **Assuming a passing dry-run means the arguments are correct.** Dry-run and
  `validate` check structure, not `with:` values. A wrong `target` or a missing
  required argument only surfaces on a live run.
- **Putting a phone number in `account`.** `account` is a local session name; you
  authenticate it with `teleautomata auth <account>`.
- **A `retry` with `max_delay_seconds` below `initial_delay_seconds`.** This is
  rejected at validation.
- **Referencing an id in `depends_on` that does not exist**, or creating a cycle.
  Both are rejected at validation with the offending id named.
- **Hard-coding a message id and reusing it on a live run.** In the examples ids
  are illustrative; on a real run, act on the id a send actually returned.

## Related reading

- [actions.md](actions.md) — every action, its arguments, and result keys.
- [workflow-engine.md](workflow-engine.md) — how the engine executes a workflow.
- [examples.md](examples.md) — sixteen runnable, categorized workflows.
- [cli.md](cli.md) — `validate`, `run`, `resume`, and the rest.
- [PUBLIC_API.md](../PUBLIC_API.md) — the schema's stability contract.
