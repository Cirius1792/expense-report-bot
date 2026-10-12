"""Tests for ExpenseQueryUseCase — browse, report, and delete workflows."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from expense_report.domain.models import Expense
from expense_report.ports.expense_queries import DeletionResult, PeriodSummary


def _make_expense(
    id: int = 1,
    amount: str = "10.00",
    currency: str = "EUR",
    merchant: str = "Shop",
    date_val: date | None = None,
    category: str | None = None,
    user_id: int = 12345,
    user_key: str | None = "20260701-1",
) -> Expense:
    d = date_val or date(2026, 7, 1)
    return Expense(
        id=id,
        user_key=user_key,
        amount=Decimal(amount),
        currency=currency,
        merchant=merchant,
        date=d,
        category=category,
        user_id=user_id,
        receipt_photo_id=None,
        created_at=datetime(2026, 7, 1, 10, 0, 0),
    )


# ============================================================================
# discover_periods
# ============================================================================


class TestDiscoverPeriods:
    """Tests for period discovery policy."""

    def test_current_year_has_data_uses_current_month_as_active(self) -> None:
        """When current year has data, active = current year/month."""
        from unittest.mock import patch

        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_months_with_expenses.side_effect = [
            {7, 3},  # 2026
            set(),  # 2025
        ]
        use_case = ExpenseQueryUseCase(repo)

        with patch("expense_report.application.expense_queries.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 15, 12, 0, 0)
            result = use_case.discover_periods(12345)

        assert result == PeriodSummary(
            periods={2026: {7, 3}},
            active_year=2026,
            active_month=7,
        )
        repo.get_months_with_expenses.assert_any_call(12345, 2026)
        repo.get_months_with_expenses.assert_any_call(12345, 2025)

    def test_current_year_no_data_previous_has_uses_most_recent(self) -> None:
        """When current year empty but previous has data, active = previous year."""
        from unittest.mock import patch

        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_months_with_expenses.side_effect = [
            set(),  # 2026 — no data
            {12, 1},  # 2025 — Dec and Jan
        ]
        use_case = ExpenseQueryUseCase(repo)

        with patch("expense_report.application.expense_queries.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 15, 12, 0, 0)
            result = use_case.discover_periods(12345)

        assert result == PeriodSummary(
            periods={2025: {12, 1}},
            active_year=2025,
            active_month=12,  # most recent
        )

    def test_no_expenses_at_all_returns_default_active(self) -> None:
        """When no expenses exist, periods is empty, active = current."""
        from unittest.mock import patch

        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_months_with_expenses.side_effect = [
            set(),
            set(),
        ]
        use_case = ExpenseQueryUseCase(repo)

        with patch("expense_report.application.expense_queries.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 15, 12, 0, 0)
            result = use_case.discover_periods(12345)

        assert result.periods == {}
        assert result.active_year == 2026
        assert result.active_month == 7

    def test_extra_years_are_also_scanned(self) -> None:
        """When extra_years provided, those years are queried too."""
        from unittest.mock import patch

        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_months_with_expenses.side_effect = [
            {7},  # 2026
            set(),  # 2025
            {6},  # 2024 (extra)
        ]
        use_case = ExpenseQueryUseCase(repo)

        with patch("expense_report.application.expense_queries.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 15, 12, 0, 0)
            result = use_case.discover_periods(12345, extra_years={2024})

        assert result == PeriodSummary(
            periods={2026: {7}, 2024: {6}},
            active_year=2026,
            active_month=7,
        )

    def test_multi_user_isolation(self) -> None:
        """Different user_ids result in different repository queries."""
        from unittest.mock import patch

        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_months_with_expenses.side_effect = [
            {7},
            set(),
        ]
        use_case = ExpenseQueryUseCase(repo)

        with patch("expense_report.application.expense_queries.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 15, 12, 0, 0)
            use_case.discover_periods(99999)

        repo.get_months_with_expenses.assert_any_call(99999, 2026)
        repo.get_months_with_expenses.assert_any_call(99999, 2025)


# ============================================================================
# get_month_expenses
# ============================================================================


class TestGetMonthExpenses:
    """Tests for month expense retrieval."""

    def test_returns_expenses_for_given_period(self) -> None:
        """Returns list from repository for the requested user/year/month."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        e1 = _make_expense(id=1, merchant="A")
        e2 = _make_expense(id=2, merchant="B")
        repo = MagicMock()
        repo.get_by_user_and_month.return_value = [e1, e2]
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.get_month_expenses(12345, 2026, 7)

        repo.get_by_user_and_month.assert_called_once_with(12345, 2026, 7)
        assert result == [e1, e2]

    def test_returns_empty_list_when_no_expenses(self) -> None:
        """Empty list when no expenses found."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_by_user_and_month.return_value = []
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.get_month_expenses(12345, 2026, 3)

        assert result == []


# ============================================================================
# get_year_expenses
# ============================================================================


class TestGetYearExpenses:
    """Tests for year expense aggregation."""

    def test_aggregates_across_all_months(self) -> None:
        """Collects expenses from every month that has data."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        e1 = _make_expense(id=1, merchant="Jan", date_val=date(2026, 1, 5))
        e2 = _make_expense(id=2, merchant="Mar", date_val=date(2026, 3, 10))
        e3 = _make_expense(id=3, merchant="Dec", date_val=date(2026, 12, 20))

        repo = MagicMock()
        repo.get_months_with_expenses.return_value = {1, 3, 12}
        repo.get_by_user_and_month.side_effect = [
            [e1],  # month 1
            [e2],  # month 3
            [e3],  # month 12
        ]
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.get_year_expenses(12345, 2026)

        assert len(result) == 3
        assert result == [e1, e2, e3]

    def test_returns_empty_list_when_year_has_no_data(self) -> None:
        """Empty list when no months have expenses."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_months_with_expenses.return_value = set()
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.get_year_expenses(12345, 2025)

        assert result == []


# ============================================================================
# generate_csv_report
# ============================================================================


class TestGenerateCsvReport:
    """Tests for CSV report generation."""

    def test_generates_csv_for_given_period(self) -> None:
        """Returns CSV string from domain generate_csv."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        e1 = _make_expense(id=1, merchant="Shop A", amount="10.00")
        e2 = _make_expense(id=2, merchant="Shop B", amount="20.50")
        repo = MagicMock()
        repo.get_by_user_and_month.return_value = [e1, e2]
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.generate_csv_report(12345, 2026, 7)

        repo.get_by_user_and_month.assert_called_once_with(12345, 2026, 7)
        assert "user_key,date,merchant,category,amount,currency" in result
        assert "Shop A" in result
        assert "Shop B" in result

    def test_empty_period_returns_header_only(self) -> None:
        """Empty expense list returns CSV with headers only."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.get_by_user_and_month.return_value = []
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.generate_csv_report(12345, 2026, 3)

        assert "user_key,date,merchant,category,amount,currency" in result
        # Header only — no data rows
        lines = result.strip().split("\n")
        assert len(lines) == 1


# ============================================================================
# delete_expense
# ============================================================================


class TestDeleteExpense:
    """Tests for expense deletion."""

    def test_successful_delete_returns_deleted_expense(self) -> None:
        """Returns DeletionResult with the deleted Expense."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        e1 = _make_expense(id=42, user_key="20260718-3")
        repo = MagicMock()
        repo.delete_by_user_key.return_value = e1
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.delete_expense(12345, "20260718-3")

        repo.delete_by_user_key.assert_called_once_with(12345, "20260718-3")
        assert result == DeletionResult(status="deleted", deleted=e1)

    def test_not_found_returns_none_deleted(self) -> None:
        """Returns DeletionResult(status="not_found") when the key addresses no live row."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        repo.delete_by_user_key.return_value = None
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.delete_expense(12345, "20260718-3")

        repo.delete_by_user_key.assert_called_once_with(12345, "20260718-3")
        assert result == DeletionResult(status="not_found", deleted=None)

    @pytest.mark.parametrize(
        "key",
        [
            "20261340-1",  # regex-valid, calendar-invalid
            "abc",  # shape-invalid
        ],
    )
    def test_delete_expense_rejects_malformed_key_without_touching_repository(
        self, key: str
    ) -> None:
        """A malformed key is rejected in the application: status invalid_key, repo untouched."""
        from expense_report.application.expense_queries import ExpenseQueryUseCase

        repo = MagicMock()
        use_case = ExpenseQueryUseCase(repo)

        result = use_case.delete_expense(12345, key)

        assert result == DeletionResult(status="invalid_key")
        repo.delete_by_user_key.assert_not_called()
