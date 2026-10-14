"""Surveys: the scale, one response each, anonymous results, and who is asked.

The aggregation is tested pure, because it is where anonymity is decided:
it is never handed a respondent, and it withholds everything below the
threshold. The rest runs through the services on the conftest's
throwaway database.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.quality import surveys as rules
from education_system.systems.apprenticeships.domain.quality.surveys import Survey
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
)
from education_system.systems.apprenticeships.services import apprentice_service, survey_service
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)


def _survey(kind: str = "Training feedback", **overrides) -> Survey:
    fields = dict(survey_id=1, title="Autumn", audience="Apprentice", kind=kind, status="Open")
    fields.update(overrides)
    return Survey(**fields)


def _answers(survey: Survey, score: object = 4) -> dict[str, object]:
    return {q: score for q in survey.questions}


@pytest.fixture
def learners(cohort, admin) -> list[Actor]:
    """Three apprentices on programme: the cohort's, plus two more."""
    actors = [cohort["learner"]]
    for n, (given, family) in enumerate((("Al", "Ng"), ("Bo", "Li")), start=2):
        created = apprentice_service.create_apprentice(admin, {
            "given_name": given, "family_name": family, "username": f"apprentice{n}",
            "date_of_birth": "2003-05-01",
            "programme_id": cohort["programme"].programme_id,
            "employer_id": cohort["employer"].employer_id, "tutor_id": cohort["tutor_id"],
        })
        apprentice_service.start_programme(admin, created.apprentice_id,
                                           start_date=cohort["start_date"])
        actors.append(Actor(username=f"apprentice{n}", role="apprentice",
                            apprentice_id=created.apprentice_id,
                            employer_id=cohort["employer"].employer_id))
    return actors


def _open(admin, kind: str = "Training feedback", **payload) -> Survey:
    survey = survey_service.create_survey(admin, {"title": f"{kind} survey", "kind": kind,
                                                  **payload})
    return survey_service.open_survey(admin, survey.survey_id)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestScale:
    @pytest.mark.parametrize(("value", "expected"), [
        (1, 1), (5, 5), ("3", 3), ("Very satisfied", 5), ("very DISSATISFIED", 1),
        ("Neutral", 3),
    ])
    def test_an_answer_is_a_score_or_its_label(self, value, expected):
        assert rules.score_for(value) == expected

    @pytest.mark.parametrize("value", [0, 6, "Great", "", None, True, "4.5"])
    def test_anything_off_the_scale_is_refused(self, value):
        with pytest.raises(ValidationError):
            rules.score_for(value)

    def test_the_scale_is_the_satisfaction_scale(self):
        assert rules.SCALE == config.SATISFACTION_SCALE
        assert rules.label_for(4) == "Satisfied"


class TestAnswers:
    def test_every_question_must_be_answered(self):
        survey = _survey()
        partial = _answers(survey)
        partial.pop(survey.questions[-1])
        with pytest.raises(ValidationError, match="answer every question"):
            rules.validate_answers(survey.kind, partial)

    def test_a_question_from_another_survey_is_refused(self):
        survey = _survey()
        with pytest.raises(ValidationError, match="Not a question"):
            rules.validate_answers(survey.kind, {**_answers(survey), "Favourite colour?": 3})

    def test_labels_become_scores(self):
        survey = _survey()
        assert set(rules.validate_answers(survey.kind, _answers(survey, "Satisfied")).values()) \
            == {4}

    def test_every_kind_has_questions(self):
        assert set(config.SURVEY_QUESTIONS) == set(config.SURVEY_KINDS)
        assert all(config.SURVEY_QUESTIONS[k] for k in config.SURVEY_KINDS)


class TestSetUp:
    def test_the_audience_must_suit_the_kind(self):
        assert rules.validate_audience("Employer satisfaction", "employer") == "Employer"
        with pytest.raises(ValidationError, match="is for"):
            rules.validate_audience("End of programme", "Employer")

    def test_draft_opens_and_open_closes_and_that_is_all(self):
        rules.require_transition("Draft", "Open")
        rules.require_transition("Open", "Closed")
        for current, new in (("Draft", "Closed"), ("Closed", "Open"), ("Open", "Draft")):
            with pytest.raises(ValidationError):
                rules.require_transition(current, new)

    def test_a_survey_cannot_close_before_it_opens(self):
        with pytest.raises(ValidationError, match="close before it opens"):
            rules.validate_dates("2026-10-01", "2026-09-01")

    def test_accepting_follows_the_status_and_dates(self):
        assert _survey(opens_on="2026-09-01", closes_on="2026-09-30").is_accepting(TODAY)
        assert not _survey(opens_on="2026-09-11").is_accepting(TODAY)
        assert not _survey(closes_on="2026-09-09").is_accepting(TODAY)
        assert not _survey(status="Draft").is_accepting(TODAY)

    def test_end_of_programme_is_for_those_at_the_end(self):
        assert rules.eligible_statuses("End of programme") == {"EPA", "Completed"}
        assert rules.eligible_statuses("Training feedback") == config.ACTIVE_STATUSES


class TestSummarise:
    def test_below_the_threshold_nothing_is_shown(self):
        survey = _survey()
        few = [_ints(survey, 5)] * (config.SURVEY_ANONYMITY_THRESHOLD - 1)
        results = rules.summarise(survey, few, ["Loved it"] * len(few),
                                  eligible_count=10, responded_count=len(few))
        assert results.withheld
        assert results.questions == [] and results.comments == []
        assert results.response_count == len(few)

    def test_averages_and_spread(self):
        survey = _survey()
        results = rules.summarise(
            survey, [_ints(survey, 5), _ints(survey, 4), _ints(survey, 3)], [None, "", None],
            eligible_count=4, responded_count=3,
        )
        first = results.questions[0]
        assert (first.average, first.answered, first.average_label) == (4.0, 3, "Satisfied")
        assert first.distribution == (0, 0, 1, 1, 1)
        assert results.response_rate == 75.0
        assert results.comments == []

    def test_comments_lose_their_order(self):
        survey = _survey()
        results = rules.summarise(
            survey, [_ints(survey, 3)] * 3, ["zebra", "  apple ", "mango"],
            eligible_count=3, responded_count=3,
        )
        assert results.comments == ["apple", "mango", "zebra"]

    def test_the_rate_is_capped_and_undefined_with_no_audience(self):
        survey = _survey()
        assert rules.summarise(survey, [], [], eligible_count=0,
                               responded_count=0).response_rate is None
        assert rules.summarise(survey, [], [], eligible_count=1,
                               responded_count=2).response_rate == 100.0


def _ints(survey: Survey, score: int) -> dict[str, int]:
    return {q: score for q in survey.questions}


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

class TestManaging:
    def test_only_the_manager_runs_surveys(self, cohort, admin):
        with pytest.raises(PermissionDenied):
            survey_service.create_survey(cohort["tutor"], {"title": "x",
                                                           "kind": "Satisfaction"})
        survey = survey_service.create_survey(admin, {"title": "Autumn",
                                                      "kind": "Training feedback"})
        assert (survey.status, survey.audience, survey.created_by) == (
            "Draft", "Apprentice", "admin5")
        with pytest.raises(PermissionDenied):
            survey_service.open_survey(cohort["tutor"], survey.survey_id)

    def test_opening_stamps_the_date_and_closing_brings_it_forward(self, cohort, admin):
        survey = survey_service.create_survey(admin, {
            "title": "Autumn", "kind": "Satisfaction",
            "closes_on": (date.today() + timedelta(days=30)).isoformat(),
        })
        opened = survey_service.open_survey(admin, survey.survey_id)
        assert opened.opens_on == date.today().isoformat()
        closed = survey_service.close_survey(admin, survey.survey_id)
        assert (closed.status, closed.closes_on) == ("Closed", date.today().isoformat())

    def test_kind_and_audience_are_fixed_once_open(self, cohort, admin):
        survey = _open(admin)
        with pytest.raises(ValidationError, match="fixed"):
            survey_service.update_survey(admin, survey.survey_id, {"kind": "Satisfaction"})
        renamed = survey_service.update_survey(admin, survey.survey_id, {"title": "Renamed"})
        assert renamed.title == "Renamed"

    def test_a_draft_is_offered_to_nobody(self, cohort, admin):
        survey_service.create_survey(admin, {"title": "Soon", "kind": "Training feedback"})
        assert survey_service.available_surveys(cohort["learner"]) == []


class TestResponding:
    def test_one_response_per_respondent(self, cohort, admin):
        survey = _open(admin)
        survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey))
        assert survey_service.has_responded(cohort["learner"], survey.survey_id)
        with pytest.raises(ValidationError, match="already responded"):
            survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey, 1))
        assert [(s.survey_id, done) for s, done in survey_service.available_surveys(
            cohort["learner"])] == [(survey.survey_id, True)]

    def test_surveys_go_to_their_own_audience(self, cohort, admin):
        apprentice_survey = _open(admin)
        employer_survey = _open(admin, "Employer satisfaction")
        assert [s.survey_id for s, _ in survey_service.available_surveys(
            cohort["learner"])] == [apprentice_survey.survey_id]
        assert [s.survey_id for s, _ in survey_service.available_surveys(
            cohort["employer_actor"])] == [employer_survey.survey_id]
        with pytest.raises(PermissionDenied, match="not addressed to you"):
            survey_service.respond(cohort["learner"], employer_survey.survey_id,
                                   _answers(employer_survey))

    def test_a_closed_survey_takes_no_more(self, cohort, admin):
        survey = _open(admin)
        survey_service.close_survey(admin, survey.survey_id)
        with pytest.raises(ValidationError, match="not open"):
            survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey))

    def test_staff_do_not_answer_surveys(self, cohort, admin):
        survey = _open(admin)
        with pytest.raises(PermissionDenied):
            survey_service.respond(cohort["tutor"], survey.survey_id, _answers(survey))

    def test_the_audit_trail_records_that_not_what(self, cohort, admin):
        survey = _open(admin)
        survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey, 2),
                               comment="The workshop room is freezing")
        (entry,) = compliance_repository.list_audit(entity="survey_response")
        assert entry.actor == "apprentice1"
        assert entry.detail == f"Responded to survey {survey.survey_id}"


class TestEndOfProgramme:
    def test_an_apprentice_on_programme_is_not_asked(self, cohort, admin):
        survey = _open(admin, "End of programme")
        assert survey_service.available_surveys(cohort["learner"]) == []
        with pytest.raises(ValidationError, match="at EPA or who have completed"):
            survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey))

    @pytest.mark.parametrize("status", ["EPA", "Completed"])
    def test_an_apprentice_at_the_end_is(self, cohort, admin, status):
        survey = _open(admin, "End of programme")
        apprentice_repository.update(cohort["apprentice_id"], {"status": status})
        assert [s.survey_id for s, _ in survey_service.available_surveys(
            cohort["learner"])] == [survey.survey_id]
        survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey, 5))

    def test_the_rate_counts_only_those_eligible(self, cohort, admin, learners):
        survey = _open(admin, "End of programme")
        apprentice_repository.update(cohort["apprentice_id"], {"status": "EPA"})
        survey_service.respond(cohort["learner"], survey.survey_id, _answers(survey))
        results = survey_service.results(admin, survey.survey_id)
        assert (results.eligible_count, results.responded_count, results.response_rate) == (
            1, 1, 100.0)


class TestResults:
    def test_results_are_withheld_until_enough_have_answered(self, cohort, admin, learners):
        survey = _open(admin)
        for learner in learners[:2]:
            survey_service.respond(learner, survey.survey_id, _answers(survey, 5),
                                   comment="Great")
        results = survey_service.results(cohort["tutor"], survey.survey_id)
        assert results.withheld and results.questions == [] and results.comments == []
        assert (results.response_count, results.eligible_count) == (2, 3)

    def test_results_are_anonymous(self, cohort, admin, learners):
        survey = _open(admin)
        for learner, score in zip(learners, (5, 4, 3), strict=True):
            survey_service.respond(learner, survey.survey_id, _answers(survey, score),
                                   comment=f"From {learner.username}'s point of view")
        results = survey_service.results(cohort["tutor"], survey.survey_id)

        assert not results.withheld
        assert [q.average for q in results.questions] == [4.0] * len(survey.questions)
        assert results.response_rate == 100.0
        # The comments are the respondents' own words; everything the
        # service adds must be free of who they are.
        shown = repr([results.questions, results.response_count, results.eligible_count])
        for learner in learners:
            assert learner.username not in shown
        assert not any(hasattr(results, f) for f in ("respondent", "respondents", "responses"))

    def test_respondents_cannot_read_results(self, cohort, admin):
        survey = _open(admin)
        with pytest.raises(PermissionDenied):
            survey_service.results(cohort["learner"], survey.survey_id)
        with pytest.raises(PermissionDenied):
            survey_service.results(cohort["employer_actor"], survey.survey_id)

    def test_an_employer_survey_counts_employers(self, cohort, admin):
        survey = _open(admin, "Employer satisfaction")
        survey_service.respond(cohort["employer_actor"], survey.survey_id, _answers(survey))
        results = survey_service.results(admin, survey.survey_id)
        assert (results.eligible_count, results.responded_count) == (1, 1)
