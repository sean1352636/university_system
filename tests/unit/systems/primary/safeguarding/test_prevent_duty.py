"""Prevent-duty referrals (systems.primary.domain.safeguarding.prevent_duty.prevent_duty)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.safeguarding.prevent_duty import prevent_duty as PD

TODAY = dt.date.today().isoformat()

_n = 0


def _pupil(year="5"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Prev{_n:03d}",
                           "year_group": year, "date_of_birth": "2016-05-01"})


def _ref(pupil, **extra):
    return PD.create({"pupil_id": pupil.pupil_id, "raised_by": "teacher1",
                      "description": "Repeating extremist slogans", "raised_date": "2026-10-01",
                      **extra})


# The fields an external referral needs before it is accepted.
EXTERNAL = {"dsl_informed": True, "dsl_name": "Mrs DSL", "referral_date": "2026-10-03"}


# ── creating a referral ─────────────────────────────────────────────

def test_create_defaults_and_read_back():
    ava = _pupil()
    r = _ref(ava)
    assert (r.concern_type, r.risk_level, r.referral_pathway) == (
        "Vulnerability to radicalisation", "Low", "Internal monitoring")
    assert (r.status, r.outcome) == ("Open", "Pending")
    assert r.dsl_informed is False and r.parents_informed is False
    assert r.closed_date is None and r.dsl_informed_date is None
    assert r.pupil_name == ava.full_name and r.pupil_year == "5"
    assert PD.get(r.referral_id) == r


def test_create_stores_every_field():
    r = _ref(_pupil(), concern_type="Far-right extremism", risk_level="High",
             dsl_informed=True, dsl_name=" Mrs DSL ", dsl_informed_date="2026-10-02",
             indicators="Symbols on books", online_activity="Forum posts",
             referral_pathway="Channel referral (Prevent)", referral_date="2026-10-03",
             referral_ref="CH-9", agencies_involved="LA Prevent officer",
             parents_informed=True, parents_informed_date="2026-10-04",
             next_review_date="2026-11-01", status="Channel panel", notes=" n ")
    assert (r.concern_type, r.risk_level, r.referral_pathway, r.status) == (
        "Far-right extremism", "High", "Channel referral (Prevent)", "Channel panel")
    assert (r.dsl_informed, r.dsl_name, r.dsl_informed_date) == (True, "Mrs DSL",
                                                                 "2026-10-02")
    assert (r.indicators, r.online_activity) == ("Symbols on books", "Forum posts")
    assert (r.referral_date, r.referral_ref, r.agencies_involved) == (
        "2026-10-03", "CH-9", "LA Prevent officer")
    assert (r.parents_informed, r.parents_informed_date) == (True, "2026-10-04")
    assert r.next_review_date == "2026-11-01" and r.notes == "n"


def test_date_defaults():
    r = PD.create({"pupil_id": _pupil().pupil_id, "raised_by": "t", "description": "d",
                   "dsl_informed": True, "dsl_name": "DSL", "parents_informed": True})
    assert r.raised_date == TODAY
    assert r.dsl_informed_date == TODAY and r.parents_informed_date == TODAY


@pytest.mark.parametrize("bad, message", [
    ({"pupil_id": " "}, "Pupil ID is required"),
    ({"pupil_id": "P0000000"}, "No pupil with id P0000000"),
    ({"concern_type": "Gangs"}, "Concern type must be one of"),
    ({"risk_level": "Severe"}, "Risk level must be one of"),
    ({"raised_by": ""}, "Raised-by is required"),
    ({"raised_date": "1/10/2026"}, "Raised date must be YYYY-MM-DD"),
    ({"raised_date": "2026-02-31"}, "Raised date is not a real date"),
    ({"dsl_informed": True}, "DSL name is required when DSL has been informed"),
    ({"description": ""}, "Description is required"),
    ({"description": "x" * 4001}, "max 4000 chars"),
    ({"referral_pathway": "Teacher chat"}, "Referral pathway must be one of"),
    ({"referral_pathway": "Police referral", "dsl_informed": True, "dsl_name": "D"},
     "Referral date is required for pathway Police referral"),
    ({"referral_pathway": "Channel referral (Prevent)", "referral_date": "2026-10-03"},
     "DSL must be informed before an external referral"),
    ({"next_review_date": "2026-09-01"}, "Next review date cannot be before raised date"),
    ({"status": "Archived"}, "Status must be one of"),
    ({"outcome": "Expelled"}, "Outcome must be one of"),
    ({"status": "Closed — supported"}, "Outcome cannot be 'Pending' on a closed referral"),
    ({"status": "Closed — supported", "outcome": "Supported", "closed_date": "2026-09-01"},
     "Closed date cannot be before raised date"),
    ({"closed_date": "2026-10-05"}, "Closed date should only be set when status is"),
    ({"risk_level": "High"}, "DSL must be informed for High-risk referrals"),
    ({"risk_level": "Imminent"}, "DSL must be informed for Imminent-risk referrals"),
])
def test_create_refusals(bad, message):
    ava = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _ref(ava, **bad)
    assert PD.list_referrals() == []


def test_external_pathways_accepted_with_dsl_and_date():
    ava = _pupil()
    for pathway in ("Channel referral (Prevent)", "Police referral", "Other agency"):
        r = _ref(ava, referral_pathway=pathway, **EXTERNAL)
        assert r.referral_pathway == pathway
    # internal pathways need neither
    assert _ref(ava, referral_pathway="DSL only").referral_date is None
    assert _ref(ava, referral_pathway="No referral").dsl_informed is False


def test_closed_status_defaults_closed_date_to_today():
    r = _ref(_pupil(), status="Closed — no further action", outcome="No further action")
    assert r.closed_date == TODAY


# ── listing and filters ─────────────────────────────────────────────

def test_list_newest_first_and_filters():
    ava, ben = _pupil(), _pupil()
    a1 = _ref(ava, raised_date="2026-10-01", concern_type="Islamist extremism")
    a2 = _ref(ava, raised_date="2026-10-05", risk_level="High",
              referral_pathway="Police referral", **EXTERNAL)
    b1 = _ref(ben, raised_date="2026-10-03", status="Closed — supported", outcome="Supported")
    b2 = _ref(ben, raised_date="2026-10-03", status="Monitoring")
    assert [r.referral_id for r in PD.list_referrals()] == [
        a2.referral_id, b2.referral_id, b1.referral_id, a1.referral_id]

    def ids(**kw):
        return {r.referral_id for r in PD.list_referrals(**kw)}
    assert ids(pupil_id=ava.pupil_id) == {a1.referral_id, a2.referral_id}
    assert ids(status="Monitoring") == {b2.referral_id}
    assert ids(risk_level="High") == {a2.referral_id}
    assert ids(concern_type="Islamist extremism") == {a1.referral_id}
    assert ids(pathway="Police referral") == {a2.referral_id}
    assert ids(open_only=True) == {a1.referral_id, a2.referral_id, b2.referral_id}
    assert ids(from_date="2026-10-03") == {a2.referral_id, b1.referral_id, b2.referral_id}
    assert ids(to_date="2026-10-03") == {a1.referral_id, b1.referral_id, b2.referral_id}


@pytest.mark.parametrize("kw, message", [
    ({"status": "Nope"}, "Status filter must be one of"),
    ({"risk_level": "Nope"}, "Risk level filter must be one of"),
    ({"concern_type": "Nope"}, "Concern type filter must be one of"),
    ({"pathway": "Nope"}, "Pathway filter must be one of"),
    ({"from_date": "01-10-2026"}, "From date must be YYYY-MM-DD"),
    ({"to_date": "soon"}, "To date must be YYYY-MM-DD"),
])
def test_list_filter_refusals(kw, message):
    with pytest.raises(P.ValidationError, match=message):
        PD.list_referrals(**kw)


def test_empty_database():
    assert PD.list_referrals() == []
    assert PD.get(1) is None
    assert PD.delete(1) is False
    s = PD.cohort_summary()
    assert (s["total"], s["open"], s["pupils"], s["by_status"]) == (0, 0, 0, {})


# ── update, status, close, delete ───────────────────────────────────

def test_update_merges_and_revalidates():
    r = _ref(_pupil(), notes="keep")
    u = PD.update(r.referral_id, {"risk_level": "Medium", "indicators": "Drawings"})
    assert (u.risk_level, u.indicators, u.notes) == ("Medium", "Drawings", "keep")
    with pytest.raises(P.ValidationError, match="DSL must be informed for High-risk"):
        PD.update(r.referral_id, {"risk_level": "High"})
    assert PD.get(r.referral_id).risk_level == "Medium"
    with pytest.raises(P.ValidationError, match="No Prevent referral #999"):
        PD.update(999, {"notes": "x"})


def test_set_status_and_reopen_clears_closed_date():
    r = _ref(_pupil())
    with pytest.raises(P.ValidationError, match="Outcome cannot be 'Pending'"):
        PD.set_status(r.referral_id, "Closed — supported")
    closed = PD.set_status(r.referral_id, "Closed — supported", outcome="Supported")
    assert (closed.status, closed.outcome, closed.closed_date) == (
        "Closed — supported", "Supported", TODAY)
    reopened = PD.set_status(r.referral_id, "Monitoring")
    assert (reopened.status, reopened.closed_date) == ("Monitoring", None)


def test_close_referral():
    r = _ref(_pupil())
    c = PD.close_referral(r.referral_id, outcome="Diverted", closure_notes="Mentoring worked",
                          status="Closed — escalated")
    assert (c.status, c.outcome, c.closure_notes, c.closed_date) == (
        "Closed — escalated", "Diverted", "Mentoring worked", TODAY)
    default = PD.close_referral(_ref(_pupil()).referral_id, outcome="No further action")
    assert default.status == "Closed — no further action"
    with pytest.raises(P.ValidationError, match="requires a Closed status"):
        PD.close_referral(r.referral_id, outcome="Supported", status="Monitoring")
    with pytest.raises(P.ValidationError, match="Outcome must be one of"):
        PD.close_referral(r.referral_id, outcome="Sorted")


def test_delete():
    r = _ref(_pupil())
    assert PD.delete(r.referral_id) is True
    assert PD.get(r.referral_id) is None
    assert PD.delete(r.referral_id) is False


# ── cohort summary ──────────────────────────────────────────────────

def test_cohort_summary_counts():
    ava, ben = _pupil(), _pupil()
    _ref(ava, risk_level="High", referral_pathway="Channel referral (Prevent)",
         parents_informed=True, **EXTERNAL)
    _ref(ava, risk_level="Imminent", referral_pathway="Police referral", **EXTERNAL)
    _ref(ben, status="Closed — supported", outcome="Supported", raised_date="2026-10-20")
    s = PD.cohort_summary()
    assert (s["total"], s["open"], s["high_risk"]) == (3, 2, 2)
    assert (s["channel"], s["police"], s["pupils"]) == (1, 1, 2)
    assert (s["dsl_informed"], s["parents_informed"]) == (2, 1)
    assert s["by_status"] == {"Open": 2, "Closed — supported": 1}
    assert s["by_risk"] == {"High": 1, "Imminent": 1, "Low": 1}
    assert s["by_concern"] == {"Vulnerability to radicalisation": 3}
    assert s["by_pathway"] == {"Channel referral (Prevent)": 1, "Police referral": 1,
                               "Internal monitoring": 1}
    assert PD.cohort_summary(from_date="2026-10-10")["total"] == 1
    assert PD.cohort_summary(to_date="2026-10-10")["total"] == 2
