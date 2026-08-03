from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, get_args

from telegram_automation.domain.errors import PermanentActionError
from telegram_automation.domain.ports import TelegramGateway
from telegram_automation.workflows.schema import ActionDefinition, ActionType

ActionHandler = Callable[[TelegramGateway, dict[str, Any]], Awaitable[dict[str, Any]]]


class ActionRegistry:
    """Maps action types to their validated gateway calls.

    Handlers are registered with :meth:`register`. A single module-level guard
    (:func:`assert_consistent_with_schema`) keeps this registry and the
    ``ActionType`` literal in lockstep so a new action can never be forgotten
    on either side.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, action_type: ActionType) -> Callable[[ActionHandler], ActionHandler]:
        def decorator(handler: ActionHandler) -> ActionHandler:
            if action_type in self._handlers:
                raise RuntimeError(f"action '{action_type}' is already registered")
            self._handlers[action_type] = handler
            return handler

        return decorator

    def handler(self, action_type: str) -> ActionHandler:
        try:
            return self._handlers[action_type]
        except KeyError as exc:
            raise PermanentActionError(f"unsupported action type '{action_type}'") from exc

    @property
    def action_types(self) -> set[str]:
        return set(self._handlers)

    def assert_consistent_with_schema(self) -> None:
        declared = set(get_args(ActionType))
        if self.action_types != declared:
            missing = declared - self.action_types
            unknown = self.action_types - declared
            raise RuntimeError(
                "action registry out of sync with the ActionType schema"
                + (f"; missing handlers: {sorted(missing)}" if missing else "")
                + (f"; undeclared handlers: {sorted(unknown)}" if unknown else "")
            )


#: The registry is a process-wide singleton: every action in the schema is
#: registered here, and the guard below verifies that invariant at import time.
registry = ActionRegistry()


def _string(arguments: dict[str, Any], field: str) -> str:
    value = arguments.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PermanentActionError(f"'{field}' must be a non-empty string")
    return value


def _string_list(arguments: dict[str, Any], field: str) -> list[str]:
    value = arguments.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise PermanentActionError(f"'{field}' must be a non-empty list of strings")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PermanentActionError(f"'{field}' must be a string")
    return value


def _user_targets(arguments: dict[str, Any]) -> list[str]:
    """Resolve the user list for member actions.

    Accepts an inline ``users`` list (usernames or numeric ids as strings) and,
    optionally, a ``users_csv`` path to a file with one user per line or
    comma-separated values. The two sources are merged, de-duplicated (keeping
    first-seen order), and must yield at least one target.
    """
    users: list[str] = []
    if "users" in arguments:
        users.extend(_string_list(arguments, "users"))
    csv_path = arguments.get("users_csv")
    if csv_path is not None:
        if not isinstance(csv_path, str) or not csv_path.strip():
            raise PermanentActionError("'users_csv' must be a path string")
        users.extend(_read_user_csv(csv_path))
    if not users:
        raise PermanentActionError(
            "member actions require 'users' (a non-empty list) or 'users_csv' (a file path)"
        )
    seen: set[str] = set()
    unique: list[str] = []
    for u in users:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _read_user_csv(path: str) -> list[str]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PermanentActionError(f"cannot read users_csv '{path}': {exc}") from exc
    values = [cell.strip() for line in raw.splitlines() for cell in line.split(",")]
    entries = [value for value in values if value]
    if not entries:
        raise PermanentActionError(f"users_csv '{path}' contained no users")
    return entries


def _integer(arguments: dict[str, Any], field: str, *, positive: bool = False) -> int:
    value = arguments.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PermanentActionError(f"'{field}' must be an integer")
    if positive and value <= 0:
        raise PermanentActionError(f"'{field}' must be a positive integer")
    return value


@registry.register("create_group")
async def _create_group(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.create_group(_string(arguments, "title"), _string_list(arguments, "users"))


@registry.register("create_channel")
async def _create_channel(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.create_channel(
        _string(arguments, "title"),
        str(arguments.get("about", "")),
        bool(arguments.get("broadcast", True)),
    )


@registry.register("update_entity")
async def _update_entity(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    title, about = arguments.get("title"), arguments.get("about")
    if title is None and about is None:
        raise PermanentActionError("update_entity requires at least one of 'title' or 'about'")
    return await gateway.update_entity(
        _string(arguments, "target"),
        _optional_string(title, "title"),
        _optional_string(about, "about"),
    )


@registry.register("send_message")
async def _send_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.send_message(_string(arguments, "target"), _string(arguments, "message"))


@registry.register("resolve_target")
async def _resolve_target(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.resolve_target(_string(arguments, "target"))


@registry.register("pin_message")
async def _pin_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.pin_message(
        _string(arguments, "target"), _integer(arguments, "message_id")
    )


@registry.register("unpin_message")
async def _unpin_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.unpin_message(_string(arguments, "target"))


@registry.register("edit_message")
async def _edit_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.edit_message(
        _string(arguments, "target"),
        _integer(arguments, "message_id"),
        _string(arguments, "text"),
    )


@registry.register("delete_message")
async def _delete_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.delete_message(
        _string(arguments, "target"), _integer(arguments, "message_id")
    )


@registry.register("forward_message")
async def _forward_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.forward_message(
        _string(arguments, "from_target"),
        _string(arguments, "to_target"),
        _integer(arguments, "message_id"),
    )


@registry.register("reply_message")
async def _reply_message(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.reply_message(
        _string(arguments, "target"),
        _integer(arguments, "reply_to_message_id"),
        _string(arguments, "message"),
    )


@registry.register("mark_read")
async def _mark_read(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.mark_read(_string(arguments, "target"))


@registry.register("archive_chat")
async def _archive_chat(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.archive_chat(_string(arguments, "target"))


@registry.register("mark_unread")
async def _mark_unread(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.mark_unread(_string(arguments, "target"))


@registry.register("mute_dialog")
async def _mute_dialog(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.mute_dialog(_string(arguments, "target"))


@registry.register("unmute_dialog")
async def _unmute_dialog(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.unmute_dialog(_string(arguments, "target"))


@registry.register("pin_dialog")
async def _pin_dialog(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.pin_dialog(_string(arguments, "target"))


@registry.register("unpin_dialog")
async def _unpin_dialog(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.unpin_dialog(_string(arguments, "target"))


@registry.register("join_channel")
async def _join_channel(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.join_channel(_string(arguments, "target"))


@registry.register("leave_channel")
async def _leave_channel(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.leave_channel(_string(arguments, "target"))


@registry.register("join_group")
async def _join_group(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.join_group(_string(arguments, "target"))


@registry.register("leave_group")
async def _leave_group(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.leave_group(_string(arguments, "target"))


@registry.register("add_members")
async def _add_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.add_members(_string(arguments, "target"), _user_targets(arguments))


@registry.register("remove_members")
async def _remove_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.remove_members(_string(arguments, "target"), _user_targets(arguments))


@registry.register("ban_members")
async def _ban_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.ban_members(_string(arguments, "target"), _user_targets(arguments))


@registry.register("unban_members")
async def _unban_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.unban_members(_string(arguments, "target"), _user_targets(arguments))


#: Per-user rights that :meth:`restrict_members` may toggle. ``view_messages`` is
#: intentionally excluded: revoking it is a full ban, which ``ban_members`` owns.
RESTRICTABLE_RIGHTS = frozenset(
    {
        "send_messages",
        "send_media",
        "send_stickers",
        "send_gifs",
        "send_games",
        "send_inline",
        "embed_link_previews",
        "send_polls",
        "change_info",
        "invite_users",
        "pin_messages",
    }
)


def _permissions(arguments: dict[str, Any]) -> dict[str, bool]:
    """Validate the ``permissions`` mapping for ``restrict_members``.

    Each key must name a known right and each value must be a bool. ``False``
    applies a restriction (removes the permission); ``True`` lifts it. At least
    one right is required so the action always has an effect.
    """
    value = arguments.get("permissions")
    if not isinstance(value, dict) or not value:
        raise PermanentActionError("'permissions' must be a non-empty mapping of right -> bool")
    permissions: dict[str, bool] = {}
    for right, allowed in value.items():
        if right not in RESTRICTABLE_RIGHTS:
            raise PermanentActionError(
                f"unknown permission '{right}'; allowed: {sorted(RESTRICTABLE_RIGHTS)}"
            )
        if not isinstance(allowed, bool):
            raise PermanentActionError(f"permission '{right}' must be a boolean")
        permissions[right] = allowed
    return permissions


@registry.register("mute_members")
async def _mute_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.mute_members(_string(arguments, "target"), _user_targets(arguments))


@registry.register("unmute_members")
async def _unmute_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.unmute_members(_string(arguments, "target"), _user_targets(arguments))


@registry.register("restrict_members")
async def _restrict_members(gateway: TelegramGateway, arguments: dict[str, Any]) -> dict[str, Any]:
    return await gateway.restrict_members(
        _string(arguments, "target"), _user_targets(arguments), _permissions(arguments)
    )


async def execute_action(gateway: TelegramGateway, action: ActionDefinition) -> dict[str, Any]:
    """Validate an action's input and dispatch it to its registered gateway call."""
    return await registry.handler(action.type)(gateway, action.with_)


# Guard the registry against schema drift at import time. A missing or extra
# handler here is a programming error that must fail loudly.
registry.assert_consistent_with_schema()
