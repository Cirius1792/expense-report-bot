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

Every test name below is verbatim from `docs/superpowers/plans/2026-10-10-user-scoped-expense-keys.md`; where the plan
names no test for an E-id, the row says so instead of inventing a name.

| E | Expectation | Test names (pytest · behave) |
|---|---|---|
| E1 | Recording replies with its key | pytest: `tests/adapters/inbound/test_telegram_bot.py::test_confirmation_line_shows_key_without_hash` · `tests/adapters/out/test_sqlite_repository.py::test_save_returns_the_assigned_key` · `tests/domain/test_models.py::test_create_with_all_fields` · `tests/domain/test_models.py::test_user_key_defaults_to_none_for_unpersisted_expense` · behave: `features/telegram_bot.feature` and `features/correction.feature` assertions `containing "Expense 20260715-1"` / `containing "Expense 20260712-1"` (Task 7; the plan names no scenario id for these)
| E2 | `/list` rows carry their key; `-` for unbackfilled | pytest: `tests/adapters/inbound/test_telegram_bot.py::test_month_view_leads_each_row_with_key` · `tests/adapters/inbound/test_telegram_bot.py::test_month_view_renders_placeholder_for_missing_key` · behave: `features/list.feature` step `the listing shows a key for every expense row` (Task 8; the plan names the step, no scenario id)
| E3 | Delete button payload carries the key | pytest: `tests/adapters/inbound/test_telegram_bot.py::test_delete_callback_payload_carries_key` (asserts `callback_data == "delete:20260715-1"`) · behave: `features/delete.feature` tap-the-delete-button scenarios (Task 7; no scenario id named)
| E4 | `/delete <key>` soft-deletes and echoes | pytest: `tests/adapters/inbound/test_telegram_bot.py::test_delete_handler_valid_key_deletes_and_echoes_key` · `tests/application/test_expense_queries.py::test_successful_delete_returns_deleted_expense` · behave: `features/delete.feature::Scenario: Delete an expense by key`
| E5 | Same-date Expenses get `-1`, `-2` in insert order | pytest: `tests/adapters/out/test_sqlite_repository.py::test_save_numbers_same_date_expenses_in_insert_order` · `tests/adapters/out/test_sqlite_repository.py::test_save_assigns_user_key_from_expense_date` · behave: the plan names no scenario for this E-id (Task 10's `Scenario: A freed key number is not reused` is the closest)
| E6 | CSV leads with the key column | pytest: `tests/domain/test_csv_generator.py::test_header_line` · `tests/domain/test_csv_generator.py::test_single_expense` · `tests/domain/test_csv_generator.py::test_multiple_expenses` · `tests/domain/test_csv_generator.py::test_category_none_uses_empty_string` · `tests/domain/test_csv_generator.py::test_null_user_key_renders_empty_cell` · `tests/application/test_expense_queries.py::test_generates_csv_for_given_period` · `tests/application/test_expense_queries.py::test_empty_period_returns_header_only` · behave: `features/report.feature` and `features/cli_extraction.feature` CSV assertions (Task 9; no scenario id named)
| E7 | Key prefix is the Expense's own date | pytest: `tests/adapters/out/test_sqlite_repository.py::test_save_key_prefix_follows_expense_date_not_created_at` · behave: the plan names no scenario for this E-id
| E8 | Malformed argument → `Usage: /delete <key>` | pytest: `tests/adapters/inbound/test_telegram_bot.py::test_delete_handler_malformed_token_replies_usage` · `tests/adapters/inbound/test_telegram_bot.py::test_delete_handler_impossible_date_key_replies_usage` · `tests/adapters/inbound/test_telegram_bot.py::test_delete_handler_no_argument_replies_usage` · behave: `features/delete.feature` invalid-command table rows `| /delete 20261340-1 |` and `| /delete #20260712-1 |` (Task 7; table rows named, no scenario id)
| E9 | Not-owned / already-deleted → `Expense <key> was not found.` | pytest: `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_returns_none_for_another_persons_key` · `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_returns_none_when_already_deleted` · `tests/adapters/inbound/test_telegram_bot.py::test_delete_handler_unknown_key_replies_not_found_wording` · `tests/application/test_expense_queries.py::test_not_found_returns_none_deleted` · behave: `features/delete.feature::Scenario: A person cannot address another person's expense`
| E10 | Freed key number never reused | pytest: `tests/adapters/out/test_sqlite_repository.py::test_save_does_not_reuse_a_key_freed_by_soft_deletion` · behave: `features/delete.feature::Scenario: A freed key number is not reused`
| E11 | Same key text for different owners; no cross-user reach | pytest: `tests/adapters/out/test_sqlite_repository.py::test_save_keys_are_per_person_on_the_same_date` · `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_deletes_only_the_owner_row` · behave: `features/delete.feature::Scenario: Two people share a key text`
| E12 | Global id never user-facing | pytest: `tests/adapters/inbound/test_telegram_bot.py::test_no_global_id_in_any_user_facing_text` · behave: `features/delete.feature::Scenario: A person cannot address another person's expense` (reply text pinned exactly) · Task 11 reds `tests/adapters/inbound/test_cli_extraction.py` on captured stdout but names no test, so there is no verbatim name to map · invariant greps: `rtk grep "Expense #" src`, `rtk grep "expense_id" src/expense_report/adapters/inbound` (no matches)
| E13 | Key computed inside the INSERT; UNIQUE backstop | pytest: `tests/adapters/out/test_sqlite_repository.py::test_save_rejects_a_key_clash_via_unique_index` (spelling verbatim from the plan) · `tests/adapters/out/test_sqlite_repository.py::test_save_allows_two_rows_with_null_user_key` · `tests/adapters/out/test_sqlite_repository.py::test_save_assigns_user_key_from_expense_date` · `tests/adapters/out/test_sqlite_repository.py::test_save_returns_the_assigned_key` · Task 3 updates four changeset-count assertions in `tests/migrations/test_changelog.py` (3 sites) and `scripts/upgrade-probe/verify.py` (1 site) — the plan names files and sites, no test names · invariant grep: `rtk grep "INSERT OR REPLACE" src` (no matches)
| E14 | ADR 0011 invariants preserved | pytest: `tests/adapters/out/test_sqlite_repository.py::test_delete_by_user_key_soft_deletes_row_retained` · `tests/ports/test_repository.py::test_protocol_compliance` · `tests/domain/test_models.py::test_user_key_is_frozen` · invariant greps: `rtk grep "DELETE FROM" src` (no matches), `rtk grep "delete_by_id" src` (no matches)
