"""A gateway that refuses to run anything.

Used for ``dry_run`` workflows: the engine never calls the gateway in that
mode, so no Telegram connection or credentials should be required to inspect
a plan. If a future code path does reach it, the raised error exposes the
bug immediately instead of silently touching the network.
"""

from typing import Any

from telegram_automation.domain.errors import PermanentActionError


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

    @staticmethod
    def _forbid(action: str) -> dict[str, Any]:
        raise PermanentActionError(
            f"dry_run must not execute Telegram actions (attempted {action})"
        )
