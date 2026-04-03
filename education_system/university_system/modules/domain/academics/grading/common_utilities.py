# refactored/students/grade_common.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    try:
        return bool(cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
        ).fetchone())
    except Exception:
        return False

def _cols(cur: sqlite3.Cursor, table: str) -> set[str]:
    try:
        safe_table = validate_identifier(table, "table")
        return {row[1] for row in cur.execute("PRAGMA table_info([" + safe_table + "])").fetchall()}
    except Exception:
        return set()

def _first_table(cur: sqlite3.Cursor, candidates: List[str]) -> Optional[str]:
    for t in candidates:
        if _table_exists(cur, t):
            return t
    return None

def _first_col(cur: sqlite3.Cursor, table: str, candidates: List[str]) -> Optional[str]:
    have = _cols(cur, table)
    for c in candidates:
        if c in have:
            return c
    return None

def select_assessment(
    auth: Any = None,
    conn: Optional[sqlite3.Connection] = None,
    cursor: Optional[sqlite3.Cursor] = None,
    allow_cancel: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Interactive selector for an assessment/exam/test, tolerant to schema drift.
    Returns a dict: {'id': <val>, 'name': <str>, 'date': <str|None>, 'table': <str>, 'id_col': <str>, 'name_col': <str>}
    or None if cancelled / nothing to select.
    """
    owns_conn = False
    try:
        if cursor is None:
            conn = conn or get_connection()
            cursor = conn.cursor()
            owns_conn = True

        table = _first_table(cursor, ["assessments", "assessment", "exams", "tests", "assignments"])
        if not table:
            print("No assessments/exams/tests table found.")
            return None

        id_col   = _first_col(cursor, table, ["assessment_id", "id", "exam_id", "test_id"])
        name_col = _first_col(cursor, table, ["name", "title", "assessment_name", "exam_name", "test_name"])
        date_col = _first_col(cursor, table, ["date", "assessment_date", "exam_date", "test_date", "due_date", "created_at"])

        if not id_col or not name_col:
            print(f"'{table}' is missing an id/name column I can use.")
            return None

        order_col = date_col or id_col
        safe_table = validate_identifier(table, "table")
        safe_id = validate_identifier(id_col, "column")
        safe_name = validate_identifier(name_col, "column")
        safe_order = validate_identifier(order_col, "column")
        select_cols = "[" + safe_id + "], [" + safe_name + "]"
        if date_col:
            safe_date = validate_identifier(date_col, "column")
            select_cols += ", [" + safe_date + "]"
        rows = cursor.execute(
            "SELECT " + select_cols +
            " FROM [" + safe_table + "] ORDER BY [" + safe_order + "] DESC LIMIT 100"
        ).fetchall()

        if not rows:
            print("No assessments available.")
            return None

        print("\nSelect Assessment:")
        for idx, row in enumerate(rows, 1):
            _id, _name = row[0], row[1]
            _date = row[2] if date_col and len(row) > 2 else None
            label = f"{_name}" + (f"  ({_date})" if _date else "")
            print(f"{idx}. {label}")

        while True:
            choice = input(f"\nEnter number 1-{len(rows)}" + (" (or 'q' to cancel): " if allow_cancel else ": ")).strip().lower()
            if allow_cancel and choice in {"q", "quit", "exit"}:
                return None
            if choice.isdigit():
                n = int(choice)
                if 1 <= n <= len(rows):
                    sel = rows[n - 1]
                    return {
                        "id": sel[0],
                        "name": sel[1],
                        "date": (sel[2] if date_col and len(sel) > 2 else None),
                        "table": table,
                        "id_col": id_col,
                        "name_col": name_col,
                        "date_col": date_col,
                    }
            print("Invalid choice. Try again.")

    finally:
        if owns_conn:
            try:
                conn.close()
            except Exception:
                pass