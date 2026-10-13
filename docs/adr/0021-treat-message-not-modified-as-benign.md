# ADR 0021: Treat Telegram "Message is not modified" as a Benign No-op

**Date:** 2026-10-13
**Status:** Accepted

## Context

Pressing the month button for the view already displayed (e.g. the current
month in `/list`) re-renders identical text and keyboard. Telegram rejects the
edit with `BadRequest: Message is not modified: specified new message content
and reply markup are exactly the same as a current content and reply markup of
the message`.

The list callback handler (`_make_list_callback_handler`) calls
`query.edit_message_text(...)` directly and does not catch this. Per ADR 0007,
factory handlers stay unwrapped, so the exception reaches the **global** error
handler (`handle_unexpected_error`), which:

1. logs the exception at ERROR with traceback, and
2. replies to the user with `GENERIC_ERROR_MESSAGE`
   (`⚠️ Il servizio non e' al momento disponibile. Riprova piu' tardi.`).

Result: a normal, idempotent "you are already viewing this" interaction is
reported to the user as a service outage.

## Decision

Classify `BadRequest: Message is not modified` as a **benign no-op** inside the
global error handler, not as an unexpected failure:

- New predicate `_is_message_not_modified(error)` in
  `adapters/inbound/telegram_bot.py` — true when the error is a
  `telegram.error.BadRequest` whose message starts with `Message is not modified`.
- `handle_unexpected_error` returns early for such errors: it logs at **INFO**
  (no traceback, no ERROR record) and does **not** notify the user.
- Any other `BadRequest` (e.g. `chat not found`) still follows the ADR 0007
  path: ERROR log + generic user message.

The benign case needs no user feedback because the user is already looking at
the requested view; the callback query was answered at the top of the handler,
so the client spinner is already stopped.

## Considered Options

| Option | Notes |
|--------|-------|
| **Central classification in the global error handler (chosen)** | Consistent with ADR 0007 (handlers stay unwrapped, one seam for all exceptions); fixes every current and future edit-based handler at once (list callback, delete callback, …) |
| Per-handler `try/except` around `edit_message_text` | Rejected by ADR 0007: duplicates logic across handlers and must be remembered for new handlers |
| Compare rendered content before calling `edit_message_text` and skip | Rejected: requires mirroring Telegram's server-side equality check (text **and** reply markup) client-side; fragile and racy |

## Consequences

- Idempotent "tap the current view" interactions are silent and healthy;
  they no longer inflate ERROR logs with false outages.
- Benign case remains observable via an INFO log line.
- The fix is Telegram-transport behavior and lives in the driving adapter,
  like ADR 0007; domain and application layers are untouched.
- Tests mock the PTB boundary: `tests/conftest.py` provides a real
  `BadRequest`-shaped exception class (`_FakeBadRequestError`) so the
  predicate and error handler can be exercised without the network.
