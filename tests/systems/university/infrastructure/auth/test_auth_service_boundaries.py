from unittest.mock import Mock
from datetime import UTC, datetime

from education_system.systems.university.infrastructure.auth.audit.events import (
    AuditEvent,
)
from education_system.systems.university.infrastructure.auth.audit.service import (
    SecurityAuditService,
)
from education_system.systems.university.infrastructure.auth.authentication.service import (
    AuthenticationService,
)
from education_system.systems.university.infrastructure.auth.credentials.service import (
    CredentialService,
)
from education_system.systems.university.infrastructure.auth.recovery.service import (
    RecoveryService,
)
from education_system.systems.university.infrastructure.auth.sessions.service import (
    SessionService,
)


def test_authentication_service_delegates_login_and_logout():
    auth = Mock()
    service = AuthenticationService(auth)

    service.login("ada", "secret")
    service.logout()

    auth.login.assert_called_once_with("ada", "secret")
    auth.logout.assert_called_once_with()


def test_credential_service_delegates_password_change():
    auth = Mock()

    CredentialService(auth).change_password("ada", "old", "new")

    auth.change_password.assert_called_once_with("ada", "old", "new")


def test_session_service_exposes_validation_and_termination():
    auth = Mock()
    auth.check_session.return_value = True
    service = SessionService(auth)

    assert service.validate()
    service.terminate()

    auth.check_session.assert_called_once_with()
    auth.logout.assert_called_once_with()


def test_recovery_service_delegates_reset_and_unlock():
    auth = Mock()
    service = RecoveryService(auth)

    service.reset_password("ada")
    service.unlock_account(7)

    auth.reset_password.assert_called_once_with("ada")
    auth.unlock_account.assert_called_once_with(7)


def test_audit_service_serializes_event_to_immutable_store():
    store = Mock()
    event = AuditEvent(
        event_type="login.succeeded",
        occurred_at=datetime.now(UTC),
        principal_id=7,
        payload={"method": "password"},
    )

    SecurityAuditService(store).record(event)

    payload = store.append.call_args.args[0]
    assert payload["event_type"] == "login.succeeded"
    assert payload["payload"] == {"method": "password"}
