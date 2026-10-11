# ADR 0019: key validation lives in the application, not in the inbound adapter

**Status:** accepted (2026-10-11)
**Issue:** #16 (PR review on the user-scoped-key cutover)
**Expectations:** `docs/expectations/delete-expenses.md` (item 3)

## Context

The reviewer's words: *"The logic to check for valid keys as well the execution of
this check should not be in the adapter but in the core of the application itself
where the key is used."*

At the cutover, key validation sat in `adapters/inbound/telegram_bot.py`: a module-level
`USER_KEY_PATTERN` and a `_is_well_formed_key` predicate, called by the `/delete`
command handler and by the delete-button callback handler before delegating to
`ExpenseQueryPort.delete_expense`. That made the adapter the owner of a product rule
("what is a well-formed key?"), and it made the rule invisible to every other inbound
adapter — a future Slack or Teams adapter would have to re-implement it, or skip it.

It also broke the hexagonal boundary: an inbound adapter's job is to translate wire
shapes into port calls and port results back into wire shapes. Deciding whether a
token is a legal key is domain policy, not transport translation.

## Decision

- **The shape predicate is a pure domain function.** `domain/expense_keys.py`
  exports `is_valid_expense_key(key: str) -> bool`: `^\d{8}-\d+$` full match **plus**
  a real-calendar parse of the 8 digits (`20261340-1` is malformed). Zero framework
  or IO imports; it knows nothing about repositories, users, or Telegram.
- **The check executes in the application use case.** `ExpenseQueryUseCase.delete_expense`
  calls the predicate *before* delegating, and returns
  `DeletionResult(status="invalid_key")` without touching the repository.
- **The port result carries the outcome.** `DeletionStatus = Literal["deleted",
  "not_found", "invalid_key"]`; `DeletionResult` gains `status: DeletionStatus =
  "not_found"` alongside `deleted`.
- **The adapter keeps no key logic.** `telegram_bot.py` loses `USER_KEY_PATTERN`,
  `_is_well_formed_key` and the `import re` that only served them. Both delete paths
  extract a key from the wire payload, delegate once, and branch on `status`:
  `invalid_key` → `Usage: /delete <key>` (command) / warning + silent return (button);
  `not_found` → the miss wording; `deleted` → the hit reply. The
  `data.startswith("delete:")` guard stays in the adapter — that is wire-payload
  handling, not key logic.

## Why

- Adapters do I/O translation only; a product rule that lives there is unreachable
  from the rest of the system and untestable without a transport mock.
- The same key is used by every inbound adapter that will ever exist (Telegram now,
  Slack/Teams later). Validation that is duplicated per adapter drifts; validation
  that runs where the key is *used* is written once and inherited.
- The predicate is domain-pure, so it belongs in `domain/` and can be reasoned about
  with no fixture at all.

## Consequences

- `DeletionResult` gains a field; the adapter branches on `status` only, never on
  key shape.
- Existing test mocks that write `DeletionResult(deleted=...)` keep working
  unchanged — `status` defaults to `"not_found"`, and those mocks are paired with
  assertions that do not compare `status`.
- The adapter can no longer reject a malformed key without a port call, so the
  port is now exercised by the malformed-key tests: they assert
  `delete_expense.assert_called_once_with(user_id, key)` and a
  `DeletionResult(status="invalid_key")` return, and the *application* tests assert
  the repository mock was not reached.
- Wording is unchanged and still pinned: `Usage: /delete <key>`,
  `Expense <key> was not found.`, `Expense not found.` (the button-path miss wording
  stays as ruled in **R10** — this ADR does not invent a new one), and the hit reply.
- Behave stays green without touching `features/delete.feature` or
  `features/steps/delete_steps.py`: the invalid-command table drives the real
  `ExpenseQueryUseCase`, which now rejects the keys itself.

## Out of scope

- Whether `invalid_key` and `not_found` should share one status — they do not, and
  the `/delete` handler needs them apart to answer with different wording.
- Validation of any other port argument (`user_id`, month/year ranges).
- Key *assignment* — still inside the INSERT, ADR 0016.
