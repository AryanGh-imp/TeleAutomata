# CLI reference

TeleAutomata ships a single command, `teleautomata`, built with Typer and
rendered with Rich. Running it with no arguments prints help. Every command
reads configuration from the environment and `.env`; see
[configuration](configuration.md) for the full list of settings (credentials,
`DATABASE_URL`, `LOG_LEVEL`, directories, and pacing).

```text
teleautomata [GLOBAL OPTIONS] COMMAND [ARGS]
```

Commands are grouped in `--help` by purpose:

| Group | Command | Purpose |
| --- | --- | --- |
| Setup | `init` | Create runtime directories and initialize the database. |
| Setup | `auth` | Interactively authenticate an account session. |
| Workflows | `validate` | Validate a workflow file without connecting to Telegram. |
| Workflows | `run` | Run a workflow. |
| Workflows | `resume` | Retry the unfinished actions of a previous execution. |
| Workflows | `list` | List and validate every workflow in a directory. |
| Inspection | `history` | Show recent executions. |
| Inspection | `status` | Show the per-action status of one execution. |

## Global options

- `--version`, `-V` — print the version and exit.
- `--debug` — show full tracebacks instead of concise error panels. Use this
  when an *unexpected* error needs diagnosing; expected failures (validation,
  configuration, gateway errors) are always reported as actionable panels
  regardless of this flag.
- `--help` — show help for the program or any command.

## Output and scripting

In an interactive terminal, output is styled: results are printed as bordered
panels and tables with colour and status glyphs. When output is **not** a
terminal — piped, redirected, or captured in CI — colour and borders are
dropped automatically and tables become plain, column-aligned text, so logs stay
readable and free of ANSI escapes.

Results are written to **stdout**; errors are written to **stderr** as panels.
Exit codes (below) are the stable, machine-readable contract. The *wording* and
layout of human output may change between releases — automation should key off
exit codes and, when it needs execution data, the `status`/`history` commands
rather than scraping prose.

## init

```bash
teleautomata init
```

Creates the session directory and initializes the operation database. Safe to
run repeatedly; it does not overwrite existing data. Run it once before your
first real workflow. Prints `✓ Initialized runtime directories and database.`

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

Loads and validates a workflow's structure and dependency graph — the schema,
unique action ids, and resolvable, acyclic dependencies — without any network
access. (Each action's `with:` arguments are validated when the action runs, not
here; a dry run likewise plans without checking them.) On success it prints a
panel summarising the workflow; a validation error names the offending field and
exits non-zero. Use this as a CI gate — see [github-actions.md](github-actions.md).

```text
╭─ ✓ Workflow valid ─╮
│         Name  sample-dry-run │
│      Account  primary        │
│      Actions  2              │
│ Dependencies  1              │
│         Mode  dry run        │
╰──────────────────────────────╯
```

## run

```bash
teleautomata run <workflow.yaml> [--yes]
```

Executes a workflow. If the file sets `dry_run: true`, the run uses a guard
gateway that requires no credentials and touches nothing — the safe way to
inspect intent. A real run connects the authenticated session named by the
workflow's `account:` field.

Before a **live** run in an interactive terminal, you are asked to confirm,
because it performs real Telegram actions:

```text
Run 'live-flow' against live account 'primary'? This performs real Telegram actions. [y/N]:
```

Pass `--yes`/`-y` to skip the prompt (for trusted scripts). Dry runs are never
prompted. In a non-interactive context (pipe/CI) the prompt is skipped so
automation does not hang — guard live runs there with your own controls.

Exits non-zero only if the run as a whole failed. An action that failed under
`continue_on_error` is reported in the counts but does not fail the run. The
summary panel includes the execution id, which `resume` and `status` consume:

```text
╭─ ✓ Workflow completed ─╮
│  Workflow  sample-dry-run                          │
│   Account  primary                                 │
│ Execution  6f1e2d3c-4b5a-6789-abcd-ef0123456789    │
│    Result  3 succeeded  ·  0 failed  ·  0 skipped   │
│      Mode  dry run                                 │
╰────────────────────────────────────────────────────╯
```

## resume

```bash
teleautomata resume <workflow.yaml> <execution_id> [--yes]
```

Re-runs only the actions that did not previously succeed, preserving completed
work. Pass the same workflow file and the execution id from the original run
(see `history`). Like `run`, a live resume prompts for confirmation in an
interactive terminal unless `--yes` is given. Exits non-zero if any action still
fails.

## list

```bash
teleautomata list [directory]
```

Lists every `*.yml`/`*.yaml` file in `directory` (default
`examples/workflows`), validating each. The table shows file, name, account,
action count, whether the workflow is a dry run, and a per-file status. Valid
files are marked `valid`; invalid files are flagged `invalid` with the offending
field, without stopping the listing.

```text
 File              Name             Account   Actions   Dry run   Status
 sample.yaml       sample-dry-run   primary         2   yes       valid
 broken.yaml       —                —               —   —         invalid: name: too short
```

## history

```bash
teleautomata history [--limit N]
```

Shows recent executions from the operation database, newest first. `--limit`
defaults to 20 (1–200). Each row lists the start time, status, workflow name,
account, full execution id, and completion time. When nothing has been recorded
yet it prints `No executions recorded yet.`

## status

```bash
teleautomata status <execution_id>
```

Shows one execution and the status of each of its actions — action id, type,
status, attempt count, and error code where present. If no execution matches the
id, an error panel is printed to stderr and the command exits non-zero.

```text
╭─ Execution detail ─╮
│ Execution  6f1e2d3c-4b5a-6789-abcd-ef0123456789 │
│  Workflow  sample-dry-run                        │
│   Account  primary                               │
│    Status  ✓ succeeded                           │
│   Started  2026-08-24 12:00:00                   │
│ Completed  2026-08-24 12:00:01                   │
╰──────────────────────────────────────────────────╯
 Action           Type             Status        Attempts   Error
 create_channel   create_channel   ○ skipped            1   —
 verify_channel   resolve_target   ○ skipped            1   —
```

## Exit codes

- `0` — success.
- `1` — an expected failure was reported as an error panel (on stderr) or the
  run failed as a whole. This covers: a workflow that failed validation
  (`validate`); missing or invalid configuration such as absent Telegram
  credentials (`run`, `resume`, `auth`); a gateway error; a run in which at
  least one action failed *without* `continue_on_error` (`run`, `resume`) —
  failures tolerated by `continue_on_error` are reported in the summary but do
  not set this code; and no matching execution found (`status`). An *unexpected*
  error also exits `1`; re-run with `--debug` for the traceback.
- `2` — a usage or argument error (Typer), such as a missing file argument or a
  malformed account name.
