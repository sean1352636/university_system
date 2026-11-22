"""Pay structure: the pay spine, grades, job → grade, annual increments and pay awards.

* A **spine point** has one annual value per **pay year** (``'2025/26'``,
  starting on the increment date, 1 August by default). A pay award adds the
  next year's values; earlier years stay for back-dated pay.
* A **grade** spans ``min_point`` .. ``max_point`` (the top the annual
  increment reaches) and may have **contribution points** above that, up to
  ``contribution_max_point``, which are only awarded by hand.
* A **contract** names its grade, spine point, ``fte`` and pension scheme.
  ``staff_contracts.salary`` is the *full-time* annual salary: the spine
  value for the current pay year, or a manual override (with a reason).
  Payroll applies ``fte``.
* The **annual increment** moves everyone below the top of their grade up
  one point on the increment date, once per date (``pay_increment_runs``),
  holding starters with less than the qualifying service. Every move and
  hold is recorded and audited.

Editing any of it is payroll's (``access.can(actor, 'payroll')``); the spine
and grades themselves are readable by anyone (published pay scales).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

logger = logging.getLogger(__name__)

#: Dotted name of the scheduled increment job (daily is fine; it acts once
#: per increment date).
INCREMENT_JOB = (
    "education_system.systems.university.domains.staff.domain.staff_hr.pay_structure.increment_job"
)
#: The scheduled job only catches up on an increment date this recent.
JOB_CATCH_UP_DAYS = 31
DEFAULT_INCREMENT_DATE = '08-01'
DAYS_PER_YEAR_WORKING = 260

_MMDD = re.compile(r'^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$')
_PAY_YEAR = re.compile(r'^(\d{4})/(\d{2})$')


# ── schema ──────────────────────────────────────────────────────────────

_SEEDED: set = set()


def ensure(conn) -> None:
    """Staff HR tables (incl. pay), plus the default schemes and settings."""
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_ddl,
        staff_hr_pay_schema,
    )
    staff_hr_ddl.apply_to_connection(conn)
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _SEEDED:
        return
    busy = conn.in_transaction
    staff_hr_pay_schema.seed_defaults(conn.execute)
    if not busy:
        conn.commit()
    if key:
        _SEEDED.add(key)


def _require_pay(actor: Any) -> str:
    access.require(actor, 'payroll', "Only payroll can change the pay structure")
    return access.username_of(actor)


def _today() -> date:
    return date.today()


def _as_date(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# ── settings and pay years ──────────────────────────────────────────────


def get_settings(conn=None) -> Dict[str, str]:
    own = conn is None
    c = conn or get_connection()
    try:
        ensure(c)
        return {k: v for k, v in c.execute("SELECT key, value FROM pay_settings").fetchall()}
    finally:
        if own:
            c.close()


def set_setting(actor: Any, key: str, value: str) -> None:
    """``increment_date`` (MM-DD) or ``increment_min_service_months`` (0-24)."""
    me = _require_pay(actor)
    value = str(value).strip()
    if key == 'increment_date':
        if not _MMDD.match(value):
            raise ValueError("The increment date must be MM-DD, e.g. 08-01")
    elif key == 'increment_min_service_months':
        if not value.isdigit() or int(value) > 24:
            raise ValueError("Qualifying service must be 0 to 24 months")
    else:
        raise ValueError(f"Unknown pay setting '{key}'")
    with transaction() as conn:
        ensure(conn)
        conn.execute("INSERT INTO pay_settings (key, value, updated_by, updated_at) "
                     "VALUES (?, ?, ?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, "
                     "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                     (key, value, me, datetime.now().isoformat()))
        access.audit(conn, actor, 'pay.setting', entity='pay_settings', entity_id=key,
                     details={'value': value})


def increment_mmdd(conn=None) -> str:
    return get_settings(conn).get('increment_date') or DEFAULT_INCREMENT_DATE


def increment_date_for(year: int, mmdd: str) -> date:
    month, day = (int(p) for p in mmdd.split('-'))
    try:
        return date(year, month, day)
    except ValueError:            # 29 Feb etc.
        return date(year, month, 28)


def pay_year_for(on: Any = None, mmdd: str = DEFAULT_INCREMENT_DATE) -> str:
    """The pay year containing ``on`` (``'2025/26'`` runs from the
    increment date in 2025)."""
    when = _as_date(on) or _today()
    start = when.year if when >= increment_date_for(when.year, mmdd) else when.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def current_pay_year(conn=None, on: Any = None) -> str:
    return pay_year_for(on, increment_mmdd(conn))


def last_increment_date(on: Any = None, mmdd: str = DEFAULT_INCREMENT_DATE) -> date:
    when = _as_date(on) or _today()
    this_year = increment_date_for(when.year, mmdd)
    return this_year if when >= this_year else increment_date_for(when.year - 1, mmdd)


def _check_pay_year(pay_year: str) -> str:
    text = str(pay_year or '').strip()
    m = _PAY_YEAR.match(text)
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValueError("A pay year looks like 2025/26")
    return text


# ── spine ───────────────────────────────────────────────────────────────


def spine_value(conn, point: Any, pay_year: str) -> Optional[float]:
    """The point's value in ``pay_year`` (or the latest earlier year)."""
    if point is None or point == '':
        return None
    row = conn.execute("SELECT annual_value FROM pay_spine_values WHERE point = ? AND pay_year <= ? "
                       "ORDER BY pay_year DESC LIMIT 1", (int(point), pay_year)).fetchone()
    return float(row[0]) if row else None


def pay_years(conn=None) -> List[str]:
    own = conn is None
    c = conn or get_connection()
    try:
        ensure(c)
        return [r[0] for r in c.execute("SELECT DISTINCT pay_year FROM pay_spine_values "
                                        "ORDER BY pay_year DESC").fetchall()]
    finally:
        if own:
            c.close()


def list_spine(pay_year: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every point with its value in ``pay_year`` (default: current)."""
    with get_connection() as conn:
        ensure(conn)
        year = pay_year or current_pay_year(conn)
        rows = conn.execute("SELECT point, label FROM pay_spine_points ORDER BY point").fetchall()
        out = []
        for point, label in rows:
            value_row = conn.execute(
                "SELECT annual_value, pay_year FROM pay_spine_values WHERE point = ? AND "
                "pay_year <= ? ORDER BY pay_year DESC LIMIT 1", (point, year)).fetchone()
            out.append({'point': point, 'label': label or '', 'pay_year': year,
                        'annual_value': float(value_row[0]) if value_row else None,
                        'value_from_year': value_row[1] if value_row else None})
        return out


def set_spine_value(actor: Any, point: int, pay_year: str, annual_value: float,
                    label: Optional[str] = None) -> None:
    """Add or change a point's value for a pay year (the point is created if new)."""
    me = _require_pay(actor)
    point = int(point)
    if point < 1:
        raise ValueError("Spine points start at 1")
    pay_year = _check_pay_year(pay_year)
    annual_value = float(annual_value)
    if annual_value <= 0:
        raise ValueError("A spine value must be more than 0")
    with transaction() as conn:
        ensure(conn)
        conn.execute("INSERT OR IGNORE INTO pay_spine_points (point, label) VALUES (?, ?)",
                     (point, label))
        if label is not None:
            conn.execute("UPDATE pay_spine_points SET label = ? WHERE point = ?", (label, point))
        conn.execute("INSERT INTO pay_spine_values (point, pay_year, annual_value, set_by, set_at) "
                     "VALUES (?, ?, ?, ?, ?) ON CONFLICT (point, pay_year) DO UPDATE SET "
                     "annual_value = excluded.annual_value, set_by = excluded.set_by, "
                     "set_at = excluded.set_at",
                     (point, pay_year, annual_value, me, datetime.now().isoformat()))
        access.audit(conn, actor, 'pay.spine_value', entity='pay_spine_values',
                     entity_id=f"{point}:{pay_year}", details={'annual_value': annual_value})
        if pay_year == current_pay_year(conn):
            resync_salaries(conn, point=point)


def delete_spine_point(actor: Any, point: int) -> None:
    """Remove a point no grade or contract uses."""
    _require_pay(actor)
    point = int(point)
    with transaction() as conn:
        ensure(conn)
        if conn.execute("SELECT 1 FROM staff_contracts WHERE spine_point = ?", (point,)).fetchone():
            raise ValueError(f"Point {point} is on a contract")
        if conn.execute("SELECT 1 FROM pay_grades WHERE ? BETWEEN min_point AND "
                        "COALESCE(contribution_max_point, max_point)", (point,)).fetchone():
            raise ValueError(f"Point {point} is inside a grade")
        conn.execute("DELETE FROM pay_spine_values WHERE point = ?", (point,))
        conn.execute("DELETE FROM pay_spine_points WHERE point = ?", (point,))
        access.audit(conn, actor, 'pay.spine_point_deleted', entity='pay_spine_points',
                     entity_id=point)


# ── grades and jobs ─────────────────────────────────────────────────────


def list_grades(include_inactive: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        ensure(conn)
        sql = "SELECT * FROM pay_grades"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return [dict(r) for r in conn.execute(sql + " ORDER BY min_point, grade_code").fetchall()]


def get_grade(conn, grade_code: Optional[str]) -> Optional[Dict[str, Any]]:
    if not grade_code:
        return None
    cur = conn.execute("SELECT * FROM pay_grades WHERE grade_code = ?", (grade_code,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(zip([d[0] for d in cur.description], row))


def save_grade(actor: Any, grade_code: str, name: str, min_point: int, max_point: int,
               contribution_max_point: Optional[int] = None, is_active: bool = True) -> None:
    """Add or change a grade."""
    _require_pay(actor)
    code = str(grade_code or '').strip()
    if not code:
        raise ValueError("A grade needs a code")
    min_point, max_point = int(min_point), int(max_point)
    contribution = int(contribution_max_point) if contribution_max_point not in (None, '') else None
    if min_point > max_point:
        raise ValueError("The bottom point must not be above the top point")
    if contribution is not None and contribution < max_point:
        raise ValueError("Contribution points sit above the top of the grade")
    with transaction() as conn:
        ensure(conn)
        top = contribution if contribution is not None else max_point
        known = {r[0] for r in conn.execute("SELECT point FROM pay_spine_points WHERE point "
                                            "BETWEEN ? AND ?", (min_point, top)).fetchall()}
        missing = [p for p in range(min_point, top + 1) if p not in known]
        if missing:
            raise ValueError(f"Spine points {missing} are not on the pay spine yet")
        conn.execute("INSERT INTO pay_grades (grade_code, name, min_point, max_point, "
                     "contribution_max_point, is_active, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                     "ON CONFLICT (grade_code) DO UPDATE SET name = excluded.name, "
                     "min_point = excluded.min_point, max_point = excluded.max_point, "
                     "contribution_max_point = excluded.contribution_max_point, "
                     "is_active = excluded.is_active, updated_at = excluded.updated_at",
                     (code, str(name or code).strip(), min_point, max_point, contribution,
                      1 if is_active else 0, datetime.now().isoformat()))
        access.audit(conn, actor, 'pay.grade_saved', entity='pay_grades', entity_id=code,
                     details={'min_point': min_point, 'max_point': max_point,
                              'contribution_max_point': contribution, 'is_active': bool(is_active)})


def list_job_grades() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT j.job_title, j.grade_code, g.name AS grade_name FROM pay_grade_jobs j "
            "LEFT JOIN pay_grades g ON g.grade_code = j.grade_code ORDER BY j.job_title").fetchall()]


def grade_for_job(job_title: Optional[str], conn=None) -> Optional[str]:
    if not job_title:
        return None
    own = conn is None
    c = conn or get_connection()
    try:
        ensure(c)
        row = c.execute("SELECT grade_code FROM pay_grade_jobs WHERE job_title = ?",
                        (str(job_title).strip(),)).fetchone()
        return row[0] if row else None
    finally:
        if own:
            c.close()


def map_job(actor: Any, job_title: str, grade_code: Optional[str]) -> None:
    """Put a job title on a grade (``grade_code`` None removes the mapping)."""
    me = _require_pay(actor)
    title = str(job_title or '').strip()
    if not title:
        raise ValueError("A job title is required")
    with transaction() as conn:
        ensure(conn)
        if not grade_code:
            conn.execute("DELETE FROM pay_grade_jobs WHERE job_title = ?", (title,))
        else:
            if not get_grade(conn, grade_code):
                raise ValueError(f"No grade '{grade_code}'")
            conn.execute("INSERT INTO pay_grade_jobs (job_title, grade_code, created_by) "
                         "VALUES (?, ?, ?) ON CONFLICT (job_title) DO UPDATE SET "
                         "grade_code = excluded.grade_code, created_by = excluded.created_by",
                         (title, grade_code, me))
        access.audit(conn, actor, 'pay.job_grade', entity='pay_grade_jobs', entity_id=title,
                     details={'grade_code': grade_code})


# ── contracts ───────────────────────────────────────────────────────────


def derive_salary(conn, contract: Dict[str, Any], on: Any = None) -> Dict[str, Any]:
    """The contract's full-time annual salary on ``on``, and where it came
    from: ``override``, ``spine`` or ``contract`` (the stored salary)."""
    fte = contract.get('fte')
    fte = float(fte) if fte not in (None, '') else 1.0
    override = contract.get('salary_override')
    if override not in (None, ''):
        return {'full_time': float(override), 'fte': fte, 'source': 'override'}
    if contract.get('spine_point') not in (None, ''):
        try:
            year = current_pay_year(conn, on)
            value = spine_value(conn, contract['spine_point'], year)
        except Exception:
            logger.warning("spine lookup failed for contract %s", contract.get('contract_id'),
                           exc_info=True)
            value = None
        if value is not None:
            return {'full_time': value, 'fte': fte, 'source': 'spine', 'pay_year': year}
    return {'full_time': float(contract.get('salary') or 0), 'fte': fte, 'source': 'contract'}


def resync_salaries(conn, point: Optional[int] = None, contract_id: Optional[int] = None) -> int:
    """Set ``salary`` to the current spine value on spine-point contracts
    (all, one point's, or one contract). Overrides are left alone."""
    sql = ("SELECT contract_id, spine_point, salary FROM staff_contracts WHERE spine_point IS NOT "
           "NULL AND salary_override IS NULL AND status = 'active'")
    params: list = []
    if point is not None:
        sql += " AND spine_point = ?"
        params.append(int(point))
    if contract_id is not None:
        sql += " AND contract_id = ?"
        params.append(int(contract_id))
    year = current_pay_year(conn)
    changed = 0
    for cid, spine_point, salary in conn.execute(sql, params).fetchall():
        value = spine_value(conn, spine_point, year)
        if value is not None and value != salary:
            conn.execute("UPDATE staff_contracts SET salary = ?, updated_at = ? WHERE contract_id = ?",
                         (value, datetime.now().isoformat(), cid))
            changed += 1
    return changed


def validate_assignment(conn, grade_code: Optional[str], spine_point: Any) -> None:
    if spine_point in (None, ''):
        return
    point = int(spine_point)
    if not conn.execute("SELECT 1 FROM pay_spine_points WHERE point = ?", (point,)).fetchone():
        raise ValueError(f"Spine point {point} is not on the pay spine")
    if grade_code:
        grade = get_grade(conn, grade_code)
        if not grade:
            raise ValueError(f"No grade '{grade_code}'")
        top = grade.get('contribution_max_point') or grade['max_point']
        if not grade['min_point'] <= point <= top:
            raise ValueError(f"Point {point} is outside grade {grade_code} "
                             f"({grade['min_point']}-{top})")


def check_fte(fte: Any) -> float:
    value = float(fte)
    if not 0 < value <= 1:
        raise ValueError("FTE must be more than 0 and at most 1")
    return value


def assign(actor: Any, contract_id: int, *, grade_code: Optional[str] = None,
           spine_point: Optional[int] = None, fte: Optional[float] = None,
           pension_scheme: Optional[str] = None, salary_override: Optional[float] = None,
           override_reason: Optional[str] = None, clear_override: bool = False) -> Dict[str, Any]:
    """Set a contract's grade / point / FTE / scheme, or override its salary.
    Payroll or HR; an override needs a reason. Returns the derived salary."""
    if not (access.can(actor, 'payroll') or access.is_hr(actor)):
        raise PermissionError("Only HR or payroll can change a contract's pay")
    me = access.username_of(actor)
    with transaction() as conn:
        ensure(conn)
        row = conn.execute("SELECT * FROM staff_contracts WHERE contract_id = ?",
                           (int(contract_id),)).fetchone()
        if not row:
            raise ValueError("Contract not found")
        contract = dict(row)
        old_scheme = contract.get('pension_scheme')
        changes: Dict[str, Any] = {}
        grade = grade_code if grade_code is not None else contract.get('grade_code')
        if grade_code is None and not grade:
            grade = grade_for_job(contract.get('job_title'), conn)
            if grade:
                changes['grade_code'] = grade
        elif grade_code is not None:
            changes['grade_code'] = grade_code or None
        point = spine_point if spine_point is not None else contract.get('spine_point')
        if spine_point is not None:
            changes['spine_point'] = int(spine_point)
        validate_assignment(conn, grade or None, point)
        if fte is not None:
            changes['fte'] = check_fte(fte)
        if pension_scheme is not None:
            from education_system.systems.university.domains.staff.domain.staff_hr import pensions
            pensions.check_scheme(conn, pension_scheme)
            changes['pension_scheme'] = pension_scheme
        if clear_override:
            changes.update(salary_override=None, salary_override_reason=None,
                           salary_override_by=None)
        elif salary_override is not None:
            if not (override_reason or '').strip():
                raise ValueError("A salary override needs a reason")
            if float(salary_override) <= 0:
                raise ValueError("An override salary must be more than 0")
            changes.update(salary_override=float(salary_override),
                           salary_override_reason=override_reason.strip(), salary_override_by=me)
        if changes:
            sets = ', '.join(f'"{k}" = ?' for k in changes)
            conn.execute(f"UPDATE staff_contracts SET {sets}, updated_at = ? "  # nosec B608
                         "WHERE contract_id = ?",
                         list(changes.values()) + [datetime.now().isoformat(), int(contract_id)])
        contract.update(changes)
        derived = derive_salary(conn, contract)
        conn.execute("UPDATE staff_contracts SET salary = ? WHERE contract_id = ?",
                     (derived['full_time'], int(contract_id)))
        if pension_scheme is not None and pension_scheme != old_scheme:
            from education_system.systems.university.domains.staff.domain.staff_hr import pensions
            pensions.enrol_in(conn, contract['user_id'], pension_scheme,
                              datetime.now().date().isoformat(), me)
        access.audit(conn, actor, 'pay.contract_assigned', subject=contract['user_id'],
                     entity='staff_contract', entity_id=contract_id,
                     details={k: v for k, v in changes.items() if k != 'salary_override'}
                     | ({'salary_override': True} if 'salary_override' in changes else {}))
        log_activity('update', 'staff_contract_pay', details={
            'contract_id': contract_id, 'fields': sorted(changes)})
        return derived


# ── annual increment ────────────────────────────────────────────────────


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return months - (1 if end.day < start.day else 0)


def plan_increments(conn, effective: date) -> List[Dict[str, Any]]:
    """Who moves and who is held on ``effective`` (nothing is changed)."""
    settings = get_settings(conn)
    min_months = int(settings.get('increment_min_service_months') or 0)
    grades = {r[0]: {'max_point': r[1], 'contribution_max_point': r[2]} for r in conn.execute(
        "SELECT grade_code, max_point, contribution_max_point FROM pay_grades").fetchall()}
    rows = conn.execute(
        "SELECT contract_id, user_id, grade_code, spine_point, start_date, end_date "
        "FROM staff_contracts WHERE status = 'active' AND spine_point IS NOT NULL "
        "AND (start_date IS NULL OR start_date <= ?) "
        "AND (end_date IS NULL OR end_date = '' OR end_date >= ?) ORDER BY contract_id",
        (effective.isoformat(), effective.isoformat())).fetchall()
    plan = []
    for cid, user, grade_code, point, start, _end in rows:
        item = {'contract_id': cid, 'user_id': user, 'from_point': point, 'to_point': point}
        grade = grades.get(grade_code)
        started = _as_date(start)
        if not grade:
            item.update(outcome='held', reason='no grade on the contract')
        elif point >= grade['max_point']:
            item.update(outcome='held', reason='contribution point' if point > grade['max_point']
                        else 'top of grade')
        elif started and _months_between(started, effective) < min_months:
            item.update(outcome='held', reason=f'less than {min_months} months service')
        else:
            item.update(outcome='moved', to_point=point + 1, reason='annual increment')
        plan.append(item)
    return plan


def run_increments(actor: Any = None, effective_date: Any = None) -> Dict[str, Any]:
    """Apply the annual increment for ``effective_date`` (default: the latest
    increment date). Once per date. ``actor`` None is the scheduled job."""
    if actor is not None:
        _require_pay(actor)
    who = access.username_of(actor) if actor is not None else 'system'
    with transaction() as conn:
        ensure(conn)
        mmdd = increment_mmdd(conn)
        effective = _as_date(effective_date) or last_increment_date(None, mmdd)
        if effective > _today():
            raise ValueError("An increment cannot be applied before its date")
        done = conn.execute("SELECT run_id, moved, held FROM pay_increment_runs "
                            "WHERE effective_date = ?", (effective.isoformat(),)).fetchone()
        if done:
            return {'already_run': True, 'run_id': done[0], 'moved': done[1], 'held': done[2],
                    'effective_date': effective.isoformat()}
        plan = plan_increments(conn, effective)
        year = pay_year_for(effective, mmdd)
        moved = sum(1 for p in plan if p['outcome'] == 'moved')
        cur = conn.execute("INSERT INTO pay_increment_runs (effective_date, pay_year, run_by, moved, "
                           "held) VALUES (?, ?, ?, ?, ?)",
                           (effective.isoformat(), year, who, moved, len(plan) - moved))
        run_id = cur.lastrowid
        for p in plan:
            conn.execute("INSERT INTO pay_increment_moves (run_id, contract_id, user_id, from_point, "
                         "to_point, outcome, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (run_id, p['contract_id'], p['user_id'], p['from_point'], p['to_point'],
                          p['outcome'], p['reason']))
            if p['outcome'] == 'moved':
                conn.execute("UPDATE staff_contracts SET spine_point = ?, updated_at = ? "
                             "WHERE contract_id = ?",
                             (p['to_point'], datetime.now().isoformat(), p['contract_id']))
                resync_salaries(conn, contract_id=p['contract_id'])
            access.audit(conn, who, f"pay.increment_{p['outcome']}", subject=p['user_id'],
                         entity='staff_contract', entity_id=p['contract_id'],
                         details={'from': p['from_point'], 'to': p['to_point'],
                                  'reason': p['reason'], 'run_id': run_id})
        log_activity('update', 'pay_increment_run', details={
            'run_id': run_id, 'effective_date': effective.isoformat(), 'moved': moved,
            'held': len(plan) - moved, 'run_by': who})
        return {'already_run': False, 'run_id': run_id, 'moved': moved,
                'held': len(plan) - moved, 'effective_date': effective.isoformat(),
                'pay_year': year}


def increment_job() -> Dict[str, Any]:
    """Scheduled (daily): run the increment once its date has come, catching
    up for :data:`JOB_CATCH_UP_DAYS` days."""
    with get_connection() as conn:
        ensure(conn)
        mmdd = increment_mmdd(conn)
    effective = last_increment_date(None, mmdd)
    if (_today() - effective).days > JOB_CATCH_UP_DAYS:
        return {'skipped': True, 'reason': 'no increment date in the catch-up window',
                'effective_date': effective.isoformat()}
    return run_increments(None, effective)


def increment_runs(actor: Any) -> List[Dict[str, Any]]:
    _require_pay(actor)
    with get_connection() as conn:
        ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pay_increment_runs ORDER BY effective_date DESC").fetchall()]


def increment_moves(actor: Any, run_id: int) -> List[Dict[str, Any]]:
    _require_pay(actor)
    with get_connection() as conn:
        ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pay_increment_moves WHERE run_id = ? ORDER BY move_id",
            (int(run_id),)).fetchall()]


def preview_increments(actor: Any, effective_date: Any = None) -> List[Dict[str, Any]]:
    _require_pay(actor)
    with get_connection() as conn:
        ensure(conn)
        effective = _as_date(effective_date) or last_increment_date(None, increment_mmdd(conn))
        return plan_increments(conn, effective)


# ── pay award ───────────────────────────────────────────────────────────


def apply_pay_award(actor: Any, pay_year: str, uplift_percent: float,
                    from_pay_year: Optional[str] = None, minimum_uplift: float = 0,
                    notes: Optional[str] = None) -> Dict[str, Any]:
    """New pay-year values: every point's ``from_pay_year`` value × (1 +
    uplift %), at least ``minimum_uplift`` more, rounded to the pound."""
    me = _require_pay(actor)
    pay_year = _check_pay_year(pay_year)
    pct = float(uplift_percent)
    minimum = float(minimum_uplift or 0)
    if pct < 0 or minimum < 0:
        raise ValueError("A pay award cannot cut pay")
    with transaction() as conn:
        ensure(conn)
        if conn.execute("SELECT 1 FROM pay_awards WHERE pay_year = ?", (pay_year,)).fetchone():
            raise ValueError(f"A pay award for {pay_year} has already been applied")
        if conn.execute("SELECT 1 FROM pay_spine_values WHERE pay_year = ?", (pay_year,)).fetchone():
            raise ValueError(f"{pay_year} already has spine values; change them point by point")
        source = from_pay_year or (conn.execute(
            "SELECT MAX(pay_year) FROM pay_spine_values WHERE pay_year < ?",
            (pay_year,)).fetchone() or [None])[0]
        if not source:
            raise ValueError("There are no earlier spine values to uplift")
        source = _check_pay_year(source)
        rows = conn.execute("SELECT p.point FROM pay_spine_points p ORDER BY p.point").fetchall()
        updated = 0
        for (point,) in rows:
            base = spine_value(conn, point, source)
            if base is None:
                continue
            value = float(round(max(base * (1 + pct / 100), base + minimum)))
            conn.execute("INSERT INTO pay_spine_values (point, pay_year, annual_value, set_by) "
                         "VALUES (?, ?, ?, ?)", (point, pay_year, value, me))
            updated += 1
        conn.execute("INSERT INTO pay_awards (pay_year, from_pay_year, uplift_percent, "
                     "minimum_uplift, points_updated, notes, applied_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (pay_year, source, pct, minimum, updated, notes, me))
        resynced = resync_salaries(conn) if pay_year == current_pay_year(conn) else 0
        access.audit(conn, actor, 'pay.award', entity='pay_awards', entity_id=pay_year,
                     details={'from': source, 'uplift_percent': pct, 'minimum': minimum,
                              'points': updated, 'contracts_resynced': resynced})
        return {'pay_year': pay_year, 'from_pay_year': source, 'points_updated': updated,
                'contracts_resynced': resynced}


def list_pay_awards() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pay_awards ORDER BY pay_year DESC").fetchall()]


__all__ = [
    'INCREMENT_JOB', 'DAYS_PER_YEAR_WORKING', 'ensure', 'get_settings', 'set_setting',
    'pay_year_for', 'current_pay_year', 'last_increment_date', 'spine_value', 'pay_years',
    'list_spine', 'set_spine_value', 'delete_spine_point', 'list_grades', 'get_grade',
    'save_grade', 'list_job_grades', 'grade_for_job', 'map_job', 'derive_salary',
    'resync_salaries', 'validate_assignment', 'check_fte', 'assign', 'plan_increments',
    'run_increments', 'increment_job', 'increment_runs', 'increment_moves',
    'preview_increments', 'apply_pay_award', 'list_pay_awards',
]
