"""Assert the upgrade probe's before/after snapshots prove a safe migration."""

from __future__ import annotations

import json
import sys


def main() -> int:
    before = json.loads(sys.argv[1])
    after = json.loads(sys.argv[2])

    assert "deleted_at" not in before["columns"], f"legacy schema already has deleted_at: {before}"
    assert "user_key" not in before["columns"], f"legacy schema already has user_key: {before}"
    assert "databasechangelog" not in before["tables"], f"legacy schema has tracking: {before}"
    assert before["rows"], "legacy database has no rows"

    assert "deleted_at" in after["columns"], f"PR schema missing deleted_at: {after}"
    assert "user_key" in after["columns"], f"PR schema missing user_key: {after}"
    assert "databasechangelog" in after["tables"], f"Liquibase tracking table missing: {after}"
    assert after["changesets"] == 4, f"expected 4 changesets: {after}"
    assert after["rows"] == before["rows"], "migration changed or lost expense rows"
    assert after["user_keys"] is not None, f"no user_key snapshot: {after}"
    assert all(k["user_key"] for k in after["user_keys"]), f"unbackfilled user_key: {after}"
    assert [k["user_key"] for k in after["user_keys"]] == [
        "20260102-1",
        "20260115-1",
    ], f"unexpected backfilled user keys: {after}"
    print(
        "PASS: legacy rows preserved, deleted_at added, user keys backfilled, Liquibase baselined"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
