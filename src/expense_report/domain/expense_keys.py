"""Per-person expense key (`YYYYMMDD-n`, ADR 0016) shape check.

Pure predicate over the key text a user types — no IO, no framework, no
repository knowledge. The shape regex alone is not enough: `20261340-1` matches
it but is not a calendar date, so the 8 digits are parsed as well.
"""

from __future__ import annotations

import re
from datetime import datetime

KEY_PATTERN = re.compile(r"^\d{8}-\d+$")


def is_valid_expense_key(key: str) -> bool:
    """True when key is a per-person expense key: `YYYYMMDD-n` with a real date."""
    if KEY_PATTERN.fullmatch(key) is None:
        return False
    digits, _, _number = key.partition("-")
    try:
        datetime.strptime(digits, "%Y%m%d")
    except ValueError:
        return False
    return True


__all__ = ["is_valid_expense_key"]
