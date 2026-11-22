"""Gender pay gap (Equality Act 2010 (Specific Duties and Public Authorities)
Regulations 2017 — the public-sector snapshot is 31 March).

For every member of staff on a contract on the snapshot date:

* **hourly pay** = annual pay / (weekly hours x 52.143). Weekly hours are the
  contract's ``working_hours_per_week``; failing that its ``fte`` (where the
  contract has one) x the standard week; failing that the standard week
  (setting ``standard_hours_per_week``, default 37.5 — flagged).
* **mean and median gap** = (men's - women's) / men's, as a percentage of
  men's pay. A positive gap means women are paid less.
* **quartiles** — everyone ranked by hourly pay, split into four equal
  groups, with the share of women and men in each.
* **bonus gap** — bonus pay (``payroll_allowances`` whose type mentions
  "bonus") in the twelve months ending on the snapshot: mean and median gap
  among those who received one, and the share of women and men who did.

Sex comes from the person's voluntary equality declaration
(``equality.py``). Anyone who has not declared Female or Male is left out
and counted separately — the report says how many, so HR can judge whether
the figures are representative.

HR and payroll only; every run is audited.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, median
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access, equality
from education_system.systems.university.infrastructure.database.db import get_connection

WEEKS_PER_YEAR = 52.143
#: Employers with fewer than this many relevant employees need not publish.
PUBLISH_THRESHOLD = 250
#: Pay frequency -> multiplier to annual pay ('hourly' is handled apart).
ANNUAL = {
    None: 1, '': 1, 'annual': 1, 'annually': 1, 'yearly': 1, 'year': 1, 'salary': 1,
    'monthly': 12, 'month': 12, 'four_weekly': 13, '4-weekly': 13, 'fortnightly': 26.0715,
    'biweekly': 26.0715, 'weekly': WEEKS_PER_YEAR, 'week': WEEKS_PER_YEAR,
}
CLOSED_CONTRACTS = ('terminated', 'cancelled', 'draft', 'rejected', 'void')
QUARTILES = ('Lower', 'Lower middle', 'Upper middle', 'Upper')


def snapshot_for(today: Optional[date] = None) -> date:
    """The most recent 31 March on or before ``today``."""
    today = today or date.today()
    this_year = date(today.year, 3, 31)
    return this_year if today >= this_year else date(today.year - 1, 3, 31)


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _require(actor: Any) -> dict:
    user = access.require_user(actor)
    if not (access.can(actor, 'reports') or access.can(actor, 'payroll')):
        raise PermissionError("The gender pay gap report is available to HR and payroll only")
    return user


def _gap(men: list, women: list, fn) -> Optional[float]:
    if not men or not women:
        return None
    m = fn(men)
    return None if not m else round((m - fn(women)) / m * 100, 1)


def _contracts(conn, snap: date) -> dict:
    """username -> the contract in force on the snapshot (latest start)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(staff_contracts)").fetchall()}
    fte = 'fte' if 'fte' in cols else 'NULL'
    rows = conn.execute(
        f"SELECT contract_id, user_id, salary, pay_frequency, working_hours_per_week, "  # nosec B608
        f"{fte} AS fte, start_date, end_date, status FROM staff_contracts "
        "WHERE start_date IS NOT NULL AND start_date <= ? "
        "AND (end_date IS NULL OR end_date = '' OR end_date >= ?) "
        "AND lower(coalesce(status, 'active')) NOT IN (%s) "
        "ORDER BY start_date" % ", ".join("?" * len(CLOSED_CONTRACTS)),
        (snap.isoformat(), snap.isoformat(), *CLOSED_CONTRACTS)).fetchall()
    out: dict = {}
    for r in rows:
        key = access.staff_key(r['user_id'], conn) or r['user_id']
        out[key] = dict(r)
    return out


def _hourly(contract: dict, standard: float) -> tuple:
    """(hourly pay, weekly hours, note) for a contract."""
    salary = contract.get('salary')
    if salary in (None, ''):
        return None, None, 'no salary on the contract'
    salary = float(salary)
    freq = str(contract.get('pay_frequency') or '').strip().lower()
    hours, note = contract.get('working_hours_per_week'), None
    if hours in (None, '', 0):
        fte = contract.get('fte')
        if fte not in (None, '', 0):
            hours = float(fte) * standard
        else:
            hours, note = standard, f'no weekly hours; assumed {standard:g}'
    hours = float(hours)
    if freq == 'hourly':
        return round(salary, 4), hours, note
    if freq not in ANNUAL:
        note = (note + '; ' if note else '') + f"pay frequency '{freq}' read as annual"
    annual = salary * ANNUAL.get(freq, 1)
    return round(annual / (hours * WEEKS_PER_YEAR), 4), hours, note


def _bonuses(conn, snap: date) -> dict:
    """username -> bonus paid in the 12 months ending on the snapshot."""
    try:
        rows = conn.execute(
            "SELECT user_id, amount FROM payroll_allowances "
            "WHERE lower(allowance_type) LIKE '%bonus%' AND coalesce(start_date, created_at) > ? "
            "AND coalesce(start_date, created_at) <= ?",
            ((snap - timedelta(days=365)).isoformat(), snap.isoformat() + ' 23:59:59')).fetchall()
    except Exception:
        return {}
    out: dict = {}
    for r in rows:
        key = access.staff_key(r['user_id'], conn) or r['user_id']
        out[key] = out.get(key, 0.0) + float(r['amount'] or 0)
    return {k: v for k, v in out.items() if v > 0}


def quartiles(people: list) -> list:
    """Four equal groups by hourly pay: [(name, women, men)]."""
    ranked = sorted(people, key=lambda p: p['hourly'])
    n = len(ranked)
    out = []
    for i, name in enumerate(QUARTILES):
        part = ranked[round(n * i / 4):round(n * (i + 1) / 4)]
        women = sum(1 for p in part if p['sex'] == 'Female')
        out.append({'quartile': name, 'size': len(part), 'women': women,
                    'men': len(part) - women,
                    'women_pct': round(women / len(part) * 100, 1) if part else None,
                    'men_pct': round((len(part) - women) / len(part) * 100, 1) if part else None})
    return out


def gender_pay_gap(actor: Any, snapshot: Any = None) -> dict:
    """The report for ``snapshot`` (a date; default the latest 31 March)."""
    _require(actor)
    snap = _date(snapshot) if snapshot else snapshot_for()
    with get_connection() as conn:
        equality._ensure(conn)
        try:
            standard = float(equality.setting('standard_hours_per_week', 37.5, conn))
        except (TypeError, ValueError):
            standard = 37.5
        contracts = _contracts(conn, snap)
        declared = equality.declarations_for(conn, list(contracts))
        bonuses = _bonuses(conn, snap)
        people, notes, excluded = [], [], {'no declared sex': 0, 'no pay': 0}
        for username, contract in sorted(contracts.items()):
            sex = (declared.get(username) or {}).get('sex')
            hourly, hours, note = _hourly(contract, standard)
            if hourly is None:
                excluded['no pay'] += 1
                notes.append(f"{username}: {note}")
                continue
            if sex not in ('Female', 'Male'):
                excluded['no declared sex'] += 1
                continue
            if note:
                notes.append(f"{username}: {note}")
            people.append({'username': username, 'sex': sex, 'hourly': hourly,
                           'bonus': bonuses.get(username, 0.0)})
        women = [p['hourly'] for p in people if p['sex'] == 'Female']
        men = [p['hourly'] for p in people if p['sex'] == 'Male']
        w_bonus = [p['bonus'] for p in people if p['sex'] == 'Female' and p['bonus'] > 0]
        m_bonus = [p['bonus'] for p in people if p['sex'] == 'Male' and p['bonus'] > 0]
        warnings = []
        if len(contracts) < PUBLISH_THRESHOLD:
            warnings.append(f"{len(contracts)} relevant employees — fewer than "
                            f"{PUBLISH_THRESHOLD}, so publication is not required.")
        if not women or not men:
            warnings.append("No gap can be calculated without both women and men in the figures.")
        if excluded['no declared sex']:
            warnings.append(f"{excluded['no declared sex']} employee(s) left out: sex not declared "
                            "as Female or Male.")
        result = {
            'snapshot': snap.isoformat(),
            'relevant_employees': len(contracts),
            'counted': len(people),
            'women': len(women),
            'men': len(men),
            'excluded': excluded,
            'mean_hourly': {'women': round(mean(women), 2) if women else None,
                            'men': round(mean(men), 2) if men else None},
            'median_hourly': {'women': round(median(women), 2) if women else None,
                              'men': round(median(men), 2) if men else None},
            'mean_gap_pct': _gap(men, women, mean),
            'median_gap_pct': _gap(men, women, median),
            'quartiles': quartiles(people),
            'bonus_mean_gap_pct': _gap(m_bonus, w_bonus, mean),
            'bonus_median_gap_pct': _gap(m_bonus, w_bonus, median),
            'bonus_received_pct': {
                'women': round(len(w_bonus) / len(women) * 100, 1) if women else None,
                'men': round(len(m_bonus) / len(men) * 100, 1) if men else None},
            'warnings': warnings,
            'notes': notes,
        }
        access.audit(conn, actor, 'pay_gap.report', entity='staff_contracts',
                     details={'snapshot': snap.isoformat(), 'counted': len(people)})
    return result


def report_lines(r: dict) -> list:
    """Plain-text lines for :func:`gender_pay_gap` (CLI and GUI)."""
    def pct(v):
        return "n/a" if v is None else f"{v:.1f}%"

    def money(v):
        return "n/a" if v is None else f"£{v:,.2f}"

    lines = [f"Snapshot date: {r['snapshot']}",
             f"Relevant employees: {r['relevant_employees']}   counted: {r['counted']} "
             f"(women {r['women']}, men {r['men']})", "",
             f"{'':<24}{'Women':>12}{'Men':>12}{'Gap':>10}",
             f"{'Mean hourly pay':<24}{money(r['mean_hourly']['women']):>12}"
             f"{money(r['mean_hourly']['men']):>12}{pct(r['mean_gap_pct']):>10}",
             f"{'Median hourly pay':<24}{money(r['median_hourly']['women']):>12}"
             f"{money(r['median_hourly']['men']):>12}{pct(r['median_gap_pct']):>10}", "",
             "Pay quartiles", f"{'':<16}{'Size':>6}{'Women':>10}{'Men':>10}"]
    for q in r['quartiles']:
        lines.append(f"{q['quartile']:<16}{q['size']:>6}{pct(q['women_pct']):>10}"
                     f"{pct(q['men_pct']):>10}")
    lines += ["", f"Bonus mean gap: {pct(r['bonus_mean_gap_pct'])}   "
                  f"median gap: {pct(r['bonus_median_gap_pct'])}",
              f"Received a bonus: women {pct(r['bonus_received_pct']['women'])}, "
              f"men {pct(r['bonus_received_pct']['men'])}"]
    if r['warnings']:
        lines += ["", "Warnings:"] + [f"  - {w}" for w in r['warnings']]
    if r['notes']:
        lines += ["", "Data notes:"] + [f"  - {n}" for n in r['notes']]
    return lines


__all__ = ['gender_pay_gap', 'quartiles', 'report_lines', 'snapshot_for', 'WEEKS_PER_YEAR']
