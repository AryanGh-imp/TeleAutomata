# Action reference

Every Telegram capability in TeleAutomata is a workflow action. This page
documents all 29 shipped actions: their arguments, validation, and result shape.
Actions are invoked from a workflow YAML file under `actions:`, each with an
`id`, a `type` from this catalog, and a `with:` mapping of arguments.

```yaml
- id: announce
  type: send_message
  with:
    target: "@my_channel"
    message: "Hello"
```

## Conventions

- **`target`** identifies a chat, channel, group, or user. It accepts an
  `@username`, a `t.me/...` link (including private `t.me/+hash` invites where
  the action supports joining), or a numeric id as a string. See
  [Telegram integration](telegram-integration.md) for how targets are resolved.
- **Arguments are validated before any network call.** A missing or wrongly
  typed argument raises a permanent error, so the action is never retried and,
  under `dry_run`, is reported without contacting Telegram.
- **Every action returns a `dict`** recorded against the action's id in the
  execution history. The "Result" columns below list the keys returned.
- **Errors** are classified as permanent (bad input, Telegram rejection),
  transient (server/connection faults — retried), or rate-limit (flood-wait —
  the engine waits and retries). See [workflow engine](workflow-engine.md).

## Entity management

| Action | Arguments | Result keys |
| --- | --- | --- |
| `create_group` | `title` (str), `users` (list[str], ≥1) | `title`, `entity_id` |
| `create_channel` | `title` (str); `about` (str, default `""`); `broadcast` (bool, default `true`) | `title`, `entity_id`, `broadcast` |
| `update_entity` | `target` (str); at least one of `title` (str), `about` (str) | `target`, `updated_title`, `updated_about` |
| `resolve_target` | `target` (str) | `target`, `entity_id`, `entity_type` |

`create_channel` creates a broadcast channel by default; set `broadcast: false`
to create a megagroup. `update_entity` requires at least one of `title` or
`about` — an empty update is rejected.

```yaml
- id: make_channel
  type: create_channel
  with:
    title: "Release Notes"
    about: "Product announcements"
    broadcast: true
```

## Messaging

| Action | Arguments | Result keys |
| --- | --- | --- |
| `send_message` | `target` (str), `message` (str) | `target`, `message_id` |
| `reply_message` | `target` (str), `reply_to_message_id` (int), `message` (str) | `target`, `reply_to_message_id`, `message_id` |
| `edit_message` | `target` (str), `message_id` (int), `text` (str) | `target`, `message_id`, `edited` |
| `delete_message` | `target` (str), `message_id` (int) | `target`, `message_id`, `deleted` |
| `forward_message` | `from_target` (str), `to_target` (str), `message_id` (int) | `from_target`, `to_target`, `message_id`, `forwarded_message_id` |
| `pin_message` | `target` (str), `message_id` (int) | `target`, `message_id`, `pinned` |
| `unpin_message` | `target` (str) | `target`, `message_id`, `unpinned_all` |
| `mark_read` | `target` (str) | `target`, `read` |
| `archive_chat` | `target` (str) | `target`, `archived` |

Integer arguments reject booleans, so `message_id: true` is an error rather than
being read as `1`. `unpin_message` unpins **all** pinned messages in the target.

```yaml
- id: announce
  type: send_message
  with:
    target: "@my_channel"
    message: "We shipped v1.0"
- id: pin_announcement
  type: pin_message
  depends_on: [announce]
  with:
    target: "@my_channel"
    message_id: 42
```

## Dialogs

Dialog actions operate on your own view of a chat and each take a single
`target`.

| Action | Result keys |
| --- | --- |
| `mark_unread` | `target`, `unread` |
| `mute_dialog` | `target`, `muted` |
| `unmute_dialog` | `target`, `muted` |
| `pin_dialog` | `target`, `pinned` |
| `unpin_dialog` | `target`, `pinned` |

```yaml
- id: quiet_noisy_chat
  type: mute_dialog
  with:
    target: "@busy_group"
```

## Membership

Join and leave channels and groups. Each takes a single `target`; `join_channel`
and `join_group` also accept private invite links (`t.me/+hash`).

| Action | Result keys |
| --- | --- |
| `join_channel` | `target`, `joined` |
| `leave_channel` | `target`, `left` |
| `join_group` | `target`, `joined` |
| `leave_group` | `target`, `left` |

## Member management

These act on many users at once. Users come from an inline `users` list, a
`users_csv` file (one user per line or comma-separated), or both — the sources
are merged and de-duplicated, preserving first-seen order. At least one user is
required.

Failure is isolated per user: a user who cannot be resolved or is permanently
rejected is recorded under `failed` and the batch continues, while a flood-wait
or transient error aborts the action so the engine's retry logic applies. Every
result therefore includes a `failed` list alongside the success list.

| Action | Arguments | Success key |
| --- | --- | --- |
| `add_members` | `target`, `users` and/or `users_csv` | `added` |
| `remove_members` | `target`, `users` and/or `users_csv` | `removed` |
| `ban_members` | `target`, `users` and/or `users_csv` | `banned` |
| `unban_members` | `target`, `users` and/or `users_csv` | `unbanned` |
| `mute_members` | `target`, `users` and/or `users_csv` | `muted` |
| `unmute_members` | `target`, `users` and/or `users_csv` | `unmuted` |
| `restrict_members` | `target`, `users` and/or `users_csv`, `permissions` (mapping) | `restricted` |

`remove_members` kicks without a lasting ban (the user may rejoin);
`ban_members` revokes all rights. `restrict_members` takes a `permissions`
mapping of right → bool, where `false` removes a right and omitted rights stay
allowed. Valid rights: `send_messages`, `send_media`, `send_stickers`,
`send_gifs`, `send_games`, `send_inline`, `embed_link_previews`, `send_polls`,
`change_info`, `invite_users`, `pin_messages`. `view_messages` is intentionally
rejected — a full ban is `ban_members`.

```yaml
- id: onboard
  type: add_members
  with:
    target: "@my_group"
    users: ["@alice", "@bob"]
    users_csv: "examples/samples/team.csv"
- id: restrict_links
  type: restrict_members
  with:
    target: "@my_group"
    users: ["@link_spammer"]
    permissions:
      send_media: false
      embed_link_previews: false
```

## Adding an action

The library is intentionally a representative set. To add your own, see the
[extension guide](extending.md).
