"""Trips & Payments (modules.trips.domain.trips)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.trips.domain import trips as TR
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
BOB = Principal(username="bob", role="teacher")
KID = Principal(username="kid", role="student")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("bob", "Bob Teacher"))]
TODAY = dt.date.today()
LATER = TODAY + dt.timedelta(days=60)


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: LOGINS)
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "form_group": "10A", "admission_date": "2021-09-01", **extra}, actor=ADMIN)


def _trip(start=LATER, end=None, actor=ADMIN, **extra):
    data = {"title": "Science Museum", "destination": "London",
            "start_date": start.isoformat(), "end_date": (end or start).isoformat(),
            "depart_time": "08:30", "return_time": "17:00", "leader": "Ann Teacher",
            "staff": "Bob Teacher", "cost": "30.00", "capacity": "2", **extra}
    return TR.create_trip(data, actor=actor)


def _approved(**extra):
    t = _trip(**extra)
    TR.record_risk_assessment(t.trip_id, actor=ADMIN, text="Coach, museum, lunch",
                              reviewed_by="EVC", reviewed_on=TODAY.isoformat())
    TR.submit_for_approval(t.trip_id, actor=ADMIN)
    return TR.approve(t.trip_id, actor=ADMIN)


# ── Money ───────────────────────────────────────────────────────────

def test_money_is_whole_pence():
    assert TR.pence("12.50") == 1250 and TR.pence("£1,000") == 100000 and TR.pence(7) == 7
    assert TR.money(1250) == "£12.50" and TR.money(-305) == "-£3.05"
    for bad in ("1.234", "-1", "abc"):
        with pytest.raises(TR.ValidationError):
            TR.pence(bad)


# ── Trips (the old fields and rules) ─────────────────────────────────

def test_trip_fields_rules_and_old_names():
    t = TR.create_trip({"name": "Zoo", "start_date": LATER.isoformat(),
                        "cost_per_place": "12.00", "deposit": "5.00"}, actor=ADMIN)
    assert (t.title, t.name, t.cost_pence, t.deposit_pence) == ("Zoo", "Zoo", 1200, 500)
    assert t.status == "Planning" and t.approval == "draft" and t.charging == TR.VOLUNTARY
    with pytest.raises(TR.ValidationError) as e:
        TR.create_trip({"start_date": "2026-02-10", "end_date": "2026-02-01",
                        "cost": "5", "deposit": "9", "capacity": "x"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Title is required", "End date cannot be before", "Deposit cannot exceed",
                "Capacity must be a whole number"):
        assert bit in text
    with pytest.raises(TR.ValidationError) as e:
        _trip(charging="Chargeable")
    assert "needs its basis" in " ".join(e.value.problems)
    with pytest.raises(TR.ValidationError) as e:
        _trip(residential="yes")
    assert "overnight" in " ".join(e.value.problems)
    with pytest.raises(TR.ValidationError) as e:
        _trip(status="Open for Booking")
    assert "approved by the EVC" in " ".join(e.value.problems)
    assert TR.get_trip(9999) is None
    assert TR.delete_trip(t.trip_id, actor=ADMIN) and TR.get_trip(t.trip_id) is None


def test_staff_propose_but_only_the_office_decides():
    t = _trip(actor=ANN, leader="")
    assert t.leader == "Ann Teacher" and TR.is_leader(ANN, t) and not TR.is_leader(BOB, t)
    TR.update_trip(t.trip_id, {"notes": "Packed lunch"}, actor=ANN)
    with pytest.raises(TR.PermissionDenied):
        TR.update_trip(t.trip_id, {"notes": "x"}, actor=BOB)
    with pytest.raises(TR.PermissionDenied):
        TR.approve(t.trip_id, actor=ANN)
    with pytest.raises(TR.PermissionDenied):
        TR.list_trips() and TR.export_bookings_csv("x.csv", actor=KID)
    assert [x.trip_id for x in TR.trips_led_by(ANN)] == [t.trip_id]
    assert TR.list_trips(search="Science")[0].trip_id == t.trip_id   # read for all staff


def test_evc_approval_flow_and_reapproval():
    t = _trip()
    with pytest.raises(TR.ValidationError) as e:
        TR.submit_for_approval(t.trip_id, actor=ADMIN)
    assert "risk assessment" in " ".join(e.value.problems)
    TR.record_risk_assessment(t.trip_id, actor=ADMIN, text="Coach and museum")
    t = TR.submit_for_approval(t.trip_id, actor=ADMIN)
    assert t.approval == "submitted" and TR.awaiting_approval()[0].trip_id == t.trip_id
    with pytest.raises(TR.ValidationError) as e:
        TR.approve(t.trip_id, actor=ADMIN)
    assert "must be reviewed" in " ".join(e.value.problems)
    TR.record_risk_assessment(t.trip_id, actor=ADMIN, reviewed_by="EVC")
    with pytest.raises(TR.ValidationError):
        TR.decline(t.trip_id, actor=ADMIN, note="")
    t = TR.approve(t.trip_id, actor=ADMIN)
    assert t.approved
    t = TR.set_trip_status(t.trip_id, "Open for Booking", actor=ADMIN)
    # Moving the date sends it back to the EVC.
    t = TR.update_trip(t.trip_id, {"start_date": (LATER + dt.timedelta(days=1)).isoformat(),
                                   "end_date": ""}, actor=ADMIN)
    assert t.approval == "submitted"
    assert any(h["action"] == "approved" for h in TR.history(t.trip_id))


def test_schedule_deposit_instalments_and_due_by():
    t = _trip(cost="100.00", deposit="20.00", deposit_due=(TODAY - dt.timedelta(days=5)
                                                           ).isoformat(),
              payment_due=(LATER - dt.timedelta(days=7)).isoformat())
    TR.add_instalment(t.trip_id, {"label": "Second", "due_date": TODAY.isoformat(),
                                  "amount": "30"}, actor=ADMIN)
    with pytest.raises(TR.ValidationError) as e:
        TR.add_instalment(t.trip_id, {"due_date": TODAY.isoformat(), "amount": "60"},
                          actor=ADMIN)
    assert "over the cost" in " ".join(e.value.problems)
    plan = TR.schedule(t.trip_id)
    assert [x["label"] for x in plan] == ["Deposit", "Second", "Balance"]
    assert plan[-1]["cumulative_pence"] == 10000
    assert TR.due_by(t.trip_id, TODAY) == 5000
    assert TR.due_by(t.trip_id, LATER) == 10000
    assert TR.due_by(t.trip_id, LATER, remission_pence=4000) == 6000


# ── Places, waiting list, consent ────────────────────────────────────

def test_invite_capacity_waiting_list_and_promotion():
    t = _approved()
    a, b, c = _pupil(), _pupil(), _pupil(form_group="10B")
    got = TR.invite(t.trip_id, actor=ADMIN, form_group="10A")
    assert got["added"] == 2
    assert TR.invite(t.trip_id, actor=ADMIN, year_group=10)["already"] == 2
    rows = {x.pupil_id: x for x in TR.list_bookings(t.trip_id)}
    assert {x.status for x in rows.values()} == {"Interested"}
    for p in (a, b, c):
        TR.confirm_place(rows[p.pupil_id].booking_id, actor=ADMIN)
    rows = {x.pupil_id: x for x in TR.list_bookings(t.trip_id)}
    assert rows[c.pupil_id].status == "Waitlist" and TR.get(t.trip_id).places_left == 0
    with pytest.raises(TR.ValidationError) as e:
        TR.set_booking_status(rows[a.pupil_id].booking_id, "Withdrawn", actor=ADMIN)
    assert "Say why" in " ".join(e.value.problems)
    _b, promoted = TR.set_booking_status(rows[a.pupil_id].booking_id, "Withdrawn",
                                         actor=ADMIN, reason="Family moving away")
    assert promoted and promoted.pupil_id == c.pupil_id and promoted.status == "Confirmed"
    with pytest.raises(TR.ValidationError):
        TR.create_booking(t.trip_id, {"pupil_id": b.pupil_id}, actor=ADMIN)   # double booking
    with pytest.raises(TR.PermissionDenied):
        TR.invite(t.trip_id, actor=ANN, year_group=10)


def test_consent_by_leader_and_missing_list():
    t = _approved()
    p = _pupil()
    bk = TR.create_booking(t.trip_id, {"pupil_id": p.admission_no, "status": "Confirmed"},
                           actor=ADMIN)
    assert [x.booking_id for x in TR.consent_missing(t.trip_id)] == [bk.booking_id]
    with pytest.raises(TR.PermissionDenied):
        TR.record_consent(bk.booking_id, "Yes", actor=BOB)
    bk = TR.record_consent(bk.booking_id, "Yes", actor=ANN, by="Mum",
                           medical_note="Inhaler", dietary_note="Vegetarian")
    assert bk.consent_received and bk.medical_note == "Inhaler" and bk.consent_by == "Mum"
    assert TR.consent_missing(t.trip_id) == []


# ── Payments, refunds, remissions, charging policy ──────────────────

def test_payments_states_refunds_and_remission():
    t = _approved(cost="30.00", deposit="10.00")
    p = _pupil(fsm_eligible=True)
    bk = TR.create_booking(t.trip_id, {"pupil_id": p.pupil_id, "status": "Confirmed"},
                           actor=ADMIN)
    assert bk.payment_state == "Unpaid" and bk.balance_pence == 3000
    with pytest.raises(TR.ValidationError) as e:
        TR.add_payment(bk.booking_id, {"amount": "5", "method": "Cheque"}, actor=ADMIN)
    assert "needs its reference" in " ".join(e.value.problems)
    pay = TR.add_payment(bk.booking_id, {"amount": "10.00", "method": "Cash"}, actor=ADMIN)
    assert pay.received_by == "admin2" and pay.amount_pence == 1000
    assert TR.get_booking(bk.booking_id).payment_state == "Partial"
    with pytest.raises(TR.ValidationError) as e:
        TR.add_payment(bk.booking_id, {"amount": "25"}, actor=ADMIN)
    assert "more than the balance" in " ".join(e.value.problems)
    bk = TR.set_remission(bk.booking_id, "20.00", reason="Pupil premium", actor=ADMIN)
    assert bk.charge_pence == 1000 and bk.payment_state == "Paid"
    with pytest.raises(TR.ValidationError):
        TR.set_remission(bk.booking_id, "25.00", reason="Pupil premium", actor=ADMIN)
    TR.set_remission(bk.booking_id, "0", actor=ADMIN)
    pending = TR.add_payment(bk.booking_id, {"amount": "5", "status": "Pending"}, actor=ADMIN)
    assert TR.get_booking(bk.booking_id).paid_pence == 1000     # pending doesn't count
    TR.update_payment(pending.payment_id, {"status": "Cleared"}, actor=ADMIN)
    assert TR.get_booking(bk.booking_id).paid_pence == 1500
    with pytest.raises(TR.ValidationError):
        TR.refund(bk.booking_id, {"amount": "20", "notes": "x"}, actor=ADMIN)
    TR.refund(bk.booking_id, {"amount": "5", "method": "Cash", "notes": "Overpaid"},
              actor=ADMIN)
    assert TR.get_booking(bk.booking_id).paid_pence == 1000
    with pytest.raises(TR.ValidationError):
        TR.delete_booking(bk.booking_id, actor=ADMIN)       # holds money
    with pytest.raises(TR.ValidationError):
        TR.delete_trip(t.trip_id, actor=ADMIN)
    ledger = TR.pupil_ledger(p.pupil_id)
    assert ledger["paid_pence"] == 1000 and len(ledger["payments"]) == 3
    assert TR.delete_payment(pending.payment_id, actor=ADMIN)
    with pytest.raises(TR.PermissionDenied):
        TR.add_payment(bk.booking_id, {"amount": "1"}, actor=ANN)


def test_voluntary_contribution_never_excludes_but_chargeable_can():
    t = _approved()
    p = _pupil()
    bk = TR.create_booking(t.trip_id, {"pupil_id": p.pupil_id, "status": "Confirmed"},
                           actor=ADMIN)
    with pytest.raises(TR.ValidationError) as e:
        TR.set_booking_status(bk.booking_id, "Cancelled", actor=ADMIN, reason="Non-payment")
    assert "voluntary contribution" in " ".join(e.value.problems)
    ch = _approved(charging="Chargeable", charge_basis=TR.CHARGE_BASES[1])
    bk2 = TR.create_booking(ch.trip_id, {"pupil_id": p.pupil_id, "status": "Confirmed"},
                            actor=ADMIN)
    b2, _ = TR.set_booking_status(bk2.booking_id, "Cancelled", actor=ADMIN,
                                  reason="Non-payment after reminders")
    assert b2.status == "Cancelled"


def test_arrears_reminders_and_consent_requests_through_the_outbox():
    t = _approved(cost="40.00", deposit="10.00", deposit_due=TODAY.isoformat(),
                  consent_due=(LATER - dt.timedelta(days=10)).isoformat())
    p = _pupil()
    C.add_contact(p.pupil_id, {"full_name": "Mum Test", "relationship": "Mother",
                               "email": "mum@example.org"}, actor=ADMIN)
    bk = TR.create_booking(t.trip_id, {"pupil_id": p.pupil_id, "status": "Confirmed"},
                           actor=ADMIN)
    rows = TR.arrears(t.trip_id)
    assert rows and rows[0]["behind_pence"] == 1000 and rows[0]["voluntary"]
    res = TR.send_reminders(actor=ADMIN, trip_id=t.trip_id)
    assert res["emails"] == 1 and TR.get_booking(bk.booking_id).last_reminder_at
    res2 = TR.send_consent_requests(t.trip_id, actor=ADMIN)
    assert res2["emails"] == 1
    with database.connect() as conn:
        bodies = [r[0] for r in conn.execute("SELECT body FROM email_recipients")]
    assert any("voluntary" in b and "left out" in b for b in bodies)
    assert any("consent" in b for b in bodies)
    TR.add_payment(bk.booking_id, {"amount": "10"}, actor=ADMIN)
    assert TR.arrears(t.trip_id) == []
    with pytest.raises(TR.ValidationError):
        TR.send_reminders(actor=ADMIN, trip_id=t.trip_id)


# ── On the day ───────────────────────────────────────────────────────

def test_register_ratio_headcount_and_attendance_code_v():
    t = _approved(start=TODAY, capacity="")
    pupils = [_pupil() for _ in range(3)]
    for p in pupils:
        TR.create_booking(t.trip_id, {"pupil_id": p.pupil_id, "status": "Confirmed"},
                          actor=ADMIN)
    rows = TR.list_bookings(t.trip_id)
    r = TR.ratio_check(t.trip_id)
    assert r == {"pupils": 3, "staff": 2, "per_adult": 10, "needed": 1, "ok": True}
    with pytest.raises(TR.ValidationError) as e:
        TR.mark_departed(t.trip_id, [rows[0].booking_id], actor=ANN)
    assert "No consent" in " ".join(e.value.problems)
    for b in rows[:2]:
        TR.record_consent(b.booking_id, "Yes", actor=ADMIN)
    assert TR.mark_departed(t.trip_id, [b.booking_id for b in rows[:2]], actor=ANN) == 2
    with pytest.raises(TR.ValidationError):
        TR.mark_returned(t.trip_id, [rows[2].booking_id], actor=ANN)
    TR.mark_returned(t.trip_id, [rows[0].booking_id], actor=ANN)
    hc = TR.headcount(t.trip_id)
    assert (hc["places"], hc["departed"], hc["returned"]) == (3, 2, 1)
    assert [b.booking_id for b in hc["still_out"]] == [rows[1].booking_id]
    assert {b.pupil_id for b in TR.on_trip(TODAY)} == {rows[0].pupil_id, rows[1].pupil_id}
    if TODAY.weekday() < 5:
        got = TR.mark_attendance(t.trip_id, actor=ADMIN)
        assert got["saved"] == 4 and got["pupils"] == 2
        assert AT.get_for(rows[0].pupil_id, TODAY, "AM").code == "V"
        assert TR.mark_attendance(t.trip_id, actor=ADMIN)["saved"] == 0
    checks = {c["item"]: c for c in TR.readiness(t.trip_id)}
    assert checks["EVC approval"]["ok"] and not checks["Consent from every family"]["ok"]


def test_ratio_needs_two_adults_overnight():
    t = _trip(residential=1, end=LATER + dt.timedelta(days=2), staff="", capacity="")
    TR.create_booking(t.trip_id, {"pupil_id": _pupil().pupil_id, "status": "Confirmed"},
                      actor=ADMIN)
    r = TR.ratio_check(t.trip_id)
    assert r["per_adult"] == 8 and r["needed"] == 2 and not r["ok"]


# ── Families, summary, export ────────────────────────────────────────

def test_family_view_summary_and_export(tmp_path):
    t = _approved(cost="30.00")
    p = _pupil()
    bk = TR.create_booking(t.trip_id, {"pupil_id": p.pupil_id, "status": "Confirmed"},
                           actor=ADMIN)
    TR.add_payment(bk.booking_id, {"amount": "12.00"}, actor=ADMIN)
    fam = TR.for_family(p.pupil_id)
    assert fam[0]["balance"] == "£18.00" and fam[0]["consent"] == "Not given"
    s = TR.summary()
    assert s["total_paid"] == 1200 and s["total_outstanding"] == 1800
    assert s["by_method"] == {"Card": 1200}
    out = tmp_path / "b.csv"
    assert TR.export_bookings_csv(out, actor=ADMIN) == 1
    rows = list(csv.reader(out.open()))
    assert rows[0][0] == "booking" and rows[1][17] == "12.00"
    assert TR.export_payments_csv(tmp_path / "p.csv", actor=ADMIN) == 1
