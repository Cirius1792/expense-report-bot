"""Step definitions for monthly report feature (Stories 9-10)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from behave import given, then, when

from features.steps.common_steps import (
    get_last_document,
    get_last_reply,
    make_telegram_update,
    seed_expense,
)

# ── Given steps for seeded expenses ─────────────────────────────────────────


def _csv_text(context: Any) -> str:
    """CSV content captured by the report steps, normalised to text."""
    raw = getattr(context, "_csv_content", "")
    return raw.decode("utf-8") if isinstance(raw, bytes) else raw


@given("I have recorded the following expenses this month:")
def step_seed_expenses_table(context: Any) -> None:
    """Seed multiple expenses from a Gherkin data table."""
    for row in context.table:
        seed_expense(
            context,
            user_id=context.user_id,
            amount=row["amount"],
            currency=row["currency"],
            merchant=row["merchant"],
            expense_date=row["date"],
            category=row.get("category"),
        )


@given("I have no expenses recorded this month")
def step_no_expenses(context: Any) -> None:
    """Ensure the database is empty for the current user/period."""
    results = context.repository.get_by_user_and_month(user_id=context.user_id, year=2026, month=7)
    assert len(results) == 0


@given('user {user_id:d} has recorded an expense of {amount} {currency} at "{merchant}"')
def step_other_user_expense(
    context: Any, user_id: int, amount: str, currency: str, merchant: str
) -> None:
    """Seed an expense for a specific user (for multi-user isolation tests)."""
    seed_expense(
        context,
        user_id=user_id,
        amount=amount,
        currency=currency,
        merchant=merchant,
        expense_date="2026-07-15",
    )


# ── When steps ──────────────────────────────────────────────────────────────


@when("user {user_id:d} requests /report")
def step_user_requests_report(context: Any, user_id: int) -> None:
    """Run the /report handler for a specific user."""
    from expense_report.adapters.inbound.telegram_bot import _make_report_handler

    handler = _make_report_handler(context.expense_queries)
    update = make_telegram_update(context, user_id=user_id, text="/report")
    ctx = MagicMock()

    with patch("expense_report.adapters.inbound.telegram_bot.datetime") as mock_dt:
        mock_dt.now.return_value = context.current_datetime
        asyncio.run(handler(update, ctx))

    # Capture CSV content for later assertions
    doc = get_last_document(context)
    if doc is not None:
        context._csv_content = doc[1]


# ── Then steps ──────────────────────────────────────────────────────────────


@then('the bot should send a CSV file named "{filename}"')
def step_csv_file_sent(context: Any, filename: str) -> None:
    doc = get_last_document(context)
    assert doc is not None, "Expected a CSV document, but none was sent"
    name, content = doc
    assert name == filename, f"Expected filename {filename}, got {name}"
    context._csv_content = content


@then("the CSV should contain {count:d} expense rows")
def step_csv_row_count(context: Any, count: int) -> None:
    csv_content = _csv_text(context)
    lines = [line for line in csv_content.strip().split("\n") if line.strip()]
    # Subtract header line
    data_rows = lines[1:] if len(lines) > 0 else []
    assert len(data_rows) == count, (
        f"Expected {count} data rows, got {len(data_rows)}. Lines: {lines}"
    )


@then('the CSV header should be "{header}"')
def step_csv_header(context: Any, header: str) -> None:
    """The header line is exactly the given column list, key leading (E6)."""
    lines = [line for line in _csv_text(context).strip().split("\n") if line.strip()]
    assert lines, "CSV has no content"
    assert lines[0] == header, f'Expected header "{header}", got "{lines[0]}"'


@then('the first CSV row should lead with "{key}"')
def step_first_row_leads_with_key(context: Any, key: str) -> None:
    """The first data row's leading field is its per-person key (E6)."""
    lines = [line for line in _csv_text(context).strip().split("\n") if line.strip()]
    data_rows = lines[1:]
    assert data_rows, "CSV has no data rows"
    assert data_rows[0].split(",")[0] == key, (
        f'Expected leading key "{key}", got row "{data_rows[0]}"'
    )


@then('the CSV row for "{merchant}" should lead with "{key}"')
def step_row_for_merchant_leads_with_key(context: Any, merchant: str, key: str) -> None:
    """Each row carries its own key in the leading column (E6, per-row)."""
    rows = [line for line in _csv_text(context).strip().split("\n") if line.strip()][1:]
    matches = [row for row in rows if merchant in row]
    assert matches, f"No CSV row mentions merchant {merchant!r}"
    assert all(row.split(",")[0] == key for row in matches), (
        f"Expected leading key {key} for {merchant!r}, got rows: {matches}"
    )


@then('the first row should contain "{text}"')
def step_first_row_contains(context: Any, text: str) -> None:
    csv_content = _csv_text(context)
    lines = csv_content.strip().split("\n")
    assert len(lines) >= 1, "CSV has no content"
    data_rows = lines[1:]
    assert len(data_rows) >= 1, "CSV has no data rows"
    assert text in data_rows[0], f'Expected "{text}" in first row "{data_rows[0]}"'


@then('the bot should reply with "Generated report with {count:d} expenses"')
def step_generated_report_count(context: Any, count: int) -> None:
    reply = get_last_reply(context)
    assert f"Generated report with {count} expenses" in reply, (
        f"Expected count message, got: {reply}"
    )


@then('the bot should reply with "No expenses recorded for {period}"')
def step_no_expenses_message(context: Any, period: str) -> None:
    reply = get_last_reply(context)
    assert f"No expenses recorded for {period}" in reply, (
        f"Expected empty message for {period}, got: {reply}"
    )


@then("the bot should not send any file")
def step_no_file_sent(context: Any) -> None:
    doc = get_last_document(context)
    assert doc is None, f"Expected no file, but got: {doc}"


@then('the CSV should contain "{text}"')
def step_csv_contains(context: Any, text: str) -> None:
    assert text in _csv_text(context), (
        f'Expected CSV to contain "{text}", got: {_csv_text(context)}'
    )


@then('the CSV should not contain "{text}"')
def step_csv_not_contains(context: Any, text: str) -> None:
    text_content = _csv_text(context)
    assert text not in text_content, f'CSV should not contain "{text}", got: {text_content}'
