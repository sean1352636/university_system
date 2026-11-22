"""Year 6 → Year 7 transition (domain.learners.pupils.year6_transition).

The secondary end is a stand-in adapter registered for ``secondary``: the
primary school reaches it only through the platform, and neither the module
nor this test imports the secondary system.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pytest

from education_system.platform.cross_system import person, transitions
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    PhaseAdapter,
)
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.learners.pupils import cross_system_adapter as CA
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils import secondary_transfer as ST
from education_system.systems.primary.domain.learners.pupils import year6_transition as Y6
from education_system.systems.primary.domain.learners.pupils.leavers import leavers as LV
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError


@dataclass
class _Enrolment(EnrolmentResult):
    email: str | None = None
    initial_password: str | None = None
    auth_user_id: int | None = None


class FakeSecondary(PhaseAdapter):
    system = "secondary"

    def __init__(self):
        super().__init__()
        self.handovers = []
        self.enrolments = 0

    def create_applicant(self, handover):
        self.handovers.append(handover)
        return ApplicantResult(local_applicant_id="S700", year_group="7")

    def create_enrolment(self, journey_id, application_id=None, **details):
        self.enrolments += 1
        return _Enrolment(local_student_id="S700", year_group="7",
                          email="s700@secondary.example", initial_password="Pw-1")


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setitem(person.SYSTEM_DB_PATHS, "primary", P.DB_PATH)
    monkeypatch.setattr(registry, "_adapters", {})
    monkeypatch.setattr(registry, "_declared", {})
    monkeypatch.setattr(registry, "_bootstrapped", True)
    CA.register()


@pytest.fixture
def secondary():
    fake = FakeSecondary()
    registry.register(fake)
    return fake


@pytest.fixture
def year():
    return Y6.current_academic_year()


@pytest.fixture
def tt(year):
    return Y6.national_timetable(year)


def _year6(first="Ben", last="Ng", **extra):
    data = {"first_name": first, "last_name": last, "year_group": "6",
            "date_of_birth": "2015-03-03", "parent_name": "Mum",
            "parent_phone": "01234 567890", "medical_notes": "Asthma", "send_status": "yes"}
    data.update(extra)
    return P.create_pupil(data)


def _all_consent(pid, year, tt, **overrides):
    consents = {k: True for k in Y6.CONSENT_FIELDS}
    consents.update(overrides)
    return Y6.set_consent(pid, year, consents, given_by="Mum",
                          given_on=tt.applications_open, method="Signed form")


def _to_accepted(pid, year, tt):
    Y6.set_destination(pid, year, Y6.DESTINATION_PLATFORM)
    Y6.record_application(pid, year, tt.application_deadline)
    Y6.record_offer(pid, year, tt.offer_day)
    return Y6.record_acceptance(pid, year, tt.reply_by)


# ── national timetable ───────────────────────────────────────────────

def test_timetable_follows_the_national_dates():
    t = Y6.national_timetable("2026-27")
    assert (t.applications_open, t.application_deadline) == ("2026-09-01", "2026-10-31")
    assert t.offer_day == "2027-03-01"          # a Monday
    assert t.reply_by == "2027-03-15"


def test_offer_day_at_a_weekend_moves_to_monday():
    assert Y6.national_timetable("2025/26").offer_day == "2026-03-02"   # 1 March is a Sunday


def test_year_spellings_normalise():
    assert Y6.normalise_year("2026/27") == Y6.normalise_year("2026-2027") == "2026-27"
    with pytest.raises(ValidationError):
        Y6.normalise_year("next year")


# ── records and cohort ───────────────────────────────────────────────

def test_cohort_is_the_year6_pupils(year):
    a, _b = _year6(), _year6("Cy", "Day")
    P.create_pupil({"first_name": "Yr", "last_name": "Five", "year_group": "5"})
    rows = Y6.cohort(year)
    assert [r.pupil.pupil_id for r in rows] == [_b.pupil_id, a.pupil_id]  # by surname
    assert all(r.record.application_status == "not_applied" for r in rows)


def test_a_non_year6_pupil_has_no_record():
    p = P.create_pupil({"first_name": "Yr", "last_name": "Five", "year_group": "5"})
    with pytest.raises(ValidationError, match="Year 6"):
        Y6.ensure_record(p.pupil_id)


# ── platform destination: staged transition ──────────────────────────

def test_choosing_the_platform_secondary_puts_the_pupil_in_its_queue(year):
    p = _year6()
    rec = Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    assert rec.destination_school == Y6.PLATFORM_DESTINATION_NAME
    queue = transitions.pending_transitions("secondary")
    assert [r["transition_id"] for r in queue] == [rec.transition_id]
    assert queue[0]["status"] == "expected" and queue[0]["source_system"] == "primary"
    assert queue[0]["effective_date"] == f"{int(year[:4]) + 1}-09-01"


def test_stages_advance_the_platform_transition(secondary, year, tt):
    p = _year6()
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    rec = Y6.record_application(p.pupil_id, year, tt.application_deadline)
    assert transitions.get_transition(rec.transition_id)["status"] == "applied"
    assert not Y6.is_late_application(rec)
    rec = Y6.record_offer(p.pupil_id, year, tt.offer_day)
    assert transitions.get_transition(rec.transition_id)["status"] == "offered"
    assert len(secondary.handovers) == 1 and secondary.handovers[0].year_group == "7"
    rec = Y6.record_acceptance(p.pupil_id, year, tt.reply_by)
    assert transitions.get_transition(rec.transition_id)["status"] == "accepted"
    assert rec.application_status == "accepted"


def test_late_application_is_flagged(year, tt):
    p = _year6()
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    late = (dt.date.fromisoformat(tt.application_deadline) + dt.timedelta(days=3)).isoformat()
    assert Y6.is_late_application(Y6.record_application(p.pupil_id, year, late))


def test_offer_rules(secondary, year, tt):
    p = _year6()
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    with pytest.raises(ValidationError, match="application before the offer"):
        Y6.record_offer(p.pupil_id, year, tt.offer_day)
    Y6.record_application(p.pupil_id, year, tt.application_deadline)
    early = (dt.date.fromisoformat(tt.offer_day) - dt.timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="national offer day"):
        Y6.record_offer(p.pupil_id, year, early)
    with pytest.raises(ValidationError, match="offer before the acceptance"):
        Y6.record_acceptance(p.pupil_id, year, tt.reply_by)


def test_application_needs_a_destination(year, tt):
    p = _year6()
    with pytest.raises(ValidationError, match="destination"):
        Y6.record_application(p.pupil_id, year, tt.application_deadline)


def test_offer_sends_only_consented_fields_and_the_report(secondary, year, tt):
    p, friend = _year6(), _year6("Cy", "Day")
    _all_consent(p.pupil_id, year, tt, send_provision=False, support_indicators=False,
                 current_interventions=False)
    Y6.save_report(p.pupil_id, year, {"strengths": "Maths", "friendships": [friend.pupil_id],
                                      "written_by": "Ms Teacher"})
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    Y6.record_application(p.pupil_id, year, tt.application_deadline)
    Y6.record_offer(p.pupil_id, year, tt.offer_day)
    payload = secondary.handovers[0].payload
    assert payload["medical_requirements"]["notes"] == "Asthma"
    assert "send_provision" not in payload
    assert payload["transition_report"]["friendships"] == ["Cy Day"]
    assert payload["transition_report"]["strengths"] == "Maths"


def test_approve_handover_needs_acceptance_and_consent(secondary, year, tt):
    p = _year6()
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    with pytest.raises(ValidationError, match="accepted"):
        Y6.approve_handover(p.pupil_id, year)
    Y6.record_application(p.pupil_id, year, tt.application_deadline)
    Y6.record_offer(p.pupil_id, year, tt.offer_day)
    Y6.record_acceptance(p.pupil_id, year, tt.reply_by)
    with pytest.raises(ValidationError, match="consent"):
        Y6.approve_handover(p.pupil_id, year)


def test_approve_handover_once_with_report_tick_and_safeguarding_pointer(secondary, year, tt):
    p = _year6()
    _all_consent(p.pupil_id, year, tt)
    Y6.save_report(p.pupil_id, year, {"written_by": "Ms Teacher"})
    sg = Y6.save_safeguarding_transfer(p.pupil_id, year, {
        "has_file": True, "sent_on": tt.induction_from, "sent_to_name": "Mr Lead",
        "method": Y6.SAFEGUARDING_METHODS[0], "recorded_by": "DSL"})
    _to_accepted(p.pupil_id, year, tt)
    rec = Y6.approve_handover(p.pupil_id, year, actor="admin3")
    row = transitions.get_transition(rec.transition_id)
    assert row["status"] == "handover_approved"
    stored = transitions.get_handover(rec.transition_id)
    assert stored["safeguarding_reference"] == sg.reference
    assert "transition_report" in stored and "send_provision" in stored
    report_item = next(i for i in row["checklist"] if i["key"] == "transition_report_sent")
    assert report_item["done"] is True
    with pytest.raises(ValidationError, match="cannot be re-approved"):
        Y6.approve_handover(p.pupil_id, year)


def test_secondary_acknowledgement_and_rejection_are_read_back(secondary, year, tt):
    a, b = _year6(), _year6("Cy", "Day")
    for p in (a, b):
        _all_consent(p.pupil_id, year, tt)
        _to_accepted(p.pupil_id, year, tt)
    Y6.approve_handover(a.pupil_id, year)
    rec_a, rec_b = Y6.get_record(a.pupil_id, year), Y6.get_record(b.pupil_id, year)
    transitions.acknowledge(rec_a.transition_id, actor_user_id=9)
    transitions.reject(rec_b.transition_id, reason="No places", actor_user_id=9)
    assert Y6.refresh_secondary_status(year) == 2
    assert Y6.get_record(a.pupil_id, year).secondary_status == "acknowledged"
    got_b = Y6.get_record(b.pupil_id, year)
    assert got_b.secondary_status == "rejected" and got_b.secondary_note == "No places"
    status = Y6.platform_status(b.pupil_id, year)
    assert status["label"] == Y6.SECONDARY_STATUS_LABELS["rejected"]
    assert "rejected" in [e["step"] for e in status["events"]]


def test_primary_can_tick_its_own_platform_items_only(year):
    p = _year6()
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    items = Y6.tick_platform_item(p.pupil_id, year, "support_meeting_held")
    assert next(i for i in items if i["key"] == "support_meeting_held")["done"] is True
    with pytest.raises(ValidationError, match="secondary school"):
        Y6.tick_platform_item(p.pupil_id, year, "documents_received")


# ── the final move continues the same transition ─────────────────────

def test_move_continues_the_open_transition(secondary, year, tt):
    p = _year6()
    _all_consent(p.pupil_id, year, tt)
    _to_accepted(p.pupil_id, year, tt)
    rec = Y6.approve_handover(p.pupil_id, year)
    result = ST.move_to_secondary_school(p.pupil_id)
    assert result.transition_id == rec.transition_id
    journey = transitions.get_transition(rec.transition_id)["journey_id"]
    assert len(transitions.list_transitions(journey)) == 1
    assert transitions.get_transition(rec.transition_id)["status"] == "completed"
    assert len(secondary.handovers) == 1              # applicant made once, at the offer
    assert result.withheld == ()                      # stored consent was used
    moved = Y6.get_record(p.pupil_id, year)
    assert moved.application_status == "moved" and moved.secondary_pupil_id == "S700"
    assert LV.get_leaver(result.leaver_id).destination_school == Y6.PLATFORM_DESTINATION_NAME


def test_move_continues_from_an_early_stage(secondary, year, tt):
    p = _year6()
    Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM)
    Y6.record_application(p.pupil_id, year, tt.application_deadline)
    tid = Y6.get_record(p.pupil_id, year).transition_id
    result = ST.move_to_secondary_school(p.pupil_id)
    assert result.transition_id == tid
    assert transitions.get_transition(tid)["status"] == "completed"


# ── external destinations ───────────────────────────────────────────

def test_external_destination_is_local_only(year, tt):
    p = _year6()
    rec = Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_EXTERNAL, "Hill Academy")
    assert rec.transition_id is None and rec.destination_school == "Hill Academy"
    Y6.record_application(p.pupil_id, year, tt.application_deadline)
    Y6.record_offer(p.pupil_id, year, tt.offer_day)
    Y6.record_acceptance(p.pupil_id, year, tt.reply_by)
    assert transitions.pending_transitions("secondary") == []
    with pytest.raises(ValidationError, match="Hill Academy"):
        ST.move_to_secondary_school(p.pupil_id)
    with pytest.raises(ValidationError, match="platform handover"):
        Y6.approve_handover(p.pupil_id, year)
    leaver_id = Y6.complete_external_move(p.pupil_id, year, tt.induction_from)
    assert LV.get_leaver(leaver_id).destination_school == "Hill Academy"
    assert P.get_pupil(p.pupil_id).roll_status == "left"
    assert Y6.get_record(p.pupil_id, year).application_status == "moved"


def test_external_needs_a_school_name(year):
    p = _year6()
    with pytest.raises(ValidationError, match="Name the external"):
        Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_EXTERNAL, " ")


def test_switching_away_from_the_platform_cancels_its_transition(year):
    p = _year6()
    tid = Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_PLATFORM).transition_id
    rec = Y6.set_destination(p.pupil_id, year, Y6.DESTINATION_EXTERNAL, "Hill Academy")
    assert rec.transition_id is None
    assert transitions.get_transition(tid)["status"] == "cancelled"


def test_decline_cancels_the_platform_transition(secondary, year, tt):
    p = _year6()
    _to_accepted(p.pupil_id, year, tt)
    tid = Y6.get_record(p.pupil_id, year).transition_id
    rec = Y6.record_decline(p.pupil_id, year, tt.reply_by, "Moving away")
    assert rec.application_status == "declined"
    assert transitions.get_transition(tid)["status"] == "cancelled"


# ── consent, report, visits, safeguarding ────────────────────────────

def test_consent_is_recorded_per_field(year, tt):
    p = _year6()
    rec = _all_consent(p.pupil_id, year, tt, medical_requirements=False)
    assert rec.consent_recorded
    assert rec.consented_fields == set(Y6.CONSENT_FIELDS) - {"medical_requirements"}
    with pytest.raises(ValidationError, match="Unknown consent"):
        Y6.set_consent(p.pupil_id, year, {"safeguarding_reference": True}, given_by="Mum",
                       given_on=tt.applications_open, method="Signed form")
    with pytest.raises(ValidationError, match="Method"):
        Y6.set_consent(p.pupil_id, year, {}, given_by="Mum", given_on=tt.applications_open,
                       method="Carrier pigeon")


def test_report_validation(year):
    p, friend, other = _year6(), _year6("Cy", "Day"), _year6("Di", "Eve")
    outsider = P.create_pupil({"first_name": "Yr", "last_name": "Five", "year_group": "5"})
    base = {"written_by": "Ms Teacher"}
    with pytest.raises(ValidationError, match="themself"):
        Y6.save_report(p.pupil_id, year, {**base, "friendships": [p.pupil_id]})
    with pytest.raises(ValidationError, match="not in the Year 6 cohort"):
        Y6.save_report(p.pupil_id, year, {**base, "friendships": [outsider.pupil_id]})
    with pytest.raises(ValidationError, match="both a friend"):
        Y6.save_report(p.pupil_id, year, {**base, "friendships": [friend.pupil_id],
                                          "keep_apart": [friend.pupil_id]})
    with pytest.raises(ValidationError, match="enhanced"):
        Y6.save_report(p.pupil_id, year, {**base, "enhanced_transition": True})
    with pytest.raises(ValidationError, match="Written by"):
        Y6.save_report(p.pupil_id, year, {})
    Y6.save_report(p.pupil_id, year, {**base, "friendships": [friend.pupil_id],
                                      "keep_apart": [other.pupil_id],
                                      "enhanced_transition": True,
                                      "enhanced_reason": "Anxious about change"})
    payload = Y6.report_payload(p.pupil_id)
    assert payload["friendships"] == ["Cy Day"] and payload["keep_apart"] == ["Di Eve"]
    assert payload["enhanced_transition"] is True and payload["written_by"] == "Ms Teacher"
    assert set(payload) == {"strengths", "interests", "learning_style", "worries",
                            "friendships", "keep_apart", "all_about_me", "teacher_comments",
                            "enhanced_transition", "enhanced_reason", "written_by",
                            "written_on"}


def test_visits_count_on_the_checklist(year, tt):
    a, b = _year6(), _year6("Cy", "Day")
    Y6.add_group_visit([a.pupil_id, b.pupil_id], year,
                       {"visit_date": tt.induction_from, "visit_type": "Induction day"})
    assert len(Y6.list_visits(year)) == 2
    item = next(i for i in Y6.checklist(a.pupil_id, year) if i.key == "visit")
    assert item.done
    v = Y6.list_visits(year, pupil_id=a.pupil_id)[0]
    Y6.update_visit(v.visit_id, {"visit_date": tt.induction_from,
                                 "visit_type": "Induction day", "attended": False})
    assert not next(i for i in Y6.checklist(a.pupil_id, year) if i.key == "visit").done
    assert Y6.delete_visit(v.visit_id)
    with pytest.raises(ValidationError, match="Visit type"):
        Y6.add_visit(a.pupil_id, year, {"visit_date": tt.induction_from, "visit_type": "Party"})


def test_safeguarding_transfer_record(year, tt):
    p = _year6()
    with pytest.raises(ValidationError, match="Name the person"):
        Y6.save_safeguarding_transfer(p.pupil_id, year, {
            "sent_on": tt.induction_from, "method": Y6.SAFEGUARDING_METHODS[0],
            "recorded_by": "DSL"})
    with pytest.raises(ValidationError, match="before the file was sent"):
        Y6.save_safeguarding_transfer(p.pupil_id, year, {
            "sent_on": tt.induction_from, "sent_to_name": "Mr Lead",
            "method": Y6.SAFEGUARDING_METHODS[0], "recorded_by": "DSL",
            "receipt_confirmed_on": tt.offer_day})
    none = Y6.save_safeguarding_transfer(p.pupil_id, year, {"has_file": False,
                                                             "recorded_by": "DSL"})
    assert not none.has_file and Y6.safeguarding_reference_for(p.pupil_id, year) is None
    assert next(i for i in Y6.checklist(p.pupil_id, year) if i.key == "safeguarding").done


# ── access ──────────────────────────────────────────────────────────

def _principal(role, *, dsl=False, superadmin=False):
    return access.Principal(username="u1", role=role, policy=access.POLICY,
                            is_dsl=dsl, is_superadmin=superadmin)


def test_year6_transition_is_a_staff_screen(monkeypatch):
    monkeypatch.setattr(access, "_is_dsl", lambda _u, _e: False)
    assert access.YEAR6_TRANSITION not in access.ADMIN_ONLY
    assert _principal("teacher").can_open(access.YEAR6_TRANSITION)
    assert not _principal("parent").can_open(access.YEAR6_TRANSITION)


def test_safeguarding_files_are_dsl_only(monkeypatch):
    monkeypatch.setattr(access, "_is_dsl", lambda _u, _e: False)
    assert not access.can_manage_year6_safeguarding_files(_principal("teacher"))
    assert not access.can_manage_year6_safeguarding_files(_principal("admin"))
    assert access.can_manage_year6_safeguarding_files(_principal("teacher", dsl=True))
    assert access.can_manage_year6_safeguarding_files(_principal("admin", superadmin=True))
    monkeypatch.setattr(access, "_is_dsl", lambda _u, _e: True)
    assert access.can_manage_year6_safeguarding_files(_principal("admin"))


def test_handover_approval_is_admin_or_dsl(monkeypatch):
    monkeypatch.setattr(access, "_is_dsl", lambda _u, _e: False)
    assert access.can_approve_year6_handover(_principal("admin"))
    assert access.can_approve_year6_handover(_principal("teacher", dsl=True))
    assert not access.can_approve_year6_handover(_principal("teacher"))
