"""Candidate number and UCI for a student.

Both belong on the student record. Older databases do not have the
columns yet, so they are looked up with ``PRAGMA table_info`` and, when
missing or blank, the candidate number falls back to the one typed on
the student's exam entry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Column names the student record may use, most likely first.
_CANDIDATE_COLUMNS: tuple[str, ...] = (
    "candidate_number", "candidate_no", "exam_candidate_number")
_UCI_COLUMNS: tuple[str, ...] = ("uci", "unique_candidate_identifier")


@dataclass
class ExamIdentity:
    student_id: str
    candidate_no: str | None
    uci: str | None
    source: str          # "student record", "exam entry" or "none"


def _student_columns() -> tuple[str | None, str | None]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _students._connect() as conn:
        have = {r["name"] if hasattr(r, "keys") else r[1]
                for r in conn.execute("PRAGMA table_info(students)")}
    cand = next((c for c in _CANDIDATE_COLUMNS if c in have), None)
    uci = next((c for c in _UCI_COLUMNS if c in have), None)
    return cand, uci


def identities(student_ids: list[str] | None = None) -> dict[str, ExamIdentity]:
    """Candidate number / UCI for every student (or the ones given)."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    cand_col, uci_col = _student_columns()
    out: dict[str, ExamIdentity] = {}
    if cand_col or uci_col:
        cols = ", ".join(c for c in ("student_id", cand_col, uci_col) if c)
        with _students._connect() as conn:
            for r in conn.execute(f"SELECT {cols} FROM students"):
                sid = r["student_id"]
                if student_ids is not None and sid not in student_ids:
                    continue
                cand = (str(r[cand_col]).strip() if cand_col and r[cand_col] else None)
                uci = (str(r[uci_col]).strip() if uci_col and r[uci_col] else None)
                out[sid] = ExamIdentity(sid, cand or None, uci or None,
                                        "student record" if cand else "none")
    # Fall back to the most recent entry's candidate number.
    for e in _entries.list_entries():
        if student_ids is not None and e.student_id not in student_ids:
            continue
        ident = out.get(e.student_id)
        if ident is None:
            out[e.student_id] = ident = ExamIdentity(e.student_id, None, None, "none")
        if not ident.candidate_no and e.candidate_no:
            ident.candidate_no = e.candidate_no
            ident.source = "exam entry"
    return out


def identity(student_id: str, entry_candidate_no: str | None = None) -> ExamIdentity:
    """One student's candidate number and UCI.

    The student record wins; *entry_candidate_no* (the entry being
    processed) is the fallback before any other entry.
    """
    ident = identities([student_id]).get(student_id) or ExamIdentity(
        student_id, None, None, "none")
    if ident.source != "student record" and entry_candidate_no:
        ident.candidate_no = entry_candidate_no
        ident.source = "exam entry"
    return ident


def candidate_number(student_id: str, entry_candidate_no: str | None = None) -> str | None:
    return identity(student_id, entry_candidate_no).candidate_no


def find_student(candidate_no: str, *, board: str | None = None,
                 uci: str | None = None) -> str | None:
    """The student a board's candidate number (or UCI) belongs to."""
    cand = (candidate_no or "").strip().upper()
    want_uci = (uci or "").strip().upper()
    if not cand and not want_uci:
        return None
    ids = identities()
    if want_uci:
        hit = next((i.student_id for i in ids.values()
                    if i.uci and i.uci.upper() == want_uci), None)
        if hit:
            return hit
    hits = {i.student_id for i in ids.values()
            if i.candidate_no and i.candidate_no.upper() == cand}
    if len(hits) == 1:
        return hits.pop()
    if hits and board:
        # Candidate numbers are per centre, but an old typed entry can
        # collide; narrow to students entered with this board.
        from education_system.systems.sixth_form.domain.assessment.exam_entries import (
            exam_entries as _entries,
        )
        narrowed = {e.student_id for e in _entries.list_entries(exam_board=board)
                    if e.student_id in hits}
        if len(narrowed) == 1:
            return narrowed.pop()
    return None
