# Security Policy

## Supported versions

TeleAutomata is versioned with [Semantic Versioning](https://semver.org/).
Security fixes target the latest released minor version. Until 1.0 is tagged,
only the `main` branch is supported.

## Reporting a vulnerability

Please report security issues **privately**, not in a public issue or pull
request. Use GitHub's private vulnerability reporting
("Report a vulnerability" under the repository's **Security** tab), which opens
a private advisory visible only to the maintainers.

Include, where you can:

- a description of the issue and its impact,
- the version or commit affected,
- steps to reproduce, and
- any suggested remediation.

You can expect an initial acknowledgement within a few days. Once a fix is
available, we will coordinate a disclosure timeline with you and credit you in
the advisory unless you prefer otherwise.

## Scope and handling of credentials

TeleAutomata automates real Telegram accounts. It never persists
`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, phone numbers, or 2FA passwords: secrets
come only from the environment or `.env`, and Telethon session files are treated
as password-equivalent access material. See [docs/security.md](docs/security.md)
for the full operational security model. When reporting an issue, never include
real credentials or session files in your report.
