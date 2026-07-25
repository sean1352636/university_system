"""Domain layer for Registration Forms & Signatures (Nursery System).

The paperwork a setting must hold signed, and be able to prove *what* was
signed. Two tables:

* ``form_templates`` — the wording, **versioned**. Enrolment agreements,
  funding declarations, medicine permission, outings consent and policy
  acknowledgements. Changing the wording of a live form issues a new version
  via ``revise`` and retires the old one; it never edits history.
* ``form_submissions`` — a signed return. Each pins the template version *and*
  a hash of the exact wording (``body_hash``), plus a signature digest over
  (form, signer, timestamp). A later edit to the template therefore cannot
  silently change what a parent agreed to, and ``verify_submission`` will say
  so if anything has drifted.

``outstanding_for`` answers the question the office actually asks: which
required forms has this child not returned, or returned against wording that
has since been superseded?

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``registration_forms_cli.py``, Tk GUI in ``registration_forms_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Registration Forms & Signatures"
CATEGORY = "Children & Admissions"

TEMPLATE_PREFIX = "NFT"
SUBMISSION_PREFIX = "NFS"
ID_DIGITS = 3

FORM_TYPES = (
    "enrolment-agreement",
    "funding-declaration",
    "medicine-permission",
    "outings-consent",
    "policy-acknowledgement",
    "photo-consent",
    "emergency-treatment",
)

TEMPLATE_STATUSES = ("draft", "active", "retired")
SUBMISSION_STATUSES = ("pending", "signed", "declined", "superseded")
SOURCES = ("portal", "paper", "in-person", "email")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_RE = re.compile(r"^\d+(\.\d+)*$")


class ValidationError(ValueError):
    """Raised for invalid form / signature input."""


@dataclass
class FormTemplate:
    template_id: str
    name: str
    form_type: str
    version: str
    body: str
    required: bool
    renew_months: int | None
    status: str
    effective_from: str | None
    superseded_by: str | None
    notes: str | None

    @property
    def body_hash(self) -> str:
        return hash_body(self.body)

    @property
    def label(self) -> str:
        return f"{self.name} v{self.version}"


@dataclass
class FormSubmission:
    submission_id: str
    template_id: str
    form_type: str
    template_version: str
    body_hash: str
    pupil_id: str
    respondent_name: str
    respondent_relationship: str | None
    signature_name: str | None
    signed_at: str | None
    signature_hash: str | None
    source: str
    answers: dict[str, Any]
    status: str
    witnessed_by: str | None
    notes: str | None
    child_name: str | None = None
    template_name: str | None = None

    @property
    def is_signed(self) -> bool:
        return self.status == "signed" and bool(self.signature_hash)

    def expires_on(self, renew_months: int | None) -> str | None:
        """When this signature needs renewing, if the form has a renewal cycle."""
        if not renew_months or not self.signed_at:
            return None
        try:
            signed = _dt.date.fromisoformat(self.signed_at[:10])
        except ValueError:
            return None
        month = signed.month - 1 + renew_months
        year = signed.year + month // 12
        month = month % 12 + 1
        day = min(signed.day, _DAYS_IN_MONTH[month - 1]
                  + (1 if month == 2 and _is_leap(year) else 0))
        return _dt.date(year, month, day).isoformat()


_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


@dataclass
class FormGap:
    """A required form a child has not validly returned."""

    pupil_id: str
    child_name: str | None
    template: FormTemplate
    reason: str  # 'never-signed' | 'superseded' | 'expired' | 'declined'
    submission: FormSubmission | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for registration forms")
        raise


# ── Hashing (what makes a signature evidential) ──────────────────────────────

def hash_body(body: str) -> str:
    """Digest of the exact wording, so a template edit is always detectable."""
    return hashlib.sha256((body or "").strip().encode("utf-8")).hexdigest()


def sign_digest(body_hash: str, signature_name: str, signed_at: str,
                pupil_id: str) -> str:
    """Digest binding the wording, the signer, the child and the moment."""
    payload = "|".join((body_hash, signature_name.strip().lower(), signed_at,
                        pupil_id))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(value)


def _check_date(value: Any, label: str, *, required: bool = True) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError(f"{label} is not a real date") from e
    return v


def _check_version(value: Any) -> str:
    v = _opt(value) or "1.0"
    if not _VERSION_RE.match(v):
        raise ValidationError("Version must look like '1.0' or '2.1'")
    return v


def _bump(version: str) -> str:
    """Next minor version — '1.0' → '1.1', '2' → '2.1'."""
    parts = version.split(".")
    if len(parts) == 1:
        return f"{parts[0]}.1"
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Malformed form answers — treating as empty")
        return {}
    return out if isinstance(out, dict) else {}


def _generate_id(table: str, column: str, prefix: str) -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                f"SELECT {column} FROM {table}").fetchall()}  # noqa: S608
    except sqlite3.Error:
        logger.exception("Could not read existing ids from %s", table)
        raise
    seq = 1
    while f"{prefix}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{prefix}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        candidate = f"{prefix}{n}"
        if candidate not in existing:
            return candidate
    raise RuntimeError(f"Could not allocate a unique id for {table}")


# ── Templates ────────────────────────────────────────────────────────────────

def _template_row(r: sqlite3.Row) -> FormTemplate:
    return FormTemplate(
        template_id=r["template_id"], name=r["name"], form_type=r["form_type"],
        version=r["version"], body=r["body"], required=bool(r["required"]),
        renew_months=r["renew_months"], status=r["status"],
        effective_from=r["effective_from"], superseded_by=r["superseded_by"],
        notes=r["notes"],
    )


def list_templates(*, form_type: str | None = None,
                   status: str | None = None) -> list[FormTemplate]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if form_type:
        clauses.append("form_type = ?")
        params.append(form_type)
    if status:
        clauses.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM form_templates"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY form_type, version"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_templates failed")
        raise
    return [_template_row(r) for r in rows]


def get_template(template_id: str) -> FormTemplate | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM form_templates WHERE template_id = ?",
                (template_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_template(%s) failed", template_id)
        raise
    return _template_row(row) if row else None


def active_template(form_type: str) -> FormTemplate | None:
    """The version of a form that should be issued right now."""
    live = [t for t in list_templates(form_type=form_type, status="active")]
    if not live:
        return None
    # Highest version wins if more than one is somehow live.
    return max(live, key=lambda t: [int(p) for p in t.version.split(".")])


def _validate_template(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _opt(data.get("name"))
    if not name:
        raise ValidationError("Form name is required")
    out["name"] = name

    form_type = str(data.get("form_type") or "").strip().lower()
    if form_type not in FORM_TYPES:
        raise ValidationError("Form type must be one of: "
                              + ", ".join(FORM_TYPES))
    out["form_type"] = form_type

    body = _opt(data.get("body"))
    if not body:
        raise ValidationError("The wording being signed is required")
    out["body"] = body

    out["version"] = _check_version(data.get("version"))
    out["required"] = _as_bool(data.get("required", True))

    renew = _opt(data.get("renew_months"))
    if renew is None:
        out["renew_months"] = None
    else:
        try:
            out["renew_months"] = int(renew)
        except ValueError as e:
            raise ValidationError("Renewal months must be a whole number") from e
        if out["renew_months"] <= 0:
            raise ValidationError("Renewal months must be positive")

    status = str(data.get("status") or "active").strip().lower()
    if status not in TEMPLATE_STATUSES:
        raise ValidationError("Status must be one of: "
                              + ", ".join(TEMPLATE_STATUSES))
    out["status"] = status
    out["effective_from"] = _check_date(
        data.get("effective_from") or _today(), "Effective from")
    out["notes"] = _opt(data.get("notes"))
    return out


def create_template(data: dict[str, Any]) -> FormTemplate:
    """Publish a new form (or the first version of one)."""
    _ensure_schema()
    payload = _validate_template(data)
    tid = _generate_id("form_templates", "template_id", TEMPLATE_PREFIX)
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO form_templates (
                    template_id, name, form_type, version, body, required,
                    renew_months, status, effective_from, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tid, payload["name"], payload["form_type"], payload["version"],
                 payload["body"], int(payload["required"]),
                 payload["renew_months"], payload["status"],
                 payload["effective_from"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            f"Version {payload['version']} of {payload['form_type']} already "
            "exists — use 'revise' to issue the next version."
        ) from e
    except sqlite3.Error as e:
        logger.exception("INSERT failed for form template %s", tid)
        raise ValidationError(f"Could not create form — {e}") from e
    t = get_template(tid)
    assert t is not None
    logger.info("Created form template %s (%s v%s)", tid, t.form_type, t.version)
    return t


def revise(template_id: str, body: str, *, version: str | None = None,
           notes: str | None = None) -> FormTemplate:
    """Issue the next version of a form and retire the current one.

    The old row is left untouched so existing signatures keep pointing at the
    wording that was actually agreed.
    """
    _ensure_schema()
    old = get_template(template_id)
    if old is None:
        raise ValidationError(f"No form template with id {template_id}")
    new_body = _opt(body)
    if not new_body:
        raise ValidationError("The new wording is required")
    if hash_body(new_body) == old.body_hash:
        raise ValidationError("The wording is unchanged — nothing to revise")

    new_version = _check_version(version or _bump(old.version))
    if [int(p) for p in new_version.split(".")] <= [int(p) for p
                                                    in old.version.split(".")]:
        raise ValidationError(
            f"New version must be higher than the current v{old.version}")

    fresh = create_template({
        "name": old.name, "form_type": old.form_type, "version": new_version,
        "body": new_body, "required": old.required,
        "renew_months": old.renew_months, "status": "active",
        "effective_from": _today(),
        "notes": notes or f"Revised from v{old.version}.",
    })
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE form_templates SET status = 'retired', "
                "superseded_by = ? WHERE template_id = ?",
                (fresh.template_id, template_id))
            # Signatures against the old wording are no longer current.
            conn.execute(
                "UPDATE form_submissions SET status = 'superseded' "
                "WHERE template_id = ? AND status = 'signed'", (template_id,))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not retire form template %s", template_id)
        raise
    logger.info("Revised form %s v%s -> v%s", old.form_type, old.version,
                new_version)
    out = get_template(fresh.template_id)
    assert out is not None
    return out


def retire_template(template_id: str) -> FormTemplate:
    _ensure_schema()
    if get_template(template_id) is None:
        raise ValidationError(f"No form template with id {template_id}")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE form_templates SET status = 'retired' "
                "WHERE template_id = ?", (template_id,))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not retire form template %s", template_id)
        raise
    out = get_template(template_id)
    assert out is not None
    return out


def delete_template(template_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            signed = conn.execute(
                "SELECT COUNT(*) FROM form_submissions WHERE template_id = ?",
                (template_id,)).fetchone()[0]
            if signed:
                raise ValidationError(
                    f"{signed} signature(s) reference this version — retire it "
                    "instead of deleting, so the audit trail survives.")
            cur = conn.execute(
                "DELETE FROM form_templates WHERE template_id = ?",
                (template_id,))
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error deleting form template %s", template_id)
        raise


def version_history(form_type: str) -> list[FormTemplate]:
    """Every version of a form, oldest first — the change history."""
    rows = list_templates(form_type=form_type)
    return sorted(rows, key=lambda t: [int(p) for p in t.version.split(".")])


# ── Submissions ──────────────────────────────────────────────────────────────

_SUBMISSION_SELECT = """
SELECT s.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       t.name AS template_name
FROM form_submissions s
LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
LEFT JOIN form_templates t ON t.template_id = s.template_id
"""


def _submission_row(r: sqlite3.Row) -> FormSubmission:
    keys = r.keys()
    return FormSubmission(
        submission_id=r["submission_id"], template_id=r["template_id"],
        form_type=r["form_type"], template_version=r["template_version"],
        body_hash=r["body_hash"], pupil_id=r["pupil_id"],
        respondent_name=r["respondent_name"],
        respondent_relationship=r["respondent_relationship"],
        signature_name=r["signature_name"], signed_at=r["signed_at"],
        signature_hash=r["signature_hash"], source=r["source"],
        answers=_loads(r["answers"]), status=r["status"],
        witnessed_by=r["witnessed_by"], notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        template_name=r["template_name"] if "template_name" in keys else None,
    )


def list_submissions(*, pupil_id: str | None = None,
                     form_type: str | None = None,
                     status: str | None = None,
                     template_id: str | None = None) -> list[FormSubmission]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("s.pupil_id = ?")
        params.append(pupil_id)
    if form_type:
        clauses.append("s.form_type = ?")
        params.append(form_type)
    if status:
        clauses.append("s.status = ?")
        params.append(status)
    if template_id:
        clauses.append("s.template_id = ?")
        params.append(template_id)
    sql = _SUBMISSION_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY s.signed_at DESC, s.submission_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_submissions failed")
        raise
    return [_submission_row(r) for r in rows]


def get_submission(submission_id: str) -> FormSubmission | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SUBMISSION_SELECT + " WHERE s.submission_id = ?",
                (submission_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_submission(%s) failed", submission_id)
        raise
    return _submission_row(row) if row else None


def sign(data: dict[str, Any]) -> FormSubmission:
    """Record a signed return against a specific template version.

    The template's current wording is hashed at signing time and stored on the
    submission, so the evidence survives any later revision.
    """
    _ensure_schema()
    pupil_id = _opt(data.get("pupil_id"))
    if not pupil_id:
        raise ValidationError("Child (pupil ID) is required")

    template_id = _opt(data.get("template_id"))
    if template_id:
        template = get_template(template_id)
        if template is None:
            raise ValidationError(f"No form template with id {template_id}")
    else:
        form_type = str(data.get("form_type") or "").strip().lower()
        if form_type not in FORM_TYPES:
            raise ValidationError(
                "Give a template_id, or a form_type from: "
                + ", ".join(FORM_TYPES))
        template = active_template(form_type)
        if template is None:
            raise ValidationError(
                f"No active version of '{form_type}' to sign — publish one first")

    respondent = _opt(data.get("respondent_name"))
    if not respondent:
        raise ValidationError("Who is signing (respondent name) is required")

    status = str(data.get("status") or "signed").strip().lower()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError("Status must be one of: "
                              + ", ".join(SUBMISSION_STATUSES))

    signature_name = _opt(data.get("signature_name")) or respondent
    signed_at = _opt(data.get("signed_at")) or _now()
    if status == "signed":
        signature_hash = sign_digest(template.body_hash, signature_name,
                                     signed_at, pupil_id)
    else:
        signature_hash, signed_at = None, (
            signed_at if status == "declined" else None)

    source = str(data.get("source") or "portal").strip().lower()
    if source not in SOURCES:
        raise ValidationError("Source must be one of: " + ", ".join(SOURCES))

    answers = data.get("answers")
    if not isinstance(answers, dict):
        answers = {}

    sid = _generate_id("form_submissions", "submission_id", SUBMISSION_PREFIX)
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (pupil_id,)).fetchone():
                raise ValidationError(f"No child on roll with id {pupil_id}")
            # A fresh signature replaces any earlier one for the same form.
            conn.execute(
                "UPDATE form_submissions SET status = 'superseded' "
                "WHERE pupil_id = ? AND form_type = ? AND status = 'signed'",
                (pupil_id, template.form_type))
            conn.execute(
                """
                INSERT INTO form_submissions (
                    submission_id, template_id, form_type, template_version,
                    body_hash, pupil_id, respondent_name,
                    respondent_relationship, signature_name, signed_at,
                    signature_hash, source, answers, status, witnessed_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, template.template_id, template.form_type,
                 template.version, template.body_hash, pupil_id, respondent,
                 _opt(data.get("respondent_relationship")), signature_name,
                 signed_at, signature_hash, source, json.dumps(answers), status,
                 _opt(data.get("witnessed_by")), _opt(data.get("notes"))),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for form submission %s", sid)
        raise ValidationError(f"Could not record signature — {e}") from e
    out = get_submission(sid)
    assert out is not None
    logger.info("Recorded %s of %s v%s for pupil %s (%s)",
                status, template.form_type, template.version, pupil_id, sid)
    return out


def verify_submission(submission_id: str) -> tuple[bool, str]:
    """Re-check a signature against its stored wording hash.

    Returns ``(ok, explanation)``. A False result means the record has been
    tampered with, or the template it points at no longer matches.
    """
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission with id {submission_id}")
    if sub.status == "declined":
        return True, "Recorded as declined — no signature to verify."
    if not sub.signature_hash or not sub.signature_name or not sub.signed_at:
        return False, "No signature recorded against this submission."

    expected = sign_digest(sub.body_hash, sub.signature_name, sub.signed_at,
                           sub.pupil_id)
    if expected != sub.signature_hash:
        return False, ("Signature does not match the stored wording, signer and "
                       "timestamp — the record has been altered.")

    template = get_template(sub.template_id)
    if template is None:
        return True, ("Signature is intact, but the template version it was "
                      "signed against has been deleted.")
    if template.body_hash != sub.body_hash:
        return True, (f"Signature is intact against the v{sub.template_version} "
                      "wording, which has since been edited in place. The "
                      "submission still evidences the original text.")
    return True, (f"Signature verified against {sub.form_type} "
                  f"v{sub.template_version}, signed by {sub.signature_name} on "
                  f"{sub.signed_at[:10]}.")


def delete_submission(submission_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM form_submissions WHERE submission_id = ?",
                (submission_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting form submission %s",
                         submission_id)
        raise
    if deleted:
        logger.info("Deleted form submission %s", submission_id)
    return deleted


# ── Who still owes what ──────────────────────────────────────────────────────

def outstanding_for(pupil_id: str, *, on_day: str | None = None
                    ) -> list[FormGap]:
    """Required forms this child has not validly returned."""
    day = _check_date(on_day or _today(), "Date")
    assert day is not None
    submissions = list_submissions(pupil_id=pupil_id)
    child_name = submissions[0].child_name if submissions else None
    if child_name is None:
        with connect() as conn:
            row = conn.execute(
                "SELECT TRIM(first_name || ' ' || last_name) FROM pupils "
                "WHERE pupil_id = ?", (pupil_id,)).fetchone()
            child_name = row[0] if row else None

    gaps: list[FormGap] = []
    for form_type in FORM_TYPES:
        template = active_template(form_type)
        if template is None or not template.required:
            continue
        mine = [s for s in submissions if s.form_type == form_type]
        signed = next((s for s in mine
                       if s.status == "signed"
                       and s.template_id == template.template_id), None)
        if signed is not None:
            expiry = signed.expires_on(template.renew_months)
            if expiry and expiry < day:
                gaps.append(FormGap(pupil_id, child_name, template, "expired",
                                    signed))
            continue
        declined = next((s for s in mine if s.status == "declined"), None)
        stale = next((s for s in mine if s.status in ("signed", "superseded")),
                     None)
        if declined is not None:
            gaps.append(FormGap(pupil_id, child_name, template, "declined",
                                declined))
        elif stale is not None:
            gaps.append(FormGap(pupil_id, child_name, template, "superseded",
                                stale))
        else:
            gaps.append(FormGap(pupil_id, child_name, template, "never-signed"))
    return gaps


def all_outstanding(*, on_day: str | None = None) -> list[FormGap]:
    """Every required-form gap across every active child."""
    _ensure_schema()
    try:
        with connect() as conn:
            pupils = [r[0] for r in conn.execute(
                "SELECT pupil_id FROM pupils WHERE status = 'active' "
                "ORDER BY last_name, first_name").fetchall()]
    except sqlite3.Error:
        logger.exception("all_outstanding failed")
        raise
    out: list[FormGap] = []
    for pid in pupils:
        out.extend(outstanding_for(pid, on_day=on_day))
    return out


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_template_choices() -> list[tuple[str, str]]:
    return [(t.template_id, f"{t.label} ({t.form_type})")
            for t in list_templates(status="active")]


def summary() -> dict[str, Any]:
    """Headline counts for the forms board."""
    templates = list_templates()
    submissions = list_submissions()
    gaps = all_outstanding()
    return {
        "templates": len(templates),
        "active_templates": sum(1 for t in templates if t.status == "active"),
        "required_forms": sum(1 for t in templates
                              if t.status == "active" and t.required),
        "submissions": len(submissions),
        "signed": sum(1 for s in submissions if s.is_signed),
        "declined": sum(1 for s in submissions if s.status == "declined"),
        "superseded": sum(1 for s in submissions if s.status == "superseded"),
        "outstanding": len(gaps),
        "children_with_gaps": len({g.pupil_id for g in gaps}),
        "outstanding_by_reason": {
            reason: sum(1 for g in gaps if g.reason == reason)
            for reason in ("never-signed", "superseded", "expired", "declined")
        },
    }
