"""Trip risk assessments: templates, items, submission and H&S sign-off.

An assessment starts as a copy of a template (or empty, 'custom'), is edited
by the trip's organisers while 'draft' or 'returned', submitted, then signed
off — or returned with notes — by a Health & Safety approver who is not the
assessor. Each item scores likelihood x severity (1-5 each) before and after
its controls; the assessment's ``overall_residual`` is banded from the worst
residual score (<= 6 low, <= 12 medium, otherwise high). A high residual can
only be signed off with notes that justify running the trip.

Field and research trips created through ``trip_bus`` also have an entry in
the university risk register (``reference_id = 'trip:<id>'``); a new
assessment records that entry's id in ``review_notes`` so the two are
linked.

Same contract as ``trips``: ``auth`` first, PermissionError / ValueError,
own short transaction unless ``conn=`` (then pass ``pending=``).
"""
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import logging

logger = logging.getLogger(__name__)

SIGN_OFF_PERMISSION = 'approve_trips_hs'
EDITABLE_STATUSES = ('draft', 'returned')
IN_PROGRESS_STATUSES = ('draft', 'submitted', 'returned')
ITEM_FIELDS = ('hazard', 'who_at_risk', 'controls', 'likelihood', 'severity',
               'residual_likelihood', 'residual_severity', 'owner')


def _item(hazard, who_at_risk, controls, likelihood, severity, residual_likelihood,
          residual_severity):
    return {'hazard': hazard, 'who_at_risk': who_at_risk, 'controls': controls,
            'likelihood': likelihood, 'severity': severity,
            'residual_likelihood': residual_likelihood, 'residual_severity': residual_severity}


# Starting points only: the assessor adapts every item to the actual trip.
TEMPLATES = {
    'general': [
        _item("Road travel to and from the venue (coach / minibus collision, breakdown)",
              "Students, staff, driver",
              "Licensed operator from the university's approved list; seatbelts worn and "
              "checked at departure; driver hours within the legal limits; minibus drivers "
              "hold the university's driving authorisation; roll call before every departure.",
              2, 5, 1, 5),
        _item("Participant separated from the group or missing",
              "Students",
              "Group briefing with meeting points and times; buddy system; leaders hold the "
              "participant list with mobile numbers; roll call at every move; missing-person "
              "procedure in the leader's pack.",
              3, 3, 2, 3),
        _item("Medical emergency, allergy or pre-existing condition",
              "Students, staff",
              "Medical and dietary information collected (with consent) before departure; a "
              "qualified first aider on the trip with a first-aid kit; participants carry "
              "their own medication; nearest A&E identified; 24-hour university contact.",
              2, 4, 1, 4),
        _item("Slips, trips and falls on site",
              "Students, staff",
              "Suitable footwear specified in the joining instructions; venue's own risk "
              "assessment obtained; leaders brief on site hazards on arrival.",
              3, 2, 2, 2),
        _item("Adverse weather (heat, cold, storms)",
              "Students, staff",
              "Met Office forecast checked the day before and on the morning; kit list "
              "includes waterproofs / sun protection and water; leader may change or cancel "
              "activities.",
              3, 3, 2, 2),
        _item("Behaviour, alcohol or substance misuse",
              "Students, members of the public",
              "Code of conduct accepted at registration; alcohol policy stated in the "
              "briefing; leaders may send a participant home under the disciplinary procedure.",
              2, 3, 1, 3),
        _item("Lone working or a leader incapacitated",
              "Staff, students",
              "At least two staff on residential trips; deputy leader named; 24-hour "
              "emergency contact holds the itinerary and participant list.",
              2, 4, 1, 3),
    ],
    'fieldwork': [
        _item("Uneven, steep or unstable terrain",
              "Students, staff",
              "Route recce or recent site report; boots with ankle support required; leaders "
              "set boundaries and keep groups away from cliff edges and quarry faces.",
              3, 4, 2, 3),
        _item("Tides, rivers and flooding at coastal or riverside sites",
              "Students, staff",
              "Tide times checked and work planned around them; no entry to water without a "
              "separate water assessment; retreat route agreed before starting.",
              2, 5, 1, 4),
        _item("Exposure: hypothermia, heat exhaustion, sunburn",
              "Students, staff",
              "Weather checked; kit list (layers, waterproofs, hat, sun cream, water) enforced "
              "at departure; regular breaks; group shelter carried in upland areas.",
              3, 3, 2, 2),
        _item("Animals, ticks and plants (Lyme disease, livestock, giant hogweed)",
              "Students, staff",
              "Long trousers tucked into socks; tick checks and removal tool; avoid livestock "
              "with young; hand washing before eating; briefing on harmful plants.",
              3, 3, 2, 2),
        _item("Use of sampling equipment and tools (augers, hammers, chemicals)",
              "Students",
              "Demonstration before use; eye protection for rock hammering; COSHH data sheets "
              "carried for any chemicals; equipment checked before issue.",
              2, 3, 1, 2),
        _item("Working away from the leader in small groups",
              "Students",
              "Groups of at least three; agreed check-in times by phone or radio; work area "
              "boundaries; leader knows each group's location.",
              3, 4, 2, 3),
        _item("Remote location delaying emergency response",
              "Students, staff",
              "First aider and kit with each party; mobile coverage checked (or satellite "
              "messenger carried); grid references of access points known; mountain rescue via 999.",
              2, 5, 1, 4),
        _item("Landowner permission and public access",
              "Students, landowner, public",
              "Written permission obtained; Countryside Code briefed; gates left as found; "
              "no work on private land without permission.",
              2, 2, 1, 2),
    ],
    'overseas': [
        _item("Destination security, political unrest or terrorism",
              "Students, staff",
              "FCDO travel advice checked and recorded before approval and again before "
              "departure; itinerary avoids areas advised against; leaders registered for FCDO "
              "alerts; plan to leave the country if advice changes.",
              2, 5, 1, 4),
        _item("Illness, disease and access to healthcare abroad",
              "Students, staff",
              "Vaccinations and malaria advice from a travel clinic (NaTHNaC / Fit for Travel); "
              "university travel insurance with medical cover and repatriation; GHIC carried "
              "where it applies; local hospitals identified.",
              2, 4, 1, 4),
        _item("Lost or stolen passport, visa refused or entry denied",
              "Students",
              "Passport valid for at least six months after return checked for every "
              "participant; visa status confirmed; copies of documents held by the leader; "
              "embassy contact details in the leader's pack.",
              3, 3, 1, 3),
        _item("Road safety and local transport",
              "Students, staff",
              "Reputable, insured transport booked in advance; no motorbike taxis; seatbelts; "
              "no travel after dark on rural roads where advised.",
              3, 5, 2, 4),
        _item("Crime, theft and personal safety",
              "Students, staff",
              "Briefing on local risks and scams; valuables kept to a minimum; walk in groups "
              "at night; accommodation with secure rooms.",
              3, 3, 2, 2),
        _item("Cultural, legal and LGBT+ safety differences",
              "Students, staff",
              "Pre-departure briefing on local laws, dress, alcohol and drug laws; FCDO local "
              "laws page shared; individual concerns discussed confidentially.",
              2, 4, 1, 3),
        _item("Food and water hygiene",
              "Students, staff",
              "Bottled or treated water; advice on street food; rehydration salts in the "
              "first-aid kit; dietary and allergy needs communicated in the local language.",
              3, 3, 2, 2),
        _item("Emergency communication across time zones",
              "Students, staff",
              "24-hour university emergency contact; leaders carry roaming-enabled phones; "
              "itinerary and participant list held by the department; insurer's assistance line.",
              2, 4, 1, 3),
    ],
    'water': [
        _item("Drowning or cold-water shock",
              "Students, staff",
              "Activity run by an AALA-licensed or NGB-accredited provider; buoyancy aids "
              "worn at all times on or near water; swimming ability declared; ratios set by "
              "the provider.",
              2, 5, 1, 5),
        _item("Fast-flowing water, currents or tides",
              "Students",
              "Conditions assessed by the instructor on the day; entry and exit points agreed; "
              "throw lines carried; activity cancelled in high water.",
              2, 5, 1, 4),
        _item("Hypothermia after immersion",
              "Students, staff",
              "Wetsuits / dry suits provided; spare warm clothing and hot drinks; session "
              "length limited in cold water.",
              3, 3, 2, 2),
        _item("Waterborne infection (Weil's disease, gastroenteritis)",
              "Students, staff",
              "Cuts covered with waterproof dressings; hands washed before eating; no "
              "swallowing water; participants told to mention the activity to a GP if unwell.",
              2, 3, 1, 3),
        _item("Collision with craft, rocks or equipment",
              "Students",
              "Helmets where the provider requires; briefing on capsize and spacing; "
              "instructor safety cover on the water.",
              2, 4, 1, 3),
    ],
    'height': [
        _item("Fall from height (climbing walls, crags, high ropes)",
              "Students, staff",
              "Provider holds AALA licence or instructors hold the relevant Mountain Training "
              "award; harnesses, helmets and ropes inspected; buddy checks before every climb.",
              2, 5, 1, 5),
        _item("Falling objects or rock fall",
              "Students, staff",
              "Helmets worn at the base of crags; no one standing below climbers; loose rock "
              "areas avoided.",
              2, 4, 1, 3),
        _item("Equipment failure",
              "Students",
              "Equipment from the provider's inspected stock with records; retired at end of "
              "life; personal kit not used unless inspected.",
              1, 5, 1, 4),
        _item("Belaying or rope-handling errors",
              "Students",
              "Instruction and supervised practice before belaying; back-up belayer for "
              "novices; instructor checks every set-up.",
              2, 5, 1, 4),
        _item("Fear, anxiety or panic at height",
              "Students",
              "Participation voluntary; challenge by choice; instructor can lower or rescue; "
              "prior conditions declared.",
              3, 2, 2, 2),
        _item("Weather on outdoor crags (wet rock, wind, lightning)",
              "Students, staff",
              "Forecast checked; climbing stops in rain or lightning; indoor alternative booked.",
              2, 4, 1, 3),
    ],
}
TEMPLATE_NAMES = tuple(TEMPLATES) + ('custom',)


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def band(score):
    """'low' (<= 6), 'medium' (<= 12) or 'high' for a likelihood x severity score."""
    if score <= 6:
        return 'low'
    if score <= 12:
        return 'medium'
    return 'high'


def overall_residual(items):
    """The band of the worst residual score among ``items`` (``None`` when empty)."""
    scores = [int(i.get('residual_likelihood') or i.get('likelihood') or 0)
              * int(i.get('residual_severity') or i.get('severity') or 0) for i in items]
    return band(max(scores)) if scores else None


def _score(name, value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: enter a whole number from 1 to 5") from None
    if not 1 <= value <= 5:
        raise ValueError(f"{name}: enter a whole number from 1 to 5")
    return value


def _clean_item(fields, current=None):
    """Validate item fields; residual defaults to the initial score and may not exceed it."""
    unknown = set(fields) - set(ITEM_FIELDS)
    if unknown:
        raise ValueError(f"unknown risk item field(s): {', '.join(sorted(unknown))}")
    merged = dict(current or {})
    for name, value in fields.items():
        merged[name] = value.strip() if isinstance(value, str) else value
    if not merged.get('hazard'):
        raise ValueError("describe the hazard")
    for name in ('likelihood', 'severity'):
        merged[name] = _score(name, merged.get(name))
    for name, base in (('residual_likelihood', 'likelihood'), ('residual_severity', 'severity')):
        value = merged.get(name)
        merged[name] = merged[base] if value in (None, '') else _score(name, value)
    if merged['residual_likelihood'] * merged['residual_severity'] > merged['likelihood'] * merged['severity']:
        raise ValueError("the residual risk cannot be higher than the risk before controls")
    return {k: merged.get(k) for k in ITEM_FIELDS}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def _rows(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def get_assessment(assessment_id, conn=None):
    """The assessment with its ``items`` (and each item's scores), or ``None``."""
    with _db().read_connection(conn) as c:
        rows = _rows(c.execute("SELECT * FROM trip_risk_assessments WHERE id = ?", (assessment_id,)))
        if not rows:
            return None
        assessment = rows[0]
        items = _rows(c.execute("SELECT * FROM trip_risk_items WHERE assessment_id = ? ORDER BY id",
                                (assessment_id,)))
    for item in items:
        item['score'] = item['likelihood'] * item['severity']
        item['residual_score'] = (item['residual_likelihood'] or item['likelihood']) * \
            (item['residual_severity'] or item['severity'])
        item['residual_band'] = band(item['residual_score'])
    assessment['items'] = items
    assessment['computed_residual'] = overall_residual(items)
    return assessment


def current(trip_id, conn=None):
    """The trip's latest risk assessment (with items), or ``None``."""
    with _db().read_connection(conn) as c:
        row = c.execute("SELECT id FROM trip_risk_assessments WHERE trip_id = ? "
                        "ORDER BY id DESC LIMIT 1", (trip_id,)).fetchone()
        return get_assessment(row[0], conn=c) if row else None


def list_assessments(trip_id, conn=None):
    """Every assessment of the trip, newest first (without items)."""
    with _db().read_connection(conn) as c:
        return _rows(c.execute("SELECT * FROM trip_risk_assessments WHERE trip_id = ? "
                               "ORDER BY id DESC", (trip_id,)))


def _register_entry(trip_id):
    """The id of the trip's risk-register entry (raised by ``trip_bus``), or ``None``."""
    try:
        from education_system.systems.university.services.bus import risk_bus
        rows = risk_bus.list_risks_for(f"trip:{trip_id}")
    except Exception:
        logger.debug("risk register lookup for trip %s failed", trip_id, exc_info=True)
        return None
    for row in rows or ():
        rid = row.get('id') or row.get('risk_id')
        if rid:
            return rid
    return None


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def _load(c, auth, assessment_id, who, editable=True):
    trips = _trips()
    assessment = get_assessment(assessment_id, conn=c)
    if not assessment:
        raise ValueError("risk assessment not found")
    trip = trips.get_trip(assessment['trip_id'], conn=c)
    if not trips.can_manage_trip(auth, trip, conn=c, who=who):
        raise PermissionError("only the trip's organisers can edit its risk assessment")
    if editable and assessment['status'] not in EDITABLE_STATUSES:
        raise ValueError(f"the assessment is {assessment['status']}; only a draft or returned "
                         "assessment can be changed")
    return assessment, trip


def create_assessment(auth, trip_id, template='general', *, conn=None, pending=None):
    """Start a risk assessment for the trip from ``template`` (copied items).

    ``template`` is one of :data:`TEMPLATE_NAMES` ('custom' starts empty).
    Refused while another assessment of the trip is still in progress (a
    signed-off one may be superseded). Returns the assessment dict.
    """
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')
    if template not in TEMPLATE_NAMES:
        raise ValueError(f"template must be one of {', '.join(TEMPLATE_NAMES)}")
    register_id = None if conn is not None else _register_entry(trip_id)

    def work(c, p):
        trip = trips._load_for_change(c, auth, trip_id, who)
        if trip['status'] in ('cancelled', 'archived', 'completed'):
            raise ValueError(f"the trip is {trip['status']}")
        marks = ", ".join('?' * len(IN_PROGRESS_STATUSES))
        busy = c.execute(f"SELECT id, status FROM trip_risk_assessments WHERE trip_id = ? "
                         f"AND status IN ({marks})", (trip_id, *IN_PROGRESS_STATUSES)).fetchone()
        if busy:
            raise ValueError(f"risk assessment #{busy[0]} is already {busy[1]}; finish it first")
        now = trips._now()
        notes = f"Risk register entry #{register_id} (trip:{trip_id})" if register_id else None
        assessment_id = c.execute(
            "INSERT INTO trip_risk_assessments (trip_id, template, status, assessor, created_at, "
            "review_notes, trip_version) VALUES (?, ?, 'draft', ?, ?, ?, ?)",
            (trip_id, template, who['username'], now, notes, trip.get('version'))).lastrowid
        for item in TEMPLATES.get(template, ()):
            cols = list(item)
            c.execute(f"INSERT INTO trip_risk_items (assessment_id, {', '.join(cols)}) "
                      f"VALUES (?, {', '.join('?' * len(cols))})",
                      (assessment_id, *[item[k] for k in cols]))
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='risk_assessment_created', field='risk_assessment',
                             new_value=f"#{assessment_id} {template}")
        return get_assessment(assessment_id, conn=c)
    return trips._in_transaction(conn, pending, work)


def add_item(auth, assessment_id, hazard, who_at_risk="", controls="", likelihood=3,
             severity=3, residual_likelihood=None, residual_severity=None, owner=None,
             *, conn=None, pending=None):
    """Add a hazard to a draft / returned assessment. Returns the item id."""
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')
    item = _clean_item({'hazard': hazard, 'who_at_risk': who_at_risk, 'controls': controls,
                        'likelihood': likelihood, 'severity': severity,
                        'residual_likelihood': residual_likelihood,
                        'residual_severity': residual_severity, 'owner': owner})

    def work(c, p):
        _load(c, auth, assessment_id, who)
        cols = list(item)
        return c.execute(f"INSERT INTO trip_risk_items (assessment_id, {', '.join(cols)}) "
                         f"VALUES (?, {', '.join('?' * len(cols))})",
                         (assessment_id, *[item[k] for k in cols])).lastrowid
    return trips._in_transaction(conn, pending, work)


def _item_assessment(c, item_id):
    cur = c.execute("SELECT * FROM trip_risk_items WHERE id = ?", (item_id,))
    rows = _rows(cur)
    if not rows:
        raise ValueError("risk item not found")
    return rows[0]


def update_item(auth, item_id, *, conn=None, pending=None, **fields):
    """Change an item's fields (:data:`ITEM_FIELDS`). Returns the item dict."""
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')

    def work(c, p):
        current_item = _item_assessment(c, item_id)
        _load(c, auth, current_item['assessment_id'], who)
        cleaned = _clean_item(fields, current=current_item)
        c.execute(f"UPDATE trip_risk_items SET {', '.join(k + ' = ?' for k in cleaned)} WHERE id = ?",
                  (*cleaned.values(), item_id))
        return _item_assessment(c, item_id)
    return trips._in_transaction(conn, pending, work)


def remove_item(auth, item_id, *, conn=None, pending=None):
    """Delete an item from a draft / returned assessment."""
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')

    def work(c, p):
        current_item = _item_assessment(c, item_id)
        _load(c, auth, current_item['assessment_id'], who)
        c.execute("DELETE FROM trip_risk_items WHERE id = ?", (item_id,))
        return True
    return trips._in_transaction(conn, pending, work)


def submit(auth, assessment_id, *, conn=None, pending=None):
    """Submit a draft / returned assessment for Health & Safety sign-off.

    Needs at least one item and controls on every item. Sets
    ``overall_residual``; the H&S coordinators are e-mailed after the commit.
    Returns the assessment dict.
    """
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')

    def work(c, p):
        assessment, trip = _load(c, auth, assessment_id, who)
        items = assessment['items']
        if not items:
            raise ValueError("add at least one hazard before submitting")
        missing = [i['hazard'] for i in items if not (i.get('controls') or '').strip()]
        if missing:
            raise ValueError("these hazards have no controls: " + "; ".join(missing))
        residual = overall_residual(items)
        c.execute("UPDATE trip_risk_assessments SET status = 'submitted', submitted_at = ?, "
                  "overall_residual = ?, trip_version = ? WHERE id = ?",
                  (trips._now(), residual, trip.get('version'), assessment_id))
        trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                             action='risk_assessment_submitted', field='risk_assessment',
                             new_value=f"#{assessment_id} residual {residual}")
        p.append(lambda: _notify_hs(trip, assessment_id, residual))
        return get_assessment(assessment_id, conn=c)
    return trips._in_transaction(conn, pending, work)


def _notify_hs(trip, assessment_id, residual):
    """After commit: tell the H&S coordinators an assessment is waiting."""
    from education_system.systems.university.services.bus import safety_bus
    pending = []
    _trips().queue_email(
        pending, safety_bus.coordinator_emails(),
        f"Trip risk assessment to sign off: {trip['trip_name']}",
        f"Risk assessment #{assessment_id} for '{trip['trip_name']}' ({trip['destination']}, "
        f"{trip['start_date']} to {trip['end_date']}) has been submitted. Overall residual "
        f"risk: {residual}. Sign it off or return it in Trip Management.")
    _db().run_after_commit(pending)


def sign_off(auth, assessment_id, decision, notes="", *, conn=None, pending=None):
    """Sign off ('signed_off') or return ('returned') a submitted assessment.

    Needs ``approve_trips_hs``; the assessor cannot sign off their own
    assessment. Returning needs notes, and so does signing off a 'high'
    residual (the justification for running the trip). The assessor is
    e-mailed after the commit. Returns the assessment dict.
    """
    trips = _trips()
    who = trips._require(auth, SIGN_OFF_PERMISSION)
    if decision not in ('signed_off', 'returned'):
        raise ValueError("decision must be 'signed_off' or 'returned'")
    notes = (notes or '').strip()

    def work(c, p):
        assessment = get_assessment(assessment_id, conn=c)
        if not assessment:
            raise ValueError("risk assessment not found")
        if assessment['status'] != 'submitted':
            raise ValueError(f"the assessment is {assessment['status']}, not submitted")
        if (assessment['assessor'] or '').lower() == (who['username'] or '').lower():
            raise PermissionError("the assessor cannot sign off their own risk assessment")
        residual = assessment['computed_residual']
        if decision == 'returned' and not notes:
            raise ValueError("say what needs changing (notes)")
        if decision == 'signed_off' and residual == 'high' and not notes:
            raise ValueError("the residual risk is high: record why the trip can still go ahead (notes)")
        now = trips._now()
        review = "\n".join(x for x in (assessment.get('review_notes'),
                                      f"[{now[:10]} {who['username']}: {decision}] {notes}".rstrip())
                           if x)
        if decision == 'signed_off':
            c.execute("UPDATE trip_risk_assessments SET status = 'signed_off', signed_off_by = ?, "
                      "signed_off_at = ?, overall_residual = ?, review_notes = ? WHERE id = ?",
                      (who['username'], now, residual, review, assessment_id))
        else:
            c.execute("UPDATE trip_risk_assessments SET status = 'returned', review_notes = ? "
                      "WHERE id = ?", (review, assessment_id))
        trip = trips.get_trip(assessment['trip_id'], conn=c)
        trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                             action=f'risk_assessment_{decision}', field='risk_assessment',
                             new_value=f"#{assessment_id} {notes}".strip())
        trips._publish_after(p, "trip.risk_assessment.decided", trip_id=trip['id'],
                             assessment_id=assessment_id, decision=decision, residual=residual)
        trips.queue_email(
            p, [trips.user_email(c, assessment['assessor'])],
            f"Risk assessment {decision.replace('_', ' ')}: {trip['trip_name']}",
            f"Risk assessment #{assessment_id} for '{trip['trip_name']}' was "
            f"{decision.replace('_', ' ')} by {who['username']}."
            + (f"\n\nNotes: {notes}" if notes else ""))
        return get_assessment(assessment_id, conn=c)
    return trips._in_transaction(conn, pending, work)


__all__ = ['TEMPLATES', 'TEMPLATE_NAMES', 'band', 'overall_residual', 'get_assessment', 'current',
           'list_assessments', 'create_assessment', 'add_item', 'update_item', 'remove_item',
           'submit', 'sign_off']
