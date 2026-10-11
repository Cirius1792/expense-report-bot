"""Step definitions for delete saved expenses feature (Stories 17-18)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from behave import given, then, when


def _key_year_month(key: str) -> tuple[int, int]:
    """Year and month of the expense date a `YYYYMMDD-n` key is derived from.

    The key prefix is the Expense's own date (E7), so a key-only lookup
    resolves the month read without ever consulting the storage id.
    """
    digits = key.partition("-")[0]
    return int(digits[:4]), int(digits[4:6])


# ── When steps ─────────────────────────────────────────────────────────────


@when('user {user_id:d} sends the delete command "{command}"')
def step_delete_user_command(context: Any, user_id: int, command: str) -> None:
    """Send a /delete command from a specific user (user-scoped variant)."""
    from expense_report.adapters.inbound.telegram_bot import _make_delete_handler

    handler = _make_delete_handler(context.expense_queries)
    update = _make_delete_update(context, user_id=user_id, text=command)
    ctx = MagicMock()
    asyncio.run(handler(update, ctx))
    context._last_delete_reply = update.effective_message.reply_text.call_args[0][0]


@when("user {user_id:d} records the following expense:")
def step_user_records_expense(context: Any, user_id: int) -> None:
    """Record one more expense for that person through the repository's save().

    Same call the recording path makes: `id=None`, so the key is assigned inside
    the INSERT (E13) and read back from the row. Hand-writing a key here would
    pin the wording of the scenario without pinning the counter it is about.
    """
    from datetime import date, datetime
    from decimal import Decimal

    from expense_report.domain.models import Expense

    for row in context.table:
        expense = Expense(
            id=None,
            user_key=None,
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            merchant=row["merchant"],
            date=date.fromisoformat(row["date"]),
            category=row.get("category"),
            user_id=user_id,
            receipt_photo_id=None,
            created_at=datetime.fromisoformat(f"{row['date']}T12:00:00"),
        )
        context._last_saved_expense = context.repository.save(expense)


@when("I send invalid delete commands:")
def step_send_invalid_delete_commands(context: Any) -> None:
    """Send each invalid delete command and collect replies."""
    from expense_report.adapters.inbound.telegram_bot import _make_delete_handler

    handler = _make_delete_handler(context.expense_queries)
    replies: list[str] = []

    for row in context.table:
        cmd = row["command"]
        update = _make_delete_update(context, text=cmd)
        ctx = MagicMock()
        asyncio.run(handler(update, ctx))
        replies.append(update.effective_message.reply_text.call_args[0][0])

    context._invalid_delete_replies = replies


@when("I tap the delete button for expense {expense_key}")
def step_tap_delete_button(context: Any, expense_key: str) -> None:
    """Simulate tapping the delete button callback."""
    from expense_report.adapters.inbound.telegram_bot import _make_delete_callback_handler

    handler = _make_delete_callback_handler(context.expense_queries)
    update = MagicMock()
    query = MagicMock()
    query.data = f"delete:{expense_key}"
    query.from_user = MagicMock()
    query.from_user.id = context.user_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_caption = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.text = (
        f"Extracted expense:\nExpense {expense_key}\n"
        f"Amount: 3.50 EUR\nMerchant: Central Cafe\n"
        f"Date: 2026-07-12\nCategory: food\n\nSaved."
    )
    query.message.caption = None
    update.callback_query = query
    callback_ctx = MagicMock()

    asyncio.run(handler(update, callback_ctx))
    if query.edit_message_text.call_count > 0:
        call_kwargs = query.edit_message_text.call_args[1]
        context._edited_text = call_kwargs.get("text", "")
        context._edited_parse_mode = call_kwargs.get("parse_mode")
        context._edited_reply_markup = call_kwargs.get("reply_markup")
    else:
        context._edited_text = ""
        context._edited_parse_mode = None
        context._edited_reply_markup = None


# ── Given steps ────────────────────────────────────────────────────────────


@given("a saved confirmation for expense {expense_key} exists:")
def step_saved_confirmation_exists(context: Any, expense_key: str) -> None:
    """Seed an expense that acquires its genuine key through save().

    The table names the expense dates that drive the key and carries no id
    column: the global id is never user-facing (E12), and seeding with an
    explicit id would take the test-only branch of save() and produce a
    key-less, unaddressable row. Fixtures never hand-write keys.
    """
    from datetime import date, datetime
    from decimal import Decimal

    from expense_report.domain.models import Expense

    for row in context.table:
        expense = Expense(
            id=None,
            user_key=None,
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            merchant=row["merchant"],
            date=date.fromisoformat(row["date"]),
            category=row.get("category"),
            user_id=context.user_id,
            receipt_photo_id=None,
            created_at=datetime.fromisoformat(f"{row['date']}T12:00:00"),
        )
        context.repository.save(expense)


# ── Then steps ─────────────────────────────────────────────────────────────


@then('the delete reply should be "{text}"')
def step_bot_reply_exact(context: Any, text: str) -> None:
    """Verify the bot's delete reply matches exactly."""
    reply = getattr(context, "_last_delete_reply", "")
    assert reply == text, f"Expected '{text}', got: '{reply}'"


@then("expense {expense_key} should no longer be recorded")
def step_expense_not_recorded(context: Any, expense_key: str) -> None:
    """Verify the addressed expense is not retrievable after deletion.

    Addressed by key through the month read, never by the storage id.
    """
    year, month = _key_year_month(expense_key)
    matches = [
        expense
        for expense in context.repository.get_by_user_and_month(
            user_id=context.user_id, year=year, month=month
        )
        if expense.user_key == expense_key
    ]
    assert not matches, f"Expected expense {expense_key} to be deleted"


@then("expense {expense_key} should still be recorded for user {user_id:d}")
def step_expense_still_recorded(context: Any, expense_key: str, user_id: int) -> None:
    """Verify the key-addressed expense is still there, owned by that person."""
    year, month = _key_year_month(expense_key)
    matches = [
        expense
        for expense in context.repository.get_by_user_and_month(
            user_id=user_id, year=year, month=month
        )
        if expense.user_key == expense_key
    ]
    assert matches, f"Expected expense {expense_key} to still exist for user {user_id}"
    owners = {expense.user_id for expense in matches}
    assert owners == {user_id}, f"Expected owner {user_id}, got {sorted(owners)}"


@then('the newly recorded expense should have key "{expense_key}"')
def step_newly_recorded_key(context: Any, expense_key: str) -> None:
    """The key that the last save() assigned, as stored in the row.

    Pins E10: a soft delete frees a key number, and the next expense on that
    date must not be handed it again.
    """
    saved = getattr(context, "_last_saved_expense", None)
    assert saved is not None, "No expense was recorded by this scenario"
    assert saved.user_key == expense_key, (
        f"Expected the new expense to be keyed '{expense_key}', got '{saved.user_key}'"
    )


@then('each delete command should reply with "{expected}"')
def step_each_delete_invalid_reply(context: Any, expected: str) -> None:
    """Verify all invalid commands returned the usage message."""
    replies = getattr(context, "_invalid_delete_replies", [])
    assert len(replies) > 0, "No replies collected"
    for i, reply in enumerate(replies):
        assert reply == expected, f"Reply {i}: expected '{expected}', got '{reply}'"


@then('the edited confirmation still contains "{text}"')
def step_edited_contains(context: Any, text: str) -> None:
    """Verify the edited confirmation still has the original text (though struck through)."""
    edited = getattr(context, "_edited_text", "")
    assert text in edited, f"Expected '{text}' in edited text, got: {edited[:200]}"


@then("the edited confirmation shows struck-through expense details")
def step_edited_strikethrough(context: Any) -> None:
    """Verify HTML strikethrough tags are present."""
    edited = getattr(context, "_edited_text", "")
    assert "<s>" in edited, f"Expected <s> tags in edited text, got: {edited[:200]}"
    assert "</s>" in edited, f"Expected </s> in edited text, got: {edited[:200]}"


@then('the edited confirmation includes "{text}"')
def step_edited_includes_text(context: Any, text: str) -> None:
    """Verify the edited confirmation has the given text."""
    edited = getattr(context, "_edited_text", "")
    assert text in edited, f"Expected '{text}' in edited text, got: {edited[:200]}"


@then("the delete button is removed from the edited confirmation")
def step_edited_no_delete_button(context: Any) -> None:
    """Verify the delete button is no longer present."""
    markup = getattr(context, "_edited_reply_markup", None)
    # No reply_markup means no buttons
    if (
        markup is not None
        and hasattr(markup, "inline_keyboard")
        and len(markup.inline_keyboard) > 0
    ):
        # Check if any button is a delete button
        for row in markup.inline_keyboard:
            for btn in row:
                assert "Delete" not in btn.text, f"Delete button still present: {btn.text}"


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_delete_update(context: Any, user_id: int | None = None, text: str = "") -> MagicMock:
    """Create a mock Update for /delete handler tests."""
    uid = user_id if user_id is not None else context.user_id
    update = MagicMock()
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = uid
    update.effective_message.text = text
    return update
