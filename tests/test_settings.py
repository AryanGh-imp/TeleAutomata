import pytest
from pydantic import ValidationError

from teleautomata.config.settings import Settings


def test_settings_reject_invalid_api_id() -> None:
    with pytest.raises(ValidationError, match="positive"):
        Settings(telegram_api_id=0)


def test_settings_requires_both_telegram_credentials() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_API_ID"):
        Settings().require_telegram_credentials()
