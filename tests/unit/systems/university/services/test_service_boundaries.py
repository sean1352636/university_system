from education_system.systems.university.services.events import in_process
from education_system.systems.university.shared.ai.features import nlp_engine


def test_event_bus_isolates_consumer_crashes_and_unsubscribe_is_idempotent():
    in_process.reset_for_tests()
    seen = []

    def broken(**_payload):
        raise RuntimeError("consumer crashed")

    unsubscribe = in_process.subscribe(in_process.EVENT_GRADE_CHANGED, broken)
    in_process.subscribe(in_process.EVENT_GRADE_CHANGED, lambda **p: seen.append(p["grade"]))
    in_process.publish(in_process.EVENT_GRADE_CHANGED, grade="A")
    assert seen == ["A"]
    unsubscribe()
    unsubscribe()
    in_process.reset_for_tests()


def test_service_sentiment_handles_empty_and_conflicting_text_deterministically(monkeypatch):
    monkeypatch.setattr(nlp_engine, "_vader", None)
    monkeypatch.setattr(nlp_engine, "_vader_tried", True)
    assert nlp_engine.analyze_sentiment_text("") == ("neutral", 0.5)
    sentiment, score = nlp_engine.analyze_sentiment_text("good but confusing")
    assert sentiment == "neutral"
    assert 0.0 <= score <= 1.0
