"""Protocol compliance tests for ExpenseRepositoryPort."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from expense_report.domain.models import Expense
from expense_report.ports.repository import ExpenseRepositoryPort


class TestExpenseRepositoryPortProtocol:
    """Verify that a class implementing ExpenseRepositoryPort satisfies the protocol."""

    def test_protocol_compliance(self) -> None:
        """An object with save/get_by_id/get_by_user_and_month methods
        should be recognized as an ExpenseRepositoryPort implementation."""

        class FakeRepository:
            def __init__(self) -> None:
                self._store: dict[int, Expense] = {}

            def save(self, expense: Expense) -> Expense:
                stored = Expense(
                    id=1 if expense.id is None else expense.id,
                    user_key=f"{expense.date:%Y%m%d}-1",
                    amount=expense.amount,
                    currency=expense.currency,
                    merchant=expense.merchant,
                    date=expense.date,
                    category=expense.category,
                    user_id=expense.user_id,
                    receipt_photo_id=expense.receipt_photo_id,
                    created_at=expense.created_at,
                )
                assert stored.id is not None
                self._store[stored.id] = stored
                return stored

            def get_by_id(self, expense_id: int) -> Expense | None:
                return self._store.get(expense_id)

            def delete_by_user_key(self, user_id: int, user_key: str) -> Expense | None:
                for expense_id, expense in list(self._store.items()):
                    if (expense.user_id, expense.user_key) == (user_id, user_key):
                        del self._store[expense_id]
                        return expense
                return None

            def get_by_user_and_month(
                self,
                user_id: int,
                year: int,
                month: int,
            ) -> list[Expense]:
                return [
                    e
                    for e in self._store.values()
                    if e.user_id == user_id and e.date.year == year and e.date.month == month
                ]

            def get_months_with_expenses(self, user_id: int, year: int) -> set[int]:
                return {
                    e.date.month
                    for e in self._store.values()
                    if e.user_id == user_id and e.date.year == year
                }

            def get_total_by_user_and_year(self, user_id: int, year: int) -> Decimal:
                return sum(
                    (
                        e.amount
                        for e in self._store.values()
                        if e.user_id == user_id and e.date.year == year
                    ),
                    Decimal("0"),
                )

        repo = FakeRepository()
        assert isinstance(repo, ExpenseRepositoryPort), (
            "FakeRepository must satisfy ExpenseRepositoryPort protocol"
        )

    def test_save_and_retrieve(self) -> None:
        """Save an expense and retrieve it by id."""

        class SimpleRepo:
            def __init__(self) -> None:
                self._store: dict[int, Expense] = {}

            def save(self, expense: Expense) -> Expense:
                stored = Expense(
                    id=42,
                    user_key=f"{expense.date:%Y%m%d}-1",
                    amount=expense.amount,
                    currency=expense.currency,
                    merchant=expense.merchant,
                    date=expense.date,
                    category=expense.category,
                    user_id=expense.user_id,
                    receipt_photo_id=expense.receipt_photo_id,
                    created_at=expense.created_at,
                )
                self._store[42] = stored
                return stored

            def get_by_id(self, expense_id: int) -> Expense | None:
                return self._store.get(expense_id)

            def delete_by_user_key(self, user_id: int, user_key: str) -> Expense | None:
                for expense_id, expense in list(self._store.items()):
                    if (expense.user_id, expense.user_key) == (user_id, user_key):
                        del self._store[expense_id]
                        return expense
                return None

            def get_by_user_and_month(
                self,
                user_id: int,
                year: int,
                month: int,
            ) -> list[Expense]:
                return [
                    e
                    for e in self._store.values()
                    if e.user_id == user_id and e.date.year == year and e.date.month == month
                ]

        repo = SimpleRepo()
        dt = datetime(2026, 7, 1, 12, 0, 0)
        expense = Expense(
            id=None,
            user_key=None,
            amount=Decimal("10.00"),
            currency="EUR",
            merchant="Shop",
            date=date(2026, 7, 1),
            category=None,
            user_id=42,
            receipt_photo_id=None,
            created_at=dt,
        )

        saved = repo.save(expense)
        assert saved.id == 42

        retrieved = repo.get_by_id(42)
        assert retrieved is not None
        assert retrieved.amount == Decimal("10.00")
        assert retrieved.merchant == "Shop"
