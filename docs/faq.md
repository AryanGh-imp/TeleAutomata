# FAQ

Questions a new user, contributor, or evaluator tends to ask. For reference
material see the [action](actions.md), [CLI](cli.md), and [API](api.md) docs;
this page focuses on the *why*.

## What is TeleAutomata for?

Running Telegram account operations declaratively. You describe a sequence of
actions in a YAML workflow — send a message, add members, restrict a user — and
the engine runs them with dependency ordering, retries, flood-wait handling, and
a durable record of what happened. It automates a **user account** via MTProto
(Telethon), which is distinct from the Bot API.

## Is this a bot framework?

No. It drives a real user account, so it can do things bots cannot (join groups
by invite link, manage dialogs), and it must respect the same limits a human
account has. That is why pacing and flood-wait handling are built in rather than
bolted on. Use it responsibly and within Telegram's terms.

## How are my API credentials handled?

`TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are read from the environment (or a
local `.env`) and used only to open a session. **The framework never writes them
to disk or to the database.** Authentication is interactive through
`teleautomata auth`; your phone number and 2FA password are passed
straight to Telethon and never stored by this app. The only persisted secret is
Telethon's own session file under the session directory, which is gitignored and
should be treated as sensitive. See [security](security.md).

## What does `dry_run` actually do?

A workflow with `dry_run: true` runs against the `NullGateway`, whose every
method raises. The engine plans and records each action as
planned-but-not-run, so you can validate structure and intent with **no
credentials and no network access**. It is the safe default for trying a
workflow. `teleautomata validate` goes further and checks a file without
running anything at all.

## Can I run workflows in CI (e.g. GitHub Actions)?

Yes, and validation is the recommended use. `teleautomata validate` never
connects to Telegram, so a CI job that validates your workflow files on every
push needs no credentials and is completely safe — it is the ideal gate. You can
also run workflows on a manual trigger or a schedule; keep those pointed at
`dry_run: true` files unless you deliberately set up a live run, which
additionally needs an authenticated session file (password-equivalent) in the
runner. Copy-and-adapt templates live in
[`examples/github-actions/`](../examples/github-actions/), and
[github-actions.md](github-actions.md) is the full walkthrough, including secrets
handling and exit codes.

## What happens when Telegram rate-limits me?

A flood-wait becomes a `RateLimitError` carrying the wait Telegram asked for. The
engine sleeps for exactly that long and retries, unless the wait exceeds
`max_flood_wait_seconds` (then it fails fast rather than hanging). A per-account
rate limiter also spaces requests so you are less likely to hit limits in the
first place. Transient network errors back off exponentially; bad input fails
immediately without retrying.

## If a workflow fails halfway, do I start over?

No. Every execution and action is persisted as it runs. Re-run with
`teleautomata resume <workflow> <execution_id>` and only the actions that
did not already succeed are attempted again; completed work is preserved. Find
the execution id with `teleautomata history`.

## Why is the action library "only" 29 actions?

By design. The goal of v1.0 is a clean, well-documented framework, not the
largest possible action count. The shipped actions are a representative set that
exercises every architectural capability — validation, batching with per-user
failure isolation, dry-run guarding, error translation. Adding more is
deliberately easy (see below), which makes new actions ideal first
contributions.

## How do I add an action?

Walk the five layers — schema, port, registry handler, Telethon adapter, null
gateway — as described in the [extension guide](extending.md). An import-time
guard ensures you cannot half-add one, and the fake gateway lets you test it
without touching Telegram.

## Two public actions would call the same Telegram method. Should I add both?

No. Prefer one action and document the alias. For example `kick` folds into
`remove_members` and `restore` into `unban_members`, because they issue the same
MTProto call. API stability and a small, coherent surface matter more than
action count.

## How do I run the tests and checks?

Run the full quality gate before every change; the exact commands are in
[Contributing → Quality gate](../CONTRIBUTING.md#quality-gate). Tests use
in-memory SQLite and a fake gateway, so they are fast and need no credentials.
See [testing](testing.md) and [development](development.md).

## Which Python versions are supported?

Python 3.12 and newer. The code uses modern typing (`StrEnum`, `X | None`,
`Annotated` CLI parameters) and is checked under strict mypy.

## Can I embed the engine instead of using the CLI?

Yes. The CLI is a thin wrapper over `WorkflowEngine`; the [API reference](api.md)
shows the wiring. Construct the engine with a gateway, repository, and rate
limiter, then call `run(load_workflow(path))`.
