"""CSV export utility for the education system."""

import csv
import sqlite3
import os


def export_to_csv(data, headers, filepath):
    """Export a list of dicts or tuples to a CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in data:
            if isinstance(row, dict):
                writer.writerow([row.get(h, "") for h in headers])
            else:
                writer.writerow(row)
    return filepath


def export_query_to_csv(db_path, query, params, filepath):
    """Run a SQL query and export results to CSV."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(query, params or ())
        rows = cursor.fetchall()
        if not rows:
            headers = []
        else:
            headers = list(rows[0].keys())
        return export_to_csv([dict(r) for r in rows], headers, filepath)
    finally:
        conn.close()
