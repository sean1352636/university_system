"""Safeguarding concerns (systems.primary.domain.safeguarding.safeguarding).

The module itself does not gate who may read a concern (its docstring leaves
access control to the calling code; the capability check lives in
``domain.access``), so these tests cover the stored rules and the one place
the module decides what leaves it: the cross-system safeguarding flag, which
must carry the category only, never the confidential description or notes.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.platform.cross_system import person
from education_system.platform.governance.safeguarding import alert_service as AS
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.safeguarding import safeguarding as SG

TODAY = dt.date.today().isoformat()
SECRET = "Child disclosed bruising from step-parent at home"

_n = 0


def _pupil(year="3"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-03-01"})


def _concern(pupil, **extra):
    return SG.raise_concern({"pupil_id": pupil.pupil_id, "description": SECRET,
                             "raised_by": "teacher1", "raised_date": "2026-10-01",
                             **extra})


# ── raising a concern ───────────────────────────────────────────────

def test_raise_concern_defaults_and_read_back():
    ava = _pupil()
    c = _concern(ava)
    assert (c.category, c.severity, c.status) == ("Disclosure", "Medium", "Open")
    assert c.confidential is True
    assert c.description == SECRET and c.raised_by == "teacher1"
    assert c.raised_date == "2026-10-01"
    assert c.pupil_name == ava.full_name and c.pupil_year == "3"
    assert SG.get(c.concern_id) == c


def test_raise_concern_stores_every_field():
    ava = _pupil()
    c = _concern(ava, category="Neglect", severity="High", incident_date="2026-09-30",
                 incident_time="09:15", location="  Playground ", dsl_reviewer="Mrs DSL",
                 review_date="2026-10-08", confidential=False, notes="  see file ",
                 referral_body="Early Help", referral_date="2026-10-02",
                 referral_reference="EH-1", status="Referred")
    assert (c.category, c.severity, c.status) == ("Neglect", "High", "Referred")
    assert (c.incident_date, c.incident_time, c.location) == ("2026-09-30", "09:15",
                                                              "Playground")
    assert (c.referral_body, c.referral_date, c.referral_reference) == (
        "Early Help", "2026-10-02", "EH-1")
    assert c.dsl_reviewer == "Mrs DSL" and c.review_date == "2026-10-08"
    assert c.confidential is False and c.notes == "see file"


def test_raised_date_defaults_to_today():
    c = SG.raise_concern({"pupil_id": _pupil().pupil_id, "description": "x"})
    assert c.raised_date == TODAY


@pytest.mark.parametrize("bad, message", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"pupil_id": "P0000000"}, "No pupil with id P0000000"),
    ({"category": "Shoplifting"}, "Category must be one of"),
    ({"severity": "Extreme"}, "Severity must be one of"),
    ({"status": "Pending"}, "Status must be one of"),
    ({"description": "   "}, "Description is required"),
    ({"incident_date": "01/10/2026"}, "Incident date must be YYYY-MM-DD"),
    ({"incident_date": "2026-02-30"}, "Incident date is not a real date"),
    ({"incident_time": "25:00"}, "Incident time must be HH:MM"),
    ({"referral_body": "Neighbour"}, "Referral body must be one of"),
    ({"status": "Closed"}, "Outcome is required when status is Closed"),
    ({"status": "Referred"}, "Referral body is required when status is Referred"),
    ({"status": "Closed", "outcome": "Resolved", "closed_date": "2026-09-01"},
     "Closed date cannot be before raised date"),
    ({"referral_body": "Police", "referral_date": "2026-09-01"},
     "Referral date cannot be before raised date"),
])
def test_raise_concern_refusals(bad, message):
    ava = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _concern(ava, **bad)
    assert SG.list_concerns() == []


def test_closed_concern_gets_todays_closed_date():
    c = _concern(_pupil(), status="Closed", outcome="No further action")
    assert c.closed_date == TODAY and c.outcome == "No further action"


# ── cross-system flag: follows the pupil, never carries the detail ──

def test_cross_system_flag_carries_category_not_description():
    ava = _pupil()
    c = _concern(ava, category="Neglect", severity="High", notes="private DSL note")
    journey = person.get_by_student("primary", ava.pupil_id)
    assert journey is not None
    alerts = AS.get_alerts(journey.journey_id)
    assert len(alerts) == 1
    alert = alerts[0]
    assert (alert["source_system"], alert["source_ref"]) == ("primary", str(c.concern_id))
    assert (alert["category"], alert["summary"]) == ("Neglect", "Neglect")
    assert alert["raised_by"] == "teacher1"
    flat = " ".join(str(v) for v in alert.values())
    assert SECRET not in flat and "private DSL note" not in flat


def test_cross_system_publish_arguments(monkeypatch):
    seen = []
    monkeypatch.setattr(AS, "raise_flag_for_local_concern",
                        lambda *a, **k: seen.append((a, k)))
    ava = _pupil()
    c = _concern(ava, category="Online safety", severity="Low", location="ICT suite")
    assert len(seen) == 1
    args, kwargs = seen[0]
    assert args == ("primary", ava.pupil_id)
    assert kwargs["summary"] == "Online safety" and kwargs["source_ref"] == str(c.concern_id)
    assert SECRET not in repr(seen) and "ICT suite" not in repr(seen)


def test_publish_failure_never_blocks_the_concern(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bus down")
    monkeypatch.setattr(AS, "raise_flag_for_local_concern", boom)
    c = _concern(_pupil())
    assert SG.get(c.concern_id) is not None


# ── listing and filters ─────────────────────────────────────────────

def test_list_orders_by_severity_then_newest():
    ava, ben = _pupil("2"), _pupil("5")
    low = _concern(ava, severity="Low", raised_date="2026-10-03")
    med_old = _concern(ava, severity="Medium", raised_date="2026-10-01")
    med_new = _concern(ben, severity="Medium", raised_date="2026-10-04")
    crit = _concern(ben, severity="Critical", raised_date="2026-10-02")
    ids = [c.concern_id for c in SG.list_concerns()]
    assert ids == [crit.concern_id, med_new.concern_id, med_old.concern_id, low.concern_id]


def test_list_filters():
    ava, ben = _pupil("2"), _pupil("5")
    a1 = _concern(ava, category="Neglect", raised_date="2026-10-01")
    a2 = _concern(ava, category="Bullying", severity="High", raised_date="2026-10-05")
    b1 = _concern(ben, status="Monitoring", raised_date="2026-10-10")

    def ids(**kw):
        return {c.concern_id for c in SG.list_concerns(**kw)}
    assert ids(pupil_id=ava.pupil_id) == {a1.concern_id, a2.concern_id}
    assert ids(year_group="5") == {b1.concern_id}
    assert ids(category="Neglect") == {a1.concern_id}
    assert ids(severity="High") == {a2.concern_id}
    assert ids(status="Monitoring") == {b1.concern_id}
    assert ids(date_from="2026-10-05") == {a2.concern_id, b1.concern_id}
    assert ids(date_to="2026-10-05") == {a1.concern_id, a2.concern_id}
    assert ids(date_from="2026-10-02", date_to="2026-10-09") == {a2.concern_id}


@pytest.mark.parametrize("kw, message", [
    ({"year_group": "7"}, "Year filter must be one of"),
    ({"category": "Nope"}, "Category filter must be one of"),
    ({"severity": "Nope"}, "Severity filter must be one of"),
    ({"status": "Nope"}, "Status filter must be one of"),
    ({"date_from": "yesterday"}, "From date must be YYYY-MM-DD"),
    ({"date_to": "2026-13-01"}, "To date is not a real date"),
])
def test_list_filter_refusals(kw, message):
    with pytest.raises(P.ValidationError, match=message):
        SG.list_concerns(**kw)


def test_empty_database():
    assert SG.list_concerns() == []
    assert SG.get(999) is None
    assert SG.delete(999) is False
    assert SG.list_actions(999) == []
    assert SG.get_action(999) is None
    assert SG.delete_action(999) is False
    assert SG.pupils_with_concerns() == {}
    assert SG.cohort_summary() == {"total": 0, "open": 0, "by_status": {},
                                   "by_severity": {}, "by_category": {},
                                   "open_critical": 0}


# ── update, status and delete ───────────────────────────────────────

def test_update_merges_and_revalidates():
    c = _concern(_pupil(), notes="first")
    u = SG.update(c.concern_id, {"severity": "Critical", "dsl_reviewer": "Mr Lead"})
    assert (u.severity, u.dsl_reviewer, u.notes, u.description) == (
        "Critical", "Mr Lead", "first", SECRET)
    with pytest.raises(P.ValidationError, match="Severity must be one of"):
        SG.update(c.concern_id, {"severity": "Huge"})
    assert SG.get(c.concern_id).severity == "Critical"
    with pytest.raises(P.ValidationError, match="No safeguarding concern #999"):
        SG.update(999, {"severity": "Low"})


def test_set_status_rules():
    c = _concern(_pupil())
    with pytest.raises(P.ValidationError, match="Referral body is required"):
        SG.set_status(c.concern_id, "Referred")
    r = SG.set_status(c.concern_id, "Referred", referral_body="MASH / Social Care")
    assert (r.status, r.referral_body) == ("Referred", "MASH / Social Care")
    with pytest.raises(P.ValidationError, match="Outcome is required"):
        SG.set_status(c.concern_id, "Closed")
    done = SG.set_status(c.concern_id, "Closed", outcome="Family supported")
    assert (done.status, done.outcome, done.closed_date) == ("Closed", "Family supported",
                                                            TODAY)


def test_delete_cascades_actions():
    c = _concern(_pupil())
    a = SG.add_action({"concern_id": c.concern_id, "summary": "Met DSL",
                       "action_date": "2026-10-02"})
    assert SG.delete(c.concern_id) is True
    assert SG.get(c.concern_id) is None
    assert SG.get_action(a.action_id) is None
    assert SG.delete(c.concern_id) is False


# ── actions ─────────────────────────────────────────────────────────

def test_add_and_list_actions():
    c = _concern(_pupil())
    first = SG.add_action({"concern_id": str(c.concern_id), "summary": " Spoke to pupil ",
                           "action_type": "Pupil interview", "action_date": "2026-10-02",
                           "actioned_by": "Mrs DSL", "outcome": "Disclosure confirmed",
                           "follow_up": "Call parent"})
    second = SG.add_action({"concern_id": c.concern_id, "summary": "Phoned home",
                            "action_type": "Phone call", "action_date": "2026-10-03"})
    same_day = SG.add_action({"concern_id": c.concern_id, "summary": "Letter",
                              "action_type": "Letter sent", "action_date": "2026-10-03"})
    assert (first.concern_id, first.summary, first.action_type) == (
        c.concern_id, "Spoke to pupil", "Pupil interview")
    assert (first.actioned_by, first.outcome, first.follow_up) == (
        "Mrs DSL", "Disclosure confirmed", "Call parent")
    assert [a.action_id for a in SG.list_actions(c.concern_id)] == [
        same_day.action_id, second.action_id, first.action_id]
    assert SG.get_action(first.action_id) == first


def test_action_defaults():
    c = _concern(_pupil())
    a = SG.add_action({"concern_id": c.concern_id, "summary": "Logged"})
    assert (a.action_type, a.action_date, a.actioned_by) == ("DSL meeting", TODAY, None)


@pytest.mark.parametrize("bad, message", [
    ({"concern_id": ""}, "Concern ID is required"),
    ({"concern_id": "abc"}, "Concern ID must be a number"),
    ({"concern_id": 999}, "No safeguarding concern #999"),
    ({"action_type": "Text message"}, "Action type must be one of"),
    ({"summary": " "}, "Summary is required"),
    ({"action_date": "2026/10/02"}, "Action date must be YYYY-MM-DD"),
])
def test_action_refusals(bad, message):
    c = _concern(_pupil())
    with pytest.raises(P.ValidationError, match=message):
        SG.add_action({"concern_id": c.concern_id, "summary": "x", **bad})
    assert SG.list_actions(c.concern_id) == []


def test_delete_action():
    c = _concern(_pupil())
    a = SG.add_action({"concern_id": c.concern_id, "summary": "x"})
    assert SG.delete_action(a.action_id) is True
    assert SG.delete_action(a.action_id) is False
    assert SG.list_actions(c.concern_id) == []


# ── summaries ───────────────────────────────────────────────────────

def test_concern_summary_counts_actions_by_type():
    c = _concern(_pupil())
    for kind in ("Phone call", "Phone call", "Home visit"):
        SG.add_action({"concern_id": c.concern_id, "summary": kind, "action_type": kind})
    s = SG.concern_summary(c.concern_id)
    assert s["concern"] == SG.get(c.concern_id)
    assert s["action_count"] == 3 and len(s["actions"]) == 3
    assert s["by_type"] == {"Phone call": 2, "Home visit": 1}
    with pytest.raises(P.ValidationError, match="No safeguarding concern #999"):
        SG.concern_summary(999)


def test_cohort_summary_counts():
    ava, ben = _pupil("2"), _pupil("5")
    _concern(ava, severity="Critical", category="Neglect")
    _concern(ava, severity="Critical", category="Neglect", status="Closed", outcome="Done")
    _concern(ben, severity="Low", category="Bullying", status="Monitoring",
             raised_date="2026-10-20")
    s = SG.cohort_summary()
    assert s["total"] == 3 and s["open"] == 2 and s["open_critical"] == 1
    assert s["by_status"] == {"Open": 1, "Closed": 1, "Monitoring": 1}
    assert s["by_severity"] == {"Critical": 2, "Low": 1}
    assert s["by_category"] == {"Neglect": 2, "Bullying": 1}
    assert SG.cohort_summary(year_group="5")["total"] == 1
    assert SG.cohort_summary(date_from="2026-10-10")["total"] == 1


def test_pupils_with_concerns_threshold():
    ava, ben, cat = _pupil(), _pupil(), _pupil()
    a_high = _concern(ava, severity="High")
    a_crit = _concern(ava, severity="Critical")
    _concern(ben, severity="Medium")
    _concern(cat, severity="Critical", status="Closed", outcome="Resolved")
    out = SG.pupils_with_concerns()
    assert set(out) == {ava.pupil_id}
    assert {c.concern_id for c in out[ava.pupil_id]} == {a_high.concern_id, a_crit.concern_id}
    assert set(SG.pupils_with_concerns(severity_min="Medium")) == {ava.pupil_id, ben.pupil_id}
    assert [c.concern_id for c in SG.pupils_with_concerns(severity_min="Critical")[
        ava.pupil_id]] == [a_crit.concern_id]
    with pytest.raises(P.ValidationError, match="severity_min must be one of"):
        SG.pupils_with_concerns(severity_min="Severe")
