from __future__ import annotations

import pytest

from education_system.systems.university.services.events import in_process


def test_publish_and_unsubscribe() -> None:
    in_process.reset_for_tests()
    received = []
    unsubscribe = in_process.subscribe(
        in_process.EVENT_ENROLMENT_CHANGED,
        lambda **payload: received.append(payload),
    )

    in_process.publish(in_process.EVENT_ENROLMENT_CHANGED, student_id="S1")
    unsubscribe()
    unsubscribe()
    in_process.publish(in_process.EVENT_ENROLMENT_CHANGED, student_id="S2")

    assert received == [{"student_id": "S1"}]


def test_unknown_contract_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown university event"):
        in_process.publish("typo.enrolment")
