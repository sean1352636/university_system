"""The skills matrix: KSB coverage per apprentice and across a cohort.

The shaping is tested pure. The levels themselves come from the
portfolio's coverage rule, so the service tests build real evidence and
check that the matrix says exactly what the portfolio says — and shows
it only to the people who may see that portfolio.
"""

from __future__ import annotations

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes.models import KSB, KSBCoverage
from education_system.systems.apprenticeships.domain.progress import skills_matrix as rules
from education_system.systems.apprenticeships.domain.progress.skills_matrix import (
    CohortRow,
    SkillsMatrix,
)
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    portfolio_service,
    programme_service,
    skills_matrix_service,
)
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied


def _cov(code: str, level: str, ksb_id: int = 0) -> KSBCoverage:
    ksb_type = {"K": "Knowledge", "S": "Skill", "B": "Behaviour"}[code[0]]
    return KSBCoverage(
        ksb=KSB(ksb_id=ksb_id, programme_id=1, code=code, ksb_type=ksb_type, description=code),
        coverage=level,
    )


# ═════════════════════════════════════════════════════════════════════
# Shaping
# ═════════════════════════════════════════════════════════════════════

class TestBars:
    def test_the_bar_fills_with_the_level(self):
        width = config.SKILLS_MATRIX_BAR_WIDTH
        assert rules.level_bar("Not started") == "░" * width
        assert rules.level_bar("Competent") == "█" * width
        assert rules.level_bar("Developing").count("█") == round(width / 2)
        assert len(rules.level_bar("Developing", width=10)) == 10

    def test_an_unknown_level_reads_as_not_started(self):
        assert rules.level_fraction("Mastered") == 0.0


class TestMatrix:
    matrix = SkillsMatrix(apprentice_id=1, coverage=[
        _cov("K10", "Competent", 1), _cov("K2", "Developing", 2), _cov("S1", "Competent", 3),
        _cov("S2", "Not started", 4),
    ])

    def test_grouped_by_type_in_numeric_order(self):
        grouped = self.matrix.by_type()
        assert list(grouped) == list(config.KSB_TYPES)
        assert [c.ksb.code for c in grouped["Knowledge"]] == ["K2", "K10"]
        assert grouped["Behaviour"] == []

    def test_a_type_the_standard_lacks_has_no_percentage_rather_than_zero(self):
        summaries = {s.ksb_type: s for s in self.matrix.summaries()}
        assert summaries["Knowledge"].percent_competent == 50.0
        assert summaries["Skill"].percent_competent == 50.0
        assert summaries["Behaviour"].percent_competent is None
        assert (self.matrix.competent, self.matrix.total, self.matrix.percent_competent) == (
            2, 4, 50.0,
        )

    def test_the_cohort_mean_leaves_out_what_does_not_apply(self):
        rows = [
            CohortRow(1, "A", coverage=[_cov("K1", "Competent"), _cov("B1", "Competent")]),
            CohortRow(2, "B", coverage=[_cov("K1", "Not started")]),
            CohortRow(3, "C", coverage=[]),
        ]
        assert rules.average_percent(rows, "Knowledge") == 50.0
        assert rules.average_percent(rows, "Behaviour") == 100.0
        assert rules.average_percent(rows, "Skill") is None
        assert rules.average_percent(rows) == 50.0


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

def _evidence_all_ksbs(cohort, *, accept: bool, competent: tuple[str, ...] = ()) -> None:
    """One piece of evidence mapped to every KSB, optionally accepted with
    some of them judged Competent."""
    learner, tutor = cohort["learner"], cohort["tutor"]
    evidence = portfolio_service.add_evidence(learner, {
        "title": "Network build", "evidence_type": "Work product",
    })
    for ksb in programme_service.list_ksbs(tutor, cohort["programme"].programme_id):
        portfolio_service.map_to_ksb(learner, evidence.evidence_id, ksb.ksb_id,
                                     coverage="Developing")
    if not accept:
        return
    portfolio_service.submit_evidence(learner, evidence.evidence_id)
    portfolio_service.assess_evidence(tutor, evidence.evidence_id, outcome="Accepted",
                                      feedback="Solid")
    for mapping in portfolio_service.get_evidence(tutor, evidence.evidence_id).mappings:
        if mapping.ksb_code in competent:
            portfolio_service.update_mapping(tutor, mapping.map_id, coverage="Competent")


class TestApprenticeMatrix:
    def test_unaccepted_evidence_shows_as_work_in_flight_not_progress(self, cohort):
        _evidence_all_ksbs(cohort, accept=False)
        matrix = skills_matrix_service.apprentice_matrix(cohort["tutor"], cohort["apprentice_id"])
        assert {c.coverage for c in matrix.coverage} == {"Not started"}
        assert {c.evidence_count for c in matrix.coverage} == {1}

    def test_levels_follow_the_assessors_judgement(self, cohort):
        _evidence_all_ksbs(cohort, accept=True, competent=("K1",))
        matrix = skills_matrix_service.apprentice_matrix(cohort["tutor"], cohort["apprentice_id"])
        assert {t: [(c.ksb.code, c.coverage) for c in items]
                for t, items in matrix.by_type().items()} == {
            "Knowledge": [("K1", "Competent")],
            "Skill": [("S1", "Developing")],
            "Behaviour": [("B1", "Developing")],
        }
        assert (matrix.apprentice_name, matrix.programme_title) == ("Jo Bell", "Software Developer")

    def test_the_matrix_and_the_portfolio_agree(self, cohort, admin):
        _evidence_all_ksbs(cohort, accept=True, competent=("K1", "B1"))
        matrix = skills_matrix_service.apprentice_matrix(admin, cohort["apprentice_id"])
        portfolio = portfolio_service.get_portfolio(admin, cohort["apprentice_id"])
        assert matrix.percent_competent == portfolio.percent_competent
        assert matrix.competent == portfolio.competent_ksbs

    def test_the_apprentice_sees_their_own(self, cohort):
        _evidence_all_ksbs(cohort, accept=True, competent=("S1",))
        mine = skills_matrix_service.my_matrix(cohort["learner"])
        assert mine is not None and mine.competent == 1
        assert skills_matrix_service.my_matrix(Actor(username="x", role="apprentice")) is None

    def test_another_organisation_is_refused(self, cohort):
        with pytest.raises(PermissionDenied):
            skills_matrix_service.apprentice_matrix(cohort["outsider"], cohort["apprentice_id"])

    def test_an_apprentice_not_on_a_programme_has_no_matrix(self, cohort, admin):
        waiting = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        with pytest.raises(ValidationError, match="not on a programme"):
            skills_matrix_service.apprentice_matrix(admin, waiting.apprentice_id)


class TestCohort:
    def test_the_tutor_employer_and_admin_see_the_apprentice_in_their_cohort(self, cohort, admin):
        _evidence_all_ksbs(cohort, accept=True, competent=("K1",))
        for who in (cohort["tutor"], cohort["employer_actor"], admin):
            (row,) = skills_matrix_service.cohort_matrix(who)
            assert (row.apprentice_name, row.employer_name) == ("Jo Bell", "Acme Ltd")
            assert (row.percent("Knowledge"), row.percent("Skill"),
                    row.percent("Behaviour")) == (100.0, 0.0, 0.0)
            assert row.percent_overall == pytest.approx(33.3)

    def test_the_cohort_is_scoped(self, cohort):
        assert skills_matrix_service.cohort_matrix(cohort["outsider"]) == []
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert skills_matrix_service.cohort_matrix(stranger) == []

    def test_an_employer_cannot_widen_their_cohort(self, cohort):
        assert skills_matrix_service.cohort_matrix(
            cohort["outsider"], employer_id=cohort["employer"].employer_id
        ) == []

    def test_the_apprentice_and_the_assessor_get_no_cohort_view(self, cohort, assessor):
        for who in (cohort["learner"], assessor):
            with pytest.raises(PermissionDenied):
                skills_matrix_service.cohort_matrix(who)

    def test_the_assessor_may_open_one_matrix_as_they_may_the_portfolio(self, cohort, assessor):
        matrix = skills_matrix_service.apprentice_matrix(assessor, cohort["apprentice_id"])
        assert matrix.total == 3

    def test_apprentices_with_no_programme_are_left_out(self, cohort, admin):
        apprentice_service.create_apprentice(admin, {"given_name": "Ali", "family_name": "Khan"})
        rows = skills_matrix_service.cohort_matrix(admin, active_only=False)
        assert [r.apprentice_name for r in rows] == ["Jo Bell"]

    def test_filtering_by_programme(self, cohort, admin):
        assert skills_matrix_service.cohort_matrix(admin, programme_id=999999) == []
        assert len(skills_matrix_service.cohort_matrix(
            admin, programme_id=cohort["programme"].programme_id
        )) == 1
