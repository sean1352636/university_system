"""Validated CSV, JSON and Excel import/export for reporting data."""

import csv
import json
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import transaction, get_connection

TABLES = {
    "students": "students",
    "courses": "courses",
    "modules": "modules",
}


def read_records(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as source:
            return list(csv.DictReader(source))
    if suffix in {".xlsx", ".xls"}:
        import pandas as pd
        return pd.read_excel(path).where(lambda frame: frame.notna(), None).to_dict("records")
    raise ValueError(f"Unsupported import format: {suffix}")


def import_table(kind, file_path):
    table = TABLES.get(kind)
    if not table:
        raise ValueError(f"Unsupported database import type: {kind}")
    rows = read_records(file_path)
    if not rows:
        return 0
    with get_connection() as conn:
        available = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    columns = [name for name in rows[0] if name in available]
    if not columns:
        raise ValueError(f"The file contains no columns recognised by {table}")
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    with transaction() as conn:
        conn.executemany(sql, [[row.get(column) for column in columns] for row in rows])
    return len(rows)


def table_records(kind):
    table = TABLES.get(kind)
    if not table:
        raise ValueError(f"Unsupported database export type: {kind}")
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def write_records(records, file_path, output_format):
    path = Path(file_path)
    records = list(records)
    if output_format == "json":
        path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    elif output_format == "csv":
        fields = list(records[0]) if records else []
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            if fields:
                writer.writeheader()
                writer.writerows(records)
    elif output_format == "excel":
        import pandas as pd
        pd.DataFrame(records).to_excel(path, index=False)
    else:
        raise ValueError(f"Unsupported export format: {output_format}")
    return path
