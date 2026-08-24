import asyncio
from typing import Any

import pytest
from telethon.tl import functions
from telethon.tl.types import Channel

from teleautomata.infrastructure.telegram import TelethonGateway, _invite_hash


class _FakeClient:
    """Minimal stand-in for TelegramClient: records the requests it is sent."""

    def __init__(self, entity: Any) -> None:
        self._entity = entity
        self.requests: list[Any] = []

    async def get_entity(self, target: str) -> Any:
        return self._entity

    async def __call__(self, request: Any) -> None:
        self.requests.append(request)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("https://t.me/+AbCdEf123", "AbCdEf123"),
        ("t.me/+AbCdEf123", "AbCdEf123"),
        ("https://t.me/joinchat/AbCdEf123", "AbCdEf123"),
        ("+AbCdEf123", "AbCdEf123"),
        ("https://t.me/joinchat/AbCdEf123/extra", "AbCdEf123"),
    ],
)
def test_invite_hash_extracts_private_links(target: str, expected: str) -> None:
    assert _invite_hash(target) == expected


@pytest.mark.parametrize(
    "target",
    ["@public_channel", "https://t.me/public_channel", "public_channel", "+", ""],
)
def test_invite_hash_returns_none_for_public_targets(target: str) -> None:
    assert _invite_hash(target) is None


def _channel() -> Channel:
    return Channel(
        id=123,
        title="Example",
        photo=None,
        date=None,
        creator=True,
        left=False,
        broadcast=True,
        verified=False,
        megagroup=False,
        restricted=False,
        signatures=False,
        min=False,
        scam=False,
        has_link=False,
        has_geo=False,
        slowmode_enabled=False,
        access_hash=0,
        username="example",
    )


def test_update_entity_edits_channel_about_via_messages_request() -> None:
    """A channel description edit must use messages.EditChatAboutRequest.

    Telethon has no ``functions.channels.EditAboutRequest``; editing an about
    text goes through the peer-based ``messages.EditChatAboutRequest`` for
    channels and chats alike. This guards against reintroducing a call to the
    non-existent request, which mypy cannot catch because Telethon ships no
    type information.
    """
    client = _FakeClient(_channel())
    gateway = TelethonGateway(client)  # type: ignore[arg-type]

    result = asyncio.run(gateway.update_entity(target="@example", title=None, about="New about"))

    assert result["updated_about"] is True
    assert len(client.requests) == 1
    assert isinstance(client.requests[0], functions.messages.EditChatAboutRequest)
    assert client.requests[0].about == "New about"
