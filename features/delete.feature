Feature: Delete Saved Expenses
  As a user
  I want to delete saved expenses by their own key or from the creation message
  So that I can remove mistakes from my records

  Background:
    Given the bot is running
    And the database is empty

  @story-17
  Scenario: Delete an expense by key
    Given a saved confirmation for expense 20260712-1 exists:
      | amount | currency | merchant     | date       | category |
      | 3.50   | EUR      | Central Cafe | 2026-07-12 | food     |
    When user 123456789 sends the delete command "/delete 20260712-1"
    Then the delete reply should be "🗑️ Deleted expense 20260712-1: Central Cafe — 3.50 EUR — 2026-07-12"
    And expense 20260712-1 should no longer be recorded

  @story-17
  Scenario: /delete reports not found for an expense outside my records
    Given a saved confirmation for expense 20260712-1 exists:
      | amount | currency | merchant      | date       | category |
      | 25.00  | EUR      | Corner Bakery | 2026-07-12 | food     |
    When user 456 sends the delete command "/delete 20260712-1"
    Then the delete reply should be "Expense 20260712-1 was not found."
    And expense 20260712-1 should still be recorded for user 123456789

  @story-17
  Scenario: Invalid /delete commands show the usage message
    When I send invalid delete commands:
      | command             |
      | /delete             |
      | /delete abc         |
      | /delete 42 extra    |
      | /delete 20261340-1  |
      | /delete #20260712-1 |
    Then each delete command should reply with "Usage: /delete <key>"

  @story-17
  Scenario: Two people share a key text
    Given the following expenses exist:
      | amount | currency | merchant      | date       | category | user_id   |
      | 3.50   | EUR      | Central Cafe  | 2026-07-18 | food     | 123456789 |
      | 7.25   | EUR      | Corner Bakery | 2026-07-18 | food     | 456       |
    When user 123456789 sends the command "/list"
    Then the message lists expense "#20260718-1" for merchant "Central Cafe"
    And the listing shows a key for every expense row

    When user 456 sends the command "/list"
    Then the message lists expense "#20260718-1" for merchant "Corner Bakery"

    When user 456 sends the delete command "/delete 20260718-1"
    Then the delete reply should be "🗑️ Deleted expense 20260718-1: Corner Bakery — 7.25 EUR — 2026-07-18"

    When user 456 sends the command "/list"
    Then the bot replies with a message that no expenses are recorded

    When user 123456789 sends the command "/list"
    Then the message lists expense "#20260718-1" for merchant "Central Cafe"
    And expense 20260718-1 should still be recorded for user 123456789

  @story-17
  Scenario: A person cannot address another person's expense
    Given the following expenses exist:
      | amount | currency | merchant      | date       | category | user_id   |
      | 3.50   | EUR      | Central Cafe  | 2026-07-18 | food     | 123456789 |
      | 7.25   | EUR      | Corner Bakery | 2026-07-19 | food     | 456       |
    When user 456 sends the delete command "/delete 20260718-1"
    Then the delete reply should be "Expense 20260718-1 was not found."
    And expense 20260718-1 should still be recorded for user 123456789
    And expense 20260719-1 should still be recorded for user 456

  @story-17
  Scenario: A freed key number is not reused
    Given the following expenses exist:
      | amount | currency | merchant      | date       | category |
      | 3.50   | EUR      | Central Cafe  | 2026-07-18 | food     |
      | 7.25   | EUR      | Corner Bakery | 2026-07-18 | food     |
    When user 123456789 sends the delete command "/delete 20260718-2"
    Then the delete reply should be "🗑️ Deleted expense 20260718-2: Corner Bakery — 7.25 EUR — 2026-07-18"

    When user 123456789 records the following expense:
      | amount | currency | merchant   | date       | category |
      | 9.99   | EUR      | Book Store | 2026-07-18 | shopping |
    Then the newly recorded expense should have key "20260718-3"

    When user 123456789 sends the command "/list"
    Then the message lists expense "#20260718-1" for merchant "Central Cafe"
    And the message lists expense "#20260718-3" for merchant "Book Store"
    And the listing shows a key for every expense row

  @story-18
  Scenario: Delete button strikes through the original saved-expense message
    Given a saved confirmation for expense 20260712-1 exists:
      | amount | currency | merchant     | date       | category |
      | 3.50   | EUR      | Central Cafe | 2026-07-12 | food     |
    When I tap the delete button for expense 20260712-1
    Then the edited confirmation still contains "Central Cafe"
    And the edited confirmation shows struck-through expense details
    And the edited confirmation includes "🗑️ Deleted."
    And the delete button is removed from the edited confirmation
    And expense 20260712-1 should no longer be recorded
