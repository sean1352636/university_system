"""Public online application — submission, throttling and staff verification.

The public endpoint (``api/sixth_form/routes/applications_routes.py``)
hands the posted form to :func:`submit`. Nothing is trusted:

* only the fields in :data:`FIELD_LIMITS` are read, each length-capped;
  anything else in the body is refused;
* the same validators as the staff form are applied, plus a privacy
  notice acknowledgement;
* submissions are throttled per client (hashed IP, never stored raw)
  across processes via the submissions table. The hash is salted with a
  secret (:func:`apply_salt`): ``SIXTHFORM_APPLY_SALT`` or the file
  ``var/secrets/sixthform_apply_salt``; a development fallback exists
  only when ``APP_ENV`` names a development/test environment — unset
  ``APP_ENV`` is production, where a missing salt refuses submissions
  rather than hashing addresses with a public value;
* a honeypot field (:data:`HONEYPOT_FIELD`, hidden on the web form) that
  a person never fills: a submission with it set is accepted with a
  normal-looking reference and silently dropped;
* the throttle check, the submission row and the applicant are tied
  together: the submission row is reserved (with the throttle check)
  in one transaction, and if the applicant cannot be created or linked
  everything written is removed again — a submission can never exist
  without staff being able to see it;
* the applicant is e-mailed a confirmation with their reference
  (:func:`admissions_comms.send_application_received`); a mail failure
  never fails the submission;
* consent to contact the previous school, parent/carer agreement and an
  optional parent/carer contact are stored through
  :mod:`applicant_details`;
* the applicant is created with status ``Online - unverified`` and
  source "Online Application"; nothing about existing records is ever
  returned — possible duplicates (the admissions dedupe: same email, or
  same name + date of birth) are only recorded for staff.

Staff then :func:`verify` (→ "Submitted"), :func:`merge_into` an existing
applicant flagged as a duplicate, or :func:`reject` it as spam/invalid.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import os
import secrets
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError


class RateLimited(Exception):
    """Too many submissions from this client recently."""


#: Accepted fields and their maximum lengths.
FIELD_LIMITS: dict[str, int] = {
    "first_name": 60, "last_name": 60, "dob": 10, "email": 120,
    "phone": 30, "address": 300, "previous_school": 120,
    "predicted_gcses": 500, "subject_1": 80, "subject_2": 80,
    "subject_3": 80, "reference_name": 120, "reference_contact": 120,
    "uln": 10, "personal_statement": 4000,
    "parent_name": 120, "parent_relationship": 40, "parent_email": 120,
    "parent_phone": 30,
}
#: Hidden field a person never fills; bots that fill every input do.
HONEYPOT_FIELD: str = "website"
#: Structured fields (not plain strings).
STRUCTURED_FIELDS: tuple[str, ...] = ("programme_choices",
                                      "privacy_notice_accepted",
                                      "consent_contact_school",
                                      "parent_consent")
_BOOL_FIELDS: tuple[str, ...] = ("consent_contact_school", "parent_consent")
MAX_CHOICES: int = 6
#: Persisted throttle: submissions per hashed client per window.
MAX_PER_WINDOW: int = 5
WINDOW_HOURS: int = 24

OUTCOMES: tuple[str, ...] = ("Pending", "Verified", "Merged", "Rejected")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_online_submissions (
    submission_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_no   TEXT NOT NULL UNIQUE,
    applicant_id   TEXT,
    client_hash    TEXT NOT NULL,
    submitted_at   TEXT NOT NULL DEFAULT (datetime('now')),
    duplicate_of   TEXT,
    outcome        TEXT NOT NULL DEFAULT 'Pending',
    handled_by     TEXT,
    handled_at     TEXT,
    notes          TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_adm_online_client
    ON admissions_online_submissions(client_hash, submitted_at);
"""


@dataclass
class Submission:
    submission_id: int
    reference_no: str
    applicant_id: str | None
    client_hash: str
    submitted_at: str
    duplicate_of: str | None
    outcome: str
    handled_by: str | None
    handled_at: str | None
    notes: str | None

    @property
    def duplicates(self) -> list[str]:
        return [d for d in (self.duplicate_of or "").split(",") if d]


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    return _adm._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _adm.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _row(r: db.Row) -> Submission:
    return Submission(**{k: r[k] for k in r.keys()})


#: Environments where a missing salt may fall back to a fixed dev value.
_DEV_ENVIRONMENTS: tuple[str, ...] = ("development", "dev", "local", "test",
                                      "testing")
SALT_ENV: str = "SIXTHFORM_APPLY_SALT"
SALT_FILE_NAME: str = "sixthform_apply_salt"
_salt_cache: str | None = None


class SaltNotConfigured(RuntimeError):
    """No salt in production: refuse rather than hash with a public value."""


def apply_salt() -> str:
    """The secret salting client hashes (and the applicant-portal code
    hashes). Read lazily: ``SIXTHFORM_APPLY_SALT``, then
    ``var/secrets/sixthform_apply_salt``; in a development/test
    ``APP_ENV`` only, a fixed development value. Unset ``APP_ENV`` is
    production and raises :class:`SaltNotConfigured`."""
    global _salt_cache
    env = os.environ.get(SALT_ENV, "").strip()
    if env:
        return env
    if _salt_cache:
        return _salt_cache
    from education_system import paths
    try:
        value = (paths.PLATFORM_SECRETS_DIR / SALT_FILE_NAME).read_text(
            encoding="utf-8").strip()
    except OSError:
        value = ""
    if value:
        _salt_cache = value
        return value
    if os.getenv("APP_ENV", "production").strip().lower() in _DEV_ENVIRONMENTS:
        return "sixthform-online-apply-dev-only"
    raise SaltNotConfigured(
        f"{SALT_ENV} (or var/secrets/{SALT_FILE_NAME}) must be set in "
        "production: without it client hashes use a public value.")


def client_hash(client_ip: str | None) -> str:
    """One-way hash of the client address (the raw IP is never stored),
    keyed with :func:`apply_salt` so the hashes cannot be matched against
    a list of addresses."""
    import hmac
    return hmac.new(apply_salt().encode(), (client_ip or "-").encode(),
                    hashlib.sha256).hexdigest()


def _new_reference(conn: db.Connection) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O/1/I
    for _ in range(20):
        ref = "OA-" + "".join(secrets.choice(alphabet) for _ in range(8))
        if not conn.execute("SELECT 1 FROM admissions_online_submissions "
                            "WHERE reference_no = ?", (ref,)).fetchone():
            return ref
    raise RuntimeError("Could not generate a unique reference number")


# ── Validation ─────────────────────────────────────────────────────

def clean(body: Any) -> dict[str, Any]:
    """Strictly validate a submitted form. Raises ValidationError with
    every problem listed (field names only — nothing from the database)."""
    if not isinstance(body, dict):
        raise ValidationError("The application must be a JSON object")
    unknown = sorted(set(body) - set(FIELD_LIMITS) - set(STRUCTURED_FIELDS)
                     - {HONEYPOT_FIELD})
    if unknown:
        raise ValidationError("Unknown field(s): " + ", ".join(unknown[:10]))
    errors: list[str] = []
    out: dict[str, Any] = {}
    for key, limit in FIELD_LIMITS.items():
        v = body.get(key)
        if v is None:
            continue
        if not isinstance(v, str):
            errors.append(f"{key} must be text")
            continue
        v = v.strip()
        if len(v) > limit:
            errors.append(f"{key} is longer than {limit} characters")
            continue
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in v):
            errors.append(f"{key} contains control characters")
            continue
        out[key] = v
    for key in ("first_name", "last_name", "dob", "email", "phone",
                "previous_school", "predicted_gcses"):
        if not out.get(key):
            errors.append(f"{key} is required")
    if body.get("privacy_notice_accepted") is not True:
        errors.append("privacy_notice_accepted must be true")
    for key in _BOOL_FIELDS:
        v = body.get(key)
        if v is None:
            continue
        if not isinstance(v, bool):
            errors.append(f"{key} must be true or false")
            continue
        out[key] = v
    if any(out.get(k) for k in ("parent_name", "parent_relationship",
                                "parent_email", "parent_phone")):
        from education_system.systems.sixth_form.domain.admissions import (
            applicant_details as _det,
        )
        if not out.get("parent_name"):
            errors.append("parent_name is required for a parent/carer contact")
        if not (out.get("parent_email") or out.get("parent_phone")):
            errors.append("parent_email or parent_phone is required for a "
                          "parent/carer contact")
        rel = out.get("parent_relationship")
        if rel and rel not in _det.CONTACT_RELATIONSHIPS:
            errors.append("parent_relationship must be one of: "
                          + ", ".join(_det.CONTACT_RELATIONSHIPS))
        for key, fn in (("parent_email", _adm._validate_email),
                        ("parent_phone", _adm._validate_phone)):
            if out.get(key):
                try:
                    fn(out[key])
                except ValidationError as e:
                    errors.append(f"{key}: {e}")
    choices = body.get("programme_choices")
    if choices is not None:
        if not isinstance(choices, list) or len(choices) > MAX_CHOICES:
            errors.append(f"programme_choices must be a list of at most "
                          f"{MAX_CHOICES}")
        else:
            cleaned = []
            for i, c in enumerate(choices, 1):
                if not (isinstance(c, dict)
                        and set(c) <= {"qualification_type", "subject"}
                        and isinstance(c.get("subject"), str)
                        and isinstance(c.get("qualification_type", "A Level"),
                                       str)
                        and 0 < len(c["subject"].strip()) <= 80
                        and len(c.get("qualification_type") or "") <= 40):
                    errors.append(f"programme_choices[{i}] is invalid")
                    continue
                cleaned.append({"qualification_type":
                                (c.get("qualification_type") or "A Level").strip(),
                                "subject": c["subject"].strip()})
            out["programme_choices"] = cleaned
    if not (out.get("subject_1") or out.get("programme_choices")):
        errors.append("subject_1 or programme_choices is required")
    # Field formats, using the staff-form validators.
    for key, fn in (("dob", lambda v: _adm._validate_date(v, "dob")),
                    ("email", _adm._validate_email),
                    ("phone", _adm._validate_phone)):
        if out.get(key):
            try:
                fn(out[key])
            except ValidationError as e:
                errors.append(str(e))
    if out.get("dob"):
        try:
            age = (_dt.date.today() - _dt.date.fromisoformat(out["dob"])).days / 365.25
            if not 14 <= age <= 25:
                errors.append("dob is outside the sixth-form age range")
        except ValueError:
            pass
    if out.get("uln"):
        try:
            from education_system.systems.sixth_form.domain.academics.qualifications import (
                identifiers,
            )
            out["uln"] = identifiers.validate_uln(out["uln"])
        except ImportError:
            pass
        except ValueError as e:
            errors.append(str(e))
    if errors:
        raise ValidationError("; ".join(errors))
    return out


# ── Submission ─────────────────────────────────────────────────────

def _check_throttle(conn: db.Connection, chash: str) -> None:
    since = (_dt.datetime.utcnow()
             - _dt.timedelta(hours=WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    n = conn.execute(
        "SELECT COUNT(*) FROM admissions_online_submissions "
        "WHERE client_hash = ? AND submitted_at >= ?", (chash, since)
    ).fetchone()[0]
    if n >= MAX_PER_WINDOW:
        raise RateLimited("Too many applications from this connection")


def submit(body: Any, *, client_ip: str | None = None) -> str:
    """Create an unverified applicant from a public form. Returns only
    the reference number. Runs as the ``system:online-form`` principal
    (nobody is signed in on the public form)."""
    if isinstance(body, dict) and str(body.get(HONEYPOT_FIELD) or "").strip():
        # A bot filled the hidden field: answer exactly as for a real
        # submission so it learns nothing, and keep nothing.
        logger.info("Online application dropped: honeypot field filled")
        return "OA-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
                               for _ in range(8))
    from education_system.systems.sixth_form.domain.admissions import _guard
    with _guard.system_actor("online-form"):
        return _submit(body, client_ip=client_ip)


def _reserve(chash: str) -> tuple[int, str]:
    """Throttle check and submission-row reservation in one write
    transaction, so concurrent posts cannot both slip under the limit."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _check_throttle(conn, chash)
        ref = _new_reference(conn)
        cur = conn.execute(
            "INSERT INTO admissions_online_submissions "
            "(reference_no, applicant_id, client_hash, notes) "
            "VALUES (?, NULL, ?, 'Reserved — applicant being created')",
            (ref, chash))
        conn.commit()
        return int(cur.lastrowid), ref
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _release(submission_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM admissions_online_submissions "
                     "WHERE submission_id = ? AND applicant_id IS NULL",
                     (submission_id,))
        conn.commit()


def _submit(body: Any, *, client_ip: str | None) -> str:
    init_db()
    data = clean(body)
    chash = client_hash(client_ip)
    payload: dict[str, Any] = {
        k: data.get(k) for k in (
            "first_name", "last_name", "dob", "email", "phone", "address",
            "previous_school", "predicted_gcses", "subject_1", "subject_2",
            "subject_3", "reference_name", "reference_contact")}
    payload["application_source"] = "Online Application"
    payload["submitted_at"] = _dt.date.today().isoformat()
    payload["status"] = _adm.ONLINE_UNVERIFIED
    if data.get("programme_choices"):
        # Validate every choice before anything is written, so a bad
        # choice cannot leave a half-created applicant behind.
        for i, c in enumerate(data["programme_choices"]):
            _adm._normalise_choice(c, i)
        payload["programme_choices"] = data["programme_choices"]
    if data.get("personal_statement"):
        payload["notes"] = "Personal statement (online form):\n" + \
            data["personal_statement"]
    dupes = _adm.find_duplicates(email=payload["email"],
                                 first_name=payload["first_name"],
                                 last_name=payload["last_name"],
                                 dob=payload["dob"])
    submission_id, ref = _reserve(chash)
    try:
        applicant = _adm.create_applicant(payload, allow_duplicate=True)
    except BaseException:
        _release(submission_id)
        raise
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE admissions_online_submissions SET applicant_id = ?, "
                "duplicate_of = ?, notes = NULL WHERE submission_id = ?",
                (applicant.applicant_id,
                 ",".join(d.applicant_id for d in dupes) or None,
                 submission_id))
            _adm._log_event(conn, applicant.applicant_id,
                            f"Online application {ref} received — awaiting "
                            "staff verification"
                            + (f"; possible duplicate of "
                               f"{', '.join(d.applicant_id for d in dupes)}"
                               if dupes else ""), kind="create")
            conn.commit()
    except BaseException:
        # Never leave an applicant staff cannot find from the queue.
        logger.exception("Online application %s: linking failed — undoing",
                         ref)
        from education_system.systems.sixth_form.domain.admissions import (
            record_safety,
        )
        record_safety.purge_applicant_rows(applicant.applicant_id)
        _release(submission_id)
        raise
    aid = applicant.applicant_id
    _after_submit(aid, ref, data)
    logger.info("Online application %s → applicant %s (duplicates: %d)",
                ref, aid, len(dupes))
    return ref


def _after_submit(aid: str, ref: str, data: dict[str, Any]) -> None:
    """Extras stored once the application is safely visible. Each one is
    best-effort: a failure is logged (and noted on the timeline) but never
    loses the submission."""
    from education_system.systems.sixth_form.domain.admissions import (
        admissions_comms,
        applicant_details,
    )

    def _note(what: str) -> None:
        try:
            with _connect() as conn:
                _adm._log_event(conn, aid, f"Online form: {what} could not be "
                                "stored — check with the applicant",
                                kind="update")
                conn.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Online application %s: timeline note failed",
                             ref)

    if data.get("uln"):
        try:
            _adm._set_extra(aid, uln=data["uln"])
        except Exception:  # noqa: BLE001
            logger.exception("Online application %s: ULN not stored", ref)
            _note("the ULN")
    consents = {k: data[k] for k in _BOOL_FIELDS if k in data}
    if consents:
        try:
            applicant_details.update_profile(aid, **consents)
        except Exception:  # noqa: BLE001
            logger.exception("Online application %s: consents not stored", ref)
            _note("the consent answers")
    if data.get("parent_name"):
        try:
            applicant_details.add_contact(aid, {
                "name": data["parent_name"],
                "relationship": data.get("parent_relationship"),
                "email": data.get("parent_email"),
                "phone": data.get("parent_phone"),
                "parental_responsibility": True,
                "receives_correspondence": True,
            })
        except Exception:  # noqa: BLE001
            logger.exception("Online application %s: parent contact not "
                             "stored", ref)
            _note("the parent/carer contact")
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            entry_requirements as _er,
        )
        _er.import_predicted_from_text(aid, source="Online")
    except Exception:  # noqa: BLE001
        logger.exception("Online application %s: predicted GCSEs not read",
                         ref)
    try:
        admissions_comms.send_application_received(aid, reference_no=ref)
    except Exception:  # noqa: BLE001 — the confirmation must not fail the form
        logger.exception("Online application %s: confirmation e-mail not "
                         "queued", ref)


# ── Staff verification ─────────────────────────────────────────────

def get_submission(*, applicant_id: str | None = None,
                   reference_no: str | None = None) -> Submission | None:
    init_db()
    if applicant_id:
        sql, arg = "applicant_id = ?", applicant_id
    elif reference_no:
        sql, arg = "reference_no = ?", reference_no.strip().upper()
    else:
        return None
    with _connect() as conn:
        r = conn.execute(f"SELECT * FROM admissions_online_submissions "
                         f"WHERE {sql} ORDER BY submission_id DESC LIMIT 1",
                         (arg,)).fetchone()
    return _row(r) if r else None


def pending() -> list[tuple[Submission, _adm.Applicant]]:
    """Unverified online applications, oldest first."""
    init_db()
    out = []
    for a in _adm.list_applicants(status=_adm.ONLINE_UNVERIFIED):
        s = get_submission(applicant_id=a.applicant_id)
        if s is None:
            continue
        out.append((s, a))
    out.sort(key=lambda t: t[0].submitted_at)
    return out


def current_duplicates(applicant_id: str) -> list[_adm.Applicant]:
    """Re-run the dedupe now (records may have changed since submission)."""
    a = _adm.get_applicant(applicant_id)
    if a is None:
        return []
    return _adm.find_duplicates(email=a.email, first_name=a.first_name,
                                last_name=a.last_name, dob=a.dob,
                                exclude_id=applicant_id)


def _close(applicant_id: str, outcome: str, by: str | None,
           notes: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_online_submissions SET outcome = ?, "
            "handled_by = ?, handled_at = datetime('now'), notes = ? "
            "WHERE applicant_id = ? AND outcome = 'Pending'",
            (outcome, by, (notes or "").strip() or None, applicant_id))
        conn.commit()


def verify(applicant_id: str, *, by: str | None = None,
           notes: str | None = None) -> _adm.Applicant:
    """Staff have checked the application: it joins the pipeline."""
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.status != _adm.ONLINE_UNVERIFIED:
        raise ValidationError(f"{applicant_id} is not an unverified online "
                              f"application (status: {a.status})")
    out = _adm.set_status(applicant_id, "Submitted", decision_by=None)
    _close(applicant_id, "Verified", by, notes)
    _adm.add_note(applicant_id, "Online application verified"
                  + (f": {notes}" if notes else ""), author=by)
    return out


def reject(applicant_id: str, *, by: str | None = None,
           reason: str = "Invalid or spam online application") -> bool:
    """Throw away an invalid/spam submission (the applicant is erased)."""
    a = _adm.get_applicant(applicant_id)
    if a is None:
        return False
    if a.status != _adm.ONLINE_UNVERIFIED:
        raise ValidationError("Only unverified online applications can be "
                              "rejected here")
    _close(applicant_id, "Rejected", by, reason)
    logger.info("Online application %s rejected by %s: %s", applicant_id,
                by or "?", reason)
    from education_system.systems.sixth_form.domain.admissions import (
        record_safety,
    )
    return record_safety.erase_unverified(applicant_id, reason=reason)


def merge_into(applicant_id: str, keep_id: str, *,
               by: str | None = None) -> _adm.Applicant:
    """The submission duplicates ``keep_id``: everything it holds moves to
    the kept record (see :func:`record_safety.merge_applicants`) and the
    submission is archived as merged."""
    dup = _adm.get_applicant(applicant_id)
    if dup is None or _adm.get_applicant(keep_id) is None:
        raise ValidationError("Both applicants must exist")
    if dup.status != _adm.ONLINE_UNVERIFIED:
        raise ValidationError("Only unverified online applications can be "
                              "merged here")
    from education_system.systems.sixth_form.domain.admissions import (
        record_safety,
    )
    _close(applicant_id, "Merged", by, f"Merged into {keep_id}")
    record_safety.merge_applicants(keep_id, applicant_id,
                                   reason="online duplicate")
    out = _adm.get_applicant(keep_id)
    assert out is not None
    return out
