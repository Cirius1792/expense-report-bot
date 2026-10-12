"""SQLite implementation of the ExpenseRepositoryPort.

Uses the sqlite3 module with check_same_thread=False for single-container use.
Thread safety is the caller's responsibility.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime
from decimal import Decimal

from expense_report.domain.models import Expense

logger = logging.getLogger(__name__)


class SqliteExpenseRepository:
    """Persists and retrieves Expense records using SQLite.

    Args:
        db_path: Path to a SQLite database file that has already been migrated.
    """

    def __init__(self, db_path: str) -> None:
        logger.info("Initializing SQLite repository at %s", db_path)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def save(self, expense: Expense) -> Expense:
        """Persist an expense record and return it with its assigned user_key.

        The per-person key (`YYYYMMDD-n`, prefixed with the Expense's own date)
        is computed inside this INSERT statement: one statement holds the write
        lock for the whole key count, so no SELECT-then-INSERT window exists
        (ADR 0016). The count includes soft-deleted rows, so a number freed by a
        soft delete is never handed out again.

        If expense.id is None, SQLite assigns the auto-increment integer id.
        If expense.id is set, it is used as-is and the caller's user_key is
        stored as given (the pre-backfill state keeps it NULL).
        """
        if expense.id is not None:
            # TODO: test-only scaffolding — replacing seeding is separate later work
            self._conn.execute(
                """
                INSERT INTO expenses
                    (id, amount, currency, merchant, date, category,
                     user_id, receipt_photo_id, created_at, deleted_at, user_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense.id,
                    str(expense.amount),
                    expense.currency,
                    expense.merchant,
                    expense.date.isoformat(),
                    expense.category,
                    expense.user_id,
                    expense.receipt_photo_id,
                    expense.created_at.isoformat(),
                    expense.deleted_at.isoformat() if expense.deleted_at is not None else None,
                    expense.user_key,
                ),
            )
            self._conn.commit()
            saved = self._read_back(expense.id)
            logger.info(
                "Saved expense %s (key %s) for user %s",
                expense.id,
                saved.user_key,
                expense.user_id,
            )
            return saved

        cursor = self._conn.execute(
            """
            INSERT INTO expenses
                (amount, currency, merchant, date, category,
                 user_id, receipt_photo_id, created_at, deleted_at, user_key)
            VALUES (
                :amount, :currency, :merchant, :date, :category,
                :user_id, :receipt_photo_id, :created_at, :deleted_at,
                substr(:date,1,4) || substr(:date,6,2) || substr(:date,9,2) || '-' ||
                ((SELECT count(id) FROM expenses WHERE user_id = :user_id AND date = :date) + 1)
            )
            """,
            {
                "amount": str(expense.amount),
                "currency": expense.currency,
                "merchant": expense.merchant,
                "date": expense.date.isoformat(),
                "category": expense.category,
                "user_id": expense.user_id,
                "receipt_photo_id": expense.receipt_photo_id,
                "created_at": expense.created_at.isoformat(),
                "deleted_at": expense.deleted_at.isoformat()
                if expense.deleted_at is not None
                else None,
            },
        )
        self._conn.commit()
        new_id = cursor.lastrowid
        assert new_id is not None
        saved = self._read_back(new_id)
        logger.info(
            "Saved expense %s (key %s) for user %s", new_id, saved.user_key, expense.user_id
        )
        return saved

    def get_by_id(self, expense_id: int) -> Expense | None:
        """Retrieve a single expense by its unique identifier.

        Logically deleted rows are excluded.
        """
        row = self._conn.execute(
            "SELECT * FROM expenses WHERE id = ? AND deleted_at IS NULL",
            (expense_id,),
        ).fetchone()

        if row is None:
            logger.info("Expense %s not found", expense_id)
            return None

        logger.info("Retrieved expense %s", expense_id)
        return self._row_to_expense(row)

    def get_by_user_and_month(
        self,
        user_id: int,
        year: int,
        month: int,
    ) -> list[Expense]:
        """Retrieve all expenses for a given user in a given month, newest first.

        Logically deleted rows are excluded.
        """
        prefix = f"{year:04d}-{month:02d}"
        rows = self._conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND date LIKE ? "
            "AND deleted_at IS NULL "
            "ORDER BY created_at DESC",
            (user_id, f"{prefix}%"),
        ).fetchall()

        expenses = [self._row_to_expense(row) for row in rows]
        logger.info(
            "Retrieved %s expenses for user %s in %04d-%02d",
            len(expenses),
            user_id,
            year,
            month,
        )
        return expenses

    def get_months_with_expenses(self, user_id: int, year: int) -> set[int]:
        """Return the set of month numbers (1-12) that have expenses for a user in a year.

        Months whose only expenses are logically deleted are excluded.
        """
        prefix = f"{year:04d}-"
        rows = self._conn.execute(
            "SELECT DISTINCT substr(date, 6, 2) AS month FROM expenses"
            " WHERE user_id = ? AND date LIKE ? AND deleted_at IS NULL",
            (user_id, f"{prefix}%"),
        ).fetchall()

        months = {int(row["month"]) for row in rows}
        logger.info(
            "Found %s months with expenses for user %s in %04d",
            len(months),
            user_id,
            year,
        )
        return months

    def get_total_by_user_and_year(self, user_id: int, year: int) -> Decimal:
        """Return the sum of all expense amounts for a user in a year.

        Logically deleted rows are excluded.
        """
        prefix = f"{year:04d}-"
        rows = self._conn.execute(
            "SELECT amount FROM expenses WHERE user_id = ? AND date LIKE ? AND deleted_at IS NULL",
            (user_id, f"{prefix}%"),
        ).fetchall()

        total = sum(
            (Decimal(row["amount"]) for row in rows),
            start=Decimal("0.00"),
        )
        logger.info(
            "Total for user %s in %04d: %s",
            user_id,
            year,
            total,
        )
        return total

    def delete_by_user_key(self, user_id: int, user_key: str) -> Expense | None:
        """Logically delete the expense a person addressed by their own key.

        Marks the row with a deleted_at timestamp (ADR 0011); the row is never
        physically removed. Ownership is part of the SELECT predicate, so another
        person's identically-keyed row is never even fetched. The UPDATE then binds
        to the id that SELECT resolved, so it stamps exactly the row that was read —
        it does not depend on (user_id, user_key) naming one row, which is what the
        UNIQUE index used to guarantee (ADR 0018). Returns the deleted Expense
        for the caller to format a success message, or None if no matching live
        expense exists (unknown key, other person, or already deleted).
        """
        row = self._conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND user_key = ? AND deleted_at IS NULL",
            (user_id, user_key),
        ).fetchone()

        if row is None:
            logger.info(
                "Expense key %s not found for user %s — nothing to delete",
                user_key,
                user_id,
            )
            return None

        deleted_at = datetime.now()
        self._conn.execute(
            "UPDATE expenses SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (deleted_at.isoformat(), row["id"]),
        )
        self._conn.commit()

        logger.info(
            "Deleted expense %s (key %s) for user %s at %s",
            row["id"],
            user_key,
            user_id,
            deleted_at,
        )

        return self._row_to_expense(row)

    @staticmethod
    def _row_to_expense(row: sqlite3.Row) -> Expense:
        """Convert a SQLite row to an Expense domain object."""
        deleted_at_raw = row["deleted_at"]
        return Expense(
            id=int(row["id"]),
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            merchant=row["merchant"],
            date=date.fromisoformat(row["date"]),
            category=row["category"],
            user_id=row["user_id"],
            receipt_photo_id=row["receipt_photo_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            deleted_at=(
                datetime.fromisoformat(deleted_at_raw) if deleted_at_raw is not None else None
            ),
            user_key=row["user_key"],
        )

    def _read_back(self, row_id: int) -> Expense:
        """Read the row just written, so the returned Expense carries the stored key.

        This is a read, not a second key computation: the key was fixed inside
        the INSERT above (ADR 0016).
        """
        row = self._conn.execute("SELECT * FROM expenses WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            raise ValueError(f"row {row_id} missing after INSERT")
        return self._row_to_expense(row)
