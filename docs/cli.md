# CLI reference

TeleAutomata ships a single command, `teleautomata`, built with Typer.
Running it with no arguments prints help. Every command reads configuration from
the environment and `.env`; see [configuration](configuration.md) for the full
list of settings (credentials, `DATABASE_URL`, `LOG_LEVEL`, directories, and
pacing).

```text
teleautomata [COMMAND] [ARGS]
```

| Command | Purpose |
| --- | --- |
| `init` | Create runtime directories and initialize the database. |
| `auth` | Interactively authenticate an account session. |
| `validate` | Validate a workflow file without connecting to Telegram. |
| `run` | Run a workflow. |
| `resume` | Retry the unfinished actions of a previous execution. |
| `list` | List and validate every workflow in a directory. |
| `history` | Show recent executions. |
| `status` | Show the per-action status of one execution. |

## init

```bash
teleautomata init
```

Creates the session directory and initializes the operation database. Safe to
run repeatedly; it does not overwrite existing data. Run it once before your
first real workflow.

## auth

```bash
teleautomata auth <account>
```

Interactively signs in a session. `<account>` is a **local session name**, not a
phone number, and must match `[a-zA-Z][a-zA-Z0-9_-]{0,63}`; it is the same
`account` value your workflow's `account:` field refers to. Requires
`TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in the environment. You are prompted
for the phone number and, if enabled, the 2FA password — neither is ever stored
by the app; only Telethon's session file is written, and it must be kept private.

## validate

```bash
teleautomata validate <workflow.yaml>
```

Loads and validates a workflow's structure, dependencies, and action arguments
without any network access. Prints the workflow name and action count on
success; a validation error is reported with a non-zero exit. Use this in CI.

## run

```bash
teleautomata run <workflow.yaml>
```

Executes a workflow. If the file sets `dry_run: true`, the run uses a guard
gateway that requires no credentials and touches nothing — the safe way to
inspect intent. A real run connects the authenticated session named by the
workflow's `account:` field. Exits non-zero if any action failed. The printed
summary includes the execution id, which `resume` and `status` consume:

```text
Execution <uuid>: succeeded; succeeded=3, failed=0, skipped=0
```

## resume

```bash
teleautomata resume <workflow.yaml> <execution_id>
```

Re-runs only the actions that did not previously succeed, preserving completed
work. Pass the same workflow file and the execution id from the original run
(see `history`). Exits non-zero if any action still fails.

## list

```bash
teleautomata list [directory]
```

Lists every `*.yml`/`*.yaml` file in `directory` (default
`examples/workflows`), validating each. Valid files show name, account, and
action count (with a `[dry_run]` marker where set); invalid files are flagged
without stopping the listing.

## history

```bash
teleautomata history [--limit N]
```

Shows recent executions from the operation database, newest first. `--limit`
defaults to 20 (1–200). Each row lists the execution id, status, workflow name,
account, and start/completion times.

## status

```bash
teleautomata status <execution_id>
```

Shows one execution and the status of each of its actions — action id, type,
status, attempt count, and error code where present. Exits non-zero if no
execution matches the id.

## Exit codes

- `0` — success.
- `1` — a workflow action failed (`run`, `resume`), or no matching execution was
  found (`status`).
- `2` — a usage or argument error (Typer), such as a missing file or a malformed
  account name.
