"""Staff wellbeing entries (systems.primary.domain.staff.staff_wellbeing.staff_wellbeing)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.staff_wellbeing import staff_wellbeing as WB

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _staff(first="Amy", last="Adams"):
    return S.create_staff({"first_name": first, "last_name": last})


def _entry(staff_id, **extra):
    return WB.create_entry({"staff_id": staff_id, "entry_type": "1:1 Check-In", **extra})


def test_likert_labels():
    assert [WB.likert_label(v) for v in WB.LIKERTS] == [
        "Very Low", "Low", "Moderate", "High", "Very High"]
    assert WB.likert_label(None) == "—" and WB.likert_label(0) == "Unknown"


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_read_back():
    s = _staff()
    e = _entry(s.staff_id, mood="3", recorded_by=" Head ", presenting_issue=" tired ")
    assert (e.entry_date, e.entry_type, e.status) == (_d(0), "1:1 Check-In", "Recorded")
    assert (e.confidential, e.anonymous, e.consent_to_share) == (True, False, False)
    assert (e.mood, e.stress, e.recorded_by, e.presenting_issue) == (3, None, "Head", "tired")
    assert (e.concern_flags, e.action_type, e.concern_flag_list) == (None, None, [])
    assert e.is_open is True
    assert WB.get_entry(e.entry_id) == e
    assert WB.get_entry(999) is None


def test_concern_flags_from_list_or_string():
    s = _staff()
    a = _entry(s.staff_id, concern_flags=["Workload", "Pupil Behaviour"])
    assert a.concern_flags == "Workload, Pupil Behaviour"
    assert a.concern_flag_list == ["Workload", "Pupil Behaviour"]
    b = _entry(s.staff_id, concern_flags=" Health , ,Financial ")
    assert b.concern_flag_list == ["Health", "Financial"]
    assert _entry(s.staff_id, concern_flags=[]).concern_flags is None
    assert _entry(s.staff_id, concern_flags=" , ").concern_flags is None


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"entry_date": "x"}, "Entry date must be YYYY-MM-DD"),
    ({"follow_up_due": "x"}, "Follow-up due must be YYYY-MM-DD"),
    ({"follow_up_done_on": "x"}, "Follow-up done must be YYYY-MM-DD"),
    ({"closed_on": "x"}, "Closed on must be YYYY-MM-DD"),
    ({"entry_type": ""}, "Entry type must be one of"),
    ({"entry_type": "Chat"}, "Entry type must be one of"),
    ({"status": "Open"}, "Status must be one of"),
    ({"mood": 6}, "Mood must be 1-5"),
    ({"stress": "high"}, "Stress must be 1-5"),
    ({"workload_pressure": 0}, "Workload Pressure must be 1-5"),
    ({"job_satisfaction": 9}, "Job Satisfaction must be 1-5"),
    ({"energy": -1}, "Energy must be 1-5"),
    ({"concern_flags": ["Workload", "Weather"]}, "Concern flag 'Weather' is not recognised"),
    ({"concern_flags": "Ofsted"}, "Concern flag 'Ofsted' is not recognised"),
    ({"action_type": "Pay rise"}, "Action type must be one of"),
])
def test_create_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, "entry_type": "1:1 Check-In", **bad}
    with pytest.raises(WB.ValidationError, match=msg):
        WB.create_entry(data)
    assert WB.list_entries() == []


# ── Derived figures ──────────────────────────────────────────────────

def test_at_risk_thresholds():
    s = _staff()
    assert _entry(s.staff_id, stress=4).at_risk is True
    assert _entry(s.staff_id, workload_pressure=4).at_risk is True
    assert _entry(s.staff_id, mood=2).at_risk is True
    assert _entry(s.staff_id, stress=3, workload_pressure=3, mood=3).at_risk is False
    assert _entry(s.staff_id).at_risk is False


def test_average_score_and_follow_up_overdue():
    s = _staff()
    assert _entry(s.staff_id).average_score is None
    assert _entry(s.staff_id, mood=4, energy=3, job_satisfaction=4).average_score == 3.67
    assert _entry(s.staff_id, follow_up_due=_d(-1)).follow_up_overdue is True
    assert _entry(s.staff_id, follow_up_due=_d(0)).follow_up_overdue is False
    assert _entry(s.staff_id, follow_up_due=_d(-1),
                  follow_up_done_on=_d(-1)).follow_up_overdue is False
    assert _entry(s.staff_id, follow_up_due=_d(-1),
                  status="Resolved").follow_up_overdue is False


# ── Update / delete ──────────────────────────────────────────────────

def test_update_and_delete():
    s = _staff()
    e = _entry(s.staff_id)
    up = WB.update_entry(e.entry_id, {"staff_id": s.staff_id, "entry_type": "Workload Review",
                                      "confidential": False, "anonymous": True})
    assert (up.entry_type, up.confidential, up.anonymous) == ("Workload Review", False, True)
    with pytest.raises(WB.ValidationError, match="No entry with id 999"):
        WB.update_entry(999, {"staff_id": s.staff_id})
    assert WB.delete_entry(e.entry_id) is True
    assert WB.delete_entry(e.entry_id) is False


def test_staff_delete_cascades():
    s = _staff()
    e = _entry(s.staff_id)
    S.delete_staff(s.staff_id)
    assert WB.get_entry(e.entry_id) is None


# ── Workflow ─────────────────────────────────────────────────────────

def test_action_plan_follow_up_resolve():
    s = _staff()
    e = _entry(s.staff_id, notes="initial")
    with pytest.raises(WB.ValidationError, match="Action type must be one of"):
        WB.set_action_plan(e.entry_id, action_type="Cake", actions_taken="x")
    with pytest.raises(WB.ValidationError, match="Actions taken is required"):
        WB.set_action_plan(e.entry_id, action_type="Mentor Assigned", actions_taken="")
    plan = WB.set_action_plan(e.entry_id, action_type="Workload Adjusted",
                              actions_taken="PPA moved", support_plan="weekly check",
                              follow_up_due="2026-11-20", referred_to="OH")
    assert (plan.status, plan.action_type, plan.actions_taken) == (
        "Action Plan Set", "Workload Adjusted", "PPA moved")
    assert (plan.support_plan, plan.follow_up_due, plan.referred_to) == (
        "weekly check", "2026-11-20", "OH")
    fu = WB.complete_follow_up(e.entry_id, done_on="2026-11-19", notes="better")
    assert (fu.follow_up_done_on, fu.status) == ("2026-11-19", "Monitoring")
    assert fu.notes == f"initial\n{_d(0)} follow-up: better"
    # a second follow-up keeps Monitoring and defaults the date to today
    fu2 = WB.complete_follow_up(e.entry_id)
    assert (fu2.follow_up_done_on, fu2.status, fu2.notes) == (_d(0), "Monitoring", fu.notes)
    res = WB.resolve(e.entry_id)
    assert (res.status, res.closed_on, res.is_open) == ("Resolved", _d(0), False)


def test_close_keeps_existing_closed_date_and_set_status():
    s = _staff()
    e = _entry(s.staff_id, closed_on="2026-10-01")
    closed = WB.close_entry(e.entry_id)
    assert (closed.status, closed.closed_on) == ("Closed", "2026-10-01")
    assert WB.close_entry(_entry(s.staff_id).entry_id).closed_on == _d(0)
    assert WB.set_status(e.entry_id, "Reviewing").status == "Reviewing"
    with pytest.raises(WB.ValidationError, match="Status must be one of"):
        WB.set_status(e.entry_id, "Happy")


def test_workflow_refuses_missing():
    calls = (
        lambda: WB.set_action_plan(404, action_type="Other", actions_taken="x"),
        lambda: WB.complete_follow_up(404),
        lambda: WB.resolve(404),
        lambda: WB.close_entry(404),
        lambda: WB.set_status(404, "Closed"),
    )
    for call in calls:
        with pytest.raises(WB.ValidationError, match="No entry with id 404"):
            call()


# ── Listing ──────────────────────────────────────────────────────────

def test_list_filters_and_order():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    e1 = _entry(a.staff_id, entry_date="2026-09-01", stress=5, concern_flags=["Workload"])
    e2 = _entry(a.staff_id, entry_date="2026-10-01", entry_type="EAP Referral",
                action_type="Signposted to EAP", status="Resolved")
    e3 = _entry(b.staff_id, entry_date="2026-11-01", follow_up_due=_d(-1),
                concern_flags="Health, Bereavement")
    ids = lambda rows: [x.entry_id for x in rows]  # noqa: E731
    assert ids(WB.list_entries()) == [e3.entry_id, e2.entry_id, e1.entry_id]
    assert ids(WB.list_entries(staff_id=a.staff_id)) == [e2.entry_id, e1.entry_id]
    assert ids(WB.entries_for_staff(b.staff_id)) == [e3.entry_id]
    assert ids(WB.list_entries(entry_type="EAP Referral")) == [e2.entry_id]
    assert ids(WB.list_entries(status="Resolved")) == [e2.entry_id]
    assert ids(WB.list_entries(action_type="Signposted to EAP")) == [e2.entry_id]
    assert ids(WB.list_entries(open_only=True)) == [e3.entry_id, e1.entry_id]
    assert ids(WB.list_entries(at_risk_only=True)) == [e1.entry_id]
    assert ids(WB.list_entries(follow_up_overdue=True)) == [e3.entry_id]
    assert ids(WB.list_entries(with_concern_flag="Bereavement")) == [e3.entry_id]
    assert ids(WB.list_entries(date_from="2026-09-15", date_to="2026-10-15")) == [e2.entry_id]
    with pytest.raises(WB.ValidationError, match="From must be YYYY-MM-DD"):
        WB.list_entries(date_from="autumn")


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = WB.summary()
    assert (sm.total, sm.distinct_staff, sm.average_mood) == (0, 0, None)


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    _entry(a.staff_id, mood=2, stress=5, workload_pressure=4, concern_flags=["Workload"],
           follow_up_due=_d(-2))
    _entry(a.staff_id, entry_type="Occupational Health Referral", mood=4, stress=2,
           job_satisfaction=4, energy=3, action_type="Occupational Health Referral",
           status="Closed", concern_flags=["Workload", "Health"])
    _entry(b.staff_id, entry_type="EAP Referral", mood=3, energy=4)
    _entry(b.staff_id, entry_type="Wellbeing Survey")
    sm = WB.summary()
    assert (sm.total, sm.open_count, sm.at_risk, sm.follow_up_overdue) == (4, 3, 1, 1)
    assert (sm.referrals_made, sm.distinct_staff) == (2, 2)
    assert sm.average_mood == 3.0              # (2 + 4 + 3) / 3
    assert sm.average_stress == 3.5            # (5 + 2) / 2
    assert sm.average_workload == 4.0
    assert sm.average_satisfaction == 4.0
    assert sm.average_energy == 3.5
    assert sm.by_type == {"1:1 Check-In": 1, "Occupational Health Referral": 1,
                          "EAP Referral": 1, "Wellbeing Survey": 1}
    assert sm.by_status == {"Recorded": 3, "Closed": 1}
    assert sm.by_action == {"Occupational Health Referral": 1}
    assert sm.by_concern_flag == {"Workload": 2, "Health": 1}
