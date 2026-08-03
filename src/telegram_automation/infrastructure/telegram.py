from pathlib import Path
from typing import Any, NoReturn

from telethon import TelegramClient, errors, functions
from telethon.tl.types import (
    Channel,
    InputDialogPeer,
    InputNotifyPeer,
    InputPeerNotifySettings,
)

from telegram_automation.domain.errors import (
    PermanentActionError,
    RateLimitError,
    TransientActionError,
)


class TelethonGateway:
    """Thin, replaceable adapter over Telethon. Business rules do not live here."""

    def __init__(self, client: TelegramClient) -> None:
        self._client = client

    async def create_group(self, title: str, users: list[str]) -> dict[str, Any]:
        try:
            input_users = [await self._client.get_input_entity(user) for user in users]
            result = await self._client(
                functions.messages.CreateChatRequest(users=input_users, title=title)
            )
            chat = next(
                (chat for chat in result.chats if getattr(chat, "title", None) == title), None
            )
            return {"title": title, "entity_id": getattr(chat, "id", None)}
        except Exception as exc:  # translated at the anti-corruption boundary
            self._raise_translated(exc)

    async def create_channel(self, title: str, about: str, broadcast: bool) -> dict[str, Any]:
        try:
            result = await self._client(
                functions.channels.CreateChannelRequest(
                    title=title,
                    about=about,
                    broadcast=broadcast,
                    megagroup=not broadcast,
                )
            )
            channel = result.chats[0]
            return {"title": title, "entity_id": channel.id, "broadcast": broadcast}
        except Exception as exc:
            self._raise_translated(exc)

    async def update_entity(
        self, target: str, title: str | None, about: str | None
    ) -> dict[str, Any]:
        try:
            entity = await self._client.get_entity(target)
            if title is not None and isinstance(entity, Channel):
                await self._client(functions.channels.EditTitleRequest(channel=entity, title=title))
            elif title is not None:
                await self._client(
                    functions.messages.EditChatTitleRequest(chat_id=entity.id, title=title)
                )
            if about is not None:
                if isinstance(entity, Channel):
                    await self._client(
                        functions.channels.EditAboutRequest(channel=entity, about=about)
                    )
                else:
                    await self._client(
                        functions.messages.EditChatAboutRequest(peer=entity, about=about)
                    )
            return {
                "target": target,
                "updated_title": title is not None,
                "updated_about": about is not None,
            }
        except Exception as exc:
            self._raise_translated(exc)

    async def send_message(self, target: str, message: str) -> dict[str, Any]:
        try:
            sent = await self._client.send_message(target, message)
            return {"target": target, "message_id": sent.id}
        except Exception as exc:
            self._raise_translated(exc)

    async def resolve_target(self, target: str) -> dict[str, Any]:
        try:
            entity = await self._client.get_entity(target)
            return {"target": target, "entity_id": entity.id, "entity_type": type(entity).__name__}
        except Exception as exc:
            self._raise_translated(exc)

    async def pin_message(self, target: str, message_id: int) -> dict[str, Any]:
        try:
            await self._client.pin_message(target, message_id)
            return {"target": target, "message_id": message_id, "pinned": True}
        except Exception as exc:
            self._raise_translated(exc)

    async def unpin_message(self, target: str, message_id: int | None = None) -> dict[str, Any]:
        try:
            await self._client.unpin_message(target, message_id)
            return {
                "target": target,
                "message_id": message_id,
                "unpinned_all": message_id is None,
            }
        except Exception as exc:
            self._raise_translated(exc)

    async def edit_message(self, target: str, message_id: int, text: str) -> dict[str, Any]:
        try:
            await self._client.edit_message(target, message_id, text)
            return {"target": target, "message_id": message_id, "edited": True}
        except Exception as exc:
            self._raise_translated(exc)

    async def delete_message(self, target: str, message_id: int) -> dict[str, Any]:
        try:
            await self._client.delete_messages(target, [message_id])
            return {"target": target, "message_id": message_id, "deleted": True}
        except Exception as exc:
            self._raise_translated(exc)

    async def forward_message(
        self, from_target: str, to_target: str, message_id: int
    ) -> dict[str, Any]:
        try:
            forwarded = await self._client.forward_messages(to_target, message_id, from_target)
            return {
                "from_target": from_target,
                "to_target": to_target,
                "message_id": message_id,
                "forwarded_message_id": getattr(forwarded, "id", None),
            }
        except Exception as exc:
            self._raise_translated(exc)

    async def reply_message(
        self, target: str, reply_to_message_id: int, message: str
    ) -> dict[str, Any]:
        try:
            sent = await self._client.send_message(target, message, reply_to=reply_to_message_id)
            return {
                "target": target,
                "reply_to_message_id": reply_to_message_id,
                "message_id": sent.id,
            }
        except Exception as exc:
            self._raise_translated(exc)

    async def mark_read(self, target: str) -> dict[str, Any]:
        try:
            await self._client.send_read_acknowledge(target)
            return {"target": target, "read": True}
        except Exception as exc:
            self._raise_translated(exc)

    async def archive_chat(self, target: str) -> dict[str, Any]:
        try:
            # Folder 1 is Telegram's built-in Archive; folder 0 is the main list.
            await self._client.edit_folder(target, folder=1)
            return {"target": target, "archived": True}
        except Exception as exc:
            self._raise_translated(exc)

    async def mark_unread(self, target: str) -> dict[str, Any]:
        try:
            entity = await self._client.get_input_entity(target)
            await self._client(functions.messages.MarkDialogUnreadRequest(peer=entity, unread=True))
            return {"target": target, "unread": True}
        except Exception as exc:
            self._raise_translated(exc)

    async def mute_dialog(self, target: str) -> dict[str, Any]:
        # mute_until far in the future is Telegram's idiom for "mute indefinitely".
        return await self._set_mute(target, muted=True)

    async def unmute_dialog(self, target: str) -> dict[str, Any]:
        return await self._set_mute(target, muted=False)

    async def _set_mute(self, target: str, *, muted: bool) -> dict[str, Any]:
        try:
            entity = await self._client.get_input_entity(target)
            # 0 restores the default (unmuted); a large offset mutes effectively forever.
            mute_until = 2**31 - 1 if muted else 0
            await self._client(
                functions.account.UpdateNotifySettingsRequest(
                    peer=InputNotifyPeer(peer=entity),
                    settings=InputPeerNotifySettings(mute_until=mute_until),
                )
            )
            return {"target": target, "muted": muted}
        except Exception as exc:
            self._raise_translated(exc)

    async def pin_dialog(self, target: str) -> dict[str, Any]:
        return await self._set_dialog_pin(target, pinned=True)

    async def unpin_dialog(self, target: str) -> dict[str, Any]:
        return await self._set_dialog_pin(target, pinned=False)

    async def _set_dialog_pin(self, target: str, *, pinned: bool) -> dict[str, Any]:
        try:
            entity = await self._client.get_input_entity(target)
            await self._client(
                functions.messages.ToggleDialogPinRequest(
                    peer=InputDialogPeer(peer=entity), pinned=pinned
                )
            )
            return {"target": target, "pinned": pinned}
        except Exception as exc:
            self._raise_translated(exc)

    @staticmethod
    def _raise_translated(exc: Exception) -> NoReturn:
        if isinstance(exc, errors.FloodWaitError):
            raise RateLimitError(exc.seconds) from exc
        if isinstance(
            exc,
            (errors.ServerError, errors.RpcCallFailError, TimeoutError, ConnectionError, OSError),
        ):
            raise TransientActionError(str(exc)) from exc
        if isinstance(exc, errors.RPCError):
            raise PermanentActionError(
                f"Telegram rejected the action: {type(exc).__name__}"
            ) from exc
        raise TransientActionError(
            f"unexpected Telegram client error: {type(exc).__name__}"
        ) from exc


async def connect_gateway(
    api_id: int, api_hash: str, session_dir: Path, account: str
) -> tuple[TelegramClient, TelethonGateway]:
    """Open a session. Authentication is intentionally interactive through the CLI only."""
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / account
    client = TelegramClient(
        str(session_path), api_id, api_hash, flood_sleep_threshold=0, auto_reconnect=True
    )
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise PermanentActionError(
            f"account '{account}' is not authenticated; run the auth command first"
        )
    return client, TelethonGateway(client)
