"""IT acceptable-use policy (AUP) acceptance for the Sixth Form System.

The policy itself lives in the Policy register
(:mod:`...governance.policies.policies`): one policy is designated the IT
AUP (``device_loan_settings['aup_policy_id']``) and its versions are that
policy's revisions — publishing a new version appends an approved
revision, which makes it the policy's current ``version``. Nothing about
the policy text is duplicated here.

What this module adds is ``aup_acceptances``: who (a student or a member
of staff) accepted which version, when and how. A device loan can only be
issued to someone who has accepted the *current* version
(:func:`require_current_acceptance`), so publishing a new version means
everyone accepts again.

Acceptances are kept as history; a mistaken one is withdrawn with a
reason rather than deleted once a loan relies on it.

Permissions: designating the policy, publishing versions and recording
acceptance for someone else need ``operations`` (or ``governance`` /
admin). A student or member of staff may accept for themselves
(:func:`accept_current`).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

STUDENT = "Student"
STAFF = "Staff"
USER_TYPES: tuple[str, ...] = (STUDENT, STAFF)

METHODS: tuple[str, ...] = (
    "Signed form", "Online (self)", "Online (recorded by staff)",
    "Induction session", "Other",
)
DEFAULT_METHOD = "Signed form"

AUP_SETTING = "aup_policy_id"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Staff ids carry no foreign key (staff rows have no delete guard, and an
# acceptance record must outlive them); student ids do, so the student
# delete guard counts them.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS device_loan_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_by  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS aup_acceptances (
    acceptance_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id        INTEGER NOT NULL,
    version          TEXT NOT NULL,
    user_type        TEXT NOT NULL,
    student_id       TEXT,
    staff_id         TEXT,
    accepted_on      TEXT NOT NULL,
    method           TEXT NOT NULL DEFAULT 'Signed form',
    recorded_by      TEXT,
    notes            TEXT,
    withdrawn_on     TEXT,
    withdrawn_reason TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    CHECK ((user_type = 'Student' AND student_id IS NOT NULL
            AND staff_id IS NULL)
        OR (user_type = 'Staff' AND staff_id IS NOT NULL
            AND student_id IS NULL)),
    FOREIGN KEY (policy_id)  REFERENCES policies(policy_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_aup_one_live
    ON aup_acceptances(policy_id, version, user_type,
                       COALESCE(student_id, ''), COALESCE(staff_id, ''))
    WHERE withdrawn_on IS NULL;
CREATE INDEX IF NOT EXISTS idx_aup_student ON aup_acceptances(student_id);
CREATE INDEX IF NOT EXISTS idx_aup_staff   ON aup_acceptances(staff_id);
"""


class ValidationError(ValueError):
    pass


@dataclass
class Acceptance:
    acceptance_id: int
    policy_id: int
    version: str
    user_type: str
    student_id: str | None
    staff_id: str | None
    accepted_on: str
    method: str
    recorded_by: str | None
    notes: str | None
    withdrawn_on: str | None
    withdrawn_reason: str | None
    created_at: str
    person_name: str | None = None

    @property
    def person_id(self) -> str:
        return self.student_id or self.staff_id or ""

    @property
    def is_live(self) -> bool:
        return self.withdrawn_on is None


@dataclass
class CurrentAUP:
    policy_id: int
    title: str
    version: str
    approved_on: str | None
    document_ref: str | None
    summary: str | None


# ── Plumbing ────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY = False


def _policies():
    from education_system.systems.sixth_form.domain.governance.policies import (
        policies as _pol,
    )
    return _pol


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _st,
    )
    return _st


def _staff():
    from education_system.systems.sixth_form.domain.staff import (
        staff as _sf,
    )
    return _sf


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _policies().init_db()
    _students().init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _row(r: _sql.Row) -> Acceptance:
    keys = r.keys()
    name = None
    if "first_name" in keys and r["first_name"]:
        name = " ".join(p for p in (r["first_name"], r["last_name"]) if p)
    elif "sf_first" in keys and r["sf_first"]:
        name = " ".join(p for p in (r["sf_first"], r["sf_last"]) if p)
    return Acceptance(
        acceptance_id=r["acceptance_id"], policy_id=r["policy_id"],
        version=r["version"], user_type=r["user_type"],
        student_id=r["student_id"], staff_id=r["staff_id"],
        accepted_on=r["accepted_on"], method=r["method"],
        recorded_by=r["recorded_by"], notes=r["notes"],
        withdrawn_on=r["withdrawn_on"],
        withdrawn_reason=r["withdrawn_reason"], created_at=r["created_at"],
        person_name=name)


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _date(v: Any, label: str) -> str | None:
    s = _text(v)
    if not s:
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def _who(p: Any) -> str | None:
    return p.staff_name or p.username or None


def _require_manager(action: str) -> Any:
    access = _access()
    p = access.current()
    if not (p.can(access.OPERATIONS) or p.can(access.GOVERNANCE)):
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not {action}.")
    return p


def resolve_person(user_type: Any, person_id: Any) -> tuple[str, str, str]:
    """``(user_type, id, name)``, checking the person exists."""
    ut = _choice(user_type, USER_TYPES, "User type")
    pid = _text(person_id)
    if not pid:
        raise ValidationError(f"{ut} is required")
    if ut == STUDENT:
        s = _students().get_student(pid)
        if s is None:
            raise ValidationError(f"No student with id {pid}")
        return ut, s.student_id, s.full_name
    st = _staff().get_staff(pid)
    if st is None:
        raise ValidationError(f"No staff member {pid.upper()}")
    return ut, st.staff_id, st.full_name


# ── The policy ──────────────────────────────────────────────────────

def _get_setting(key: str) -> str | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM device_loan_settings WHERE key=?",
                         (key,)).fetchone()
    return r["value"] if r else None


def aup_policy() -> Any:
    """The Policy-register row designated as the IT AUP, or None."""
    raw = _get_setting(AUP_SETTING)
    if not raw:
        return None
    try:
        return _policies().get_policy(int(raw))
    except ValueError:
        return None


def set_aup_policy(policy_id: int) -> Any:
    p = _require_manager("choose the IT acceptable-use policy")
    pol = _policies().get_policy(int(policy_id))
    if pol is None:
        raise ValidationError(f"No policy #{policy_id}")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO device_loan_settings (key, value, updated_by) "
            "VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value, updated_by=excluded.updated_by, "
            "updated_at=datetime('now')",
            (AUP_SETTING, str(pol.policy_id), _who(p)))
    logger.info("IT AUP set to policy #%d (%s)", pol.policy_id, pol.title)
    return pol


def create_aup_policy(payload: dict[str, Any]) -> Any:
    """Add the AUP to the Policy register (category "IT & Online",
    approved, with a first revision) and designate it."""
    p = _require_manager("create the IT acceptable-use policy")
    pol_mod = _policies()
    today = _dt.date.today().isoformat()
    version = _text(payload.get("version")) or "1.0"
    approved_on = _date(payload.get("approved_on"), "Approved on") or today
    pol = pol_mod.create_policy({
        "title": _text(payload.get("title")) or "IT Acceptable Use Policy",
        "category": "IT & Online", "version": version,
        "owner": _text(payload.get("owner")), "status": "Draft",
        "review_cycle": _text(payload.get("review_cycle")) or "Annual",
        "summary": _text(payload.get("summary")),
        "document_ref": _text(payload.get("document_ref")),
    })
    pol_mod.add_revision(pol.policy_id, {
        "version": version, "revised_on": approved_on,
        "revised_by": _who(p), "changes": "First version",
        "approved_by": _text(payload.get("approved_by")) or _who(p)
        or "Sixth Form",
    })
    return set_aup_policy(pol.policy_id)


def current_aup() -> CurrentAUP | None:
    """The version people must accept: the designated policy's current
    version, provided the policy is Approved (or under review — the
    approved text still stands while it is reviewed)."""
    pol = aup_policy()
    if pol is None or pol.status not in ("Approved", "Under review"):
        return None
    return CurrentAUP(policy_id=pol.policy_id, title=pol.title,
                      version=pol.version, approved_on=pol.approved_on,
                      document_ref=pol.document_ref, summary=pol.summary)


def _version_key(v: str) -> tuple[int, ...]:
    parts = [int(x) for x in v.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def publish_version(payload: dict[str, Any]) -> CurrentAUP:
    """Approve a new AUP version (a revision in the Policy register).
    It must be later than the current one; everybody then has to accept
    it again before their next loan."""
    p = _require_manager("publish an acceptable-use policy version")
    pol = aup_policy()
    if pol is None:
        raise ValidationError("Choose or create the IT acceptable-use "
                              "policy first")
    version = _text(payload.get("version"))
    if not version:
        raise ValidationError("Version is required")
    try:
        newer = _version_key(version) > _version_key(pol.version)
    except ValueError:
        raise ValidationError(
            "Version must be numeric (e.g. '1.1', '2.0')") from None
    if not newer:
        raise ValidationError(
            f"Version {version} is not later than the current {pol.version}")
    _policies().add_revision(pol.policy_id, {
        "version": version,
        "revised_on": _date(payload.get("revised_on"), "Approved on")
        or _dt.date.today().isoformat(),
        "revised_by": _who(p), "changes": _text(payload.get("changes")),
        "approved_by": _text(payload.get("approved_by")) or _who(p)
        or "Sixth Form",
    })
    if "document_ref" in payload or "summary" in payload:
        upd = {k: payload[k] for k in ("document_ref", "summary")
               if k in payload}
        _policies().update_policy(pol.policy_id, upd)
    cur = current_aup()
    if cur is None:
        raise ValidationError("The policy is not approved")
    return cur


def versions() -> list[Any]:
    """Revisions of the AUP, newest first (Policy register rows)."""
    pol = aup_policy()
    return _policies().list_revisions(pol.policy_id) if pol else []


# ── Acceptances ─────────────────────────────────────────────────────

_SELECT = (
    "SELECT a.*, s.first_name, s.last_name, sf.first_name AS sf_first, "
    "sf.last_name AS sf_last FROM aup_acceptances a "
    "LEFT JOIN students s ON s.student_id = a.student_id "
    "LEFT JOIN staff sf ON sf.staff_id = a.staff_id")


def _staff_ready() -> None:
    _staff().init_db()


def _insert(ut: str, pid: str, *, version_row: CurrentAUP,
            accepted_on: str, method: str, recorded_by: str | None,
            notes: str | None) -> Acceptance:
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO aup_acceptances (policy_id, version, user_type, "
                "student_id, staff_id, accepted_on, method, recorded_by, "
                "notes) VALUES (?,?,?,?,?,?,?,?,?)",
                (version_row.policy_id, version_row.version, ut,
                 pid if ut == STUDENT else None,
                 pid if ut == STAFF else None, accepted_on, method,
                 recorded_by, notes))
        except _sql.IntegrityError:
            raise ValidationError(
                f"{pid} has already accepted version "
                f"{version_row.version}") from None
        new_id = cur.lastrowid
    logger.info("AUP v%s accepted by %s %s", version_row.version, ut, pid)
    out = get_acceptance(new_id)
    assert out is not None
    return out


def record_acceptance(user_type: str, person_id: str, *,
                      accepted_on: str | None = None,
                      method: str | None = None,
                      notes: str | None = None) -> Acceptance:
    """Record that someone accepted the current AUP version (e.g. a
    signed form handed in). Staff with operations may record for anyone;
    otherwise only for yourself."""
    init_db()
    _staff_ready()
    ut, pid, _ = resolve_person(user_type, person_id)
    access = _access()
    p = access.current()
    own = (ut == STUDENT and p.student_id == pid) or \
          (ut == STAFF and (p.staff_id or "").upper() == pid)
    if not own:
        _require_manager("record acceptable-use acceptance for others")
    cur = current_aup()
    if cur is None:
        raise ValidationError("There is no approved IT acceptable-use "
                              "policy to accept")
    on = _date(accepted_on, "Accepted on") or _dt.date.today().isoformat()
    if on > _dt.date.today().isoformat():
        raise ValidationError("Accepted on cannot be in the future")
    if cur.approved_on and on < cur.approved_on:
        raise ValidationError(
            f"Version {cur.version} was approved on {cur.approved_on} — it "
            "cannot have been accepted before then")
    m = _choice(method, METHODS, "Method",
                "Online (self)" if own else DEFAULT_METHOD)
    return _insert(ut, pid, version_row=cur, accepted_on=on, method=m,
                   recorded_by=_who(p), notes=_text(notes))


def accept_current() -> Acceptance:
    """The signed-in student or member of staff accepts for themselves
    (portal "I accept" button)."""
    p = _access().current()
    if p.student_id:
        return record_acceptance(STUDENT, p.student_id,
                                 method="Online (self)")
    if p.staff_id:
        return record_acceptance(STAFF, p.staff_id, method="Online (self)")
    raise ValidationError("Only a student or member of staff can accept "
                          "the acceptable-use policy")


def get_acceptance(acceptance_id: int) -> Acceptance | None:
    init_db()
    _staff_ready()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE a.acceptance_id=?",
                         (int(acceptance_id),)).fetchone()
    return _row(r) if r else None


def current_acceptance(user_type: str, person_id: str
                       ) -> Acceptance | None:
    """The live acceptance of the current version, if any."""
    cur = current_aup()
    if cur is None:
        return None
    ut = _choice(user_type, USER_TYPES, "User type")
    pid = (person_id or "").strip()
    if ut == STAFF:
        pid = pid.upper()
    init_db()
    _staff_ready()
    col = "student_id" if ut == STUDENT else "staff_id"
    with _connect() as conn:
        r = conn.execute(
            f"{_SELECT} WHERE a.policy_id=? AND a.version=? AND "
            f"a.{col}=? AND a.withdrawn_on IS NULL",
            (cur.policy_id, cur.version, pid)).fetchone()
    return _row(r) if r else None


def has_accepted_current(user_type: str, person_id: str) -> bool:
    return current_acceptance(user_type, person_id) is not None


def require_current_acceptance(user_type: str, person_id: str
                               ) -> Acceptance:
    """Raise unless the person has accepted the current AUP version."""
    cur = current_aup()
    if cur is None:
        raise ValidationError(
            "No approved IT acceptable-use policy is set up — a device "
            "cannot be lent until there is one to accept")
    acc = current_acceptance(user_type, person_id)
    if acc is None:
        raise ValidationError(
            f"{person_id} has not accepted version {cur.version} of the "
            f"{cur.title} — record their acceptance first")
    return acc


def list_acceptances(*, user_type: str | None = None,
                     person_id: str | None = None,
                     current_only: bool = False,
                     include_withdrawn: bool = True) -> list[Acceptance]:
    init_db()
    _staff_ready()
    clauses: list[str] = []
    args: list[Any] = []
    if user_type:
        clauses.append("a.user_type = ?")
        args.append(_choice(user_type, USER_TYPES, "User type"))
    if person_id:
        clauses.append("(a.student_id = ? OR a.staff_id = ?)")
        args += [person_id.strip(), person_id.strip().upper()]
    if current_only:
        cur = current_aup()
        if cur is None:
            return []
        clauses.append("a.policy_id = ? AND a.version = ?")
        args += [cur.policy_id, cur.version]
    if not include_withdrawn:
        clauses.append("a.withdrawn_on IS NULL")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            f"{_SELECT}{where} ORDER BY a.accepted_on DESC, "
            "a.acceptance_id DESC", args).fetchall()]


def withdraw_acceptance(acceptance_id: int, reason: str, *,
                        withdrawn_on: str | None = None) -> Acceptance:
    """Withdraw an acceptance (recorded in error, or the person retracts
    it). The row stays as history."""
    p = _require_manager("withdraw acceptable-use acceptance")
    a = get_acceptance(acceptance_id)
    if a is None:
        raise ValidationError(f"No acceptance #{acceptance_id}")
    if not a.is_live:
        raise ValidationError("That acceptance is already withdrawn")
    why = _text(reason)
    if not why:
        raise ValidationError("Give a reason for withdrawing it")
    on = _date(withdrawn_on, "Withdrawn on") or _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE aup_acceptances SET withdrawn_on=?, withdrawn_reason=?, "
            "notes=COALESCE(notes || '; ', '') || ? WHERE acceptance_id=?",
            (on, why, f"withdrawn by {_who(p) or 'staff'}", acceptance_id))
    out = get_acceptance(acceptance_id)
    assert out is not None
    return out


def outstanding(user_type: str = STUDENT) -> list[tuple[str, str]]:
    """``[(id, name)]`` of on-roll students (or active staff) who have not
    accepted the current version."""
    ut = _choice(user_type, USER_TYPES, "User type")
    cur = current_aup()
    if cur is None:
        return []
    done = {a.person_id for a in list_acceptances(
        user_type=ut, current_only=True, include_withdrawn=False)}
    if ut == STUDENT:
        people = [(s.student_id, s.full_name)
                  for s in _students().list_students() if s.on_roll]
    else:
        people = [(s.staff_id, s.full_name)
                  for s in _staff().list_staff(active_only=True)]
    return sorted([(pid, name) for pid, name in people if pid not in done],
                  key=lambda x: x[1])
