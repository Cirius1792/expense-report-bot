# ADR 0020: Backfilling user keys for pre-existing Expenses

**Date:** 2026-07-21
**Status:** Accepted
**Issue:** #16
**Depends on:** ADR 0011 (logical deletion), ADR 0013 (Liquibase schema migrations),
ADR 0016 (user-scoped expense keys)
**Expectations:** `docs/expectations/user-scoped-expense-keys.md` (E15–E17)

## Context

ADR 0016 introduced the user-facing `YYYYMMDD-n` key and changeset
`003-add-user-key`, which rebuilds the `expenses` table and copies every
existing row across with `user_key = NULL`. The Bot is already in production
use, so a deployed database holds Expenses that have no key. Without filling
those NULLs, listing renders `-` and `/delete <key>` cannot address them — the
feature is not shippable to existing users.

The key is *derived*, not stored by the user: `save()` builds it inside the
INSERT statement as `substr(date, …) || '-' || (COUNT(id) + 1)` over
`(user_id, date)`, counting soft-deleted rows (ADR 0011). The backfill must
therefore reproduce the numbering the Bot would have assigned had the feature
always existed, and must leave the count unchanged so the *next* insert cannot
collide.

## Decision

Add changeset **`004-backfill-user-key`** to `db/changelog/db.changelog.xml`,
immediately after `003` (which becomes immutable, per ADR 0013). It runs inside
the same `liquibase update` as the schema rebuild, before any code reads the
database.

- **Numbering is dense and follows insertion order.** For each
  `(user_id, date)`, `ROW_NUMBER() OVER (PARTITION BY user_id, date ORDER BY id)`
  yields `1..N` in ascending internal `id`. This matches the Bot's
  `COUNT(id) + 1` semantics (the `k`-th row ever inserted for that person/date
  gets `k`), so the next insert computes `N + 1` and is always free.
- **The prefix is each row's own `date`**, not `created_at`, consistent with
  ADR 0016 and the application's `date`-based bucketing.
- **Soft-deleted rows are numbered.** No `deleted_at` filter: the count in the
  application includes them, and a freed number is never reused (ADR 0011).
- **Only NULL keys are written** (`WHERE user_key IS NULL`). On a fresh database
  the update matches zero rows; a database that already carries keys is left
  alone. Liquibase's changelog tracking makes re-encounter a no-op.

The migration is pure SQL using a window function (SQLite ≥ 3.25; the bundled
`sqlite-jdbc` driver is 3.50.2.0), so no Java extension is needed.

### Why Liquibase and not a bot startup script

Every entry point that opens the database already runs `liquibase update`
first — `docker-entrypoint.sh`, `main()` (`ensure_database_migrated`), the
`expense-extract` CLI, and the integration fixtures. An application-owned
startup script would be a second migrator racing the first and would split
ownership of schema/data state, contradicting ADR 0013. Liquibase's changelog
tracking also gives the backfill exactly-once semantics for free.

## Consequences

- Existing users' Expenses become addressable by key the moment the Bot starts
  after deploy; the `-` placeholder is reachable only inside tests.
- The generated schema snapshot `tests/_schema/expenses.sql` is data-neutral, so
  its *schema* is unchanged; only its embedded changelog digest changes and it
  must be regenerated.
- The four sites that pin the applied-changeset count (`tests/migrations/
  test_changelog.py` ×3, `scripts/upgrade-probe/verify.py`) move from 3 to 4.
- Backfill behavior is proven by **integration** tests through the real
  Liquibase wrapper (ADR 0014); the hermetic unit suite only guards the snapshot
  digest and the pinned count.

## Alternatives considered

- **Application startup migration in Python**: a second migrator beside
  Liquibase, needing its own exactly-once guard and its own DDL/DML tests.
  Rejected — duplicates a responsibility ADR 0013 already placed with Liquibase.
- **Folding the backfill into changeset `003`**: would edit an already-authored,
  potentially already-applied changeset, violating ADR 0013's immutability rule.
  Rejected in favour of an appended changeset.
- **Correlated `COUNT(*)` subquery instead of a window function**: identical
  result and arguably closer to `save()`'s wording, but quadratic; the window
  function is linear and equally portable on the pinned driver.
- **Numbering `NULL` rows starting after existing keys**: only matters for a
  mixed keyed/NULL database, a state this project cannot reach because `003`
  and `004` apply in one `update` with no writer between them. Rejected as
  speculative complexity.
