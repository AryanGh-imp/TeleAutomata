# Release checklist

A repeatable checklist for cutting a TeleAutomata release. Steps are ordered;
do not skip the quality gate.

## 1. Pre-flight

- [ ] Working tree is clean and on the release branch (`git status`).
- [ ] `CHANGELOG.md` has a dated section for the new version, with `Added` /
      `Changed` / `Removed` entries and every **Breaking** change called out.
- [ ] Version is bumped consistently in `pyproject.toml` and
      `src/teleautomata/__init__.py` (`__version__`).
- [ ] For a major version: `MIGRATION_GUIDE.md` covers every breaking change,
      and `PUBLIC_API.md` reflects the current stable surface.
- [ ] `ROADMAP.md` matches reality — shipped items moved out of "planned".

## 2. Quality gate

Run the full gate; every step must pass with no warnings.

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m build
```

- [ ] `ruff check .` clean
- [ ] `ruff format --check .` clean
- [ ] `mypy src` clean (strict)
- [ ] `pytest` all green; tests make no network calls
- [ ] `python -m build` produces a wheel and sdist under `dist/`

## 3. Package validation

- [ ] `python -m twine check dist/*` reports the README renders on PyPI.
- [ ] Wheel contents look right (`teleautomata/`, `py.typed`, no `tests/`,
      no `.env`, no `sessions/`, no `data/`).
- [ ] A fresh-venv smoke install works:
      `pip install dist/teleautomata-*.whl` then `teleautomata --help` and
      `python -c "import teleautomata; print(teleautomata.__version__)"`.

## 4. Tag and publish

- [ ] Commit the release with the existing git identity (no Co-Authored-By).
- [ ] Tag `vX.Y.Z` and push the branch and tag.
- [ ] Publish to PyPI: `python -m twine upload dist/*`.
- [ ] Create the GitHub release from the tag, using
      `RELEASE_NOTES_v<version>.md` as the body.

## 5. Post-release

- [ ] `pip install teleautomata==X.Y.Z` from PyPI succeeds in a clean venv.
- [ ] Open a new `## [Unreleased]` section at the top of `CHANGELOG.md`.
- [ ] Confirm the roadmap and issues reflect what ships next.
