"""Trip approval: which stages a trip needs, who decides them, and the gates.

A trip is proposed, submitted for approval (one ``trip_approvals`` row per
required stage, decision 'pending'), decided stage by stage, and moves to
'approved' when the last stage is approved. Opening it for registration
also needs a signed-off risk assessment, the staffing checks and — for an
overseas trip — the overseas checks; :func:`gate_problems` lists everything
still missing and ``trips.set_trip_status`` refuses with that list.

Rows are never overwritten by a new round: a resubmission or a reset after a
material edit (dates, destination, cost, overseas details) inserts new
'pending' rows, so the table is the approval history. The latest row per
stage is the current decision.

Same contract as ``trips``: ``auth`` first, PermissionError / ValueError,
own short transaction unless ``conn=`` (then pass ``pending=``), e-mails
and events after the commit.
"""
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import get_text, logging

logger = logging.getLogger(__name__)

STAGES = ('department', 'health_safety', 'finance', 'international')
DECISIONS = ('approved', 'rejected', 'returned')

# Permission that decides each stage (seeded in permissions.TRIP_APPROVAL_PERMISSIONS).
STAGE_PERMISSIONS = {
    'department': 'approve_trips_department',
    'health_safety': 'approve_trips_hs',
    'finance': 'approve_trips_finance',
    'international': 'approve_trips_international',
}
STAGE_LABELS = {
    'department': 'Department',
    'health_safety': 'Health & Safety',
    'finance': 'Finance',
    'international': 'International',
}

# A change to any of these after submission means the approvals given no
# longer describe the trip: they are reset to pending.
MATERIAL_FIELDS = ('start_date', 'end_date', 'destination', 'country', 'cost', 'budget',
                   'is_overseas', 'trip_type', 'fcdo_advice_level')

# Statuses a trip can be submitted from.
_SUBMITTABLE = ('proposed', 'planning')


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


# Re-exported so callers find the life-cycle API in one place.
def set_status(auth, trip_id, new_status, reason="", *, conn=None, pending=None):
    """``trips.set_trip_status`` (the state machine and its gates)."""
    return _trips().set_trip_status(auth, trip_id, new_status, reason, conn=conn, pending=pending)


def archive_trip(auth, trip_id, reason="", *, conn=None, pending=None):
    """``trips.archive_trip`` — archiving replaces deleting a trip."""
    return _trips().archive_trip(auth, trip_id, reason=reason, conn=conn, pending=pending)


def record_history(conn, trip_id, **fields):
    """``trips.record_history`` on the caller's transaction."""
    return _trips().record_history(conn, trip_id, **fields)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def required_stages(trip):
    """The approval stages ``trip`` (a dict) needs, in decision order.

    Department and Health & Safety always; Finance when the trip charges
    (cost > 0) or has a budget; International when it is overseas or the
    FCDO advises against all but essential travel.
    """
    stages = ['department', 'health_safety']
    if float(trip.get('cost') or 0) > 0 or trip.get('budget') not in (None, '', 0, 0.0):
        stages.append('finance')
    if int(trip.get('is_overseas') or 0) or trip.get('fcdo_advice_level') == 'all_but_essential':
        stages.append('international')
    return stages


def _latest_rows(conn, trip_id):
    """``{stage: row dict}`` — the latest approval row per stage."""
    cur = conn.execute(
        "SELECT * FROM trip_approvals WHERE trip_id = ? ORDER BY id", (trip_id,))
    names = [d[0] for d in cur.description]
    latest = {}
    for row in cur.fetchall():
        d = dict(zip(names, row))
        latest[d['stage']] = d
    return latest


def approval_state(trip_id, conn=None):
    """Where the trip's approval stands.

    Returns ``{'trip_id', 'required', 'stages': {stage: {decision,
    decided_by, decided_at, comments, trip_version}}, 'submitted',
    'complete', 'outstanding': [stage...], 'rejected': [stage...]}``.
    A required stage with no row yet is 'not_submitted'.
    """
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        latest = _latest_rows(c, trip_id)
    required = required_stages(trip)
    stages = {}
    for stage in required:
        row = latest.get(stage)
        stages[stage] = {
            'decision': row['decision'] if row else 'not_submitted',
            'decided_by': row and row['decided_by'],
            'decided_at': row and row['decided_at'],
            'comments': row and row['comments'],
            'trip_version': row and row['trip_version'],
        }
    outstanding = [s for s in required if stages[s]['decision'] != 'approved']
    return {
        'trip_id': trip_id,
        'required': required,
        'stages': stages,
        'submitted': any(s['decision'] != 'not_submitted' for s in stages.values()),
        'complete': not outstanding,
        'outstanding': outstanding,
        'rejected': [s for s in required if stages[s]['decision'] in ('rejected', 'returned')],
    }


def gate_problems(trip_id, target='open', conn=None, record=False):
    """Everything stopping the trip moving to ``target`` ('approved' or 'open').

    'approved' needs every required stage approved. 'open' also needs the
    current risk assessment signed off, :func:`safeguarding.staffing_check`
    clear and, for an overseas trip, :func:`overseas.overseas_problems`
    clear. With ``record`` (and ``conn`` inside a write transaction) the
    staff DBS / first-aid findings are mirrored onto ``trip_staff``.
    Returns a list of plain-language problems (empty = go).
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        overseas, risk, safeguarding,
    )
    problems = []
    with _db().read_connection(conn) as c:
        trip = _trips().get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        state = approval_state(trip_id, conn=c)
        for stage in state['outstanding']:
            decision = state['stages'][stage]['decision']
            label = STAGE_LABELS[stage]
            if decision == 'not_submitted':
                problems.append(f"{label} approval has not been requested (submit the trip for approval)")
            elif decision == 'pending':
                problems.append(f"{label} approval is still pending")
            else:
                comments = state['stages'][stage]['comments']
                problems.append(f"{label} approval was {decision}"
                                + (f": {comments}" if comments else "")
                                + " — resubmit once addressed")
        if target != 'open':
            return problems
        assessment = risk.current(trip_id, conn=c)
        if not assessment:
            problems.append("there is no risk assessment")
        elif assessment['status'] != 'signed_off':
            problems.append(f"the risk assessment (#{assessment['id']}) is {assessment['status']}, "
                            "not signed off")
        problems.extend(safeguarding.staffing_check(trip_id, conn=c, record=record))
        if int(trip.get('is_overseas') or 0):
            problems.extend(overseas.overseas_problems(trip_id, conn=c))
    return problems


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def _insert_pending(conn, trip, stages, now):
    for stage in stages:
        conn.execute(
            "INSERT INTO trip_approvals (trip_id, stage, decision, trip_version, created_at) "
            "VALUES (?, ?, 'pending', ?, ?)",
            (trip['id'], stage, int(trip.get('version') or 1), now))


def _approver_emails(conn, stages):
    """Addresses of the users whose role holds the permission for any of ``stages``."""
    perms = [STAGE_PERMISSIONS[s] for s in stages]
    if not perms:
        return []
    marks = ", ".join('?' * len(perms))
    try:
        rows = conn.execute(
            "SELECT DISTINCT u.email FROM users u "
            "JOIN roles r ON LOWER(r.role_name) = LOWER(u.role) "
            "JOIN role_permissions rp ON rp.role_id = r.id "
            "JOIN permissions p ON p.id = rp.permission_id "
            f"WHERE p.permission_name IN ({marks}) AND COALESCE(u.email, '') <> ''",
            perms).fetchall()
    except Exception:
        logger.debug("approver lookup failed", exc_info=True)
        return []
    return [r[0] for r in rows]


def submit_for_approval(auth, trip_id, *, conn=None, pending=None):
    """Ask for approval: a 'pending' row for each required stage not yet approved.

    The trip must be 'proposed' (or legacy 'planning') and the user able to
    manage it. Stages already approved for this trip stand; rejected or
    returned ones are asked again. The approvers are e-mailed after the
    commit. Returns :func:`approval_state`.
    """
    trips = _trips()
    who = trips._require(auth, 'manage_trips', 'create_trips')

    def work(c, p):
        trip = trips._load_for_change(c, auth, trip_id, who)
        if trip['status'] not in _SUBMITTABLE:
            raise ValueError(f"only a proposed trip can be submitted for approval (this one is {trip['status']})")
        latest = _latest_rows(c, trip_id)
        required = required_stages(trip)
        to_ask = [s for s in required
                  if latest.get(s, {}).get('decision') not in ('approved', 'pending')]
        if not to_ask:
            if any(latest.get(s, {}).get('decision') == 'pending' for s in required):
                raise ValueError("this trip is already waiting for approval")
            raise ValueError("every approval stage has already been approved")
        now = trips._now()
        _insert_pending(c, trip, to_ask, now)
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='submitted', field='approvals', new_value=",".join(to_ask))
        trips._publish_after(p, "trip.approval.requested", trip_id=trip_id, stages=to_ask,
                             version=trip.get('version'))
        trips.queue_email(
            p, _approver_emails(c, to_ask),
            f"Trip approval requested: {trip['trip_name']}",
            f"{who['username']} has submitted the trip '{trip['trip_name']}' to "
            f"{trip['destination']} ({trip['start_date']} to {trip['end_date']}) for approval.\n\n"
            f"Stages waiting: {', '.join(STAGE_LABELS[s] for s in to_ask)}.\n"
            "Decide it in Trip Management (Approvals).")
        return approval_state(trip_id, conn=c)
    return trips._in_transaction(conn, pending, work)


def decide(auth, trip_id, stage, decision, comments="", *, conn=None, pending=None):
    """Record a stage decision: 'approved', 'rejected' or 'returned'.

    Needs the stage's permission (:data:`STAGE_PERMISSIONS`). The trip's
    creator or a leader may not decide their own trip, unless they hold
    ``manage_trips`` and give comments (recorded as a self-approval).
    Rejecting or returning needs comments and sends an 'approved' trip back
    to 'proposed'. When every required stage is approved the trip moves to
    'approved'. The trip's creator and leaders are e-mailed after the
    commit. Returns :func:`approval_state`.
    """
    trips = _trips()
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {', '.join(STAGES)}")
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    who = trips._require(auth, STAGE_PERMISSIONS[stage])
    comments = (comments or '').strip()
    if decision != 'approved' and not comments:
        raise ValueError("say why the trip is being rejected or returned (comments)")

    def work(c, p):
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if trip['status'] in ('cancelled', 'archived', 'completed'):
            raise ValueError(f"the trip is {trip['status']}")
        if stage not in required_stages(trip):
            raise ValueError(f"this trip does not need {STAGE_LABELS[stage]} approval")
        own = trip.get('created_by') == who['user_id'] and who['user_id'] is not None
        if not own and who['user_id'] is not None:
            own = c.execute("SELECT 1 FROM trip_staff WHERE trip_id = ? AND staff_user_id = ? "
                            "AND role IN ('coordinator', 'supervisor')",
                            (trip_id, who['user_id'])).fetchone() is not None
        note = comments
        if own:
            if not (auth.check_permission('manage_trips') and comments):
                raise PermissionError("you created or lead this trip, so someone else must decide it")
            note = f"[self-approval] {comments}"
        row = _latest_rows(c, trip_id).get(stage)
        if not row or row['decision'] != 'pending':
            raise ValueError(f"{STAGE_LABELS[stage]} approval is not waiting for a decision")
        now = trips._now()
        c.execute("UPDATE trip_approvals SET decision = ?, decided_by = ?, decided_at = ?, "
                  "comments = ? WHERE id = ?", (decision, who['username'], now, note or None, row['id']))
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action=f'approval_{decision}', field=stage, new_value=note or None)
        state = approval_state(trip_id, conn=c)
        new_status = None
        if decision == 'approved' and state['complete'] and trip['status'] in _SUBMITTABLE:
            new_status = 'approved'
        elif decision != 'approved' and trip['status'] == 'approved':
            new_status = 'proposed'
        if new_status:
            version = int(trip.get('version') or 1) + 1
            c.execute("UPDATE trips SET status = ?, version = ?, updated_by = ?, updated_at = ? "
                      "WHERE id = ?", (new_status, version, who['username'], now, trip_id))
            trips.record_history(c, trip_id, version=version, changed_by=who['username'],
                                 action='status', field='status', old_value=trip['status'],
                                 new_value=new_status)
            trips._publish_after(p, "trip.status.changed", trip_id=trip_id,
                                 old_status=trip['status'], new_status=new_status,
                                 reason=f"{stage} {decision}", version=version)
        trips._publish_after(p, "trip.approval.decided", trip_id=trip_id, stage=stage,
                             decision=decision, decided_by=who['username'])
        outcome = (f"{STAGE_LABELS[stage]} approval: {decision}"
                   + (f"\nComments: {note}" if note else ""))
        if new_status == 'approved':
            outcome += "\n\nEvery stage is approved; the trip is now Approved."
        trips.queue_email(p, trips.leader_emails(c, trip),
                          f"Trip {decision}: {trip['trip_name']} ({STAGE_LABELS[stage]})", outcome)
        return approval_state(trip_id, conn=c)
    return trips._in_transaction(conn, pending, work)


def reset_for_material_change(conn, trip, who, changed_fields, *, pending=None):
    """Put the trip's approvals back to pending after a material edit.

    Runs on the caller's transaction (``trips.update_trip_record`` and
    ``overseas.record_fcdo_check`` call it). Only a trip that has been
    submitted is reset: a new 'pending' row for every stage it now needs
    (at its new version), and an 'approved' trip goes back to 'proposed'.
    An open trip keeps taking registrations, but cannot be reopened (from
    full / closed) until it is approved again. Returns True when it reset.
    """
    trips = _trips()
    latest = _latest_rows(conn, trip['id'])
    if not latest or trip['status'] in ('cancelled', 'archived', 'completed'):
        return False
    stages = required_stages(trip)
    now = trips._now()
    _insert_pending(conn, trip, stages, now)
    trips.record_history(conn, trip['id'], version=trip.get('version'), changed_by=who['username'],
                         action='approvals_reset', field='approvals',
                         new_value=f"material change: {', '.join(changed_fields)}")
    if trip['status'] == 'approved':
        conn.execute("UPDATE trips SET status = 'proposed', updated_by = ?, updated_at = ? "
                     "WHERE id = ?", (who['username'], now, trip['id']))
        trips.record_history(conn, trip['id'], version=trip.get('version'),
                             changed_by=who['username'], action='status', field='status',
                             old_value='approved', new_value='proposed')
        if pending is not None:
            trips._publish_after(pending, "trip.status.changed", trip_id=trip['id'],
                                 old_status='approved', new_status='proposed',
                                 reason="approvals reset", version=trip.get('version'))
    if pending is not None:
        trips._publish_after(pending, "trip.approval.requested", trip_id=trip['id'],
                             stages=stages, version=trip.get('version'))
        trips.queue_email(
            pending, _approver_emails(conn, stages),
            f"Trip changed — approval needed again: {trip['trip_name']}",
            f"The trip '{trip['trip_name']}' was changed ({', '.join(changed_fields)}) by "
            f"{who['username']}, so its approvals have been reset. Stages waiting: "
            f"{', '.join(STAGE_LABELS[s] for s in stages)}.")
    return True


def pending_for(auth, conn=None):
    """Approval rows waiting on a stage the signed-in user can decide."""
    stages = [s for s in STAGES if auth.check_permission(STAGE_PERMISSIONS[s])]
    if not stages:
        return []
    marks = ", ".join('?' * len(stages))
    with _db().read_connection(conn) as c:
        cur = c.execute(
            "SELECT a.id, a.trip_id, a.stage, a.trip_version, a.created_at, t.trip_name, "
            "t.destination, t.start_date, t.end_date, t.status FROM trip_approvals a "
            "JOIN trips t ON t.id = a.trip_id "
            "WHERE a.decision = 'pending' AND a.id IN ("
            "  SELECT MAX(id) FROM trip_approvals GROUP BY trip_id, stage) "
            f"AND a.stage IN ({marks}) ORDER BY t.start_date, a.id", stages)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]
