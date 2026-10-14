"""The terms this university attaches to a UCAS offer.

An offer is more than a status. It carries the grades it is conditional
on, an alternative pathway where one is allowed, a date the applicant has
to reply by, a date it expires, whether a scholarship comes with it, and
whether accommodation is guaranteed. Every one of those is *issued* — the
university decides them and tells the applicant.

They were stored only in the sixth form, in
``progression.offers.offer_details``, typed in by college staff reading a
letter. That is the right home for the four choices at institutions this
platform does not run: the college is genuinely the only party here, and
it keeps them. It was the wrong home for the choice that names *us*,
where the terms were a hand-copy of something we never actually recorded
— the university had no scholarship field, no reply deadline, nothing.

This module is where ours live. One row per sixth-form UCAS choice,
stored in ``student_records.db`` beside ``ucas_application_links``, which
is the same shape and for the same reason: the sixth form owns the
application, we own what we decided about it.

The sixth form reads these back through ``offers.get_details_for_choice``
and shows them exactly where it always showed its own, so the screens
college staff use are unchanged — they just stopped being editable for
our choices, because they are now answers rather than entries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)

__all__ = [
    "OfferTerms",
    "OfferTermsError",
    "TERM_FIELDS",
    "delete_terms",
    "get_terms",
    "save_terms",
    "terms_for_choices",
    "validate_terms",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: The issued fields, in the order a reader wants them. Named here so the
#: sixth form's read-through can project a row without restating them.
TERM_FIELDS: tuple[str, ...] = (
    "grade_requirement", "grade_alternative", "reply_deadline",
    "expiry_date", "scholarship", "accommodation_guaranteed", "notes",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_offer_terms (
    terms_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    sf_choice_id             INTEGER NOT NULL UNIQUE,
    grade_requirement        TEXT,
    grade_alternative        TEXT,
    reply_deadline           TEXT,
    expiry_date              TEXT,
    scholarship              TEXT,
    accommodation_guaranteed INTEGER NOT NULL DEFAULT 0,
    notes                    TEXT,
    issued_by                TEXT,
    issued_at                TEXT DEFAULT (datetime('now')),
    updated_at               TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ucas_terms_choice
    ON ucas_offer_terms(sf_choice_id);
CREATE INDEX IF NOT EXISTS idx_ucas_terms_deadline
    ON ucas_offer_terms(reply_deadline);
"""


@dataclass
class OfferTerms:
    terms_id: int
    sf_choice_id: int
    grade_requirement: str | None
    grade_alternative: str | None
    reply_deadline: str | None
    expiry_date: str | None
    scholarship: str | None
    accommodation_guaranteed: bool
    notes: str | None
    issued_by: str | None
    issued_at: str
    updated_at: str

    def as_dict(self) -> dict[str, Any]:
        """The issued fields alone, for a consumer that only wants terms."""
        return {f: getattr(self, f) for f in TERM_FIELDS}


class OfferTermsError(Exception):
    """Raised for invalid offer-terms input."""


# ── DB plumbing ────────────────────────────────────────────────────

_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    logger.debug("UCAS offer-terms schema ready")
    _DB_READY = True


def _row(r) -> OfferTerms:
    return OfferTerms(
        terms_id=r["terms_id"],
        sf_choice_id=r["sf_choice_id"],
        grade_requirement=r["grade_requirement"],
        grade_alternative=r["grade_alternative"],
        reply_deadline=r["reply_deadline"],
        expiry_date=r["expiry_date"],
        scholarship=r["scholarship"],
        accommodation_guaranteed=bool(r["accommodation_guaranteed"]),
        notes=r["notes"],
        issued_by=r["issued_by"],
        issued_at=r["issued_at"],
        updated_at=r["updated_at"],
    )


# ── Validation ─────────────────────────────────────────────────────

def _date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise OfferTermsError(f"{label} must be YYYY-MM-DD")
    return s


def validate_terms(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise and check a terms payload without storing it.

    Exposed so a caller can reject a malformed deadline *before* it writes
    the decision — the alternative is recording an offer and then silently
    dropping the terms attached to it.
    """
    return _validate(data)


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "grade_requirement": (data.get("grade_requirement") or "").strip() or None,
        "grade_alternative": (data.get("grade_alternative") or "").strip() or None,
        "reply_deadline": _date(data.get("reply_deadline"), "Reply deadline"),
        "expiry_date": _date(data.get("expiry_date"), "Expiry date"),
        "scholarship": (data.get("scholarship") or "").strip() or None,
        "notes": (data.get("notes") or "").strip() or None,
    }
    accom = data.get("accommodation_guaranteed")
    if isinstance(accom, str):
        accom = accom.strip().lower() in ("1", "true", "yes", "y", "on")
    out["accommodation_guaranteed"] = 1 if bool(accom) else 0

    deadline, expiry = out["reply_deadline"], out["expiry_date"]
    if deadline and expiry and expiry < deadline:
        raise OfferTermsError(
            f"The offer expires ({expiry}) before the applicant has to "
            f"reply ({deadline}).")
    return out


# ── Read ───────────────────────────────────────────────────────────

def get_terms(sf_choice_id: int) -> OfferTerms | None:
    init_db()
    conn = get_connection()
    try:
        r = conn.execute(
            "SELECT * FROM ucas_offer_terms WHERE sf_choice_id = ?",
            (sf_choice_id,),
        ).fetchone()
        return _row(r) if r else None
    finally:
        conn.close()


def terms_for_choices(sf_choice_ids) -> dict[int, OfferTerms]:
    """``{sf_choice_id: OfferTerms}`` for many choices in one roundtrip.

    The sixth form's offer directory renders every choice on one screen;
    asking per row turned a single list into one connection per applicant.
    """
    ids = sorted({int(i) for i in sf_choice_ids})
    if not ids:
        return {}
    init_db()
    out: dict[int, OfferTerms] = {}
    conn = get_connection()
    try:
        # Chunked below SQLITE_MAX_VARIABLE_NUMBER.
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            # db-audit: ignore[DBW001] - join of placeholders
            rows = conn.execute(
                f"SELECT * FROM ucas_offer_terms "  # nosec B608
                f"WHERE sf_choice_id IN ({marks})",
                chunk,
            ).fetchall()
            for r in rows:
                out[r["sf_choice_id"]] = _row(r)
    finally:
        conn.close()
    return out


# ── Write ──────────────────────────────────────────────────────────

def save_terms(sf_choice_id: int, data: dict[str, Any],
               *, issued_by: str | None = None) -> OfferTerms:
    """Issue (or re-issue) the terms attached to a UCAS choice.

    Upsert keyed on the choice, because an offer has one set of terms at a
    time — revising a deadline is the same offer, not a second one.
    """
    p = _validate(data)
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO ucas_offer_terms
                   (sf_choice_id, grade_requirement, grade_alternative,
                    reply_deadline, expiry_date, scholarship,
                    accommodation_guaranteed, notes, issued_by,
                    issued_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT(sf_choice_id) DO UPDATE SET
                   grade_requirement = excluded.grade_requirement,
                   grade_alternative = excluded.grade_alternative,
                   reply_deadline    = excluded.reply_deadline,
                   expiry_date       = excluded.expiry_date,
                   scholarship       = excluded.scholarship,
                   accommodation_guaranteed =
                       excluded.accommodation_guaranteed,
                   notes             = excluded.notes,
                   issued_by         = COALESCE(excluded.issued_by,
                                                ucas_offer_terms.issued_by),
                   updated_at        = datetime('now')""",
            (sf_choice_id, p["grade_requirement"], p["grade_alternative"],
             p["reply_deadline"], p["expiry_date"], p["scholarship"],
             p["accommodation_guaranteed"], p["notes"],
             (issued_by or "").strip() or None),
        )
        conn.commit()
    finally:
        conn.close()
    out = get_terms(sf_choice_id)
    assert out is not None
    logger.info(
        "Issued offer terms for sf choice #%d (deadline=%s, scholarship=%s, "
        "accommodation=%s, by=%s)",
        sf_choice_id, out.reply_deadline, bool(out.scholarship),
        out.accommodation_guaranteed, out.issued_by or "—")
    return out


def delete_terms(sf_choice_id: int) -> bool:
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM ucas_offer_terms WHERE sf_choice_id = ?",
            (sf_choice_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Withdrew offer terms for sf choice #%d", sf_choice_id)
            return True
        return False
    finally:
        conn.close()
