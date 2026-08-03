from typing import Any

import pytest

from telegram_automation.application.actions import execute_action
from telegram_automation.domain.errors import PermanentActionError
from telegram_automation.workflows.schema import ActionDefinition


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
