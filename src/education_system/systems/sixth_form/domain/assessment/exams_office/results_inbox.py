"""Watched inbox for exam board results files (A2C / EDI / CSV).

Drop the files the boards send (fetched through A2C, or downloaded as
CSV) into the inbox folder; the scheduler's "Import exam board results"
job imports each one through :func:`edi.import_results_file`, so the
results land under the results-day embargo exactly as a manual import
would — hidden from candidates until the series is released.

Folder (under the sixth form data directory)::

    exam_results_inbox/                 ← drop files here
        Summer_2026_AQA/                ← optional: a folder per series
        processed/                      ← imported files (+ .report.txt)
        failed/                         ← files that could not be imported
                                          (+ .error.txt saying why)

The series (season + year) and, for a fixed-width EDI file, the board
are read from the file name and its folder name: any of ``Summer`` /
``January`` / ``November``, a year ``20xx`` and a board name or alias
(``AQA``, ``OCR``, ``Edexcel``/``Pearson``, ``WJEC``/``Eduqas``,
``CCEA``, ``CIE``), separated by ``_``, ``-``, space or ``.``, e.g.
``AQA_Summer_2026_results.txt`` or ``Summer 2026/ocr.csv``. A CSV file
carries the board per row.

Idempotent: each file's SHA-256 is recorded, and a file whose content
was imported once is never imported again (a re-dropped copy goes to
``failed/`` saying so). A file that fails can be fixed or re-dropped —
only a successful import claims its hash.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from education_system import paths
from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

INBOX_DIRNAME = "exam_results_inbox"
PROCESSED = "processed"
FAILED = "failed"
#: A file modified more recently than this may still be being written.
SETTLE_SECONDS = 30
MAX_FILE_BYTES = 50 * 1024 * 1024

STATUS_IMPORTED = "Imported"
STATUS_FAILED = "Failed"
STATUS_DUPLICATE = "Duplicate"

_SKIP_SUFFIXES = (".part", ".tmp", ".crdownload", ".report.txt", ".error.txt")
_TOKEN_RE = re.compile(r"[\s_\-.]+")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_results_inbox_files (
    file_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256         TEXT NOT NULL,
    file_name      TEXT NOT NULL,
    status         TEXT NOT NULL,
    season         TEXT,
    year           INTEGER,
    exam_board     TEXT,
    fmt            TEXT,
    rows           INTEGER NOT NULL DEFAULT 0,
    components     INTEGER NOT NULL DEFAULT 0,
    qualifications INTEGER NOT NULL DEFAULT 0,
    problems       TEXT,
    embargo_note   TEXT,
    error          TEXT,
    moved_to       TEXT,
    processed_at   TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exams_inbox_imported_sha
    ON exams_results_inbox_files(sha256) WHERE status = 'Imported';
CREATE INDEX IF NOT EXISTS idx_exams_inbox_processed
    ON exams_results_inbox_files(processed_at DESC);
"""


def init_db() -> None:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    store.ensure("results_inbox", _SCHEMA, after=(results_day.init_db,))


def inbox_dir() -> Path:
    return Path(paths.SIXTH_FORM_DATA_DIR) / INBOX_DIRNAME


def ensure_dirs() -> Path:
    base = inbox_dir()
    for d in (base, base / PROCESSED, base / FAILED):
        d.mkdir(parents=True, exist_ok=True)
    return base


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class InboxFile:
    file_id: int
    sha256: str
    file_name: str
    status: str
    season: str | None
    year: int | None
    exam_board: str | None
    fmt: str | None
    rows: int
    components: int
    qualifications: int
    problems: str | None
    embargo_note: str | None
    error: str | None
    moved_to: str | None
    processed_at: str


@dataclass
class FileOutcome:
    name: str
    status: str
    detail: str


@dataclass
class InboxReport:
    files: list[FileOutcome] = field(default_factory=list)
    waiting: int = 0          # too new — still being written

    @property
    def imported(self) -> int:
        return sum(1 for f in self.files if f.status == STATUS_IMPORTED)

    @property
    def errors(self) -> list[str]:
        return [f"{f.name}: {f.detail}" for f in self.files
                if f.status != STATUS_IMPORTED]

    @property
    def summary(self) -> str:
        if not self.files:
            return ("Inbox empty" if not self.waiting else
                    f"{self.waiting} file(s) still being written — next run")
        parts = [f"{len(self.files)} file(s): {self.imported} imported, "
                 f"{len(self.files) - self.imported} not imported"]
        parts += [f"{f.name} — {f.detail}" for f in self.files
                  if f.status == STATUS_IMPORTED]
        return "; ".join(parts)


# ── Series from the file name ───────────────────────────────────────

@dataclass
class Series:
    season: str | None = None
    year: int | None = None
    board: str | None = None


def series_from_name(relative: Path) -> Series:
    """Season, year and board read from a file's name and folders."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
        normalise_board,
    )
    text = " ".join([*relative.parent.parts, relative.stem])
    tokens = [t for t in _TOKEN_RE.split(text) if t]
    out = Series()
    seasons = {s.lower(): s for s in _entries.SEASONS}
    for i, tok in enumerate(tokens):
        low = tok.lower()
        if out.season is None and low in seasons:
            out.season = seasons[low]
        elif out.year is None and re.fullmatch(r"20\d\d", tok):
            out.year = int(tok)
        elif out.board is None:
            pair = f"{tok} {tokens[i + 1]}" if i + 1 < len(tokens) else ""
            out.board = normalise_board(pair) or normalise_board(tok)
    return out


# ── Processing ──────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _candidates(base: Path) -> list[Path]:
    out = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(base)
        if rel.parts[0] in (PROCESSED, FAILED):
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        if p.name.lower().endswith(_SKIP_SUFFIXES):
            continue
        out.append(p)
    return out


def _move(path: Path, base: Path, folder: str, note: str) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = base / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    rel = path.relative_to(base)
    flat = "__".join(rel.parts)
    dest = dest_dir / f"{stamp}_{flat}"
    n = 1
    while dest.exists():
        dest = dest_dir / f"{stamp}_{n}_{flat}"
        n += 1
    shutil.move(str(path), str(dest))
    suffix = ".report.txt" if folder == PROCESSED else ".error.txt"
    dest.with_name(dest.name + suffix).write_text(note + "\n", encoding="utf-8")
    # Tidy an emptied series folder (never the inbox itself).
    parent = path.parent
    while parent != base and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return dest


def _record(**cols) -> int:
    keys = ", ".join(cols)
    marks = ", ".join("?" * len(cols))
    with store.connect() as conn:
        cur = conn.execute(
            f"INSERT INTO exams_results_inbox_files ({keys}) VALUES ({marks})",
            tuple(cols.values()))
        conn.commit()
        return cur.lastrowid


def _imported_before(sha: str) -> _sql.Row | None:
    with store.connect() as conn:
        return conn.execute(
            "SELECT file_id, file_name, processed_at FROM exams_results_inbox_files "
            "WHERE sha256 = ? AND status = ?", (sha, STATUS_IMPORTED)).fetchone()


def _embargo_note(season: str, year: int, boards: set[str | None]) -> str:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    notes = []
    for b in sorted(boards, key=lambda x: x or ""):
        rel = results_day.release_for(season, year, b)
        label = b or "all boards"
        if rel is None:
            notes.append(f"{label}: HELD — no results day scheduled for {season} "
                         f"{year}; results stay hidden until one is scheduled "
                         "and released")
        elif rel.released:
            notes.append(f"{label}: series already released at {rel.released_at} — "
                         "results are visible")
        else:
            notes.append(f"{label}: HELD under embargo until {rel.embargo_until}")
    return "; ".join(notes)


def _boards_in(content: str, series: Series, fmt: str) -> set[str | None]:
    if fmt == "edi":
        return {series.board}
    import csv
    import io
    from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
        normalise_board,
    )
    found: set[str | None] = set()
    reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
    col = next((c for c in (reader.fieldnames or [])
                if (c or "").strip().lower() in ("board", "exam_board",
                                                 "awarding_body", "awarding body")),
               None)
    for row in reader:
        found.add(normalise_board(row.get(col)) if col else None)
    return found or {None}


def process_file(path: Path, *, base: Path | None = None) -> FileOutcome:
    """Import one inbox file and move it to processed/ or failed/."""
    from education_system.systems.sixth_form.domain.assessment.exams_office import edi
    init_db()
    base = base or inbox_dir()
    rel = path.relative_to(base)
    name = str(rel)
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValidationError(f"File is larger than {MAX_FILE_BYTES // 1048576} MB")
        sha = _sha256(path)
    except (OSError, ValidationError) as e:
        dest = _move(path, base, FAILED, f"Could not read {name}: {e}")
        _record(sha256="", file_name=name, status=STATUS_FAILED, error=str(e),
                moved_to=str(dest))
        return FileOutcome(name, STATUS_FAILED, f"could not read: {e}")

    before = _imported_before(sha)
    if before is not None:
        why = (f"Already imported on {before['processed_at']} as "
               f"{before['file_name']!r} (inbox record #{before['file_id']}) — "
               "the same results file is never imported twice")
        dest = _move(path, base, FAILED, why)
        _record(sha256=sha, file_name=name, status=STATUS_DUPLICATE, error=why,
                moved_to=str(dest))
        return FileOutcome(name, STATUS_DUPLICATE, "already imported — not re-imported")

    series = series_from_name(rel)
    season, year = series.season, series.year
    try:
        if season is None or year is None:
            raise ValidationError(
                "Cannot tell the series from the file name — include the season "
                "(Summer/January/November) and the year, e.g. "
                "'AQA_Summer_2026_results.txt' or a 'Summer_2026' folder")
        content = path.read_bytes().decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        content = None
        err = "The file is not UTF-8 text"
    except ValidationError as e:
        content = None
        err = str(e)
    if content is None:
        dest = _move(path, base, FAILED, err)
        _record(sha256=sha, file_name=name, status=STATUS_FAILED, season=season,
                year=year, exam_board=series.board, error=err, moved_to=str(dest))
        return FileOutcome(name, STATUS_FAILED, err)

    first = next((ln for ln in content.splitlines() if ln.strip()), "")
    fmt = "csv" if "," in first else "edi"
    try:
        report = edi.import_results_file(content, season=season, year=year,
                                         fmt=fmt, exam_board=series.board)
    except (ValidationError, ValueError) as e:
        err = str(e)
        dest = _move(path, base, FAILED, err)
        _record(sha256=sha, file_name=name, status=STATUS_FAILED, season=season,
                year=year, exam_board=series.board, fmt=fmt, error=err,
                moved_to=str(dest))
        return FileOutcome(name, STATUS_FAILED, err)

    written = report.components + report.qualifications
    problems = "\n".join(report.problems)
    if written == 0:
        err = ("No result in the file could be matched to an entry"
               + (f" ({len(report.problems)} problem(s)):\n{problems}"
                  if problems else ""))
        dest = _move(path, base, FAILED, err)
        _record(sha256=sha, file_name=name, status=STATUS_FAILED, season=season,
                year=year, exam_board=series.board, fmt=fmt, rows=report.rows,
                problems=problems or None, error=err, moved_to=str(dest))
        return FileOutcome(name, STATUS_FAILED,
                           f"nothing imported ({len(report.problems)} problem(s))")

    embargo = _embargo_note(season, year, _boards_in(content, series, fmt))
    note = (f"Imported {name} ({fmt.upper()}, {season} {year}"
            f"{', ' + series.board if series.board else ''}): {report.rows} row(s), "
            f"{report.components} paper result(s), {report.qualifications} "
            f"qualification result(s).\nEmbargo: {embargo}"
            + (f"\n{len(report.problems)} row(s) not imported:\n{problems}"
               if problems else ""))
    try:
        file_id = _record(sha256=sha, file_name=name, status=STATUS_IMPORTED,
                          season=season, year=year, exam_board=series.board, fmt=fmt,
                          rows=report.rows, components=report.components,
                          qualifications=report.qualifications,
                          problems=problems or None, embargo_note=embargo)
    except _sql.IntegrityError:
        # Another instance imported the same content a moment ago.
        dest = _move(path, base, FAILED, "Imported concurrently by another instance")
        return FileOutcome(name, STATUS_DUPLICATE, "imported concurrently elsewhere")
    dest = _move(path, base, PROCESSED, note)
    with store.connect() as conn:
        conn.execute("UPDATE exams_results_inbox_files SET moved_to = ? "
                     "WHERE file_id = ?", (str(dest), file_id))
        conn.commit()
    detail = (f"{report.components} paper + {report.qualifications} qualification "
              f"result(s); {embargo}"
              + (f"; {len(report.problems)} row(s) skipped" if problems else ""))
    logger.info("Results inbox: imported %s — %s", name, detail)
    return FileOutcome(name, STATUS_IMPORTED, detail)


def process_inbox(*, settle_seconds: int = SETTLE_SECONDS) -> InboxReport:
    """Import every settled file waiting in the inbox."""
    init_db()
    base = ensure_dirs()
    report = InboxReport()
    now = time.time()
    for path in _candidates(base):
        try:
            if now - path.stat().st_mtime < settle_seconds:
                report.waiting += 1
                continue
        except OSError:
            continue
        report.files.append(process_file(path, base=base))
    return report


def list_files(*, limit: int = 200) -> list[InboxFile]:
    init_db()
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM exams_results_inbox_files "
            "ORDER BY file_id DESC LIMIT ?", (int(limit),)).fetchall()
    return [InboxFile(**{k: r[k] for k in r.keys()}) for r in rows]
