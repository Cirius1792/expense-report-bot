# ADR 0018: the soft-delete UPDATE shares the SELECT predicate

**Status:** accepted (2026-10-11)

`delete_by_user_key` finds the row with
`SELECT * FROM expenses WHERE user_id = ? AND user_key = ? AND deleted_at IS NULL`
and then stamps it. The UPDATE originally omitted `AND deleted_at IS NULL`, so the
write addressed a wider set than the read. It was a no-op while
`UNIQUE(user_id, user_key)` (changeset `003-add-user-key`) held, which is why the
plan's SQL shipped unchanged — but the correctness of the write was then a property
of the *index*, not of the statement.

**Decision:** the UPDATE carries the same predicate as the SELECT:
`UPDATE expenses SET deleted_at = ? WHERE user_id = ? AND user_key = ? AND deleted_at IS NULL`.

**Why.** The index is not a guarantee the adapter can rely on. Changeset `003-add-user-key`
guards itself with a precondition that uses `onFail="MARK_RAN"`, so a schema that
already has `user_key` but is missing the index runs nothing and is still marked
applied; ADR 0016 sanctions table-rebuild changesets, which are the kind of change
that can forget to re-create an index. In that state the wider
UPDATE silently re-stamps an already-deleted row sharing the key — invisible to the
user, so a silent failure mode.

**Consequences.**
- The write is narrowed to live rows: it can no longer re-stamp a row that already
  carries `deleted_at`. It is *not* yet keyed to the exact row the read returned —
  under the same drift state, two **live** rows sharing `(user_id, user_key)` would
  both be stamped. Closing that fully means adding `AND id = ?` to the UPDATE, using
  the id the SELECT already resolved; deliberately left open (see Open question).
- No behaviour change on a correctly-migrated database (rowcount stays 1), so no
  existing test changes.
- Pinned by `TestDeleteUnderMissingUniqueness` in
  `tests/adapters/out/test_sqlite_repository.py`, which runs on the snapshot schema
  with the `CREATE UNIQUE INDEX` line removed — the drift state, not the healthy one.
- The INSERT key counter still *includes* soft-deleted rows (ADR 0011); that is
  unchanged and deliberate — keys are never handed out twice.

**Honest limits.** The drift state is not reachable through the changelog as it
stands: changeset `003-add-user-key` creates the index on an empty `expenses_new`
before any `INSERT`, so it cannot fail on existing data, and no later rebuild
changeset exists yet. The fixture is a hand-mutation of the schema snapshot — it
pins the contract for a future rebuild that forgets the index, it does not
reproduce a bug seen in the field.
