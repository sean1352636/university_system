from __future__ import annotations

from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.integrations.external import cross_system_bus as bus


def _failed_delivery(path: str) -> tuple[str, str]:
    initialise_auth_db(path)
    bus.clear_subscribers_for_test()

    def fail(_event: dict) -> None:
        raise RuntimeError("consumer unavailable")

    handler_name = "tests.always_fails"
    bus.subscribe("enrolment.changed", fail, handler_name=handler_name)
    event_id = bus.publish_cross_system(
        "enrolment.changed",
        source_system="university",
        source_module="test",
        target_system="university",
        db_path=path,
        student_id="S1",
    )
    bus.poll_and_dispatch("university", max_attempts=1, db_path=path)
    return event_id, handler_name


def test_failed_delivery_is_visible_as_dead_letter(tmp_path) -> None:
    path = str(tmp_path / "auth.db")
    event_id, _ = _failed_delivery(path)

    failures = bus.list_failed_deliveries(
        consumer_system="university",
        exhausted_only=True,
        max_attempts=1,
        db_path=path,
    )

    assert failures[0]["event_id"] == event_id
    assert failures[0]["dead_letter"] is True
    assert failures[0]["payload"]["student_id"] == "S1"


def test_new_dead_letter_emits_structured_operator_alert(tmp_path) -> None:
    alerts: list[dict] = []
    unsubscribe = bus.subscribe_delivery_alerts(alerts.append)
    try:
        event_id, handler_name = _failed_delivery(str(tmp_path / "auth.db"))
    finally:
        unsubscribe()

    assert len(alerts) == 1
    assert alerts[0]["event_id"] == event_id
    assert alerts[0]["event_name"] == "enrolment.changed"
    assert alerts[0]["consumer_system"] == "university"
    assert alerts[0]["consumer_handler"] == handler_name
    assert alerts[0]["attempts"] == 1


def test_operator_can_retry_or_abandon_failed_delivery(tmp_path) -> None:
    path = str(tmp_path / "auth.db")
    event_id, handler_name = _failed_delivery(path)

    assert bus.retry_failed_delivery(
        event_id, "university", handler_name, db_path=path
    )
    failures = bus.list_failed_deliveries(db_path=path)
    assert failures[0]["attempts"] == 0

    assert bus.abandon_failed_delivery(
        event_id,
        "university",
        handler_name,
        reason="Superseded by corrected enrolment event",
        db_path=path,
    )
    assert bus.list_failed_deliveries(db_path=path) == []
