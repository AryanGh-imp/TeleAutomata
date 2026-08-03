from typing import Any, get_args

import pytest

from telegram_automation.application.actions import execute_action, registry
from telegram_automation.domain.errors import PermanentActionError
from telegram_automation.workflows.schema import ActionDefinition, ActionType


class RecordingGateway:
    """Gateway that records the arguments each action was called with."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def create_group(self, title: str, users: list[str]) -> dict[str, Any]:
        self.calls.append(("create_group", (title, users)))
        return {"ok": "create_group"}

    async def create_channel(self, title: str, about: str, broadcast: bool) -> dict[str, Any]:
        self.calls.append(("create_channel", (title, about, broadcast)))
        return {"ok": "create_channel"}

    async def update_entity(
        self, target: str, title: str | None, about: str | None
    ) -> dict[str, Any]:
        self.calls.append(("update_entity", (target, title, about)))
        return {"ok": "update_entity"}

    async def send_message(self, target: str, message: str) -> dict[str, Any]:
        self.calls.append(("send_message", (target, message)))
        return {"ok": "send_message"}

    async def resolve_target(self, target: str) -> dict[str, Any]:
        self.calls.append(("resolve_target", (target,)))
        return {"ok": "resolve_target"}

    async def pin_message(self, target: str, message_id: int) -> dict[str, Any]:
        self.calls.append(("pin_message", (target, message_id)))
        return {"ok": "pin_message"}

    async def unpin_message(self, target: str, message_id: int | None = None) -> dict[str, Any]:
        self.calls.append(("unpin_message", (target, message_id)))
        return {"ok": "unpin_message"}

    async def edit_message(self, target: str, message_id: int, text: str) -> dict[str, Any]:
        self.calls.append(("edit_message", (target, message_id, text)))
        return {"ok": "edit_message"}

    async def delete_message(self, target: str, message_id: int) -> dict[str, Any]:
        self.calls.append(("delete_message", (target, message_id)))
        return {"ok": "delete_message"}

    async def forward_message(
        self, from_target: str, to_target: str, message_id: int
    ) -> dict[str, Any]:
        self.calls.append(("forward_message", (from_target, to_target, message_id)))
        return {"ok": "forward_message"}

    async def reply_message(
        self, target: str, reply_to_message_id: int, message: str
    ) -> dict[str, Any]:
        self.calls.append(("reply_message", (target, reply_to_message_id, message)))
        return {"ok": "reply_message"}

    async def mark_read(self, target: str) -> dict[str, Any]:
        self.calls.append(("mark_read", (target,)))
        return {"ok": "mark_read"}

    async def archive_chat(self, target: str) -> dict[str, Any]:
        self.calls.append(("archive_chat", (target,)))
        return {"ok": "archive_chat"}

    async def mark_unread(self, target: str) -> dict[str, Any]:
        self.calls.append(("mark_unread", (target,)))
        return {"ok": "mark_unread"}

    async def mute_dialog(self, target: str) -> dict[str, Any]:
        self.calls.append(("mute_dialog", (target,)))
        return {"ok": "mute_dialog"}

    async def unmute_dialog(self, target: str) -> dict[str, Any]:
        self.calls.append(("unmute_dialog", (target,)))
        return {"ok": "unmute_dialog"}

    async def pin_dialog(self, target: str) -> dict[str, Any]:
        self.calls.append(("pin_dialog", (target,)))
        return {"ok": "pin_dialog"}

    async def unpin_dialog(self, target: str) -> dict[str, Any]:
        self.calls.append(("unpin_dialog", (target,)))
        return {"ok": "unpin_dialog"}


def _action(action_type: str, **arguments: Any) -> ActionDefinition:
    return ActionDefinition.model_validate({"id": "action", "type": action_type, "with": arguments})


@pytest.mark.asyncio
async def test_create_group_forwards_arguments() -> None:
    gateway = RecordingGateway()
    result = await execute_action(gateway, _action("create_group", title="Team", users=["@a"]))
    assert result == {"ok": "create_group"}
    assert gateway.calls == [("create_group", ("Team", ["@a"]))]


@pytest.mark.asyncio
async def test_create_channel_defaults_about_and_broadcast() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("create_channel", title="News"))
    assert gateway.calls == [("create_channel", ("News", "", True))]


@pytest.mark.asyncio
async def test_send_message_requires_target_and_message() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("send_message", target="@a", message="hi"))
    assert gateway.calls == [("send_message", ("@a", "hi"))]


@pytest.mark.asyncio
async def test_resolve_target_forwards_target() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("resolve_target", target="@telegram"))
    assert gateway.calls == [("resolve_target", ("@telegram",))]


@pytest.mark.asyncio
async def test_update_entity_requires_title_or_about() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="at least one"):
        await execute_action(gateway, _action("update_entity", target="@a"))
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_update_entity_accepts_partial_update() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("update_entity", target="@a", title="New"))
    assert gateway.calls == [("update_entity", ("@a", "New", None))]


@pytest.mark.asyncio
async def test_missing_required_string_is_permanent_error() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="'title' must be a non-empty string"):
        await execute_action(gateway, _action("create_channel"))


@pytest.mark.asyncio
async def test_blank_string_is_rejected() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="non-empty string"):
        await execute_action(gateway, _action("resolve_target", target="   "))


@pytest.mark.asyncio
async def test_empty_user_list_is_rejected() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="non-empty list of strings"):
        await execute_action(gateway, _action("create_group", title="Team", users=[]))


@pytest.mark.asyncio
async def test_user_list_with_non_string_is_rejected() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="non-empty list of strings"):
        await execute_action(gateway, _action("create_group", title="Team", users=["@a", 3]))


@pytest.mark.asyncio
async def test_optional_string_must_be_string_when_present() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="'title' must be a string"):
        await execute_action(gateway, _action("update_entity", target="@a", title=42))


@pytest.mark.asyncio
async def test_pin_message_forwards_target_and_id() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("pin_message", target="@a", message_id=7))
    assert gateway.calls == [("pin_message", ("@a", 7))]


@pytest.mark.asyncio
async def test_unpin_message_forwards_target_only() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("unpin_message", target="@a"))
    assert gateway.calls == [("unpin_message", ("@a", None))]


@pytest.mark.asyncio
async def test_edit_message_forwards_all_arguments() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("edit_message", target="@a", message_id=7, text="new"))
    assert gateway.calls == [("edit_message", ("@a", 7, "new"))]


@pytest.mark.asyncio
async def test_delete_message_forwards_target_and_id() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("delete_message", target="@a", message_id=7))
    assert gateway.calls == [("delete_message", ("@a", 7))]


@pytest.mark.asyncio
async def test_forward_message_forwards_all_arguments() -> None:
    gateway = RecordingGateway()
    await execute_action(
        gateway, _action("forward_message", from_target="@a", to_target="@b", message_id=7)
    )
    assert gateway.calls == [("forward_message", ("@a", "@b", 7))]


@pytest.mark.asyncio
async def test_reply_message_forwards_all_arguments() -> None:
    gateway = RecordingGateway()
    await execute_action(
        gateway, _action("reply_message", target="@a", reply_to_message_id=7, message="hi")
    )
    assert gateway.calls == [("reply_message", ("@a", 7, "hi"))]


@pytest.mark.asyncio
async def test_mark_read_forwards_target() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("mark_read", target="@a"))
    assert gateway.calls == [("mark_read", ("@a",))]


@pytest.mark.asyncio
async def test_archive_chat_forwards_target() -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action("archive_chat", target="@a"))
    assert gateway.calls == [("archive_chat", ("@a",))]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_type",
    ["mark_unread", "mute_dialog", "unmute_dialog", "pin_dialog", "unpin_dialog"],
)
async def test_dialog_actions_forward_target(action_type: str) -> None:
    gateway = RecordingGateway()
    await execute_action(gateway, _action(action_type, target="@a"))
    assert gateway.calls == [(action_type, ("@a",))]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_type",
    ["mark_unread", "mute_dialog", "unmute_dialog", "pin_dialog", "unpin_dialog"],
)
async def test_dialog_actions_require_target(action_type: str) -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="'target' must be a non-empty string"):
        await execute_action(gateway, _action(action_type))
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_message_id_must_be_integer() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="'message_id' must be an integer"):
        await execute_action(gateway, _action("pin_message", target="@a", message_id="7"))
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_message_id_rejects_bool() -> None:
    gateway = RecordingGateway()
    with pytest.raises(PermanentActionError, match="'message_id' must be an integer"):
        await execute_action(gateway, _action("delete_message", target="@a", message_id=True))
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_unsupported_action_is_permanent_error() -> None:
    gateway = RecordingGateway()
    action = ActionDefinition.model_construct(id="action", type="does_not_exist", with_={})
    with pytest.raises(PermanentActionError, match="unsupported action type 'does_not_exist'"):
        await execute_action(gateway, action)


def test_registry_matches_action_type_schema() -> None:
    """The registry and the ActionType literal must never drift apart."""
    assert registry.action_types == set(get_args(ActionType))
    # The import-time guard is also callable directly and must not raise.
    registry.assert_consistent_with_schema()
