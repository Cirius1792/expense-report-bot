# ADR 0018: the soft-delete UPDATE binds to the row the SELECT resolved

**Status:** accepted (2026-10-11)

`delete_by_user_key` finds the row with
`SELECT * FROM expenses WHERE user_id = ? AND user_key = ? AND deleted_at IS NULL`
and then stamps it. The UPDATE originally omitted `AND deleted_at IS NULL`, so the
write addressed a wider set than the read. It was a no-op while
`UNIQUE(user_id, user_key)` (changeset `003-add-user-key`) held, which is why the
plan's SQL shipped unchanged — but correctness of the write was then a property of
the *index*, not of the statement.

**Decision:** the UPDATE keys on the id the SELECT returned:
`UPDATE expenses SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL`.

Ownership scoping stays in the SELECT (`user_id`, `user_key`, `deleted_at IS NULL`);
the write no longer re-derives the target from the key pair. `id` is internal only —
ADR 0016 keeps it as the storage join target and it is never shown or accepted.

**Why.** The index is not a guarantee the adapter can rely on. Changeset `003-add-user-key`
guards itself with a precondition that uses `onFail="MARK_RAN"`, so a schema that
already has `user_key` but is missing the index runs nothing and is still marked
applied; ADR 0016 sanctions table-rebuild changesets, which are the kind of change
that can forget to re-create an index. In that state a key-pair UPDATE silently
re-stamps rows that were never read — invisible to the user, so a silent failure
mode. Two intermediate shapes were considered and rejected:

- keep the key pair and add `AND deleted_at IS NULL` — narrows the mismatch to live
  rows, but two **live** rows sharing the key would still both be stamped.
- key on the id alone without `deleted_at IS NULL` — would let a second delete
  re-stamp a dead row; the clause keeps the write idempotent with the read.

**Consequences.**
- The write provably touches at most the row the read returned; rowcount is 0 or 1.
- No behaviour change on a correctly-migrated database (the UNIQUE index already
  bounds the key pair to one row), so no existing test changes.
- Pinned by `TestDeleteUnderMissingUniqueness` in
  `tests/adapters/out/test_sqlite_repository.py`, which runs on the snapshot schema
  with the `CREATE UNIQUE INDEX` line removed.
- The INSERT key counter still *includes* soft-deleted rows (ADR 0011); unchanged and
  deliberate — keys are never handed out twice.

**Honest limits.** The drift state is not reachable through the changelog as it
stands: changeset `003-add-user-key` creates the index on an empty `expenses_new`
before any `INSERT`, so it cannot fail on existing data, and no later rebuild
changeset exists yet. The fixture is a hand-mutation of the schema snapshot — it
pins the contract for a future rebuild that forgets the index; it does not
reproduce a bug seen in the field.
