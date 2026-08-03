from pathlib import Path
from typing import Any

from telethon import TelegramClient, errors, functions
from telethon.tl.types import Channel

from telegram_automation.domain.errors import PermanentActionError, RateLimitError, TransientActionError


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
            chat = next((chat for chat in result.chats if getattr(chat, "title", None) == title), None)
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

    async def update_entity(self, target: str, title: str | None, about: str | None) -> dict[str, Any]:
        try:
            entity = await self._client.get_entity(target)
            if title is not None and isinstance(entity, Channel):
                await self._client(
                    functions.channels.EditTitleRequest(channel=entity, title=title)
                )
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
            return {"target": target, "updated_title": title is not None, "updated_about": about is not None}
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

    @staticmethod
    def _raise_translated(exc: Exception) -> None:
        if isinstance(exc, errors.FloodWaitError):
            raise RateLimitError(exc.seconds) from exc
        if isinstance(exc, (errors.ServerError, errors.RpcCallFailError, TimeoutError, ConnectionError, OSError)):
            raise TransientActionError(str(exc)) from exc
        if isinstance(exc, errors.RPCError):
            raise PermanentActionError(f"Telegram rejected the action: {type(exc).__name__}") from exc
        raise TransientActionError(f"unexpected Telegram client error: {type(exc).__name__}") from exc


async def connect_gateway(api_id: int, api_hash: str, session_dir: Path, account: str) -> tuple[TelegramClient, TelethonGateway]:
    """Open a session. Authentication is intentionally interactive through the CLI only."""
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / account
    client = TelegramClient(str(session_path), api_id, api_hash, flood_sleep_threshold=0, auto_reconnect=True)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise PermanentActionError(f"account '{account}' is not authenticated; run the auth command first")
    return client, TelethonGateway(client)
