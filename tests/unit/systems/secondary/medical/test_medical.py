"""Medical: conditions, allergies, medicines, doses, first aid and emergencies
(modules.medical.domain.medical) on scratch databases."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.medical.domain import medical as M
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
KID = Principal(username="kid", role="student")
TODAY = dt.date.today()


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


def _pupil(year=10):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Male", "year_group": year,
        "form_group": f"{year}B", "admission_date": "2021-09-01"}, actor=ADMIN)


def _medicine(p, **extra):
    return M.add_medicine({"pupil_id": p.pupil_id, "name": "Salbutamol", "form": "Inhaler",
                           "dose": "2 puffs", "location": "Office cupboard", "quantity": 3,
                           "expiry_date": (TODAY + dt.timedelta(days=200)).isoformat(),
                           "consent_on": TODAY.isoformat(), "consent_by": "Mum", **extra},
                          actor=ADMIN)


def test_conditions_ihp_and_the_care_list():
    ava = _pupil()
    with pytest.raises(M.ValidationError) as e:
        M.add_condition({"pupil_id": ava.pupil_id, "condition": "Epilepsy",
                         "severity": "Life-threatening", "emergency_medication": "Midazolam"},
                        actor=ADMIN)
    text = " ".join(e.value.problems)
    assert "what to do" in text and "where the emergency medication" in text
    c = M.add_condition({"pupil_id": ava.pupil_id, "condition": "Epilepsy",
                         "severity": "Life-threatening", "what_to_do": "Time it; 999 at 5 min",
                         "emergency_medication": "Buccal midazolam",
                         "medication_location": "Office", "has_ihp": True}, actor=ADMIN)
    assert c.ihp_review_date == M.add_months(TODAY, 12).isoformat()
    with pytest.raises(M.PermissionDenied):
        M.add_condition({"pupil_id": ava.pupil_id, "condition": "Asthma"}, actor=ANN)
    M.add_allergy({"pupil_id": ava.pupil_id, "allergen": "Peanut", "anaphylaxis": True,
                   "auto_injector": True, "action": "Auto-injector, call 999"}, actor=ADMIN)
    rows = M.care_list(actor=ANN)                     # every member of staff
    assert rows[0]["worst"] == "Life-threatening" and rows[0]["anaphylaxis"]
    assert "Buccal midazolam - Office" in rows[0]["medication"]
    assert any("Peanut allergy" in x for x in rows[0]["what_to_do"])
    with pytest.raises(M.PermissionDenied):
        M.care_list(actor=KID)
    c = M.review_ihp(c.condition_id, actor=ADMIN, reviewed_on=TODAY.isoformat(), note="Same")
    assert "IHP reviewed" in c.notes
    soon = M.update_condition(c.condition_id, {"ihp_review_date": (
        TODAY + dt.timedelta(days=5)).isoformat()}, actor=ADMIN)
    assert any(d["ref"] == f"condition:{soon.condition_id}" for d in M.due())


def test_allergy_list_for_a_trip():
    a, b = _pupil(), _pupil()
    al = M.add_allergy({"pupil_id": a.pupil_id, "allergen": "Milk", "severity": "Mild"},
                       actor=ADMIN)
    assert al.dietary == "No Milk"
    M.add_allergy({"pupil_id": b.pupil_id, "allergen": "Wasp", "kind": "Insect sting",
                   "anaphylaxis": True, "action": "Auto-injector"}, actor=ADMIN)
    trip = M.allergy_list(actor=ANN, pupil_ids=[a.pupil_id])
    assert [r["allergen"] for r in trip] == ["Milk"]
    assert M.get_allergy(al.allergy_id).severity == "Mild"
    assert len(M.allergy_list(actor=ANN)) == 2


def test_medicines_consent_expiry_doses_and_stock():
    ava = _pupil()
    with pytest.raises(M.ValidationError) as e:
        M.add_medicine({"pupil_id": ava.pupil_id, "name": "Calpol", "dose": "5ml",
                        "location": "Office", "expiry_date": "2020-01-01"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    assert "expired" in text and "consent" in text
    with pytest.raises(M.ValidationError):
        _medicine(ava, controlled=True, location="Office shelf")     # not locked
    m = _medicine(ava, emergency=True)
    with pytest.raises(M.ValidationError):
        M.give_dose({"medicine_id": m.medicine_id, "given_by": "Ms Aid"}, actor=ADMIN)
    d = M.give_dose({"medicine_id": m.medicine_id, "given_by": "Ms Aid",
                     "consent_checked": True}, actor=ADMIN)
    assert d.dose == "2 puffs" and M.get_medicine(m.medicine_id).quantity == 2
    assert any("Low stock" in x["item"] for x in M.due())
    # Emergency use without the check is allowed for emergency medication.
    M.give_dose({"medicine_id": m.medicine_id, "given_by": "Ms Aid", "emergency": True},
                actor=ADMIN)
    assert len(M.doses_today(ava.pupil_id)) == 2
    assert M.delete_dose(d.dose_id, actor=ADMIN, reason="Entered twice")
    assert M.get_medicine(m.medicine_id).quantity == 2
    with pytest.raises(M.ValidationError):
        M.delete_medicine(m.medicine_id, actor=ADMIN)          # doses given: keep it
    # Controlled drug needs a witness.
    cd = _medicine(ava, name="Methylphenidate", controlled=True,
                   location="Locked cupboard, office")
    with pytest.raises(M.ValidationError) as e:
        M.give_dose({"medicine_id": cd.medicine_id, "given_by": "Ms Aid",
                     "consent_checked": True}, actor=ADMIN)
    assert "witness" in " ".join(e.value.problems)
    # Expiring medicine: on the list, and the family asked to replace it.
    old = M.update_medicine(cd.medicine_id, {"expiry_date": (
        TODAY + dt.timedelta(days=10)).isoformat()}, actor=ADMIN)
    assert old.expiring and old in M.expiring()
    C.add_contact(ava.pupil_id, {"full_name": "Dad Test", "relationship": "Father",
                                 "email": "dad@example.org"}, actor=ADMIN)
    assert M.ask_for_replacement(old.medicine_id, actor=ADMIN)["emails"] == 1
    gone = M.return_medicine(old.medicine_id, actor=ADMIN, disposed=True)
    assert gone.status == "Disposed" and gone not in M.list_medicines()
    assert M.dose_report()[0]["doses"] >= 1


def test_first_aid_riddor_and_family():
    ava = _pupil()
    data = {"pupil_id": ava.pupil_id, "location": "Field", "injury_type": "Head injury",
            "description": "Collided in football", "treatment": "Ice pack",
            "treated_by": "Ms Aid", "outcome": "Ambulance called"}
    warn = " ".join(M.check_incident(data))
    assert "Tell the parents" in warn and "RIDDOR" in warn
    i = M.create_incident({**data, "riddor_reportable": True}, actor=ADMIN)
    assert i.hospital_referral and i.riddor_due == (TODAY + dt.timedelta(days=10)).isoformat()
    assert [x.incident_id for x in M.riddor_outstanding()] == [i.incident_id]
    with pytest.raises(M.ValidationError):
        M.record_riddor(i.incident_id, actor=ADMIN)               # needs the reference
    i = M.record_riddor(i.incident_id, actor=ADMIN, reference="HSE-123")
    assert not M.riddor_outstanding()
    with pytest.raises(M.ValidationError):
        M.delete_incident(i.incident_id, actor=ADMIN)             # reported: keep it
    staff = M.create_incident({"person_type": "Staff", "person_name": "Mr Tea",
                               "location": "Staff room", "injury_type": "Burn/Scald",
                               "description": "Kettle", "treatment": "Cold water",
                               "treated_by": "Ms Aid"}, actor=ADMIN)
    assert staff.pupil_id is None and "staff" in staff.who
    with pytest.raises(M.ValidationError):
        M.notify_parents(staff.incident_id, actor=ADMIN)
    C.add_contact(ava.pupil_id, {"full_name": "Mum Test", "relationship": "Mother",
                                 "email": "mum@example.org"}, actor=ADMIN)
    assert M.notify_parents(i.incident_id, actor=ADMIN)["emails"] == 1
    i = M.get_incident(i.incident_id)
    assert i.parent_contacted and i.parent_contact_how == "E-mail"
    s = M.first_aid_summary()
    assert s["total"] == 2 and s["hospital"] == 1 and s["pupils"] == 1
    assert len(M.list_incidents(hospital_only=True)) == 1


def test_emergencies_and_drills():
    with pytest.raises(M.ValidationError) as e:
        M.create_emergency({"kind": "Real", "missing_count": 1, "status": "Closed"},
                           actor=ADMIN)
    assert "missing" in " ".join(e.value.problems)
    ev = M.create_emergency({"kind": "Drill", "event_type": "Fire", "start_time": "10:00",
                             "end_time": "10:09", "pupils_evacuated": 600,
                             "status": "Actions outstanding",
                             "follow_up_actions": "Fix the bell in block C"}, actor=ADMIN)
    assert ev.duration_min == 9
    assert M.drills_this_term()["this_term"]
    assert any(d["ref"] == f"emergency:{ev.event_id}" for d in M.due())
    assert M.close_emergency(ev.event_id, actor=ADMIN).status == "Closed"
    s = M.emergency_summary()
    assert s["drills"] == 1 and s["avg_duration_min"] == 9.0
    assert M.delete_emergency(ev.event_id, actor=ADMIN)


def test_exports_and_no_conditions_in_the_log(tmp_path):
    ava = _pupil()
    M.add_condition({"pupil_id": ava.pupil_id, "condition": "Diabetes (type 1)",
                     "severity": "Severe", "what_to_do": "Check sugar"}, actor=ADMIN)
    M.add_allergy({"pupil_id": ava.pupil_id, "allergen": "Sesame"}, actor=ADMIN)
    out = tmp_path / "care.csv"
    assert M.export_care_list(out, actor=ANN) == 1
    assert "Diabetes" in out.read_text()
    assert M.export_allergy_list(tmp_path / "a.csv", actor=ANN) == 1
    M.create_incident({"pupil_id": ava.pupil_id, "location": "Hall", "description": "Trip",
                       "treatment": "Plaster", "treated_by": "X"}, actor=ADMIN)
    assert M.export_first_aid(tmp_path / "f.csv", actor=ANN) == 1
    assert list(csv.reader((tmp_path / "f.csv").open()))[0][0] == "id"
    log = activity_log.log_path().read_text()
    assert "Diabetes" not in log and "Sesame" not in log
    assert any(h["item"] == "condition" for h in M.history(ava.pupil_id))
