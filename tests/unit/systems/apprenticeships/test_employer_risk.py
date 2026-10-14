"""Employer risk: the scoring rules, and the figures gathered for them."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.employers.risk import (
    EmployerRiskMetrics,
    assess,
)
from education_system.systems.apprenticeships.infrastructure.persistence import schema
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    review_repository,
)
from education_system.systems.apprenticeships.services import (
    employer_contact_service,
    employer_risk_service,
    employer_service,
)
from education_system.systems.apprenticeships.services.access import PermissionDenied


def _metrics(**overrides) -> EmployerRiskMetrics:
    fields = dict(employer_id=1, employer_name="Acme")
    fields.update(overrides)
    return EmployerRiskMetrics(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestAssess:
    def test_no_indicators_is_low_and_says_what_was_not_assessed(self):
        result = assess(_metrics())
        assert (result.level, result.points) == ("Low", 0)
        assert "No active apprentices, so off-the-job progress is not assessed" in result.reasons

    def test_attendance_scores_against_the_configured_lines(self):
        poor = _metrics(active_apprentices=1, otj_on_track=1,
                        sessions_attended=7, sessions_countable=10)
        middling = _metrics(active_apprentices=1, otj_on_track=1,
                            sessions_attended=17, sessions_countable=20)
        assert assess(poor).points == 2
        assert assess(middling).points == 1
        assert "Attendance 70.0%" in assess(poor).reasons[0]

    def test_attendance_is_not_rated_on_too_few_sessions(self):
        few = _metrics(sessions_attended=0, sessions_countable=config.ATTENDANCE_MIN_SESSIONS - 1)
        assert few.attendance_percent is None
        assert assess(few).points == 0

    def test_off_the_job_compliance(self):
        assert assess(_metrics(active_apprentices=10, otj_on_track=5)).points == 2
        assert assess(_metrics(active_apprentices=10, otj_on_track=7)).points == 1
        assert assess(_metrics(active_apprentices=10, otj_on_track=9)).points == 0

    def test_overdue_reviews(self):
        assert assess(_metrics(reviews_overdue=1)).points == 1
        assert assess(_metrics(
            reviews_overdue=config.EMPLOYER_RISK_OVERDUE_REVIEWS_CONCERN)).points == 2

    def test_commitments_overdue_and_escalated(self):
        assert assess(_metrics(commitments_overdue=2)).points == 1
        escalated = assess(_metrics(commitments_overdue=1, highest_escalation=2))
        assert escalated.points == 3 and escalated.level == "Medium"

    def test_satisfaction(self):
        assert assess(_metrics(satisfaction=2.0)).points == 2
        assert assess(_metrics(satisfaction=3.0)).points == 1
        assert assess(_metrics(satisfaction=4.5)).points == 0

    def test_the_total_decides_the_level(self):
        assert assess(_metrics(reviews_overdue=1, satisfaction=3.0)).level == "Medium"
        high = assess(_metrics(reviews_overdue=5, satisfaction=1.0))
        assert (high.level, high.rag) == ("High", "Red")

    def test_highest_risk_sorts_first(self):
        results = [assess(_metrics(employer_name=n, **kw)) for n, kw in (
            ("Calm", {}), ("Bad", {"reviews_overdue": 5, "satisfaction": 1.0}),
            ("Meh", {"satisfaction": 2.0}),
        )]
        assert [r.employer_name for r in sorted(results, key=lambda r: r.sort_key)] == [
            "Bad", "Meh", "Calm",
        ]


# ═════════════════════════════════════════════════════════════════════
# Through the service
# ═════════════════════════════════════════════════════════════════════

def _mark_register(apprentice_id: int, marks: list[str]) -> None:
    """Sessions in the past with one mark each, straight into the test database."""
    with schema.connect() as conn:
        for index, mark in enumerate(marks):
            cur = conn.execute(
                "INSERT INTO training_sessions (title, session_date) VALUES (?, ?)",
                (f"Session {index}", (date.today() - timedelta(days=index + 1)).isoformat()),
            )
            conn.execute(
                "INSERT INTO session_attendance (session_id, apprentice_id, status) "
                "VALUES (?, ?, ?)",
                (cur.lastrowid, apprentice_id, mark),
            )


class TestService:
    def test_a_struggling_employer_is_high_risk(self, cohort, admin):
        aid, eid = cohort["apprentice_id"], cohort["employer"].employer_id
        _mark_register(aid, ["Absent", "Absent", "Absent", "Present", "Late"])
        review_repository.create({
            "apprentice_id": aid, "status": "Scheduled",
            "scheduled_date": (date.today() - timedelta(days=30)).isoformat(),
        })
        review_repository.add_feedback({"employer_id": eid, "satisfaction": "Very dissatisfied"})
        commitment = employer_contact_service.add_commitment(admin, eid, {
            "commitment": "Release on Fridays", "due_date":
                (date.today() - timedelta(days=5)).isoformat(),
        })
        employer_contact_service.escalate_commitment(admin, commitment.commitment_id, reason="a")

        result = employer_risk_service.assess_employer(admin, eid)
        metrics = result.metrics
        assert (metrics.apprentices, metrics.active_apprentices) == (1, 1)
        assert (metrics.sessions_attended, metrics.sessions_countable) == (2, 5)
        assert (metrics.reviews_overdue, metrics.commitments_overdue) == (1, 1)
        assert metrics.satisfaction == 1.0
        assert result.level == "High"
        assert any(reason.startswith("Attendance 40.0%") for reason in result.reasons)
        assert any("review" in reason for reason in result.reasons)

    def test_an_employer_with_nobody_on_programme_is_low(self, cohort, admin):
        quiet = employer_service.create_employer(admin, {"name": "Quiet Co", "status": "Active"})
        result = employer_risk_service.assess_employer(admin, quiet.employer_id)
        assert (result.level, result.metrics.apprentices) == ("Low", 0)

    def test_every_employer_is_listed_highest_risk_first(self, cohort, admin):
        employer_service.create_employer(admin, {"name": "Quiet Co", "status": "Active"})
        review_repository.add_feedback({
            "employer_id": cohort["employer"].employer_id, "satisfaction": "Very dissatisfied",
        })
        names = [r.employer_name for r in employer_risk_service.assess_employers(admin)]
        assert names == ["Acme Ltd", "Quiet Co"]

    def test_staff_see_only_their_caseloads_employers(self, cohort, admin):
        employer_service.create_employer(admin, {"name": "Quiet Co", "status": "Active"})
        seen = employer_risk_service.assess_employers(cohort["tutor"])
        assert [r.employer_name for r in seen] == ["Acme Ltd"]

    @pytest.mark.parametrize("who", ["employer_actor", "learner"])
    def test_outsiders_may_not_see_ratings(self, cohort, who):
        with pytest.raises(PermissionDenied):
            employer_risk_service.assess_employers(cohort[who])

    def test_risk_counts_cover_every_level(self, cohort, admin):
        counts = employer_risk_service.risk_counts(admin)
        assert set(counts) == set(config.EMPLOYER_RISK_LEVELS)
        assert sum(counts.values()) == 1
