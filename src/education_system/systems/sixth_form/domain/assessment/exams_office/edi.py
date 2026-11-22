"""Exam board data files (EDI): entries export and results import.

UK boards exchange entries and results with centres as fixed-width
text files in the JCQ "Formats" (EDI) specification, usually through
the A2C application, and most also offer CSV. This module writes an
entries file per board and series and reads a results file, in either
form.

IMPORTANT: the fixed-width record layouts below are a configurable
field map, one constant per file type. They follow the shape of the
JCQ entries (header / detail / trailer) and results files, but the
exact column positions, record identifiers and widths MUST be checked
against the current JCQ Formats specification (published each year
on the JCQ website) before live use with a board, and edited here if
they differ. CSV import/export does not depend on them.

Results read here go through :func:`results_day.import_result_rows`,
so they land under the series embargo like any other import.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# The centre number boards know the college by. Set it here (or pass
# centre_number=) before producing a file for a board.
CENTRE_NUMBER: str = ""


@dataclass(frozen=True)
class Field:
    name: str
    start: int        # 1-based column
    width: int
    align: str = "left"   # left = pad right with spaces; right = zero-pad numbers

    @property
    def end(self) -> int:
        return self.start + self.width - 1


# ── Field maps (check against the current JCQ Formats spec) ─────────

# Entries file: one header record, one detail record per component
# entry, one trailer record carrying the detail count.
ENTRIES_RECORD_LENGTH: int = 80
ENTRIES_HEADER: tuple[Field, ...] = (
    Field("record_type", 1, 1),          # "H"
    Field("centre_number", 2, 5),
    Field("exam_board", 7, 12),
    Field("series", 19, 2),              # season code, see SEASON_CODES
    Field("year", 21, 4),
    Field("created", 25, 8),             # YYYYMMDD
)
ENTRIES_DETAIL: tuple[Field, ...] = (
    Field("record_type", 1, 1),          # "D"
    Field("centre_number", 2, 5),
    Field("candidate_number", 7, 4, "right"),
    Field("uci", 11, 13),
    Field("entry_code", 24, 6),
    Field("component_code", 30, 10),
    Field("tier", 40, 1),
    Field("surname", 41, 20),
    Field("forename", 61, 15),
    Field("action", 76, 1),              # A = add, W = withdraw
)
ENTRIES_TRAILER: tuple[Field, ...] = (
    Field("record_type", 1, 1),          # "T"
    Field("centre_number", 2, 5),
    Field("record_count", 7, 7, "right"),
)

# Results file: detail records only are read; header/trailer skipped.
RESULTS_DETAIL_TYPE: str = "D"
RESULTS_DETAIL: tuple[Field, ...] = (
    Field("record_type", 1, 1),
    Field("centre_number", 2, 5),
    Field("candidate", 7, 4),
    Field("uci", 11, 13),
    Field("entry_code", 24, 6),
    Field("component_code", 30, 10),
    Field("grade", 40, 12),
    Field("marks", 52, 4),
    Field("ums", 56, 4),
)

SEASON_CODES: dict[str, str] = {"Summer": "06", "January": "01", "November": "11"}

# Board identifier written into fixed-width headers (check against the
# JCQ Formats specification / the board's A2C set-up).
BOARD_EDI_CODES: dict[str, str] = {
    "Pearson (Edexcel)": "EDEXCEL", "AQA": "AQA", "OCR": "OCR",
    "WJEC/Eduqas": "WJEC", "CCEA": "CCEA", "CIE": "CIE", "Other": "OTHER"}

CSV_ENTRY_COLUMNS: tuple[str, ...] = (
    "centre_number", "exam_board", "series", "year", "candidate_number", "uci",
    "entry_code", "component_code", "tier", "surname", "forename", "status")


# ── Fixed-width helpers ─────────────────────────────────────────────

def _render(fields: tuple[Field, ...], values: dict[str, object], length: int) -> str:
    line = [" "] * length
    for f in fields:
        raw = "" if values.get(f.name) is None else str(values.get(f.name))
        cell = (raw.rjust(f.width, "0") if f.align == "right" and raw.isdigit()
                else raw.ljust(f.width))[:f.width]
        line[f.start - 1:f.end] = list(cell)
    return "".join(line).rstrip()


def _parse(fields: tuple[Field, ...], line: str) -> dict[str, str]:
    return {f.name: line[f.start - 1:f.end].strip() for f in fields}


# ── Entries export ──────────────────────────────────────────────────

@dataclass
class EntriesFile:
    exam_board: str
    season: str
    year: int
    fmt: str
    content: str
    detail_count: int
    problems: list[str]

    @property
    def suggested_name(self) -> str:
        board = "".join(c for c in self.exam_board if c.isalnum())
        ext = "csv" if self.fmt == "csv" else "txt"
        return f"entries_{board}_{self.season}{self.year}.{ext}"


def export_entries(exam_board: str, season: str, year: int, *, fmt: str = "edi",
                   centre_number: str | None = None,
                   include_withdrawn: bool = True) -> EntriesFile:
    """Build a board's entries file for a series (``fmt`` = "edi" or "csv").

    Candidate numbers and UCIs come from the student record (falling
    back to the entry). Rows missing a candidate number are listed in
    ``problems`` — boards reject them.
    """
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        candidates,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    board = store.board(exam_board)
    season, year = store.season_year(season, year)
    if fmt not in ("edi", "csv"):
        raise ValidationError("Format must be 'edi' or 'csv'")
    centre = (centre_number or CENTRE_NUMBER or "").strip()
    problems: list[str] = []
    if not centre:
        problems.append("No centre number set (edi.CENTRE_NUMBER or centre_number=)")
    entries = [e for e in _entries.list_entries(exam_board=board, season=season, year=year)
               if include_withdrawn or e.status != "Withdrawn"]
    ids = candidates.identities(sorted({e.student_id for e in entries}))
    people = {s.student_id: s for s in _students.list_students()}
    details: list[dict[str, object]] = []
    for e in sorted(entries, key=lambda x: (x.candidate_no or "", x.paper_code)):
        ident = ids.get(e.student_id)
        cand = (ident.candidate_no if ident else None) or e.candidate_no
        if not cand:
            problems.append(f"{e.student_id} {e.paper_code}: no candidate number")
        s = people.get(e.student_id)
        details.append({
            "centre_number": centre, "exam_board": board,
            "series": SEASON_CODES.get(season, season), "year": year,
            "candidate_number": cand or "", "uci": (ident.uci if ident else "") or "",
            "entry_code": e.entry_code or "", "component_code": e.paper_code,
            "tier": (e.tier or "")[:1], "surname": (s.last_name if s else "").upper(),
            "forename": (s.first_name if s else "").upper(),
            "status": e.status,
            "action": "W" if e.status == "Withdrawn" else "A",
        })
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(CSV_ENTRY_COLUMNS), extrasaction="ignore")
        w.writeheader()
        for d in details:
            w.writerow(d)
        content = buf.getvalue()
    else:
        import datetime as _dt
        lines = [_render(ENTRIES_HEADER, {
            "record_type": "H", "centre_number": centre,
            "exam_board": BOARD_EDI_CODES.get(board, board),
            "series": SEASON_CODES.get(season, season), "year": year,
            "created": _dt.date.today().strftime("%Y%m%d")}, ENTRIES_RECORD_LENGTH)]
        lines += [_render(ENTRIES_DETAIL, {"record_type": "D", **d}, ENTRIES_RECORD_LENGTH)
                  for d in details]
        lines.append(_render(ENTRIES_TRAILER, {
            "record_type": "T", "centre_number": centre,
            "record_count": str(len(details))}, ENTRIES_RECORD_LENGTH))
        content = "\r\n".join(lines) + "\r\n"
    logger.info("Built %s entries file for %s %s %d: %d record(s)", fmt, board, season,
                year, len(details))
    return EntriesFile(board, season, year, fmt, content, len(details), problems)


# ── Results import ──────────────────────────────────────────────────

def parse_results_edi(content: str, *, exam_board: str) -> list[tuple[int, dict[str, str]]]:
    """Detail records of a fixed-width results file as import rows."""
    board = store.board(exam_board)
    rows = []
    for n, line in enumerate(content.splitlines(), start=1):
        if not line.strip() or not line.startswith(RESULTS_DETAIL_TYPE):
            continue
        rec = _parse(RESULTS_DETAIL, line)
        rec["board"] = board
        rows.append((n, rec))
    return rows


def import_results_file(content: str, *, season: str, year: int, fmt: str = "auto",
                        exam_board: str | None = None, dry_run: bool = False):
    """Import a board results file (EDI fixed-width or CSV).

    ``fmt="auto"`` treats a file whose first line contains a comma as CSV.
    An EDI file carries no board name per record, so ``exam_board`` is
    required for it.
    """
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    first = next((ln for ln in content.splitlines() if ln.strip()), "")
    if fmt == "auto":
        fmt = "csv" if "," in first else "edi"
    if fmt == "csv":
        return results_day.import_results_csv(content, season=season, year=year,
                                              dry_run=dry_run)
    if fmt != "edi":
        raise ValidationError("Format must be 'auto', 'edi' or 'csv'")
    if not exam_board:
        raise ValidationError("Pick the board the EDI results file came from")
    rows = parse_results_edi(content, exam_board=exam_board)
    if not rows:
        raise ValidationError(
            f"No '{RESULTS_DETAIL_TYPE}' detail records found — check the file and the "
            "RESULTS_DETAIL field map against the JCQ Formats specification")
    return results_day.import_result_rows(rows, season=season, year=year, dry_run=dry_run)
