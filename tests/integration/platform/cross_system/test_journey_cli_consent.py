"""journey_cli promotion: consent is asked for, required, and passed through.

The system promoters are replaced with fakes, so no system module or
database is loaded.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import journey_cli


def _answers(*values):
    it = iter(values)
    return lambda _prompt="": next(it)


def test_nursery_to_primary_requires_medical_consent():
    assert "medical_alerts" in journey_cli.consent_requirements("nursery")
    # The safeguarding reference is statutory, never a consent question.
    assert "safeguarding_reference" not in journey_cli.consent_requirements(
        "nursery")


@pytest.fixture
def fake_nursery(monkeypatch):
    calls = []

    def move(child_id, *, consent=None, safeguarding_reference=None):
        calls.append((child_id, consent, safeguarding_reference))
        return "moved"

    def consent_for(*, medical, support):
        return ({"medical_alerts"} if medical else set()) | (
            {"send_support"} if support else set())

    monkeypatch.setattr(journey_cli, "_resolve", lambda system: move)
    monkeypatch.setattr(journey_cli, "_consent_builder",
                        lambda system: consent_for)
    return calls


def test_without_medical_consent_the_promotion_is_refused(fake_nursery):
    out = []
    journey_cli.prompt_and_promote(
        "nursery", input_fn=_answers("N1", "n", "y", ""), output_fn=out.append)
    assert fake_nursery == []
    assert any("medical_alerts" in line and "Cannot promote" in line
               for line in out)


def test_consent_and_reference_are_passed_through(fake_nursery):
    out = []
    journey_cli.prompt_and_promote(
        "nursery", input_fn=_answers("N1", "y", "n", "SG-7"),
        output_fn=out.append)
    assert fake_nursery == [("N1", {"medical_alerts"}, "SG-7")]


def test_a_promoter_without_consent_is_not_asked(monkeypatch):
    calls = []

    def mark(student_id, *, moved_by=None):
        calls.append(student_id)

    monkeypatch.setattr(journey_cli, "_resolve", lambda system: mark)
    journey_cli.prompt_and_promote("sixth_form", input_fn=_answers("SF1"),
                                   output_fn=lambda *_a: None)
    assert calls == ["SF1"]


def test_promote_refuses_arguments_the_promoter_cannot_take(monkeypatch):
    monkeypatch.setattr(journey_cli, "_resolve",
                        lambda system: (lambda sid, *, moved_by=None: None))
    with pytest.raises(ValueError, match="consent"):
        journey_cli.promote("sixth_form", "SF1", consent=True)


def test_all_or_nothing_consent_without_a_builder(monkeypatch):
    monkeypatch.setattr(journey_cli, "_consent_builder", lambda system: None)
    assert journey_cli.build_consent("primary", medical=True, support=True) is True
    assert journey_cli.build_consent("primary", medical=True, support=False) is None
