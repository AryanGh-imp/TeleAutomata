class TelegramAutomationError(Exception):
    """Base framework exception."""


class PermanentActionError(TelegramAutomationError):
    """The requested action cannot succeed by retrying."""


class TransientActionError(TelegramAutomationError):
    """Temporary service or network failure."""


class RateLimitError(TransientActionError):
    def __init__(
        self, retry_after_seconds: int, message: str = "Telegram requested a wait"
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
