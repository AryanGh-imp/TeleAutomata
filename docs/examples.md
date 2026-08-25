# Examples

The [`examples/`](../examples/) directory is a runnable cookbook. Every workflow
in it is small, focused, and **safe to run as-is**: each ships with
`dry_run: true`, so it plans and records an execution but makes no Telegram
request and needs no credentials. Read one, validate it, dry-run it, then adapt
it to chats you manage.

New to the project? Start with
[`examples/workflows/send-message.yaml`](../examples/workflows/send-message.yaml),
then work down the index below.

## What the directory contains

```text
examples/
├── workflows/        # 16 dry-run workflow files, one concept each
├── samples/          # CSV inputs for the users_csv argument
└── github-actions/   # copy-and-adapt CI templates (inert until copied)
```

- **`workflows/`** — the sixteen examples indexed below. Each file opens with a
  comment header stating what it demonstrates, which actions it uses, whether
  credentials are needed, and the exact validate/dry-run commands.
- **`samples/`** — CSV files referenced by the member-management examples through
  the `users_csv` argument (see [Sample data](#sample-data)).
- **`github-actions/`** — ready-to-adapt GitHub Actions templates. They live here,
  not under `.github/workflows/`, so GitHub never runs them by accident (see
  [GitHub Actions examples](#github-actions-examples)).

## Dry-run in one paragraph

Dry-run is a **property of the workflow file** (`dry_run: true`), not a
command-line flag — there is no `--dry-run` option. In dry-run the engine records
a planned execution and marks every action `skipped` without contacting Telegram,
so no credentials or session are required. It validates the *structure* of a
workflow (schema and dependency graph), **not** the contents of each action's
`with:` arguments — those are checked when the action actually runs. All examples
here are dry-run. The full model is in [workflows.md](workflows.md#dry-run).

## Example index

Sixteen workflows, grouped by what they teach. "Level" is a rough reading order,
not a capability rating.

### Start here

| Example | Demonstrates | Actions |
| --- | --- | --- |
| [send-message.yaml](../examples/workflows/send-message.yaml) | The smallest useful workflow: one action, `target` + `message`. | `send_message` |
| [resolve-targets.yaml](../examples/workflows/resolve-targets.yaml) | Every accepted target format (`@username`, `t.me` link, numeric id, invite link); independent actions form one batch. | `resolve_target` |

### Messaging

| Example | Demonstrates | Actions |
| --- | --- | --- |
| [announce-and-pin.yaml](../examples/workflows/announce-and-pin.yaml) | `depends_on` ordering — pin only after the send succeeds. | `send_message`, `pin_message` |
| [forward-and-reply.yaml](../examples/workflows/forward-and-reply.yaml) | Forwarding between chats and threading a reply under a specific message. | `forward_message`, `reply_message` |
| [edit-and-cleanup.yaml](../examples/workflows/edit-and-cleanup.yaml) | Editing, deleting, unpinning **all** pins (omit `message_id`), and marking read. | `edit_message`, `delete_message`, `unpin_message`, `mark_read` |

### Entity management

| Example | Demonstrates | Actions |
| --- | --- | --- |
| [create-channel.yaml](../examples/workflows/create-channel.yaml) | Creating a channel then verifying it, with a per-action `retry` policy and a dependency. | `create_channel`, `resolve_target` |
| [create-group.yaml](../examples/workflows/create-group.yaml) | Creating a group with an **inline** `users` list (note: `create_group` does not read a CSV). | `create_group` |
| [update-entity.yaml](../examples/workflows/update-entity.yaml) | Updating a title and/or description (at least one is required). | `update_entity` |

### Dialogs and membership

| Example | Demonstrates | Actions |
| --- | --- | --- |
| [manage-dialogs.yaml](../examples/workflows/manage-dialogs.yaml) | Dialog actions that change **your own** view: mute, pin, mark unread, archive, unmute. | `mute_dialog`, `pin_dialog`, `mark_unread`, `archive_chat`, `unmute_dialog` |
| [join-and-leave.yaml](../examples/workflows/join-and-leave.yaml) | Joining and leaving channels and groups, including a private invite link. | `join_channel`, `join_group`, `leave_channel`, `leave_group` |

### Member management

| Example | Demonstrates | Actions |
| --- | --- | --- |
| [add-members.yaml](../examples/workflows/add-members.yaml) | Adding members from an inline list; per-user failures are isolated, not fatal. | `add_members` |
| [add-members-from-csv.yaml](../examples/workflows/add-members-from-csv.yaml) | `users_csv` input merged with inline `users` and de-duplicated. | `add_members` |
| [moderate-members.yaml](../examples/workflows/moderate-members.yaml) | Removing, banning (from a CSV), and restricting individual rights via the `permissions` map. | `remove_members`, `ban_members`, `restrict_members` |

### Engine features

| Example | Demonstrates | Actions |
| --- | --- | --- |
| [retry-policy.yaml](../examples/workflows/retry-policy.yaml) | Per-action `retry` overrides vs. the engine default, and the bounds on each field. | `resolve_target`, `send_message` |
| [continue-on-error.yaml](../examples/workflows/continue-on-error.yaml) | `continue_on_error` — a tolerated failure neither fails the run nor skips its dependants. | `resolve_target`, `send_message` |
| [community-launch.yaml](../examples/workflows/community-launch.yaml) | A realistic branching + fan-in dependency graph across five action types. | `resolve_target`, `update_entity`, `send_message`, `pin_message`, `forward_message` |

The full catalogue of all 29 actions and their arguments is in
[actions.md](actions.md); the schema behind these files is in
[workflows.md](workflows.md).

## Validating and dry-running

Run commands from the repository root so relative paths such as
`examples/samples/team.csv` resolve. With the package installed
(`pip install -e ".[dev]"`) and `teleautomata init` run once:

```bash
teleautomata validate examples/workflows/send-message.yaml
```

```bash
teleautomata run examples/workflows/send-message.yaml
```

`validate` checks structure and the dependency graph and exits non-zero if the
file is invalid — no network. `run` on a `dry_run: true` file prints the planned
execution and an execution id, touching no account. To validate every example at
once:

```bash
teleautomata list examples/workflows
```

Then inspect what a dry-run recorded:

```bash
teleautomata history
```

```bash
teleautomata status <execution-id>
```

See [cli.md](cli.md) for the full command reference and exit codes.

## Running an example for real

The examples are placeholders — `@my_channel`, `@alice`, sample ids. A live run
performs **real, possibly irreversible** Telegram actions, so promote an example
deliberately:

1. **Edit the targets and payloads** in the YAML to entities you are authorized
   to manage. Message ids in the examples are illustrative — on a real run you
   pin/edit/forward the id a send actually returned, not a hard-coded value.
2. **Turn off dry-run** by setting `dry_run: false` (the default is `false`, so
   removing the line also makes it live).
3. **Provide credentials.** Copy `.env.example` to `.env` and set
   `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from <https://my.telegram.org> (see
   [configuration.md](configuration.md)).
4. **Authenticate** the account named in the file (`account: primary` here):

   ```bash
   teleautomata auth primary
   ```

5. **Run it.** A live run asks for confirmation first; `--yes` skips the prompt:

   ```bash
   teleautomata run examples/workflows/send-message.yaml --yes
   ```

Start with a throwaway or test chat and keep the conservative default pacing.

## Sample data

[`examples/samples/`](../examples/samples/) holds CSV inputs for the `users_csv`
argument that the `*_members` actions accept. Each line is one target, or several
separated by commas; blank lines are ignored. The reader keeps **every** non-blank
cell, so these files contain data only — no comment lines.

| File | Used by | Contents |
| --- | --- | --- |
| [team.csv](../examples/samples/team.csv) | [add-members-from-csv.yaml](../examples/workflows/add-members-from-csv.yaml) | Placeholder members to add (one per line, plus a comma-separated line). |
| [spammers.csv](../examples/samples/spammers.csv) | [moderate-members.yaml](../examples/workflows/moderate-members.yaml) | Placeholder accounts to ban. |

Inline `users` and `users_csv` are merged and de-duplicated (first-seen order
wins). `create_group` is the exception — its `users` list is inline only, with no
CSV. Replace placeholders with usernames or numeric ids you actually manage, and
never commit real member lists.

## GitHub Actions examples

[`examples/github-actions/`](../examples/github-actions/) contains four
ready-to-adapt CI workflows. They live under `examples/` on purpose: GitHub only
auto-runs workflows in the top-level `.github/workflows/` directory, so nothing
here runs until you copy it there.

| File | Trigger | Needs secrets? |
| --- | --- | --- |
| [validate.yml](../examples/github-actions/validate.yml) | `push`, `pull_request` | No — validation never connects to Telegram. |
| [run-manual.yml](../examples/github-actions/run-manual.yml) | `workflow_dispatch` (manual button) | Only for live runs. |
| [scheduled.yml](../examples/github-actions/scheduled.yml) | `schedule` (cron) + manual | Only for live runs. |
| [run-from-pypi.yml](../examples/github-actions/run-from-pypi.yml) | `workflow_dispatch` (manual button) | Only for live runs. |

The first three install TeleAutomata from the checked-out source (for
contributors and forks); `run-from-pypi.yml` installs the published package and
runs your own `workflow.yaml` (recommended for end users). See the two approaches
in [github-actions.md](github-actions.md#2-two-ways-to-run-teleautomata-in-ci).

Credentials are always read from GitHub Secrets
(`${{ secrets.TELEGRAM_API_ID }}`), never hard-coded. Validation is the safest and
recommended use. The full walkthrough — secrets setup, exit codes, dry-run
safety, and why live runs in CI are advanced and discouraged — is in
[github-actions.md](github-actions.md).

## Related reading

- [workflows.md](workflows.md) — the workflow schema and authoring guide.
- [actions.md](actions.md) — every action and its arguments.
- [cli.md](cli.md) — the full command reference and exit codes.
- [github-actions.md](github-actions.md) — running workflows in CI.
- [security.md](security.md) and [SECURITY.md](../SECURITY.md) — the security model.
