# Security

This framework automates real Telegram accounts. Treat everything it touches as
capable of real-world effect, and never operate entities you are not authorized
to manage.

## Credential handling

- Secrets come only from environment variables or `.env`, never from YAML,
  source control, logs, command-line arguments, or the operation database.
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are read from the environment at
  runtime. `.env` is git-ignored; `.env.example` documents the shape with empty
  values.
- 2FA passwords are prompted interactively by `auth` and never stored by this
  application.

## Session files

Telegram session files under `SESSION_DIR` are access material equivalent to a
password — anyone holding one can act as the account. The directory is
git-ignored. Protect it accordingly:

- Keep it on encrypted storage.
- Restrict filesystem access to the worker identity.
- Never commit it; never include it in backups or archives without encryption.
- One account session must never be shared across workers.

## Operation database

The database records workflow definitions, execution states, and action outputs.
It does not store secrets or message content. Treat recorded outputs as
potentially sensitive and control read access. In production, use PostgreSQL via
`DATABASE_URL` rather than a shared file database.

## Telegram-side safety

The framework deliberately treats Telegram's responses as authoritative and
does not attempt to bypass rate limits or restrictions:

- `FLOOD_WAIT` waits for Telegram's requested time; waits above
  `MAX_FLOOD_WAIT_SECONDS` fail safely for review instead of being slept off.
- Permanent rejections (permissions, privacy, invalid requests, unauthorized
  accounts) are terminal, not endlessly retried.
- Default pacing is conservative (`MIN_REQUEST_INTERVAL_SECONDS=1.0`, one
  operation per account). Increase only after observing real API behavior.
- Resume is safe for idempotent actions; review non-idempotent outcomes before
  re-running, since Telegram may have accepted a request before an observed
  interruption.

## Reporting

Report vulnerabilities privately to the maintainers rather than in a public
issue. Do not include credentials or session material in any report.
