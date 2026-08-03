from typing import Any

from telegram_automation.domain.errors import PermanentActionError
from telegram_automation.domain.ports import TelegramGateway
from telegram_automation.workflows.schema import ActionDefinition


async def execute_action(gateway: TelegramGateway, action: ActionDefinition) -> dict[str, Any]:
    """Validate each action's input close to its business operation."""
    arguments = action.with_
    if action.type == "create_group":
        return await gateway.create_group(
            _string(arguments, "title"), _string_list(arguments, "users")
        )
    if action.type == "create_channel":
        return await gateway.create_channel(
            _string(arguments, "title"),
            str(arguments.get("about", "")),
            bool(arguments.get("broadcast", True)),
        )
    if action.type == "update_entity":
        title, about = arguments.get("title"), arguments.get("about")
        if title is None and about is None:
            raise PermanentActionError("update_entity requires at least one of 'title' or 'about'")
        return await gateway.update_entity(
            _string(arguments, "target"),
            _optional_string(title, "title"),
            _optional_string(about, "about"),
        )
    if action.type == "send_message":
        return await gateway.send_message(
            _string(arguments, "target"), _string(arguments, "message")
        )
    if action.type == "resolve_target":
        return await gateway.resolve_target(_string(arguments, "target"))
    raise PermanentActionError(f"unsupported action type '{action.type}'")


def _string(arguments: dict[str, Any], field: str) -> str:
    value = arguments.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PermanentActionError(f"'{field}' must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PermanentActionError(f"'{field}' must be a string")
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
