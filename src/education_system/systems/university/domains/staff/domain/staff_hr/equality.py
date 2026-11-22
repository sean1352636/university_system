"""Staff equality monitoring.

Each member of staff may — voluntarily — tell the university their sex,
gender identity, ethnicity, disability, religion or belief, sexual
orientation and caring responsibilities. Every question has "Prefer not to
say", and leaving a question unanswered is just as valid.

**Kept apart.** Declarations live in ``staff_equality_declarations``, not in
the personnel record, and no screen or manager joins them back to a person:

* the person reads and changes their own (:func:`get_own`, :func:`declare`)
  and may withdraw it entirely (:func:`withdraw`);
* HR sees them only as counts (:func:`aggregate`), with every group smaller
  than the configured minimum (default 5) suppressed — and, where one hidden
  number could be worked out from the total, the next smallest too;
* the gender pay gap and the HESA staff return read them inside
  ``pay_gap`` / ``hesa_staff`` for their statutory purpose.

The categories follow the ONS 2021 census and HESA staff record groupings, so
the HESA return can code them directly.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.infrastructure.database.db import get_connection

PREFER_NOT = 'Prefer not to say'
NOT_DECLARED = 'Not declared'

#: field -> (question, answers). "Prefer not to say" is always the last answer.
CATEGORIES: dict = {
    'sex': ("Sex", ('Female', 'Male', 'Other', PREFER_NOT)),
    'gender_identity': (
        "Is your gender identity the same as the sex you were registered at birth?",
        ('Yes', 'No', PREFER_NOT)),
    'ethnicity': ("Ethnic group", (
        'Asian or Asian British - Bangladeshi',
        'Asian or Asian British - Chinese',
        'Asian or Asian British - Indian',
        'Asian or Asian British - Pakistani',
        'Any other Asian background',
        'Black or Black British - African',
        'Black or Black British - Caribbean',
        'Any other Black background',
        'Mixed - White and Asian',
        'Mixed - White and Black African',
        'Mixed - White and Black Caribbean',
        'Any other Mixed or multiple ethnic background',
        'White - English, Welsh, Scottish, Northern Irish or British',
        'White - Irish',
        'White - Gypsy or Irish Traveller',
        'White - Roma',
        'Any other White background',
        'Arab',
        'Any other ethnic group',
        PREFER_NOT)),
    'disability': ("Disability", (
        'No known disability',
        'Learning difference such as dyslexia or dyspraxia',
        'Social or communication impairment such as autism',
        'Long-standing illness or health condition',
        'Mental health condition',
        'Physical impairment',
        'Deaf or serious hearing impairment',
        'Blind or serious visual impairment',
        'A disability, impairment or condition not listed',
        'Two or more impairments or conditions',
        PREFER_NOT)),
    'religion': ("Religion or belief", (
        'No religion', 'Buddhist', 'Christian', 'Hindu', 'Jewish', 'Muslim', 'Sikh',
        'Spiritual', 'Any other religion or belief', PREFER_NOT)),
    'sexual_orientation': ("Sexual orientation", (
        'Bisexual', 'Gay man', 'Gay woman or lesbian', 'Heterosexual or straight',
        'Other sexual orientation', PREFER_NOT)),
    'caring_responsibilities': ("Caring responsibilities", (
        'None',
        'Primary carer of a child or children (under 18)',
        'Primary carer of a disabled child or children',
        'Primary carer of a disabled adult (18 and over)',
        'Primary carer of an older person (65 and over)',
        'Secondary carer',
        PREFER_NOT)),
}
FIELDS = tuple(CATEGORIES)
DEFAULT_MIN_GROUP = 5
#: Breakdowns HR may ask for (personnel fields, never another equality field).
GROUP_BY = ('department', 'job_title', 'employment_type')


def _ensure(conn) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_ddl,
    )
    staff_hr_ddl.apply_to_connection(conn)


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── settings ────────────────────────────────────────────────────────────


def setting(key: str, default: Any = None, conn=None) -> Any:
    own = conn is None
    c = conn if conn is not None else get_connection()
    try:
        _ensure(c)
        row = c.execute("SELECT value FROM staff_compliance_settings WHERE key = ?",
                        (key,)).fetchone()
        return row[0] if row and row[0] not in (None, '') else default
    finally:
        if own:
            c.close()


def set_setting(actor: Any, key: str, value: Any) -> None:
    """Change a compliance setting (HR administrators)."""
    access.require(actor, 'hr_admin', "Only an HR administrator can change compliance settings")
    with get_connection() as conn:
        _ensure(conn)
        old = setting(key, conn=conn)
        conn.execute("INSERT INTO staff_compliance_settings (key, value, updated_by, updated_at) "
                     "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                     "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                     (key, None if value is None else str(value), access.username_of(actor),
                      _now()))
        access.audit(conn, actor, 'compliance.setting', entity='staff_compliance_settings',
                     entity_id=key, details={'from': old, 'to': value})


def min_group(conn=None) -> int:
    """Smallest group HR reports show (smaller ones are suppressed)."""
    try:
        return max(1, int(setting('equality_min_group', DEFAULT_MIN_GROUP, conn)))
    except (TypeError, ValueError):
        return DEFAULT_MIN_GROUP


def set_min_group(actor: Any, value: int) -> None:
    value = int(value)
    if value < 2:
        raise ValueError("The smallest reportable group must be at least 2")
    set_setting(actor, 'equality_min_group', value)


# ── the person's own declaration ────────────────────────────────────────


def get_own(actor: Any) -> Optional[dict]:
    """The signed-in person's declaration (None if they have not made one)."""
    me = access.require_user(actor)['username']
    with get_connection() as conn:
        _ensure(conn)
        row = conn.execute("SELECT * FROM staff_equality_declarations WHERE username = ?",
                           (me,)).fetchone()
    return dict(row) if row else None


def validate(answers: dict) -> dict:
    """Only known questions and answers; blank means "not answered"."""
    clean = {}
    for field, value in (answers or {}).items():
        if field not in CATEGORIES:
            raise ValueError(f"Unknown equality question '{field}'")
        text = str(value).strip() if value is not None else ''
        if not text:
            clean[field] = None
            continue
        if text not in CATEGORIES[field][1]:
            raise ValueError(f"'{text}' is not an answer to '{CATEGORIES[field][0]}'")
        clean[field] = text
    return clean


def declare(actor: Any, **answers) -> dict:
    """Save (or change) the signed-in person's own answers. Only the person
    themselves can — nobody declares on someone else's behalf."""
    me = access.require_user(actor)['username']
    clean = validate(answers)
    with get_connection() as conn:
        _ensure(conn)
        exists = conn.execute("SELECT 1 FROM staff_equality_declarations WHERE username = ?",
                              (me,)).fetchone()
        if exists:
            if clean:
                sets = ", ".join(f"{f} = ?" for f in clean)
                conn.execute(f"UPDATE staff_equality_declarations SET {sets}, "  # nosec B608
                             "updated_at = ? WHERE username = ?",
                             (*clean.values(), _now(), me))
        else:
            cols = ['username', *clean, 'declared_at', 'updated_at']
            conn.execute(f"INSERT INTO staff_equality_declarations ({', '.join(cols)}) "  # nosec B608
                         f"VALUES ({', '.join('?' * len(cols))})",
                         (me, *clean.values(), _now(), _now()))
        # The answers themselves never go into the audit trail.
        access.audit(conn, actor, 'equality.declared', subject=me,
                     entity='staff_equality_declarations', details={'questions': sorted(clean)})
    return get_own(actor) or {}


def withdraw(actor: Any) -> bool:
    """Delete the signed-in person's declaration altogether."""
    me = access.require_user(actor)['username']
    with get_connection() as conn:
        _ensure(conn)
        gone = conn.execute("DELETE FROM staff_equality_declarations WHERE username = ?",
                            (me,)).rowcount
        if gone:
            access.audit(conn, actor, 'equality.withdrawn', subject=me,
                         entity='staff_equality_declarations')
    return bool(gone)


# ── HR: counts only ─────────────────────────────────────────────────────


def current_staff(conn, on: Optional[str] = None) -> list:
    """Staff in post on ``on`` (default today) as personnel rows."""
    on = on or date.today().isoformat()
    rows = conn.execute("SELECT user_id, department, job_title, employment_type FROM staff_profiles "
                        "WHERE (contract_end_date IS NULL OR contract_end_date = '' "
                        "OR contract_end_date >= ?) "
                        "AND (hire_date IS NULL OR hire_date = '' OR hire_date <= ?)",
                        (on, on)).fetchall()
    return [dict(zip(('username', 'department', 'job_title', 'employment_type'), r))
            for r in rows]


def suppress(counts: list, threshold: int) -> list:
    """``[(label, n)]`` -> ``[(label, n or None)]``: any 0 < n < threshold is
    hidden, and when exactly one cell is hidden (so total minus the rest
    would reveal it) the smallest other non-zero cell is hidden too."""
    out = [(label, None if 0 < n < threshold else n) for label, n in counts]
    hidden = [i for i, (_, v) in enumerate(out) if v is None]
    if len(hidden) == 1:
        others = sorted((n, i) for i, (_, n) in enumerate(counts)
                        if i not in hidden and n > 0)
        if others:
            i = others[0][1]
            out[i] = (out[i][0], None)
    return out


def _tally(people: list, declared: dict, field: str) -> list:
    counts = {a: 0 for a in CATEGORIES[field][1]}
    counts[NOT_DECLARED] = 0
    for p in people:
        answer = (declared.get(p['username']) or {}).get(field)
        counts[answer if answer in counts else NOT_DECLARED] += 1
    return list(counts.items())


def aggregate(actor: Any, fields: Optional[list] = None, group_by: Optional[str] = None,
              on: Optional[str] = None) -> dict:
    """Counts of staff in post by each answer (HR reports capability).

    ``group_by`` (one of :data:`GROUP_BY`) splits each field by a personnel
    attribute; a whole group smaller than the minimum is shown only as
    "suppressed". Hidden counts are ``None``.
    """
    access.require(actor, 'reports', "Equality monitoring is available to HR only")
    fields = [f for f in (fields or FIELDS) if f in CATEGORIES]
    if group_by is not None and group_by not in GROUP_BY:
        raise ValueError(f"Cannot break equality data down by '{group_by}'")
    with get_connection() as conn:
        _ensure(conn)
        k = min_group(conn)
        people = current_staff(conn, on)
        declared = {r['username']: dict(r) for r in conn.execute(
            "SELECT * FROM staff_equality_declarations").fetchall()}
        groups: dict = {}
        if group_by:
            for p in people:
                groups.setdefault(p.get(group_by) or 'Not recorded', []).append(p)
        report: dict = {
            'on': on or date.today().isoformat(),
            'population': len(people),
            'declared': sum(1 for p in people if p['username'] in declared),
            'min_group': k,
            'group_by': group_by,
            'fields': {},
        }
        for field in fields:
            entry: dict = {'question': CATEGORIES[field][0],
                           'rows': suppress(_tally(people, declared, field), k)}
            if group_by:
                entry['groups'] = {
                    name: (suppress(_tally(members, declared, field), k)
                           if len(members) >= k else None)
                    for name, members in sorted(groups.items())}
            report['fields'][field] = entry
        access.audit(conn, actor, 'equality.report', entity='staff_equality_declarations',
                     details={'fields': fields, 'group_by': group_by})
    return report


def report_lines(report: dict) -> list:
    """Plain-text lines for :func:`aggregate`'s result (CLI and GUI)."""
    k = report['min_group']
    lines = [f"Staff in post on {report['on']}: {report['population']}",
             f"Made a declaration: {report['declared']}",
             f"Groups smaller than {k} are shown as '<{k}' (and one more where needed "
             f"to stop the hidden one being worked out).", ""]

    def cell(v):
        return f"<{k}" if v is None else str(v)

    for field, entry in report['fields'].items():
        lines.append(entry['question'])
        lines.append("-" * min(70, max(20, len(entry['question']))))
        for label, n in entry['rows']:
            lines.append(f"  {label[:58]:<58}{cell(n):>8}")
        for group, rows in (entry.get('groups') or {}).items():
            if rows is None:
                lines.append(f"  [{group}] suppressed (fewer than {k} staff)")
                continue
            shown = ", ".join(f"{label}: {cell(n)}" for label, n in rows if n != 0)
            lines.append(f"  [{group}] {shown or 'none'}")
        lines.append("")
    return lines


def declarations_for(conn, usernames: Optional[list] = None) -> dict:
    """username -> declaration, for the statutory reports in this package
    (gender pay gap, HESA). Not for screens."""
    _ensure(conn)
    rows = conn.execute("SELECT * FROM staff_equality_declarations").fetchall()
    wanted = set(usernames) if usernames is not None else None
    return {r['username']: dict(r) for r in rows if wanted is None or r['username'] in wanted}


def erase(conn, username: str) -> int:
    """Remove a person's declaration (retention / erasure, inside the
    caller's transaction)."""
    _ensure(conn)
    return conn.execute("DELETE FROM staff_equality_declarations WHERE username = ?",
                        (username,)).rowcount


__all__ = [
    'CATEGORIES', 'FIELDS', 'GROUP_BY', 'NOT_DECLARED', 'PREFER_NOT', 'aggregate', 'declare',
    'declarations_for', 'erase', 'get_own', 'min_group', 'report_lines', 'set_min_group',
    'set_setting', 'setting', 'suppress', 'validate', 'withdraw', 'current_staff',
]
