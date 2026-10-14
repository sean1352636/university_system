"""Tests for ``admissions.services.handover_board`` — the university's half
of the University Progression board.

The tables and the outbox are stubbed, so nothing here touches a database.

Two properties carry most of the weight. First, the board must **never
create a student itself**: ``complete_enrolment`` delegates to
``convert_to_student``, which refuses until every admissions gate is
satisfied, and the board's job is to show the refusal rather than route
around it. Second, the duplicate warnings must fire — they are the only
thing standing between "two records for one person" and somebody being
enrolled twice.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service
from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_lifecycle as lifecycle,
    handover_board as hb,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

_PAYLOAD = {
    "student_identity": {"sixth_form_student_id": "SF-1",
                         "first_name": "Ada", "last_name": "Lovelace"},
    "ucas_application": {"ucas_id": "UC1"},
    "confirmed_destination": {"course_name": "Computer Science",
                              "entry_year": 2027},
    "offer_conditions": {"grade_requirement": "AAB"},
    "handover_consent": {"consent_id": 9},
    "achieved_qualifications": [{"subject": "Mathematics", "grade": "A"},
                                {"subject": "Physics", "grade": "B"}],
}

_SUMMARIES = [
    dict(application_id=1, journey_id="J1", status="documents_pending",
         converted_student_id=None, external_reference="UC1",
         program_applied="Computer Science", academic_year="2027",
         first_name="Ada", last_name="Lovelace",
         high_school="Riverside Sixth Form"),
    dict(application_id=2, journey_id="J2", status="ready_to_enrol",
         converted_student_id=None, external_reference="UC2",
         program_applied="Data Science", academic_year="2027",
         first_name="Alan", last_name="Turing",
         high_school="Riverside Sixth Form"),
    # Deliberately a second application on J2 — the shape the intake now
    # prevents, but which older rows still have.
    dict(application_id=3, journey_id="J2", status="submitted",
         converted_student_id=None, external_reference="UC2b",
         program_applied="Data Science", academic_year="2027",
         first_name="Alan", last_name="Turing",
         high_school="Riverside Sixth Form"),
    dict(application_id=4, journey_id="J4", status="enrolled",
         converted_student_id="7654321", external_reference="UC4",
         program_applied="Law", academic_year="2027",
         first_name="Grace", last_name="Hopper",
         high_school="Northgate College"),
]

_APPS = {
    1: dict(_SUMMARIES[0],
            requirements=[{"requirement_type": "identity",
                           "description": "ID evidence",
                           "required": 1, "status": "pending"}],
            conditions=[{"condition_type": "academic",
                         "description": "AAB", "status": "pending"}]),
    2: dict(_SUMMARIES[1], requirements=[],
            conditions=[{"condition_type": "academic",
                         "description": "AAB", "status": "satisfied"}]),
    3: dict(_SUMMARIES[2], requirements=[], conditions=[]),
    4: dict(_SUMMARIES[3], requirements=[], conditions=[]),
}


@pytest.fixture()
def sources(monkeypatch):
    """Stub the admissions tables, the outbox and the journey registry."""
    monkeypatch.setattr(hb, "_handover_applications", lambda: list(_SUMMARIES))
    monkeypatch.setattr(lifecycle, "get_application", lambda aid: _APPS[aid])
    monkeypatch.setattr(
        cross_system_bus, "events_for_journeys",
        lambda ids, event_name=None: {
            "J1": [{"payload": _PAYLOAD}],
            "J2": [{"payload": {**_PAYLOAD,
                                "achieved_qualifications": None,
                                "predicted_qualifications": [
                                    {"subject": "Mathematics",
                                     "grade": "A*"}]}}],
            "J4": [{"payload": _PAYLOAD}],
        })
    journeys = {
        "J1": {"journey_id": "J1", "legal_first_name": "Ada",
               "legal_last_name": "Lovelace", "date_of_birth": "2007-01-01"},
        "J2": {"journey_id": "J2"},
        "J4": {"journey_id": "J4", "university_student_id": "7654321"},
    }
    monkeypatch.setattr(identity_service, "get", lambda jid: journeys.get(jid))
    monkeypatch.setattr(identity_service, "find_by_identity",
                        lambda f, l, d: {"journey_id": "J-TWIN"})
    return journeys


class TestBoard:
    def test_rows_carry_the_source_and_the_programme(self, sources):
        row = hb.board().get(1)
        assert row.full_name == "Ada Lovelace"
        assert row.source_sixth_form == "Riverside Sixth Form"
        assert row.sixth_form_student_id == "SF-1"
        assert row.ucas_id == "UC1"
        assert row.programme == "Computer Science"

    def test_handover_fields_are_read_back_off_the_outbox(self, sources):
        """The applicant record does not say which fields crossed; only the
        published event does."""
        row = hb.board().get(1)
        assert "student_identity" in row.included
        assert "ucas_application" in row.included
        assert "reference" in row.withheld
        assert "predicted_qualifications" in row.withheld

    def test_achieved_qualifications_beat_predicted(self, sources):
        board = hb.board()
        assert board.get(1).qualification_status.startswith("Achieved:")
        assert board.get(2).qualification_status.startswith("Predicted only:")

    def test_offer_status_counts_unsatisfied_conditions(self, sources):
        board = hb.board()
        assert board.get(1).offer_status == "1 of 1 condition(s) outstanding"
        assert board.get(2).offer_status == "All 1 condition(s) satisfied"

    def test_outstanding_lists_requirements_and_conditions(self, sources):
        outstanding = hb.board().get(1).outstanding
        assert any(o.startswith("Requirement:") for o in outstanding)
        assert any(o.startswith("Condition:") for o in outstanding)

    def test_a_converted_application_is_enrolled(self, sources):
        row = hb.board().get(4)
        assert row.state == hb.ENROLLED
        assert row.converted_student_id == "7654321"

    def test_trouble_sorts_to_the_top(self, sources):
        assert hb.board().rows[0].state == hb.NEEDS_ATTENTION

    def test_no_handovers_is_an_empty_board(self, monkeypatch):
        monkeypatch.setattr(hb, "_handover_applications", lambda: [])
        assert hb.board().rows == []

    def test_a_missing_event_is_flagged_rather_than_silently_blank(
        self, sources, monkeypatch
    ):
        monkeypatch.setattr(cross_system_bus, "events_for_journeys",
                            lambda ids, event_name=None: {})
        row = hb.board().get(1)
        assert any("No progression event" in w for w in row.warnings)

    def test_an_unreadable_outbox_does_not_take_the_board_down(
        self, sources, monkeypatch
    ):
        def _boom(ids, event_name=None):
            raise RuntimeError("auth.db is locked")

        monkeypatch.setattr(cross_system_bus, "events_for_journeys", _boom)
        assert len(hb.board().rows) == 4


class TestDuplicateWarnings:
    def test_two_applications_on_one_journey(self, sources):
        board = hb.board()
        assert "application(s) 3" in " ".join(board.get(2).warnings)
        assert "application(s) 2" in " ".join(board.get(3).warnings)
        assert board.get(2).state == hb.NEEDS_ATTENTION

    def test_a_name_and_dob_twin_on_another_journey(self, sources):
        """The registry failing to match is what produces a duplicate
        student later, so it is surfaced before enrolment, not after."""
        assert "J-TWIN" in " ".join(hb.board().get(1).warnings)

    def test_no_twin_means_no_warning(self, sources, monkeypatch):
        monkeypatch.setattr(identity_service, "find_by_identity",
                            lambda f, l, d: None)
        assert hb.board().get(1).warnings == ()

    def test_an_unconverted_application_on_an_enrolled_journey(
        self, sources, monkeypatch
    ):
        """The shape the students-GUI direct import used to leave behind."""
        monkeypatch.setattr(identity_service, "find_by_identity",
                            lambda f, l, d: None)
        monkeypatch.setattr(
            identity_service, "get",
            lambda jid: {"journey_id": jid,
                         "university_student_id": "1234567"}
            if jid == "J1" else sources.get(jid))
        assert "already university student 1234567" in " ".join(
            hb.board().get(1).warnings)


class TestActions:
    def test_accept_transitions_and_audits(self, sources, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            lifecycle, "transition",
            lambda aid, st, reason="", actor_id="", force=False:
                calls.update(aid=aid, status=st, reason=reason,
                             actor=actor_id))
        result = hb.accept(1, actor_id="registrar")
        assert result.ok
        assert calls["status"] == lifecycle.UNDER_REVIEW
        assert "registrar" in calls["reason"]

    def test_accept_reports_an_invalid_transition(self, sources, monkeypatch):
        def _refuse(aid, st, reason="", actor_id="", force=False):
            raise AdmissionsBoundaryError("Invalid admissions transition")

        monkeypatch.setattr(lifecycle, "transition", _refuse)
        result = hb.accept(1)
        assert not result.ok and "Invalid" in result.detail

    def test_request_information_raises_requirements(self, sources,
                                                     monkeypatch):
        added = []
        monkeypatch.setattr(
            lifecycle, "add_requirement",
            lambda aid, t, d, due_date="": added.append(t))
        monkeypatch.setattr(lifecycle, "transition",
                            lambda *a, **k: None)
        result = hb.request_information(
            1, ["reference", "personal_statement"], actor_id="reg")
        assert result.ok
        assert added == ["reference", "personal_statement"]

    def test_request_information_is_idempotent_per_field(self, sources,
                                                         monkeypatch):
        """Application 1 already has an ``identity`` requirement, so asking
        again must not add a second row — the button is safe to press when
        a colleague already pressed it."""
        added = []
        monkeypatch.setattr(
            lifecycle, "add_requirement",
            lambda aid, t, d, due_date="": added.append(t))
        monkeypatch.setattr(lifecycle, "transition", lambda *a, **k: None)
        hb.request_information(1, ["identity", "reference"])
        assert added == ["reference"]
        result = hb.request_information(1, ["identity"])
        assert result.ok and "Already requested" in result.detail

    def test_request_information_with_nothing_selected(self, sources):
        assert not hb.request_information(1, []).ok

    def test_requirements_survive_a_failed_status_move(self, sources,
                                                       monkeypatch):
        """The requirements are the substance; the status is presentation."""
        added = []
        monkeypatch.setattr(
            lifecycle, "add_requirement",
            lambda aid, t, d, due_date="": added.append(t))

        def _boom(*a, **k):
            raise RuntimeError("status write failed")

        monkeypatch.setattr(lifecycle, "transition", _boom)
        result = hb.request_information(1, ["reference"])
        assert result.ok and added == ["reference"]


class TestEnrolment:
    def test_the_board_never_creates_a_student_itself(self, sources,
                                                      monkeypatch):
        seen = {}

        def _convert(application_id, actor_id=""):
            seen["aid"] = application_id
            return "1234567"

        monkeypatch.setattr(
            lifecycle, "convert_to_student",
            _convert)
        result = hb.complete_enrolment(2, actor_id="reg")
        assert result.ok and result.student_id == "1234567"
        assert seen["aid"] == 2

    def test_a_refusal_is_reported_not_worked_around(self, sources,
                                                     monkeypatch):
        def _refuse(aid, actor_id=""):
            raise AdmissionsBoundaryError(
                "Application is not ready to enrol: right-to-study policy "
                "decision is not approved")

        monkeypatch.setattr(lifecycle, "convert_to_student", _refuse)
        result = hb.complete_enrolment(2)
        assert not result.ok
        assert "right-to-study" in result.detail
        assert result.student_id is None

    def test_blockers_are_surfaced_before_the_attempt(self, sources,
                                                      monkeypatch):
        monkeypatch.setattr(lifecycle, "readiness_issues",
                            lambda aid: ["deposit policy decision is not "
                                         "satisfied"])
        assert hb.enrolment_blockers(2) == [
            "deposit policy decision is not satisfied"]

    def test_a_broken_readiness_check_reads_as_a_blocker(self, sources,
                                                         monkeypatch):
        def _boom(aid):
            raise RuntimeError("schema mismatch")

        monkeypatch.setattr(lifecycle, "readiness_issues", _boom)
        assert "schema mismatch" in hb.enrolment_blockers(2)[0]

    def test_bulk_never_stops_on_the_first_refusal(self, sources,
                                                   monkeypatch):
        converted = []

        def _convert(aid, actor_id=""):
            if aid == 3:
                raise AdmissionsBoundaryError("no accepted programme choice")
            converted.append(aid)
            return f"999000{aid}"

        monkeypatch.setattr(lifecycle, "convert_to_student", _convert)
        results = hb.complete_enrolment_many([2, 3, 1], actor_id="reg")
        assert [r.ok for r in results] == [True, False, True]
        assert converted == [2, 1]
        assert "no accepted programme choice" in results[1].detail
