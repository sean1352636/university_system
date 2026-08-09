"""Tests for the safeguarding text-analysis layer (pure, no DB).

Covers the regex risk classifier (``analyse_text``), the bag-of-words NLP
classifier (``nlp_classify`` / ``_crude_stem``) and the self-harm predicate.
"""

import pytest

from education_system.systems.university.domain.safeguarding.analysis import (
    RiskCategory,
    SEVERITY_ORDER,
    analyse_text,
    _crude_stem,
    is_self_harm_case,
    nlp_classify,
)


class TestAnalyseText:
    def test_clean_text_is_none_severity(self):
        matches, overall = analyse_text("Everything is going well this term, thanks!")
        assert matches == {}
        assert overall == "NONE"

    def test_self_harm_detected_as_critical(self):
        matches, overall = analyse_text("I want to kill myself and don't want to live")
        assert RiskCategory.SELF_HARM in matches
        assert overall == "CRITICAL"
        # Snippets carry surrounding context for the reviewer.
        assert matches[RiskCategory.SELF_HARM]["snippets"]

    def test_overall_is_highest_severity_across_categories(self):
        # "overwhelmed" -> ACADEMIC (LOW); "depressed" -> MENTAL_HEALTH (HIGH).
        matches, overall = analyse_text("I feel overwhelmed and completely depressed")
        assert RiskCategory.ACADEMIC in matches
        assert RiskCategory.MENTAL_HEALTH in matches
        assert overall == "HIGH"
        assert SEVERITY_ORDER[overall] == max(
            SEVERITY_ORDER[m["severity"]] for m in matches.values()
        )

    def test_matching_is_case_insensitive(self):
        lower, _ = analyse_text("i want to die")
        upper, _ = analyse_text("I WANT TO DIE")
        assert RiskCategory.SELF_HARM in lower
        assert RiskCategory.SELF_HARM in upper

    def test_multiple_hits_produce_multiple_snippets(self):
        matches, _ = analyse_text("bullying now, still bullying me every day")
        assert len(matches[RiskCategory.BULLYING]["snippets"]) >= 2


class TestCrudeStem:
    @pytest.mark.parametrize(
        "word,expected",
        [
            ("running", "runn"),
            ("bullies", "bull"),
            ("failed", "fail"),
            ("drugs", "drug"),
        ],
    )
    def test_strips_common_suffixes(self, word, expected):
        assert _crude_stem(word) == expected

    def test_short_words_untouched(self):
        # Guard against over-stemming: "is" must not lose its 's'.
        assert _crude_stem("is") == "is"
        assert _crude_stem("ed") == "ed"


class TestNlpClassify:
    def test_empty_text_returns_empty(self):
        assert nlp_classify("") == ({}, 0.0)
        assert nlp_classify("   ") == ({}, 0.0)

    def test_flags_category_above_threshold(self):
        scores, overall = nlp_classify("suicide suicide die death")
        assert RiskCategory.SELF_HARM in scores
        assert overall == max(scores.values())
        assert 0.0 < overall <= 1.0

    def test_neutral_text_scores_nothing(self):
        scores, overall = nlp_classify("the timetable meeting room booking system")
        assert scores == {}
        assert overall == 0.0


class TestIsSelfHarmCase:
    def test_true_when_regex_flags_self_harm(self):
        matches, _ = analyse_text("I want to die")
        assert is_self_harm_case(matches, {}) is True

    def test_true_when_nlp_score_high_enough(self):
        assert is_self_harm_case({}, {RiskCategory.SELF_HARM: 0.2}) is True

    def test_false_when_nlp_below_cutoff(self):
        assert is_self_harm_case({}, {RiskCategory.SELF_HARM: 0.1}) is False

    def test_false_on_empty_inputs(self):
        assert is_self_harm_case({}, {}) is False
        assert is_self_harm_case(None, None) is False
