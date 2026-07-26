"""Full database report generator for the Super Admin dashboard.

Produces a structured, audit-style PDF from every SQLite database in the
education system: an executive dashboard, data-quality findings, health
indicators, per-database summaries, relationship diagrams and generated
insights up front — with raw table data and empty tables pushed to appendices.

Pure data + reportlab + matplotlib (no Tk), so it can be unit-tested and run
from a background thread. The Tk dashboard calls ``generate_database_report``
and marshals progress back onto the main loop.
"""

from __future__ import annotations

import io
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless: render charts to files, never to a display
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

_EDU_ROOT = Path(__file__).resolve().parents[2]

_DB_LABELS = {
    "student_records": "University — Student Records",
    "sixthform": "Sixth Form College",
    "secondary": "Secondary School",
    "primary": "Primary School",
    "nursery": "Nursery",
    "auth": "Shared — Authentication",
    "audit": "Shared — Audit Log",
    "metrics": "Shared — Metrics",
    "tenants": "Shared — Tenants",
    "webhooks": "Shared — Webhooks",
    "lms_integrations": "Shared — LMS Integrations",
    "bank_holidays": "Shared — Bank Holidays",
    "retention": "Data Retention",
    "skills": "Skill Generator (extras)",
}

_CHART_COLORS = [
    "#1abc9c", "#3498db", "#9b59b6", "#e67e22", "#e74c3c",
    "#2ecc71", "#f1c40f", "#34495e", "#16a085", "#c0392b",
]

# Health levels: key -> (label, dot/text colour, light cell background)
_HEALTH = {
    "active": ("Active", "#27ae60", "#d5f5e3"),
    "empty": ("Mostly Empty", "#f39c12", "#fdebd0"),
    "nodata": ("No Data", "#e74c3c", "#fadbd8"),
    "error": ("Error", "#c0392b", "#fadbd8"),
}

# Values that strongly suggest placeholder / template / test records.
_PLACEHOLDERS = {
    "test", "test test", "test student", "test user", "placeholder", "demo",
    "example", "sample", "lorem ipsum", "n/a", "na", "tbd", "xxx", "asdf",
    "john doe", "jane doe", "ada lovelace", "foo", "bar", "string",
}
_PERSON_NAME_COLS = {
    "first_name", "last_name", "full_name", "student_name", "child_name",
    "pupil_name", "forename", "surname", "middle_name", "guardian_name",
    "parent_name", "staff_name", "display_name",
}
_PERSON_TABLE_HINTS = (
    "student", "pupil", "child", "staff", "user", "parent", "guardian",
    "member", "teacher", "applicant", "employee", "person",
)
_CATEGORICAL_PREFERRED = (
    "status", "state", "type", "category", "gender", "grade", "role", "level",
    "priority", "result", "outcome", "term", "year_group", "stage", "band",
)


# --------------------------------------------------------------------------- #
# Discovery + extraction
# --------------------------------------------------------------------------- #
def discover_databases(edu_root: Path | None = None) -> list[Path]:
    """Return every real .db file under the education_system tree, sorted."""
    root = Path(edu_root) if edu_root else _EDU_ROOT
    found = []
    for p in root.rglob("*.db"):
        s = str(p)
        if "__pycache__" in s or s.endswith(".bak") or ".bak-" in s or "backup" in s.lower():
            continue
        found.append(p)
    return sorted(found)


def _label_for(db_path: Path) -> str:
    return _DB_LABELS.get(db_path.stem, db_path.stem.replace("_", " ").title())


def _pick_categorical(conn, tname, columns, row_count):
    """Find a low-cardinality text column and its top values, or None."""
    order = [c for c in columns if c.lower() in _CATEGORICAL_PREFERRED]
    order += [c for c in columns if c.lower() not in _CATEGORICAL_PREFERRED]
    for c in order:
        try:
            distinct = conn.execute(f'SELECT COUNT(DISTINCT "{c}") FROM "{tname}"').fetchone()[0]
        except sqlite3.Error:
            continue
        if distinct is None or not (1 <= distinct <= 8) or distinct >= row_count:
            continue
        try:
            rows = conn.execute(
                f'SELECT "{c}", COUNT(*) AS n FROM "{tname}" '
                f'GROUP BY "{c}" ORDER BY n DESC LIMIT 6'
            ).fetchall()
        except sqlite3.Error:
            continue
        vals = [(r[0], r[1]) for r in rows if r[0] not in (None, "")]
        if vals:
            return c, vals
    return None


def collect_database_info(db_path: Path, *, max_rows_per_table: int = 50) -> dict:
    """Open a database read-only and extract structure, samples, FKs, top values."""
    info = {
        "path": str(db_path), "name": db_path.name, "label": _label_for(db_path),
        "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "tables": [], "table_count": 0, "nonempty_count": 0, "total_rows": 0,
        "error": None,
    }
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        info["table_count"] = len(names)
        for tname in names:
            rec = {"name": tname, "columns": [], "row_count": 0, "sample": [],
                   "fks": [], "top_values": None, "error": None}
            try:
                rec["columns"] = [c[1] for c in conn.execute(f'PRAGMA table_info("{tname}")')]
                try:
                    rec["fks"] = [(fk[3], fk[2], fk[4])  # (from_col, ref_table, to_col)
                                  for fk in conn.execute(f'PRAGMA foreign_key_list("{tname}")')]
                except sqlite3.Error:
                    rec["fks"] = []
                rec["row_count"] = conn.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
                if rec["row_count"] > 0:
                    info["nonempty_count"] += 1
                    info["total_rows"] += rec["row_count"]
                    cur = conn.execute(f'SELECT * FROM "{tname}" LIMIT {int(max_rows_per_table)}')
                    rec["sample"] = [list(r) for r in cur.fetchall()]
                    rec["top_values"] = _pick_categorical(conn, tname, rec["columns"], rec["row_count"])
            except sqlite3.Error as exc:
                rec["error"] = str(exc)
            info["tables"].append(rec)
    except sqlite3.Error as exc:
        info["error"] = str(exc)
    finally:
        if conn is not None:
            conn.close()
    return info


# --------------------------------------------------------------------------- #
# Analysis: health, quality, insights, relationships
# --------------------------------------------------------------------------- #
def _classify_health(info: dict) -> str:
    if info["error"]:
        return "error"
    if info["total_rows"] == 0 or info["nonempty_count"] == 0:
        return "nodata"
    ratio = info["nonempty_count"] / max(info["table_count"], 1)
    if ratio < 0.15:
        return "empty"
    return "active"


def _is_placeholder(value: str) -> bool:
    v = value.strip().lower()
    if v in _PLACEHOLDERS:
        return True
    return any(tok in v for tok in ("test ", "placeholder", "lorem", "dummy", "example"))


def scan_data_quality(infos: list[dict]) -> dict:
    """Heuristic data-quality scan over sampled rows. Returns findings + score."""
    findings = {"High": [], "Medium": [], "Low": []}
    scanned_cells = 0
    good_cells = 0

    for info in infos:
        if info["error"]:
            continue
        table_is_person = any(h in info["name"].lower() for h in _PERSON_TABLE_HINTS)
        for t in info["tables"]:
            if not t["sample"]:
                continue
            cols = t["columns"]
            lower = [c.lower() for c in cols]
            tbl_person = table_is_person or any(h in t["name"].lower() for h in _PERSON_TABLE_HINTS)

            name_idx = [i for i, c in enumerate(lower)
                        if c in _PERSON_NAME_COLS or (c == "name" and tbl_person)]
            email_idx = [i for i, c in enumerate(lower) if "email" in c]
            date_idx = [i for i, c in enumerate(lower)
                        if c == "dob" or (c.endswith("date") or "_date" in c or c == "date")]

            where = f"{info['label']} → {t['name']}"

            # Names: mixed casing + placeholders
            for i in name_idx:
                vals = [str(r[i]) for r in t["sample"] if i < len(r) and r[i] not in (None, "")]
                if not vals:
                    continue
                scanned_cells += len(t["sample"])
                good = [v for v in vals if not _is_placeholder(v)]
                good_cells += len(good)
                low = [v for v in vals if v.isalpha() and v.islower()]
                mixed = [v for v in vals if v[:1].isupper()]
                if low and mixed:
                    findings["Medium"].append(f"Mixed name capitalisation in {where} ({len(low)} lower-case)")
                ph = [v for v in vals if _is_placeholder(v)]
                if ph:
                    findings["High"].append(f"Placeholder/template names in {where} (e.g. '{ph[0]}')")

            # Emails: empty + malformed
            for i in email_idx:
                cells = [r[i] if i < len(r) else None for r in t["sample"]]
                scanned_cells += len(cells)
                empties = sum(1 for v in cells if v in (None, ""))
                present = [str(v) for v in cells if v not in (None, "")]
                good_cells += sum(1 for v in present if "@" in v)
                if empties:
                    findings["Medium"].append(f"Empty email addresses in {where} ({empties} of {len(cells)} sampled)")
                bad = [v for v in present if "@" not in v]
                if bad:
                    findings["Low"].append(f"Malformed emails in {where} ({len(bad)} sampled)")

            # Dates: missing
            for i in date_idx:
                cells = [r[i] if i < len(r) else None for r in t["sample"]]
                scanned_cells += len(cells)
                empties = sum(1 for v in cells if v in (None, ""))
                good_cells += len(cells) - empties
                if empties:
                    findings["Low"].append(f"Missing dates in {where}.{cols[i]} ({empties} sampled)")

    # De-duplicate while preserving order, then cap per priority.
    def _dedup(items, cap=14):
        seen, out = set(), []
        for it in items:
            if it not in seen:
                seen.add(it)
                out.append(it)
        extra = len(out) - cap
        return (out[:cap], extra) if extra > 0 else (out, 0)

    capped = {k: _dedup(v) for k, v in findings.items()}
    total_issues = sum(len(v) for v in findings.values())
    score = round(100 * good_cells / scanned_cells) if scanned_cells else 100
    return {
        "findings": {k: capped[k][0] for k in capped},
        "overflow": {k: capped[k][1] for k in capped},
        "total_issues": total_issues,
        "score": score,
        "scanned_cells": scanned_cells,
    }


def build_relationships(info: dict) -> tuple[str, list[str]]:
    """Return ('declared'|'inferred'|'none', lines[]) describing a table tree."""
    table_names = {t["name"] for t in info["tables"]}
    children = {}  # parent -> set(child)
    declared = False
    for t in info["tables"]:
        for (_from_col, ref_table, _to_col) in t["fks"]:
            if ref_table in table_names and ref_table != t["name"]:
                children.setdefault(ref_table, set()).add(t["name"])
                declared = True

    mode = "declared"
    if not declared:
        # Infer from "<thing>_id" columns pointing at a "<thing>"/"<thing>s" table.
        lower_map = {n.lower(): n for n in table_names}
        for t in info["tables"]:
            for c in t["columns"]:
                cl = c.lower()
                if not cl.endswith("_id") or cl in ("id",):
                    continue
                base = cl[:-3]
                ref = lower_map.get(base) or lower_map.get(base + "s") or lower_map.get(base + "es")
                if ref and ref != t["name"]:
                    children.setdefault(ref, set()).add(t["name"])
        mode = "inferred" if children else "none"

    if not children:
        return mode, []

    # Roots = referenced tables that are not themselves children, else any parent.
    all_children = set().union(*children.values()) if children else set()
    roots = [p for p in children if p not in all_children] or list(children)
    roots = sorted(roots)[:8]  # keep the diagram readable

    lines, seen = [], set()

    def walk(node, depth):
        if depth > 3 or node in seen:
            return
        seen.add(node)
        prefix = "    " * depth + ("└── " if depth else "")
        lines.append(f"{prefix}{node}")
        for child in sorted(children.get(node, []))[:12]:
            walk(child, depth + 1)

    for r in roots:
        walk(r, 0)
        lines.append("")
    return mode, lines[:40]


def generate_insights(infos: list[dict], quality: dict) -> list[str]:
    """Generate plain-language observations about the data estate."""
    out = []
    total_rows = sum(d["total_rows"] for d in infos) or 1
    total_size = sum(d["size_bytes"] for d in infos) or 1
    populated = [d for d in infos if d["total_rows"] > 0]

    if populated:
        top_rows = max(populated, key=lambda d: d["total_rows"])
        out.append(f"{top_rows['label']} holds {top_rows['total_rows'] / total_rows * 100:.0f}% "
                   f"of all rows ({top_rows['total_rows']:,} of {total_rows:,}).")
    top_size = max(infos, key=lambda d: d["size_bytes"])
    out.append(f"{top_size['label']} occupies {top_size['size_bytes'] / total_size * 100:.0f}% "
               f"of total database storage.")

    for d in infos:
        if d["table_count"] >= 30 and 0 < d["nonempty_count"] <= 2:
            out.append(f"{d['label']} defines {d['table_count']:,} tables but only "
                       f"{d['nonempty_count']} are populated — likely incomplete migration "
                       f"or test data.")
    nodata = [d for d in infos if d["total_rows"] == 0 and not d["error"]]
    if nodata:
        out.append(f"{len(nodata)} database(s) contain no data yet: "
                   f"{', '.join(d['label'] for d in nodata[:5])}.")

    # Attendance-style insight if a present/absent breakdown is available.
    for d in infos:
        for t in d["tables"]:
            if t["top_values"] and "attend" in t["name"].lower():
                col, vals = t["top_values"]
                total = sum(n for _, n in vals)
                present = sum(n for v, n in vals if str(v).lower() in ("present", "p", "present_am", "1"))
                if total and present:
                    out.append(f"{d['label']} attendance is {present / total * 100:.1f}% present "
                               f"across {total:,} sampled records.")
                break

    if quality["total_issues"]:
        out.append(f"{quality['total_issues']} data-quality issue(s) detected "
                   f"(overall data-quality score {quality['score']}%).")
    return out


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def _image(path, width_inch, max_height_inch=6.0):
    """Fresh Image flowable for a rendered PNG (safe to create on each build)."""
    img = Image(path)
    ratio = img.imageHeight / float(img.imageWidth)
    draw_w = width_inch * inch
    draw_h = draw_w * ratio
    if draw_h > max_height_inch * inch:
        scale = (max_height_inch * inch) / draw_h
        draw_w *= scale
        draw_h *= scale
    img.drawWidth, img.drawHeight = draw_w, draw_h
    return img


class _Charts:
    """Renders each chart PNG exactly once (memoised by key) so the report
    content can be laid out twice (measure + final) without re-rendering."""

    def __init__(self, tmpdir):
        self.tmpdir = tmpdir

    def hbar(self, key, labels, values, title, xlabel, width_inch=9.5, color=None, unit=""):
        path = os.path.join(self.tmpdir, f"{key}.png")
        if not os.path.exists(path):
            fig, ax = plt.subplots(figsize=(9, max(2.0, 0.4 * len(labels) + 1.0)))
            y = range(len(labels))
            bar_colors = color or (_CHART_COLORS * (len(labels) // len(_CHART_COLORS) + 1))[: len(labels)]
            ax.barh(list(y), values, color=bar_colors)
            ax.set_yticks(list(y))
            ax.set_yticklabels(labels, fontsize=9)
            ax.invert_yaxis()
            ax.set_xlabel(xlabel, fontsize=9)
            ax.set_title(title, fontsize=12, fontweight="bold")
            for i, v in enumerate(values):
                lbl = f" {v:,.1f}{unit}" if isinstance(v, float) else f" {v:,}{unit}"
                ax.text(v, i, lbl, va="center", fontsize=8)
            ax.grid(axis="x", linestyle=":", alpha=0.5)
            fig.tight_layout()
            fig.savefig(path, format="png", dpi=130, bbox_inches="tight")
            plt.close(fig)
        return _image(path, width_inch)


# --------------------------------------------------------------------------- #
# PDF building blocks
# --------------------------------------------------------------------------- #
def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("ReportTitle", parent=ss["Title"], fontSize=28, leading=32,
                          textColor=colors.HexColor("#2c3e50")))
    # TOC-tracked headings (afterFlowable bookmarks these).
    ss.add(ParagraphStyle("TOCHeading1", parent=ss["Heading1"], fontSize=17,
                          textColor=colors.HexColor("#16a085"), spaceBefore=6, spaceAfter=6))
    ss.add(ParagraphStyle("TOCHeading2", parent=ss["Heading2"], fontSize=13,
                          textColor=colors.HexColor("#2c3e50"), spaceBefore=8, spaceAfter=3))
    ss.add(ParagraphStyle("SubHeading", parent=ss["Heading2"], fontSize=11,
                          textColor=colors.HexColor("#2c3e50"), spaceBefore=8, spaceAfter=2))
    ss.add(ParagraphStyle("Cell", parent=ss["BodyText"], fontSize=7, leading=8))
    ss.add(ParagraphStyle("CellHead", parent=ss["BodyText"], fontSize=7, leading=8,
                          textColor=colors.white, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Muted", parent=ss["BodyText"], fontSize=9,
                          textColor=colors.HexColor("#7f8c8d")))
    ss.add(ParagraphStyle("Note", parent=ss["BodyText"], fontSize=8,
                          textColor=colors.HexColor("#7f8c8d"), spaceBefore=2))
    ss.add(ParagraphStyle("Insight", parent=ss["BodyText"], fontSize=10, leading=14,
                          leftIndent=10, spaceAfter=4))
    return ss


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _cell(value, style, limit=140):
    if value is None:
        text = ""
    else:
        text = str(value).replace("\n", " ").replace("\r", " ")
        if len(text) > limit:
            text = text[: limit - 1] + "…"
    return Paragraph(_esc(text), style)


def _cards_row(items, ss, card_w):
    """A row of stat cards. items = [(value, label, hexcolor), ...]."""
    cells, styles = [], []
    for col, (value, label, color) in enumerate(items):
        cstyle = ParagraphStyle(f"card{col}", parent=ss["BodyText"], alignment=1,
                                textColor=colors.white, leading=22)
        para = Paragraph(
            f'<font size=20><b>{_esc(value)}</b></font><br/>'
            f'<font size=9>{_esc(label)}</font>', cstyle)
        cells.append(para)
        styles.append(("BACKGROUND", (col, 0), (col, 0), colors.HexColor(color)))
    tbl = Table([cells], colWidths=[card_w] * len(items))
    tbl.setStyle(TableStyle(styles + [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER", (0, 0), (-2, 0), 6, colors.white),
    ]))
    return tbl


class _ReportDoc(BaseDocTemplate):
    """Doc template that records TOC-tracked headings (text, level, key, page)
    and writes PDF outline bookmarks + a page footer.

    Used for both passes: a measuring pass (records relative heading pages) and
    the final pass (writes bookmarks; page numbers already known). Headings are
    keyed sec0..secN in document order, so keys are identical across passes.
    """

    def __init__(self, filename, entries_out=None, **kw):
        super().__init__(filename, **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._footer)])
        self._key = 0
        self._entries = entries_out if entries_out is not None else []

    def afterFlowable(self, flowable):
        name = getattr(getattr(flowable, "style", None), "name", "")
        if name in ("TOCHeading1", "TOCHeading2"):
            text = flowable.getPlainText()
            level = 0 if name == "TOCHeading1" else 1
            key = f"sec{self._key}"
            self._key += 1
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=(level == 0))
            self._entries.append({"level": level, "text": text, "key": key, "page": self.page})

    def _footer(self, canv, doc):
        # Page 1 is the title; the contents page is page 2 — bookmark it so
        # "↑ Contents" return links have a target.
        if doc.page == 2:
            canv.bookmarkPage("contents")
        canv.saveState()
        canv.setFont("Helvetica", 8)
        canv.setFillColor(colors.HexColor("#95a5a6"))
        canv.drawString(doc.leftMargin, 0.3 * inch, "Education System — Database Report")
        canv.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.3 * inch, f"Page {doc.page}")
        canv.restoreState()


def _count_pages(story, **doc_kwargs):
    """Build a story to a throwaway buffer and return how many pages it spans."""
    doc = _ReportDoc(io.BytesIO(), **doc_kwargs)
    doc.build(story)
    return doc.page


def _toc_table(entries, ss, page_w, page_offset, links=True):
    """Static, clickable contents table. page_offset is added to each entry's
    (measured, relative) page to get its absolute page in the final document.

    ``links=False`` renders plain text (no <a href>) — used when measuring the
    contents page count in isolation, where the link targets don't yet exist.
    """
    rows = []
    for e in entries:
        indent = 18 if e["level"] == 1 else 4
        link_style = ParagraphStyle(
            f"toc{e['level']}", parent=ss["BodyText"],
            fontSize=10 if e["level"] == 0 else 9,
            fontName="Helvetica-Bold" if e["level"] == 0 else "Helvetica",
            leftIndent=indent, leading=15,
            textColor=colors.HexColor("#2c3e50" if e["level"] == 0 else "#5d6d7e"))
        page_style = ParagraphStyle("tocp", parent=link_style, alignment=2)
        text = _esc(e["text"])
        cell = f'<a href="#{e["key"]}" color="#2c3e50">{text}</a>' if links else text
        rows.append([Paragraph(cell, link_style),
                     Paragraph(str(e["page"] + page_offset), page_style)])
    tbl = Table(rows, colWidths=[page_w - 0.8 * inch, 0.8 * inch])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#ecf0f1")),
    ]))
    return tbl


def _basic_table(data, col_widths, header_bg="#34495e", row_alt="#f4f6f7"):
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(row_alt)]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def _fmt_size(num_bytes: int) -> str:
    val = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if val < 1024 or unit == "GB":
            return f"{val:.0f} {unit}" if unit in ("B", "KB") else f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} GB"


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def generate_database_report(
    output_path: str,
    db_paths: list | None = None,
    *,
    max_rows_per_table: int = 50,
    max_detail_cols: int = 10,
    summary_sample_rows: int = 5,
    progress_cb=None,
) -> dict:
    """Generate the structured PDF report. Returns a summary dict."""
    def _progress(frac, msg):
        if progress_cb:
            try:
                progress_cb(max(0.0, min(1.0, frac)), msg)
            except Exception:
                pass

    paths = [Path(p) for p in db_paths] if db_paths else discover_databases()
    _progress(0.02, f"Found {len(paths)} database file(s)")

    infos = []
    for i, p in enumerate(paths):
        _progress(0.02 + 0.45 * (i / max(len(paths), 1)), f"Reading {p.name}…")
        infos.append(collect_database_info(p, max_rows_per_table=max_rows_per_table))

    _progress(0.50, "Analysing data quality…")
    quality = scan_data_quality(infos)
    insights = generate_insights(infos, quality)

    totals = {
        "dbs": len(infos),
        "tables": sum(d["table_count"] for d in infos),
        "nonempty": sum(d["nonempty_count"] for d in infos),
        "empty": sum(d["table_count"] - d["nonempty_count"] for d in infos),
        "rows": sum(d["total_rows"] for d in infos),
        "size": sum(d["size_bytes"] for d in infos),
    }
    largest = max(infos, key=lambda d: d["size_bytes"]) if infos else None
    most_active = max(infos, key=lambda d: d["total_rows"]) if infos else None

    ss = _styles()
    page_w = landscape(A4)[0] - 0.8 * inch
    tmpdir = tempfile.mkdtemp(prefix="dbreport_")
    charts = _Charts(tmpdir)
    doc_kwargs = dict(
        pagesize=landscape(A4),
        leftMargin=0.4 * inch, rightMargin=0.4 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        title="Education System Database Report")

    def _ret():
        """A small right-aligned 'return to contents' link."""
        return Paragraph(
            '<a href="#contents" color="#3498db">↑ Contents</a>',
            ParagraphStyle("ret", parent=ss["Note"], alignment=2,
                           textColor=colors.HexColor("#3498db")))

    def build_content():
        """Build a FRESH content story (sections 1..Appendix B). Charts are
        memoised so calling this twice (measure + final) is cheap and produces
        identical pagination."""
        story = []

        # ---- 1. Executive summary --------------------------------------- #
        story.append(Paragraph("1. Executive Summary", ss["TOCHeading1"]))
        story.append(_cards_row([
            (f"{totals['dbs']}", "Databases", "#1abc9c"),
            (f"{totals['rows']:,}", "Total Rows", "#3498db"),
            (f"{totals['nonempty']:,}", "Active Tables", "#9b59b6"),
            (f"{quality['score']}%", "Data Quality", "#e67e22"),
        ], ss, page_w / 4))
        story.append(Spacer(1, 0.18 * inch))

        metric_rows = [
            [_cell("Metric", ss["CellHead"]), _cell("Value", ss["CellHead"])],
            ["Total Databases", f"{totals['dbs']:,}"],
            ["Total Tables", f"{totals['tables']:,}"],
            ["Tables With Data", f"{totals['nonempty']:,}"],
            ["Total Rows", f"{totals['rows']:,}"],
            ["Largest Database", largest["label"] if largest else "—"],
            ["Most Active Database", most_active["label"] if most_active else "—"],
            ["Empty Tables", f"{totals['empty']:,}"],
            ["Combined Size", _fmt_size(totals["size"])],
            ["Data Quality Score", f"{quality['score']}%"],
        ]
        mt = Table(metric_rows, colWidths=[3.0 * inch, 4.0 * inch])
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#ecf0f1")),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(mt)

        # ---- 2. Key metrics / charts ------------------------------------ #
        story.append(PageBreak())
        story.append(Paragraph("2. Key Metrics", ss["TOCHeading1"]))
        story.append(_ret())
        with_rows = sorted([d for d in infos if d["total_rows"] > 0],
                           key=lambda d: d["total_rows"], reverse=True)
        if with_rows:
            story.append(charts.hbar(
                "rows_per_db",
                [d["label"] for d in with_rows],
                [d["total_rows"] for d in with_rows],
                "Rows per database (most active first)", "Rows", 9.3))
            story.append(Spacer(1, 0.12 * inch))
        sized = sorted([d for d in infos if d["size_bytes"] > 0],
                       key=lambda d: d["size_bytes"], reverse=True)
        if sized:
            story.append(charts.hbar(
                "db_sizes", [d["label"] for d in sized],
                [d["size_bytes"] / (1024 * 1024) for d in sized],
                "Database file sizes (largest first)", "Size (MB)", 9.3,
                color="#3498db", unit=" MB"))

        # ---- 3. Data quality findings ----------------------------------- #
        story.append(PageBreak())
        story.append(Paragraph("3. Data Quality Findings", ss["TOCHeading1"]))
        story.append(_ret())
        story.append(Paragraph(
            f"Total issues found: <b>{quality['total_issues']}</b> &nbsp;·&nbsp; "
            f"Overall data-quality score: <b>{quality['score']}%</b> "
            f"(sampled {quality['scanned_cells']:,} cells)", ss["Muted"]))
        story.append(Spacer(1, 0.1 * inch))
        any_finding = False
        for prio, color in (("High", "#c0392b"), ("Medium", "#e67e22"), ("Low", "#7f8c8d")):
            items = quality["findings"][prio]
            if not items:
                continue
            any_finding = True
            story.append(Paragraph(f"{prio} Priority", ParagraphStyle(
                f"prio{prio}", parent=ss["SubHeading"], textColor=colors.HexColor(color))))
            for it in items:
                story.append(Paragraph(f"• {_esc(it)}", ss["Insight"]))
            if quality["overflow"][prio]:
                story.append(Paragraph(f"… and {quality['overflow'][prio]} more", ss["Note"]))
        if not any_finding:
            story.append(Paragraph("No data-quality issues detected in the sampled data.", ss["Muted"]))

        # ---- 4. Insights ------------------------------------------------ #
        story.append(PageBreak())
        story.append(Paragraph("4. Insights", ss["TOCHeading1"]))
        for ins in insights:
            story.append(Paragraph(f"▸ {_esc(ins)}", ss["Insight"]))
        if not insights:
            story.append(Paragraph("No notable insights generated.", ss["Muted"]))

        # ---- 5. Database inventory (with health) ------------------------ #
        story.append(PageBreak())
        story.append(Paragraph("5. Database Inventory", ss["TOCHeading1"]))
        inv = [[_cell(h, ss["CellHead"]) for h in
                ("Database", "Health", "Size", "Tables", "With Data", "Empty", "Rows")]]
        health_rows = []
        for d in infos:
            hk = _classify_health(d)
            label, _c, bg = _HEALTH[hk]
            inv.append([
                _cell(d["label"], ss["Cell"]),
                _cell(label, ss["Cell"]),
                _cell(_fmt_size(d["size_bytes"]), ss["Cell"]),
                _cell(f"{d['table_count']:,}", ss["Cell"]),
                _cell(f"{d['nonempty_count']:,}", ss["Cell"]),
                _cell(f"{d['table_count'] - d['nonempty_count']:,}", ss["Cell"]),
                _cell(f"{d['total_rows']:,}", ss["Cell"]),
            ])
            health_rows.append(bg)
        invt = Table(inv, colWidths=[2.7*inch, 1.3*inch, 0.9*inch, 0.8*inch, 0.9*inch, 0.7*inch, 0.9*inch], repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for r, bg in enumerate(health_rows, start=1):
            style.append(("BACKGROUND", (1, r), (1, r), colors.HexColor(bg)))
        invt.setStyle(TableStyle(style))
        story.append(invt)

        # ---- 6. Per-database summaries ---------------------------------- #
        for d in infos:
            story.append(PageBreak())
            hk = _classify_health(d)
            hlabel, hcolor, _bg = _HEALTH[hk]
            story.append(Paragraph(f"{d['label']}", ss["TOCHeading1"]))
            story.append(_ret())
            story.append(Paragraph(
                f'<font color="{hcolor}"><b>● {hlabel}</b></font> &nbsp;·&nbsp; '
                f"{d['name']} &nbsp;·&nbsp; {_fmt_size(d['size_bytes'])} &nbsp;·&nbsp; "
                f"{d['table_count']:,} tables &nbsp;·&nbsp; {d['nonempty_count']:,} with data "
                f"&nbsp;·&nbsp; {d['total_rows']:,} rows", ss["Muted"]))

            if d["error"]:
                story.append(Paragraph(f"Could not read database: {_esc(d['error'])}", ss["Note"]))
                continue

            nonempty = sorted([t for t in d["tables"] if t["row_count"] > 0],
                              key=lambda t: t["row_count"], reverse=True)
            if not nonempty:
                story.append(Spacer(1, 0.1 * inch))
                story.append(Paragraph("This database currently contains no data.", ss["Muted"]))
                continue

            top = nonempty[:12]
            story.append(Spacer(1, 0.08 * inch))
            story.append(charts.hbar(
                f"top_{d['name']}",
                [t["name"][:30] for t in top], [t["row_count"] for t in top],
                "Top tables by row count", "Rows", 8.6, color="#16a085"))

            # Compact populated-table inventory.
            ti = [[_cell(h, ss["CellHead"]) for h in ("Table", "Rows", "Cols")]]
            for t in nonempty:
                ti.append([_cell(t["name"], ss["Cell"]),
                           _cell(f"{t['row_count']:,}", ss["Cell"]),
                           _cell(str(len(t["columns"])), ss["Cell"])])
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph(f"Populated tables ({len(nonempty)})", ss["SubHeading"]))
            story.append(_basic_table(ti, [5.6*inch, 1.1*inch, 1.0*inch], header_bg="#16a085", row_alt="#eafaf1"))

            # Relationship diagram.
            mode, lines = build_relationships(d)
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("Relationships", ss["SubHeading"]))
            if lines:
                tag = "declared foreign keys" if mode == "declared" else "inferred from column names"
                story.append(Paragraph(f"({tag})", ss["Note"]))
                story.append(Preformatted("\n".join(lines).rstrip(),
                                          ParagraphStyle("erd", fontName="Courier", fontSize=8, leading=10)))
            else:
                story.append(Paragraph("No table relationships detected.", ss["Note"]))

        # ---- Appendix A: detailed table data ---------------------------- #
        story.append(PageBreak())
        story.append(Paragraph("Appendix A — Detailed Table Data", ss["TOCHeading1"]))
        story.append(_ret())
        story.append(Paragraph(
            f"Top values and the first {summary_sample_rows} record(s) of each populated table.",
            ss["Muted"]))
        for d in infos:
            nonempty = sorted([t for t in d["tables"] if t["row_count"] > 0],
                              key=lambda t: t["row_count"], reverse=True)
            if not nonempty:
                continue
            story.append(Paragraph(d["label"], ss["TOCHeading2"]))
            for t in nonempty:
                story.append(Paragraph(
                    f'{t["name"]} — {t["row_count"]:,} row(s), {len(t["columns"])} column(s)',
                    ss["SubHeading"]))
                # Top values block.
                if t["top_values"]:
                    col, vals = t["top_values"]
                    tv = [[_cell(f"Top values · {col}", ss["CellHead"]), _cell("Count", ss["CellHead"])]]
                    for v, n in vals:
                        tv.append([_cell(v, ss["Cell"]), _cell(f"{n:,}", ss["Cell"])])
                    story.append(_basic_table(tv, [3.5*inch, 1.2*inch], header_bg="#8e44ad", row_alt="#f5eef8"))
                    story.append(Spacer(1, 0.05 * inch))
                # First N sample rows.
                show_cols = t["columns"][:max_detail_cols]
                if show_cols and t["sample"]:
                    head = [_cell(c, ss["CellHead"]) for c in show_cols]
                    data = [head]
                    for row in t["sample"][:summary_sample_rows]:
                        data.append([_cell(row[i] if i < len(row) else "", ss["Cell"])
                                     for i in range(len(show_cols))])
                    cw = page_w / max(len(show_cols), 1)
                    story.append(_basic_table(data, [cw] * len(show_cols)))
                    notes = []
                    if t["row_count"] > summary_sample_rows:
                        notes.append(f"showing {summary_sample_rows} of {t['row_count']:,} rows")
                    if len(t["columns"]) > len(show_cols):
                        notes.append(f"+{len(t['columns']) - len(show_cols)} more column(s)")
                    if notes:
                        story.append(Paragraph("· " + "; ".join(notes), ss["Note"]))
                story.append(Spacer(1, 0.08 * inch))

        # ---- Appendix B: empty tables ----------------------------------- #
        story.append(PageBreak())
        story.append(Paragraph("Appendix B — Empty Tables", ss["TOCHeading1"]))
        story.append(_ret())
        story.append(Paragraph(
            f"{totals['empty']:,} table(s) across all databases contain no rows.", ss["Muted"]))
        for d in infos:
            empties = [t["name"] for t in d["tables"] if t["row_count"] == 0]
            if not empties:
                continue
            story.append(Paragraph(f"{d['label']} ({len(empties)})", ss["TOCHeading2"]))
            # Lay names out in a compact 3-column grid.
            per_row = 3
            grid = []
            for i in range(0, len(empties), per_row):
                chunk = empties[i:i + per_row]
                chunk += [""] * (per_row - len(chunk))
                grid.append([_cell(c, ss["Cell"]) for c in chunk])
            t = Table(grid, colWidths=[page_w / per_row] * per_row)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7e9")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#7f8c8d")),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.06 * inch))

        return story

    def _title_flowables():
        return [
            Spacer(1, 0.5 * inch),
            Paragraph("Education System", ss["ReportTitle"]),
            Paragraph("Database Audit Report", ss["Heading1"]),
            Spacer(1, 0.08 * inch),
            Paragraph(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ss["Muted"]),
        ]

    try:
        # Pass 1 — measure: lay out the content alone to capture each heading's
        # (relative) page number. Charts render here once and are reused.
        _progress(0.55, "Laying out report (measuring pages)…")
        entries = []
        mdoc = _ReportDoc(io.BytesIO(), entries_out=entries, **doc_kwargs)
        mdoc.build(build_content())

        # Measure how many pages the contents listing itself needs.
        toc_probe = [Paragraph("Contents", ss["SubHeading"]),
                     _toc_table(entries, ss, page_w, 0, links=False)]
        toc_pages = _count_pages(toc_probe, **doc_kwargs)
        page_offset = 1 + toc_pages  # title page + contents pages

        # Pass 2 — final build with title, clickable contents, then content.
        _progress(0.85, "Writing final PDF…")
        final_story = _title_flowables()
        final_story.append(PageBreak())
        final_story.append(Paragraph("Contents", ss["SubHeading"]))
        final_story.append(_toc_table(entries, ss, page_w, page_offset))
        final_story.append(PageBreak())
        final_story.extend(build_content())

        doc = _ReportDoc(output_path, **doc_kwargs)
        doc.build(final_story)
        _progress(1.0, "Done")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return {
        "output_path": output_path,
        "databases": totals["dbs"],
        "tables": totals["tables"],
        "rows": totals["rows"],
        "empty_tables": totals["empty"],
        "data_quality_score": quality["score"],
        "issues": quality["total_issues"],
        "size_bytes": totals["size"],
    }
