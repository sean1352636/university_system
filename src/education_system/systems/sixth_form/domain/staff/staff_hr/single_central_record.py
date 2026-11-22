"""Single central record (SCR) for the Sixth Form System.

KCSIE Part 3 requires one record of the pre-appointment checks made on
everyone who works at the college. Before this module only DBS (the
:mod:`dbs_checks` register) and right to work (on the HR record)
existed. This adds the rest:

* ``scr_checks`` — one row per check carried out: identity, right to
  work, qualifications, prohibition from teaching, section 128
  (management), overseas checks, first and second references, medical
  fitness, children's barred list. Date, checked by, outcome and a
  document reference. Rows are voided with a reason, never deleted.
* ``scr_staff_profile`` — the facts that decide which checks apply:
  lived/worked overseas, and overrides for "teaching role" / "management
  role" when the job title alone does not say.

:func:`scr_report` combines these with the DBS register and HR record
into one row per staff member, flagging every missing or expired check.

Access: DSL, HR or administrators only (``access.SAFEGUARDING`` or
``access.HR``); every read and write goes to the sensitive-access log
under the area ``"scr"``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from education_system import paths as _paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)

logger = logging.getLogger(__name__)

AREA = "scr"

IDENTITY = "Identity"
RIGHT_TO_WORK = "Right to work"
QUALIFICATIONS = "Qualifications"
PROHIBITION = "Prohibition from teaching"
SECTION_128 = "Section 128"
OVERSEAS = "Overseas checks"
REFERENCE_1 = "Reference 1"
REFERENCE_2 = "Reference 2"
MEDICAL = "Medical fitness"
BARRED_LIST = "Children's barred list"
ENHANCED_DBS = "Enhanced DBS"          # derived from the DBS register

#: Checks recorded in ``scr_checks`` (DBS comes from its own register).
CHECK_TYPES: tuple[str, ...] = (
    IDENTITY, RIGHT_TO_WORK, QUALIFICATIONS, PROHIBITION, SECTION_128,
    OVERSEAS, REFERENCE_1, REFERENCE_2, MEDICAL, BARRED_LIST,
)

#: Column order for the combined SCR view.
SCR_COLUMNS: tuple[str, ...] = (
    IDENTITY, RIGHT_TO_WORK, ENHANCED_DBS, BARRED_LIST, PROHIBITION,
    SECTION_128, OVERSEAS, QUALIFICATIONS, REFERENCE_1, REFERENCE_2,
    MEDICAL,
)

OUTCOMES: tuple[str, ...] = ("Clear", "Concern raised", "Not applicable")

#: Job titles that carry out teaching work (prohibition check applies).
TEACHING_ROLES: frozenset[str] = frozenset({
    "Principal", "Vice Principal", "Head of Sixth Form", "Head of Year",
    "Head of Department", "Subject Lead", "Teacher", "Tutor",
    "Cover Teacher", "SENCO",
})
#: Job titles that are management positions (section 128 applies).
MANAGEMENT_ROLES: frozenset[str] = frozenset({
    "Principal", "Vice Principal", "Head of Sixth Form",
    "Head of Department", "Head of Year", "Safeguarding Lead (DSL)",
})
#: Job titles that need a qualifications check.
QUALIFIED_ROLES: frozenset[str] = TEACHING_ROLES | frozenset({
    "Counsellor", "Careers Adviser", "Safeguarding Lead (DSL)",
    "Deputy DSL", "Exams Officer",
})

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scr_checks (
    check_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id     TEXT NOT NULL,
    check_type   TEXT NOT NULL,
    checked_on   TEXT NOT NULL,
    checked_by   TEXT NOT NULL,
    outcome      TEXT NOT NULL DEFAULT 'Clear',
    reference    TEXT,
    expires_on   TEXT,
    notes        TEXT,
    voided       INTEGER NOT NULL DEFAULT 0,
    voided_reason TEXT,
    voided_by    TEXT,
    voided_at    TEXT,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_scr_staff ON scr_checks(staff_id, check_type);

CREATE TABLE IF NOT EXISTS scr_staff_profile (
    staff_id           TEXT PRIMARY KEY,
    lived_overseas     INTEGER NOT NULL DEFAULT 0,
    overseas_countries TEXT,
    teaching_role      INTEGER,
    management_role    INTEGER,
    notes              TEXT,
    updated_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class ValidationError(Exception):
    pass


@dataclass
class SCRCheck:
    check_id: int
    staff_id: str
    check_type: str
    checked_on: str
    checked_by: str
    outcome: str
    reference: str | None
    expires_on: str | None
    notes: str | None
    voided: bool
    voided_reason: str | None
    voided_by: str | None
    voided_at: str | None
    created_by: str | None
    created_at: str

    @property
    def expired(self) -> bool:
        return bool(self.expires_on
                    and self.expires_on < _dt.date.today().isoformat())


@dataclass
class StaffProfile:
    staff_id: str
    lived_overseas: bool = False
    overseas_countries: str | None = None
    teaching_role: bool | None = None       # None = from job title
    management_role: bool | None = None     # None = from job title
    notes: str | None = None


@dataclass
class CheckStatus:
    check_type: str
    required: bool
    state: str                 # Done / Missing / Expired / Concern / N/A
    checked_on: str | None = None
    checked_by: str | None = None
    reference: str | None = None
    source: str = ""           # SCR / DBS register / HR record

    @property
    def is_gap(self) -> bool:
        return self.required and self.state in ("Missing", "Expired")

    @property
    def label(self) -> str:
        if self.state == "Done":
            return self.checked_on or "Done"
        return self.state


@dataclass
class SCRRow:
    staff_id: str
    name: str
    role: str
    start_date: str | None
    active: bool
    checks: dict[str, CheckStatus] = field(default_factory=dict)

    @property
    def missing(self) -> list[str]:
        return [c.check_type for c in self.checks.values() if c.is_gap]

    @property
    def complete(self) -> bool:
        return not self.missing


# ── DB / access ───────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    _paths.ensure_sixth_form_directories()
    conn = _sql.connect(_paths.SIXTH_FORM_STAFF_HR_DB)
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _principal(principal: access.Principal | None) -> access.Principal:
    return principal if principal is not None else access.current()


def can_access(principal: access.Principal | None = None) -> bool:
    p = _principal(principal)
    return p.can(access.HR) or p.can(access.SAFEGUARDING)


def require_scr(principal: access.Principal | None = None, *,
                action: str = "view",
                staff_id: str | None = None) -> access.Principal:
    """DSL, HR or admin only; logs the access either way."""
    p = _principal(principal)
    ok = can_access(p)
    access.log_sensitive_access(
        p, AREA, action, record_ref=f"staff:{staff_id}" if staff_id else None,
        allowed=ok)
    if not ok:
        raise access.AccessDenied(
            "The single central record is restricted to the DSL, HR and "
            "administrators.")
    return p


def _actor(p: access.Principal) -> str:
    return p.staff_name or p.username or "System"


def _date(value: Any, label: str, *, required: bool = False) -> str | None:
    s = (str(value).strip() if value is not None else "")
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _row_check(r: _sql.Row) -> SCRCheck:
    return SCRCheck(
        check_id=r["check_id"], staff_id=r["staff_id"],
        check_type=r["check_type"], checked_on=r["checked_on"],
        checked_by=r["checked_by"], outcome=r["outcome"],
        reference=r["reference"], expires_on=r["expires_on"],
        notes=r["notes"], voided=bool(r["voided"]),
        voided_reason=r["voided_reason"], voided_by=r["voided_by"],
        voided_at=r["voided_at"], created_by=r["created_by"],
        created_at=r["created_at"])


def _staff(staff_id: str):
    from education_system.systems.sixth_form.domain.staff import staff as _s
    return _s.get_staff(staff_id)


# ── Checks ────────────────────────────────────────────────────────

def record_check(staff_id: str, check_type: str, *,
                 checked_on: str | None = None,
                 checked_by: str | None = None,
                 outcome: str = "Clear", reference: str | None = None,
                 expires_on: str | None = None, notes: str | None = None,
                 principal: access.Principal | None = None) -> SCRCheck:
    """Record a pre-appointment check. A later row supersedes an earlier one."""
    init_db()
    sid = (staff_id or "").strip()
    p = require_scr(principal, action="record-check", staff_id=sid)
    if _staff(sid) is None:
        raise ValidationError(f"No staff member with id {sid}")
    if check_type not in CHECK_TYPES:
        raise ValidationError(
            f"Check type must be one of: {', '.join(CHECK_TYPES)}")
    if outcome not in OUTCOMES:
        raise ValidationError(f"Outcome must be one of: {', '.join(OUTCOMES)}")
    on = _date(checked_on or _dt.date.today().isoformat(), "Checked on",
               required=True)
    if on > _dt.date.today().isoformat():
        raise ValidationError("A check cannot be dated in the future")
    exp = _date(expires_on, "Expires on")
    by = (checked_by or "").strip() or _actor(p)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO scr_checks (staff_id, check_type, checked_on, "
            "checked_by, outcome, reference, expires_on, notes, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, check_type, on, by, outcome,
             (reference or "").strip() or None, exp,
             (notes or "").strip() or None, _actor(p)))
        new_id = cur.lastrowid
    logger.info("SCR: %s recorded for %s (%s)", check_type, sid, outcome)
    out = _get_check(new_id)
    assert out is not None
    return out


def _get_check(check_id: int) -> SCRCheck | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM scr_checks WHERE check_id = ?",
                         (check_id,)).fetchone()
    return _row_check(r) if r else None


def void_check(check_id: int, *, reason: str,
               principal: access.Principal | None = None) -> SCRCheck:
    """Mark a check entered in error. It stays visible in the history."""
    c = _get_check(check_id)
    if c is None:
        raise ValidationError(f"No SCR check #{check_id}")
    p = require_scr(principal, action="void-check", staff_id=c.staff_id)
    if not (reason or "").strip():
        raise ValidationError("A reason is required")
    with _connect() as conn:
        conn.execute(
            "UPDATE scr_checks SET voided = 1, voided_reason = ?, "
            "voided_by = ?, voided_at = datetime('now') WHERE check_id = ?",
            (reason.strip(), _actor(p), check_id))
    out = _get_check(check_id)
    assert out is not None
    return out


def _checks(staff_id: str | None = None,
            include_voided: bool = False) -> list[SCRCheck]:
    init_db()
    sql = "SELECT * FROM scr_checks WHERE 1=1"
    args: list[Any] = []
    if staff_id:
        sql += " AND staff_id = ?"
        args.append(staff_id)
    if not include_voided:
        sql += " AND voided = 0"
    sql += " ORDER BY checked_on, check_id"
    with _connect() as conn:
        return [_row_check(r) for r in conn.execute(sql, args)]


def checks_for_staff(staff_id: str, *, include_voided: bool = True,
                     principal: access.Principal | None = None
                     ) -> list[SCRCheck]:
    require_scr(principal, action="list-checks", staff_id=staff_id)
    return _checks(staff_id, include_voided=include_voided)


# ── Profile ───────────────────────────────────────────────────────

def _profile(staff_id: str) -> StaffProfile:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM scr_staff_profile WHERE staff_id = ?",
                         (staff_id,)).fetchone()
    if r is None:
        return StaffProfile(staff_id=staff_id)

    def tri(v):
        return None if v is None else bool(v)

    return StaffProfile(
        staff_id=staff_id, lived_overseas=bool(r["lived_overseas"]),
        overseas_countries=r["overseas_countries"],
        teaching_role=tri(r["teaching_role"]),
        management_role=tri(r["management_role"]), notes=r["notes"])


def get_profile(staff_id: str, *,
                principal: access.Principal | None = None) -> StaffProfile:
    require_scr(principal, action="view-profile", staff_id=staff_id)
    return _profile(staff_id)


def set_profile(staff_id: str, *, lived_overseas: bool,
                overseas_countries: str | None = None,
                teaching_role: bool | None = None,
                management_role: bool | None = None,
                notes: str | None = None,
                principal: access.Principal | None = None) -> StaffProfile:
    init_db()
    p = require_scr(principal, action="set-profile", staff_id=staff_id)
    if _staff(staff_id) is None:
        raise ValidationError(f"No staff member with id {staff_id}")

    def tri(v):
        return None if v is None else int(bool(v))

    with _connect() as conn:
        conn.execute(
            """INSERT INTO scr_staff_profile
                   (staff_id, lived_overseas, overseas_countries,
                    teaching_role, management_role, notes, updated_by,
                    updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(staff_id) DO UPDATE SET
                   lived_overseas = excluded.lived_overseas,
                   overseas_countries = excluded.overseas_countries,
                   teaching_role = excluded.teaching_role,
                   management_role = excluded.management_role,
                   notes = excluded.notes, updated_by = excluded.updated_by,
                   updated_at = excluded.updated_at""",
            (staff_id, int(bool(lived_overseas)),
             (overseas_countries or "").strip() or None,
             tri(teaching_role), tri(management_role),
             (notes or "").strip() or None, _actor(p)))
    return _profile(staff_id)


# ── Combined view ─────────────────────────────────────────────────

def _requirements(member, prof: StaffProfile) -> dict[str, bool]:
    role = getattr(member, "role", "") or ""
    teaching = prof.teaching_role if prof.teaching_role is not None \
        else role in TEACHING_ROLES
    management = prof.management_role if prof.management_role is not None \
        else role in MANAGEMENT_ROLES
    return {
        IDENTITY: True, RIGHT_TO_WORK: True, ENHANCED_DBS: True,
        BARRED_LIST: True, PROHIBITION: teaching, SECTION_128: management,
        OVERSEAS: prof.lived_overseas,
        QUALIFICATIONS: role in QUALIFIED_ROLES or teaching,
        REFERENCE_1: True, REFERENCE_2: True, MEDICAL: True,
    }


def _status_from_check(ctype: str, required: bool,
                       c: SCRCheck | None) -> CheckStatus:
    if c is None:
        return CheckStatus(ctype, required, "Missing" if required else "N/A")
    if c.outcome == "Not applicable":
        return CheckStatus(ctype, False, "N/A", c.checked_on, c.checked_by,
                           c.reference, "SCR")
    state = "Expired" if c.expired else (
        "Concern" if c.outcome == "Concern raised" else "Done")
    return CheckStatus(ctype, required, state, c.checked_on, c.checked_by,
                       c.reference, "SCR")


def _row_for(member, latest: dict[str, SCRCheck], dbs, hr) -> SCRRow:
    prof = _profile(member.staff_id)
    req = _requirements(member, prof)
    row = SCRRow(staff_id=member.staff_id, name=member.full_name,
                 role=member.role, start_date=member.start_date,
                 active=member.is_active)
    for ctype in SCR_COLUMNS:
        required = req.get(ctype, False)
        if ctype == ENHANCED_DBS:
            if dbs is not None and (dbs.is_active or dbs.is_expired):
                row.checks[ctype] = CheckStatus(
                    ctype, required, "Expired" if dbs.is_expired else "Done",
                    dbs.issued_on or dbs.certificate_seen_on,
                    dbs.signed_off_by, dbs.dbs_number, "DBS register")
            elif hr is not None and hr.dbs_issued_on:
                row.checks[ctype] = CheckStatus(
                    ctype, required,
                    "Expired" if hr.dbs_expired else "Done",
                    hr.dbs_issued_on, None, hr.dbs_number, "HR record")
            else:
                row.checks[ctype] = CheckStatus(ctype, required, "Missing")
            continue
        status = _status_from_check(ctype, required, latest.get(ctype))
        if ctype == BARRED_LIST and status.state == "Missing" and \
                dbs is not None and dbs.is_active and \
                "Barred" in (dbs.level or "") and \
                "Adults'" not in (dbs.level or ""):
            status = CheckStatus(ctype, required, "Done",
                                 dbs.issued_on, dbs.signed_off_by,
                                 dbs.dbs_number, "DBS register")
        if ctype == RIGHT_TO_WORK and status.state == "Missing" and \
                hr is not None and hr.right_to_work_checked:
            status = CheckStatus(ctype, required, "Done",
                                 hr.right_to_work_checked_on, None, None,
                                 "HR record")
        row.checks[ctype] = status
    return row


def _build_rows(staff_rows: list) -> list[SCRRow]:
    from education_system.systems.sixth_form.domain.staff.dbs_checks import (
        dbs_checks as _dbs,
    )
    from education_system.systems.sixth_form.domain.staff.staff_hr import (
        staff_hr as _hr,
    )
    latest: dict[str, dict[str, SCRCheck]] = {}
    for c in _checks():
        latest.setdefault(c.staff_id, {})[c.check_type] = c
    out = []
    for m in staff_rows:
        try:
            dbs = _dbs.latest_for_staff(m.staff_id)
        except Exception:
            logger.exception("DBS lookup failed for %s", m.staff_id)
            dbs = None
        try:
            hr = _hr.get_record_for_staff(m.staff_id)
        except Exception:
            logger.exception("HR lookup failed for %s", m.staff_id)
            hr = None
        out.append(_row_for(m, latest.get(m.staff_id, {}), dbs, hr))
    return out


def scr_report(*, include_left: bool = False, missing_only: bool = False,
               principal: access.Principal | None = None) -> list[SCRRow]:
    """One row per staff member with every SCR check and its state."""
    require_scr(principal, action="report")
    from education_system.systems.sixth_form.domain.staff import staff as _s
    members = [m for m in _s.list_staff() if include_left or m.is_active]
    rows = _build_rows(sorted(members, key=lambda m: (m.last_name,
                                                      m.first_name)))
    if missing_only:
        rows = [r for r in rows if r.missing]
    return rows


def scr_for_staff(staff_id: str, *,
                  principal: access.Principal | None = None) -> SCRRow:
    require_scr(principal, action="view", staff_id=staff_id)
    m = _staff(staff_id)
    if m is None:
        raise ValidationError(f"No staff member with id {staff_id}")
    return _build_rows([m])[0]


@dataclass
class SCRSummary:
    staff: int = 0
    complete: int = 0
    with_gaps: int = 0
    gaps_by_check: dict[str, int] = field(default_factory=dict)


def scr_summary(*, principal: access.Principal | None = None) -> SCRSummary:
    rows = scr_report(principal=principal)
    out = SCRSummary(staff=len(rows))
    for r in rows:
        if r.missing:
            out.with_gaps += 1
            for c in r.missing:
                out.gaps_by_check[c] = out.gaps_by_check.get(c, 0) + 1
        else:
            out.complete += 1
    return out


def export_scr_csv(path: Path | str | None = None, *,
                   include_left: bool = False,
                   principal: access.Principal | None = None) -> Path:
    """Write the SCR to CSV (default under the sixth form data dir)."""
    p = require_scr(principal, action="export")
    rows = scr_report(include_left=include_left, principal=p)
    if path is None:
        out_dir = _paths.SIXTH_FORM_DATA_DIR / "scr_exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / (
            f"single_central_record_"
            f"{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        header = ["Staff ID", "Name", "Role", "Start date", "Active"]
        for col in SCR_COLUMNS:
            header += [col, f"{col} — checked by", f"{col} — ref / source"]
        header.append("Missing")
        w.writerow(header)
        for r in rows:
            line: list[Any] = [r.staff_id, r.name, r.role,
                               r.start_date or "", "Yes" if r.active else "No"]
            for col in SCR_COLUMNS:
                c = r.checks[col]
                line += [c.label, c.checked_by or "",
                         " / ".join(x for x in (c.reference, c.source) if x)]
            line.append("; ".join(r.missing))
            w.writerow(line)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    logger.info("SCR exported to %s (%d staff)", path, len(rows))
    return path
