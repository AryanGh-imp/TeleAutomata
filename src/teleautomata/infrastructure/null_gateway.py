"""A gateway that refuses to run anything.

Used for ``dry_run`` workflows: the engine never calls the gateway in that
mode, so no Telegram connection or credentials should be required to inspect
a plan. If a future code path does reach it, the raised error exposes the
bug immediately instead of silently touching the network.
"""

from typing import Any

from teleautomata.domain.errors import PermanentActionError


class NullGateway:
    """Gateway stand-in that raises if any Telegram action is attempted."""

    async def create_group(self, title: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("create_group")

    async def create_channel(self, title: str, about: str, broadcast: bool) -> dict[str, Any]:
        return self._forbid("create_channel")

    async def update_entity(
        self, target: str, title: str | None, about: str | None
    ) -> dict[str, Any]:
        return self._forbid("update_entity")

    async def send_message(self, target: str, message: str) -> dict[str, Any]:
        return self._forbid("send_message")

    async def resolve_target(self, target: str) -> dict[str, Any]:
        return self._forbid("resolve_target")

    async def pin_message(self, target: str, message_id: int) -> dict[str, Any]:
        return self._forbid("pin_message")

    async def unpin_message(self, target: str, message_id: int | None = None) -> dict[str, Any]:
        return self._forbid("unpin_message")

    async def edit_message(self, target: str, message_id: int, text: str) -> dict[str, Any]:
        return self._forbid("edit_message")

    async def delete_message(self, target: str, message_id: int) -> dict[str, Any]:
        return self._forbid("delete_message")

    async def forward_message(
        self, from_target: str, to_target: str, message_id: int
    ) -> dict[str, Any]:
        return self._forbid("forward_message")

    async def reply_message(
        self, target: str, reply_to_message_id: int, message: str
    ) -> dict[str, Any]:
        return self._forbid("reply_message")

    async def mark_read(self, target: str) -> dict[str, Any]:
        return self._forbid("mark_read")

    async def archive_chat(self, target: str) -> dict[str, Any]:
        return self._forbid("archive_chat")

    async def mark_unread(self, target: str) -> dict[str, Any]:
        return self._forbid("mark_unread")

    async def mute_dialog(self, target: str) -> dict[str, Any]:
        return self._forbid("mute_dialog")

    async def unmute_dialog(self, target: str) -> dict[str, Any]:
        return self._forbid("unmute_dialog")

    async def pin_dialog(self, target: str) -> dict[str, Any]:
        return self._forbid("pin_dialog")

    async def unpin_dialog(self, target: str) -> dict[str, Any]:
        return self._forbid("unpin_dialog")

    async def join_channel(self, target: str) -> dict[str, Any]:
        return self._forbid("join_channel")

    async def leave_channel(self, target: str) -> dict[str, Any]:
        return self._forbid("leave_channel")

    async def join_group(self, target: str) -> dict[str, Any]:
        return self._forbid("join_group")

    async def leave_group(self, target: str) -> dict[str, Any]:
        return self._forbid("leave_group")

    async def add_members(self, target: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("add_members")

    async def remove_members(self, target: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("remove_members")

    async def ban_members(self, target: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("ban_members")

    async def unban_members(self, target: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("unban_members")

    async def mute_members(self, target: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("mute_members")

    async def unmute_members(self, target: str, users: list[str]) -> dict[str, Any]:
        return self._forbid("unmute_members")

    async def restrict_members(
        self, target: str, users: list[str], permissions: dict[str, bool]
    ) -> dict[str, Any]:
        return self._forbid("restrict_members")

    @staticmethod
    def _forbid(action: str) -> dict[str, Any]:
        raise PermanentActionError(
            f"dry_run must not execute Telegram actions (attempted {action})"
        )
