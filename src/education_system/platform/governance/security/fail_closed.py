"""Fail-closed helpers for security control points.

A security check has exactly two acceptable outcomes: it *allowed* the
operation because it positively verified something, or it *denied* the
operation. "The check raised, so we carried on" is not one of them — yet that
is what a bare ``except Exception: pass`` around a permission lookup, an audit
write, a signature verification or an MFA query produces. The failure mode is
the worst possible one: the control silently stops applying, and because
nothing raises, nothing alerts.

This module gives those call sites a shape that cannot fail open:

* :class:`SecurityControlError` — raised when a control could not complete.
  Callers must let it propagate (or convert it to a denial); it deliberately
  does *not* subclass anything an existing broad handler is likely to catch by
  accident.
* :func:`security_critical` — a context manager that converts any unexpected
  exception into a logged, alerted :class:`SecurityControlError`.
* :func:`deny_on_error` — the same idea for functions returning a boolean
  decision, where the safe answer is ``False``.
* :func:`alert_security_failure` — records a control failure to the audit log
  and the alert channel, so an operator sees a control that has stopped
  working rather than a quiet gap in the evidence.

The distinction that matters when applying these: a control that *did* run and
said "no" raises the domain's own error (``AuthError``, ``PermissionError``).
A control that *could not run* raises :class:`SecurityControlError`. Both deny;
only the second is an operational alert.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

logger = logging.getLogger(__name__)

__all__ = [
    "SecurityControlError",
    "alert_security_failure",
    "security_critical",
    "deny_on_error",
]

T = TypeVar("T")


class SecurityControlError(Exception):
    """A security control could not be evaluated, so the operation is denied.

    Raised when the *mechanism* failed — the permissions table was
    unreadable, the audit write errored, the signature library was missing,
    the session store timed out. It is not raised when a control ran and
    returned "denied"; that is the caller's own domain error.

    Deriving straight from ``Exception`` (not ``ValueError`` or ``RuntimeError``)
    is intentional: it must not be swallowed by handlers written for ordinary
    application errors.
    """

    def __init__(self, control: str, message: str = "", *, cause: BaseException | None = None):
        self.control = control
        detail = f": {message}" if message else ""
        super().__init__(f"Security control {control!r} could not be evaluated{detail}")
        self.__cause__ = cause


def alert_security_failure(
    control: str,
    detail: str,
    *,
    user_id: Any = None,
    severity: str = "high",
    exc: BaseException | None = None,
) -> None:
    """Log and raise an operational alert for a failed security control.

    Never raises: alerting is best-effort by nature, and a broken alert
    channel must not mask the denial the caller is already performing. The
    ``logger.critical`` call is the floor — it lands in the structured log
    even if every downstream sink is unavailable.
    """
    logger.critical(
        "SECURITY CONTROL FAILURE: %s — %s (user_id=%s, severity=%s)",
        control, detail, user_id, severity,
        exc_info=exc if exc is not None else False,
        extra={
            "event": "security_control_failure",
            "control": control,
            "severity": severity,
            "user_id": user_id,
        },
    )

    # Audit trail. A control failure is itself an auditable event — without
    # this row there is no record that the control stopped applying, and a
    # later investigation sees an unexplained gap rather than a known outage.
    try:
        from education_system.platform.governance.audit.audit_service import AuditService

        AuditService().log_security(
            action="security_control_failure",
            user_id=user_id if isinstance(user_id, int) else None,
            resource_type="security_control",
            resource_id=control,
            details={"detail": detail, "severity": severity},
        )
    except Exception:  # noqa: BLE001 — alerting must never mask the denial
        logger.debug("Audit sink unavailable for control failure %s", control, exc_info=True)

    # Operational metric, so a control that has begun failing shows up on a
    # dashboard and can be alerted on by rate rather than by log grep.
    try:
        from education_system.platform.kernel.core.metrics import metrics

        metrics.increment(
            "security_control_failures_total",
            labels={"control": control, "severity": severity},
        )
    except Exception:  # noqa: BLE001 — ditto
        logger.debug("Metrics sink unavailable for control failure %s", control, exc_info=True)


@contextmanager
def security_critical(
    control: str,
    *,
    user_id: Any = None,
    expected: tuple[type[BaseException], ...] = (),
    severity: str = "high",
    rollback: Callable[[], Any] | None = None,
) -> Iterator[None]:
    """Run a security control, converting any unexpected failure into a denial.

    Args:
        control: Name of the control, used in the alert and the raised error
            (e.g. ``"mfa.lookup"``, ``"audit.write"``, ``"session.validate"``).
        user_id: Subject of the check, recorded on the alert.
        expected: Exception types that represent a *decided* outcome and
            should propagate unchanged — typically the domain's own denial
            error, e.g. ``(AuthError,)``. Everything else becomes a
            :class:`SecurityControlError`.
        severity: Alert severity.
        rollback: Called before raising, to undo a partially applied change.
            Its own failure is logged and does not replace the original error.

    Raises:
        SecurityControlError: if the block raised anything not in ``expected``.

    Example:
        with security_critical("mfa.lookup", user_id=uid, expected=(AuthError,)):
            mfa_required = mfa_service.is_required(uid)
        # A DB error here denies the login instead of skipping MFA.
    """
    try:
        yield
    except expected:
        # A decided outcome — the control ran and said no. Propagate as-is.
        raise
    except SecurityControlError:
        # Already converted further down; do not double-alert.
        raise
    except BaseException as exc:
        if rollback is not None:
            try:
                rollback()
            except Exception:  # noqa: BLE001
                logger.error("Rollback for %s failed", control, exc_info=True)
        alert_security_failure(control, str(exc) or type(exc).__name__,
                               user_id=user_id, severity=severity, exc=exc)
        raise SecurityControlError(control, str(exc), cause=exc) from exc


def deny_on_error(
    control: str,
    func: Callable[[], bool],
    *,
    user_id: Any = None,
    expected: tuple[type[BaseException], ...] = (),
    severity: str = "high",
) -> bool:
    """Evaluate a boolean control, returning ``False`` if it cannot be evaluated.

    For control points whose contract is already "return True to allow", where
    raising would be a larger change than the security fix warrants. The
    failure is still alerted — the difference from a bare ``except: return
    False`` is that this leaves evidence.

    Args:
        control: Control name for the alert.
        func: Zero-argument callable returning the allow/deny decision.
        user_id: Subject of the check.
        expected: Exception types that should propagate unchanged.
        severity: Alert severity.

    Returns:
        The control's decision, or ``False`` if it could not be evaluated.
    """
    try:
        return bool(func())
    except expected:
        raise
    except BaseException as exc:
        alert_security_failure(control, str(exc) or type(exc).__name__,
                               user_id=user_id, severity=severity, exc=exc)
        return False
