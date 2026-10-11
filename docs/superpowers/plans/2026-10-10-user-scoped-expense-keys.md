# User-scoped Expense Keys — implementation plan

**Plan date:** 2026-10-10 · **Spec:** `docs/superpowers/specs/2026-10-10-user-scoped-expense-keys-design.md` · **Issue:** #16
**Depends on:** ADR 0011 (logical deletion) — already merged · **Slice shape:** **A** (S0 lands knowingly red; green gate enforced at end of S1)

> Created with the `writing-plans` skill. Every task is red-first TDD: failing test → implement → run → commit.
> Every task ends by pasting the actual command output into the conversation (AGENTS.md EDD rule: evidence, never narration).

---

## Scope check

The spec covers **one subsystem**: replacing the user-facing global id with a per-person key. It touches seven layers, but they are one connected cutover — one plan, twelve tasks, four vertical slices (S0–S4) plus docs, CLI, and the final gate. No second plan is needed.

**Out of scope (spec §3, §8):** backfill of existing databases (separate design, ships *alongside* this slice — never released in the interim state), restoring soft-deleted expenses, extraction/correction/period-discovery/totals, concurrency safety.

## Prerequisites

- `uv run pre-commit install` — **mandatory before any other work** (gitleaks hook). If not installed, install first; never bypass with `--no-verify` / `SKIP=gitleaks`.
- Docker daemon reachable + `docker pull liquibase/liquibase:4.33.0` for the integration profile and for regenerating the schema snapshot.
- Work in a clean worktree/branch; the repo already carries stale worktrees (`.worktrees/hexagonal-alignment`) — **never edit or grep into `.worktrees/`, `.venv/`, `.superpowers/`, or `__pycache__`**.

## Verification command (every task)

```bash
uvx ruff format && uvx ruff check && uvx ty check && uv run pytest -o addopts=""   # ~30s, unit + integration
uv run behave                                                                     # BDD gate
```

Green gate for **shape A**: the full `pytest -o addopts=""` run and `uv run behave` must both be green **at the end of Task 7 (S1)**. Tasks 2–6 are knowingly red in between — that state cannot ship and must not be released.

## Global constraints (verbatim from spec §5, §6, §7)

| Constraint | Source |
|---|---|
| `domain/` stays framework-free; `Expense` stays a frozen dataclass; no new imports there | hexagonal boundary, AGENTS.md |
| Ports are Protocols; adapters implement them; application owns use cases | ADR 0001, ADR 0006 |
| Every signature typed; no `Any`, no bare `dict` | AGENTS.md |
| Schema changes go through the Liquibase changelog, **never in-code DDL** | ADR 0013 |
| One INSERT statement holds the write lock for the whole key count | spec §5 |
| Key = expense **date** prefix, not insertion date | decision §6.1 |
| Keys unique for good — soft-deleted rows counted; a freed number is never reused | decision §6.2 |
| Key shape `YYYYMMDD-n`, `n` from 1, **no zero-padding** | decision §6.3 |
| `delete_by_id` is **dropped** when `delete_by_user_key` arrives — nothing keeps both | decision §6.10 (shape A) |
| The explicit-id branch of `save()` becomes a plain `INSERT` + `TODO` comment; no `INSERT OR REPLACE` anywhere | decision §6.7 |
| `/delete` takes the exact key, **no leading `#`** | decision §6.9 |
| `get_by_id(expense_id: int)` stays as-is: tests-only, internal-only | §7 port renames |

## Review focus — five input classes / failure modes

1. **Key collision within one person's records** — two Expenses of the same person on the same date must get `-1`, `-2`; the `UNIQUE(user_id, user_key)` index must fire (IntegrityError) if the count is ever computed wrong.
2. **Cross-user addressing** — a person typing another person's key must miss. Keys collide across people (`user 2` also gets `20260718-1`); ownership scoping in the SQL predicate is what makes it safe.
3. **Malformed / impossible input** — `/delete` with no argument, a non-key token, or `20261340-1` (regex-valid, calendar-invalid) → usage reply, nothing deleted. Distinct from a well-formed-but-absent key → `Expense <key> was not found.`
4. **Soft-delete interaction** — a deleted row must stay invisible to every read path, must never be re-addressable, and its slot must not be reused by the next insert.
5. **Information spill** — the global id must appear in **no** message, listing line, CSV row, or button payload; and no `SELECT`-then-`INSERT` may compute the key outside the write statement.

## Invariant greps (run at the final gate; expected output in each row)

| # | Command | Expected |
|---|---|---|
| 1 | `rtk grep "DELETE FROM" src` | no matches (ADR 0011 consequence; `features/environment.py` fixture wipe is out of scope — invariant is stated over `src/`) |
| 2 | `rtk grep "get_by_id" src/expense_report/adapters/inbound` | no matches |
| 3 | `rtk grep "delete_by_id" src` | no matches |
| 4 | `rtk grep "Expense #" src` and `rtk grep "expense_id" src/expense_report/adapters/inbound` | no matches |
| 5 | `rtk grep "INSERT OR REPLACE" src` | no matches |
| 6 | `rtk grep -l "import" src/expense_report/domain/models.py` | unchanged import set (no framework/IO) |
| 7 | `rtk grep "user_key" db/changelog/db.changelog.xml` | changeset `003-add-user-key` present |

## File structure (what changes, why)

```
docs/expectations/user-scoped-expense-keys.md   NEW  EDD expectations, written before implementation (Task 1)
docs/adr/0016-user-scoped-expense-keys.md       NEW  the decision record (Task 1)
docs/adr/0011-logical-deletion.md               EDIT one-line note: "ADR 0010 (user-scoped ids)" was never written → ADR 0016
docs/expectations/logical-deletion.md           EDIT same note + the deferred-row line
docs/expectations/delete-expenses.md            REWRITE asserts #<id>, hard deletion, no CSV id column
docs/expectations/expense-query-policy.md       REWRITE pins delete_by_id
docs/expectations/telegram-command-hints.md     REWRITE pins /delete <expense_id>

src/expense_report/
  domain/models.py                EDIT  Expense gains user_key: str | None (after id)
  domain/csv_generator.py         EDIT  leading user_key column
  ports/repository.py             EDIT  delete_by_user_key replaces delete_by_id; save docstring states key
  ports/expense_queries.py        EDIT  delete_expense(user_id, key: str)
  application/expense_queries.py  EDIT  delegates only — no key logic
  application/expense_recording.py UNCHANGED (_build_expense keeps user_key=None)
  adapters/out/sqlite_repository.py  EDIT single-statement INSERT; delete_by_user_key; _row_to_expense
  adapters/inbound/telegram_bot.py   EDIT listing line, confirmation, button payload, /delete parse+validate, wordings
  adapters/inbound/cli_extraction.py EDIT expense-extract presents the key, not the internal id

db/changelog/db.changelog.xml     EDIT  changeset 003-add-user-key (table rebuild + UNIQUE index)
tests/_schema/expenses.sql        REGEN uv run python -m tests._schema --write (digest-guarded artifact)
tests/migrations/test_changelog.py       EDIT 3 changeset-count assertions 2 → 3
scripts/upgrade-probe/verify.py  EDIT 1 changeset-count assertion 2 → 3

features/delete.feature           EDIT  S1 re-expression + S4 anti-spill scenarios
features/telegram_bot.feature     EDIT  "Expense #1" → "Expense 20260715-1"
features/correction.feature       EDIT  "Expense #1" → key
features/list.feature             EDIT  S2 key assertions
features/report.feature           EDIT  S3 CSV header/row
features/cli_extraction.feature   EDIT  CLI output presents key
features/steps/delete_steps.py    EDIT  fixture seeds id=None; Then steps look up by key
features/steps/list_steps.py      EDIT  id column optional; key assertions
features/steps/common_steps.py    UNCHANGED seed_expense already seeds id=None through save → real keys for free
features/environment.py           EDIT  comment only (fixture DELETE FROM stays; it makes numbering reproducible)
```

---

## Task 1 — Expectations and decision record (docs only, S0)

**Files**
- Create `docs/expectations/user-scoped-expense-keys.md`
- Create `docs/adr/0016-user-scoped-expense-keys.md`
- Modify `docs/adr/0011-logical-deletion.md`, `docs/expectations/logical-deletion.md`, `docs/expectations/delete-expenses.md`, `docs/expectations/expense-query-policy.md`, `docs/expectations/telegram-command-hints.md`

**Interfaces** — Produces for every later task: expectation ids `E1…E14` that the test names below must map onto one-to-one.

- [ ] Write the expectations file **before any code**: happy path (recording replies with its key; `/list` shows a key per row; button carries `delete:20260718-1`; `/delete 20260718-3` soft-deletes and echoes; same-date expenses get `-1`/`-2` in insert order; CSV leads with the key), edge cases (submitted-today-dated-last-month; no-arg / non-key / impossible-date → usage; not-owned / already-deleted → miss wording; freed number not reused; two people same date both get `-1`), and the Must-NOT list (global id anywhere user-facing, no `DELETE FROM expenses` in `src/`, no `include_deleted`, no SELECT-then-INSERT, no framework import in `domain/`). Be specific: pin the exact strings.
- [ ] Write ADR 0016: context (global id leaks cross-user write activity), decision (`YYYYMMDD-n` per-person key computed inside the INSERT, `UNIQUE(user_id, user_key)` backstop, global id stays the storage join target), consequences (backfill ships alongside; interim state exists only in tests; ADR 0011's key-count rule is honoured).
- [ ] In `docs/adr/0011-logical-deletion.md` and `docs/expectations/logical-deletion.md`, add a one-line note wherever "ADR 0010 (user-scoped ids)" appears: *"(that ADR was never written; the decision now lives in ADR 0016 — User-scoped Expense Keys)".* No renumbering.
- [ ] Rewrite the three stale expectation files to the new behaviour (`delete-expenses.md`: key not `#<id>`, logical not physical, CSV carries the key column; `expense-query-policy.md`: `delete_by_user_key`; `telegram-command-hints.md`: `/delete <key>`).
- [ ] Commit: `docs: expectations + ADR 0016 for user-scoped expense keys`

**Verification:** `uvx ruff format && uvx ruff check && uvx ty check && uv run pytest -o addopts=""` — must stay green (no code changed).

---

## Task 2 — Domain: `Expense.user_key` (S0)

**Files** — Modify `src/expense_report/domain/models.py`, Modify `tests/domain/test_models.py`

**Interfaces** — Produces `Expense.user_key: str | None` (positional field immediately after `id`, **no default** — `deleted_at` is the only defaulted field and must stay last). Consumed by Tasks 3–11. `domain/` gains **no** import.

- [ ] Red: add to `tests/domain/test_models.py`
  - `test_create_with_all_fields` — extend the existing construction with `user_key="20260718-2"` and assert it round-trips.
  - `test_user_key_defaults_to_none_for_unpersisted_expense` — an `Expense` built by `_build_expense`-style code (no `user_key`) has `user_key is None`.
  - `test_user_key_is_frozen` — assignment raises (`FrozenAttributeError`).
- [ ] Run `uv run pytest tests/domain/test_models.py` → confirm red, paste output.
- [ ] Green: add the field + docstring line ("per-person key assigned by the repository at save time; `None` means not persisted / pre-backfill row").
- [ ] Run `uv run pytest tests/domain/test_models.py` → green, paste output.
- [ ] Commit: `domain: Expense.user_key value object field`

---

## Task 3 — Schema: changeset `003-add-user-key` + snapshot + count assertions (S0)

**Files** — Modify `db/changelog/db.changelog.xml`, Regenerate `tests/_schema/expenses.sql`, Modify `tests/migrations/test_changelog.py` (3 sites), Modify `scripts/upgrade-probe/verify.py` (1 site)

**Interfaces** — Produces the `expenses` column `user_key TEXT` and `CREATE UNIQUE INDEX uk ON expenses (user_id, user_key)`. Consumed by Task 4 (INSERT) and by `tests/_schema.apply_snapshot` (hermetic unit fixtures).

- [ ] Add the changeset. SQLite cannot add a constraint by `ALTER TABLE`, so it is a **table-rebuild** changeset (sanctioned by ADR 0013), guarded by the same `preconditions` idiom as `002`:

```xml
<changeSet id="003-add-user-key" author="expense-report">
  <preconditions onFail="MARK_RAN" onError="HALT">
    <not><sqlCheck expectedResult="1">SELECT CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('expenses') WHERE name = 'user_key') THEN '1' ELSE '0' END</sqlCheck></not>
  </preconditions>
  <sql>CREATE TABLE expenses_new (id INTEGER PRIMARY KEY AUTOINCREMENT, amount TEXT NOT NULL, currency TEXT NOT NULL, merchant TEXT NOT NULL, date TEXT NOT NULL, category TEXT, user_id INTEGER NOT NULL, receipt_photo_id TEXT, created_at TEXT NOT NULL, deleted_at TEXT, user_key TEXT);</sql>
  <sql>CREATE UNIQUE INDEX uk ON expenses_new (user_id, user_key);</sql>
  <sql>INSERT INTO expenses_new (id, amount, currency, merchant, date, category, user_id, receipt_photo_id, created_at, deleted_at) FROM expenses;</sql>
  <sql>DROP TABLE expenses;</sql>
  <sql>ALTER TABLE expenses_new RENAME TO expenses;</sql>
</changeSet>
```

  Old rows copy across with a **NULL** key (backfill is deferred, §8); ids are copied explicitly so the AUTOINCREMENT counter and existing joins survive. If Liquibase rejects one-statement-per-`<sql>` splitting, keep splitting until the integration run accepts it — do **not** fold DDL into product code (ADR 0013).
- [ ] Regenerate the snapshot: `uv run python -m tests._schema --write` (needs Docker), then `rtk read tests/_schema/expenses.sql` and confirm `user_key TEXT` + `CREATE UNIQUE INDEX uk` appear and the `source-changelog-sha256` line changed.
- [ ] Update the four changeset-count assertions `2 → 3`: `tests/migrations/test_changelog.py` (three `databasechangelog` counts) and `scripts/upgrade-probe/verify.py` (`after["changesets"] == 2`).
- [ ] Run `uv run pytest tests/migrations` (hermetic — snapshot guard) and `uv run pytest -o addopts="" -m integration tests/migrations` (real Liquibase). Paste both outputs.
- [ ] Run the upgrade probe end-to-end (`scripts/upgrade-probe/` recipe) and confirm `verify.py` still prints `PASS` — it asserts `after["rows"] == before["rows"]`, which now also proves the rebuild copied every legacy row across.
- [ ] Commit: `schema: changeset 003-add-user-key (table rebuild + UNIQUE(user_id,user_key))`

**Review note:** the rebuild `DROP TABLE` is not a physical row deletion in the ADR 0011 sense — every row is copied across and the probe's row-count assertion proves it. Flag it if the row count ever differs.

---

## Task 4 — Driven adapter: key computed inside the INSERT (S0)

**Files** — Modify `src/expense_report/adapters/out/sqlite_repository.py`, Modify `tests/adapters/out/test_sqlite_repository.py`

**Interfaces** — Consumes Task 2 field + Task 3 schema. Produces:
- `SqliteExpenseRepository.save(expense: Expense) -> Expense` returning the saved `Expense` with `user_key` populated.
- `SqliteExpenseRepository.delete_by_user_key(user_id: int, user_key: str) -> Expense | None` (replaces `delete_by_id`; **delete `delete_by_id` outright** — shape A).
- `_row_to_expense` maps `user_key` (`None` passes through).
- `get_by_id`, `get_by_user_and_month`, `get_months_with_expenses`, `get_total_by_user_and_year` keep their shape and keep filtering `deleted_at IS NULL`.

- [ ] Red — add to `tests/adapters/out/test_sqlite_repository.py` (fixture: the migrated/snapshot DB, same as existing `snapshot_db`/`repo` fixtures):
  - `test_save_assigns_user_key_from_expense_date` — save `date=2026-07-18` for `user_id=1` → returned `Expense.user_key == "20260718-1"`.
  - `test_save_numbers_same_date_expenses_in_insert_order` — second save, same user + same date → `"20260718-2"`.
  - `test_save_keys_are_per_person_on_the_same_date` — `user_id=2`, same date → `"20260718-1"` (same text, different owner).
  - `test_save_key_prefix_follows_expense_date_not_created_at` — `date=2026-06-30`, `created_at=2026-07-20` → `"20260630-1"`.
  - `test_save_does_not_reuse_a_key_freed_by_soft_deletion` — save two, soft-delete the second via `delete_by_user_key`, save a third → `"20260718-3"`.
  - `test_save_returns_the_assigned_key` — the returned object's `user_key` matches the stored row on re-read.
  - `test_save_rejects_a_key_clash_via_unique_index` — force a duplicate `(user_id, user_key)` with a raw `execute` → `sqlite3.IntegrityError` matching `UNIQUE constraint failed: expenses.user_id, expenses.user_key`.
  - `test_save_allows_two_rows_with_null_user_key` — the pre-backfill state: two legacy rows coexist.
  - `test_delete_by_user_key_deletes_only_the_owner_row` — `delete_by_user_key(1, "20260718-1")` soft-deletes user 1's row; user 2's identically-keyed row survives.
  - `test_delete_by_user_key_returns_none_for_another_persons_key`
  - `test_delete_by_user_key_returns_none_when_already_deleted`
  - `test_delete_by_user_key_soft_deletes_row_retained` — row still in the table with `deleted_at` set (rename of existing `test_delete_by_id_soft_deletes_row_retained`).
  - Rename the remaining `test_delete_by_id_*` tests to `test_delete_by_user_key_*` (lines ~414–460, 629, 691).
  - Keep `test_get_by_id_*` tests as-is — `get_by_id` stays internal/tests-only.
- [ ] Run `uv run pytest tests/adapters/out/test_sqlite_repository.py` → red, paste output.
- [ ] Green — one INSERT, key built inside the write statement (spec §9, verified probe). Use named parameters so the date is not repeated positionally:

```python
cur = self._conn.execute(
    """
    INSERT INTO expenses
      (amount, currency, merchant, date, category, user_id, receipt_photo_id, created_at, deleted_at, user_key)
    VALUES (
      :amount, :currency, :merchant, :date, :category, :user_id, :receipt_photo_id, :created_at, :deleted_at,
      substr(:date,1,4) || substr(:date,6,2) || substr(:date,9,2) || '-' ||
      ((SELECT count(id) FROM expenses WHERE user_id = :user_id AND date = :date) + 1)
    )
    """,
    {...},
)
```

  No `deleted_at IS NULL` in the count — keys are unique for good (decision §6.2). Read the row back with `cur.lastrowid` (or the explicit id in the scaffolding branch) to return the saved `Expense`; that second statement is a read, not a race (spec §9).
- [ ] Explicit-id branch: plain `INSERT` (drop `OR REPLACE`) + `# TODO: test-only scaffolding — replacing seeding is separate later work` (decision §6.7).
- [ ] `delete_by_user_key`: `SELECT * WHERE user_id = ? AND user_key = ? AND deleted_at IS NULL`, then `UPDATE expenses SET deleted_at = ? WHERE user_id = ? AND user_key = ?`. Never reference `id`. Log **both** the internal id and the key at this boundary (logging call, §7).
- [ ] Run the file's tests → green, paste output.
- [ ] Commit: `adapter(out/sqlite): compute user_key inside the INSERT; delete_by_user_key`

---

## Task 5 — Ports + application rename (S0)

**Files** — Modify `src/expense_report/ports/repository.py`, `src/expense_report/ports/expense_queries.py`, `src/expense_report/application/expense_queries.py`, `tests/ports/test_repository.py`, `tests/application/test_expense_queries.py`

**Interfaces** — Produces:
- `ExpenseRepositoryPort.delete_by_user_key(self, user_id: int, user_key: str) -> Expense | None` (docstring states: deleted rows are **counted** by the key and **excluded** from reads).
- `ExpenseQueryPort.delete_expense(self, user_id: int, key: str) -> DeletionResult`.
- `ExpenseQueryUseCase.delete_expense(self, user_id: int, key: str) -> DeletionResult` — delegates to `self._repo.delete_by_user_key(user_id, key)`; **no key logic, no validation here** (validation lives in the inbound adapter, lookup in the driven adapter).
- `save` docstring: "returns the saved expense with its persistent id and its assigned per-person `user_key`."

- [ ] Red: `tests/application/test_expense_queries.py` — rename `test_successful_delete_returns_deleted_expense` / `test_not_found_returns_none_deleted` bodies to `repo.delete_by_user_key` mocks and `use_case.delete_expense(12345, "20260718-3")`, asserting `repo.delete_by_user_key.assert_called_once_with(12345, "20260718-3")`.
- [ ] Red: `tests/ports/test_repository.py` — the `FakeRepository` implementations rename `delete_by_id` → `delete_by_user_key` keyed on `(user_id, user_key)`; `test_protocol_compliance` must fail while the port still names `delete_by_id`.
- [ ] Run both files → red, paste output.
- [ ] Green: rename in the two port Protocols and the application delegation; update the `FakeRepository` fixtures.
- [ ] Run both files → green, paste output.
- [ ] Commit: `ports+application: delete_by_id → delete_by_user_key (no transitional surface)`

**Known red state:** Tasks 4–5 break `features/delete.feature`, the delete-button fixture, and the telegram adapter tests. That is shape A — do not chase it; Task 6–7 close it.

---

## Task 6 — Driving adapter cutover: Telegram (S1)

**Files** — Modify `src/expense_report/adapters/inbound/telegram_bot.py`, Modify `tests/adapters/inbound/test_telegram_bot.py`

**Interfaces** — Consumes Tasks 4–5. Produces the pinned user-facing strings (Behave asserts them verbatim in Task 7, so they are review-pinned):

| Site | New value |
|---|---|
| `_format_month_view` line | `f"#{(e.user_key or '-'):<10} {e.date}  {e.merchant:<20}" f" {e.amount:>8.2f} {e.currency:<4} {e.category or ''}"` → `#20260718-1 2026-07-18  …`; unbackfilled row renders `-` |
| Recording confirmation (×2: photo + correction-resolved) | `f"Expense {saved_expense.user_key}\n"` — `#` dropped |
| Delete button payload | `callback_data=f"delete:{saved_expense.user_key}"` |
| `/delete` usage | `Usage: /delete <key>` |
| `/delete` miss | `f"Expense {key} was not found."` |
| `/delete` hit | `f"🗑️ Deleted expense {deleted.user_key}: {deleted.merchant} — {deleted.amount:.2f} {deleted.currency} — {deleted.date}"` |
| `REMOVE_EXPENSE_PROMPT` | `/delete <key>`; "expense key" instead of "expense ID" |
| Validation | `^\d{8}-\d+$` **plus** real-calendar check on the 8 digits (`datetime.strptime(digits, "%Y%m%d")`); malformed → usage |

- [ ] Red — unit tests in `tests/adapters/inbound/test_telegram_bot.py` (rename the six `test_delete_*` tests at lines ~1650–1810 and `test_save_confirmation_includes_id_and_delete_button`):
  - `test_delete_handler_valid_key_deletes_and_echoes_key` — `/delete 20260718-3` → `delete_expense(12345, "20260718-3")`, reply is the hit wording.
  - `test_delete_handler_unknown_key_replies_not_found_wording`
  - `test_delete_handler_malformed_token_replies_usage` — `"abc"`, `"#20260718-1"`, `"-1"`, `""`.
  - `test_delete_handler_impossible_date_key_replies_usage` — `"20261340-1"` (regex-valid, calendar-invalid).
  - `test_delete_handler_no_argument_replies_usage`
  - `test_delete_callback_payload_carries_key` — button `callback_data == "delete:20260715-1"`.
  - `test_confirmation_line_shows_key_without_hash`
  - `test_month_view_leads_each_row_with_key` — `#20260710-1`, alignment intact.
  - `test_month_view_renders_placeholder_for_missing_key` — `user_key is None` → `-` cell, and the row is **not** addressable.
  - `test_no_global_id_in_any_user_facing_text` — assert `str(expense.id)` absent from reply text and button payload.
- [ ] Run `uv run pytest tests/adapters/inbound/test_telegram_bot.py` → red, paste output.
- [ ] Green: implement the table above. `/delete` parsing: `text.split(maxsplit=1)` → strip → validate shape+calendar → `expense_queries.delete_expense(user_id, key)`. Callback handler: `data.split(":", 1)[1]` is the key **as a string** (drop `int(...)`); malformed payload logs a warning and returns.
- [ ] Logging at this boundary carries both identities: `logger.info("Saved expense %s (key %s) for user %s", saved_expense.id, saved_expense.user_key, ...)`.
- [ ] Run → green, paste output.
- [ ] Commit: `adapter(in/telegram): cutover to user-scoped keys`

---

## Task 7 — Behave cutover on the recording/delete path (S1) — **GREEN GATE**

**Files** — Modify `features/delete.feature`, `features/telegram_bot.feature`, `features/correction.feature`, `features/steps/delete_steps.py`, `features/steps/common_steps.py` (comment only), `features/environment.py` (comment only)

**Interfaces** — Consumes Task 6. Produces the end-to-end proof for S1.

- [ ] `features/steps/delete_steps.py`:
  - `@given("a saved confirmation for expense {expense_key} exists:")` — feature table **drops the `id` column** and names the expense dates that drive the key; seed with `id=None` through `repository.save` (the `id=int(row["id"])` fixture at line ~99 takes the explicit-id branch and would produce a key-less, unaddressable row).
  - `@when("I tap the delete button for expense {expense_key}")` — `query.data = f"delete:{expense_key}"`; the fixture message text uses `Expense {expense_key}`.
  - `@then("expense {expense_key} should no longer be recorded")` — look up via `context.repository.get_by_user_and_month(...)` filtered on `user_key`, **not** `get_by_id`.
  - `@then("expense {expense_key} should still be recorded for user {user_id:d}")` — same lookup, assert present and `user_id` matches.
- [ ] `features/delete.feature` re-expression (verbatim strings from Task 6's table):

```gherkin
Scenario: Delete an expense by key
  Given a saved confirmation for expense 20260712-1 exists:
    | amount | currency | merchant     | date       | category |
    | 3.50   | EUR      | Central Cafe | 2026-07-12 | food     |
  When user 123456789 sends the delete command "/delete 20260712-1"
  Then the delete reply should be "🗑️ Deleted expense 20260712-1: Central Cafe — 3.50 EUR — 2026-07-12"
  And expense 20260712-1 should no longer be recorded
```

  Invalid-command table gains `| /delete 20261340-1 |` and `| /delete #20260712-1 |`, each replying `Usage: /delete <key>`.
- [ ] `features/telegram_bot.feature` and `features/correction.feature`: `containing "Expense #1"` → `containing "Expense 20260715-1"` (photo scenario, date 2026-07-15) and `containing "Expense 20260712-1"` (free-text scenario, date 2026-07-12).
- [ ] `features/environment.py`: keep the `DELETE FROM expenses` fixture wipe (it is what makes key numbering reproducible per scenario) and add a one-line comment saying the "no `DELETE FROM expenses`" invariant is stated over `src/`.
- [ ] **Green gate** — run and paste both:

```bash
uv run behave
uv run pytest -o addopts=""
```

  Both must be green. If they are not, stop here — do not proceed with S2–S4 on a red cutover.
- [ ] Commit: `features: delete/recording path speaks user-scoped keys`

---

## Task 8 — S2: listings render keys

**Files** — Modify `features/list.feature`, `features/steps/list_steps.py`

**Interfaces** — Consumes Task 6's `_format_month_view`. Produces: every row of `/list` carries its key; navigation, month headers, totals, and buttons untouched.

- [ ] Re-express the `the message lists expense "…"` assertions: `"#1"` → `"#20260710-1"`, `"#2"` → `"#20260710-2"`, and the multi-user scenario asserts each person sees their **own** `-1` on the same date.
- [ ] `features/steps/list_steps.py`: the Given-table `id` column is dropped (fixtures seed `id=None`); `step_message_lists_expense_id` takes the key token as `str`.
- [ ] Add `the listing shows a key for every expense row` — count rows vs keys in the message text.
- [ ] `uv run behave` green; commit `features(list): rows carry their person-scoped key`.

---

## Task 9 — S3: CSV leads with the key

**Files** — Modify `src/expense_report/domain/csv_generator.py`, `tests/domain/test_csv_generator.py`, `tests/application/test_expense_queries.py`, `features/report.feature`, `features/cli_extraction.feature`, `features/steps/report_steps.py`, `features/steps/cli_steps.py`

**Interfaces** — Produces `generate_csv(expenses: list[Expense]) -> str` with header exactly `user_key,date,merchant,category,amount,currency`; `user_key is None` renders as the **empty string**. Reply/attachment plumbing untouched.

- [ ] Red: `test_header_line` expects the new header; `test_single_expense` / `test_multiple_expenses` / `test_category_none_uses_empty_string` gain the leading key; add `test_null_user_key_renders_empty_cell` (`2026-07-15,Shop,,10.00,EUR` shape — leading empty field).
- [ ] Red: `tests/application/test_expense_queries.py::test_generates_csv_for_given_period` and `test_empty_period_returns_header_only` expect the new header.
- [ ] Green: prepend the column in `csv_generator` (still zero framework/IO imports).
- [ ] `features/report.feature` + `features/cli_extraction.feature`: CSV assertions lead with `user_key`; report reply text untouched.
- [ ] `uvx ruff format && uvx ruff check && uvx ty check && uv run pytest -o addopts=""` + `uv run behave` green; commit `domain(csv)+features: CSV leads with user_key`.

---

## Task 10 — S4: anti-spill invariant through the bot

**Files** — Modify `features/delete.feature`, `features/steps/delete_steps.py`

**Interfaces** — Consumes Tasks 6–7. Produces three new scenarios, each end-to-end through the Telegram adapter:

- [ ] `Scenario: Two people share a key text` — user A and user B both record on `2026-07-18`; both listings show `#20260718-1`; `user B sends the delete command "/delete 20260718-1"` deletes **B's** expense only; `Then expense 20260718-1 should still be recorded for user 123456789`.
- [ ] `Scenario: A person cannot address another person's expense` — B types A's key; reply is exactly `Expense 20260718-1 was not found.`; A's expense still recorded.
- [ ] `Scenario: A freed key number is not reused` — A records two on one date, deletes `-2`, records a third; the listing shows `-1` and `-3`, never a second `-2`.
- [ ] `uv run behave` green; commit `features(delete): anti-spill invariants pinned end-to-end`.

---

## Task 11 — CLI stays coherent with the bot (§6.8)

**Files** — Modify `src/expense_report/adapters/inbound/cli_extraction.py`, `tests/adapters/inbound/test_cli_extraction.py`, `features/cli_extraction.feature`

**Interfaces** — Produces: `expense-extract` stdout presents the key and **never** the internal id. Today it prints the whole `Expense` repr (`print(f"\nSaved expense: {outcome.expense}")`), which leaks `id`.

- [ ] Red: capture stdout in `tests/adapters/inbound/test_cli_extraction.py` — assert `"id=None"` / the internal id absent, and the key present.
- [ ] Green — builder-changeable rendering (my call), mirroring the delete reply:

```python
expense = outcome.expense
print(
    f"\nSaved expense: {expense.user_key} — {expense.merchant} — {expense.amount:.2f} {expense.currency} — {expense.date}"
)
```

- [ ] `features/cli_extraction.feature` asserts the same line.
- [ ] Full suite + behave green; commit `adapter(in/cli): expense-extract presents the key`.

---

## Task 12 — Final gate: invariants, docs, evidence map

- [ ] Run the seven invariant greps from the table above; paste each command and its (empty/expected) output.
- [ ] Run and paste in full:

```bash
uvx ruff format && uvx ruff check && uvx ty check && uv run pytest -o addopts=""
uv run behave
```

- [ ] Paste the `scripts/upgrade-probe` `PASS` line (legacy rows preserved through the rebuild, `user_key` added, changesets = 3).
- [ ] Write the expectations→evidence map in the conversation: every `E*` id from `docs/expectations/user-scoped-expense-keys.md` → the executed command/test that proves it. No narration, no "tests pass".
- [ ] Update `AGENTS.md` "Key Decisions" pointer line if it enumerates ADRs; confirm `uv run pre-commit` blocked nothing and that no secret was committed.
- [ ] Commit: `chore: user-scoped expense keys — full gate green`

---

## Self-review before execution

Re-read the spec and check the plan against it. Confirm each of these appears in a task, or fix the plan:

- Key prefix = **expense date**, not insertion date (Task 4 test `test_save_key_prefix_follows_expense_date_not_created_at`).
- Keys unique for good, soft-deleted counted, no reuse (Tasks 4, 7, 10).
- `YYYYMMDD-n`, no zero-padding; `n` from 1 (Tasks 4, 7, 8).
- `UNIQUE(user_id, user_key)` backstop fires (Task 3 schema, Task 4 IntegrityError test).
- No `INSERT OR REPLACE` anywhere (Task 4).
- `delete_by_id` fully dropped, nothing keeps both (Tasks 4, 5, and grep #3).
- `get_by_id` stays internal/tests-only, never called from `adapters/inbound` (grep #2).
- Malformed vs well-formed-but-absent are different outcomes (Task 6 tests + delete.feature).
- Calendar validation of the 8 digits (`20261340-1` → usage) (Task 6).
- CSV header exactly `user_key,date,merchant,category,amount,currency`; NULL → empty (Task 9).
- Confirmation drops `#`; listing keeps `#` (Tasks 6, 8).
- Unbackfilled row renders `-` and is not addressable (Task 6 test).
- Logging carries both identities at the adapter boundary (Tasks 4, 6).
- ADR 0016 + the one-line dangling-ADR-0010 notes (Task 1).
- Four changeset-count assertions updated (Task 3).
- `domain/` gains no import (grep #6).
- Backfill is **not** in this plan (spec §8) — flag if anything here starts assigning keys to pre-existing rows.

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-10-10-user-scoped-expense-keys.md`. Two ways to run it:

1. **Subagent-driven (AGENTS.md default)** — one `worker` per task in spawn mode, each brief self-contained (task section + acceptance criteria + the verification command); `reviewer` audits each diff; `oracle` before Task 3/4 if the rebuild-changeset shape is questioned. Produce a `handoff.md` first so the spawn-mode children carry the decisions above.
2. **Inline** — execute task-by-task in this session, red→green→commit, pasting evidence at every step.

Which one?
