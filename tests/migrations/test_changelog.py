"""Executable acceptance tests for the Liquibase schema changelog."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests._schema import apply_snapshot, dump_application_schema, migrate_with_liquibase

pytestmark = pytest.mark.integration

# The schema shipped by ADR 0011 (deleted_at present) but before ADR 0016 added
# user_key. A deployed database looks like this, so it is the realistic starting
# point for the backfill.
_PRE_USER_KEY_SCHEMA = """
    CREATE TABLE expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount TEXT NOT NULL,
        currency TEXT NOT NULL,
        merchant TEXT NOT NULL,
        date TEXT NOT NULL,
        category TEXT,
        user_id INTEGER NOT NULL,
        receipt_photo_id TEXT,
        created_at TEXT NOT NULL,
        deleted_at TEXT
    )
"""


def _seed_pre_user_key_expenses(
    db: Path, rows: list[tuple[str, str, str, str, int, str, str | None]]
) -> None:
    """Seed a pre-user_key database with (amount, currency, merchant, date, user_id,
    created_at, deleted_at) rows in insertion order."""
    with sqlite3.connect(db) as connection:
        connection.execute(_PRE_USER_KEY_SCHEMA)
        connection.executemany(
            "INSERT INTO expenses "
            "(amount, currency, merchant, date, user_id, created_at, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()


def test_fresh_database_gets_schema_and_tracking_tables(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        columns = {row[1] for row in connection.execute("PRAGMA table_info(expenses)")}
    # Liquibase creates tracking tables in uppercase on SQLite.
    tables_lower = {t.lower() for t in tables}
    assert {"expenses", "databasechangelog", "databasechangeloglock"} <= tables_lower
    assert "deleted_at" in columns


def test_reapplying_changelog_is_no_op(tmp_path: Path) -> None:
    db = tmp_path / "repeat.db"
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        before = connection.execute("SELECT COUNT(*) FROM databasechangelog").fetchone()[0]
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        after = connection.execute("SELECT COUNT(*) FROM databasechangelog").fetchone()[0]
    assert after == before == 4


def test_legacy_database_gains_deleted_at_without_losing_rows(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    # Seed a pre-ADR-0011 schema (no deleted_at column) with one row.
    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                merchant TEXT NOT NULL,
                date TEXT NOT NULL,
                category TEXT,
                user_id INTEGER NOT NULL,
                receipt_photo_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO expenses (amount, currency, merchant, date, user_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("10.00", "EUR", "Legacy Shop", "2026-07-01", 42, "2026-07-01T12:00:00"),
        )
        connection.commit()
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        row = connection.execute("SELECT merchant, deleted_at FROM expenses").fetchone()
        assert row == ("Legacy Shop", None)
        assert connection.execute("SELECT COUNT(*) FROM databasechangelog").fetchone()[0] == 4


def test_current_schema_database_is_baselined_without_data_loss(tmp_path: Path) -> None:
    """A DB already matching the current schema is baselined and left untouched."""
    db = tmp_path / "current.db"
    apply_snapshot(db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "INSERT INTO expenses (amount, currency, merchant, date, category, user_id, "
            "receipt_photo_id, created_at, deleted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "9.99",
                "EUR",
                "Baseline Shop",
                "2026-02-03",
                "travel",
                7,
                None,
                "2026-02-03T08:00:00",
                None,
            ),
        )
        connection.commit()
    schema_before = dump_application_schema(db)

    # Pre-Liquibase database: current schema and user data, no tracking tables.
    migrate_with_liquibase(db)

    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT amount, merchant FROM expenses").fetchall() == [
            ("9.99", "Baseline Shop")
        ]
        assert connection.execute("SELECT COUNT(*) FROM databasechangelog").fetchone()[0] == 4
    assert dump_application_schema(db) == schema_before


def test_backfill_assigns_dense_keys_in_insertion_order(tmp_path: Path) -> None:
    db = tmp_path / "backfill.db"
    _seed_pre_user_key_expenses(
        db,
        [
            ("1.00", "EUR", "A", "2026-07-18", 1, "2026-07-18T09:00:00", None),
            ("2.00", "EUR", "B", "2026-07-18", 1, "2026-07-18T10:00:00", None),
            ("3.00", "EUR", "C", "2026-07-18", 2, "2026-07-18T11:00:00", None),
            ("4.00", "EUR", "D", "2026-06-30", 1, "2026-06-30T09:00:00", None),
            ("5.00", "EUR", "E", "2026-07-18", 1, "2026-07-18T12:00:00", None),
        ],
    )
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        keys = dict(connection.execute("SELECT id, user_key FROM expenses").fetchall())
        amounts = dict(connection.execute("SELECT id, amount FROM expenses").fetchall())
    assert keys == {
        1: "20260718-1",
        2: "20260718-2",
        3: "20260718-1",  # other user, same date, own series
        4: "20260630-1",  # prefix is the expense date, not the insert date
        5: "20260718-3",
    }
    assert amounts == {
        1: "1.00",
        2: "2.00",
        3: "3.00",
        4: "4.00",
        5: "5.00",
    }
    assert all(key is not None for key in keys.values())


def test_backfill_numbers_soft_deleted_rows_and_preserves_them(tmp_path: Path) -> None:
    db = tmp_path / "softdeleted.db"
    _seed_pre_user_key_expenses(
        db,
        [
            ("1.00", "EUR", "Live1", "2026-07-18", 1, "2026-07-18T09:00:00", None),
            ("2.00", "EUR", "Live2", "2026-07-18", 1, "2026-07-18T10:00:00", None),
            (
                "3.00",
                "EUR",
                "Gone",
                "2026-07-18",
                1,
                "2026-07-18T11:00:00",
                "2026-07-18T12:00:00",
            ),
        ],
    )
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        rows = connection.execute(
            "SELECT id, user_key, deleted_at FROM expenses ORDER BY id"
        ).fetchall()
    # Dense 1..N over every row, soft-deleted included (E10/E16).
    assert rows == [
        (1, "20260718-1", None),
        (2, "20260718-2", None),
        (3, "20260718-3", "2026-07-18T12:00:00"),
    ]


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "idempotent.db"
    _seed_pre_user_key_expenses(
        db,
        [
            ("1.00", "EUR", "A", "2026-07-18", 1, "2026-07-18T09:00:00", None),
            ("2.00", "EUR", "B", "2026-07-18", 1, "2026-07-18T10:00:00", None),
        ],
    )
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        first = connection.execute("SELECT id, user_key FROM expenses ORDER BY id").fetchall()
    migrate_with_liquibase(db)
    with sqlite3.connect(db) as connection:
        second = connection.execute("SELECT id, user_key FROM expenses ORDER BY id").fetchall()
        changesets = connection.execute("SELECT COUNT(*) FROM databasechangelog").fetchone()[0]
    assert second == first == [(1, "20260718-1"), (2, "20260718-2")]
    assert changesets == 4
