# Contributing

Thank you for improving TeleAutomata. This project favors
maintainability and operational safety over feature count, so contributions are
reviewed against the existing architecture rather than added beside it.

## Development setup

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# Unix:     source .venv/bin/activate
pip install -e ".[dev]"
```

Tests use in-memory SQLite and a fake gateway; they never contact Telegram or
require credentials.

## Quality gate

Every change must pass the full quality gate — the same checks CI runs on every
push and pull request:

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m build
```

Run `ruff format .` to apply formatting before committing. Keep `mypy src`
strict-clean; Telethon's untyped surface is isolated at the adapter boundary,
not by weakening strictness project-wide.

## Architecture rules

The codebase is ports and adapters — see [docs/architecture.md](docs/architecture.md).
Please respect these boundaries:

- Keep all `telethon` imports inside `infrastructure/`. The rest of the code
  depends on the `TelegramGateway` protocol in `domain/ports.py`.
- Translate every Telegram exception at the anti-corruption boundary in
  `infrastructure/telegram.py` into a domain error (`RateLimitError`,
  `TransientActionError`, `PermanentActionError`). The engine alone decides
  whether an error is retryable.
- Validate action arguments in `application/actions.py`, close to the operation
  they belong to.

## Adding a workflow action

1. Add the type to the `ActionType` literal in `workflows/schema.py`.
2. Validate its arguments and dispatch it in `application/actions.py`.
3. Add a typed method to `TelegramGateway` (`domain/ports.py`) and implement it
   on `TelethonGateway` and `NullGateway`.
4. Add tests for the success, transient-failure, and permanent-failure paths.
5. Document authorization and pacing expectations.

## Commits and pull requests

- Write focused, logical commits with clear messages (this project uses
  Conventional Commit prefixes such as `feat:`, `fix:`, `test:`, `docs:`).
- Do not commit secrets, `.env`, session files, or the local `data/` database.
- Include tests with behavioral changes and update the relevant docs.

## Security

Never automate accounts or entities you are not authorized to manage. Report
security concerns privately rather than in a public issue — see
[SECURITY.md](SECURITY.md) for how. The operational security model is documented
in [docs/security.md](docs/security.md).
