# Running TeleAutomata in GitHub Actions

This guide shows how to run TeleAutomata workflows in [GitHub
Actions](https://docs.github.com/actions), GitHub's built-in CI/CD. It starts
from zero — no prior Actions experience assumed — and builds up to a scheduled,
credentialed run, with the safety and security trade-offs called out at each
step.

Ready-to-adapt example files live in
[`examples/github-actions/`](../examples/github-actions/). This document explains
them.

## Contents

1. [What this is for, and what to be careful about](#1-what-this-is-for-and-what-to-be-careful-about)
2. [Two ways to run TeleAutomata in CI](#2-two-ways-to-run-teleautomata-in-ci)
3. [Repository setup](#3-repository-setup)
4. [Installing TeleAutomata in the runner](#4-installing-teleautomata-in-the-runner)
5. [Providing credentials with GitHub Secrets](#5-providing-credentials-with-github-secrets)
6. [Validating workflows in CI (no credentials)](#6-validating-workflows-in-ci-no-credentials)
7. [Manual runs with workflow_dispatch](#7-manual-runs-with-workflow_dispatch)
8. [Scheduled runs with cron](#8-scheduled-runs-with-cron)
9. [Dry-run safety](#9-dry-run-safety)
10. [Authenticating for unattended live runs](#10-authenticating-for-unattended-live-runs)
11. [Reading logs and diagnosing failures](#11-reading-logs-and-diagnosing-failures)
12. [Exit codes and how GitHub interprets them](#12-exit-codes-and-how-github-interprets-them)
13. [Security considerations](#13-security-considerations)
14. [Complete, copy-pasteable examples](#14-complete-copy-pasteable-examples)

## 1. What this is for, and what to be careful about

There are two very different things you might want CI to do:

- **Validate** workflow files on every push or pull request. This is pure
  linting — `teleautomata validate` reads and schema-checks a file and never
  connects to Telegram. It needs no credentials and is completely safe. **This is
  the recommended use of CI and where you should start.**
- **Execute** workflows automatically (on a button press or a schedule). This
  performs real Telegram actions and therefore needs both API credentials **and**
  an authenticated session. Running a real account from CI has real security
  implications (covered in [§13](#13-security-considerations)) and is an advanced,
  deliberately-chosen setup — not the default.

Everything below treats validation as the primary case and live execution as an
opt-in you take with eyes open.

## 2. Two ways to run TeleAutomata in CI

Before writing any YAML, decide how the runner will get the `teleautomata`
command. There are two approaches, and they differ only in the install step —
everything else in this guide (secrets, validation, dry-run, exit codes) applies
to both.

### Approach A — install from PyPI (recommended for end users)

Your repository holds only your own workflow YAML and one CI file. The runner
installs the published package from PyPI; it does **not** clone TeleAutomata's
source.

```
Your repository (workflow.yaml + .github/workflows/run.yml)
        |
        v
GitHub Actions:  setup Python 3.12  ->  pip install teleautomata  ->  teleautomata run workflow.yaml  ->  Telegram
```

`actions/checkout` here checks out **your** repository (so the runner can read
your `workflow.yaml`); the TeleAutomata source repository is never cloned. This
is the right approach for normal use: automating your own groups and channels
from your own repo. The template is
[`run-from-pypi.yml`](../examples/github-actions/run-from-pypi.yml).

> **Availability.** TeleAutomata is **not yet published to PyPI** (see the README
> project-status note). Until the first release lands, `pip install teleautomata`
> will not resolve — use Approach B in the meantime, or install from a git ref
> (`pip install "git+https://github.com/AryanGh-imp/TeleAutomata.git"`). Once
> published, pin a version for reproducible CI (`pip install teleautomata==1.0.0`).

### Approach B — run from a source checkout (for contributors / development)

The workflow files live **inside** a checkout of the TeleAutomata repository (or
a fork), so the runner installs the package from that checked-out source.

```
TeleAutomata repository (or a fork)
        |
        v
GitHub Actions:  actions/checkout  ->  Python 3.12  ->  pip install .  ->  teleautomata run <workflow.yaml>
```

`actions/checkout` clones the TeleAutomata repository onto the runner (its
`pyproject.toml` is at the repo root), and `pip install .` builds it from that
source. You do **not** need to clone anything locally — the checkout happens on
the runner. This is the right approach for contributors, forks, development and
testing, and for the workflows that ship inside this repository under
`examples/workflows/`. The shipped
[`validate.yml`](../examples/github-actions/validate.yml),
[`run-manual.yml`](../examples/github-actions/run-manual.yml), and
[`scheduled.yml`](../examples/github-actions/scheduled.yml) all use this approach.

**Which should you pick?** If you are automating your own account from your own
repository, use **Approach A**. If you are contributing to TeleAutomata, running a
fork, or authoring workflows that live in this repository, use **Approach B**.

## 3. Repository setup

A GitHub Actions workflow is a YAML file under `.github/workflows/` in your
repository. GitHub automatically discovers and runs files **only** in that exact
directory — not in subdirectories, and not elsewhere in the repo.

That is why this project keeps its examples under
[`examples/github-actions/`](../examples/github-actions/): they are inert there
and will never run by accident. To use one, copy it into your own repository:

```bash
mkdir -p .github/workflows
cp examples/github-actions/validate.yml .github/workflows/validate.yml
git add .github/workflows/validate.yml
git commit -m "ci: validate teleautomata workflows"
git push
```

If you are an end user following **Approach A**, copy
[`run-from-pypi.yml`](../examples/github-actions/run-from-pypi.yml) instead and
keep your own `workflow.yaml` at your repository root. After you push, open the
**Actions** tab on GitHub to watch runs.

## 4. Installing TeleAutomata in the runner

Each job runs on a fresh virtual machine ("runner"). You install Python, then the
package — using whichever approach from [§2](#2-two-ways-to-run-teleautomata-in-ci)
you chose. Both start the same way:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"    # TeleAutomata requires 3.12+
```

**Approach A (PyPI)** — install the published package. `actions/checkout` is
still used, but only to fetch *your* repository's workflow YAML:

```yaml
- run: |
    python -m pip install --upgrade pip
    pip install teleautomata          # pin, e.g. teleautomata==1.0.0
```

**Approach B (source checkout)** — `actions/checkout` clones TeleAutomata itself,
and you install it from the repo root:

```yaml
- run: |
    python -m pip install --upgrade pip
    pip install .
```

Either way, the install puts the `teleautomata` command on the runner's `PATH`,
and every command below behaves identically.

## 5. Providing credentials with GitHub Secrets

**Never put credentials in a workflow file.** Anything committed to the repo —
including CI YAML — is visible to anyone who can read the repo and lives forever
in git history. Use GitHub Secrets instead.

Add them under **Settings → Secrets and variables → Actions → New repository
secret**:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`

Reference them in a workflow through the `secrets` context, exposing them as
environment variables — the exact names TeleAutomata reads:

```yaml
env:
  TELEGRAM_API_ID: ${{ secrets.TELEGRAM_API_ID }}
  TELEGRAM_API_HASH: ${{ secrets.TELEGRAM_API_HASH }}
```

GitHub masks secret values in logs. They are **not** available to workflows
triggered by pull requests from forks, which is a deliberate protection — do not
try to defeat it. A validation-only workflow needs none of this.

## 6. Validating workflows in CI (no credentials)

The safest and most useful CI job validates every workflow on each push and pull
request. `teleautomata validate` exits non-zero on the first invalid file, which
fails the step and the job.

End users (Approach A) validate their own file directly —
`teleautomata validate workflow.yaml`, or a loop over their repo's `*.yaml`. The
shipped template uses Approach B and validates this repository's own examples:

```yaml
# .github/workflows/validate.yml
name: Validate workflows
on:
  push:
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          python -m pip install --upgrade pip
          pip install .                 # Approach A: pip install teleautomata
      - name: Validate every example workflow
        run: |
          for file in examples/workflows/*.yaml; do
            echo "::group::$file"
            teleautomata validate "$file"
            echo "::endgroup::"
          done
```

`validate` checks the file's structure and dependency graph — the schema, unique
action ids, known and acyclic dependencies — without any network access. It does
not connect to Telegram and needs no secrets. (`echo "::group::"` /
`"::endgroup::"` are GitHub log-folding markers that make multi-file output
collapsible; they are optional.)

The complete file is
[`examples/github-actions/validate.yml`](../examples/github-actions/validate.yml).

## 7. Manual runs with workflow_dispatch

`workflow_dispatch` adds a **Run workflow** button to the Actions tab so you can
trigger a run by hand, optionally with inputs. This example lets you type which
workflow file to run and defaults to a dry-run example:

```yaml
on:
  workflow_dispatch:
    inputs:
      workflow:
        description: "Path to the workflow YAML to run"
        required: true
        default: "examples/workflows/send-message.yaml"
```

```yaml
- name: Validate the selected workflow
  run: teleautomata validate "${{ inputs.workflow }}"
- name: Run the selected workflow
  run: teleautomata run "${{ inputs.workflow }}" --yes
```

`--yes` skips the interactive confirmation. It is not strictly required — CI has
no terminal, so the confirmation prompt is skipped automatically (see
[cli.md](cli.md)) — but passing it makes the intent explicit and keeps the step
robust.

The source-checkout template is
[`examples/github-actions/run-manual.yml`](../examples/github-actions/run-manual.yml);
the PyPI/end-user equivalent, which runs your repository's own `workflow.yaml`, is
[`examples/github-actions/run-from-pypi.yml`](../examples/github-actions/run-from-pypi.yml).

> A live run of a non-dry-run file needs more than credentials — see
> [§9](#9-dry-run-safety), [§10](#10-authenticating-for-unattended-live-runs), and
> [§13](#13-security-considerations). Out of the box these examples target a
> `dry_run: true` file and do nothing to your account.

## 8. Scheduled runs with cron

`schedule` runs a workflow on a cron timer. **GitHub cron is always UTC** and
ignores your local timezone.

```yaml
on:
  schedule:
    - cron: "17 8 * * 1"   # 08:17 UTC every Monday
  workflow_dispatch:        # also allow a manual run
```

Two practical notes:

- Prefer an off-the-hour minute (here `17`, not `0`). Jobs scheduled exactly on
  the hour are the most contended on GitHub's shared infrastructure and the most
  likely to start late.
- Scheduled runs always use the workflow file on your **default branch**.

The complete file is
[`examples/github-actions/scheduled.yml`](../examples/github-actions/scheduled.yml).

## 9. Dry-run safety

Dry-run is a property of the **workflow file** (`dry_run: true`), not a CLI flag —
there is no `--dry-run` option. A dry-run records a plan and marks every action
`skipped` without touching Telegram, so it needs no credentials or session. All
of this project's example workflows ship with `dry_run: true`.

This makes dry-run the ideal thing to run in CI: you exercise the whole
pipeline — parse, validate, plan, persist — with zero risk. The example run and
schedule workflows point at dry-run files precisely so that adopting them cannot
harm an account.

A **live** run (`dry_run: false`) in CI additionally requires an authenticated
Telethon **session file** — credentials alone are not enough. Provisioning one
safely is its own topic; see
[§10](#10-authenticating-for-unattended-live-runs).

## 10. Authenticating for unattended live runs

A live run needs an authenticated Telethon **session** in addition to the API
credentials from [§5](#5-providing-credentials-with-github-secrets). Understanding
how the two CLI paths differ explains why:

- **`teleautomata auth <account>` is interactive.** It prompts for your phone
  number and 2FA password to create the session, so it **cannot run unattended on
  a GitHub runner**. Do not try to script it into CI.
- **`teleautomata run` is non-interactive.** For a live run it opens the existing
  session for the workflow's `account:` and, if that session is missing or not
  authorized, fails fast with a permanent error
  (`account '<name>' is not authenticated; run the auth command first`) — it never
  prompts. So the session must already be present on the runner before `run`.

The supported pattern is therefore: **authenticate once locally, then inject the
resulting session into the runner as a secret.** There is no CLI export/import
command — you handle the session *file* directly.

1. **Create the session locally**, on a trusted machine, with the same account
   name your workflow uses (`account: primary` → `primary.session`):

   ```bash
   teleautomata auth primary
   ```

   This writes `sessions/primary.session` (an SQLite file) under `SESSION_DIR`
   (default `./sessions`).

2. **Base64-encode it** into a single line and copy the output:

   ```bash
   base64 -w0 sessions/primary.session      # macOS: base64 -i sessions/primary.session
   ```

3. **Store it as a GitHub Secret** — for example `TELEGRAM_SESSION_B64` — under
   **Settings → Secrets and variables → Actions**, alongside `TELEGRAM_API_ID`
   and `TELEGRAM_API_HASH`.

4. **Decode it on the runner** into `SESSION_DIR` *before* the `run` step, using
   the same file name:

   ```yaml
   - name: Restore the Telegram session
     run: |
       mkdir -p sessions
       echo "${{ secrets.TELEGRAM_SESSION_B64 }}" | base64 -d > sessions/primary.session
   - name: Run the workflow live
     run: teleautomata run workflow.yaml --yes
   ```

   (If you set a custom `SESSION_DIR`, decode into that directory and keep the
   `<account>.session` name.)

This is exactly the optional, commented-out step in
[`run-from-pypi.yml`](../examples/github-actions/run-from-pypi.yml).

**Treat this as sensitive.** A session file is password-equivalent: anyone holding
it can act as your account (see [security.md](security.md)). Only inject one into
CI as a deliberate, reviewed decision, and observe the rules in
[§13](#13-security-considerations) — never print it, never upload it as an
artifact, and rotate it (re-auth and re-encode) if you suspect exposure. If you do
not need automated *live* runs, prefer keeping CI on dry-run files and skip this
entirely.

## 11. Reading logs and diagnosing failures

Open the **Actions** tab, pick a run, then a job, to see per-step logs. Each
`run:` step is expandable; failed steps are marked and expanded by default.

TeleAutomata detects that it is not attached to a terminal and drops colour and
box-drawing automatically, so CI logs are plain, readable text (see
["Output and scripting" in cli.md](cli.md#output-and-scripting)). Results go to
stdout; error panels go to stderr. For a deeper look, add `--debug` to a `run`/
`resume` step to print full tracebacks for *unexpected* errors:

```yaml
- run: teleautomata --debug run examples/workflows/send-message.yaml --yes
```

To inspect what a run recorded, the `history` and `status` commands read the
operation database — but note the default database is a local SQLite file that
does **not** persist between CI runs unless you configure a durable
`DATABASE_URL` or cache it.

## 12. Exit codes and how GitHub interprets them

A GitHub step succeeds when its command exits `0` and fails on any non-zero exit.
By default each `run:` step executes under `bash -eo pipefail`, so the first
failing command aborts the step. TeleAutomata's exit codes (full list in
[cli.md](cli.md#exit-codes)) map cleanly onto this:

| Exit code | Meaning | Effect in GitHub Actions |
| --- | --- | --- |
| `0` | Success. `validate` passed; a run finished with no fatal failures. | Step passes ✓ |
| `1` | Expected failure: invalid workflow, missing credentials, a gateway error, or a run where an action failed **without** `continue_on_error`. | Step fails ✗ |
| `2` | Usage error: a missing file argument or a malformed account name. | Step fails ✗ |

Consequences worth internalising:

- An invalid workflow file fails your validation job — exactly the CI gate you
  want.
- In the validation loop, `set -e` means the **first** invalid file fails the
  job; fix it and re-run to surface any later ones.
- An action failure that you tolerated with `continue_on_error: true` is reported
  in the run summary but does **not** exit non-zero, so it will not fail the job.
  Automation should key off the exit code, not scrape the printed summary.

## 13. Security considerations

Running an automation framework in CI concentrates risk. Treat the following as
requirements, not suggestions — and cross-reference [SECURITY.md](../SECURITY.md)
and [docs/security.md](security.md), with which this guidance is consistent.

- **Never commit `.env` files.** They are git-ignored for a reason. Credentials
  belong in GitHub Secrets, nowhere else.
- **Never hard-code Telegram credentials** in a workflow file or step. Read them
  from `${{ secrets.* }}` into environment variables, as shown above.
- **Session files are password-equivalent.** A Telethon session under
  `SESSION_DIR` lets anyone act as the account. Do not commit one, do not print
  one, and think hard before injecting one into a runner
  ([§10](#10-authenticating-for-unattended-live-runs)). Prefer not to run live
  automation from CI at all.
- **Never expose session files or auth artifacts in logs or artifacts.** Do not
  `cat` a session file, do not upload `sessions/` with `actions/upload-artifact`,
  and do not enable step debugging that might echo sensitive paths.
- **Understand what `workflow_dispatch` grants.** Anyone who can trigger the
  workflow can run it against your account. Keep the repository private, restrict
  who has write access, and treat the ability to dispatch as equivalent to
  account access. Secrets are withheld from fork pull requests by design — keep
  it that way.
- **Prefer dry-run in CI.** Keep automated jobs pointed at `dry_run: true` files
  unless you have made a deliberate, reviewed decision to run live.
- **Use least privilege.** Scope secrets to the one repository that needs them,
  and rotate `TELEGRAM_API_HASH` (and any provisioned session) if you suspect
  exposure.

## 14. Complete, copy-pasteable examples

### Approach A — end user, install from PyPI

Your repository holds a `workflow.yaml` and this one CI file. It offers a manual
**Run workflow** button; as written it needs **no secrets**, because it runs your
file as a dry-run. Save it as `.github/workflows/run.yml`:

```yaml
name: Run TeleAutomata

on:
  workflow_dispatch:
    inputs:
      workflow:
        description: "Workflow YAML in this repository"
        required: true
        default: "workflow.yaml"

# Wired for convenience; unused by dry-run jobs. Add these under
# Settings > Secrets and variables > Actions before attempting a live run.
env:
  TELEGRAM_API_ID: ${{ secrets.TELEGRAM_API_ID }}
  TELEGRAM_API_HASH: ${{ secrets.TELEGRAM_API_HASH }}

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4          # your repo (the workflow YAML)
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          python -m pip install --upgrade pip
          pip install teleautomata          # pin, e.g. teleautomata==1.0.0
      - name: Validate then run
        run: |
          teleautomata validate "${{ inputs.workflow }}"
          teleautomata run "${{ inputs.workflow }}" --yes
```

For a live run, add a session-restore step before `run` as described in
[§10](#10-authenticating-for-unattended-live-runs). (TeleAutomata is not yet on
PyPI — until it is, use Approach B or a git install per
[§2](#2-two-ways-to-run-teleautomata-in-ci).)

### Approach B — contributor, run from a checkout

A single file that validates on every push and also offers a manual dry-run
button. It needs **no secrets** as written, because its default target is a
dry-run workflow. Save it as `.github/workflows/teleautomata.yml`:

```yaml
name: TeleAutomata

on:
  push:
  pull_request:
  workflow_dispatch:
    inputs:
      workflow:
        description: "Workflow YAML to run (dry-run by default)"
        required: true
        default: "examples/workflows/send-message.yaml"

# Wired for convenience; unused by dry-run jobs. Add these under
# Settings > Secrets and variables > Actions before attempting a live run.
env:
  TELEGRAM_API_ID: ${{ secrets.TELEGRAM_API_ID }}
  TELEGRAM_API_HASH: ${{ secrets.TELEGRAM_API_HASH }}

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          python -m pip install --upgrade pip
          pip install .
      - name: Validate all example workflows
        run: |
          for file in examples/workflows/*.yaml; do
            echo "::group::$file"
            teleautomata validate "$file"
            echo "::endgroup::"
          done

  run:
    # Only on the manual button, so pushes just validate.
    if: ${{ github.event_name == 'workflow_dispatch' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          python -m pip install --upgrade pip
          pip install .
      - name: Validate then run the selected workflow
        run: |
          teleautomata validate "${{ inputs.workflow }}"
          teleautomata run "${{ inputs.workflow }}" --yes
```

To go further, adapt the dedicated example files in
[`examples/github-actions/`](../examples/github-actions/) and read the
[examples guide](examples.md).
