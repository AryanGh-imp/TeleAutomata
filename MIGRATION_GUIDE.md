# Migration guide — upgrading to 1.0.0

Version 1.0.0 freezes the public API under
[Semantic Versioning](https://semver.org/). Getting there required a handful of
breaking changes relative to the pre-1.0 code. This guide lists each one and how
to update. After 1.0.0, changes like these will only happen in a new major
version.

If you are installing TeleAutomata for the first time, you can ignore this guide
— just follow the [README](README.md) quick start.

## 1. Package and distribution renamed

The project was renamed from `telegram_automation` to **`teleautomata`**. This
affects the distribution name, the import root, and the CLI.

| Before | After |
| --- | --- |
| `pip install telegram-automation` | `pip install teleautomata` |
| `import telegram_automation` | `import teleautomata` |
| `telegram-automation run ...` | `teleautomata run ...` |

The default SQLite database path also changed to
`./data/teleautomata.sqlite3`. If you have an existing database under the old
name, either point `DATABASE_URL` at it or rename the file.

## 2. Import from the top-level public API

The stable public surface is now re-exported from the top-level package. Import
from `teleautomata` (or `teleautomata.errors`) rather than reaching into the
internal `domain` / `application` / `workflows` subpackages, whose layout is no
longer part of the public contract.

```python
# Before
from teleautomata.application.engine import WorkflowEngine
from teleautomata.workflows.schema import load_workflow
from teleautomata.domain.errors import PermanentActionError

# After
from teleautomata import WorkflowEngine, load_workflow
from teleautomata.errors import PermanentActionError
```

See [PUBLIC_API.md](PUBLIC_API.md) for the full stable surface.

## 3. Base exception renamed

The base of the error hierarchy is now `TeleAutomataError` (was
`TelegramAutomationError`), matching the package name. The subclasses
(`PermanentActionError`, `TransientActionError`, `RateLimitError`) are unchanged.

```python
# Before
from teleautomata.domain.errors import TelegramAutomationError

try:
    ...
except TelegramAutomationError:
    ...

# After
from teleautomata.errors import TeleAutomataError

try:
    ...
except TeleAutomataError:
    ...
```

## 4. `edit_message` argument renamed

The `edit_message` action's body argument is now **`message`** (was `text`),
consistent with `send_message` and `reply_message`. Update any workflow YAML:

```yaml
# Before
- id: fix_typo
  type: edit_message
  with: {target: "@channel", message_id: 42, text: "Corrected text"}

# After
- id: fix_typo
  type: edit_message
  with: {target: "@channel", message_id: 42, message: "Corrected text"}
```

## 5. `run` / `resume` exit codes

`run` and `resume` now exit non-zero **only when the run failed as a whole** — an
action failed *without* `continue_on_error`. A failure tolerated by
`continue_on_error` is still reported in the summary counts but no longer forces
a non-zero exit. If a script relied on any tolerated failure producing exit
code 1, inspect the printed summary (or the `status` command) instead.

## Not affected

Workflow file structure (`version: 1`), action names other than the argument
above, configuration environment variables, and the CLI command set are
unchanged. Existing `version: 1` workflows continue to load.
