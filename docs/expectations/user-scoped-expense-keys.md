# User-scoped Expense Keys — Expectations (issue #16)

**Date:** 2026-10-10 · **Spec:** `docs/superpowers/specs/2026-10-10-user-scoped-expense-keys-design.md`
**Supersedes:** the identifier-facing parts of `delete-expenses.md`, `expense-query-policy.md`,
`telegram-command-hints.md` (all rewritten to this behaviour).
**Depends on:** ADR 0011 (logical deletion) — already merged; ADR 0016 records the decision.

## Concept

A person addresses their own Expenses by a **per-person key**, never by the storage id.
The key is `YYYYMMDD-n`: the prefix is the **Expense's own `date`** (not the insertion date),
`n` starts at `1`, no zero-padding. Keys are unique **for good** within a person — soft-deleted
rows are counted, so a freed number is never handed to a new Expense again.
`UNIQUE(user_id, user_key)` is the backstop. The global integer `id` stays the storage join
target and is never user-facing.

## Pinned strings (verbatim — Behave asserts these, do not paraphrase)

| Site | Exact value |
|---|---|
| Recording confirmation (photo, free-text, correction-resolved) | `Expense 20260718-1` — no `#` |
| `/list` row identifier cell | `#20260718-1` — the `#` marker is kept; an unbackfilled row renders `-` |
| Delete button callback payload | `delete:20260718-1` |
| `/delete` usage reply | `Usage: /delete <key>` |
| `/delete` miss reply | `Expense 20260718-3 was not found.` — the word `was` is required |
| `/delete` hit reply | `🗑️ Deleted expense 20260718-3: <merchant> — <amount> <currency> — <date>` (e.g. `🗑️ Deleted expense 20260712-1: Central Cafe — 3.50 EUR — 2026-07-12`) |
| CSV header | `user_key,date,merchant,category,amount,currency` — `user_key` is the **leading** column; a `None` key renders as the empty string |
| Key validation | `^\d{8}-\d+$` **plus** a real-calendar check on the 8 digits (`20261340-1` is malformed → usage) |

## Happy path

### E1 — Recording replies with its own key

- Complete photo extraction, complete free-text extraction, and a successful correction each
  reply with the key of the Expense just saved: `Expense 20260718-1`.
- `repository.save(expense)` returns the `Expense` with `user_key` already assigned — the key
  is fixed inside the write statement, so reading it back is not a second computation.
- `Expense.user_key` is `None` for an Expense that has never been persisted
  (`application/expense_recording.py::_build_expense` keeps it `None`).

### E2 — `/list` shows the key for every row, and nothing else identifies it

- Every row of a month view carries its key as `#20260718-1`; no row carries the global id.
- A row whose key has not been backfilled renders `-` in that cell and is not addressable
  by `/delete` (there is no key to type). This state exists in tests only — see "Deferred".
- Navigation, month headers, totals, and buttons are untouched.

### E3 — The delete button under a fresh confirmation carries the key

- `callback_data` is exactly `delete:20260718-1` — never `delete:42`.
- Tapping it still edits the original message with strikethrough and `🗑️ Deleted.` (ADR 0011
  behaviour unchanged).

### E4 — `/delete 20260718-3` soft-deletes that Expense and echoes the key

- Reply: `🗑️ Deleted expense 20260718-3: Central Cafe — 3.50 EUR — 2026-07-12`.
- The row is soft-deleted (`deleted_at` set), not removed; it disappears from `/list`,
  `/report`, and CSV.
- `ExpenseQueryPort.delete_expense(user_id, key)` and
  `ExpenseRepositoryPort.delete_by_user_key(user_id, user_key)` take the key; `delete_by_id`
  does not exist after the cutover (nothing keeps both).

### E5 — Expenses on the same expense date get `-1`, `-2` in insert order

- Two Expenses for one person on `2026-07-18`, saved in that order, get `20260718-1`
  and `20260718-2`.

### E6 — The CSV leads with the key

- Header is exactly `user_key,date,merchant,category,amount,currency`.
- A `None` key renders as an empty field (`,2026-07-15,Shop,,10.00,EUR`).
- Reply/attachment plumbing and the report reply text are untouched.

## Edge cases

### E7 — Submitted today, dated last month

- An Expense submitted on 2026-07-20 but dated 2026-06-30 gets key `20260630-1` (the
  Expense's own date, not the insertion date) and appears in the June listing, June totals,
  and June CSV.

### E8 — Malformed `/delete` argument → usage reply, nothing deleted

- `/delete`, `/delete abc`, `/delete 20260718-3 extra`, `/delete 20261340-1`
  (regex-valid, calendar-invalid), `/delete #20260712-1` (leading `#` is **not** accepted)
  all reply `Usage: /delete <key>` and delete nothing.

### E9 — Well-formed key that is not there → miss wording

- A key the person does not own, and a key already soft-deleted, both reply
  `Expense <key> was not found.`
- The other person's Expense is untouched; the already-deleted row is not resurrected.

### E10 — A freed key number is never reused

- Person deletes their own `20260718-3`; the next Expense they save for `2026-07-18` gets
  `20260718-4`, never `20260718-3`. Soft-deleted rows are counted by the key.

### E11 — Two people on the same expense date both get `-1`

- Person A and person B each get `20260718-1` for their first Expense on that date: same key
  text, different owner. A person cannot reach another person's Expense by typing a key.

## Behaviors that must NOT happen

- No global id in any user-facing message, listing line, CSV row, or button payload —
  including the `expense-extract` CLI stdout, which today prints the whole `Expense` repr.
- No old global integer resolves through `/delete` or a delete button after the cutover.
- No read path shows soft-deleted rows; no `include_deleted` opt-in is added anywhere.
- `DELETE FROM expenses` remains absent from `src/` (the fixture wipe in
  `features/environment.py` is test infrastructure, not product code).
- No `SELECT`-then-`INSERT`: the key is computed inside the write statement.
- No `INSERT OR REPLACE` anywhere — once the UNIQUE index exists, `REPLACE` can silently
  discard an unrelated Expense on a key clash. The explicit-id branch of `save()` becomes a
  plain `INSERT` carrying a `TODO` comment marking it as test-only scaffolding.
- `domain/` gains no framework or IO import; `Expense` stays a frozen dataclass.
- `get_by_id(expense_id: int)` is never called from `adapters/inbound/` (tests-only, internal).
- Fixtures never hand-write keys: `seed_expense` seeds with `id=None` through
  `repository.save`, so seeded rows acquire genuine keys.

## Invariants

### E12 — The global id is never user-facing

Not one user-visible artefact carries it: confirmation, listing row, delete reply, button
payload, CSV row, CLI stdout.

### E13 — The key is assigned inside the INSERT, and the UNIQUE index is the backstop

- One statement writes the row and its key (the key text is built from the row's own `date`
  parameter plus a `COUNT` subquery over the table) — spec §9 probe, `/tmp/keyprobe.db`.
- A forced duplicate `(user_id, user_key)` raises
  `sqlite3.IntegrityError: UNIQUE constraint failed: expenses.user_id, expenses.user_key`.
- Two rows with `NULL` `user_key` coexist under the UNIQUE index (the pre-backfill state).

### E14 — ADR 0011's invariants still hold after the cutover

- Deletion stays logical: the row is retained with `deleted_at` set.
- Every read still filters `deleted_at IS NULL`.
- No `DELETE FROM expenses` in `src/`; no `include_deleted` surface.
- `domain/` stays framework-free.

## Deferred — but not shippable apart

Backfill/migration of keys for Expenses that already exist in a database is separate work
(spec §8). **The two ship together**: nothing is released in the state where new Expenses
have keys and older ones do not, so the `-` cell of E2 exists only inside the repository and
in tests, never in a user's database.

## Expectation → test-name mapping

Later tasks write exactly these tests; the final task's evidence map reuses this table.
Pytest paths are under `tests/`, behave scenarios under `features/`.

| E | Expectation | Test names (pytest · behave) |
|---|---|---|
| E1 | Recording replies with its key | `tests/adapters/inbound/test_telegram_bot.py::test_save_confirmation_includes_key_and_delete_button` · `features/telegram_bot.feature` (`containing "Expense 20260715-1"`) · `features/correction.feature` (`containing "Expense 20260712-1"`) |
| E2 | `/list` rows carry their key; `-` for unbackfilled | `tests/adapters/inbound/test_telegram_bot.py::test_format_month_view_includes_expense_keys` · `tests/adapters/inbound/test_telegram_bot.py::test_format_month_view_renders_dash_for_unbackfilled_key` · `features/list.feature::Scenario: every listing row carries its key` |
| E3 | Delete button payload carries the key | `tests/adapters/inbound/test_telegram_bot.py::test_save_confirmation_includes_key_and_delete_button` (asserts `callback_data == "delete:20260718-1"`) · `features/delete.feature` (tap delete button) |
| E4 | `/delete <key>` soft-deletes and echoes | `tests/adapters/inbound/test_telegram_bot.py::test_delete_success_replies_with_key` · `features/delete.feature::Scenario: Delete expense by key` |
| E5 | Same-date Expenses get `-1`, `-2` in insert order | `tests/adapters/out/test_sqlite_repository.py::test_save_numbers_same_date_expenses_in_insert_order` · `features/delete.feature::Scenario: freed key number not reused` |
| E6 | CSV leads with the key column | `tests/domain/test_csv_generator.py::test_header_line` · `tests/domain/test_csv_generator.py::test_none_user_key_renders_empty_field` · `features/report.feature` · `features/cli_extraction.feature` |
| E7 | Key prefix is the Expense's own date | `tests/adapters/out/test_sqlite_repository.py::test_save_key_prefix_follows_expense_date_not_created_at` · `features/list.feature` (submitted-today-dated-last-month scenario) |
| E8 | Malformed argument → `Usage: /delete <key>` | `tests/adapters/inbound/test_telegram_bot.py::test_delete_invalid_format_returns_usage` (incl. `20261340-1`, `#20260712-1`) · `features/delete.feature` (invalid-command table) |
| E9 | Not-owned / already-deleted → `Expense <key> was not found.` | `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_returns_none_for_another_persons_key` · `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_returns_none_when_already_deleted` · `tests/adapters/inbound/test_telegram_bot.py::test_delete_not_found_replies_with_not_found_message` · `features/delete.feature::Scenario: person cannot address another person's expense` |
| E10 | Freed key number never reused | `tests/adapters/out/test_sqlite_repository.py::test_save_does_not_reuse_freed_key_number` · `features/delete.feature::Scenario: freed key number not reused` |
| E11 | Same key text for different owners; no cross-user reach | `tests/adapters/out/test_sqlite_repository.py::test_save_assigns_same_key_text_for_different_owners` · `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_deletes_only_the_owner_row` · `features/delete.feature::Scenario: two people share a key text` |
| E12 | Global id never user-facing | `tests/adapters/inbound/test_cli_extraction.py::test_cli_presents_key_not_internal_id` · the E2/E3/E4/E6 assertions · invariant greps: `rtk grep "Expense #" src`, `rtk grep "expense_id" src/expense_report/adapters/inbound` (no matches) |
| E13 | Key computed inside the INSERT; UNIQUE backstop | `tests/adapters/out/test_sqlite_repository.py::test_save_rejects_duplicate_key_via_unique_index` · `tests/adapters/out/test_sqlite_repository.py::test_save_allows_two_rows_with_null_user_key` · `tests/adapters/out/test_sqlite_repository.py::test_save_returns_the_assigned_key` · invariant grep: `rtk grep "INSERT OR REPLACE" src` (no matches) |
| E14 | ADR 0011 invariants preserved | `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_soft_deletes_row_retained` · `tests/adapters/out/test_sqlite_repository.py::test_reads_exclude_soft_deleted_rows` · `tests/domain/test_models.py::test_user_key_is_frozen` · `tests/domain/test_models.py::test_user_key_defaults_to_none_for_unpersisted_expense` · invariant greps: `rtk grep "DELETE FROM" src` (no matches), `rtk grep "delete_by_id" src` (no matches) |
