"""Tests for the expense key predicate (domain/expense_keys.py).

The predicate is a pure domain rule: no fixture, no repository, no transport.
"""

from __future__ import annotations

from expense_report.domain.expense_keys import is_valid_expense_key


class TestExpenseKeyPredicate:
    """Verify what counts as a well-formed per-person expense key."""

    def test_accepts_a_dated_key_with_a_count(self) -> None:
        """`YYYYMMDD-n` over a real date is accepted."""
        assert is_valid_expense_key("20260718-1") is True

    def test_accepts_a_multi_digit_count(self) -> None:
        """The count is not zero-padded and may exceed 9."""
        assert is_valid_expense_key("20260710-12") is True

    def test_rejects_text_that_is_not_a_key(self) -> None:
        """A free-word is not a key."""
        assert is_valid_expense_key("abc") is False

    def test_rejects_an_empty_key(self) -> None:
        """The empty string is not a key."""
        assert is_valid_expense_key("") is False

    def test_rejects_a_leading_hash(self) -> None:
        """The `#` shown in /list is not part of the key a user may send."""
        assert is_valid_expense_key("#20260718-1") is False

    def test_rejects_a_missing_count(self) -> None:
        """A date with no count after the dash is not a key."""
        assert is_valid_expense_key("20260718-") is False

    def test_rejects_trailing_text(self) -> None:
        """Text after the count is not part of a key."""
        assert is_valid_expense_key("20260718-1x") is False

    def test_rejects_a_calendar_impossible_key(self) -> None:
        """Shape alone is not enough: month 13, day 40 is not a date."""
        assert is_valid_expense_key("20261340-1") is False
