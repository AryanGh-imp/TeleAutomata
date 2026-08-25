# TeleAutomata

A safety-first, asynchronous framework for managing Telegram groups and channels through durable, declarative workflows. It is a maintainable application—not a bulk-action script—and deliberately treats Telegram responses, permissions, and rate limits as authoritative.

## Quick start

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
# Edit .env; add your own API ID and API hash from my.telegram.org.
teleautomata init
teleautomata validate examples/workflows/create-channel.yaml
teleautomata run examples/workflows/create-channel.yaml
```

The example is `dry_run: true`, so it writes a planned execution but makes no Telegram request. Authenticate only when ready to use an account:

```powershell
teleautomata auth primary
```

To retry an interrupted or failed execution without rerunning recorded successful actions, use `teleautomata resume <workflow.yml> <execution-id>`. Review non-idempotent action outcomes before resuming: Telegram may have accepted a request before a network interruption was observed.

Inspect workflows and past runs without connecting to Telegram:

```powershell
teleautomata list examples/workflows   # validate and summarize every workflow
teleautomata history                    # recent executions
teleautomata status <execution-id>      # per-action detail for one execution
```

Do not commit `.env` or the `sessions/` directory. Authentication is interactive; phone/2FA input is never placed in a workflow or database.

## Workflow format

```yaml
version: 1
name: update-project-channel
account: primary
dry_run: true
actions:
  - id: check_target
    type: resolve_target
    with: {target: "@my_project"}
  - id: update_description
    type: update_entity
    depends_on: [check_target]
    with:
      target: "@my_project"
      about: "A current project description"
    retry: {max_attempts: 3, initial_delay_seconds: 2, max_delay_seconds: 60}
```

TeleAutomata ships 29 actions across five categories — entity management,
messaging, dialogs, membership, and member management — documented in full in
[docs/actions.md](docs/actions.md). The library is a representative, frozen set
that demonstrates the pattern for adding more, not an exhaustive one. Actions run
only after their dependencies complete successfully. A failed dependency skips
its descendants, and each action has a durable history record.

## Examples

The [`examples/`](examples/) directory is a runnable cookbook. It holds sixteen
small, focused workflows — messaging, dialogs, entity and member management,
retry and `continue_on_error`, every accepted target format, CSV-driven member
lists, and a branching/fan-in DAG — each documented with what it demonstrates
and the exact commands to validate and dry-run it. All ship with `dry_run: true`,
so they are safe to run as-is with no credentials. Start with
[`examples/README.md`](examples/README.md).

```powershell
teleautomata list examples/workflows                       # validate all sixteen
teleautomata run examples/workflows/send-message.yaml      # dry-run one
```

To run workflows in CI, [`examples/github-actions/`](examples/github-actions/)
provides copy-and-adapt GitHub Actions templates (validate-on-push, manual, and
scheduled); [docs/github-actions.md](docs/github-actions.md) is the full guide.

## Operational safety

The framework defaults to running at most two actions concurrently (`MAX_CONCURRENCY`) and a one-second minimum interval between requests to an account. Telegram does not publish a universal safe throughput, so configure conservatively and observe real API responses. `FLOOD_WAIT` pauses for Telegram’s requested time; waits above `MAX_FLOOD_WAIT_SECONDS` fail safely for review. Invalid requests, missing permissions, privacy restrictions, and unauthorized accounts are terminal rather than endlessly retried.

Use it only for entities and accounts you are authorized to manage. This project does not attempt to bypass Telegram restrictions or automate spam-like behavior.

## Production deployment

- Set `DATABASE_URL` to PostgreSQL using `postgresql+asyncpg://...` and install `.[postgres]`.
- Put secrets in a deployment secret store and expose them as environment variables.
- Keep session files on encrypted persistent storage with access limited to the worker identity.
- Run one worker for a given account session; isolate workers for multiple accounts.
- Export structured JSON logs to your central log service, without credentials or message content.

See [architecture](docs/architecture.md), [API & interfaces](docs/api.md), [workflow engine](docs/workflow-engine.md), [actions](docs/actions.md), [CLI](docs/cli.md), [Telegram integration](docs/telegram-integration.md), [configuration](docs/configuration.md), [security](docs/security.md), [GitHub Actions](docs/github-actions.md), [testing](docs/testing.md), [development](docs/development.md), [extending](docs/extending.md), [FAQ](docs/faq.md), and [troubleshooting](docs/troubleshooting.md).

## Development

```powershell
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest
```

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[changelog](CHANGELOG.md). This project is released under the [MIT License](LICENSE).

## Extension points

The action dispatcher and `TelegramGateway` protocol are deliberate extension points. Add a new typed workflow action by implementing input validation and a gateway operation; the engine, scheduler, persistence, and retry policy remain unchanged. The initial schema is created at startup for a clean local installation. For controlled production rollout, generate and review an Alembic baseline migration before deploying schema changes.
