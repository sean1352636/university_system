"""Tests for the escalation ladder, contracts and meetings.

Nothing escalates itself: :func:`suggest_stage` says what the ladder
implies, but moving a case is always somebody's decision with their name
on it.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_escalation as escalation,
)


def mark_percentage(attdb, student_id: str, *, attended: int,
                    total: int) -> None:
    monday = _dt.date.fromisoformat(attdb.prev_monday)
    for index in range(total):
        date = (monday - _dt.timedelta(days=index)).isoformat()
        core.save_register(attdb.slot, date,
                           {student_id: {"code": "/" if index < attended
                                         else "O"}}, allow_retro=True)


# ── 1. Cases ───────────────────────────────────────────────────────

class TestCases:

    def test_a_case_can_be_opened(self, attdb):
        case = escalation.open_case(attdb.s1, owner="Mr Patel",
                                    opened_by="head")
        assert case.state == escalation.OPEN
        assert case.stage == escalation.TUTOR_CONVERSATION
        assert case.review_on is not None

    def test_opening_twice_returns_the_same_case(self, attdb):
        first = escalation.open_case(attdb.s1)
        second = escalation.open_case(attdb.s1)
        assert first.case_id == second.case_id

    def test_an_unknown_learner_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="No student"):
            escalation.open_case("NOPE")

    def test_the_baseline_figure_is_captured(self, attdb):
        mark_percentage(attdb, attdb.s1, attended=8, total=10)
        case = escalation.open_case(attdb.s1)
        assert case.baseline_pct == 80.0

    def test_opening_is_logged_as_a_stage(self, attdb):
        case = escalation.open_case(attdb.s1, opened_by="head")
        history = escalation.stage_history(case.case_id)
        assert history[0].note == "Case opened"

    def test_the_ladder_suggests_without_acting(self, attdb):
        mark_percentage(attdb, attdb.s1, attended=4, total=10)   # 40%
        assert escalation.suggest_stage(attdb.s1) == escalation.REFERRAL
        assert escalation.list_cases() == []

    def test_a_healthy_learner_suggests_nothing(self, attdb):
        mark_percentage(attdb, attdb.s1, attended=10, total=10)
        assert escalation.suggest_stage(attdb.s1) is None


# ── 2. Escalating ──────────────────────────────────────────────────

class TestEscalating:

    def test_escalation_climbs_one_rung(self, attdb):
        case = escalation.open_case(attdb.s1)
        out = escalation.escalate(case.case_id, actor="head")
        assert out.stage == escalation.TUTOR_MEETING

    def test_escalation_can_name_a_stage(self, attdb):
        case = escalation.open_case(attdb.s1)
        out = escalation.escalate(case.case_id, to=escalation.FORMAL_REVIEW,
                                  actor="head")
        assert out.stage == escalation.FORMAL_REVIEW

    def test_escalation_cannot_go_downwards(self, attdb):
        case = escalation.open_case(attdb.s1,
                                    stage=escalation.FORMAL_REVIEW)
        with pytest.raises(core.ValidationError, match="use set_stage"):
            escalation.escalate(case.case_id, to=escalation.TUTOR_MEETING)

    def test_the_top_of_the_ladder_cannot_escalate(self, attdb):
        case = escalation.open_case(attdb.s1, stage=escalation.REFERRAL)
        with pytest.raises(core.ValidationError, match="top of the ladder"):
            escalation.escalate(case.case_id)

    def test_de_escalation_is_possible_deliberately(self, attdb):
        # A learner who recovers should visibly come back down.
        case = escalation.open_case(attdb.s1,
                                    stage=escalation.FORMAL_REVIEW)
        out = escalation.set_stage(case.case_id,
                                   escalation.TUTOR_CONVERSATION,
                                   actor="head", note="Attendance recovered")
        assert out.stage == escalation.TUTOR_CONVERSATION

    def test_every_move_is_logged(self, attdb):
        case = escalation.open_case(attdb.s1)
        escalation.escalate(case.case_id, actor="head")
        escalation.escalate(case.case_id, actor="head")
        assert len(escalation.stage_history(case.case_id)) == 3

    def test_a_closed_case_cannot_escalate(self, attdb):
        case = escalation.open_case(attdb.s1)
        escalation.close_case(case.case_id, outcome="Improved",
                              closed_by="head")
        with pytest.raises(core.ValidationError, match="closed"):
            escalation.escalate(case.case_id)

    def test_closing_needs_an_outcome(self, attdb):
        case = escalation.open_case(attdb.s1)
        with pytest.raises(core.ValidationError, match="needs an outcome"):
            escalation.close_case(case.case_id, outcome="  ")


# ── 3. Reviews ─────────────────────────────────────────────────────

class TestReviews:

    def test_an_overdue_case_is_listed(self, attdb):
        case = escalation.open_case(attdb.s1)
        yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        escalation.set_review(case.case_id, yesterday)
        overdue = escalation.overdue_reviews()
        assert [c.case_id for c in overdue] == [case.case_id]
        assert overdue[0].student_name == "Ada Test"

    def test_a_case_inside_its_review_date_is_not(self, attdb):
        escalation.open_case(attdb.s1)
        assert escalation.overdue_reviews() == []

    def test_a_closed_case_is_never_overdue(self, attdb):
        case = escalation.open_case(attdb.s1)
        yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        escalation.set_review(case.case_id, yesterday)
        escalation.close_case(case.case_id, outcome="Done", closed_by="head")
        assert escalation.overdue_reviews() == []

    def test_a_caseload_is_readable(self, attdb):
        escalation.open_case(attdb.s1, owner="Mr Patel")
        escalation.open_case(attdb.s2, owner="Mr Patel")
        assert len(escalation.caseload("Mr Patel")) == 2

    def test_open_cases_are_counted_by_stage(self, attdb):
        escalation.open_case(attdb.s1)
        escalation.open_case(attdb.s2, stage=escalation.FORMAL_REVIEW)
        counts = escalation.stage_counts()
        assert counts[escalation.TUTOR_CONVERSATION] == 1
        assert counts[escalation.FORMAL_REVIEW] == 1


# ── 4. Contracts ───────────────────────────────────────────────────

class TestContracts:

    def test_a_contract_can_be_agreed(self, attdb):
        contract = escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.next_monday,
            terms="Attend every lesson",
            support="Bus pass and a weekly check-in")
        assert contract.state == escalation.ACTIVE
        assert contract.support is not None

    def test_a_nonsense_target_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="between 1 and 100"):
            escalation.create_contract(attdb.s1, target_pct=150,
                                       start_date=attdb.prev_monday,
                                       end_date=attdb.next_monday)

    def test_an_end_before_a_start_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="must end after"):
            escalation.create_contract(attdb.s1, target_pct=90,
                                       start_date=attdb.next_monday,
                                       end_date=attdb.prev_monday)

    def test_signatures_are_recorded(self, attdb):
        contract = escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.next_monday)
        out = escalation.sign_contract(contract.contract_id,
                                       by_student=True,
                                       by_staff="Mr Patel")
        assert out.fully_signed is True

    def test_progress_is_measured_from_the_start_date(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        contract = escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.next_monday)
        progress = escalation.contract_progress(contract.contract_id)
        assert progress.achieved_pct == 100.0
        assert progress.on_track is True

    def test_a_missed_target_is_reported(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        contract = escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.next_monday)
        progress = escalation.contract_progress(contract.contract_id)
        assert progress.on_track is False
        assert progress.gap == -90.0

    def test_closing_settles_it_from_the_figure(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        contract = escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.next_monday)
        out = escalation.close_contract(contract.contract_id)
        assert out.state == escalation.MET
        assert out.outcome_pct == 100.0

    def test_contracts_due_review_are_listed(self, attdb):
        escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.prev_monday,
            review_on=attdb.prev_monday)
        assert len(escalation.contracts_due_review()) == 1

    def test_effectiveness_is_measurable(self, attdb):
        # The question a college should be able to answer about its own
        # intervention and almost never can.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "/"}})
        contract = escalation.create_contract(
            attdb.s1, target_pct=90, start_date=attdb.prev_monday,
            end_date=attdb.next_monday)
        escalation.close_contract(contract.contract_id)
        report = escalation.contract_effectiveness()
        assert report["contracts"] == 1
        assert report["met"] == 1


# ── 5. Meetings ────────────────────────────────────────────────────

class TestMeetings:

    def test_a_meeting_is_recorded(self, attdb):
        meeting = escalation.log_meeting(
            attdb.s1, attdb.prev_monday, kind="Tutor meeting",
            attendees="Ada, Mr Patel", actions="Daily report card",
            outcome="Agreed to attend period 1", recorded_by="Mr Patel")
        assert meeting.actions == "Daily report card"

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            escalation.log_meeting(attdb.s1, attdb.prev_monday,
                                   kind="Chat in the corridor")

    def test_a_meeting_moves_the_case_review_date(self, attdb):
        case = escalation.open_case(attdb.s1)
        escalation.log_meeting(attdb.s1, attdb.prev_monday,
                               case_id=case.case_id,
                               next_review=attdb.next_monday)
        assert escalation.get_case(case.case_id).review_on == \
            attdb.next_monday

    def test_meetings_are_listed_for_a_learner(self, attdb):
        escalation.log_meeting(attdb.s1, attdb.prev_monday)
        assert len(escalation.list_meetings(student_id=attdb.s1)) == 1

    def test_the_case_file_pulls_everything_together(self, attdb):
        case = escalation.open_case(attdb.s1, owner="Mr Patel")
        escalation.create_contract(attdb.s1, target_pct=90,
                                   start_date=attdb.prev_monday,
                                   end_date=attdb.next_monday)
        escalation.log_meeting(attdb.s1, attdb.prev_monday,
                               case_id=case.case_id)
        file = escalation.case_file(attdb.s1)
        assert len(file["cases"]) == 1
        assert len(file["contracts"]) == 1
        assert len(file["meetings"]) == 1
        assert file["stages"]
