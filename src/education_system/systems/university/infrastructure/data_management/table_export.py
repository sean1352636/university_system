"""Write a table (columns + rows) to a file in the formats the student
search and its reports offer: CSV, any-delimiter text, JSON, plain text,
XML, Excel (openpyxl), PDF (reportlab) and SQL INSERT statements.

Heavy libraries are imported only when their format is chosen.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from xml.sax.saxutils import escape

FORMATS = {
    "csv": "CSV",
    "tsv": "Tab-separated",
    "delimited": "Other delimiter",
    "json": "JSON",
    "txt": "Text table",
    "xml": "XML",
    "xlsx": "Excel",
    "pdf": "PDF",
    "sql": "SQL INSERT statements",
}
EXTENSIONS = {"csv": ".csv", "tsv": ".tsv", "delimited": ".txt", "json": ".json", "txt": ".txt",
              "xml": ".xml", "xlsx": ".xlsx", "pdf": ".pdf", "sql": ".sql"}
_TAG = re.compile(r"[^A-Za-z0-9_]")


def format_for(path, default="csv") -> str:
    """The format a file name asks for (by extension)."""
    lower = str(path).lower()
    for fmt, ext in EXTENSIONS.items():
        if fmt not in ("delimited", "txt") and lower.endswith(ext):
            return fmt
    return "txt" if lower.endswith(".txt") else default


def _cell(value):
    return "" if value is None else value


def write(path, columns, rows, fmt="csv", *, title="", labels=None, delimiter=",",
          table_name="students") -> int:
    """Write ``rows`` (dicts keyed by ``columns``) to ``path``. ``labels``
    maps column -> heading. Returns the number of rows written."""
    if fmt not in FORMATS:
        raise ValueError(f"Unknown export format {fmt!r}")
    labels = labels or {}
    heads = [labels.get(c, c) for c in columns]
    writer = globals()[f"_{fmt}"]
    writer(path, columns, heads, rows, title=title, delimiter=delimiter, table_name=table_name)
    return len(rows)


def _csv(path, columns, heads, rows, delimiter=",", **_):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        out = csv.writer(handle, delimiter=delimiter)
        out.writerow(heads)
        out.writerows([[_cell(r.get(c)) for c in columns] for r in rows])


def _tsv(path, columns, heads, rows, **_):
    _csv(path, columns, heads, rows, delimiter="\t")


def _delimited(path, columns, heads, rows, delimiter=";", **_):
    if not delimiter or len(delimiter) != 1:
        raise ValueError("The delimiter must be one character")
    _csv(path, columns, heads, rows, delimiter=delimiter)


def _json(path, columns, heads, rows, **_):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([{c: r.get(c) for c in columns} for r in rows], handle, indent=2, default=str)


def text_table(columns, heads, rows, title="") -> str:
    widths = [min(40, max(len(str(h)), *(len(str(_cell(r.get(c)))) for r in rows)))
              if rows else len(str(h)) for c, h in zip(columns, heads)]
    line = "  ".join("-" * w for w in widths)
    out = [title, "=" * len(title), ""] if title else []
    out += ["  ".join(str(h).ljust(w)[:w] for h, w in zip(heads, widths)), line]
    out += ["  ".join(str(_cell(r.get(c))).ljust(w)[:w] for c, w in zip(columns, widths))
            for r in rows]
    out += ["", f"{len(rows)} row(s)"]
    return "\n".join(out)


def _txt(path, columns, heads, rows, title="", **_):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text_table(columns, heads, rows, title) + "\n")


def _xml(path, columns, heads, rows, table_name="students", **_):
    root = _TAG.sub("_", table_name) or "rows"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<{root} exported="{datetime.now().isoformat(timespec="seconds")}">']
    for r in rows:
        lines.append("  <row>")
        for c in columns:
            tag = _TAG.sub("_", c) or "field"
            lines.append(f"    <{tag}>{escape(str(_cell(r.get(c))))}</{tag}>")
        lines.append("  </row>")
    lines.append(f"</{root}>")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _xlsx(path, columns, heads, rows, title="", **_):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    book = Workbook()
    sheet = book.active
    sheet.title = re.sub(r"[\[\]:*?/\\]", "-", title or "Export")[:31] or "Export"
    sheet.append(heads)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for r in rows:
        sheet.append([_cell(r.get(c)) for c in columns])
    for column in sheet.columns:
        width = max(len(str(c.value or "")) for c in column)
        sheet.column_dimensions[column[0].column_letter].width = min(50, max(10, width + 2))
    sheet.freeze_panes = "A2"
    book.save(path)


def _pdf(path, columns, heads, rows, title="", **_):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=7, leading=8)
    data = [[Paragraph(f"<b>{escape(str(h))}</b>", small) for h in heads]]
    data += [[Paragraph(escape(str(_cell(r.get(c)))), small) for c in columns] for r in rows]
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=24, rightMargin=24,
                            topMargin=24, bottomMargin=24)
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [Paragraph(escape(title or "Export"), styles["Title"]),
             Paragraph(f"{len(rows)} row(s), {datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]),
             Spacer(1, 8), table]
    doc.build(story)


def _sql_value(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _sql(path, columns, heads, rows, table_name="students", **_):
    table = _TAG.sub("_", table_name) or "export"
    cols = ", ".join(f'"{_TAG.sub("_", c)}"' for c in columns)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"-- {len(rows)} row(s) exported {datetime.now().isoformat(timespec='seconds')}\n")
        for r in rows:
            values = ", ".join(_sql_value(r.get(c)) for c in columns)
            handle.write(f'INSERT INTO "{table}" ({cols}) VALUES ({values});\n')
