# User-scoped Expense Keys — design

**Date:** 2026-10-10
**Status:** Builder-checked on 2026-10-10 — six questions from a fresh builder were sorted into the piles below; the six that only the maintainer can answer are listed under "Answers needed" and block approval.
**Issue:** #16
**Depends on:** ADR 0011 (logical deletion) — already merged

---

## 1. Intent and the why

Expenses are today stored under one system-wide `INTEGER PRIMARY KEY AUTOINCREMENT`
id and that id is printed to users (`/list`, the recording confirmation, the delete
button, the delete replies). Because the sequence is global, the id a user sees on
their **own first expense** tells them how many expenses exist across every user, and
repeated insert/delete cycles let them watch global write activity over time. That is
an unintended information spill — nothing in the product wants to publish it.

The fix is to stop showing the storage identity and show a **per-person key** instead.
The key's only job is to be a name a person can read off a listing and type back into
`/delete`. It must carry no information about anyone else.

## 2. Goals

- No user-facing output, message, button, or CSV column contains the global id.
- No user-facing input accepts the global id after the cutover.
- A person's key reveals only facts about that person's own Expenses: how many of their
  own Expenses exist for that one expense date, and that their own deletions happened.
- The global id remains the storage join target: nothing about how Expenses are stored,
  listed, summed, or soft-deleted changes.

## 3. Non-goals

- Backfilling keys for Expenses that already exist in a database. Deferred, see §8.
- Restoring soft-deleted Expenses (ADR 0011 already defers this).
- Touching Extraction, Correction, period discovery, totals, or listing *content*
  beyond the identifier column.
- Multi-container or concurrent-writer safety beyond what the single-container model
  already assumes (`check_same_thread=False`, "thread safety is the caller's
  responsibility").

## 4. Anti-goals — what makes this a failure even if it compiles

- Any key that repeats within a person's own records.
- Any code path where a person can address another person's Expense by typing a key.
- Any key derived from wall-clock insert time (it would not line up with the listing
  the key is read from).
- A SELECT-then-INSERT that computes the key outside the write statement.
- No `INSERT OR REPLACE` remains — once the UNIQUE index exists, `REPLACE` can silently
  discard an unrelated Expense on a key clash.
- The global id appearing in a message, a listing line, a CSV row, or button payload.
- An `include_deleted` opt-in, or any read path that starts showing soft-deleted rows.
- Framework or IO imports reaching `src/expense_report/domain/`.

## 5. Constraints

| Constraint | Why |
|---|---|
| `domain/` stays framework-free | hexagonal boundary, AGENTS.md |
| `Expense` is a frozen dataclass | existing convention |
| Ports are Protocols; adapters implement them; application owns use cases | hexagonal shape, ADR 0001, ADR 0006 |
| Every signature typed; no `Any`, no bare `dict` | AGENTS.md |
| Schema changes go through the Liquibase changelog, never in-code DDL | ADR 0013 |
| One INSERT statement holds the write lock for the whole statement | atomicity of the key count |

## 6. Decisions — made by the maintainer

1. **Expense date is the key prefix**, not insertion date. Settled in conversation on
   2026-10-10 and coherent with the application's existing bucketing: `get_by_user_and_month`,
   `get_months_with_expenses`, `get_total_by_user_and_year` and the CSV all filter on the
   `date` column; `created_at` is used only for `ORDER BY created_at DESC`. A receipt
   submitted on 2026-07-20 but dated 2026-06-30 lives in the June listing, June totals,
   June CSV — and gets a `20260630-n` key.
2. **Keys are unique for good, soft-deleted rows included.** The maintainer stepped back
   on this and asked for permanent uniqueness rather than uniqueness-among-live-rows. A
   person who deleted `20260718-3` never gets `3` handed to a new Expense again. This is
   the rule ADR 0011 already committed to, so the merged logical-deletion work is not
   revisited.
3. **Key shape is compact: `YYYYMMDD-n`** — e.g. `20260718-3`, `n` starting at 1, no
   zero-padding. Chosen by the maintainer over the hyphenated `2026-07-18-3` draft so the
   typed form has fewer separators on a phone.
4. **The CSV gains the key as a column.** Also the maintainer's.
5. **Migration/backfill is a separate, later piece of work.** The maintainer's.
6. **Carried over from issue #16 (maintainer, recorded there):** the global id stays the
   primary key and is never exposed or accepted; `/delete` and the delete button accept
   only the key from the moment of cutover, with no transition window; the key is
   computed inside the INSERT; `UNIQUE(user_id, user_key)` is the backstop; malformed
   keys and well-formed-but-absent keys are different outcomes; the listing never shows
   the global id.
7. **Nobody ever stores an Expense with a caller-chosen id.** The maintainer's, 2026-10-10:
   the explicit-id branch of `save()` is test scaffolding only, so it becomes a plain
   `INSERT` — `INSERT OR REPLACE` would, once the UNIQUE index exists, let a key clash
   silently discard an unrelated Expense. The branch carries a `TODO` comment marking it as
   test-only scaffolding whose replacement (a way to seed Expenses that is not a second
   writer) is a separate later piece of work, deliberately not solved here.
8. **The CLI must stay coherent with the bot.** The maintainer's, 2026-10-10: the inbound
   adapters are two implementations of the same driving ports and must present the same
   behaviour, so `expense-extract` stops printing the internal id and presents the key.
9. **`/delete` takes the exact key, no leading `#`.** The maintainer's, 2026-10-10.
10. **Port rename, no transitional surface.** The maintainer's, 2026-10-10: `delete_by_id`
   is dropped when `delete_by_user_key` arrives, nothing keeps both. This selects slice
   shape A: S0 lands knowingly red and the green gate is enforced at the end of S1.
11. **The stale expectation files are rewritten to this behaviour.** The maintainer's,
   2026-10-10.
12. **The listing is the only channel through which a key is discoverable.** The maintainer's,
   2026-10-10: a person reads the key off `/list` (and off the recording confirmation and
   its delete button) and types it into `/delete`. Nothing else in the product prints a
   key for a Expense the person did not just create, so the listing slice carries the
   requirement "every row carries its key".

## 7. My calls — a builder may change any of these without changing the product

| Call | Decision |
|---|---|
| Field name | `user_key: str \| None` on `Expense`; `None` means "not persisted / pre-backfill row" |
| Port renames | `ExpenseRepositoryPort.delete_by_id(user_id, expense_id: int)` → `delete_by_user_key(user_id, user_key: str)`; `ExpenseQueryPort.delete_expense(user_id, key: str)`; `get_by_id(expense_id: int)` stays as-is, tests-only, internal-only |
| Schema shape | new changeset `003-add-user-key`: SQLite cannot add a constraint by `ALTER TABLE`, so it is a table-rebuild changeset (`CREATE expenses_new` with `user_key TEXT` + `UNIQUE(user_id, user_key)`, copy old rows across keeping their `NULL` key, drop, rename). ADR 0013 already sanctions rebuild changesets for exactly this, and multiple `NULL` keys coexist under a UNIQUE index (proven, §9), so deferring backfill and enforcing the constraint do not conflict |
| Listing line | `#{e.user_key:<10}` → `#20260718-1`; the `#` marker is kept so a listing row still reads as an addressable thing; alignment is unchanged up to the 10th Expense of one date for one person. A row whose key has not been backfilled yet renders `-` in that cell rather than blanks, and is not addressable by `/delete` — there is no key to type |
| Reply wording | usage: `Usage: /delete <key>`; miss: `Expense 20260718-3 was not found.`; hit: `🗑️ Deleted expense 20260718-3: <merchant> — <amount> <currency> — <date>`. `#` is dropped in the typed/echoed forms because `#20260718-3` is not what the person types. Behave asserts these strings verbatim, so they are pinned in the tests and listed for review |
| Key validation | `^\d{8}-\d+$` plus a real-calendar check on the 8 digits; a well-formed-but-not-a-date key (`20261340-1`) is reported as malformed, matching the existing "invalid format → usage" family |
| CSV column position | `user_key` as the leading column: `user_key,date,merchant,category,amount,currency`; `NULL` key renders as empty string |
| Confirmation text | `Expense 20260718-1` (drop `#`), matching the delete reply |
| Logging | internal id and key both logged at the adapter boundary — logs are the audit channel, they are not user-facing |
| ADR | new `docs/adr/0016-user-scoped-expense-keys.md`; ADR 0011 and `docs/expectations/logical-deletion.md` both cite "ADR 0010 (user-scoped ids)", a file that was never written — a one-line note is added there pointing at 0016 by title, no renumbering |

## 8. Deferred — but not shippable apart

**Backfill and migration strategy** for databases that already hold Expenses is a
separate piece of work with its own design; the rebuild changeset above is chosen so it
can be run again as a backfill without touching this slice's code. The maintainer's,
2026-10-10: **the two ship together** — nothing is released in the state where new
Expenses have keys and older ones do not. The interim state therefore exists only inside
the repository and in tests, never in a user's database, which is what makes the
placeholder in §14 a rendering detail rather than a user-visible compromise.

## 9. Verified by execution (throwaway probe, `/tmp/keyprobe.db`, not product code)

Schema used for the probe: changeSet `001-create-expenses` columns + `user_key TEXT`, plus
`CREATE UNIQUE INDEX uk ON expenses (user_id, user_key)`.

Single INSERT that assigns both identities in one statement — the key text is built from
the row's own `date` parameter and a COUNT subquery over the table:

```sql
INSERT INTO expenses
  (amount, currency, merchant, date, category, user_id, receipt_photo_id, created_at, deleted_at, user_key)
VALUES
  (?, ?, ?, ?, ?, ?, ?, ?, ?,
   (substr(?,1,4) || substr(?,6,2) || substr(?,9,2) || '-' ||
    ((SELECT count(id) FROM expenses WHERE user_id = ? AND date = ?) + 1)))
```

Executed results:

```
user 1, date 2026-07-18, 2 inserts   -> keys 20260718-1, 20260718-2   (id 1, 2)
user 2, date 2026-07-18, 1 insert    -> key 20260718-1                (id 3) — same text, different owner
user 1, date 2026-06-30, 1 insert    -> key 20260630-1                (id 4) — expense date, not insert date
soft-delete user 1 id 2, then insert -> key 20260718-3                (id 5) — freed slot NOT reused
forced duplicate (user_id, user_key) -> IntegrityError: UNIQUE constraint failed: expenses.user_id, expenses.user_key
two rows with NULL user_key side by side -> allowed, count 2
```

Reading the key back after the INSERT (to return the saved `Expense`) is a second
statement and is not a race: the value was fixed inside the write statement above.

## 10. Affected layers

| Layer | Change |
|---|---|
| `domain/models.py` | `Expense` gains `user_key: str \| None`. No new imports. |
| `domain/csv_generator.py` | header gains leading `user_key`; `None` renders empty. |
| `ports/repository.py` | `save` returns the Expense with its assigned key; `delete_by_user_key(user_id, user_key: str)` replaces `delete_by_id`; docstrings state that deleted rows are counted by the key and excluded from reads. |
| `ports/expense_queries.py` | `delete_expense(user_id, key: str)`. |
| `application/expense_queries.py` | delegates; no key logic — validation lives in the inbound adapter, lookup lives in the driven adapter. |
| `application/expense_recording.py` | unchanged (`_build_expense` keeps `user_key=None`). |
| `adapters/out/sqlite_repository.py` | single-statement INSERT above; `delete_by_user_key`; every read unchanged in shape. |
| `adapters/inbound/telegram_bot.py` | listing line, confirmation text, `delete:<key>` callback payload, `/delete` parsing + validation, help/usage strings. |
| `adapters/inbound/cli_extraction.py` | the `expense-extract` entry point prints the whole `Expense` repr (`print(f"\nSaved expense: {outcome.expense}")`), which today leaks the global id and would leak the key — scope is an open item, see "Answers needed". |
| `db/changelog/db.changelog.xml` | changeset `003-add-user-key`. |
| `features/*.feature`, `features/steps/*` | listing/delete/report scenarios re-expressed against keys; `seed_expense` already goes through `repository.save`, so seeded rows get real keys for free. |

## 11. Acceptance criteria

### Happy path

- Recording a Receipt or a free-text Expense replies with its key.
- `/list` shows the key for every Expense in the month; nothing else identifies it.
- The delete button on a confirmation carries `delete:20260718-1`.
- `/delete 20260718-3` soft-deletes that Expense and echoes the key.
- Two Expenses on the same expense date for one person get `-1` and `-2` in insert order.
- The CSV for a month leads with the key.

### Edge cases

- Expense submitted today, dated last month: key prefix is the expense date; it appears
  in the listing and CSV of the month that prefix names.
- `/delete` with no argument, a non-key token, or an impossible date: usage reply,
  nothing deleted.
- `/delete` with a well-formed key that person does not own, or that is already
  deleted: `Expense <key> was not found.`
- A person deleting their own last Expense for a date: the next Expense for that date
  does not reuse the freed number.
- Two people on the same expense date: both get `-1`.

### Must NOT happen

- No global id in any user-facing message, listing line, CSV row, or button payload.
- No old global integer resolves through `/delete` or a delete button after cutover.
- No read path shows soft-deleted rows; no `include_deleted` surface is added.
- `DELETE FROM expenses` still absent from the codebase.
- Domain layer gains no framework/IO import.
- No SELECT-then-INSERT key computation.

## 12. Vertical slices, each end-to-end testable

**The port rename and the adapter switch cannot both land green.** `delete_by_id` is a
port member, so renaming it breaks `features/delete.feature`, the delete-button fixture,
and four adapter tests the moment S0 lands. There is no slice boundary that keeps the
gate green in the middle of the cutover. Two shapes, and the choice is the maintainer's
(see "Answers needed", item 1):

- **A — one cutover branch:** S0 groundwork lands knowingly red; the gate is enforced at
  the end of S1, when the adapter and the features switch together. Fewer commits, an
  intermediate state that cannot ship.
- **B — transitional surface:** `delete_by_user_key` is *added* next to `delete_by_id`, the
  adapter switches to the key, and a later slice removes the now-dead port member. Every
  slice can end green, at the cost of a port holding two delete operations for one slice
  and a wider file set.

| Slice | What ships | End-to-end proof |
|---|---|---|
| **S0 — groundwork** | `user_key` on `Expense`; changeset `003-add-user-key`; single-statement INSERT; `delete_by_user_key`; the old member handled per shape A or B | adapter pytest on a real migrated database (keys per owner, per date, no reuse after soft-delete, UNIQUE backstop firing, reads still filtering deleted rows) — a person cannot reach it yet |
| **S1 — cutover on the recording/delete path** | confirmation shows the key; button payload carries it; `/delete <key>`; usage and miss wording; global ids stop resolving | `features/delete.feature`, `features/telegram_bot.feature`, `features/correction.feature` rewritten to type keys |
| **S2 — listings render keys** | listing line format; navigation and totals untouched | `features/list.feature` |
| **S3 — CSV leads with the key** | `csv_generator` header and column; report reply untouched | `features/report.feature` + `tests/domain/test_csv_generator.py` |
| **S4 — anti-spill invariant** | cross-user key collision; other-person miss wording; soft-delete-then-reinsert non-reuse asserted through the bot | new scenarios in `features/delete.feature` |

### Fixture seeding and schema bookkeeping that the green gate depends on

- `features/steps/common_steps.py::seed_expense` seeds with `id=None` through
  `repository.save`, so seeded rows acquire genuine keys — fixtures must not hand-write
  keys.
- `features/steps/delete_steps.py:99` (the delete-button fixture) builds
  `Expense(id=int(row["id"]), ...)`, which takes the explicit-id branch of `save()` and
  therefore **no key** — those rows would be unaddressable. Settled: that fixture seeds
  with `id=None` like the bot does, its feature table drops the `id` column and names the
  expense dates that drive the key, and the `Then` steps that call `repository.get_by_id(int)`
  are re-expressed against the key.
- `tests/migrations/test_changelog.py` pins the applied-changeset count at `2` in three
  tests, and `scripts/upgrade-probe/verify.py` asserts 2 changesets. Adding `003-add-user-key`
  breaks all four; they are part of S0's file set.
- `tests/_schema/expenses.sql` is a digest-guarded generated artifact regenerated with
  `uv run python -m tests._schema --write` (needs Docker). It must be regenerated after the
  changeset lands, and its guard is what makes the hermetic unit fixtures see the new column.
- `features/environment.py` wipes rows per scenario with `DELETE FROM expenses`; that is
  fixture infrastructure, not product code, and it is what makes key numbering reproducible.
  The "no `DELETE FROM expenses`" invariant is stated over `src/` for this reason.
- Stale expectation files contradict this feature and are rewritten in the slice that
  changes the behavior: `docs/expectations/delete-expenses.md` (asserts `#<id>`, hard
  deletion, no CSV id column), `expense-query-policy.md` (pins `delete_by_id`),
  `telegram-command-hints.md` (pins `/delete <expense_id>`), plus a new
  `docs/expectations/user-scoped-expense-keys.md` written before implementation per AGENTS.md.

## 13. Answered during grilling, 2026-10-10

Folded into §6 as items 7-11: slice shape (rename, no transitional surface), the explicit-id
branch of `save()`, the CLI's scope, the `#` in front of a typed key, and the stale
expectation files.

## 14. Settled as my call, not the maintainer's

A row whose key has not been backfilled yet renders `-` where its identifier belongs and
is not addressable by `/delete`, since there is no key to type. This state is reachable in
tests and inside the repository only: §8 records that the backfill ships alongside this
feature, so no user's database is ever in it. Hiding such a row outright was rejected —
`get_total_by_user_and_year` would still count it, making the listing disagree with the
month total.

Also settled as my call, not the maintainer's: reply wording (§7), CSV column position,
calendar validation of the 8 digits, logging, ADR numbering.

Answered by the builder check but settled as my call rather than the maintainer's: reply
wording (§7), CSV column position, calendar validation of the 8 digits, logging, ADR
numbering.
