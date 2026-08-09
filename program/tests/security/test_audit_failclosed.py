"""Audit logging must be mandatory and never silently suppressed.

Covers task 8: a required audit write that fails raises (so the surrounding
transaction can roll back), and every failure is routed to the alerting path.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.security

MOD = "education_system.systems.university.infrastructure.security.audit_helpers"
IMMUT = "education_system.systems.university.infrastructure.security.immutable_audit_log.log_security_event"


def test_required_audit_failure_raises():
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        AuditWriteError,
        safe_log_security_event,
    )

    with patch(IMMUT, side_effect=RuntimeError("db locked")):
        with patch(f"{MOD}._alert_audit_failure") as alert:
            with pytest.raises(AuditWriteError):
                safe_log_security_event("grade.update", user_id="u1", required=True)
            assert alert.called, "a failed required audit write must alert"


def test_non_required_audit_failure_still_alerts_but_returns_false():
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
    )

    with patch(IMMUT, side_effect=RuntimeError("db locked")):
        with patch(f"{MOD}._alert_audit_failure") as alert:
            result = safe_log_security_event("session.read", user_id="u1")
            assert result is False
            assert alert.called, "even non-required failures must never be silent"


def test_alert_helper_routes_to_fail_closed_alerter():
    from education_system.systems.university.infrastructure.security import audit_helpers

    target = "education_system.platform.governance.security.fail_closed.alert_security_failure"
    with patch(target) as alert:
        audit_helpers._alert_audit_failure("a", "grade", "1", "u1", RuntimeError("x"))
        assert alert.called
        assert alert.call_args.args[0] == "audit.write"


def test_success_path_returns_true():
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
    )

    with patch(IMMUT, return_value=None):
        assert safe_log_security_event("login.success", user_id="u1") is True
