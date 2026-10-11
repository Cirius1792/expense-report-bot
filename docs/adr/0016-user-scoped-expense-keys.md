# ADR 0016: User-scoped Expense Keys

**Date:** 2026-10-10
**Status:** Accepted
**Issue:** #16
**Depends on:** ADR 0011 (logical deletion) — already merged
**Expectations:** `docs/expectations/user-scoped-expense-keys.md` (E1–E14)

## Context

Expenses are stored under one system-wide `INTEGER PRIMARY KEY AUTOINCREMENT` id, and that
id is printed to users: `/list`, the recording confirmation, the delete button payload, and
the delete replies. Because the sequence is global, the id a user sees on their **own first
Expense** tells them how many Expenses exist across every user, and repeated insert/delete
cycles let them watch global write activity over time. That is an unintended information
spill — nothing in the product wants to publish it.

The fix is to stop showing storage identity and show a **per-person key** instead. The key's
only job is to be a name a person can read off a listing and type back into `/delete`. It
must carry no information about anyone else.

Note: ADR 0011 and `docs/expectations/logical-deletion.md` both cite "ADR 0010 (user-scoped
ids)" — a file that was never written. This ADR is that decision; nothing is renumbered.

## Decision

- **Per-person key `YYYYMMDD-n`.** The prefix is the **Expense's own `date`**, not the
  insertion date — coherent with the application's existing bucketing
  (`get_by_user_and_month`, `get_months_with_expenses`, `get_total_by_user_and_year` and the
  CSV all filter on `date`; `created_at` is used only for `ORDER BY created_at DESC`).
  `n` starts at `1`, no zero-padding; the compact shape was chosen over `2026-07-18-3` so the
  typed form has fewer separators on a phone.
- **Keys are unique for good, soft-deleted rows included.** A person who deleted
  `20260718-3` never gets `3` handed to a new Expense again. This is the rule ADR 0011
  already committed to, so the merged logical-deletion work is not revisited.
- **The key is computed inside the INSERT**, in a single statement that holds the write lock
  for the whole key count: the key text is built from the row's own `date` parameter plus a
  `COUNT` subquery over the table. No SELECT-then-INSERT computes a key outside the write
  statement.
- **`UNIQUE(user_id, user_key)` is the backstop**, enforced by changeset `003-add-user-key`
  (a table-rebuild changeset — SQLite cannot add a constraint by `ALTER TABLE`; ADR 0013
  sanctions rebuild changesets for exactly this). Multiple `NULL` keys coexist under it, so
  deferring backfill and enforcing the constraint do not conflict.
- **The global integer id stays the storage join target.** Nothing about how Expenses are
  stored, listed, summed, or soft-deleted changes. It is never exposed and never accepted
  after the cutover: `/delete` and the delete button take only the key, from the moment of
  cutover, with no transition window.
- **Port rename, no transitional surface:** `ExpenseRepositoryPort.delete_by_id` is dropped
  when `delete_by_user_key(user_id, user_key)` arrives; nothing keeps both. `get_by_id`
  stays as-is, tests-only and internal-only.
- **No `INSERT OR REPLACE` anywhere.** Once the UNIQUE index exists, `REPLACE` can silently
  discard an unrelated Expense on a key clash; the explicit-id branch of `save()` becomes a
  plain `INSERT` carrying a `TODO` comment marking it as test-only scaffolding whose
  replacement is separate later work.
- **User-facing forms:** confirmation `Expense 20260718-1` (no `#`), listing row `#20260718-1`
  (the `#` marker kept so a row still reads as addressable), button payload `delete:20260718-1`,
  usage `Usage: /delete <key>`, miss `Expense 20260718-3 was not found.`, hit
  `🗑️ Deleted expense 20260718-3: <merchant> — <amount> <currency> — <date>`, CSV header
  `user_key,date,merchant,category,amount,currency`. `/delete` takes the exact key, no leading
  `#`. Validation is `^\d{8}-\d+$` plus a real-calendar check on the 8 digits, so
  `20261340-1` is malformed → usage.
- **The listing is the only channel through which a key is discoverable** — a person reads it
  off `/list` (and off the recording confirmation and its delete button) and types it into
  `/delete`.
- **The CLI stays coherent with the bot:** `expense-extract` presents the key, not the
  internal id (its stdout today prints the whole `Expense` repr, which leaks it).
- **Logging:** internal id and key are both logged at the adapter boundary — logs are the
  audit channel, they are not user-facing.

## Consequences

- A person's key reveals only facts about their own Expenses: how many of their own Expenses
  exist for that one Expense date, and that their own deletions happened.
- Backfill for databases that already hold Expenses **ships alongside** this work — nothing
  is released in the state where new Expenses have keys and older ones do not. The interim
  state (a row whose key renders as `-` and is not addressable by `/delete`) therefore exists
  only inside the repository and in tests, never in a user's database, which is what makes
  the `-` a rendering detail rather than a user-visible compromise. Hiding such a row outright
  was rejected: `get_total_by_user_and_year` would still count it, making the listing disagree
  with the month total.
- ADR 0011's key-count rule is honoured: the key-count INSERT counts soft-deleted rows, so
  keys remain permanently unique per `(user_id, user_key)`.
- The cutover cannot land green in the middle: `delete_by_id` is a port member, so renaming
  it breaks the delete feature and adapter tests the moment groundwork lands. Slice shape A
  was chosen — groundwork lands knowingly red and the green gate is enforced when the adapter
  and the features switch together.
- Stale expectation files (`delete-expenses.md`, `expense-query-policy.md`,
  `telegram-command-hints.md`) are rewritten to this behaviour.
- `tests/migrations/test_changelog.py` and `scripts/upgrade-probe/verify.py` pin the applied
  changeset count and move from 2 to 3 with `003-add-user-key`.

## Out of scope

- Backfill/migration of keys for existing Expenses (separate design, ships alongside).
- Restoring soft-deleted Expenses (ADR 0011 already defers this).
- Extraction, Correction, period discovery, totals, and listing *content* beyond the
  identifier column.
- Multi-container or concurrent-writer safety beyond the existing single-container model.
- Replacing the explicit-id branch of `save()` with a non-second-writer seeding mechanism.
