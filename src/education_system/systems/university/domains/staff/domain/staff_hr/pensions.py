"""Pension schemes and membership.

* **Schemes** — USS, TPS, LGPS and NONE (``pension_schemes``). Each has an
  employer rate and either a flat employee rate or employee tiers
  (``pension_scheme_tiers``: lower ≤ salary < upper). A tiered scheme picks
  its tier from the actual salary, or — TPS — from the full-time salary
  (``tier_basis = 'fte'``). Rates are percentages and payroll keeps them
  current.
* **Membership** (``pension_memberships``) — who is in which scheme from
  when; an opt-out (or a move to another scheme) closes it on a date.
  Setting a contract's scheme enrols the person.

Payroll asks :func:`scheme_for_period` and :func:`contributions`.
Changing schemes and enrolling others is payroll's; anyone may opt
themselves out.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.pay_structure import ensure
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

NO_SCHEME = 'NONE'


def _require_pay(actor: Any) -> str:
    access.require(actor, 'payroll', "Only payroll can change pension schemes")
    return access.username_of(actor)


def _iso(value: Any) -> str:
    text = str(value or '').strip()[:10]
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ValueError("Dates look like YYYY-MM-DD") from None
    return text


# ── schemes ─────────────────────────────────────────────────────────────


def list_schemes(include_inactive: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        ensure(conn)
        sql = "SELECT * FROM pension_schemes"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        schemes = [dict(r) for r in conn.execute(sql + " ORDER BY scheme_code").fetchall()]
        for s in schemes:
            s['tiers'] = tiers(conn, s['scheme_code'])
        return schemes


def tiers(conn, scheme_code: str) -> List[Dict[str, Any]]:
    return [{'lower_limit': r[0], 'upper_limit': r[1], 'employee_rate_pct': r[2]}
            for r in conn.execute("SELECT lower_limit, upper_limit, employee_rate_pct FROM "
                                  "pension_scheme_tiers WHERE scheme_code = ? ORDER BY lower_limit",
                                  (scheme_code,)).fetchall()]


def get_scheme(conn, scheme_code: Optional[str]) -> Optional[Dict[str, Any]]:
    if not scheme_code:
        return None
    cur = conn.execute("SELECT * FROM pension_schemes WHERE scheme_code = ?", (scheme_code,))
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def check_scheme(conn, scheme_code: Optional[str]) -> None:
    ensure(conn)
    if scheme_code in (None, ''):
        return
    scheme = get_scheme(conn, scheme_code)
    if not scheme or not scheme.get('is_active'):
        raise ValueError(f"No active pension scheme '{scheme_code}'")


def update_scheme(actor: Any, scheme_code: str, *, name: Optional[str] = None,
                  employee_rate_pct: Optional[float] = None,
                  employer_rate_pct: Optional[float] = None, tiered: Optional[bool] = None,
                  tier_basis: Optional[str] = None, is_active: Optional[bool] = None) -> None:
    """Change a scheme's rates (percentages), tiering or name; a new code adds a scheme."""
    me = _require_pay(actor)
    code = str(scheme_code or '').strip().upper()
    if not code:
        raise ValueError("A scheme needs a code")
    for label, rate in (('employee', employee_rate_pct), ('employer', employer_rate_pct)):
        if rate is not None and not 0 <= float(rate) <= 100:
            raise ValueError(f"The {label} rate must be a percentage (0-100)")
    if tier_basis is not None and tier_basis not in ('actual', 'fte'):
        raise ValueError("Tier basis is 'actual' or 'fte'")
    with transaction() as conn:
        ensure(conn)
        if not get_scheme(conn, code):
            conn.execute("INSERT INTO pension_schemes (scheme_code, name) VALUES (?, ?)",
                         (code, name or code))
        changes = {k: v for k, v in (
            ('name', name), ('employee_rate_pct', employee_rate_pct),
            ('employer_rate_pct', employer_rate_pct),
            ('tiered', None if tiered is None else int(bool(tiered))),
            ('tier_basis', tier_basis),
            ('is_active', None if is_active is None else int(bool(is_active)))) if v is not None}
        if changes:
            sets = ', '.join(f'"{k}" = ?' for k in changes)
            conn.execute(f"UPDATE pension_schemes SET {sets}, updated_by = ?, updated_at = ? "  # nosec B608
                         "WHERE scheme_code = ?",
                         list(changes.values()) + [me, datetime.now().isoformat(), code])
        access.audit(conn, actor, 'pension.scheme', entity='pension_schemes', entity_id=code,
                     details=changes)


def set_tiers(actor: Any, scheme_code: str, new_tiers: List[Tuple[float, Optional[float], float]]) -> None:
    """Replace a scheme's employee tiers: ``(lower, upper or None, rate %)``,
    from 0 upwards with no gaps; the last one may be open-ended."""
    _require_pay(actor)
    rows = sorted((float(lo), None if hi in (None, '') else float(hi), float(rate))
                  for lo, hi, rate in new_tiers)
    if not rows:
        raise ValueError("Give at least one tier")
    if rows[0][0] != 0:
        raise ValueError("The first tier starts at 0")
    for i, (lo, hi, rate) in enumerate(rows):
        if not 0 <= rate <= 100:
            raise ValueError("Tier rates are percentages (0-100)")
        if hi is not None and hi <= lo:
            raise ValueError("Each tier's upper limit is above its lower limit")
        if i + 1 < len(rows):
            if hi is None or hi != rows[i + 1][0]:
                raise ValueError("Each tier starts where the one below it ends")
    with transaction() as conn:
        ensure(conn)
        if not get_scheme(conn, scheme_code):
            raise ValueError(f"No pension scheme '{scheme_code}'")
        conn.execute("DELETE FROM pension_scheme_tiers WHERE scheme_code = ?", (scheme_code,))
        for lo, hi, rate in rows:
            conn.execute("INSERT INTO pension_scheme_tiers (scheme_code, lower_limit, upper_limit, "
                         "employee_rate_pct) VALUES (?, ?, ?, ?)", (scheme_code, lo, hi, rate))
        conn.execute("UPDATE pension_schemes SET tiered = 1, updated_by = ?, updated_at = ? "
                     "WHERE scheme_code = ?",
                     (access.username_of(actor), datetime.now().isoformat(), scheme_code))
        access.audit(conn, actor, 'pension.tiers', entity='pension_schemes',
                     entity_id=scheme_code, details=rows)


def employee_rate(conn, scheme: Dict[str, Any], full_time_annual: float,
                  actual_annual: float) -> float:
    """The employee rate (%) for this salary."""
    if not scheme.get('tiered'):
        return float(scheme.get('employee_rate_pct') or 0)
    basis = full_time_annual if scheme.get('tier_basis') == 'fte' else actual_annual
    for t in tiers(conn, scheme['scheme_code']):
        if basis >= t['lower_limit'] and (t['upper_limit'] is None or basis < t['upper_limit']):
            return float(t['employee_rate_pct'])
    return float(scheme.get('employee_rate_pct') or 0)


def contributions(conn, scheme_code: Optional[str], pensionable_pay: float,
                  full_time_annual: float, actual_annual: float) -> Dict[str, Any]:
    """Employee and employer contributions on ``pensionable_pay``."""
    scheme = get_scheme(conn, scheme_code) if scheme_code else None
    if not scheme or scheme_code == NO_SCHEME:
        return {'scheme': scheme_code or NO_SCHEME, 'employee': 0.0, 'employer': 0.0,
                'employee_rate_pct': 0.0, 'employer_rate_pct': 0.0}
    ee = employee_rate(conn, scheme, full_time_annual, actual_annual)
    er = float(scheme.get('employer_rate_pct') or 0)
    return {'scheme': scheme_code, 'employee': round(pensionable_pay * ee / 100, 2),
            'employer': round(pensionable_pay * er / 100, 2),
            'employee_rate_pct': ee, 'employer_rate_pct': er}


# ── membership ──────────────────────────────────────────────────────────


def enrol_in(conn, user: str, scheme_code: str, joined_on: str, by: Optional[str]) -> Optional[int]:
    """Close any open membership in another scheme the day before and start
    this one (NONE just closes). Inside the caller's transaction."""
    ensure(conn)
    open_rows = conn.execute("SELECT membership_id, scheme_code FROM pension_memberships "
                             "WHERE user_id = ? AND opted_out_on IS NULL", (user,)).fetchall()
    for membership_id, code in open_rows:
        if code == scheme_code:
            return membership_id
        conn.execute("UPDATE pension_memberships SET opted_out_on = ?, opt_out_reason = ?, "
                     "updated_at = ? WHERE membership_id = ?",
                     (joined_on, f"moved to {scheme_code}", datetime.now().isoformat(),
                      membership_id))
    if not scheme_code or scheme_code == NO_SCHEME:
        return None
    cur = conn.execute("INSERT INTO pension_memberships (user_id, scheme_code, joined_on, created_by) "
                       "VALUES (?, ?, ?, ?)", (user, scheme_code, joined_on, by))
    return cur.lastrowid


def enrol(actor: Any, staff: str, scheme_code: str, joined_on: Optional[str] = None) -> Optional[int]:
    """Put someone in a scheme (payroll)."""
    me = _require_pay(actor)
    with transaction() as conn:
        user = access.staff_key(staff, conn)
        if not user:
            raise ValueError(f"No member of staff '{staff}'")
        check_scheme(conn, scheme_code)
        joined = _iso(joined_on or date.today().isoformat())
        membership_id = enrol_in(conn, user, scheme_code, joined, me)
        conn.execute("UPDATE staff_contracts SET pension_scheme = ?, updated_at = ? "
                     "WHERE user_id = ? AND status = 'active'",
                     (scheme_code, datetime.now().isoformat(), user))
        access.audit(conn, actor, 'pension.enrol', subject=user, entity='pension_memberships',
                     entity_id=membership_id, details={'scheme': scheme_code, 'joined_on': joined})
        log_activity('create', 'pension_membership', details={'user_id': user,
                                                              'scheme': scheme_code})
        return membership_id


def opt_out(actor: Any, staff: str, opted_out_on: Optional[str] = None,
            reason: Optional[str] = None) -> bool:
    """End someone's membership (themselves, or payroll for anyone)."""
    me = access.username_of(actor)
    with transaction() as conn:
        user = access.staff_key(staff, conn)
        if not user:
            raise ValueError(f"No member of staff '{staff}'")
        if user != me and not access.can(actor, 'payroll', conn):
            raise PermissionError("Only payroll can opt someone else out of their pension")
        when = _iso(opted_out_on or date.today().isoformat())
        cur = conn.execute("UPDATE pension_memberships SET opted_out_on = ?, opt_out_reason = ?, "
                           "updated_at = ? WHERE user_id = ? AND opted_out_on IS NULL",
                           (when, reason or 'opted out', datetime.now().isoformat(), user))
        if not cur.rowcount:
            return False
        conn.execute("UPDATE staff_contracts SET pension_scheme = ?, updated_at = ? "
                     "WHERE user_id = ? AND status = 'active'",
                     (NO_SCHEME, datetime.now().isoformat(), user))
        access.audit(conn, actor, 'pension.opt_out', subject=user, entity='pension_memberships',
                     details={'opted_out_on': when, 'reason': reason})
        return True


def memberships(actor: Any, staff: Optional[str] = None) -> List[Dict[str, Any]]:
    """Memberships: one person's (themselves or payroll) or everyone's (payroll)."""
    me = access.username_of(actor)
    with get_connection() as conn:
        ensure(conn)
        user = access.staff_key(staff, conn) if staff else None
        if user is None and staff:
            return []
        if (user is None or user != me) and not access.can(actor, 'payroll', conn):
            if user is None:
                user = me
            else:
                raise PermissionError("Only payroll can see someone else's pension")
        sql = ("SELECT m.*, s.name AS scheme_name FROM pension_memberships m "
               "LEFT JOIN pension_schemes s ON s.scheme_code = m.scheme_code")
        params: list = []
        if user:
            sql += " WHERE m.user_id = ?"
            params.append(user)
        return [dict(r) for r in conn.execute(sql + " ORDER BY m.user_id, m.joined_on DESC",
                                               params).fetchall()]


def scheme_for_period(conn, user: str, start: str, end: str) -> Tuple[str, int]:
    """(scheme, days in it) for the member over ``start``..``end`` — the
    membership covering most of the period; NONE when there is none."""
    best: Tuple[str, int] = (NO_SCHEME, 0)
    rows = conn.execute("SELECT scheme_code, joined_on, opted_out_on FROM pension_memberships "
                        "WHERE user_id = ? AND joined_on <= ? AND (opted_out_on IS NULL OR "
                        "opted_out_on > ?)", (user, end, start)).fetchall()
    p_start, p_end = date.fromisoformat(start[:10]), date.fromisoformat(end[:10])
    for code, joined, left in rows:
        first = max(p_start, date.fromisoformat(str(joined)[:10]))
        # the opt-out date is the first day out of the scheme
        last = p_end if not left else min(p_end, date.fromisoformat(str(left)[:10]) - timedelta(days=1))
        days = (last - first).days + 1
        if days > best[1]:
            best = (code, days)
    return best


__all__ = [
    'NO_SCHEME', 'list_schemes', 'tiers', 'get_scheme', 'check_scheme', 'update_scheme',
    'set_tiers', 'employee_rate', 'contributions', 'enrol_in', 'enrol', 'opt_out',
    'memberships', 'scheme_for_period',
]
