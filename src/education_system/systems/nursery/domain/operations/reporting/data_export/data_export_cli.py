"""CLI flow for Data Export (Nursery System).

Lists the exportable nursery tables with live row counts and writes them to
CSV — either all tables at once or a single chosen table.
"""

from __future__ import annotations

import logging

from education_system.systems.nursery.domain.operations.reporting.data_export import (
    data_export as data,
)

logger = logging.getLogger(__name__)


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_tables(tables: list[dict]) -> None:
    print("\n═══ Data Export ═══")
    if not tables:
        print("  No exportable tables found.")
        return
    print(f"  {'#':>2}  {'Table':<26} {'Rows':>7}")
    print("  " + "-" * 40)
    for i, t in enumerate(tables, start=1):
        print(f"  {i:>2}  {t['label'][:26]:<26} {t['rows']:>7}")
    total = sum(t["rows"] for t in tables)
    print("  " + "-" * 40)
    print(f"  Tables: {len(tables)}   Total rows: {total}")


def _prompt_dir() -> str | None:
    default = str(data.default_export_dir())
    try:
        raw = input(f"\n  Destination directory [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return raw or default


def _export_all() -> None:
    dir_path = _prompt_dir()
    if dir_path is None:
        return
    try:
        res = data.export_all(dir_path)
    except (data.ValidationError, OSError) as e:
        print(f"  ✗ {e}")
        return
    for f in res["files"]:
        if "path" in f:
            print(f"  ✓ {f['table']}: {f['row_count']} row(s) → {f['path']}")
        else:
            print(f"  ✗ {f['table']}: {f['error']}")
    print(f"\n  Wrote {res['table_count']} file(s), "
          f"{res['total_rows']} total row(s) → {res['dir']}")


def _export_one(tables: list[dict]) -> None:
    if not tables:
        print("  Nothing to export.")
        return
    try:
        raw = input("\n  Table number to export: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not raw.isdigit() or not (1 <= int(raw) <= len(tables)):
        print("  Invalid selection.")
        return
    table = tables[int(raw) - 1]["table"]
    dir_path = _prompt_dir()
    if dir_path is None:
        return
    try:
        res = data.export_table(table, dir_path)
        print(f"  ✓ Wrote {res['row_count']} row(s) → {res['path']}")
    except (data.ValidationError, OSError) as e:
        print(f"  ✗ {e}")


def run(auth=None) -> None:
    """Entry point for the Data Export CLI screen."""
    while True:
        try:
            tables = data.list_tables()
            _print_tables(tables)
        except Exception as e:  # noqa: BLE001
            logger.exception("Data export failed")
            print(f"\n  ✗ Could not load tables: {e}")
            _pause()
            return
        print("\n   1) Export all tables   2) Export one table   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "1":
            _export_all()
            _pause()
        elif choice == "2":
            _export_one(tables)
            _pause()
        elif choice == "0" or choice == "":
            return
        else:
            print("  Invalid selection.")


def dispatch(label: str) -> bool:
    if label != "Data Export":
        return False
    run()
    return True
