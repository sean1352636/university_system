"""Enrichment & Clubs rules (domain.enrichment) on a scratch school DB.

auth.db (for a club leader's login) and the activity log are redirected, so
nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
COACH = Principal(username="en_coach", role="teacher")
OTHER = Principal(username="en_other", role="teacher")
TODAY = dt.date(2026, 2, 12)  # a Thursday
DOB = {y: f"{2026 - y - 4}-01-15" for y in P.YEAR_GROUPS}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(EN, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=8, **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": DOB[year], "gender": "Female", "year_group": year,
        "admission_date": "2024-09-01", **extra}, actor=ADMIN)


def _coach_login():
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.systems.secondary import SYSTEM_KEY
    UserAuth(db_path=accounts._override).provision_user(
        "en_coach", "Teach!ng-Pass-123", display_name="Mr Coach", email="coach@school.org",
        systems=[(SYSTEM_KEY, "teacher")])


def _club(name="Chess", **extra):
    data = {"name": name, "category": "Academic", "day_of_week": "Thu",
            "start_time": "15:30", "end_time": "16:30", **extra}
    return EN.create_club(data, actor=ADMIN)


# ── Clubs ────────────────────────────────────────────────────────────

def test_create_cleans_fields():
    c = _club(category="stem", day_of_week="thursday", eligible_years=[9, 8, 8],
              max_capacity="12", cost="£5", consent_required=True)
    assert (c.category, c.day_of_week, c.eligible_years, c.years, c.max_capacity, c.cost,
            c.consent_required, c.is_active) == ("STEM", "Thu", "8,9", (8, 9), 12, 5.0,
                                                 True, True)
    assert c.when == "Thu 15:30-16:30" and c.years_label == "8, 9"
    assert [h["action"] for h in EN.history(c.club_id)] == ["create"]


def test_all_years_ticked_means_all():
    c = _club(eligible_years="7,8,9,10,11")
    assert c.eligible_years is None and c.years_label == "All"


def test_create_reports_every_problem():
    with pytest.raises(EN.ValidationError) as e:
        EN.create_club({"name": "", "category": "zz", "start_time": "25:00",
                        "max_capacity": "0", "eligible_years": "6", "cost": "x"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("name", "Category", "Start time", "Capacity", "Eligible years", "Cost"):
        assert bit in text


def test_end_time_after_start():
    with pytest.raises(EN.ValidationError, match="end time"):
        _club(start_time="16:00", end_time="15:00")


def test_name_unique_ignoring_case():
    _club("Chess")
    with pytest.raises(EN.ValidationError, match="already a club"):
        _club("CHESS")


def test_only_the_enrichment_lead_sets_up_clubs():
    with pytest.raises(EN.PermissionDenied):
        EN.create_club({"name": "Chess"}, actor=COACH)
    c = _club()
    for f in (lambda: EN.update_club(c.club_id, {"room": "A1"}, actor=COACH),
              lambda: EN.toggle_active(c.club_id, actor=COACH),
              lambda: EN.delete_club(c.club_id, actor=COACH)):
        with pytest.raises(EN.PermissionDenied):
            f()


def test_leader_login_must_be_staff_and_fills_name():
    with pytest.raises(EN.ValidationError, match="staff login"):
        _club(leader_username="nobody_here")
    _coach_login()
    c = _club(leader_username="EN_COACH")
    assert (c.leader_username, c.leader) == ("en_coach", "Mr Coach")
    assert [x.name for x in EN.my_clubs(COACH)] == ["Chess"]


def test_update_records_changed_fields():
    c = _club()
    c = EN.update_club(c.club_id, {"room": "B2", "notes": "bring boards"}, actor=ADMIN)
    assert c.room == "B2"
    assert EN.history(c.club_id)[0]["detail"] == {"fields": ["notes", "room"]}
    assert EN.update_club(c.club_id, {"room": "B2"}, actor=ADMIN).updated_at == c.updated_at


def test_toggle_active():
    c = _club()
    assert EN.toggle_active(c.club_id, actor=ADMIN).is_active is False
    assert EN.list_clubs(active_only=True) == []
    assert EN.toggle_active(c.club_id, actor=ADMIN).is_active is True


def test_list_filters():
    _club("Chess", eligible_years="7")
    _club("Football", category="Sport", day_of_week="Mon")
    assert [c.name for c in EN.list_clubs(category="Sport")] == ["Football"]
    assert [c.name for c in EN.list_clubs(year_group=8)] == ["Football"]
    assert [c.name for c in EN.list_clubs(search="ches")] == ["Chess"]
    assert [c.name for c in EN.list_clubs(day="Thu")] == ["Chess"]


# ── Members ──────────────────────────────────────────────────────────

def test_join_and_waiting_list():
    c = _club(max_capacity=2)
    a, b, w = _pupil(), _pupil(), _pupil()
    assert EN.join(c.club_id, a.pupil_id, actor=ADMIN)[0].status == "Active"
    assert EN.join(c.club_id, b.pupil_id, actor=ADMIN)[0].status == "Active"
    m, warns = EN.join(c.club_id, w.pupil_id, actor=ADMIN)
    assert m.status == "Waitlisted" and "waiting list" in warns[0]
    assert EN.get_club(c.club_id).waiting == 1
    assert EN.overview()["active_memberships"] == 2


def test_join_refuses_wrong_year_inactive_and_duplicates():
    c = _club(eligible_years="9")
    p = _pupil(8)
    with pytest.raises(EN.ValidationError, match="Year 8"):
        EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    q = _pupil(9)
    EN.join(c.club_id, q.pupil_id, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="already active"):
        EN.join(c.club_id, q.pupil_id, actor=ADMIN)
    EN.toggle_active(c.club_id, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="inactive"):
        EN.join(c.club_id, _pupil(9).pupil_id, actor=ADMIN)


def test_join_refuses_future_date():
    c = _club()
    with pytest.raises(EN.ValidationError, match="future"):
        EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN, joined_on="2026-03-01")


def test_clash_is_a_warning():
    a = _club("Chess")
    b = _club("Drama", category="Drama", start_time="16:00", end_time="17:00")
    p = _pupil()
    EN.join(a.club_id, p.pupil_id, actor=ADMIN)
    _m, warns = EN.join(b.club_id, p.pupil_id, actor=ADMIN)
    assert any("Chess" in w and "same time" in w for w in warns)


def test_leaving_moves_the_waiting_list_up():
    c = _club(max_capacity=1)
    a, w = _pupil(), _pupil()
    ma, _ = EN.join(c.club_id, a.pupil_id, actor=ADMIN)
    mw, _ = EN.join(c.club_id, w.pupil_id, actor=ADMIN)
    m, moved = EN.set_status(ma.member_id, "Left", actor=ADMIN)
    assert (m.status, m.left_on) == ("Left", TODAY.isoformat())
    assert [x.member_id for x in moved] == [mw.member_id]
    assert EN.get_member(mw.member_id).status == "Active"


def test_active_needs_a_place_and_suspension_needs_a_reason():
    c = _club(max_capacity=1)
    ma, _ = EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    mw, _ = EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="capacity"):
        EN.set_status(mw.member_id, "Active", actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="why"):
        EN.set_status(ma.member_id, "Suspended", actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="Status must be"):
        EN.set_status(ma.member_id, "Gone", actor=ADMIN)


def test_capacity_cannot_drop_below_members():
    c = _club()
    for _ in range(3):
        EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="capacity"):
        EN.update_club(c.club_id, {"max_capacity": 2}, actor=ADMIN)


def test_raising_capacity_moves_the_waiting_list_up():
    c = _club(max_capacity=1)
    EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    mw, _ = EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    EN.update_club(c.club_id, {"max_capacity": 2}, actor=ADMIN)
    assert EN.get_member(mw.member_id).status == "Active"


def test_leader_runs_their_club_only():
    _coach_login()
    c = _club(leader_username="en_coach")
    other = _club("Drama")
    m, _ = EN.join(c.club_id, _pupil().pupil_id, actor=COACH)
    assert m.status == "Active"
    with pytest.raises(EN.PermissionDenied):
        EN.join(other.club_id, _pupil().pupil_id, actor=COACH)
    with pytest.raises(EN.PermissionDenied):
        EN.join(c.club_id, _pupil().pupil_id, actor=OTHER)


def test_rejoining_reuses_the_membership():
    c = _club()
    p = _pupil()
    m, _ = EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    EN.set_status(m.member_id, "Left", actor=ADMIN)
    m2, _ = EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    assert m2.member_id == m.member_id and (m2.status, m2.left_on) == ("Active", None)


def test_pupil_history():
    a, b = _club("Chess"), _club("Art", category="Arts", day_of_week="Mon")
    p = _pupil()
    EN.join(a.club_id, p.pupil_id, actor=ADMIN)
    m, _ = EN.join(b.club_id, p.pupil_id, actor=ADMIN)
    EN.set_status(m.member_id, "Left", actor=ADMIN)
    assert [(x.club_name, x.status) for x in EN.for_pupil(p.pupil_id)] == [
        ("Chess", "Active"), ("Art", "Left")]


# ── Consent and registers ────────────────────────────────────────────

def test_consent_warns_on_join_and_blocks_present():
    c = _club(consent_required=True)
    p, q = _pupil(), _pupil()
    m, warns = EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    assert any("consent" in w for w in warns)
    mq, warns_q = EN.join(c.club_id, q.pupil_id, actor=ADMIN, consent=True)
    assert mq.has_consent and not any("consent" in w for w in warns_q)
    assert [x.pupil_id for x in EN.club_summary(c.club_id)["no_consent"]] == [p.pupil_id]
    with pytest.raises(EN.ValidationError, match="consent"):
        EN.save_register(c.club_id, TODAY, {p.pupil_id: "P"}, actor=ADMIN)
    EN.save_register(c.club_id, TODAY, {p.pupil_id: "A", q.pupil_id: "P"}, actor=ADMIN)
    EN.record_consent(m.member_id, actor=ADMIN)
    EN.save_register(c.club_id, TODAY, {p.pupil_id: "P"}, actor=ADMIN)
    assert dict((x.pupil_id, mark) for x, mark in EN.register(c.club_id, TODAY)[0]) == {
        p.pupil_id: "P", q.pupil_id: "P"}


def test_register_rules():
    c = _club()
    p, outsider = _pupil(), _pupil()
    EN.join(c.club_id, p.pupil_id, actor=ADMIN, joined_on="2026-01-05")
    with pytest.raises(EN.ValidationError, match="future"):
        EN.save_register(c.club_id, TODAY + dt.timedelta(days=7), {p.pupil_id: "P"},
                         actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="isn't a member"):
        EN.save_register(c.club_id, TODAY, {outsider.pupil_id: "P"}, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="P, A or E"):
        EN.save_register(c.club_id, TODAY, {p.pupil_id: "X"}, actor=ADMIN)
    meeting, warns = EN.save_register(c.club_id, TODAY - dt.timedelta(days=1),
                                      {p.pupil_id: "P"}, actor=ADMIN)
    assert meeting.taken_by == "admin2" and any("usually meets on Thu" in w for w in warns)


def test_attendance_rate_ignores_excused():
    c = _club()
    a, b, e = _pupil(), _pupil(), _pupil()
    for p in (a, b, e):
        EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    EN.save_register(c.club_id, TODAY, {a.pupil_id: "P", b.pupil_id: "A", e.pupil_id: "E"},
                     actor=ADMIN)
    assert EN.attendance_rate(c.club_id) == 50.0
    assert EN.member_attendance(c.club_id)[e.pupil_id]["pct"] is None
    assert EN.club_summary(c.club_id)["meetings"] == 1


def test_cancelled_meeting():
    c = _club()
    p = _pupil()
    EN.join(c.club_id, p.pupil_id, actor=ADMIN, joined_on="2026-01-05")
    with pytest.raises(EN.ValidationError, match="why"):
        EN.cancel_meeting(c.club_id, TODAY, "", actor=ADMIN)
    m = EN.cancel_meeting(c.club_id, TODAY, "Snow", actor=ADMIN)
    assert m.cancelled and m.note == "Snow"
    with pytest.raises(EN.ValidationError, match="cancelled"):
        EN.save_register(c.club_id, TODAY, {p.pupil_id: "P"}, actor=ADMIN)
    day = TODAY - dt.timedelta(days=7)
    EN.save_register(c.club_id, day, {p.pupil_id: "P"}, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="taken"):
        EN.cancel_meeting(c.club_id, day, "Oops", actor=ADMIN)


def test_registers_protect_members_and_clubs():
    c = _club()
    p = _pupil()
    m, _ = EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    EN.save_register(c.club_id, TODAY, {p.pupil_id: "P"}, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="Left instead"):
        EN.delete_member(m.member_id, actor=ADMIN)
    with pytest.raises(EN.ValidationError, match="inactive instead"):
        EN.delete_club(c.club_id, actor=ADMIN)


def test_delete_member_and_club_without_registers():
    c = _club()
    m, _ = EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    EN.delete_member(m.member_id, actor=ADMIN)
    assert EN.list_members(c.club_id) == []
    EN.join(c.club_id, _pupil().pupil_id, actor=ADMIN)
    EN.delete_club(c.club_id, actor=ADMIN)
    with pytest.raises(EN.NotFound):
        EN.get_club(c.club_id)


# ── Reports ──────────────────────────────────────────────────────────

def test_participation_counts_fsm_and_active_clubs_only():
    c = _club()
    fsm_in, fsm_out, other = _pupil(fsm_eligible=True), _pupil(fsm_eligible=True), _pupil()
    EN.join(c.club_id, fsm_in.pupil_id, actor=ADMIN)
    r = EN.participation()
    assert (r["pupils"], r["taking_part"], r["fsm_pct"]) == (3, 1, 50.0)
    assert {p.pupil_id for p in r["not_in_a_club"]} == {fsm_out.pupil_id, other.pupil_id}
    EN.toggle_active(c.club_id, actor=ADMIN)
    assert EN.participation()["taking_part"] == 0


def test_timetable_groups_by_day_in_time_order():
    _club("Late", start_time="16:30", end_time="17:30")
    _club("Early", start_time="12:30", end_time="13:00")
    _club("Footy", category="Sport", day_of_week="Mon")
    tt = EN.timetable()
    assert list(tt) == ["Mon", "Thu"]
    assert [c.name for c in tt["Thu"]] == ["Early", "Late"]


def test_export_escapes_formulas(tmp_path):
    c = _club()
    p = _pupil()
    m, _ = EN.join(c.club_id, p.pupil_id, actor=ADMIN, notes="=HYPERLINK(1)")
    path = tmp_path / "club.csv"
    assert EN.export_members(c.club_id, path, actor=ADMIN) == 1
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert rows[0][0] == "Admission no" and rows[1][-1] == "'=HYPERLINK(1)"


def test_notify_families_writes_to_the_outbox():
    c = _club()
    p = _pupil()
    EN.join(c.club_id, p.pupil_id, actor=ADMIN)
    with pytest.raises(EN.ValidationError):
        EN.notify_families(_club("Empty").club_id, "Hi", "Hello", actor=ADMIN)
    C.add_contact(p.pupil_id, {"full_name": "Parent", "relationship": "Mother",
                               "email": "parent@example.org", "receives_email": True,
                               "parental_responsibility": True}, actor=ADMIN)
    subject, body = EN.cancellation_text(c, TODAY, "Snow")
    result = EN.notify_families(c.club_id, subject, body, actor=ADMIN)
    assert result.recipients == 1 and "Snow" in body
    assert EN.history(c.club_id)[0]["action"] == "notify"
