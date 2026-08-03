import pytest

from telegram_automation.infrastructure.telegram import _invite_hash


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
