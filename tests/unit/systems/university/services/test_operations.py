from __future__ import annotations

from education_system.systems.university.services.operations import (
    OperationResult,
    OperationStatus,
    OperationalFailure,
    OperationalIssue,
)


def test_success_is_serialisable() -> None:
    result = OperationResult.success({"student_id": "S1"}, correlation_id="c-1")

    assert result.ok
    assert result.to_dict()["value"] == {"student_id": "S1"}
    assert result.to_dict()["correlation_id"] == "c-1"


def test_retryable_issue_produces_retrying_result() -> None:
    issue = OperationalIssue(
        code="SMTP_UNAVAILABLE",
        message="Email service unavailable",
        retryable=True,
        component="email",
    )

    result = OperationResult.failure(issue)

    assert result.status is OperationStatus.RETRYING
    assert result.retryable
    assert not result.ok


def test_university_exception_keeps_structured_details() -> None:
    error = OperationalFailure(
        "Outbox unavailable",
        operation="publish",
        details={"event": "enrolment.changed"},
    )

    issue = OperationalIssue.from_exception(error, component="events")

    assert issue.code == "OPERATIONAL_FAILURE"
    assert issue.details["operation"] == "publish"
    assert issue.details["event"] == "enrolment.changed"
