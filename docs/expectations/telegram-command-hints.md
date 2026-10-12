# Telegram Command Hints Expectations (issue #10)

> **Amended 2026-10-10 (ADR 0016 — User-scoped Expense Keys).** The `/remove` hint text now
> addresses expenses by key: it explains `/delete <key>` and calls it an "expense key", never an
> "expense ID". The menu commands themselves are unchanged — they are hint-only and gain no parsing.

## Happy path

- The bot registers Telegram's native command menu via `Bot.set_my_commands` with exactly four commands, in this order: `list`, `report`, `add`, `remove`.
- Each command has a short non-empty user-facing description of at most 256 characters.
- `set_my_commands` is wired as the Application's `post_init` callback so it runs after PTB bot initialization (calling bot methods before initialization must not happen).
- Tapping the list menu button triggers the existing `/list` month-view behaviour (no new handler — the menu surfaces the existing command).
- Tapping the report menu button triggers the existing `/report` CSV export (no new handler).
- `/add` replies with a usage prompt telling the user to send a receipt/invoice photo or PDF, or describe the expense in text with at least amount and merchant.
- `/remove` replies with a usage prompt explaining `/delete <key>` and the 🗑️ Delete button under freshly recorded expenses (`REMOVE_EXPENSE_PROMPT` names the key, not an "expense ID").
- `WELCOME_MESSAGE` advertises the same command set as the menu (`/add`, `/remove` added alongside `/report`, `/list`).

## Edge cases

- An update with no effective message or user is ignored by both `/add` and `/remove` handlers (no reply, no crash) — mirrors existing handlers.

## Behaviors that must NOT happen

- `/delete <key>` behaviour is unchanged **by this issue**: argument parsing, the not-found reply (`Expense <key> was not found.`), and the success reply are exactly what ADR 0016's cutover pins (see `delete-expenses.md`); the menu commands add no parsing of their own.
- `/add` and `/remove` do NOT open a wizard, record anything, or touch the recording/query ports — they are hint-only commands.
- `/remove` is NOT an alias of `/delete`; it never performs a deletion itself.
- The command menu does not introduce inline keyboards or new dependencies.
