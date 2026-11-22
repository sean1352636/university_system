"""HR record retention.

How long each kind of HR record is kept is a policy in
``staff_retention_policies`` (HR administrators change it with
:func:`update_policy`). The defaults follow common UK practice (CIPD /
HMRC / Home Office guidance):

=======================  ==========  =========================  ===========
record                   keep        counted from               then
=======================  ==========  =========================  ===========
leavers' personnel file  6 years     leaving                    anonymise
grievance cases          6 years     closure                    delete
disciplinary cases       6 years     closure                    delete
unsuccessful applicants  6 months    the decision               delete
right to work checks     2 years     employment ending          delete
sickness absence         3 years     the absence ending         delete
payroll                  6 years     the pay period ending      anonymise
=======================  ==========  =========================  ===========

*Anonymise* keeps a record's numbers for statistics and removes who it was
about; for a leaver's file that means every Staff HR table's reference to
the username becomes a pseudonym (``former-…``), their personal fields are
cleared, their equality declaration is deleted and the staff directory row
says "Former member of staff". *Delete* removes the record and its child
rows.

A person under a hold (:func:`place_hold` — litigation, a tribunal, an open
investigation) is skipped until the hold is released.

:func:`preview` shows what is due; :func:`run` does it (HR administrators,
audited, logged in ``staff_retention_runs``); :func:`daily_job` runs it
unattended each day; :func:`erase_leaver` applies everything due for one
leaver now (a right-to-erasure request), keeping only what the law still
requires.

Other Staff HR schema modules can add their own tables by declaring
``RETENTION_TARGETS`` — a tuple of dicts shaped like :data:`TARGETS`' values
plus ``'record_type'``.
"""

from __future__ import annotations

import importlib
import logging
import secrets
from datetime import date, datetime
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access, equality
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

ACTIONS = ('anonymise', 'delete')
ANON = '[anonymised]'
#: Record types whose retention is a legal duty: an erasure request keeps
#: them until their period ends.
STATUTORY = ('payroll', 'right_to_work')
CLOSED_CASE = ('closed', 'resolved', 'withdrawn', 'dismissed', 'dropped', 'completed', 'no_case',
               'upheld', 'not_upheld', 'partially_upheld', 'appeal_closed', 'concluded')
UNSUCCESSFUL = ('rejected', 'unsuccessful', 'withdrawn', 'declined', 'not_shortlisted',
                'offer_declined', 'closed')
#: Leaver: the person's leaving date is ``'@left'`` instead of a column.
LEFT = '@left'
#: Personal fields cleared when a leaver's file is anonymised.
PROFILE_PERSONAL = ('employee_id', 'office_location', 'phone_extension', 'emergency_contact_name',
                    'emergency_contact_phone', 'emergency_contact_relationship', 'bio',
                    'expertise_areas', 'qualifications', 'date_of_birth', 'nationality')

#: Built-in targets. Each: ``table``, ``pk``, ``person`` (username column),
#: ``date`` (SQL over the row giving the trigger date, or :data:`LEFT`),
#: optional ``where`` (SQL), ``children`` ((table, fk column)) deleted first,
#: ``anonymise`` ({column: value}) for the anonymise action.
TARGETS: dict = {
    'grievance': (
        {'table': 'grievances', 'pk': 'grievance_id', 'person': 'complainant_id',
         'date': "coalesce(resolution_date, updated_at, filed_date)",
         'where': "lower(coalesce(status, '')) IN ({closed})",
         'children': (('grievance_actions', 'grievance_id'), ('grievance_meetings', 'grievance_id')),
         'anonymise': {'complainant_id': ANON, 'respondent_id': None, 'subject': ANON,
                       'description': ANON, 'resolution_summary': None, 'outcome': None,
                       'category_other': None}},
    ),
    'discipline': (
        {'table': 'staff_disciplinary_records', 'pk': 'record_id', 'person': 'user_id',
         'date': "coalesce(updated_at, date_reported, date_occurred)",
         'where': "lower(coalesce(status, '')) IN ({closed})",
         'children': (('staff_disciplinary_appeals', None), ('staff_disciplinary_actions', 'record_id')),
         'anonymise': {'user_id': ANON, 'description': ANON, 'witnesses': None,
                       'evidence_path': None, 'investigation_notes': None, 'reported_by': None}},
    ),
    'unsuccessful_applicant': (
        {'table': 'staff_recruitment_applications', 'pk': 'application_id', 'person': None,
         'date': "coalesce(shortlisted_date, application_date)",
         'where': "lower(coalesce(status, '')) IN ({unsuccessful})",
         'children': (('staff_recruitment_interviews', 'application_id'),),
         'files': ('cv_path', 'cover_letter_path'),
         'anonymise': {'applicant_name': ANON, 'applicant_email': None, 'applicant_phone': None,
                       'applicant_address': None, 'cv_path': None, 'cover_letter_path': None,
                       'portfolio_url': None, 'notes': None}},
    ),
    'sickness': (
        {'table': 'leave_requests', 'pk': 'request_id', 'person': 'user_id',
         'date': "coalesce(end_date, start_date)",
         'where': "leave_type_id IN (SELECT leave_type_id FROM leave_types "
                  "WHERE lower(name) LIKE '%sick%')",
         'anonymise': {'user_id': ANON, 'reason': None, 'document_path': None}},
    ),
    'payroll': (
        {'table': 'payroll_records', 'pk': 'record_id', 'person': 'user_id',
         'date': "(SELECT p.end_date FROM payroll_periods p WHERE p.period_id = payroll_records.period_id)",
         'anonymise': {'user_id': ANON, 'contract_id': None, 'payment_reference': None,
                       'notes': None}},
        {'table': 'payroll_allowances', 'pk': 'allowance_id', 'person': 'user_id',
         'date': "coalesce(end_date, start_date, created_at)",
         'anonymise': {'user_id': ANON, 'notes': None, 'approved_by': None}},
        {'table': 'payroll_overtime', 'pk': 'overtime_id', 'person': 'user_id', 'date': "date",
         'anonymise': {'user_id': ANON, 'reason': None, 'approved_by': None}},
    ),
    'right_to_work': (
        {'table': 'documents', 'pk': 'document_id', 'person': 'owner_id', 'date': LEFT,
         'where': "lower(coalesce(document_type, '')) IN ('right_to_work', 'right to work', "
                  "'rtw', 'visa', 'passport', 'brp', 'share_code')",
         'files': ('file_path',),
         'anonymise': {'owner_id': ANON, 'file_path': None, 'file_content': None,
                       'original_filename': None, 'notes': None}},
    ),
}


def _ensure(conn) -> None:
    equality._ensure(conn)


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _day(value) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return date(year, month, 28)


def cutoff(now: date, keep_months: int) -> date:
    """Records whose trigger date is before this are due."""
    return add_months(now, -int(keep_months))


# ── policies and holds ──────────────────────────────────────────────────


def policies(conn=None) -> list:
    own = conn is None
    c = conn if conn is not None else get_connection()
    try:
        _ensure(c)
        return [dict(r) for r in c.execute("SELECT * FROM staff_retention_policies "
                                           "ORDER BY record_type").fetchall()]
    finally:
        if own:
            c.close()


def update_policy(actor: Any, record_type: str, keep_months: Optional[int] = None,
                  action: Optional[str] = None, enabled: Optional[bool] = None) -> dict:
    """Change one policy (HR administrators; audited)."""
    access.require(actor, 'hr_admin', "Only an HR administrator can change retention policies")
    if action is not None and action not in ACTIONS:
        raise ValueError(f"Action must be one of {', '.join(ACTIONS)}")
    if keep_months is not None and int(keep_months) < 0:
        raise ValueError("Keep months cannot be negative")
    with get_connection() as conn:
        _ensure(conn)
        old = conn.execute("SELECT * FROM staff_retention_policies WHERE record_type = ?",
                           (record_type,)).fetchone()
        if not old:
            raise LookupError(f"No retention policy '{record_type}'")
        new = {'keep_months': int(keep_months) if keep_months is not None else old['keep_months'],
               'action': action or old['action'],
               'enabled': (1 if enabled else 0) if enabled is not None else old['enabled']}
        conn.execute("UPDATE staff_retention_policies SET keep_months = ?, action = ?, enabled = ?, "
                     "updated_by = ?, updated_at = ? WHERE record_type = ?",
                     (new['keep_months'], new['action'], new['enabled'],
                      access.username_of(actor), _now(), record_type))
        access.audit(conn, actor, 'retention.policy', entity='staff_retention_policies',
                     entity_id=record_type,
                     details={'from': {k: old[k] for k in new}, 'to': new})
    return {**dict(old), **new}


def holds(conn=None, active_only: bool = True) -> list:
    own = conn is None
    c = conn if conn is not None else get_connection()
    try:
        _ensure(c)
        sql = "SELECT * FROM staff_retention_holds"
        if active_only:
            sql += " WHERE released_at IS NULL"
        return [dict(r) for r in c.execute(sql + " ORDER BY placed_at DESC").fetchall()]
    finally:
        if own:
            c.close()


def list_holds(actor: Any, active_only: bool = True) -> list:
    access.require(actor, 'hr_admin', "Only an HR administrator can review retention holds")
    return holds(active_only=active_only)


def _held(conn) -> set:
    return {h['username'] for h in holds(conn)}


def place_hold(actor: Any, username: str, reason: str) -> int:
    access.require(actor, 'hr_admin', "Only an HR administrator can place a retention hold")
    if not (reason or '').strip():
        raise ValueError("Give a reason for the hold")
    with get_connection() as conn:
        _ensure(conn)
        key = access.staff_key(username, conn) or str(username).strip()
        cur = conn.execute("INSERT INTO staff_retention_holds (username, reason, placed_by, placed_at) "
                           "VALUES (?, ?, ?, ?)", (key, reason.strip(), access.username_of(actor),
                                                   _now()))
        access.audit(conn, actor, 'retention.hold', subject=key, entity='staff_retention_holds',
                     entity_id=cur.lastrowid, details={'reason': reason.strip()})
        return cur.lastrowid


def release_hold(actor: Any, hold_id: int) -> bool:
    access.require(actor, 'hr_admin', "Only an HR administrator can release a retention hold")
    with get_connection() as conn:
        _ensure(conn)
        row = conn.execute("SELECT username FROM staff_retention_holds WHERE hold_id = ? "
                           "AND released_at IS NULL", (int(hold_id),)).fetchone()
        if not row:
            return False
        conn.execute("UPDATE staff_retention_holds SET released_by = ?, released_at = ? "
                     "WHERE hold_id = ?", (access.username_of(actor), _now(), int(hold_id)))
        access.audit(conn, actor, 'retention.release', subject=row[0],
                     entity='staff_retention_holds', entity_id=hold_id)
    return True


# ── who has left ────────────────────────────────────────────────────────


def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                             (table,)).fetchone())


def _columns(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def leavers(conn, now: Optional[date] = None) -> dict:
    """username -> leaving date (ISO) for everyone who has left by ``now``:
    the last working day of their exit, or failing that their profile's
    contract end date — and no contract running past it."""
    now = now or date.today()
    found: dict = {}
    if _table_exists(conn, 'exit_interviews'):
        for user, day in conn.execute(
                "SELECT user_id, MAX(last_working_day) FROM exit_interviews "
                "WHERE last_working_day IS NOT NULL AND last_working_day != '' "
                "AND lower(coalesce(status, '')) != 'cancelled' GROUP BY user_id").fetchall():
            found[access.staff_key(user, conn) or user] = str(day)[:10]
    for user, day in conn.execute(
            "SELECT user_id, contract_end_date FROM staff_profiles "
            "WHERE contract_end_date IS NOT NULL AND contract_end_date != ''").fetchall():
        found.setdefault(user, str(day)[:10])
    running: dict = {}
    if _table_exists(conn, 'staff_contracts'):
        for user, end in conn.execute(
                "SELECT user_id, MAX(coalesce(nullif(end_date, ''), '9999-12-31')) "
                "FROM staff_contracts WHERE lower(coalesce(status, 'active')) NOT IN "
                "('terminated', 'cancelled', 'void', 'draft', 'rejected', 'ended', 'expired') "
                "GROUP BY user_id").fetchall():
            running[access.staff_key(user, conn) or user] = str(end)[:10]
    out = {}
    for user, day in found.items():
        if day > now.isoformat():
            continue
        if running.get(user, '') > day:
            continue
        out[user] = day
    return out


# ── targets ─────────────────────────────────────────────────────────────


def targets() -> dict:
    """:data:`TARGETS` plus every schema module's ``RETENTION_TARGETS``."""
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_ddl,
    )
    out = {k: list(v) for k, v in TARGETS.items()}
    for name in staff_hr_ddl.MODULES:
        try:
            module = importlib.import_module(f"{staff_hr_ddl._PKG}.{name}")
        except Exception:
            logger.warning("Retention: schema module %s not importable", name, exc_info=True)
            continue
        for extra in getattr(module, 'RETENTION_TARGETS', ()) or ():
            spec = dict(extra)
            out.setdefault(spec.pop('record_type'), []).append(spec)
    return out


def _where(spec: dict) -> str:
    sql = spec.get('where') or ''
    return sql.replace('{closed}', ", ".join(f"'{s}'" for s in CLOSED_CASE)) \
              .replace('{unsuccessful}', ", ".join(f"'{s}'" for s in UNSUCCESSFUL))


def _usable(conn, spec: dict) -> bool:
    if not _table_exists(conn, spec['table']):
        return False
    cols = _columns(conn, spec['table'])
    return spec['pk'] in cols and (spec.get('person') is None or spec['person'] in cols)


def _due_rows(conn, spec: dict, keep_months: int, now: date, held: set,
              left: dict, only: Optional[str] = None, ignore_period: bool = False) -> list:
    """[(pk, person)] due under ``spec``. ``only``: just that person's rows."""
    table, pk, person = spec['table'], spec['pk'], spec.get('person')
    person_sql = f'"{person}"' if person else 'NULL'
    clauses, params = [], []
    if spec.get('where'):
        clauses.append(f"({_where(spec)})")
    if only is not None:
        if not person:
            return []
        clauses.append(f'"{person}" = ?')
        params.append(only)
    due_before = cutoff(now, keep_months).isoformat()
    if spec['date'] != LEFT and not ignore_period:
        clauses.append(f"({spec['date']}) IS NOT NULL AND substr({spec['date']}, 1, 10) < ?")
        params.append(due_before)
    sql = f'SELECT "{pk}", {person_sql} FROM "{table}"'  # nosec B608
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    out = []
    for key, who in conn.execute(sql, params).fetchall():
        if who is not None and str(who) == ANON:
            continue
        if who is not None and str(who) in held:
            continue
        if spec['date'] == LEFT:
            day = left.get(str(who)) if who is not None else None
            if day is None or (not ignore_period and day >= due_before):
                continue
        out.append((key, who))
    return out


def _remove_files(paths: list) -> int:
    """Delete stored files that live under the university upload area."""
    from education_system import paths as app_paths
    root = getattr(app_paths, 'UNIVERSITY_UPLOAD_DIR', None)
    if not root:
        return 0
    from pathlib import Path
    base = Path(root).resolve()
    gone = 0
    for p in paths:
        if not p:
            continue
        try:
            path = Path(str(p)).resolve()
            if base in path.parents and path.is_file():
                path.unlink()
                gone += 1
        except OSError:
            logger.warning("Retention: could not remove %s", p, exc_info=True)
    return gone


def _apply(conn, spec: dict, action: str, keys: list) -> tuple:
    """Delete or anonymise ``keys`` of ``spec``'s table. (rows, files removed)."""
    if not keys:
        return 0, 0
    table, pk = spec['table'], spec['pk']
    marks = ", ".join("?" * len(keys))
    files = []
    file_cols = [c for c in spec.get('files', ()) if c in _columns(conn, table)]
    if file_cols:
        for row in conn.execute(f'SELECT {", ".join(file_cols)} FROM "{table}" '  # nosec B608
                                f'WHERE "{pk}" IN ({marks})', keys).fetchall():
            files.extend(row)
    if action == 'delete':
        for child, fk in spec.get('children', ()):
            if not _table_exists(conn, child):
                continue
            if child == 'staff_disciplinary_appeals':
                conn.execute(f"DELETE FROM staff_disciplinary_appeals WHERE action_id IN "  # nosec B608
                             f"(SELECT action_id FROM staff_disciplinary_actions WHERE record_id "
                             f"IN ({marks}))", keys)
                continue
            if fk in _columns(conn, child):
                conn.execute(f'DELETE FROM "{child}" WHERE "{fk}" IN ({marks})', keys)  # nosec B608
        n = conn.execute(f'DELETE FROM "{table}" WHERE "{pk}" IN ({marks})', keys).rowcount  # nosec B608
    else:
        cols = _columns(conn, table)
        sets = {c: v for c, v in (spec.get('anonymise') or {}).items() if c in cols}
        if not sets:
            return 0, 0
        assign = ", ".join(f'"{c}" = ?' for c in sets)
        n = conn.execute(f'UPDATE "{table}" SET {assign} WHERE "{pk}" IN ({marks})',  # nosec B608
                         (*sets.values(), *keys)).rowcount
    return n, _remove_files(files)


# ── leaver files ────────────────────────────────────────────────────────


def _person_tables(conn) -> list:
    """(table, column) for every person column of every Staff HR table."""
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_access_schema as schema,
    )
    out = []
    for table in schema.staff_tables():
        if table in ('staff_hr_audit', 'staff_equality_declarations', 'staff_retention_holds',
                     'staff_retention_runs') or not _table_exists(conn, table):
            continue
        for col in sorted(_columns(conn, table) & set(schema.PERSON_COLUMNS)):
            out.append((table, col))
    for table, col in (('staff_hr_roles', 'username'), ('exit_interviews', 'user_id'), ('exit_checklist', 'user_id'),
                       ('knowledge_transfer', 'departing_user_id'), ('leave_balances', 'user_id'),
                       ('appraisal_records', 'user_id'), ('appraisal_goals', 'user_id'),
                       ('training_enrollments', 'user_id'), ('certifications', 'user_id'),
                       ('time_entries', 'user_id'), ('timesheets', 'user_id'),
                       ('onboarding_assignments', 'user_id')):
        if (table, col) not in out and _table_exists(conn, table) and col in _columns(conn, table):
            out.append((table, col))
    return out


def _anonymise_leaver(conn, username: str, keep: dict) -> dict:
    """Pseudonymise ``username`` across Staff HR (rows in ``keep`` —
    {table: [pk]} still under a legal duty — keep the name)."""
    alias = f"former-{secrets.token_hex(4)}"
    changed = {}
    for table, col in _person_tables(conn):
        kept = keep.get(table) or []
        sql = f'UPDATE "{table}" SET "{col}" = ? WHERE "{col}" = ?'  # nosec B608
        params: list = [alias, username]
        if kept:
            pk = next((s['pk'] for specs in targets().values() for s in specs
                       if s['table'] == table), None)
            if pk:
                sql += f' AND "{pk}" NOT IN ({", ".join("?" * len(kept))})'
                params += list(kept)
        n = conn.execute(sql, params).rowcount
        if n:
            changed[f"{table}.{col}"] = n
    if _table_exists(conn, 'exit_interviews'):
        conn.execute("UPDATE exit_interviews SET reason_for_leaving = NULL, new_employer = NULL, "
                     "new_role = NULL, liked_most = NULL, liked_least = NULL, suggestions = NULL, "
                     "additional_comments = NULL, confidential_notes = NULL WHERE user_id = ?",
                     (alias,))
    pcols = _columns(conn, 'staff_profiles')
    clear = [c for c in PROFILE_PERSONAL if c in pcols]
    if clear:
        conn.execute(f"UPDATE staff_profiles SET {', '.join(f'{c} = NULL' for c in clear)} "  # nosec B608
                     "WHERE user_id = ?", (alias,))
    if _table_exists(conn, 'staff'):
        scols = _columns(conn, 'staff')
        sets = ["username = ?", "name = 'Former member of staff'"]
        sets += [f"{c} = NULL" for c in ('email', 'phone', 'last_login') if c in scols]
        if 'status' in scols:
            sets.append("status = 'left'")
        if 'password_hash' in scols:
            sets.append("password_hash = '!'")
        changed['staff'] = conn.execute(f"UPDATE staff SET {', '.join(sets)} "  # nosec B608
                                        "WHERE username = ?", (alias, username)).rowcount
    changed['staff_equality_declarations'] = equality.erase(conn, username)
    return {'alias': alias, 'changed': changed}


def _delete_leaver(conn, username: str, keep: dict) -> dict:
    """Delete the leaver's personnel file (rows in ``keep`` stay)."""
    removed = {}
    for table, col in _person_tables(conn):
        if col not in ('user_id', 'departing_user_id') or keep.get(table):
            continue
        if table in ('staff_contracts',):
            for child in ('contract_amendments', 'probation_reviews', 'contract_renewal_alerts'):
                if _table_exists(conn, child) and 'contract_id' in _columns(conn, child):
                    conn.execute(f'DELETE FROM "{child}" WHERE contract_id IN '  # nosec B608
                                 f'(SELECT contract_id FROM staff_contracts WHERE user_id = ?)',
                                 (username,))
        try:
            n = conn.execute(f'DELETE FROM "{table}" WHERE "{col}" = ?', (username,)).rowcount  # nosec B608
        except Exception as exc:
            # A row other tables still point at: anonymise it instead.
            logger.info("Retention: %s rows for a leaver kept (%s); pseudonymising", table, exc)
            continue
        if n:
            removed[table] = n
    if _table_exists(conn, 'staff'):
        removed['staff'] = conn.execute("DELETE FROM staff WHERE username = ?", (username,)).rowcount
    removed['staff_equality_declarations'] = equality.erase(conn, username)
    rest = _anonymise_leaver(conn, username, keep)
    return {'removed': removed, **rest}


# ── preview / run ───────────────────────────────────────────────────────


def _plan(conn, now: date, record_types: Optional[list] = None,
          include_disabled: bool = False) -> list:
    held, left = _held(conn), leavers(conn, now)
    specs = targets()
    plan = []
    for policy in policies(conn):
        rtype = policy['record_type']
        if record_types and rtype not in record_types:
            continue
        if not policy['enabled'] and not include_disabled:
            continue
        on = bool(policy['enabled'])
        if rtype == 'leaver_file':
            due_before = cutoff(now, policy['keep_months']).isoformat()
            people = sorted(u for u, day in left.items() if day < due_before and u not in held
                            and not u.startswith('former-'))
            plan.append({'record_type': rtype, 'label': policy['label'], 'action': policy['action'],
                         'enabled': on,
                         'keep_months': policy['keep_months'], 'table': 'staff_profiles (+ all HR)',
                         'spec': None, 'keys': people, 'people': len(people)})
            continue
        for spec in specs.get(rtype, []):
            if not _usable(conn, spec):
                continue
            rows = _due_rows(conn, spec, policy['keep_months'], now, held, left)
            plan.append({'record_type': rtype, 'label': policy['label'], 'action': policy['action'],
                         'enabled': on,
                         'keep_months': policy['keep_months'], 'table': spec['table'],
                         'spec': spec, 'keys': [k for k, _ in rows],
                         'people': len({w for _, w in rows if w is not None})})
    # Leavers' files last: the other policies act on named rows first.
    plan.sort(key=lambda p: p['record_type'] == 'leaver_file')
    return plan


def preview(actor: Any, now: Any = None) -> list:
    """What each policy would do now (HR administrators). No names.

    Policies that are switched off are included with ``enabled`` False, so
    their effect can be checked before an HR administrator switches them on;
    :func:`run` and the daily job apply only the enabled ones."""
    access.require(actor, 'hr_admin', "Only an HR administrator can review HR retention")
    with get_connection() as conn:
        _ensure(conn)
        plan = _plan(conn, _day(now), include_disabled=True)
    return [{k: v for k, v in p.items() if k not in ('spec', 'keys')} | {'due': len(p['keys'])}
            for p in plan]


def _run(conn, actor_name: str, now: date, record_types: Optional[list]) -> list:
    results = []
    for step in _plan(conn, now, record_types):
        rows = files = 0
        if step['record_type'] == 'leaver_file':
            for username in step['keys']:
                if step['action'] == 'delete':
                    _delete_leaver(conn, username, {})
                else:
                    _anonymise_leaver(conn, username, {})
                rows += 1
        else:
            rows, files = _apply(conn, step['spec'], step['action'], step['keys'])
        if rows or files:
            conn.execute("INSERT INTO staff_retention_runs (at, actor, record_type, table_name, "
                         "action, rows_affected, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (_now(), actor_name, step['record_type'], step['table'], step['action'],
                          rows, f"files removed: {files}" if files else None))
            access.audit(conn, actor_name, f"retention.{step['action']}",
                         entity=step['table'], entity_id=step['record_type'],
                         details={'rows': rows, 'files': files,
                                  'keep_months': step['keep_months']})
        results.append({'record_type': step['record_type'], 'table': step['table'],
                        'action': step['action'], 'rows': rows, 'files': files})
    return results


def run(actor: Any, now: Any = None, dry_run: bool = False,
        record_types: Optional[list] = None) -> list:
    """Apply every enabled policy (HR administrators). ``dry_run`` is
    :func:`preview`."""
    access.require(actor, 'hr_admin', "Only an HR administrator can run HR retention")
    if dry_run:
        return preview(actor, now)
    with get_connection() as conn:
        _ensure(conn)
        return _run(conn, access.username_of(actor), _day(now), record_types)


def daily_job() -> dict:
    """Scheduled entry point: apply every enabled policy as the system.

    Dotted name for the scheduler:
    ``education_system.systems.university.domains.staff.domain.staff_hr.retention.daily_job``
    """
    with get_connection() as conn:
        _ensure(conn)
        results = _run(conn, 'system:retention', date.today(), None)
    done = {f"{r['record_type']}:{r['table']}": r['rows'] for r in results if r['rows']}
    if done:
        logger.info("HR retention applied: %s", done)
    return {'ran': len(results), 'applied': done}


# ── one leaver, now ─────────────────────────────────────────────────────


def erase_leaver(actor: Any, username: str, now: Any = None,
                 include_statutory: bool = False) -> dict:
    """Erase a leaver's HR data now — a right-to-erasure request.

    Everything is removed or anonymised as its policy says, ignoring the
    keep period, except records under a legal duty (:data:`STATUTORY` —
    payroll, right to work) still inside their period, unless
    ``include_statutory``. Refuses for someone still employed or on hold.
    Returns what was done and what was kept (and until when).
    """
    access.require(actor, 'hr_admin', "Only an HR administrator can erase a leaver's HR data")
    today = _day(now)
    with get_connection() as conn:
        _ensure(conn)
        key = access.staff_key(username, conn) or str(username).strip()
        left = leavers(conn, today)
        if key not in left:
            raise ValueError(f"{key} has not left (no past leaving date and no running contract "
                             "ends before today)")
        if key in _held(conn):
            raise PermissionError(f"{key} is under a retention hold")
        pols = {p['record_type']: p for p in policies(conn)}
        done, kept, keep = [], [], {}
        for rtype, specs in targets().items():
            policy = pols.get(rtype)
            if not policy:
                continue
            for spec in specs:
                if not _usable(conn, spec) or not spec.get('person'):
                    continue
                rows = _due_rows(conn, spec, policy['keep_months'], today, set(), left,
                                 only=key, ignore_period=True)
                if not rows:
                    continue
                if rtype in STATUTORY and not include_statutory:
                    in_period = [k for k, _ in rows if k not in {
                        r for r, _ in _due_rows(conn, spec, policy['keep_months'], today, set(),
                                                left, only=key)}]
                    if in_period:
                        keep.setdefault(spec['table'], []).extend(in_period)
                        until = add_months(_day(left[key]), policy['keep_months']) \
                            if spec['date'] == LEFT else None
                        kept.append({'record_type': rtype, 'table': spec['table'],
                                     'rows': len(in_period),
                                     'until': until.isoformat() if until else
                                     f"{policy['keep_months']} months after each record"})
                        rows = [(k, w) for k, w in rows if k not in in_period]
                n, files = _apply(conn, spec, policy['action'], [k for k, _ in rows])
                if n:
                    done.append({'record_type': rtype, 'table': spec['table'],
                                 'action': policy['action'], 'rows': n, 'files': files})
        leaver_policy = pols.get('leaver_file') or {'action': 'anonymise'}
        if leaver_policy['action'] == 'delete' and not keep:
            file_result = _delete_leaver(conn, key, keep)
        else:
            file_result = _anonymise_leaver(conn, key, keep)
        conn.execute("INSERT INTO staff_retention_runs (at, actor, record_type, table_name, action, "
                     "rows_affected, details) VALUES (?, ?, 'erasure', 'all', ?, ?, ?)",
                     (_now(), access.username_of(actor), leaver_policy['action'],
                      sum(d['rows'] for d in done), f"alias {file_result['alias']}"))
        access.audit(conn, actor, 'retention.erase_leaver', subject=file_result['alias'],
                     entity='staff_profiles',
                     details={'done': done, 'kept': kept, 'alias': file_result['alias']})
    return {'alias': file_result['alias'], 'done': done, 'kept': kept,
            'file': file_result.get('changed', {}), 'removed': file_result.get('removed', {})}


def recent_runs(actor: Any, limit: int = 100) -> list:
    access.require(actor, 'hr_admin', "Only an HR administrator can review HR retention")
    with get_connection() as conn:
        _ensure(conn)
        return [dict(r) for r in conn.execute("SELECT * FROM staff_retention_runs "
                                              "ORDER BY run_id DESC LIMIT ?",
                                              (int(limit),)).fetchall()]


__all__ = ['ACTIONS', 'STATUTORY', 'TARGETS', 'add_months', 'cutoff', 'daily_job', 'erase_leaver',
           'holds', 'leavers', 'list_holds', 'place_hold', 'policies', 'preview', 'recent_runs', 'release_hold',
           'run', 'targets', 'update_policy']
