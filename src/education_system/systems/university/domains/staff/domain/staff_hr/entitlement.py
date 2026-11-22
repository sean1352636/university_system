"""Leave entitlements: how many days of each leave type someone gets in a
leave year, and what carries over.

**Rules** (``staff_leave_entitlements``, one per leave type; HR administrators
set them; a type without a row uses :func:`default_rule`):

* ``fte_pro_rata`` — ``full_time_days`` × FTE (annual leave);
* ``fixed`` — the same days for everyone (study, personal ...);
* ``absence`` — not an allowance; sickness is recorded as absence
  (``absence``), so nothing is allocated or used up;
* ``case`` — booked from a family leave case; no allowance;
* ``none`` — no allowance and no balance check.

**Pro rata for service.** Someone who starts or leaves inside the leave year
gets the share of the year they are employed (``pro_rata_service``).

**Bank holidays** (annual leave). Unless the type's days already include
them, the leave year's bank holidays are added to the allocation — pro rata
to FTE when ``bank_holidays_pro_rata`` — and the ones that fall on the
person's own working days are booked against it (``bank_holiday_days``). A
full-timer with 25 days and 8 bank holidays has 33 allocated, 8 booked, 25
to take; a three-day-a-week colleague gets the same share of each, however
the holidays fall on their days.

**Carry-over.** What is left at the end of a year carries into the next, up
to the type's cap (else ``carry_over_cap_days``), and expires
``carry_over_expiry_months`` into the year: carried days are used first, so
whatever of them is still unused then is expired.

Allocations are rounded up to the half day. A balance HR set by hand
(``allocation_basis = 'manual'``) is left alone unless forced.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules as lr
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

BASES = ('fte_pro_rata', 'fixed', 'absence', 'case', 'none')
BASIS_LABELS = {
    'fte_pro_rata': 'Pro rata to FTE',
    'fixed': 'Fixed days',
    'absence': 'Recorded as absence',
    'case': 'Family leave case',
    'none': 'No allowance',
}
#: Bases that keep a balance.
BALANCED = ('fte_pro_rata', 'fixed')
FAMILY_NAMES = ('maternity leave', 'paternity leave', 'adoption leave', 'shared parental leave')


def _half_up(value: float) -> float:
    return math.ceil(round(value * 2, 6)) / 2


def default_rule(leave_type: dict) -> dict:
    name = str(leave_type.get('name') or '').lower()
    days = float(leave_type.get('max_days_per_year') or 0)
    if name.startswith('annual'):
        basis, carry, service = 'fte_pro_rata', 1, 1
    elif name.startswith('sick'):
        basis, carry, service = 'absence', 0, 0
    elif name in FAMILY_NAMES:
        basis, carry, service = 'case', 0, 0
    else:
        basis, carry, service = 'fixed', 0, 0
    return {'leave_type_id': leave_type.get('leave_type_id'), 'basis': basis,
            'full_time_days': days, 'pro_rata_service': service, 'carry_over': carry,
            'carry_over_cap': None, 'includes_bank_holidays': 0, 'stored': False}


def _type(conn, leave_type_id) -> Optional[dict]:
    row = conn.execute("SELECT * FROM leave_types WHERE leave_type_id = ?",
                       (leave_type_id,)).fetchone()
    return dict(row) if row else None


def rule_for(leave_type_id: int, conn=None) -> dict:
    own = conn is None
    c = get_connection() if own else conn
    try:
        lr.ensure(c)
        leave_type = _type(c, leave_type_id) or {'leave_type_id': leave_type_id}
        rule = default_rule(leave_type)
        row = c.execute("SELECT * FROM staff_leave_entitlements WHERE leave_type_id = ?",
                        (leave_type_id,)).fetchone()
        if row:
            row = dict(row)
            rule.update({k: row[k] for k in ('basis', 'pro_rata_service', 'carry_over',
                                             'carry_over_cap', 'includes_bank_holidays')})
            if row.get('full_time_days') is not None:
                rule['full_time_days'] = float(row['full_time_days'])
            rule['stored'] = True
        rule['leave_type_name'] = leave_type.get('name')
        return rule
    finally:
        if own:
            c.close()


def rules(conn=None) -> list:
    """Every leave type with its rule (for the HR screen)."""
    own = conn is None
    c = get_connection() if own else conn
    try:
        lr.ensure(c)
        out = []
        for t in c.execute("SELECT * FROM leave_types ORDER BY name").fetchall():
            rule = rule_for(t['leave_type_id'], c)
            rule.update({'is_active': t['is_active'], 'is_paid': t['is_paid']})
            out.append(rule)
        return out
    finally:
        if own:
            c.close()


def is_balanced(leave_type_id: int, conn=None) -> bool:
    return rule_for(leave_type_id, conn)['basis'] in BALANCED


def set_rule(actor: Any, leave_type_id: int, basis: str, full_time_days: Optional[float] = None,
             carry_over: bool = False, carry_over_cap: Optional[float] = None,
             pro_rata_service: bool = True, includes_bank_holidays: bool = False) -> dict:
    """Set how a leave type is allocated (HR administrators)."""
    access.require(actor, 'hr_admin', "Only an HR administrator can change leave entitlements")
    if basis not in BASES:
        raise ValueError(f"Basis must be one of {', '.join(BASES)}")
    for label, value in (('Days', full_time_days), ('Carry-over cap', carry_over_cap)):
        if value is not None and float(value) < 0:
            raise ValueError(f"{label} cannot be negative")
    with get_connection() as conn:
        lr.ensure(conn)
        if not _type(conn, leave_type_id):
            raise ValueError("No such leave type")
        conn.execute(
            "INSERT INTO staff_leave_entitlements (leave_type_id, basis, full_time_days, "
            "pro_rata_service, carry_over, carry_over_cap, includes_bank_holidays, updated_by, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(leave_type_id) DO UPDATE "
            "SET basis = excluded.basis, full_time_days = excluded.full_time_days, "
            "pro_rata_service = excluded.pro_rata_service, carry_over = excluded.carry_over, "
            "carry_over_cap = excluded.carry_over_cap, "
            "includes_bank_holidays = excluded.includes_bank_holidays, "
            "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
            (leave_type_id, basis, full_time_days, int(bool(pro_rata_service)),
             int(bool(carry_over)), carry_over_cap, int(bool(includes_bank_holidays)),
             access.username_of(actor), lr.now()))
        access.audit(conn, actor, 'leave_entitlement_rule', None, 'staff_leave_entitlements',
                     leave_type_id, {'basis': basis, 'days': full_time_days})
        conn.commit()
        return rule_for(leave_type_id, conn)


# ── working it out ──────────────────────────────────────────────────────


def remaining(balance: dict) -> float:
    """Days left on a ``leave_balances`` row."""
    def num(key):
        return float(balance.get(key) or 0)
    return round(num('allocated_days') + num('carried_over') - num('carry_over_expired')
                 - num('used_days') - num('bank_holiday_days'), 2)


def calculate(username: str, leave_type_id: int, year: int, conn=None,
              leaving: Any = None) -> Optional[dict]:
    """``{'allocated', 'bank_holiday_days', 'basis'}`` for one person, type
    and leave year, or None when the type keeps no balance (``leaving``:
    as if employment ended that day)."""
    own = conn is None
    c = get_connection() if own else conn
    try:
        rule = rule_for(leave_type_id, c)
        if rule['basis'] not in BALANCED:
            return None
        y_start, y_end = lr.leave_year_bounds(year, c)
        hired, ends = lr.employment_dates(username, c)
        leaving = lr.as_date(leaving) or ends
        start = max(y_start, hired) if hired else y_start
        end = min(y_end, leaving) if leaving else y_end
        if end < start:
            return {'allocated': 0.0, 'bank_holiday_days': 0.0,
                    'basis': 'not employed in this leave year'}
        share = 1.0
        if rule['pro_rata_service']:
            share = ((end - start).days + 1) / ((y_end - y_start).days + 1)
        notes = []
        days = float(rule['full_time_days'] or 0)
        if rule['basis'] == 'fixed':
            allocated = days * share
            notes.append(f"{days:g} days")
            return {'allocated': _half_up(allocated), 'bank_holiday_days': 0.0,
                    'basis': ', '.join(notes + ([f"x {share:.3f} of the year"]
                                                if share < 1 else []))}
        pattern = lr.pattern_of(username, c)
        fte = pattern['fte']
        allocated = days * fte * share
        notes.append(f"{days:g} days x FTE {fte:g}")
        if share < 1:
            notes.append(f"x {share:.3f} of the year")
        booked = 0.0
        settings = lr.settings(c)
        if rule['basis'] == 'fte_pro_rata':
            off = lr.holidays(y_start, y_end, c)
            weekday_holidays = [d for d in off if d.weekday() < 5]
            mine = [d for d in off if start <= d <= end and d.weekday() in pattern['work_days']]
            if rule['includes_bank_holidays']:
                booked = float(len(mine))
                notes.append(f"includes bank holidays; {len(mine)} on working days booked")
            elif settings['bank_holidays_pro_rata']:
                extra = len(weekday_holidays) * fte * share
                allocated += extra
                booked = float(len(mine))
                notes.append(f"+ {extra:.2f} bank holiday days; {len(mine)} on working days booked")
        return {'allocated': _half_up(allocated), 'bank_holiday_days': booked,
                'basis': '; '.join(notes)}
    finally:
        if own:
            c.close()


def carry_over_for(username: str, leave_type_id: int, year: int, conn=None) -> tuple:
    """``(days, expires)`` carried from ``year - 1`` into ``year``."""
    own = conn is None
    c = get_connection() if own else conn
    try:
        rule = rule_for(leave_type_id, c)
        if not rule['carry_over'] or rule['basis'] not in BALANCED:
            return 0.0, None
        prev = c.execute("SELECT * FROM leave_balances WHERE user_id = ? AND leave_type_id = ? "
                         "AND year = ?", (username, leave_type_id, year - 1)).fetchone()
        if not prev:
            return 0.0, None
        settings = lr.settings(c)
        cap = rule['carry_over_cap']
        cap = float(settings['carry_over_cap_days'] if cap is None else cap)
        days = max(0.0, min(remaining(dict(prev)), cap))
        if not days:
            return 0.0, None
        months = int(settings['carry_over_expiry_months'])
        expires = None
        if months > 0:
            expires = (lr.add_months(lr.leave_year_bounds(year, c)[0], months)
                       - timedelta(days=1)).isoformat()
        return days, expires
    finally:
        if own:
            c.close()


def allocate(username: str, leave_type_id: int, year: int, actor: Any = None,
             conn=None, force: bool = False) -> Optional[dict]:
    """Work out and store one balance; returns the row (None: no balance
    for this type). Keeps ``used_days``; leaves a manual balance alone
    unless ``force``."""
    own = conn is None
    c = get_connection() if own else conn
    try:
        lr.ensure(c)
        calc = calculate(username, leave_type_id, year, c)
        if calc is None:
            return None
        existing = c.execute("SELECT * FROM leave_balances WHERE user_id = ? AND "
                             "leave_type_id = ? AND year = ?",
                             (username, leave_type_id, year)).fetchone()
        if existing and existing['allocation_basis'] == 'manual' and not force:
            return dict(existing)
        carried, expires = carry_over_for(username, leave_type_id, year, c)
        stamp = lr.now()
        if existing:
            c.execute("UPDATE leave_balances SET allocated_days = ?, bank_holiday_days = ?, "
                      "carried_over = ?, carry_over_expires = ?, allocation_basis = ?, "
                      "updated_at = ? WHERE balance_id = ?",
                      (calc['allocated'], calc['bank_holiday_days'], carried, expires,
                       calc['basis'], stamp, existing['balance_id']))
        else:
            c.execute("INSERT INTO leave_balances (user_id, leave_type_id, year, allocated_days, "
                      "used_days, carried_over, bank_holiday_days, carry_over_expires, "
                      "carry_over_expired, allocation_basis, created_at, updated_at) "
                      "VALUES (?, ?, ?, ?, 0, ?, ?, ?, 0, ?, ?, ?)",
                      (username, leave_type_id, year, calc['allocated'], carried,
                       calc['bank_holiday_days'], expires, calc['basis'], stamp, stamp))
        if actor is not None:
            access.audit(c, actor, 'leave_allocated', username, 'leave_balances',
                         f"{leave_type_id}/{year}", calc)
        if own:
            c.commit()
        row = c.execute("SELECT * FROM leave_balances WHERE user_id = ? AND leave_type_id = ? "
                        "AND year = ?", (username, leave_type_id, year)).fetchone()
        return dict(row) if row else None
    finally:
        if own:
            c.close()


def ensure_balance(username: str, leave_type_id: int, year: int, conn) -> Optional[dict]:
    """The balance row, allocated by the rules when it does not exist yet."""
    row = conn.execute("SELECT * FROM leave_balances WHERE user_id = ? AND leave_type_id = ? "
                       "AND year = ?", (username, leave_type_id, year)).fetchone()
    if row:
        return dict(row)
    return allocate(username, leave_type_id, year, conn=conn)


def set_manual(actor: Any, username: str, leave_type_id: int, year: int,
               allocated_days: float, carried_over: float = 0, note: str = '') -> dict:
    """HR sets a balance by hand (kept by the daily recalculation)."""
    access.require(actor, 'hr', "Only HR can set a leave balance by hand")
    if float(allocated_days) < 0 or float(carried_over) < 0:
        raise ValueError("Days cannot be negative")
    with get_connection() as conn:
        lr.ensure(conn)
        key = access.staff_key(username, conn) or username
        stamp = lr.now()
        basis = 'manual'
        conn.execute("INSERT INTO leave_balances (user_id, leave_type_id, year, allocated_days, "
                     "used_days, carried_over, allocation_basis, created_at, updated_at) "
                     "VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?) ON CONFLICT(user_id, leave_type_id, year) "
                     "DO UPDATE SET allocated_days = excluded.allocated_days, "
                     "carried_over = excluded.carried_over, allocation_basis = 'manual', "
                     "updated_at = excluded.updated_at",
                     (key, leave_type_id, year, float(allocated_days), float(carried_over),
                      basis, stamp, stamp))
        access.audit(conn, actor, 'leave_balance_manual', key, 'leave_balances',
                     f"{leave_type_id}/{year}", {'allocated': allocated_days,
                                                 'carried_over': carried_over, 'note': note})
        conn.commit()
        return dict(conn.execute("SELECT * FROM leave_balances WHERE user_id = ? AND "
                                 "leave_type_id = ? AND year = ?",
                                 (key, leave_type_id, year)).fetchone())


def staff_usernames(conn) -> list:
    """Everyone who takes staff leave: staff profiles plus staff logins."""
    names = {r[0] for r in conn.execute("SELECT user_id FROM staff_profiles "
                                        "WHERE user_id IS NOT NULL AND user_id != ''")}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    service = " AND COALESCE(service_account, 0) = 0" if 'service_account' in cols else ''
    names |= {r[0] for r in conn.execute(
        "SELECT username FROM users WHERE LOWER(COALESCE(role, '')) IN "
        f"('staff', 'instructor', 'lecturer', 'admin', 'administrator'){service}")}
    return sorted(n for n in names if n)


def allocate_year(actor: Any = None, year: Optional[int] = None, users: Optional[list] = None,
                  force: bool = False) -> dict:
    """Allocate every balanced leave type for everyone (or ``users``) for
    ``year`` (default: the current leave year). ``actor`` None is the
    scheduler; a person must be HR."""
    if actor is not None:
        access.require(actor, 'hr', "Only HR can allocate leave")
    with get_connection() as conn:
        lr.ensure(conn)
        target = year if year is not None else lr.leave_year_of(None, conn)
        people = [access.staff_key(u, conn) or u for u in users] if users else \
            staff_usernames(conn)
        types = [t['leave_type_id'] for t in conn.execute(
            "SELECT leave_type_id FROM leave_types WHERE is_active = 1").fetchall()
            if is_balanced(t['leave_type_id'], conn)]
        done = skipped = 0
        for person in people:
            for type_id in types:
                before = conn.execute("SELECT allocation_basis FROM leave_balances WHERE "
                                      "user_id = ? AND leave_type_id = ? AND year = ?",
                                      (person, type_id, target)).fetchone()
                if before and before[0] == 'manual' and not force:
                    skipped += 1
                    continue
                if allocate(person, type_id, target, actor, conn, force):
                    done += 1
        conn.commit()
        return {'year': target, 'people': len(people), 'allocated': done,
                'manual_kept': skipped}


def expire_carry_over(on: Optional[date] = None) -> dict:
    """Expire carried days whose expiry date has passed; warn people a
    month before."""
    on = on or lr.today()
    with lr.write() as c:
        expired = warned = 0
        for b in c.execute("SELECT b.*, t.name AS leave_type_name FROM leave_balances b "
                           "JOIN leave_types t ON t.leave_type_id = b.leave_type_id "
                           "WHERE COALESCE(b.carried_over, 0) > 0 AND b.carry_over_expires "
                           "IS NOT NULL AND COALESCE(b.carry_over_expired, 0) = 0").fetchall():
            b = dict(b)
            ends = lr.as_date(b['carry_over_expires'])
            unused = max(0.0, float(b['carried_over']) - float(b['used_days'] or 0))
            if ends < on:
                c.execute("UPDATE leave_balances SET carry_over_expired = ?, updated_at = ? "
                          "WHERE balance_id = ?", (unused, lr.now(), b['balance_id']))
                expired += 1
            elif unused and (ends - on).days <= 30 and \
                    lr.remind_once(c, f"carry_expiry:{b['balance_id']}", b['user_id']):
                lr.mail(b['user_id'], f"{unused:g} carried {b['leave_type_name']} days expire "
                        f"on {ends.isoformat()}",
                        f"You have {unused:g} {b['leave_type_name']} days carried over from last "
                        f"year that expire on {ends.isoformat()}. Book them before then or "
                        "they will be lost.")
                warned += 1
        return {'expired': expired, 'warned': warned}


def leaver_position(actor: Any, username: str, leaving: Optional[str] = None) -> list:
    """Each balanced type for a leaver: days owed (positive) or taken in
    advance (negative), pro rata to the leaving date — for final pay."""
    with get_connection() as conn:
        lr.ensure(conn)
        key = access.staff_key(username, conn) or username
        if not (access.can(actor, 'hr', conn) or access.can_view_pay(actor, key, conn)):
            raise PermissionError("Only HR or payroll can see a leaver's leave position")
        year = lr.leave_year_of(leaving, conn)
        out = []
        for t in conn.execute("SELECT * FROM leave_types WHERE is_active = 1").fetchall():
            calc = calculate(key, t['leave_type_id'], year, conn, leaving)
            if calc is None:
                continue
            bal = conn.execute("SELECT * FROM leave_balances WHERE user_id = ? AND "
                               "leave_type_id = ? AND year = ?",
                               (key, t['leave_type_id'], year)).fetchone()
            bal = dict(bal) if bal else {}
            row = {'allocated_days': calc['allocated'],
                   'carried_over': bal.get('carried_over', 0),
                   'carry_over_expired': bal.get('carry_over_expired', 0),
                   'used_days': bal.get('used_days', 0),
                   'bank_holiday_days': calc['bank_holiday_days']}
            out.append({'leave_type_id': t['leave_type_id'], 'leave_type_name': t['name'],
                        'year': year, **row, 'position': remaining(row)})
        access.audit(conn, actor, 'leaver_leave_position', key, 'leave_balances', year)
        conn.commit()
        return out


def run_daily(on: Optional[date] = None) -> dict:
    """Scheduler job: allocate the current leave year for everyone (starters
    get theirs, leavers are pro-rated; manual balances kept) and expire /
    warn about carried days."""
    on = on or lr.today()
    with get_connection() as conn:
        lr.ensure(conn)
        year = lr.leave_year_of(on, conn)
    result = allocate_year(None, year)
    result.update(expire_carry_over(on))
    return result


__all__ = [
    'BASES', 'BASIS_LABELS', 'BALANCED', 'default_rule', 'rule_for', 'rules', 'is_balanced',
    'set_rule', 'remaining', 'calculate', 'carry_over_for', 'allocate', 'ensure_balance',
    'set_manual', 'staff_usernames', 'allocate_year', 'expire_carry_over', 'leaver_position',
    'run_daily',
]
