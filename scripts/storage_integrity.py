from __future__ import annotations

import argparse
from pathlib import Path

from src.infrastructure.persistence.sqlite import (
    SQLiteConnectionFactory,
    SQLiteMigrator,
    check_integrity,
    create_backup,
    write_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and optionally back up the AIGC local SQLite store.")
    parser.add_argument("--database", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--backup")
    args = parser.parse_args()

    factory = SQLiteConnectionFactory(args.database)
    SQLiteMigrator(factory, ROOT / "migrations" / "sqlite").apply_all()
    if args.backup:
        receipt = create_backup(factory, args.backup)
    else:
        receipt = check_integrity(factory)
    write_receipt(receipt, args.receipt)
    if getattr(receipt, "integrity_result", "") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
