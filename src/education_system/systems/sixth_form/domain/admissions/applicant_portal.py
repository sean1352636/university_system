"""Applicant self-service portal: check an application, answer an offer.

An applicant has no login. They identify with their online reference
number (``OA-…``) or applicant id plus their date of birth; a one-time
six-digit code is then e-mailed to the address on the application
(:func:`request_code`). Entering it (:func:`verify_code`) gives a
short-lived session token. With the token they can:

* see where the application is (:func:`status_view`) — the stage, the
  interview date, the offer type, conditions and expiry. Nothing
  internal is ever shown: no notes, interview scores, references, staff
  names or sensitive information;
* accept or decline an offer (:func:`accept_offer`,
  :func:`decline_offer` with one of ``admissions.WITHDRAWAL_REASONS``);
* upload documents (:func:`upload_document`; size, type and count
  limits, stored through ``admissions.add_document``);
* correct their e-mail, phone or address (:func:`update_contact`; the old
  address is told when the e-mail changes).

Security:

* codes and tokens are stored only as hashes; a code is keyed with the
  application salt (``online_application.apply_salt``), expires after
  :data:`CODE_VALID_MINUTES`, allows :data:`MAX_CODE_ATTEMPTS` tries and
  works once; a session ends after :data:`SESSION_IDLE_MINUTES` idle or
  :data:`SESSION_MAX_MINUTES` in all;
* failed lookups and codes are counted per client (hashed address); past
  :data:`MAX_FAILURES_PER_CLIENT` in :data:`FAILURE_WINDOW_MINUTES` the
  client is refused (:class:`RateLimited`). At most
  :data:`MAX_CODES_PER_HOUR` codes are e-mailed per applicant;
* :func:`request_code` answers the same whether or not the details
  matched, so it cannot be used to discover applicants.

Everything runs inside ``_guard.system_actor("applicant-portal")`` and
each action goes on the applicant timeline as "… via applicant portal".
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import logging
import re
import secrets
import tempfile
from pathlib import Path
from typing import Any, Callable, TypeVar

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

ACTOR: str = "applicant-portal"
VIA: str = "via applicant portal"

CODE_VALID_MINUTES: int = 30
MAX_CODE_ATTEMPTS: int = 5
MAX_CODES_PER_HOUR: int = 3
SESSION_IDLE_MINUTES: int = 30
SESSION_MAX_MINUTES: int = 120
MAX_FAILURES_PER_CLIENT: int = 10
FAILURE_WINDOW_MINUTES: int = 60

MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
MAX_PORTAL_UPLOADS: int = 10
#: Accepted file types: extension → leading bytes the content must have.
ALLOWED_UPLOADS: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".docx": (b"PK\x03\x04",),
}
#: Document types an applicant may upload (references come from referees).
UPLOAD_DOC_TYPES: tuple[str, ...] = ("Personal Statement", "Transcript",
                                     "Photo", "Other")
CONTACT_FIELDS: tuple[str, ...] = ("email", "phone", "address")

#: What the applicant sees for each internal status.
STAGES: dict[str, tuple[str, str]] = {
    _adm.ONLINE_UNVERIFIED: ("Received", "We have your application and are "
                             "checking it."),
    "Submitted": ("Under review", "Your application is with our admissions "
                  "team."),
    "Under Review": ("Under review", "Your application is with our "
                     "admissions team."),
    "Interview Scheduled": ("Interview arranged", "We would like to meet "
                            "you — see the interview date."),
    "Interviewed": ("Interviewed", "Thank you for coming to interview; we "
                    "will be in touch with a decision."),
    "Offer Made": ("Offer made", "We have offered you a place — please "
                   "accept or decline it."),
    "Offer Accepted": ("Offer accepted", "You have accepted your place."),
    "Deferred": ("Deferred", "Your place has been moved to a later intake."),
    "Offer Declined": ("Offer declined", "You declined your offer."),
    "Waitlisted": ("Waiting list", "You are on our waiting list; we will "
                   "contact you if a place becomes available."),
    "Rejected": ("Unsuccessful", "We were unable to offer you a place."),
    "Withdrawn": ("Withdrawn", "Your application has been withdrawn."),
    "Enrolled": ("Enrolled", "You are enrolled — welcome!"),
}


class PortalError(Exception):
    """A portal failure whose message is safe to show the applicant."""


class AuthFailed(PortalError):
    """The details, code or session were not accepted."""


class RateLimited(PortalError):
    """Too many failed attempts from this client."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_portal_codes (
    code_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    code_salt     TEXT NOT NULL,
    code_hash     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 0,
    used_at       TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_portal_code_aid
    ON admissions_portal_codes(applicant_id, created_at);
CREATE TABLE IF NOT EXISTS admissions_portal_sessions (
    session_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    created_at    TEXT NOT NULL,
    last_used_at  TEXT NOT NULL,
    revoked_at    TEXT,
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS admissions_portal_failures (
    failure_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    client_hash   TEXT NOT NULL,
    kind          TEXT NOT NULL,
    at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_adm_portal_fail
    ON admissions_portal_failures(client_hash, at);
CREATE TABLE IF NOT EXISTS admissions_portal_uploads (
    upload_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id  TEXT NOT NULL,
    document_id   INTEGER NOT NULL,
    uploaded_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES admissions_documents(id)
        ON DELETE CASCADE
);
"""

T = TypeVar("T")


# ── Plumbing ───────────────────────────────────────────────────────

_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True


def _now() -> _dt.datetime:
    return _dt.datetime.utcnow().replace(microsecond=0)


def _ts(d: _dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def _as_portal(fn: Callable[[], T]) -> T:
    with _guard.system_actor(ACTOR):
        init_db()
        return fn()


def _client(client_ip: str | None) -> str:
    from education_system.systems.sixth_form.domain.admissions import (
        online_application,
    )
    return online_application.client_hash(client_ip)


def _check_client(conn: Any, chash: str) -> None:
    since = _ts(_now() - _dt.timedelta(minutes=FAILURE_WINDOW_MINUTES))
    n = conn.execute(
        "SELECT COUNT(*) FROM admissions_portal_failures "
        "WHERE client_hash = ? AND at >= ?", (chash, since)).fetchone()[0]
    if n >= MAX_FAILURES_PER_CLIENT:
        raise RateLimited("Too many attempts — please try again later.")


def _fail(chash: str, kind: str) -> None:
    with _adm._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_portal_failures (client_hash, kind, at) "
            "VALUES (?, ?, ?)", (chash, kind, _ts(_now())))
        # Keep the table small: forget failures well outside the window.
        conn.execute("DELETE FROM admissions_portal_failures WHERE at < ?",
                     (_ts(_now() - _dt.timedelta(days=1)),))
        conn.commit()


def _log(applicant_id: str, detail: str, kind: str = "portal") -> None:
    with _adm._connect() as conn:
        _adm._log_event(conn, applicant_id, f"{detail} {VIA}", kind=kind)
        conn.commit()


def _code_hash(salt: str, applicant_id: str, code: str) -> str:
    from education_system.systems.sixth_form.domain.admissions import (
        online_application,
    )
    key = online_application.apply_salt().encode()
    return hmac.new(key, f"{salt}|{applicant_id}|{code}".encode(),
                    hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _find(identifier: str, dob: str) -> _adm.Applicant | None:
    """The applicant for (reference or applicant id, date of birth), or
    None. Follows a merged duplicate to the record it was merged into."""
    ident = (identifier or "").strip().upper()
    dob = (dob or "").strip()
    if not ident or not re.match(r"^\d{4}-\d{2}-\d{2}$", dob) \
            or len(ident) > 20:
        return None
    aid: str | None = None
    if ident.startswith("OA-"):
        from education_system.systems.sixth_form.domain.admissions import (
            online_application,
        )
        sub = online_application.get_submission(reference_no=ident)
        aid = sub.applicant_id if sub else None
    elif re.match(r"^A\d{7}$", ident):
        aid = ident
    if not aid:
        return None
    a = _adm.get_applicant(aid)
    for _ in range(3):
        if a is None or not a.merged_into:
            break
        a = _adm.get_applicant(a.merged_into)
    if a is None or a.is_archived:
        return None
    if not a.dob or not hmac.compare_digest(a.dob[:10], dob):
        return None
    return a


def _reference_for(a: _adm.Applicant) -> str:
    from education_system.systems.sixth_form.domain.admissions import (
        online_application,
    )
    sub = online_application.get_submission(applicant_id=a.applicant_id)
    return sub.reference_no if sub else a.applicant_id


# ── Sign-in ────────────────────────────────────────────────────────

def request_code(identifier: str, dob: str, *,
                 client_ip: str | None = None) -> None:
    """E-mail a one-time code to the applicant matching *identifier* and
    *dob*. Returns nothing either way — the caller always shows the same
    "if the details matched, a code is on its way" message. Raises
    :class:`RateLimited` after too many failures from this client."""
    def run() -> None:
        chash = _client(client_ip)
        with _adm._connect() as conn:
            _check_client(conn, chash)
        a = _find(identifier, dob)
        if a is None:
            _fail(chash, "lookup")
            return
        if not a.email:
            _log(a.applicant_id, "Sign-in code not sent (no e-mail on "
                                 "record), requested")
            return
        now = _now()
        with _adm._connect() as conn:
            recent = conn.execute(
                "SELECT COUNT(*) FROM admissions_portal_codes "
                "WHERE applicant_id = ? AND created_at >= ?",
                (a.applicant_id, _ts(now - _dt.timedelta(hours=1)))
            ).fetchone()[0]
        if recent >= MAX_CODES_PER_HOUR:
            _log(a.applicant_id, "Sign-in code not sent (hourly limit "
                                 "reached), requested")
            return
        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(8)
        with _adm._connect() as conn:
            # A new code replaces any earlier unused one.
            conn.execute(
                "UPDATE admissions_portal_codes SET used_at = ? "
                "WHERE applicant_id = ? AND used_at IS NULL",
                (_ts(now), a.applicant_id))
            conn.execute(
                "INSERT INTO admissions_portal_codes (applicant_id, "
                "code_salt, code_hash, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (a.applicant_id, salt, _code_hash(salt, a.applicant_id, code),
                 _ts(now),
                 _ts(now + _dt.timedelta(minutes=CODE_VALID_MINUTES))))
            conn.commit()
        from education_system.systems.sixth_form.domain.admissions import (
            admissions_comms,
        )
        try:
            admissions_comms.send_portal_code(
                a.applicant_id, code, valid_minutes=CODE_VALID_MINUTES)
        except ValidationError:
            logger.warning("Portal code for %s not queued", a.applicant_id,
                           exc_info=True)
    _as_portal(run)


def verify_code(identifier: str, dob: str, code: str, *,
                client_ip: str | None = None) -> str:
    """Exchange (identifier, dob, code) for a session token. Raises
    :class:`AuthFailed` (one message for every failure) or
    :class:`RateLimited`."""
    def run() -> str:
        chash = _client(client_ip)
        with _adm._connect() as conn:
            _check_client(conn, chash)
        a = _find(identifier, dob)
        clean = (code or "").strip()
        if a is None or not re.match(r"^\d{6}$", clean):
            _fail(chash, "code")
            raise AuthFailed("Those details or that code were not accepted.")
        now = _now()
        with _adm._connect() as conn:
            row = conn.execute(
                "SELECT * FROM admissions_portal_codes WHERE applicant_id = ? "
                "AND used_at IS NULL AND expires_at >= ? "
                "ORDER BY code_id DESC LIMIT 1",
                (a.applicant_id, _ts(now))).fetchone()
            if row is None or row["attempts"] >= MAX_CODE_ATTEMPTS:
                ok = False
            else:
                ok = hmac.compare_digest(
                    row["code_hash"],
                    _code_hash(row["code_salt"], a.applicant_id, clean))
            if row is not None and not ok:
                attempts = row["attempts"] + 1
                conn.execute(
                    "UPDATE admissions_portal_codes SET attempts = ?, "
                    "used_at = CASE WHEN ? >= ? THEN ? ELSE used_at END "
                    "WHERE code_id = ?",
                    (attempts, attempts, MAX_CODE_ATTEMPTS, _ts(now),
                     row["code_id"]))
                conn.commit()
            if not ok:
                failed = True
            else:
                failed = False
                token = secrets.token_urlsafe(32)
                conn.execute("UPDATE admissions_portal_codes SET used_at = ? "
                             "WHERE code_id = ?", (_ts(now), row["code_id"]))
                conn.execute(
                    "INSERT INTO admissions_portal_sessions (applicant_id, "
                    "token_hash, created_at, last_used_at) VALUES (?, ?, ?, ?)",
                    (a.applicant_id, _token_hash(token), _ts(now), _ts(now)))
                conn.commit()
        if failed:
            _fail(chash, "code")
            raise AuthFailed("Those details or that code were not accepted.")
        _log(a.applicant_id, "Signed in")
        return token
    return _as_portal(run)


def _session(token: str) -> str:
    """The applicant id for a live session token (touches it), or
    :class:`AuthFailed`."""
    if not token or len(token) > 200:
        raise AuthFailed("Please sign in again.")
    now = _now()
    with _adm._connect() as conn:
        row = conn.execute(
            "SELECT * FROM admissions_portal_sessions WHERE token_hash = ?",
            (_token_hash(token),)).fetchone()
        if (row is None or row["revoked_at"]
                or row["last_used_at"] < _ts(
                    now - _dt.timedelta(minutes=SESSION_IDLE_MINUTES))
                or row["created_at"] < _ts(
                    now - _dt.timedelta(minutes=SESSION_MAX_MINUTES))):
            raise AuthFailed("Please sign in again.")
        conn.execute("UPDATE admissions_portal_sessions SET last_used_at = ? "
                     "WHERE session_id = ?", (_ts(now), row["session_id"]))
        conn.commit()
    return row["applicant_id"]


def _live_applicant(token: str) -> _adm.Applicant:
    aid = _session(token)
    a = _adm.get_applicant(aid)
    if a is None or a.is_archived:
        raise AuthFailed("Please sign in again.")
    return a


def sign_out(token: str) -> None:
    def run() -> None:
        try:
            aid = _session(token)
        except AuthFailed:
            return
        with _adm._connect() as conn:
            conn.execute("UPDATE admissions_portal_sessions SET revoked_at = ? "
                         "WHERE token_hash = ?", (_ts(_now()),
                                                  _token_hash(token)))
            conn.commit()
        _log(aid, "Signed out")
    _as_portal(run)


# ── What the applicant sees ────────────────────────────────────────

def _offer_expired(a: _adm.Applicant) -> bool:
    return bool(a.offer_expiry
                and a.offer_expiry[:10] < _dt.date.today().isoformat())


def _view(a: _adm.Applicant) -> dict[str, Any]:
    stage, detail = STAGES.get(a.status, ("In progress", ""))
    out: dict[str, Any] = {
        "reference": _reference_for(a),
        "first_name": a.first_name,
        "stage": stage,
        "stage_detail": detail,
        "submitted_on": a.submitted_at,
        "intake_year": a.intake_year,
        "programme": [c.label for c in _adm.list_programme_choices(
            a.applicant_id)],
        "interview": None,
        "offer": None,
        "can_respond_to_offer": False,
        "decline_reasons": [],
        "contact": {"email": a.email, "phone": a.phone,
                    "address": a.address},
        "documents": [],
        "upload_limits": {
            "max_bytes": MAX_UPLOAD_BYTES, "max_files": MAX_PORTAL_UPLOADS,
            "types": sorted(ALLOWED_UPLOADS), "doc_types": list(
                UPLOAD_DOC_TYPES)},
    }
    if a.status == "Interview Scheduled" and a.interview_date:
        out["interview"] = {"date": a.interview_date}
    if a.status in ("Offer Made", "Offer Accepted", "Deferred"):
        out["offer"] = {"type": a.offer_type,
                        "conditions": a.offer_conditions,
                        "expires": a.offer_expiry,
                        "expired": _offer_expired(a)
                        if a.status == "Offer Made" else False}
    if a.status == "Offer Made" and not _offer_expired(a):
        out["can_respond_to_offer"] = True
        out["decline_reasons"] = list(_adm.WITHDRAWAL_REASONS)
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT d.doc_type, d.label, u.uploaded_at FROM "
            "admissions_portal_uploads u JOIN admissions_documents d "
            "ON d.id = u.document_id WHERE u.applicant_id = ? "
            "ORDER BY u.upload_id", (a.applicant_id,)).fetchall()
    out["documents"] = [{"type": r["doc_type"], "label": r["label"],
                         "uploaded": r["uploaded_at"]} for r in rows]
    return out


def status_view(token: str) -> dict[str, Any]:
    """The applicant-facing view of their application (see module doc
    for what is deliberately left out)."""
    return _as_portal(lambda: _view(_live_applicant(token)))


# ── Actions ────────────────────────────────────────────────────────

def _require_open_offer(a: _adm.Applicant) -> None:
    if a.status != "Offer Made":
        raise PortalError("There is no offer waiting for a reply.")
    if _offer_expired(a):
        raise PortalError("This offer has expired — please contact the "
                          "admissions team.")


def accept_offer(token: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        a = _live_applicant(token)
        _require_open_offer(a)
        try:
            _adm.accept_offer(a.applicant_id)
        except ValidationError:
            logger.warning("Portal accept for %s refused", a.applicant_id,
                           exc_info=True)
            raise PortalError("Your reply could not be recorded — please "
                              "contact the admissions team.") from None
        _log(a.applicant_id, "Offer accepted", kind="offer")
        _confirm(a.applicant_id)
        return _view(_adm.get_applicant(a.applicant_id) or a)
    return _as_portal(run)


def decline_offer(token: str, reason: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        a = _live_applicant(token)
        _require_open_offer(a)
        if reason not in _adm.WITHDRAWAL_REASONS:
            raise PortalError("Please choose a reason from the list.")
        try:
            _adm.decline_offer(a.applicant_id, reason=reason)
        except ValidationError:
            logger.warning("Portal decline for %s refused", a.applicant_id,
                           exc_info=True)
            raise PortalError("Your reply could not be recorded — please "
                              "contact the admissions team.") from None
        _log(a.applicant_id, f"Offer declined ({reason})", kind="offer")
        _confirm(a.applicant_id)
        return _view(_adm.get_applicant(a.applicant_id) or a)
    return _as_portal(run)


def _confirm(applicant_id: str) -> None:
    """E-mail the applicant the new status (best effort)."""
    from education_system.systems.sixth_form.domain.admissions import (
        admissions_comms,
    )
    try:
        admissions_comms.send_status_email(applicant_id)
    except Exception:  # noqa: BLE001 — the reply is recorded either way
        logger.warning("Portal: status e-mail for %s not queued",
                       applicant_id, exc_info=True)


def _safe_name(filename: str) -> str:
    base = Path((filename or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "document"
    return stem[-80:]


def upload_document(token: str, filename: str, content: bytes, *,
                    doc_type: str = "Other") -> dict[str, Any]:
    """Store an uploaded file on the application (type sniffed from its
    first bytes, size and count limited)."""
    def run() -> dict[str, Any]:
        a = _live_applicant(token)
        if a.status in _adm.TERMINAL_STATUSES or a.converted_student_id:
            raise PortalError("Documents can no longer be added to this "
                              "application.")
        if doc_type not in UPLOAD_DOC_TYPES:
            raise PortalError("Please choose a document type from the list.")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise PortalError("The file is empty.")
        if len(content) > MAX_UPLOAD_BYTES:
            raise PortalError(f"Files must be {MAX_UPLOAD_BYTES // (1024 * 1024)}"
                              " MB or smaller.")
        name = _safe_name(filename)
        ext = Path(name).suffix.lower()
        magic = ALLOWED_UPLOADS.get(ext)
        if magic is None or not any(bytes(content).startswith(m)
                                    for m in magic):
            raise PortalError("Only PDF, Word (.docx), PNG or JPEG files "
                              "can be uploaded.")
        with _adm._connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM admissions_portal_uploads "
                             "WHERE applicant_id = ?",
                             (a.applicant_id,)).fetchone()[0]
        if n >= MAX_PORTAL_UPLOADS:
            raise PortalError("You have uploaded the maximum number of "
                              "files; please contact the admissions team.")
        with tempfile.TemporaryDirectory(prefix="sf-portal-") as tmp:
            path = Path(tmp) / name
            path.write_bytes(bytes(content))
            doc = _adm.add_document(a.applicant_id, str(path),
                                    doc_type=doc_type,
                                    label=f"{name} (applicant portal)")
        with _adm._connect() as conn:
            conn.execute("INSERT INTO admissions_portal_uploads "
                         "(applicant_id, document_id) VALUES (?, ?)",
                         (a.applicant_id, doc.id))
            conn.commit()
        _log(a.applicant_id, f"Document uploaded: {doc_type} — {name}",
             kind="document")
        return {"type": doc.doc_type, "label": doc.label,
                "uploaded": doc.added_at}
    return _as_portal(run)


def update_contact(token: str, *, email: str | None = None,
                   phone: str | None = None,
                   address: str | None = None) -> dict[str, Any]:
    """Correct the applicant's own e-mail, phone or address. ``None``
    leaves a field unchanged; e-mail and phone cannot be blanked."""
    def run() -> dict[str, Any]:
        a = _live_applicant(token)
        if a.converted_student_id:
            raise PortalError("You are enrolled — please update your details "
                              "with the college office.")
        payload: dict[str, Any] = {}
        for key, value, limit in (("email", email, 120), ("phone", phone, 30),
                                  ("address", address, 300)):
            if value is None:
                continue
            v = str(value).strip()
            if len(v) > limit or any(ord(ch) < 32 and ch not in "\n"
                                     for ch in v):
                raise PortalError(f"The {key} is not valid.")
            if key in ("email", "phone") and not v:
                raise PortalError(f"Your {key} cannot be left blank.")
            if key == "email":
                try:
                    v = _adm._validate_email(v) or ""
                except ValidationError:
                    raise PortalError("That is not a valid e-mail "
                                      "address.") from None
            if key == "phone":
                try:
                    _adm._validate_phone(v)
                except ValidationError:
                    raise PortalError("That is not a valid phone "
                                      "number.") from None
            if (getattr(a, key) or "") != v:
                payload[key] = v or None
        if not payload:
            return _view(a)
        try:
            out = _adm.update_applicant(a.applicant_id, payload)
        except ValidationError:
            logger.warning("Portal contact update for %s refused",
                           a.applicant_id, exc_info=True)
            raise PortalError("Your details could not be saved — please "
                              "contact the admissions team.") from None
        labels = {"email": "E-mail", "phone": "Phone", "address": "Address"}
        changes = [f"{labels[k]} changed" for k in payload]
        _log(a.applicant_id, "Contact details updated ("
             + ", ".join(changes) + ")", kind="update")
        if "email" in payload and a.email:
            from education_system.systems.sixth_form.domain.admissions import (
                admissions_comms,
            )
            try:
                admissions_comms.send_contact_change_notice(
                    a.applicant_id, a.email, changes)
            except Exception:  # noqa: BLE001 — the change is saved
                logger.warning("Portal: change notice for %s not queued",
                               a.applicant_id, exc_info=True)
        return _view(out)
    return _as_portal(run)
