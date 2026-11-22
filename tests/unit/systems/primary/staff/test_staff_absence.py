"""Daily staff absence tracker (systems.primary.domain.staff.staff_absence.staff_absence)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.staff_absence import staff_absence as SA

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _staff(first="Amy", last="Adams"):
    return S.create_staff({"first_name": first, "last_name": last})


def _absence(staff_id, date=None, **extra):
    return SA.create_absence({"staff_id": staff_id, "absence_date": date or _d(0),
                              "absence_type": "Sickness", **extra})


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_read_back():
    s = _staff()
    a = _absence(s.staff_id, "2026-11-02", reason=" flu ", days_lost="2.5")
    assert (a.absence_date, a.absence_type, a.reason, a.days_lost) == (
        "2026-11-02", "Sickness", "flu", 2.5)
    assert (a.notification_method, a.certificate_type, a.cover_source, a.status) == (
        "Phone Call", "Self-Cert", "Pending", "Reported")
    assert (a.cover_required, a.critical, a.parents_informed, a.rtw_required) == (
        False, False, False, False)
    assert a.is_open is True and a.is_active is False
    assert SA.get_absence(a.absence_id) == a
    assert SA.get_absence(999) is None


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"absence_date": ""}, "Absence date is required"),
    ({"absence_date": "02/11/2026"}, "Absence date must be YYYY-MM-DD"),
    ({"expected_return": "x"}, "Expected return must be YYYY-MM-DD"),
    ({"actual_return": "x"}, "Actual return must be YYYY-MM-DD"),
    ({"notified_on": "x"}, "Notified on must be YYYY-MM-DD"),
    ({"cert_received_on": "x"}, "Cert received must be YYYY-MM-DD"),
    ({"rtw_meeting_on": "x"}, "RTW meeting must be YYYY-MM-DD"),
    ({"expected_return": "2026-11-01"}, "Expected return must be on or after absence date"),
    ({"actual_return": "2026-11-01"}, "Actual return must be on or after absence date"),
    ({"absence_type": "Holiday"}, "Absence type must be one of"),
    ({"notification_method": "Carrier pigeon"}, "Notification method must be one of"),
    ({"certificate_type": "Note from mum"}, "Certificate type must be one of"),
    ({"cover_source": "Parent"}, "Cover source must be one of"),
    ({"status": "Away"}, "Status must be one of"),
    ({"days_lost": "two"}, "Days lost must be a number"),
    ({"days_lost": -1}, "Days lost must be >= 0"),
])
def test_create_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, "absence_date": "2026-11-02", "absence_type": "Sickness",
            **bad}
    with pytest.raises(SA.ValidationError, match=msg):
        SA.create_absence(data)
    assert SA.list_absences() == []


# ── Derived flags ────────────────────────────────────────────────────

def test_cover_outstanding_flag():
    s = _staff()
    assert _absence(s.staff_id, cover_required=True).cover_outstanding is True
    assert _absence(s.staff_id, cover_required=True,
                    cover_source="Internal").cover_outstanding is False
    assert _absence(s.staff_id, cover_required=False).cover_outstanding is False
    assert _absence(s.staff_id, cover_required=True,
                    status="Closed").cover_outstanding is False


def test_return_overdue_flag():
    s = _staff()
    assert _absence(s.staff_id, _d(-5), expected_return=_d(-1)).return_overdue is True
    assert _absence(s.staff_id, _d(-5), expected_return=_d(0)).return_overdue is False
    assert _absence(s.staff_id, _d(-5), expected_return=_d(-1),
                    status="Returned").return_overdue is False


def test_rtw_overdue_after_seven_days():
    s = _staff()
    overdue = _absence(s.staff_id, _d(-20), actual_return=_d(-8), status="Returned",
                       rtw_required=True)
    on_time = _absence(s.staff_id, _d(-20), actual_return=_d(-7), status="Returned",
                       rtw_required=True)
    held = _absence(s.staff_id, _d(-20), actual_return=_d(-10), status="Returned",
                    rtw_required=True, rtw_meeting_on=_d(-9))
    not_needed = _absence(s.staff_id, _d(-20), actual_return=_d(-10), status="Returned")
    assert overdue.rtw_overdue is True
    assert on_time.rtw_overdue is False
    assert held.rtw_overdue is False
    assert not_needed.rtw_overdue is False
    assert [a.absence_id for a in SA.list_absences(rtw_overdue=True)] == [overdue.absence_id]


# ── Update / delete ──────────────────────────────────────────────────

def test_update_and_delete():
    s = _staff()
    a = _absence(s.staff_id, "2026-11-02")
    up = SA.update_absence(a.absence_id, {"staff_id": s.staff_id, "absence_date": "2026-11-03",
                                          "absence_type": "Bereavement"})
    assert (up.absence_date, up.absence_type) == ("2026-11-03", "Bereavement")
    with pytest.raises(SA.ValidationError, match="No absence with id 999"):
        SA.update_absence(999, {"staff_id": s.staff_id})
    assert SA.delete_absence(a.absence_id) is True
    assert SA.delete_absence(a.absence_id) is False


def test_staff_delete_cascades():
    s = _staff()
    a = _absence(s.staff_id)
    S.delete_staff(s.staff_id)
    assert SA.get_absence(a.absence_id) is None


# ── Workflow ─────────────────────────────────────────────────────────

def test_confirm_moves_reported_absence_on():
    s = _staff()
    a = _absence(s.staff_id)
    out = SA.confirm_absence(a.absence_id)
    assert out.status == "Active" and out.is_active
    with pytest.raises(SA.ValidationError, match="No absence with id 999"):
        SA.confirm_absence(999)


def test_confirming_an_active_absence_does_not_move_it_backwards():
    """Statuses run Reported → Confirmed → Active; confirming an absence
    that is already Active must not drop it back to Confirmed."""
    s = _staff()
    a = _absence(s.staff_id, status="Active")
    assert SA.confirm_absence(a.absence_id).status == "Active"


def test_arrange_cover():
    s = _staff()
    a = _absence(s.staff_id, cover_required=True)
    out = SA.arrange_cover(a.absence_id, source="Supply Agency", arranged_by="Office",
                           notes="Ms Supply")
    assert (out.cover_source, out.cover_arranged_by, out.cover_notes) == (
        "Supply Agency", "Office", "Ms Supply")
    assert out.cover_outstanding is False
    with pytest.raises(SA.ValidationError, match="Cover source must be one of"):
        SA.arrange_cover(a.absence_id, source="Parent helper")
    with pytest.raises(SA.ValidationError, match="No absence with id 999"):
        SA.arrange_cover(999, source="Internal")


def test_record_return_days_lost():
    s = _staff()
    a = _absence(s.staff_id, "2026-11-02")
    out = SA.record_return(a.absence_id, returned_on="2026-11-09")
    assert (out.actual_return, out.days_lost, out.status) == ("2026-11-09", 7.0, "Returned")
    same_day = _absence(s.staff_id, "2026-11-04")
    assert SA.record_return(same_day.absence_id, returned_on="2026-11-04").days_lost == 1.0
    given = _absence(s.staff_id, "2026-11-02")
    assert SA.record_return(given.absence_id, returned_on="2026-11-09",
                            days_lost=5).days_lost == 5.0
    today = _absence(s.staff_id, _d(-3))
    out = SA.record_return(today.absence_id)
    assert (out.actual_return, out.days_lost) == (_d(0), 3.0)
    with pytest.raises(SA.ValidationError, match="Actual return must be on or after"):
        SA.record_return(a.absence_id, returned_on="2026-10-01")


def test_complete_rtw_close_cancel_set_status():
    s = _staff()
    a = _absence(s.staff_id, "2026-11-02", rtw_required=True)
    with pytest.raises(SA.ValidationError, match="Completed-by is required"):
        SA.complete_rtw(a.absence_id, completed_by="")
    rtw = SA.complete_rtw(a.absence_id, completed_by="Head", meeting_on="2026-11-10")
    assert (rtw.rtw_completed_by, rtw.rtw_meeting_on) == ("Head", "2026-11-10")
    assert SA.complete_rtw(a.absence_id, completed_by="Head").rtw_meeting_on == _d(0)
    closed = SA.close_absence(a.absence_id)
    assert closed.status == "Closed" and closed.is_open is False
    assert SA.cancel_absence(a.absence_id).status == "Cancelled"
    assert SA.set_status(a.absence_id, "Confirmed").status == "Confirmed"
    with pytest.raises(SA.ValidationError, match="Status must be one of"):
        SA.set_status(a.absence_id, "Gone")


def test_workflow_helpers_refuse_missing():
    calls = (
        lambda: SA.record_return(404),
        lambda: SA.complete_rtw(404, completed_by="x"),
        lambda: SA.close_absence(404),
        lambda: SA.cancel_absence(404),
        lambda: SA.set_status(404, "Closed"),
    )
    for call in calls:
        with pytest.raises(SA.ValidationError, match="No absence with id 404"):
            call()


# ── Listing ──────────────────────────────────────────────────────────

def test_list_filters_and_order():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    today = _absence(a.staff_id, _d(0), cover_required=True, critical=True)
    past = _absence(b.staff_id, _d(-10), expected_return=_d(-2), status="Confirmed",
                    absence_type="Jury Service", cover_source="Internal")
    done = _absence(a.staff_id, _d(-5), actual_return=_d(-3), status="Returned")
    future = _absence(b.staff_id, _d(3), absence_type="Hospital Appointment")
    ids = lambda rows: [x.absence_id for x in rows]  # noqa: E731
    assert ids(SA.list_absences()) == [future.absence_id, today.absence_id, done.absence_id,
                                       past.absence_id]
    assert ids(SA.list_absences(staff_id=a.staff_id)) == [today.absence_id, done.absence_id]
    assert ids(SA.absences_for_staff(b.staff_id)) == [future.absence_id, past.absence_id]
    assert ids(SA.list_absences(absence_type="Jury Service")) == [past.absence_id]
    assert ids(SA.list_absences(status="Returned")) == [done.absence_id]
    assert ids(SA.list_absences(cover_source="Internal")) == [past.absence_id]
    assert ids(SA.list_absences(open_only=True)) == [future.absence_id, today.absence_id,
                                                     past.absence_id]
    assert ids(SA.list_absences(active_today=True)) == [today.absence_id, past.absence_id]
    assert ids(SA.list_absences(critical_only=True)) == [today.absence_id]
    assert ids(SA.list_absences(cover_outstanding=True)) == [today.absence_id]
    assert ids(SA.list_absences(return_overdue=True)) == [past.absence_id]
    assert ids(SA.list_absences(date_from=_d(-5), date_to=_d(0))) == [today.absence_id,
                                                                      done.absence_id]
    with pytest.raises(SA.ValidationError, match="From must be YYYY-MM-DD"):
        SA.list_absences(date_from="last week")


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = SA.summary()
    assert (sm.total, sm.total_days_lost, sm.distinct_staff) == (0, 0.0, 0)


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    _absence(a.staff_id, _d(0), cover_required=True, critical=True, parents_informed=True)
    _absence(a.staff_id, _d(-10), expected_return=_d(-1), days_lost=8)          # self-cert > 7
    _absence(b.staff_id, _d(-12), days_lost=9, certificate_type="Medical Cert",
             cover_source="Internal", cover_required=True, parents_informed=True)
    _absence(b.staff_id, _d(-30), actual_return=_d(-20), status="Returned", rtw_required=True,
             days_lost=10.25, absence_type="Bereavement")
    _absence(b.staff_id, _d(3), parents_informed=True)                          # not yet begun
    sm = SA.summary()
    assert (sm.total, sm.open_count, sm.active_today) == (5, 4, 3)
    assert (sm.cover_outstanding, sm.critical_open, sm.return_overdue) == (1, 1, 1)
    assert (sm.awaiting_cert, sm.parents_pending, sm.rtw_overdue) == (1, 1, 1)
    assert sm.distinct_staff == 2
    assert sm.total_days_lost == 27.2                    # 8 + 9 + 10.25 = 27.25 → 1 dp
    assert sm.by_type == {"Sickness": 4, "Bereavement": 1}
    assert sm.by_status == {"Reported": 4, "Returned": 1}
    assert sm.by_cover_source == {"Pending": 4, "Internal": 1}
