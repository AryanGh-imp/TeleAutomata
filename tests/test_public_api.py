"""Guards for the public API facade.

These assert that the shallow public import paths re-export exactly the same
objects as their internal sources, so the facade cannot silently drift, and that
importing the package does not drag in the Telethon stack.
"""

import subprocess
import sys

import teleautomata
from teleautomata import errors
from teleautomata.domain import errors as domain_errors


def test_public_all_names_are_importable() -> None:
    for name in teleautomata.__all__:
        assert hasattr(teleautomata, name), f"{name} is declared in __all__ but not exported"


def test_errors_module_reexports_domain_errors() -> None:
    for name in errors.__all__:
        assert getattr(errors, name) is getattr(domain_errors, name)


def test_top_level_errors_match_errors_module() -> None:
    for name in errors.__all__:
        assert getattr(teleautomata, name) is getattr(errors, name)


def test_importing_package_does_not_require_telethon() -> None:
    # The public facade must stay lightweight: importing teleautomata pulls in
    # the engine and schema but never the MTProto adapter, so no Telethon. Run in
    # a fresh interpreter so a sibling test that imports the adapter can't make
    # this pass or fail by accident.
    result = subprocess.run(
        [sys.executable, "-c", "import teleautomata, sys; assert 'telethon' not in sys.modules"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
