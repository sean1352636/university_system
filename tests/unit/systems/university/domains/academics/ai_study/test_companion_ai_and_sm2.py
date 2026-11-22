"""SM-2 scheduling and the study companion's AI layer (Claude faked)."""

from __future__ import annotations

import json
import sys
import types
from datetime import date

import pytest

from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    companion_ai,
    spaced_repetition as sr,
)


# ---------------------------------------------------------------- SM-2
class TestSM2:
    def test_first_second_third_intervals(self):
        s1 = sr.schedule(quality=4, today=date(2026, 1, 1))
        s2 = sr.schedule(ease=s1["ease_factor"], interval=s1["interval_days"],
                         repetitions=s1["repetitions"], quality=4, today=date(2026, 1, 2))
        s3 = sr.schedule(ease=s2["ease_factor"], interval=s2["interval_days"],
                         repetitions=s2["repetitions"], quality=4, today=date(2026, 1, 8))
        assert [s1["interval_days"], s2["interval_days"], s3["interval_days"]] == [1, 6, 15]
        assert s1["next_review"] == "2026-01-02"

    def test_lapse_resets_run(self):
        s = sr.schedule(ease=2.5, interval=30, repetitions=5, quality=1)
        assert (s["interval_days"], s["repetitions"], s["lapsed"]) == (1, 0, True)

    def test_ease_floor(self):
        ease = 1.4
        for _ in range(5):
            ease = sr.schedule(ease=ease, interval=1, repetitions=0, quality=0)["ease_factor"]
        assert ease == sr.MIN_EASE

    def test_interval_cap(self):
        s = sr.schedule(ease=2.5, interval=300, repetitions=8, quality=5)
        assert s["interval_days"] == sr.MAX_INTERVAL_DAYS

    @pytest.mark.parametrize("given,expected", [
        ({"correct": True}, 4), ({"correct": False}, 1), ({"quality": "hard"}, 3),
        ({"quality": "Easy"}, 5), ({"quality": 2}, 2), ({"quality": "0"}, 0),
    ])
    def test_quality_for(self, given, expected):
        assert sr.quality_for(**given) == expected

    @pytest.mark.parametrize("bad", [{"quality": 6}, {"quality": "meh"}, {}])
    def test_quality_for_rejects(self, bad):
        with pytest.raises(ValueError):
            sr.quality_for(**bad)

    def test_retention(self):
        assert sr.retention([{"quality": 4}, {"quality": 1}]) == 50.0
        assert sr.retention([]) is None


# ------------------------------------------------- course-materials path
class TestWithoutAI:
    @pytest.fixture(autouse=True)
    def _off(self, monkeypatch):
        monkeypatch.setenv("STUDY_COMPANION_AI", "off")

    def test_explanation_is_grounded_and_says_so(self):
        material = {"module_code": "CS101", "module_name": "Programming", "aims": "Learn to code",
                    "topics": ["Recursion and the call stack"], "mentions":
                    ["Recursion and the call stack"], "description": ""}
        out = companion_ai.explain("Recursion", "Advanced", material)
        assert out["source"] == "course_materials" and out["model"] is None
        assert "Recursion and the call stack" in out["explanation"]
        assert "AI explanations are not available" in out["explanation"]

    def test_nothing_known_is_said_plainly(self):
        out = companion_ai.explain("Quasars", "Beginner", None)
        assert "do not mention Quasars" in out["explanation"]

    def test_long_concept_rejected(self):
        with pytest.raises(ValueError):
            companion_ai.explain("x" * 301)

    def test_notes_limit_is_reported_not_truncated(self):
        with pytest.raises(ValueError, match="limit"):
            companion_ai.cards_from_text("a" * (companion_ai.MAX_NOTES_CHARS + 1))

    @pytest.mark.parametrize("line,question", [
        ("Mitosis: cell division into two identical cells", "What is Mitosis?"),
        ("- Osmosis - movement of water across a membrane", "What is Osmosis?"),
        ("Entropy means the measure of disorder in a system.", "What is Entropy?"),
        ("A ledger is a record of financial transactions.", "What is ledger?"),
    ])
    def test_definition_extraction(self, line, question):
        cards = companion_ai.extract_definitions(line)
        assert cards and cards[0]["question"] == question

    def test_admin_lines_are_not_cards(self):
        assert companion_ai.extract_definitions("Note: lecture moved to room 4") == []


# --------------------------------------------------------- Claude (faked)
class _Block:
    def __init__(self, text):
        self.type, self.text = "text", text


class _Response:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


@pytest.fixture()
def fake_claude(monkeypatch):
    """A stand-in ``anthropic`` module; records each request."""
    calls, replies = [], []
    module = types.ModuleType("anthropic")

    class BadRequestError(Exception):
        pass

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return replies.pop(0)

    class _Client:
        def __init__(self):
            self.messages = _Messages()
            self.beta = types.SimpleNamespace(messages=_Messages())

    module.Anthropic = _Client
    module.BadRequestError = BadRequestError
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setenv("STUDY_COMPANION_AI", "on")
    return calls, replies


class TestWithClaude:
    def test_explanation_request_shape(self, fake_claude):
        calls, replies = fake_claude
        replies.append(_Response("Recursion is when a function calls itself."))
        out = companion_ai.explain("Recursion", "Beginner",
                                   {"module_code": "CS101", "module_name": "Prog", "topics": ["Loops"]})
        assert out == {"explanation": "Recursion is when a function calls itself.",
                       "source": "claude", "model": "claude-opus-5-5"}
        call = calls[0]
        assert call["model"] == "claude-opus-5-5"
        assert call["fallbacks"] == "default"
        assert call["betas"] == ["server-side-fallback-2026-07-01"]
        assert call["output_config"]["effort"] == "medium"
        assert "Academic integrity" in call["system"]
        assert "CS101" in call["messages"][0]["content"]

    def test_refusal_falls_back_to_course_materials(self, fake_claude):
        _, replies = fake_claude
        replies.append(_Response("", stop_reason="refusal"))
        assert companion_ai.explain("Recursion")["source"] == "course_materials"

    def test_cards_use_json_schema(self, fake_claude):
        calls, replies = fake_claude
        replies.append(_Response(json.dumps({"cards": [
            {"question": "What is recursion?", "answer": "Self-reference."},
            {"question": "What is recursion?", "answer": "Duplicate."}]})))
        out = companion_ai.cards_from_text("notes about recursion", 5)
        assert out == {"cards": [{"question": "What is recursion?", "answer": "Self-reference."}],
                       "source": "claude"}
        assert calls[0]["output_config"]["format"]["type"] == "json_schema"

    def test_unparseable_cards_fall_back(self, fake_claude):
        _, replies = fake_claude
        replies.append(_Response("not json"))
        out = companion_ai.cards_from_text("Mitosis: cell division", 5)
        assert out["source"] == "extracted" and out["cards"]

    def test_model_override(self, fake_claude, monkeypatch):
        calls, replies = fake_claude
        monkeypatch.setenv("STUDY_COMPANION_MODEL", "claude-sonnet-5-5")
        replies.append(_Response("ok"))
        companion_ai.explain("Loops")
        assert calls[0]["model"] == "claude-sonnet-5-5"
