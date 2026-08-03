"""Public error taxonomy — the canonical import path for TeleAutomata exceptions.

Catch :class:`TeleAutomataError` to handle any framework error, or a subclass
for a specific class of failure. These names are re-exported from the internal
domain layer so the public path stays stable if that layer is reorganized.
"""

from teleautomata.domain.errors import (
    PermanentActionError,
    RateLimitError,
    TeleAutomataError,
    TransientActionError,
)

__all__ = [
    "TeleAutomataError",
    "PermanentActionError",
    "TransientActionError",
    "RateLimitError",
]
