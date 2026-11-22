"""Attendance: absence reasons, the rate and its rating, and the concerns.

The rules are tested pure. The register and the dashboards run through
the services on the conftest's throwaway database, because a concern is
only useful if it reaches the people who act on it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.training import attendance
from education_system.systems.apprenticeships.domain.training.sessions import SessionAttendance
from education_system.systems.apprenticeships.application.learning import training_service
from education_system.systems.apprenticeships.application.workspace import reporting_service


def _mark(n: int, status: str, reason: str | None = None) -> SessionAttendance:
    return SessionAttendance(
        attendance_id=n, session_id=n, apprentice_id=1, status=status, absence_reason=reason,
    )


def _summary(*statuses: str) -> attendance.AttendanceSummary:
    """Marks newest first, as the register history is read."""
    return attendance.summarise(1, [_mark(n, s) for n, s in enumerate(statuses)])


# ═════════════════════════════════════════════════════════════════════
# Absence reasons
# ═════════════════════════════════════════════════════════════════════

class TestAbsenceReasons:
    def test_the_reasons_the_rules_depend_on_are_configured(self):
        assert attendance.SICKNESS_REASON in config.ABSENCE_REASONS
        assert config.UNEXPLAINED_ABSENCE_REASON in config.ABSENCE_REASONS

    def test_attendance_marks_carry_no_reason(self):
        assert attendance.validate_absence_reason("Present", "Sickness") is None
        assert attendance.validate_absence_reason("Late", "Transport") is None

    def test_an_unexplained_absence_is_recorded_as_such(self):
        assert attendance.validate_absence_reason(
            "Absent", None
        ) == config.UNEXPLAINED_ABSENCE_REASON

    def test_a_reason_is_matched_ignoring_case(self):
        assert attendance.validate_absence_reason(
            "Excused", " medical APPOINTMENT "
        ) == "Medical appointment"

    def test_excusing_an_absence_needs_a_real_reason(self):
        with pytest.raises(ValidationError, match="needs a reason"):
            attendance.validate_absence_reason("Excused", None)
        with pytest.raises(ValidationError, match="cannot be excused"):
            attendance.validate_absence_reason("Excused", config.UNEXPLAINED_ABSENCE_REASON)

    def test_an_unknown_reason_is_refused(self):
        with pytest.raises(ValidationError, match="must be one of"):
            attendance.validate_absence_reason("Absent", "Overslept")


# ═════════════════════════════════════════════════════════════════════
# The summary
# ═════════════════════════════════════════════════════════════════════

class TestSummary:
    def test_counts_split_authorised_from_unauthorised_and_count_sickness(self):
        summary = attendance.summarise(1, [
            _mark(1, "Present"), _mark(2, "Late"),
            _mark(3, "Absent", "Sickness"), _mark(4, "Excused", "Sickness"),
            _mark(5, "Excused", "Annual leave"),
        ])
        assert (summary.present, summary.late) == (1, 1)
        assert (summary.unauthorised, summary.authorised, summary.sickness) == (1, 2, 2)

    def test_excused_absences_do_not_lower_the_rate(self):
        assert _summary("Present", "Present", "Present", "Absent",
                        "Excused", "Excused").attendance_rate == 75.0

    def test_too_few_sessions_are_not_rated(self):
        few = _summary("Absent", "Present", "Present")
        assert few.rag is None
        assert not few.is_concern

    @pytest.mark.parametrize(("attended", "missed", "rag"), [
        (9, 1, "Green"),    # 90%: on the target line
        (17, 3, "Amber"),   # 85%
        (4, 1, "Amber"),    # 80%: on the concern line
        (3, 1, "Red"),      # 75%
    ])
    def test_rag_follows_the_configured_lines(self, attended, missed, rag):
        # Absences first would make a run; attended marks lead instead.
        assert _summary(*["Present"] * attended, *["Absent"] * missed).rag == rag

    def test_the_run_counts_back_from_the_latest_mark(self):
        assert _summary("Absent", "Absent", "Present", "Absent").consecutive_unauthorised == 2
        assert _summary("Excused", "Absent", "Absent").consecutive_unauthorised == 0

    def test_a_run_of_absences_is_a_concern_before_there_is_a_rating(self):
        run = _summary("Absent", "Absent", "Absent")
        assert run.rag is None
        assert run.is_concern
        assert run.concern_reason == "3 unauthorised absences in a row"

    def test_a_red_rate_is_a_concern(self):
        red = _summary("Present", "Absent", "Present", "Absent", "Present")
        assert red.rag == "Red"
        assert red.is_concern
        assert "below 80%" in red.concern_reason


# ═════════════════════════════════════════════════════════════════════
# The register, and the dashboards it feeds
# ═════════════════════════════════════════════════════════════════════

def _session(admin, cohort, days_ago: int):
    return training_service.create_session(admin, {
        "title": f"Workshop ({days_ago} days ago)",
        "session_date": (date.today() - timedelta(days=days_ago)).isoformat(),
        "programme_id": cohort["programme"].programme_id,
        "otj_hours": 3,
    })


def _miss_three_in_a_row(admin, cohort) -> None:
    for days_ago in (21, 14, 7):
        session = _session(admin, cohort, days_ago)
        training_service.mark_attendance(
            admin, session.session_id, cohort["apprentice_id"], status="Absent",
        )


class TestRegister:
    def test_the_absence_reason_is_kept_on_the_register(self, cohort, admin):
        session = _session(admin, cohort, 7)
        training_service.mark_attendance(
            admin, session.session_id, cohort["apprentice_id"],
            status="Excused", absence_reason="Medical appointment",
        )
        (mark,) = training_service.get_register(admin, session.session_id)
        assert (mark.status, mark.absence_reason, mark.otj_hours) == (
            "Excused", "Medical appointment", 0.0,
        )

    def test_excusing_without_a_reason_is_refused(self, cohort, admin):
        session = _session(admin, cohort, 7)
        with pytest.raises(ValidationError, match="needs a reason"):
            training_service.mark_attendance(
                admin, session.session_id, cohort["apprentice_id"], status="Excused",
            )

    def test_re_marking_as_present_clears_the_reason(self, cohort, admin):
        session = _session(admin, cohort, 7)
        aid = cohort["apprentice_id"]
        training_service.mark_attendance(
            admin, session.session_id, aid, status="Absent", absence_reason="Transport",
        )
        training_service.mark_attendance(
            admin, session.session_id, aid, status="Present", absence_reason="Transport",
        )
        (mark,) = training_service.get_register(admin, session.session_id)
        assert (mark.status, mark.absence_reason) == ("Present", None)


class TestDashboards:
    def test_a_run_of_absences_reaches_the_tutor(self, cohort, admin):
        _miss_three_in_a_row(admin, cohort)
        data = reporting_service.staff_dashboard(cohort["tutor"])
        assert dict(data["kpis"])["Attendance concerns"] == 1
        ((summary, record),) = data["attendance_concerns"]
        assert summary.apprentice.apprentice_id == cohort["apprentice_id"]
        assert record.consecutive_unauthorised == 3

    def test_the_employer_sees_it_too(self, cohort, admin):
        _miss_three_in_a_row(admin, cohort)
        data = reporting_service.employer_dashboard(cohort["employer_actor"])
        assert [s.apprentice.apprentice_id for s, _ in data["attendance_concerns"]] == [
            cohort["apprentice_id"]
        ]

    def test_the_apprentice_sees_their_own_record(self, cohort, admin):
        session = _session(admin, cohort, 7)
        training_service.mark_attendance(
            admin, session.session_id, cohort["apprentice_id"],
            status="Excused", absence_reason="Sickness",
        )
        data = reporting_service.apprentice_dashboard(cohort["learner"])
        assert data["attendance"].sickness == 1
        # One mark is too few to rate, so the headline says so rather than 0%.
        assert dict(data["kpis"])["Attendance"] == "—"

    def test_nobody_is_flagged_when_attendance_is_fine(self, cohort, admin):
        for days_ago in (28, 21, 14, 7):
            session = _session(admin, cohort, days_ago)
            training_service.mark_attendance(
                admin, session.session_id, cohort["apprentice_id"], status="Present",
            )
        data = reporting_service.staff_dashboard(cohort["tutor"])
        assert data["attendance_concerns"] == []
