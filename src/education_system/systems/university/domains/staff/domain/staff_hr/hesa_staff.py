"""HESA staff return.

Builds the staff record for a reporting year (1 August - 31 July) on the
same footing as the student return in Governance's HESA export: a row in
``hesa_returns`` (``return_type = 'Staff'``) holding the XML, with each step
written to ``hesa_submission_log``. Codes can be overridden per institution
in ``hesa_field_mappings`` (``return_type = 'Staff'``, ``hesa_field`` = the
field, ``local_field`` = our value, ``transform_rule`` = the HESA code) — the
built-in codes follow the HESA coding frame current when this was written and
should be checked against the coding manual for the year being returned.

Who is returned: everyone with a ``staff_profiles`` record whose contract
(``staff_contracts``) overlaps the reporting year, and anyone in post with no
contract at all (reported as an error so HR can fix it).

:func:`validate` lists what is missing per person *without* any equality
answers, so HR officers can chase gaps; :func:`create_return` — which writes
individual equality codes into the XML, as the statutory return requires —
is for HR administrators only.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional
from xml.etree.ElementTree import Element, SubElement, tostring  # nosec B405

from education_system.systems.university.domains.staff.domain.staff_hr import access, equality
from education_system.systems.university.infrastructure.database.db import get_connection

RETURN_TYPE = 'Staff'

#: field -> {our value: HESA code}; unanswered -> NOT_AVAILABLE, "Prefer not to say" -> REFUSED.
CODES = {
    'SEXID': {'Female': '10', 'Male': '11', 'Other': '12'},
    'GENDERID': {'Yes': '01', 'No': '02'},
    'ETHNIC': {
        'Asian or Asian British - Bangladeshi': '100',
        'Asian or Asian British - Chinese': '101',
        'Asian or Asian British - Indian': '103',
        'Asian or Asian British - Pakistani': '104',
        'Any other Asian background': '119',
        'Black or Black British - African': '120',
        'Black or Black British - Caribbean': '121',
        'Any other Black background': '139',
        'Mixed - White and Asian': '140',
        'Mixed - White and Black African': '141',
        'Mixed - White and Black Caribbean': '142',
        'Any other Mixed or multiple ethnic background': '159',
        'White - English, Welsh, Scottish, Northern Irish or British': '160',
        'White - Irish': '161',
        'White - Gypsy or Irish Traveller': '163',
        'White - Roma': '166',
        'Any other White background': '179',
        'Arab': '180',
        'Any other ethnic group': '899',
    },
    'DISABLE': {
        'No known disability': '95',
        'Learning difference such as dyslexia or dyspraxia': '51',
        'Social or communication impairment such as autism': '53',
        'Long-standing illness or health condition': '54',
        'Mental health condition': '55',
        'Physical impairment': '56',
        'Deaf or serious hearing impairment': '57',
        'Blind or serious visual impairment': '58',
        'A disability, impairment or condition not listed': '96',
        'Two or more impairments or conditions': '96',
    },
    'RELBLF': {
        'No religion': '01', 'Buddhist': '02', 'Christian': '03', 'Hindu': '09',
        'Jewish': '10', 'Muslim': '11', 'Sikh': '12', 'Spiritual': '13',
        'Any other religion or belief': '80',
    },
    'SEXORT': {
        'Bisexual': '10', 'Gay man': '11', 'Gay woman or lesbian': '12',
        'Heterosexual or straight': '13', 'Other sexual orientation': '14',
    },
    #: Terms of employment: 1 open-ended/permanent, 2 fixed-term, 3 atypical.
    'TERMS': {'permanent': '1', 'open-ended': '1', 'full-time': '1', 'part-time': '1',
              'fixed_term': '2', 'fixed-term': '2', 'temporary': '2', 'contract': '2',
              'casual': '3', 'hourly': '3', 'zero_hours': '3', 'atypical': '3'},
}
REFUSED = {'SEXID': '96', 'GENDERID': '98', 'ETHNIC': '998', 'DISABLE': '98',
           'RELBLF': '98', 'SEXORT': '98'}
NOT_AVAILABLE = {'SEXID': '99', 'GENDERID': '99', 'ETHNIC': '997', 'DISABLE': '99',
                 'RELBLF': '99', 'SEXORT': '99'}
#: HESA field -> equality question.
EQUALITY_FIELDS = {'SEXID': 'sex', 'GENDERID': 'gender_identity', 'ETHNIC': 'ethnicity',
                   'DISABLE': 'disability', 'RELBLF': 'religion',
                   'SEXORT': 'sexual_orientation'}
#: Academic employment function: 1 teaching and research, 2 teaching only,
#: 3 research only, 9 neither (professional services).
_RESEARCH_ONLY = re.compile(r'\bresearch (fellow|associate|assistant|officer|scientist)\b|'
                            r'\bpostdoc', re.I)
_TEACHING_ONLY = re.compile(r'\b(teaching fellow|teaching associate|tutor|demonstrator)\b', re.I)
_ACADEMIC = re.compile(r'\b(lecturer|professor|reader|academic|fellow)\b', re.I)

PERSON_REQUIRED = ('STAFFID', 'OWNSTAF', 'BIRTHDTE', 'NATION')
CONTRACT_REQUIRED = ('OWNCONTID', 'TERMS', 'STARTCON', 'FTE', 'SALARY', 'ACEMPFUN', 'CCENTRE')
LABELS = {
    'STAFFID': 'staff (employee) number', 'OWNSTAF': 'username', 'BIRTHDTE': 'date of birth',
    'NATION': 'nationality', 'OWNCONTID': 'contract', 'TERMS': 'terms of employment',
    'STARTCON': 'contract start date', 'FTE': 'FTE (weekly hours)', 'SALARY': 'salary',
    'ACEMPFUN': 'academic employment function (job title)', 'CCENTRE': 'department',
}


def year_bounds(academic_year: Optional[str] = None, today: Optional[date] = None) -> tuple:
    """('2025/26', 2025-08-01, 2026-07-31). Default: the year ``today`` is in."""
    if academic_year:
        start = int(str(academic_year)[:4])
    else:
        today = today or date.today()
        start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}", date(start, 8, 1), date(start + 1, 7, 31)


def academic_function(job_title: Optional[str]) -> Optional[str]:
    title = (job_title or '').strip()
    if not title:
        return None
    if _RESEARCH_ONLY.search(title):
        return '3'
    if _TEACHING_ONLY.search(title):
        return '2'
    if _ACADEMIC.search(title):
        return '1'
    return '9'


def _overrides(conn) -> dict:
    try:
        rows = conn.execute("SELECT hesa_field, local_field, transform_rule FROM hesa_field_mappings "
                            "WHERE return_type = ? AND coalesce(is_active, 1) = 1",
                            (RETURN_TYPE,)).fetchall()
    except Exception:
        return {}
    out: dict = {}
    for field, local, code in rows:
        if field and local and code:
            out.setdefault(field, {})[local] = code
    return out


def _code(field: str, value: Optional[str], overrides: dict) -> Optional[str]:
    if field in EQUALITY_FIELDS:
        if not value:
            return NOT_AVAILABLE[field]
        if value == equality.PREFER_NOT:
            return REFUSED[field]
    if value is None:
        return None
    key = str(value).strip().lower() if field == 'TERMS' else value
    return overrides.get(field, {}).get(value) or CODES.get(field, {}).get(key)


def _profile_cols(conn) -> set:
    return {r[1] for r in conn.execute("PRAGMA table_info(staff_profiles)").fetchall()}


def _records(conn, academic_year: Optional[str]) -> tuple:
    """(year label, start, end, [person dict with 'contracts'])."""
    label, start, end = year_bounds(academic_year)
    pcols = _profile_cols(conn)
    dob = 'date_of_birth' if 'date_of_birth' in pcols else 'NULL'
    nat = 'nationality' if 'nationality' in pcols else 'NULL'
    profiles = {r['user_id']: dict(r) for r in conn.execute(
        f"SELECT user_id, employee_id, department, job_title, employment_type, hire_date, "  # nosec B608
        f"contract_end_date, {dob} AS date_of_birth, {nat} AS nationality FROM staff_profiles"
    ).fetchall()}
    ccols = {r[1] for r in conn.execute("PRAGMA table_info(staff_contracts)").fetchall()}
    fte = 'fte' if 'fte' in ccols else 'NULL'
    contracts: dict = {}
    for r in conn.execute(
            f"SELECT contract_id, user_id, contract_type, start_date, end_date, salary, "  # nosec B608
            f"pay_frequency, working_hours_per_week, {fte} AS fte, department, job_title, status "
            "FROM staff_contracts WHERE (start_date IS NULL OR start_date <= ?) "
            "AND (end_date IS NULL OR end_date = '' OR end_date >= ?) "
            "AND lower(coalesce(status, 'active')) NOT IN ('draft', 'cancelled', 'void', 'rejected') "
            "ORDER BY start_date", (end.isoformat(), start.isoformat())).fetchall():
        key = access.staff_key(r['user_id'], conn) or r['user_id']
        contracts.setdefault(key, []).append(dict(r))
    people = []
    for username, p in sorted(profiles.items()):
        in_post = (not p.get('contract_end_date') or str(p['contract_end_date']) >= start.isoformat()) \
            and (not p.get('hire_date') or str(p['hire_date']) <= end.isoformat())
        if username in contracts or in_post:
            people.append({**p, 'username': username, 'contracts': contracts.get(username, [])})
    return label, start, end, people


def _contract_fields(c: dict, profile: dict, standard: float) -> dict:
    hours = c.get('working_hours_per_week')
    if hours in (None, '', 0) and c.get('fte') not in (None, '', 0):
        fte = float(c['fte'])
    elif hours not in (None, '', 0):
        fte = float(hours) / standard
    else:
        fte = None
    salary = c.get('salary')
    if salary not in (None, ''):
        freq = str(c.get('pay_frequency') or '').lower()
        mult = {'monthly': 12, 'weekly': 52.143, 'fortnightly': 26.0715, 'four_weekly': 13}
        salary = round(float(salary) * mult.get(freq, 1))
    return {
        'OWNCONTID': c.get('contract_id'),
        'TERMS': c.get('contract_type') or profile.get('employment_type'),
        'STARTCON': (c.get('start_date') or '')[:10] or None,
        'ENDCON': (c.get('end_date') or '')[:10] or None,
        'FTE': None if fte is None else f"{min(fte, 1.0) * 100:.1f}",
        'SALARY': salary if salary not in (None, '') else None,
        'ACEMPFUN': academic_function(c.get('job_title') or profile.get('job_title')),
        'CCENTRE': c.get('department') or profile.get('department'),
        'JOBTITLE': c.get('job_title') or profile.get('job_title'),
    }


def _standard(conn) -> float:
    try:
        return float(equality.setting('standard_hours_per_week', 37.5, conn))
    except (TypeError, ValueError):
        return 37.5


def _validate(conn, people: list, standard: float) -> list:
    issues = []
    for p in people:
        values = {'STAFFID': p.get('employee_id'), 'OWNSTAF': p['username'],
                  'BIRTHDTE': p.get('date_of_birth'), 'NATION': p.get('nationality')}
        missing = [LABELS[f] for f in PERSON_REQUIRED if not values.get(f)]
        if not p['contracts']:
            missing.append('a contract in the reporting year')
        for c in p['contracts']:
            fields = _contract_fields(c, p, standard)
            gaps = [LABELS[f] for f in CONTRACT_REQUIRED if fields.get(f) in (None, '')]
            if fields.get('TERMS') and _code('TERMS', fields['TERMS'], {}) is None:
                gaps.append(f"terms of employment '{fields['TERMS']}' has no HESA code")
            missing += [f"contract {c['contract_id']}: {g}" for g in gaps]
        if missing:
            issues.append({'username': p['username'], 'employee_id': p.get('employee_id'),
                           'missing': missing})
    return issues


def validate(actor: Any, academic_year: Optional[str] = None) -> dict:
    """Who would be returned and what is missing for each (HR). Contains no
    equality answers — only whether a declaration exists."""
    access.require(actor, 'reports', "The HESA staff return is available to HR only")
    with get_connection() as conn:
        equality._ensure(conn)
        label, start, end, people = _records(conn, academic_year)
        declared = equality.declarations_for(conn, [p['username'] for p in people])
        issues = _validate(conn, people, _standard(conn))
        access.audit(conn, actor, 'hesa_staff.validate', entity='hesa_returns',
                     details={'year': label, 'people': len(people), 'issues': len(issues)})
    return {'academic_year': label, 'start': start.isoformat(), 'end': end.isoformat(),
            'people': len(people), 'contracts': sum(len(p['contracts']) for p in people),
            'without_declaration': sum(1 for p in people if p['username'] not in declared),
            'issues': issues, 'valid': not issues}


def build_xml(conn, academic_year: Optional[str] = None, ukprn: Optional[str] = None) -> tuple:
    """(XML text, validation issues) for the return."""
    label, start, end, people = _records(conn, academic_year)
    standard = _standard(conn)
    overrides = _overrides(conn)
    declared = equality.declarations_for(conn, [p['username'] for p in people])
    root = Element('StaffReturn', {'ReturnType': RETURN_TYPE, 'AcademicYear': label,
                                   'ReferencePeriodStart': start.isoformat(),
                                   'ReferencePeriodEnd': end.isoformat(),
                                   'Generated': datetime.now().isoformat(timespec='seconds')})
    SubElement(SubElement(root, 'Provider'), 'UKPRN').text = ukprn or ''
    for p in people:
        person = SubElement(root, 'Person')
        decl = declared.get(p['username']) or {}
        for field, value in (('STAFFID', p.get('employee_id')), ('OWNSTAF', p['username']),
                             ('BIRTHDTE', (p.get('date_of_birth') or '')[:10]),
                             ('NATION', overrides.get('NATION', {}).get(p.get('nationality') or '',
                                                                         p.get('nationality')))):
            SubElement(person, field).text = '' if value is None else str(value)
        for field, question in EQUALITY_FIELDS.items():
            SubElement(person, field).text = _code(field, decl.get(question), overrides) or ''
        for c in p['contracts']:
            fields = _contract_fields(c, p, standard)
            contract = SubElement(person, 'Contract')
            for field in ('OWNCONTID', 'TERMS', 'STARTCON', 'ENDCON', 'FTE', 'SALARY',
                          'ACEMPFUN', 'CCENTRE', 'JOBTITLE'):
                value = fields.get(field)
                if field == 'TERMS':
                    value = _code('TERMS', value, overrides)
                SubElement(contract, field).text = '' if value is None else str(value)
    xml = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml, _validate(conn, people, standard)


def create_return(actor: Any, academic_year: Optional[str] = None, notes: Optional[str] = None,
                  allow_errors: bool = False) -> dict:
    """Generate and store the year's staff return (HR administrators).

    Refuses while :func:`validate` finds missing data unless
    ``allow_errors`` (the return is then stored as ``draft`` with the
    issues in the submission log)."""
    access.require(actor, 'hr_admin', "Only an HR administrator can generate the HESA staff return "
                                      "(it contains individual equality data)")
    me = access.username_of(actor)
    with get_connection() as conn:
        equality._ensure(conn)
        ukprn = equality.setting('ukprn', '', conn)
        xml, issues = build_xml(conn, academic_year, ukprn)
        label = year_bounds(academic_year)[0]
        if issues and not allow_errors:
            raise ValueError(f"{len(issues)} staff record(s) are missing HESA data — fix them or "
                             "generate a draft with the errors listed")
        status = 'draft' if issues or not ukprn else 'validated'
        cur = conn.execute("INSERT INTO hesa_returns (academic_year, return_type, status, created_by, "
                           "notes, xml_data) VALUES (?, ?, ?, ?, ?, ?)",
                           (label, RETURN_TYPE, status, me, notes, xml))
        return_id = cur.lastrowid
        conn.execute("INSERT INTO hesa_submission_log (return_id, action, details, performed_by) "
                     "VALUES (?, 'generated', ?, ?)",
                     (return_id, f"{xml.count('<Person>')} people; {len(issues)} with missing data"
                                 + ("" if ukprn else "; UKPRN not set"), me))
        for issue in issues:
            conn.execute("INSERT INTO hesa_submission_log (return_id, action, details, performed_by) "
                         "VALUES (?, 'validation', ?, ?)",
                         (return_id, f"{issue['employee_id'] or issue['username']}: "
                                     + "; ".join(issue['missing']), me))
        access.audit(conn, actor, 'hesa_staff.generate', entity='hesa_returns',
                     entity_id=return_id, details={'year': label, 'issues': len(issues)})
    return {'return_id': return_id, 'academic_year': label, 'status': status,
            'issues': issues, 'ukprn_set': bool(ukprn)}


def list_returns(actor: Any) -> list:
    access.require(actor, 'reports', "The HESA staff return is available to HR only")
    with get_connection() as conn:
        rows = conn.execute("SELECT id, academic_year, status, created_by, created_at, submitted_at, "
                            "notes FROM hesa_returns WHERE return_type = ? ORDER BY id DESC",
                            (RETURN_TYPE,)).fetchall()
    return [dict(r) for r in rows]


def export_xml(actor: Any, return_id: int) -> str:
    """The stored XML of a staff return (HR administrators; audited)."""
    access.require(actor, 'hr_admin', "Only an HR administrator can export the HESA staff return")
    with get_connection() as conn:
        row = conn.execute("SELECT xml_data FROM hesa_returns WHERE id = ? AND return_type = ?",
                           (int(return_id), RETURN_TYPE)).fetchone()
        if not row:
            raise LookupError(f"No staff return {return_id}")
        conn.execute("INSERT INTO hesa_submission_log (return_id, action, details, performed_by) "
                     "VALUES (?, 'exported', NULL, ?)", (int(return_id), access.username_of(actor)))
        access.audit(conn, actor, 'hesa_staff.export', entity='hesa_returns', entity_id=return_id)
    return row[0] or ''


def set_personal_details(actor: Any, username: str, date_of_birth: Optional[str] = None,
                         nationality: Optional[str] = None) -> None:
    """Fill the two HESA fields the personnel record lacked (HR)."""
    access.require(actor, 'hr', "Only HR can change personal details for the HESA return")
    if date_of_birth:
        date.fromisoformat(date_of_birth)
    with get_connection() as conn:
        equality._ensure(conn)
        key = access.staff_key(username, conn)
        if not key:
            raise LookupError(f"No member of staff '{username}'")
        sets, params = [], []
        if date_of_birth:
            sets.append("date_of_birth = ?")
            params.append(date_of_birth)
        if nationality:
            sets.append("nationality = ?")
            params.append(nationality.strip())
        if not sets:
            return
        conn.execute(f"UPDATE staff_profiles SET {', '.join(sets)}, "  # nosec B608
                     "updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (*params, key))
        access.audit(conn, actor, 'hesa_staff.personal_details', subject=key,
                     entity='staff_profiles', details={'fields': [s.split()[0] for s in sets]})


__all__ = ['CODES', 'RETURN_TYPE', 'academic_function', 'build_xml', 'create_return',
           'export_xml', 'list_returns', 'set_personal_details', 'validate', 'year_bounds']
