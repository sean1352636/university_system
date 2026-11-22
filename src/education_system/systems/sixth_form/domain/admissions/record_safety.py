"""Archive, merge, delete and erase applicants without losing data.

Before this, Delete and the duplicate merge hard-deleted the applicant;
the foreign-key cascade then took its GCSEs, references, documents and
conversion link with it (even for an applicant who had become a
student), and GDPR erasure was one click by anyone with the menu.

* **Archive** hides a record from every list but keeps everything;
  :func:`restore_applicant` brings it back.
* **Delete** (``admissions.delete_applicant``) is only for a record
  entered by mistake that has not progressed (:func:`delete_blockers`).
* **Merge** moves every row that belongs to the duplicate onto the kept
  record — whatever admissions table it is in — fills the kept record's
  empty fields, then archives the duplicate with ``merged_into`` set.
  Nothing is deleted.
* **Erasure** needs two people: one requests it with a reason, a second
  (governance or admin) approves, and only then is the data removed. An
  applicant who became a student is refused — their data is now the
  student record's. The erasure log keeps who/when/why and the applicant
  id only.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_erasure_requests (
    request_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id   TEXT NOT NULL,
    requested_by   TEXT NOT NULL,
    requested_at   TEXT NOT NULL DEFAULT (datetime('now')),
    reason         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Pending',
    decided_by     TEXT,
    decided_at     TEXT,
    decision_note  TEXT
);
CREATE INDEX IF NOT EXISTS idx_adm_erq_aid
    ON admissions_erasure_requests(applicant_id);

-- What was erased, by whom and why. Holds the applicant id only.
CREATE TABLE IF NOT EXISTS admissions_erasure_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id   TEXT NOT NULL,
    erased_at      TEXT NOT NULL DEFAULT (datetime('now')),
    requested_by   TEXT,
    approved_by    TEXT,
    reason         TEXT,
    rows_json      TEXT
);
"""

REQUEST_STATUSES = ("Pending", "Approved", "Rejected", "Done")

#: Applicant columns a merge copies onto the kept record when empty.
_FILL_FIELDS = ("dob", "email", "phone", "address", "previous_school",
                "predicted_gcses", "reference_name", "reference_contact")
_FILL_EXTRA = ("uln", "upn")

#: Child tables whose link is cleared, not deleted, when the applicant
#: goes (the booking/submission itself belongs to the event/form log).
_SET_NULL_TABLES = ("admissions_event_bookings", "admissions_online_submissions")

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY = True


def applicant_tables() -> list[str]:
    """Every admissions table with an ``applicant_id`` column other than
    the applicant table itself — so a table added later is merged and
    erased too."""
    init_db()
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details,
    )
    applicant_details.init_db()
    out = []
    with _adm._connect() as conn:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall()]
        for n in names:
            if n in ("admissions_applicants", "admissions_erasure_requests",
                     "admissions_erasure_log"):
                continue
            cols = {r[1] for r in conn.execute(
                f'PRAGMA table_info("{n}")').fetchall()}  # noqa: S608 — names from sqlite_master
            if "applicant_id" in cols:
                out.append(n)
    return sorted(out)


def _counts(conn: Any, applicant_id: str, tables: list[str]) -> dict[str, int]:
    out = {}
    for t in tables:
        n = conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE applicant_id = ?',  # noqa: S608
                         (applicant_id,)).fetchone()[0]
        if n:
            out[t] = n
    return out


# ── Archive ────────────────────────────────────────────────────────

def archive_applicant(applicant_id: str, *, reason: str) -> _adm.Applicant:
    _guard.require("archiving applications")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Give a reason for archiving.")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.is_archived:
        return a
    import datetime as _dt
    _adm._set_profile(applicant_id,
                      archived_at=_dt.datetime.now().isoformat(
                          timespec="seconds"),
                      archived_by=_guard.actor(), archive_reason=reason,
                      event=f"Archived: {reason}")
    out = _adm.get_applicant(applicant_id)
    assert out is not None
    return out


def restore_applicant(applicant_id: str) -> _adm.Applicant:
    _guard.require("restoring applications")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.merged_into:
        raise ValidationError(
            f"{applicant_id} was merged into {a.merged_into}; its records "
            "are there now.")
    if not a.is_archived:
        return a
    _adm._set_profile(applicant_id, archived_at=None, archived_by=None,
                      archive_reason=None, event="Restored from archive")
    out = _adm.get_applicant(applicant_id)
    assert out is not None
    return out


def list_archived() -> list[_adm.Applicant]:
    return [a for a in _adm.list_applicants(include_archived=True)
            if a.is_archived]


# ── Delete ─────────────────────────────────────────────────────────

def delete_blockers(a: _adm.Applicant) -> list[str]:
    """Why *a* cannot be deleted outright (empty = it can)."""
    out = []
    if a.status not in _adm.DELETABLE_STATUSES:
        out.append(f"status is {a.status}")
    if a.converted_student_id:
        out.append(f"linked to student {a.converted_student_id}")
    with _adm._connect() as conn:
        counts = _counts(conn, a.applicant_id, [
            t for t in applicant_tables() if t in (
                "admissions_conversions", "admissions_references",
                "admissions_applicant_gcses", "admissions_results_day",
                "admissions_offer_conditions")])
    labels = {"admissions_conversions": "conversion record",
              "admissions_references": "references",
              "admissions_applicant_gcses": "GCSE results",
              "admissions_results_day": "results-day record",
              "admissions_offer_conditions": "offer conditions"}
    out += [f"has {labels[t]}" for t in counts]
    return out


def _remove_files(applicant_id: str) -> None:
    for d in _adm.list_documents(applicant_id):
        try:
            Path(d.path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete document file %s", d.path)
    doc_dir = _adm._documents_dir() / applicant_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)


def purge_applicant_rows(applicant_id: str) -> dict[str, int]:
    """Remove the applicant and every row that belongs to it (files
    too). Internal: callers decide whether that is allowed."""
    tables = applicant_tables()
    _remove_files(applicant_id)
    with _adm._connect() as conn:
        counts = _counts(conn, applicant_id, tables)
        for t in tables:
            if t in _SET_NULL_TABLES:
                conn.execute(f'UPDATE "{t}" SET applicant_id = NULL '  # noqa: S608
                             "WHERE applicant_id = ?", (applicant_id,))
            else:
                conn.execute(f'DELETE FROM "{t}" WHERE applicant_id = ?',  # noqa: S608
                             (applicant_id,))
        conn.execute("DELETE FROM admissions_applicants WHERE applicant_id = ?",
                     (applicant_id,))
        conn.commit()
    return counts


# ── Merge ──────────────────────────────────────────────────────────

@dataclass
class MergeResult:
    kept: str
    duplicate: str
    filled: list[str] = field(default_factory=list)
    moved: dict[str, int] = field(default_factory=dict)
    left_on_duplicate: dict[str, int] = field(default_factory=dict)


def merge_applicants(keep_id: str, duplicate_id: str, *,
                     reason: str | None = None) -> MergeResult:
    """Merge *duplicate_id* into *keep_id*: nothing is deleted.

    Rows that cannot move because the kept record already has the same
    one (the same GCSE, programme choice, scorecard…) stay on the
    duplicate, which is archived with ``merged_into`` and can still be
    opened from the archive."""
    _guard.require("merging applications")
    if keep_id == duplicate_id:
        raise ValidationError("Pick two different applicants.")
    keep = _adm.get_applicant(keep_id)
    dup = _adm.get_applicant(duplicate_id)
    if keep is None or dup is None:
        raise ValidationError("Both applicants must exist.")
    if keep.is_archived or dup.is_archived:
        raise ValidationError("Restore archived applicants before merging.")
    if dup.converted_student_id and keep.converted_student_id:
        raise ValidationError(
            "Both applicants are enrolled students; link the students in "
            "the Student Directory instead.")
    if dup.converted_student_id:
        raise ValidationError(
            f"{duplicate_id} is enrolled as {dup.converted_student_id}: "
            f"merge {keep_id} into {duplicate_id} instead.")
    out = MergeResult(kept=keep_id, duplicate=duplicate_id)

    fill = {f: getattr(dup, f) for f in _FILL_FIELDS
            if getattr(dup, f) and not getattr(keep, f)}
    if fill:
        _adm.update_applicant(keep_id, fill)
        out.filled += list(fill)
    extra = {f: getattr(dup, f) for f in _FILL_EXTRA
             if getattr(dup, f) and not getattr(keep, f)}
    if extra:
        _adm._set_extra(keep_id, **extra)
        out.filled += list(extra)
    profile = {}
    for k in _adm.PROFILE_COLUMNS:
        if k in ("archived_at", "archived_by", "archive_reason",
                 "merged_into", "converting_at", "intake_year",
                 "deferred_from"):
            continue
        if k in _adm.FLAG_COLUMNS:
            if getattr(dup, k) and not getattr(keep, k):
                profile[k] = True
        elif getattr(dup, k) and not getattr(keep, k):
            profile[k] = getattr(dup, k)
    if profile:
        _adm._set_profile(keep_id, **profile)
        out.filled += list(profile)

    tables = [t for t in applicant_tables() if t != "admissions_conversions"]
    with _adm._connect() as conn:
        before = _counts(conn, duplicate_id, tables)
        for t in tables:
            conn.execute(f'UPDATE OR IGNORE "{t}" SET applicant_id = ? '  # noqa: S608
                         "WHERE applicant_id = ?", (keep_id, duplicate_id))
        after = _counts(conn, duplicate_id, tables)
        out.moved = {t: n - after.get(t, 0) for t, n in before.items()
                     if n - after.get(t, 0)}
        out.left_on_duplicate = after
        conn.execute(
            "UPDATE admissions_online_submissions SET outcome = 'Merged', "
            "handled_by = ?, handled_at = datetime('now'), notes = ? "
            "WHERE applicant_id = ? AND outcome = 'Pending'",
            (_guard.actor(), f"Merged from {duplicate_id}", keep_id))
        why = f" ({reason})" if reason else ""
        _adm._log_event(conn, keep_id,
                        f"Merged in duplicate {duplicate_id}{why}",
                        kind="update")
        _adm._log_event(conn, duplicate_id,
                        f"Merged into {keep_id}{why}", kind="update")
        conn.commit()
    import datetime as _dt
    _adm._set_profile(duplicate_id, merged_into=keep_id,
                      archived_at=_dt.datetime.now().isoformat(
                          timespec="seconds"),
                      archived_by=_guard.actor(),
                      archive_reason=f"Merged into {keep_id}")
    # Choices were moved row by row; refresh the kept record's slots
    # (only when it has stored choices — otherwise the slots are the
    # choices, and an empty list would clear them).
    try:
        stored = _adm._stored_choices(keep_id)
        if stored and out.moved.get("admissions_programme_choices"):
            _adm.set_programme_choices(keep_id, [
                {"qualification_type": c.qualification_type,
                 "subject": c.subject, "notes": c.notes} for c in stored])
    except Exception:  # noqa: BLE001 — slots are a mirror; choices are kept
        logger.warning("merge %s→%s: could not refresh subject slots",
                       duplicate_id, keep_id, exc_info=True)
    logger.info("Merged applicant %s into %s (moved %s)", duplicate_id,
                keep_id, out.moved)
    return out


# ── Erasure (two people) ───────────────────────────────────────────

@dataclass
class ErasureRequest:
    request_id: int
    applicant_id: str
    requested_by: str
    requested_at: str
    reason: str
    status: str
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None


def _req(r: Any) -> ErasureRequest:
    return ErasureRequest(**{k: r[k] for k in r.keys()})


def request_erasure(applicant_id: str, *, reason: str) -> ErasureRequest:
    init_db()
    p = _guard.require("requesting GDPR erasure")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Give the reason for erasure (e.g. the "
                              "applicant's request and its date).")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.converted_student_id:
        raise ValidationError(
            f"{applicant_id} became student {a.converted_student_id}; erase "
            "through the student's GDPR request instead.")
    with _adm._connect() as conn:
        if conn.execute(
                "SELECT 1 FROM admissions_erasure_requests WHERE "
                "applicant_id = ? AND status = 'Pending'",
                (applicant_id,)).fetchone():
            raise ValidationError("An erasure request is already waiting "
                                  "for approval.")
        cur = conn.execute(
            "INSERT INTO admissions_erasure_requests (applicant_id, "
            "requested_by, reason) VALUES (?, ?, ?)",
            (applicant_id, p.username or "?", reason))
        _adm._log_event(conn, applicant_id,
                        "GDPR erasure requested — waiting for a second "
                        "person to approve", kind="gdpr")
        conn.commit()
        r = conn.execute("SELECT * FROM admissions_erasure_requests "
                         "WHERE request_id = ?", (cur.lastrowid,)).fetchone()
    return _req(r)


def list_erasure_requests(*, status: str | None = None
                          ) -> list[ErasureRequest]:
    init_db()
    _guard.require("GDPR erasure requests")
    sql = "SELECT * FROM admissions_erasure_requests"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    with _adm._connect() as conn:
        rows = conn.execute(sql + " ORDER BY request_id DESC", args).fetchall()
    return [_req(r) for r in rows]


def can_approve_erasure() -> bool:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().can(access.GOVERNANCE)


def _decide(request_id: int, status: str, note: str | None) -> ErasureRequest:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    init_db()
    p = access.current()
    p.require(access.GOVERNANCE, "approving GDPR erasure")
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_erasure_requests "
                         "WHERE request_id = ?", (request_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No erasure request #{request_id}")
    req = _req(r)
    if req.status != "Pending":
        raise ValidationError(f"Request #{request_id} is already {req.status}.")
    if (p.username or "") == req.requested_by:
        raise ValidationError("A second person must approve the erasure.")
    with _adm._connect() as conn:
        conn.execute(
            "UPDATE admissions_erasure_requests SET status = ?, "
            "decided_by = ?, decided_at = datetime('now'), decision_note = ? "
            "WHERE request_id = ?",
            (status, p.username, (note or "").strip() or None, request_id))
        conn.commit()
    return req


def reject_erasure(request_id: int, *, note: str | None = None
                   ) -> ErasureRequest:
    req = _decide(request_id, "Rejected", note)
    with _adm._connect() as conn:
        _adm._log_event(conn, req.applicant_id,
                        "GDPR erasure request rejected"
                        + (f": {note}" if note else ""), kind="gdpr")
        conn.commit()
    return req


def approve_erasure(request_id: int, *, note: str | None = None) -> bool:
    """Approve (as a second person with governance) and erase now."""
    req = _decide(request_id, "Approved", note)
    a = _adm.get_applicant(req.applicant_id)
    if a is None:
        return False
    if a.converted_student_id:
        raise ValidationError(
            f"{a.applicant_id} became a student since the request; erase "
            "through the student's GDPR request instead.")
    _erase(a.applicant_id, requested_by=req.requested_by,
           approved_by=_guard.actor(), reason=req.reason)
    with _adm._connect() as conn:
        conn.execute("UPDATE admissions_erasure_requests SET status = 'Done' "
                     "WHERE request_id = ?", (request_id,))
        conn.commit()
    return True


def erase_if_approved(applicant_id: str) -> bool:
    """Old single-step entry point: erasure now needs a request and a
    second person's approval, so this only explains that."""
    init_db()
    _guard.require("GDPR erasure")
    if _adm.get_applicant(applicant_id) is None:
        return False
    raise ValidationError(
        "Erasure needs two people: request it with a reason, then a second "
        "person with governance access approves it (Erasure requests).")


def erase_unverified(applicant_id: str, *, reason: str) -> bool:
    """Remove an unverified online submission rejected as spam or junk.
    It was never accepted as an application, so one person may do it;
    it is still logged."""
    init_db()
    _guard.require("rejecting online applications")
    a = _adm.get_applicant(applicant_id)
    if a is None:
        return False
    if a.status != _adm.ONLINE_UNVERIFIED or a.converted_student_id:
        raise ValidationError("Only an unverified online application can be "
                              "removed this way.")
    _erase(applicant_id, requested_by=_guard.actor(),
           approved_by="(unverified online submission)", reason=reason)
    return True


def _erase(applicant_id: str, *, requested_by: str | None,
           approved_by: str | None, reason: str | None) -> None:
    with _adm._connect() as conn:
        # Open-event bookings keep the booking but lose the person.
        try:
            conn.execute(
                "UPDATE admissions_event_bookings SET attendee_name = "
                "'(erased)', student_name = NULL, email = NULL, phone = NULL, "
                "notes = NULL WHERE applicant_id = ?", (applicant_id,))
            conn.commit()
        except Exception:  # noqa: BLE001 — table not created yet
            logger.debug("No bookings table to anonymise", exc_info=True)
        # Mail sent to the applicant or their parents stays in the
        # messages log as a record that something was sent, without the
        # person: the body and addresses go.
        try:
            conn.execute(
                "UPDATE messages SET body = '(erased under GDPR)', "
                "to_name = NULL, to_address = NULL, cc_address = NULL "
                "WHERE message_id IN (SELECT message_id FROM "
                "admissions_messages WHERE applicant_id = ?)",
                (applicant_id,))
            conn.commit()
        except Exception:  # noqa: BLE001 — no messages sent / table absent
            logger.debug("No applicant messages to anonymise", exc_info=True)
    counts = purge_applicant_rows(applicant_id)
    with _adm._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_erasure_log (applicant_id, requested_by, "
            "approved_by, reason, rows_json) VALUES (?, ?, ?, ?, ?)",
            (applicant_id, requested_by, approved_by, reason,
             json.dumps(counts)))
        conn.commit()
    logger.info("GDPR erase of %s (requested by %s, approved by %s)",
                applicant_id, requested_by, approved_by)


def erasure_log(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    _guard.require("the erasure log")
    with _adm._connect() as conn:
        rows = conn.execute("SELECT * FROM admissions_erasure_log "
                            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
