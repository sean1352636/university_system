"""Pupil premium: eligibility, funding, the spending plan, allocation and impact
(modules.finance.domain.pupil_premium) on scratch databases."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.finance.domain import pupil_premium as PP
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
KID = Principal(username="kid", role="student")
YEAR = PP.current_year()
LAST = f"{int(YEAR[:4]) - 2}/{(int(YEAR[:4]) - 1) % 100:02d}"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: [])
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(fsm=False, year=10):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": year,
        "form_group": "10C", "admission_date": "2021-09-01", "fsm_eligible": fsm},
        actor=ADMIN)


def test_eligibility_builds_on_fsm_flag_and_ever6():
    now, past, care, none = _pupil(fsm=True), _pupil(), _pupil(), _pupil()
    PP.upsert({"pupil_id": past.pupil_id, "academic_year": LAST, "category": PP.FSM},
              actor=ADMIN)
    with pytest.raises(PP.ValidationError):
        PP.upsert({"pupil_id": care.pupil_id, "category": PP.PLAC}, actor=ADMIN)  # evidence
    PP.upsert({"pupil_id": care.pupil_id, "category": PP.PLAC,
               "eligibility_source": "Adoption order"}, actor=ADMIN)
    PP.upsert({"pupil_id": care.admission_no, "category": PP.SERVICE}, actor=ADMIN)
    rows = {r["pupil"].pupil_id: r for r in PP.cohort()}
    assert set(rows) == {now.pupil_id, past.pupil_id, care.pupil_id}
    assert rows[now.pupil_id]["categories"] == [PP.FSM]        # from the pupil record
    assert rows[past.pupil_id]["categories"] == [PP.EVER6]     # FSM two years ago
    rate = PP.rates()
    # The care rate replaces the deprivation rate; the service premium is added.
    assert rows[care.pupil_id]["funding"] == rate[PP.PLAC] + rate[PP.SERVICE]
    assert PP.is_pupil_premium(past.pupil_id) and not PP.is_pupil_premium(none.pupil_id)
    assert PP.record_fsm_from_pupils(actor=ADMIN) == 1
    assert PP.record_fsm_from_pupils(actor=ADMIN) == 0
    # Withdrawn no longer counts; a record's own amount overrides the rate.
    e = PP.get_for(care.pupil_id)[0]
    PP.update(e.eligibility_id, {"funding_amount": 2000}, actor=ADMIN)
    PP.set_rate(YEAR, PP.SERVICE, 400, actor=ADMIN)
    rows = {r["pupil"].pupil_id: r for r in PP.cohort()}
    assert rows[care.pupil_id]["funding"] == 2400
    PP.update(e.eligibility_id, {"status": "Withdrawn"}, actor=ADMIN)
    assert PP.get(e.eligibility_id).end_date


def test_permissions():
    p = _pupil()
    with pytest.raises(PP.PermissionDenied):
        PP.upsert({"pupil_id": p.pupil_id, "category": PP.FSM}, actor=ANN)
    with pytest.raises(PP.PermissionDenied):
        PP.export_csv("x.csv", actor=KID)
    assert PP.cohort() == []


def test_strategy_plan_tiers_and_allocation():
    a, b, other = _pupil(fsm=True), _pupil(fsm=True), _pupil()
    with pytest.raises(PP.ValidationError):
        PP.add_line(None, {"title": "No tier"}, actor=ADMIN)
    t = PP.add_line(None, {"tier": "High-quality teaching", "title": "CPD on feedback",
                           "planned_cost": 500}, actor=ADMIN)
    tut = PP.add_line(None, {"tier": "Targeted academic support", "title": "Tutoring",
                             "planned_cost": 900}, actor=ADMIN)
    res = PP.allocate(tut.line_id, [a.pupil_id, b.pupil_id, other.pupil_id], actor=ADMIN)
    assert len(res["added"]) == 3 and res["added"][0].spend == 300
    assert [x.pupil_id for x in res["not_pp"]] == [other.pupil_id]
    assert PP.allocate(tut.line_id, [a.pupil_id], actor=ADMIN)["skipped"] == 1
    ps = PP.plan_summary()
    by = {x["tier"]: x for x in ps["tiers"]}
    assert by["Targeted academic support"]["actual"] == 900        # from the activities
    assert ps["budget"]["allocation"] == 2 * PP.rates()[PP.FSM]
    assert ps["planned"] == 1400 and not ps["warnings"]
    PP.update_line(t.line_id, {"planned_cost": 5000}, actor=ADMIN)
    assert any("more than the budget" in w for w in PP.plan_summary()["warnings"])
    with pytest.raises(PP.ValidationError):
        PP.update_line(tut.line_id, {"status": "Complete"}, actor=ADMIN)   # rate impact
    with pytest.raises(PP.ValidationError):
        PP.delete_line(tut.line_id, actor=ADMIN)                           # has pupils
    with pytest.raises(PP.ValidationError):
        PP.save_strategy(None, {"published_on": dt.date.today().isoformat()}, actor=ADMIN)
    PP.save_strategy(None, {"challenges": "Low reading ages", "intended_outcomes": "Close gap",
                            "lead": "Mrs Lead", "carried_forward": 100}, actor=ADMIN)
    assert PP.budget()["total"] == ps["budget"]["allocation"] + 100
    text = PP.strategy_text()
    assert "Low reading ages" in text and "Tutoring" in text
    nxt = PP.next_year(YEAR)
    assert PP.copy_plan(YEAR, actor=ADMIN) == 2 and len(PP.list_lines(nxt)) == 2


def test_old_interventions_and_summaries(tmp_path):
    a = _pupil()
    e = PP.upsert({"pupil_id": a.pupil_id, "category": PP.LAC,
                   "eligibility_source": "Virtual school", "keyworker": "Mr K"}, actor=ADMIN)
    act = PP.add_intervention({"pp_id": e.pp_id, "title": "Mentoring", "spend": 250},
                              actor=ADMIN)
    assert act.academic_year == YEAR and act.intervention_id == act.activity_id
    PP.update_intervention(act.activity_id, {"status": "Complete", "impact_rating": "High"},
                           actor=ADMIN)
    s = PP.record_summary(e.eligibility_id)
    assert s["total_spend"] == 250 and s["remaining"] == PP.rates()[PP.LAC] - 250
    assert s["by_impact"] == {"High": 1}
    c = PP.cohort_summary()
    assert c["total"] == 1 and c["interventions"] == 1 and c["by_category"] == {PP.LAC: 1}
    out = tmp_path / "pp.csv"
    assert PP.export_csv(out, actor=ANN) == 1
    rows = list(csv.reader(out.open()))
    assert rows[1][4] == PP.LAC and rows[1][7] == "Mr K"
    assert PP.delete_intervention(act.activity_id, actor=ADMIN)
    assert PP.delete(e.eligibility_id, actor=ADMIN)


def test_impact_reads_attendance_and_behaviour():
    pp, other = _pupil(fsm=True), _pupil()
    day = dt.date.today()
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    if day < P.academic_year_start(dt.date.today()):
        pytest.skip("no school day yet this year")
    AT.record_mark(pp.pupil_id, day, "AM", "O", actor=ADMIN)
    AT.record_mark(other.pupil_id, day, "AM", "/", actor=ADMIN)
    BH.log_incident({"pupil_id": pp.pupil_id, "incident_type": "Disruption",
                     "description": "Talking"}, actor=ADMIN)
    m = {x["measure"]: x for x in PP.impact()["measures"]}
    assert m["Attendance %"]["pp"] is not None and m["Attendance %"]["gap"] < 0
    assert m["Behaviour incidents per pupil"]["pp"] == 1 and \
        m["Behaviour incidents per pupil"]["other"] == 0
    assert m["Average Attainment 8"]["pp"] is None        # no A8 records: no figure
