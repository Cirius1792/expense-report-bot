# ADR 0017: Schema snapshot emitted in dependency order

**Date:** 2026-10-11
**Status:** Accepted
**Depends on:** ADR 0013 (Liquibase owns the schema), ADR 0014 (Liquibase test strategy)

## Context

`tests/_schema/expenses.sql` is a generated file: `tests/_schema.py::dump_application_schema` walks
`sqlite_master` and emits every application-owned schema object. The snapshot has two jobs
(ADR 0014): the hermetic digest guard fails when the changelog is edited without
regenerating it, and the integration guard fails when it stops matching what Liquibase
actually produces. The second job requires the snapshot to be **re-appliable** —
`apply_snapshot` feeds the text to `executescript` top to bottom.

`sqlite_master` has no meaningful order. Emitted as-is, an index can precede the table it
attaches to, and replay fails with `no such table: expenses`. This became load-bearing when
changeset `003-add-user-key` added `CREATE UNIQUE INDEX uk ON expenses_new (user_id, user_key)`
(ADR 0016): a rebuild changeset introduces a table and an index in the same changeset, so the
snapshot now contains index objects that did not exist before.

## Decision

Order the dump by an explicit two-level key:

```sql
ORDER BY CASE WHEN type = 'table' THEN 0 ELSE 1 END, type, name
```

- **Tables first**, then everything that references them (indexes, views, triggers).
- **Within each level, `type` then `name`** — a total order, so the generated file is
  byte-stable across runs and the digest guard does not churn on re-generation.

This is a *stable* ordering, not a topological sort. SQLite forbids an index on a table that
does not exist, so table-before-dependent is the only layering the schema can actually have;
there is no deeper chain to sort. A real topological sort would read more code for no
additional guarantee.

## Consequences

- Adding a schema object that depends on another schema object is safe without touching this
  ordering rule.
- A schema object that depends on a *view* (SQLite does not allow indexes on views) would need
  a third level; not reachable today.
- The ordering is a property of the **generator**, not of the changelog. Liquibase applies
  changesets in declared order; the snapshot only has to replay.
- Recorded here rather than in ADR 0013/0014 because the decision was surfaced while
  regenerating the snapshot for `003-add-user-key`; the heuristic itself predates that
  changeset.
