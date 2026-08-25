"""Static, offline checks for the shipped examples and CI templates.

These tests never touch the network or a real Telegram account. They assert that
every example workflow is structurally valid, that its actions would pass the
same argument validation a live run performs (dispatched through an in-memory
recording gateway), that referenced data files exist, that nothing that looks
like a real secret has crept into the examples, and that the GitHub Actions
templates are valid YAML that only ever reference credentials via GitHub Secrets.
"""

import re
from pathlib import Path

import pytest
import yaml

# Reuse the full recording gateway from the action tests. pytest's default
# "prepend" import mode puts the tests directory on sys.path, so this resolves.
from test_actions import RecordingGateway

from teleautomata.application.actions import execute_action, registry
from teleautomata.workflows.schema import load_workflow

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"
WORKFLOW_DIR = EXAMPLES / "workflows"
SAMPLES_DIR = EXAMPLES / "samples"
GHA_DIR = EXAMPLES / "github-actions"

WORKFLOW_FILES = sorted(WORKFLOW_DIR.glob("*.y*ml"))
GHA_FILES = sorted(GHA_DIR.glob("*.y*ml"))

# A Telegram api_hash is a 32-character hex string; flag any hex run that long.
# Placeholder ids in the examples ("123456789", "1001234567890") are short
# decimal numbers and the sample invite hash contains non-hex letters, so none
# of them match this pattern.
_HEX_SECRET = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
# A phone number hard-coded into an example: "+" followed by 10-15 digits. The
# sample invite link "t.me/+AbCd..." has letters after the "+", so it is safe.
_PHONE = re.compile(r"\+\d{10,15}\b")
_CRED_TOKEN = re.compile(r"TELEGRAM_API_(?:ID|HASH)", re.IGNORECASE)


def _workflow_id(path: Path) -> str:
    return path.name


def test_example_directory_is_populated() -> None:
    """Guard against a glob that silently matches nothing."""
    assert WORKFLOW_FILES, f"no example workflows found in {WORKFLOW_DIR}"
    assert GHA_FILES, f"no GitHub Actions templates found in {GHA_DIR}"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_workflow_id)
def test_example_workflow_loads_and_validates(path: Path) -> None:
    """Every example parses and passes schema + dependency-graph validation."""
    definition = load_workflow(path)
    assert definition.actions, f"{path.name} has no actions"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_workflow_id)
def test_example_workflow_is_dry_run(path: Path) -> None:
    """Shipped examples must be safe to run as-is."""
    assert load_workflow(path).dry_run is True, f"{path.name} is not dry_run: true"


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_workflow_id)
def test_example_action_types_are_registered(path: Path) -> None:
    """Each action's type must exist in the dispatch registry."""
    definition = load_workflow(path)
    for action in definition.actions:
        assert action.type in registry.action_types, (
            f"{path.name}: unknown action type {action.type!r}"
        )


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_workflow_id)
def test_example_dependencies_reference_known_ids(path: Path) -> None:
    """depends_on must only name actions defined in the same workflow."""
    definition = load_workflow(path)
    ids = {action.id for action in definition.actions}
    for action in definition.actions:
        for dependency in action.depends_on:
            assert dependency in ids, (
                f"{path.name}: action {action.id!r} depends on unknown id {dependency!r}"
            )


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_workflow_id)
async def test_example_actions_pass_handler_validation(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dispatch every action offline to confirm its ``with:`` arguments are valid.

    Dry-run *skips* action handlers, so a passing dry-run does not prove the
    arguments are well-formed. Running each action through ``execute_action``
    against a recording gateway exercises exactly the validation a live run
    would, without any network access. ``users_csv`` paths in the examples are
    relative to the repository root, so run from there.
    """
    monkeypatch.chdir(REPO_ROOT)
    definition = load_workflow(path)
    gateway = RecordingGateway()
    for action in definition.actions:
        await execute_action(gateway, action)
    assert len(gateway.calls) == len(definition.actions)


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=_workflow_id)
def test_referenced_csv_files_exist(path: Path) -> None:
    """Any users_csv an example points at must be present in the repository."""
    definition = load_workflow(path)
    for action in definition.actions:
        csv_path = action.with_.get("users_csv")
        if csv_path is not None:
            assert (REPO_ROOT / csv_path).is_file(), (
                f"{path.name}: users_csv {csv_path!r} does not exist"
            )


def _text_files_under(directory: Path, *patterns: str) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(directory.glob(pattern)))
    return files


@pytest.mark.parametrize(
    "path",
    _text_files_under(WORKFLOW_DIR, "*.y*ml") + _text_files_under(SAMPLES_DIR, "*.csv"),
    ids=lambda p: p.name,
)
def test_examples_contain_no_hard_coded_secrets(path: Path) -> None:
    """No example or sample file may contain a credential-shaped string."""
    text = path.read_text(encoding="utf-8")
    assert not _HEX_SECRET.search(text), f"{path.name} contains a 32+ char hex string (api_hash?)"
    assert not _PHONE.search(text), f"{path.name} contains a hard-coded phone number"


@pytest.mark.parametrize("path", GHA_FILES, ids=_workflow_id)
def test_gha_template_is_valid_yaml(path: Path) -> None:
    """Each CI template parses and declares at least one job."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    # "on:" parses to the YAML boolean True; the trigger block may sit under
    # either key depending on the loader.
    assert document.get("on") is not None or True in document
    assert document.get("jobs"), f"{path.name} declares no jobs"


@pytest.mark.parametrize("path", GHA_FILES, ids=_workflow_id)
def test_gha_credentials_only_via_secrets(path: Path) -> None:
    """CI templates must never hard-code credentials.

    Any non-comment line that names a Telegram credential must reference it
    through the ``${{ secrets.* }}`` context, and no template may embed an
    api_hash- or phone-shaped literal.
    """
    text = path.read_text(encoding="utf-8")
    assert not _HEX_SECRET.search(text), f"{path.name} contains a 32+ char hex string (api_hash?)"
    assert not _PHONE.search(text), f"{path.name} contains a hard-coded phone number"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # prose in comments may name the variables freely
        if _CRED_TOKEN.search(line):
            assert "secrets." in line, (
                f"{path.name}: credential referenced without the secrets context: {stripped!r}"
            )


def test_gha_examples_demonstrate_secrets_usage() -> None:
    """The credentialed templates must actually show the secrets pattern."""
    texts = [p.read_text(encoding="utf-8") for p in GHA_FILES]
    assert any("${{ secrets.TELEGRAM_API_ID }}" in t for t in texts)
    assert any("${{ secrets.TELEGRAM_API_HASH }}" in t for t in texts)


def test_examples_docs_exist() -> None:
    """The examples guide and the CI guide the examples point at must be present."""
    assert (REPO_ROOT / "docs" / "examples.md").is_file()
    assert (REPO_ROOT / "docs" / "github-actions.md").is_file()
