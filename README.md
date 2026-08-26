<div align="center">

<img src="https://raw.githubusercontent.com/AryanGh-imp/TeleAutomata/master/docs/assets/teleautomata_logo.gif" alt="TeleAutomata logo" />
<h1>TeleAutomata</h1>

<p><strong>Safety-first, workflow-driven Telegram account automation.</strong></p>

<p>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+" />
  <a href="https://github.com/AryanGh-imp/TeleAutomata/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/lint-ruff-261230.svg" alt="Linted with Ruff" />
  <img src="https://img.shields.io/badge/types-mypy%20strict-2a6db2.svg" alt="Type-checked with mypy (strict)" />
  <a href="https://pypi.org/project/teleautomata/"><img src="https://img.shields.io/pypi/v/teleautomata.svg" alt="PyPI version" /></a>
</p>

</div>

<!--
  Demo: to show a short terminal recording, drop it at docs/assets/demo.gif
  and uncomment the line below.
  <p align="center"><img src="docs/assets/demo.gif" alt="TeleAutomata demo" width="720" /></p>
-->

TeleAutomata manages Telegram groups and channels by running **declarative YAML
workflows** against a real user account. You describe *what* should happen — send
a message, create a channel, add members from a CSV, restrict a user — and the
engine handles dependency ordering, retries, flood-wait handling, and a durable
record of every run.

## Why it exists

Automating a Telegram user account is easy to do badly: an ad-hoc script fires
requests as fast as it can, has no memory of what already ran, and treats a
rate-limit or a permission error as a crash. TeleAutomata is built the opposite
way, around three commitments:

- **Safety is the default.** Telegram's rate limits, permissions, and responses
  are treated as authoritative — never bypassed. Every shipped example is a
  dry run, and going live is a deliberate, confirmed act.
- **Runs are durable.** Every execution and action is persisted as it happens, so
  an interrupted run resumes instead of starting over, and you can inspect
  exactly what occurred afterwards.
- **The architecture is the product.** A small, coherent, well-tested core with a
  frozen, representative action set — not a sprawling pile of one-off commands.

It automates a **user account** over MTProto (via Telethon), which is distinct
from — and more capable than — the Bot API, and carries the same limits a human
account does.

## Capabilities

- **Declarative workflows** — a versioned YAML schema with a validated dependency
  graph (DAG); independent actions run concurrently, dependent ones wait.
- **29 actions** across entity management, messaging, dialogs, membership, and
  member management — a deliberately frozen, representative set.
- **Resilient execution** — per-action retry policies with full-jitter backoff,
  flood-wait handling with a safety ceiling, and per-user failure isolation in
  batch actions.
- **`continue_on_error`** for genuinely optional steps, with honest reporting.
- **Dry-run by file property** — no `--dry-run` flag; `dry_run: true` plans a run
  with no credentials and no network, so intent is reviewable in version control.
- **Durable history & resume** — a SQLite (local) or PostgreSQL (production)
  operation database, inspectable via `history` and `status`.
- **A polished CLI** — Typer + Rich output that degrades cleanly to plain text in
  pipes and CI.
- **Strictly typed, offline-tested** — strict mypy, and a test suite that runs
  without a network or credentials against a fake gateway.

## Architecture at a glance

TeleAutomata is ports-and-adapters: a pure **domain** core, an **application**
engine that orchestrates workflows, and **infrastructure** adapters (Telethon,
persistence, pacing) behind a single `TelegramGateway` contract. Because the
engine depends only on that contract, the whole system runs against an in-memory
fake in tests. See [docs/architecture.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/architecture.md) for the full
design, diagrams, and rationale.

## Installation

TeleAutomata is a Python package and command-line tool. Install it from PyPI with
[pip](https://pip.pypa.io/) — this is the standard, recommended way to use it, and
cloning the repository is **not** required:

```bash
pip install teleautomata
teleautomata --version
```

It requires **Python 3.12+**. For PostgreSQL support, install the extra:
`pip install "teleautomata[postgres]"`.

### Installing from source — for contributors and development

Clone the repository only if you intend to develop TeleAutomata, run a fork, or work
on the in-tree examples:

```bash
git clone https://github.com/AryanGh-imp/TeleAutomata.git
cd TeleAutomata

python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"            # Add ,postgres for PostgreSQL support
```

See [CONTRIBUTING.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/CONTRIBUTING.md) for the full development workflow.

## Quick start

TeleAutomata runs from a directory of your own — **no clone required**. These steps
take you from an empty directory to a safe dry run, and then to a real run.

Along the way you create two files; keep their roles distinct:

- **`.env`** — your credentials and configuration (Telegram API id/hash, database
  URL, pacing defaults).
- **`workflow.yaml`** — the automation itself: the ordered actions to perform.

**1 — Install TeleAutomata** from PyPI:

```bash
pip install teleautomata
teleautomata --version
```

**2 — Initialize the local runtime.** Creates the runtime directories (including
`sessions/`) and the operation database in the current directory:

```bash
teleautomata init
```

**3 — Create your `.env`.** Configuration is read from environment variables or a
`.env` file in the working directory. Create `.env` and add your Telegram API
credentials:

```dotenv
# .env
TELEGRAM_API_ID=1234567
TELEGRAM_API_HASH=your_api_hash_here
```

Get both values from [my.telegram.org](https://my.telegram.org) → **API development
tools**, where you register a developer application. These two are the only required
settings; every other value has a safe default (see
[docs/configuration.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/configuration.md) for the full list). *(Installed from a
clone instead? Copy the shipped template: `cp .env.example .env`.)*

**4 — Authenticate the account.** Runs an interactive phone/2FA login and writes a
reusable session file under `sessions/`; nothing else is stored:

```bash
teleautomata auth primary          # "primary" is a local session name, not a phone number
```

**5 — Create a workflow.** Describe what should happen in `workflow.yaml`. This one
sends a message and ships as a dry run:

```yaml
version: 1
name: send-message
account: primary                   # the session you authenticated in step 4
dry_run: true                      # plan only — makes no Telegram request
actions:
  - id: greet
    type: send_message
    with:
      target: "@my_channel"
      message: "Hello from TeleAutomata."
```

**6 — Validate it.** Checks the schema and dependency graph without connecting to
Telegram:

```bash
teleautomata validate workflow.yaml
```

**7 — Run the dry run.** Because `dry_run: true`, this records a planned execution
but makes **no** Telegram request and needs no credentials — so you can review the
intent safely before anything happens for real:

```bash
teleautomata run workflow.yaml
```

**8 — Go live when ready.** Set `dry_run: false` in `workflow.yaml`, then run it
again. A live run asks for confirmation first (pass `--yes` to skip the prompt in
automation):

```bash
teleautomata run workflow.yaml
```

Inspect workflows and past runs at any time, without connecting to Telegram:

```bash
teleautomata list .                    # validate and summarize every workflow in a directory
teleautomata history                   # recent executions
teleautomata status <execution-id>     # per-action detail for one execution
```

If a run is interrupted, resume it without repeating completed work:

```bash
teleautomata resume workflow.yaml <execution-id>
```

> **Never** commit `.env` or the `sessions/` directory. Credentials come only from
> the environment or `.env`, and a session file is account access material.

The repository's [`examples/`](https://github.com/AryanGh-imp/TeleAutomata/tree/master/examples) directory is a reference cookbook of
ready-made workflows — browse it for patterns, and copy any file into your own
project as a starting point.

## Workflow format

```yaml
version: 1
name: update-project-channel
account: primary                     # a local session name, not a phone number
dry_run: true
actions:
  - id: check_target
    type: resolve_target
    with: {target: "@my_project"}
  - id: update_description
    type: update_entity
    depends_on: [check_target]       # runs only after check_target succeeds
    with:
      target: "@my_project"
      about: "A current project description"
    retry: {max_attempts: 3, initial_delay_seconds: 2, max_delay_seconds: 60}
```

The full authoring guide — every field, dependency and retry semantics, and
common mistakes — is in [docs/workflows.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/workflows.md); the 29 actions and
their arguments are catalogued in [docs/actions.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/actions.md).

## Command-line interface

| Command | Purpose |
| --- | --- |
| `init` | Create runtime directories and initialize the database. |
| `auth <account>` | Interactively authenticate an account session. |
| `validate <file>` | Validate a workflow's schema and dependency graph (no network). |
| `run <file> [--yes]` | Run a workflow (dry-run or live). |
| `resume <file> <id> [--yes]` | Retry only the unfinished actions of a prior run. |
| `list [dir]` | Validate and summarize every workflow in a directory. |
| `history [--limit N]` | Show recent executions. |
| `status <id>` | Show per-action status for one execution. |

Exit codes are a stable contract (`0` success, `1` expected failure, `2` usage
error). Full descriptions and examples: [docs/cli.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/cli.md).

## Examples

The [`examples/`](https://github.com/AryanGh-imp/TeleAutomata/tree/master/examples) directory is a runnable cookbook: **sixteen** small,
focused workflows covering messaging, dialogs, entity and member management,
retry and `continue_on_error`, every accepted target format, CSV-driven member
lists, and a branching/fan-in DAG. All ship with `dry_run: true`, so they are
safe to run as-is with no credentials.

```bash
teleautomata list examples/workflows                    # validate all sixteen
teleautomata run examples/workflows/send-message.yaml   # dry-run one
```

Each example is indexed and explained in [docs/examples.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/examples.md). To
run workflows in CI, [`examples/github-actions/`](https://github.com/AryanGh-imp/TeleAutomata/tree/master/examples/github-actions)
provides copy-and-adapt templates — validate-on-push, manual, scheduled, and an
install-from-PyPI variant — with the full walkthrough in
[docs/github-actions.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/github-actions.md).

## Documentation

**Using it**
&nbsp;·&nbsp; [Workflows](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/workflows.md)
&nbsp;·&nbsp; [Actions](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/actions.md)
&nbsp;·&nbsp; [CLI](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/cli.md)
&nbsp;·&nbsp; [Examples](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/examples.md)
&nbsp;·&nbsp; [Configuration](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/configuration.md)

**Running in production & CI**
&nbsp;·&nbsp; [Security](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/security.md)
&nbsp;·&nbsp; [GitHub Actions](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/github-actions.md)
&nbsp;·&nbsp; [Troubleshooting](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/troubleshooting.md)

**Understanding it**
&nbsp;·&nbsp; [Architecture](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/architecture.md)
&nbsp;·&nbsp; [Workflow engine](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/workflow-engine.md)
&nbsp;·&nbsp; [Telegram integration](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/telegram-integration.md)
&nbsp;·&nbsp; [API & interfaces](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/api.md)
&nbsp;·&nbsp; [Public API contract](https://github.com/AryanGh-imp/TeleAutomata/blob/master/PUBLIC_API.md)

**Contributing & reference**
&nbsp;·&nbsp; [Contributing](https://github.com/AryanGh-imp/TeleAutomata/blob/master/CONTRIBUTING.md)
&nbsp;·&nbsp; [Development](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/development.md)
&nbsp;·&nbsp; [Extending](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/extending.md)
&nbsp;·&nbsp; [Testing](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/testing.md)
&nbsp;·&nbsp; [FAQ](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/faq.md)

## Development

Set up an editable install with dev dependencies and run the quality gate before
every change:

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src && pytest && python -m build
```

Tests use in-memory SQLite and a fake gateway — no network, no credentials. See
[CONTRIBUTING.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/CONTRIBUTING.md) for the contribution workflow and
[docs/development.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/development.md) for environment specifics.

## Security

TeleAutomata automates real accounts, so it treats everything it touches as
capable of real-world effect. Credentials are never persisted; session files are
password-equivalent; and pacing defaults are conservative. Only automate entities
and accounts you are authorized to manage. Full guidance is in
[docs/security.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/docs/security.md), and vulnerabilities should be reported per
[SECURITY.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/SECURITY.md).

## Project status

Version **1.0.2**, with a frozen public API defined in
[PUBLIC_API.md](https://github.com/AryanGh-imp/TeleAutomata/blob/master/PUBLIC_API.md). Install it from PyPI with `pip install teleautomata`
(see [Installation](#installation)).

## License

Released under the [MIT License](https://github.com/AryanGh-imp/TeleAutomata/blob/master/LICENSE).
