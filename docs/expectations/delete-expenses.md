# Delete Saved Expenses — Expectations

> **Amended 2026-10-10 (ADR 0016 — User-scoped Expense Keys).** This file originally described
> addressing expenses by their global integer id and physically deleting them. Both are untrue
> now: expenses are addressed by a per-person key (`YYYYMMDD-n`), deletion is logical (ADR 0011),
> and CSV leads with a `user_key` column. Current contract: `docs/expectations/user-scoped-expense-keys.md`
> (E1–E14).

## Happy Path

1. **Per-person keys are assigned and visible in /list.**
   - When an expense is saved, the repository assigns it a per-person key `YYYYMMDD-n` — the prefix is the Expense's own `date`, `n` counts that person's expenses on that date from `1`, no zero-padding.
   - `/list` output shows each key in the format `#<key>` before each expense line (e.g. `#20260718-1`); a row whose key has not been backfilled renders `-` in that cell.
   - The global integer id is never shown to a user.

2. **/delete <key> logically deletes a user-scoped expense.**
   - `/delete 20260718-3` soft-deletes the Expense at that key for the current Telegram user only.
   - Successful deletion replies with: `🗑️ Deleted expense 20260718-3: <merchant> — <amount> <currency> — <date>` (no `#`).
   - After deletion the row is **retained** with `deleted_at` set (ADR 0011); `repository.delete_by_user_key(user_id, user_key)` returns the deleted `Expense`, and a repeat attempt on the same key returns `None`.
   - Deleted expenses disappear from `/list` and `/report`.

3. **/delete invalid formats show usage.**
   - `/delete`, `/delete abc`, `/delete 20260718-3 extra`, `/delete 0`, `/delete #20260712-1` (leading `#` is **not** accepted), `/delete 20261340-1` (regex-valid, calendar-invalid) all reply: `Usage: /delete <key>`.
   - Key shape is `^\d{8}-\d+$` **plus** a real-calendar check on the 8 digits.
   - Key validation is **application policy** (ADR 0019): `ExpenseQueryUseCase.delete_expense` returns `DeletionResult(status="invalid_key")` without touching the repository; the Telegram adapter renders from `status` and holds no key logic of its own.

4. **User-scoped delete: not-found for wrong user.**
   - User A's `/delete <key>` targeting user B's expense returns `Expense <key> was not found.`
   - User B's expense remains intact.
   - A key that is well-formed but already soft-deleted replies with the same miss wording.

5. **Save confirmations include the key and delete button.**
   - Complete photo extraction, complete free-text extraction, and successful correction all show `Expense 20260718-1` in the confirmation — no `#`.
   - Each confirmation has exactly one inline button: `🗑️ Delete` with callback data `delete:20260718-1`.

6. **Delete button edits original message with strikethrough.**
   - Tapping the delete button edits the original confirmation message.
   - Original details remain visible wrapped in `<s>...</s>` (HTML strikethrough).
   - `🗑️ Deleted.` is appended after the struck-through content.
   - The delete button is removed from the edited message.
   - The expense is soft-deleted: the row is retained with `deleted_at` set (ADR 0011).

## Edge Cases

7. **CSV output leads with the key column.**
   - CSV header is exactly `user_key,date,merchant,category,amount,currency`.
   - `user_key` is the **leading** column; a `None` key renders as the empty field (`,2026-07-15,Shop,,10.00,EUR`).
   - The global integer id is never a CSV column.

8. **The key column ships as a Liquibase changeset, not a hand edit.**
   - The `expenses` table gains `user_key TEXT` plus a `UNIQUE(user_id, user_key)` index via changeset `003-add-user-key` (table rebuild — SQLite cannot add a UNIQUE column by `ALTER TABLE`; ADR 0013 sanctions rebuild changesets).
   - Existing rows copy across with a `NULL` key; the backfill that gives them keys ships **alongside** this slice, never before it.
   - The `id` column itself is unchanged: `INTEGER PRIMARY KEY AUTOINCREMENT`, and it stays the storage join target.

9. **/list does not get per-expense delete buttons.**
   - The `/list` inline keyboard remains year/month navigation only.

10. **No confirmation prompt or undo.**
    - Delete button immediately deletes — no confirmation dialog.
    - There is no undo mechanism in this slice.

## Non-Behaviors

- Per-expense delete buttons are NOT present in `/list`.
- There is NO delete confirmation prompt.
- There is NO undo delete flow.
- CSV does NOT include the global id column — it includes the `user_key` column.
- No `DELETE FROM expenses` in `src/` — deletion is logical (ADR 0011).
- The global integer id is never user-facing (ADR 0016, E12).
- No `include_deleted` opt-in is added to any port.
- UUID dev databases are NOT migrated.

## Evidence Mapping

| Expectation | Evidence |
|-------------|----------|
| Per-person keys assigned | `test_save_returns_the_assigned_key` (pytest), delete.feature (behave) — E5 |
| Keys visible in /list | `test_month_view_leads_each_row_with_key` + `test_month_view_renders_placeholder_for_missing_key` (pytest), list.feature key assertions (behave) — E2 |
| /delete soft-deletes user-scoped | `TestDeleteHandler` tests (pytest), delete.feature (behave) — E4, E14 |
| /delete invalid format usage | `test_delete_handler_malformed_key_replies_usage_from_status`, `test_delete_handler_impossible_date_key_replies_usage`, `test_delete_handler_blank_argument_replies_usage_without_calling_the_port`, `test_delete_handler_no_argument_replies_usage` (pytest), delete.feature invalid-command table (behave) — E8 |
| invalid key rejected in the application layer | `test_delete_expense_rejects_malformed_key_without_touching_repository[20261340-1]` + `[abc]` (pytest) — `status="invalid_key"` and repository mock `assert_not_called`; the predicate itself: `TestExpenseKeyPredicate` (8 tests, `tests/domain/test_expense_keys.py`) — ADR 0019 |
| User-scoped not-found | `test_delete_by_user_key_returns_none_for_another_persons_key` (pytest), delete.feature (behave) — E9, E11 |
| Save confirmations with key + button | `test_confirmation_line_shows_key_without_hash` + `test_delete_callback_payload_carries_key` (pytest), telegram_bot.feature + correction.feature (behave) — E1, E3 |
| Delete button strikethrough edit | `TestDeleteCallbackHandler` (pytest), delete.feature @story-18 (behave) — E3 |
| CSV leads with user_key | `test_header_line` (pytest), report.feature (behave) — E6 |
| Schema changeset `003-add-user-key` lands the `user_key` column | `tests/migrations/test_changelog.py` changeset count (pytest), `tests/_schema/expenses.sql` snapshot — E1 |
