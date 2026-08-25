# TeleAutomata examples

A practical cookbook for the workflow files in this directory. Every example is
small, focused, and **safe to run as-is**: each sets `dry_run: true`, so it plans
an execution and records it, but makes no Telegram request and needs no
credentials. Read one, validate it, dry-run it, then adapt it to your own chats.

New to the project? Start with [`workflows/send-message.yaml`](workflows/send-message.yaml),
then work down the index below.

## Contents

- [How dry-run works (read this first)](#how-dry-run-works-read-this-first)
- [Quick start](#quick-start)
- [Example index](#example-index)
- [Running an example](#running-an-example)
- [Promoting an example to a live run](#promoting-an-example-to-a-live-run)
- [Sample data files](#sample-data-files)
- [Running examples in GitHub Actions](#running-examples-in-github-actions)
- [Security notes](#security-notes)
- [Further reading](#further-reading)

## How dry-run works (read this first)

Dry-run is a **property of the workflow file**, not a command-line flag. There is
**no `--dry-run` option**. A file runs in dry-run mode when it contains:

```yaml
dry_run: true
```

In dry-run the engine records a planned execution and marks every action as
`skipped` without calling Telegram — so no credentials or authenticated session
are required. All examples here ship with `dry_run: true`. To make an example
perform real actions you edit the file (set `dry_run: false`) and authenticate
first; see [Promoting an example to a live run](#promoting-an-example-to-a-live-run).

> Dry-run validates the *structure* of a workflow (schema, dependency graph) and
> that the file parses. It does **not** validate the contents of each action's
> `with:` arguments — those are checked when the action actually executes on a
> live run. So a dry-run passing is not proof that every argument is correct for
> the target, only that the plan is well-formed.

## Quick start

From the repository root, with the package installed (`pip install -e ".[dev]"`):

```bash
teleautomata init
```

```bash
teleautomata validate examples/workflows/send-message.yaml
```

```bash
teleautomata run examples/workflows/send-message.yaml
```

`validate` checks the file and exits non-zero if it is invalid. `run` on a
`dry_run: true` file prints the planned execution and an execution id, touching
no account. To see all examples validated at once:

```bash
teleautomata list examples/workflows
```

## Example index

Sixteen workflows, grouped by what they teach. "Level" is a rough reading order,
not a capability rating.

### Start here

| Example | Demonstrates | Actions | Level |
| --- | --- | --- | --- |
| [send-message.yaml](workflows/send-message.yaml) | The smallest useful workflow: one action, `target` + `message`. | `send_message` | Beginner |
| [resolve-targets.yaml](workflows/resolve-targets.yaml) | Every accepted target format (`@username`, `t.me` link, numeric id, invite link); independent actions form one batch. | `resolve_target` | Beginner |

### Messaging

| Example | Demonstrates | Actions | Level |
| --- | --- | --- | --- |
| [announce-and-pin.yaml](workflows/announce-and-pin.yaml) | `depends_on` ordering — pin only after the send succeeds. | `send_message`, `pin_message` | Beginner |
| [forward-and-reply.yaml](workflows/forward-and-reply.yaml) | Forwarding between chats and threading a reply under a specific message. | `forward_message`, `reply_message` | Beginner |
| [edit-and-cleanup.yaml](workflows/edit-and-cleanup.yaml) | Editing, deleting, unpinning **all** pins (omit `message_id`), and marking read. | `edit_message`, `delete_message`, `unpin_message`, `mark_read` | Intermediate |

### Entity management

| Example | Demonstrates | Actions | Level |
| --- | --- | --- | --- |
| [create-channel.yaml](workflows/create-channel.yaml) | Creating a channel then verifying it, with a per-action `retry` policy and a dependency. | `create_channel`, `resolve_target` | Intermediate |
| [create-group.yaml](workflows/create-group.yaml) | Creating a group with an **inline** `users` list (note: `create_group` does not read a CSV). | `create_group` | Beginner |
| [update-entity.yaml](workflows/update-entity.yaml) | Updating a title and/or description (at least one is required). | `update_entity` | Beginner |

### Dialogs and membership

| Example | Demonstrates | Actions | Level |
| --- | --- | --- | --- |
| [manage-dialogs.yaml](workflows/manage-dialogs.yaml) | Dialog actions that change **your own** view: mute, pin, mark unread, archive, unmute. | `mute_dialog`, `pin_dialog`, `mark_unread`, `archive_chat`, `unmute_dialog` | Beginner |
| [join-and-leave.yaml](workflows/join-and-leave.yaml) | Joining and leaving channels and groups, including a private invite link. | `join_channel`, `join_group`, `leave_channel`, `leave_group` | Beginner |

### Member management

| Example | Demonstrates | Actions | Level |
| --- | --- | --- | --- |
| [add-members.yaml](workflows/add-members.yaml) | Adding members from an inline list; per-user failures are isolated, not fatal. | `add_members` | Beginner |
| [add-members-from-csv.yaml](workflows/add-members-from-csv.yaml) | `users_csv` input merged with inline `users` and de-duplicated. | `add_members` | Intermediate |
| [moderate-members.yaml](workflows/moderate-members.yaml) | Removing, banning (from a CSV), and restricting individual rights via the `permissions` map. | `remove_members`, `ban_members`, `restrict_members` | Intermediate |

### Engine features

| Example | Demonstrates | Actions | Level |
| --- | --- | --- | --- |
| [retry-policy.yaml](workflows/retry-policy.yaml) | Per-action `retry` overrides vs. the engine default; the bounds on each field. | `resolve_target`, `send_message` | Intermediate |
| [continue-on-error.yaml](workflows/continue-on-error.yaml) | `continue_on_error` — a failed action neither fails the run nor skips its dependants. | `resolve_target`, `send_message` | Intermediate |
| [community-launch.yaml](workflows/community-launch.yaml) | A realistic branching + fan-in dependency graph across five action types. | `resolve_target`, `update_entity`, `send_message`, `pin_message`, `forward_message` | Advanced |

The full catalogue of 29 actions and their arguments is in
[docs/actions.md](../docs/actions.md).

## Running an example

Every workflow file opens with a comment header stating what it demonstrates,
which actions it uses, whether credentials are needed, and the exact validate and
dry-run commands. The pattern is always:

1. **Read** the file and its header comment.
2. **Validate** it (structure only, no network):

   ```bash
   teleautomata validate examples/workflows/announce-and-pin.yaml
   ```

3. **Dry-run** it (records a plan, still no network while `dry_run: true`):

   ```bash
   teleautomata run examples/workflows/announce-and-pin.yaml
   ```

4. **Inspect** what was recorded:

   ```bash
   teleautomata history
   ```

   ```bash
   teleautomata status <execution-id>
   ```

Run commands from the repository root so relative paths such as
`examples/samples/team.csv` resolve correctly.

## Promoting an example to a live run

The examples are placeholders — `@my_channel`, `@alice`, sample ids. Before a
live run you must edit them to reference entities you are authorized to manage,
and then:

1. **Edit the targets and payloads** in the YAML to real values.
2. **Turn off dry-run** by setting `dry_run: false` (the default is `false`, so
   removing the line also makes it live).
3. **Provide credentials.** Copy `.env.example` to `.env` and set
   `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` (from <https://my.telegram.org>).
4. **Authenticate the account** named in the file (`account: primary` here):

   ```bash
   teleautomata auth primary
   ```

5. **Run it.** A live run asks for confirmation first; `--yes` skips the prompt
   (and CI has no prompt anyway):

   ```bash
   teleautomata run examples/workflows/send-message.yaml --yes
   ```

> **A live run performs real, possibly irreversible Telegram actions** (sending,
> banning, deleting). Validate and dry-run first, start with a throwaway or test
> chat, and keep the conservative default pacing. Message ids in the examples are
> illustrative: on a real run you would pin/edit/forward the id that a send
> actually returned, not a hard-coded `1001`.

## Sample data files

[`samples/`](samples/) holds CSV inputs for the `users_csv` argument that the
`*_members` actions accept. Each line is one target, or several separated by
commas; blank lines are ignored. The reader keeps **every** non-blank cell, so
these files contain data only — no comment lines.

| File | Used by | Contents |
| --- | --- | --- |
| [samples/team.csv](samples/team.csv) | [add-members-from-csv.yaml](workflows/add-members-from-csv.yaml) | Placeholder members to add (one per line, plus a comma-separated line). |
| [samples/spammers.csv](samples/spammers.csv) | [moderate-members.yaml](workflows/moderate-members.yaml) | Placeholder accounts to ban. |

Replace the placeholders with the usernames or numeric ids you actually manage.
`create_group` does **not** read a CSV — its `users` list is inline only.

## Running examples in GitHub Actions

[`github-actions/`](github-actions/) contains three ready-to-adapt CI workflows.
They live under `examples/` on purpose: GitHub only auto-runs workflows in the
top-level `.github/workflows/` directory, so nothing here runs until you copy it
there.

| File | Trigger | Needs secrets? |
| --- | --- | --- |
| [github-actions/validate.yml](github-actions/validate.yml) | `push`, `pull_request` | No — validation never connects to Telegram. |
| [github-actions/run-manual.yml](github-actions/run-manual.yml) | `workflow_dispatch` (manual button) | Only for live runs. |
| [github-actions/scheduled.yml](github-actions/scheduled.yml) | `schedule` (cron) + manual | Only for live runs. |

Credentials are always read from GitHub Secrets
(`${{ secrets.TELEGRAM_API_ID }}`), never hard-coded. The validation workflow is
the safest starting point. The full walkthrough — secrets setup, exit codes,
dry-run safety, and why live runs in CI are advanced and discouraged — is in
[docs/github-actions.md](../docs/github-actions.md).

## Security notes

- **Never commit `.env` or session files.** Both are git-ignored. Credentials
  come only from the environment; session files under `SESSION_DIR` are
  password-equivalent — anyone holding one can act as the account.
- **Never hard-code credentials** in a workflow YAML, in CI, or in these
  examples. They belong in `.env` locally and GitHub Secrets in CI.
- **The placeholders are not real.** Editing them to real targets means the file
  can take real actions once `dry_run` is off — treat that change deliberately.
- **CSV files can contain personal data** (user ids/usernames). Handle them like
  any other list of people, and do not commit real member lists.

See [docs/security.md](../docs/security.md) and [SECURITY.md](../SECURITY.md) for
the full model.

## Further reading

- [docs/actions.md](../docs/actions.md) — every action and its arguments.
- [docs/cli.md](../docs/cli.md) — the full command reference and exit codes.
- [docs/github-actions.md](../docs/github-actions.md) — running workflows in CI.
- [docs/configuration.md](../docs/configuration.md) — environment settings and pacing.
- [docs/faq.md](../docs/faq.md) — common questions.
- [README.md](../README.md) — project overview and quick start.
