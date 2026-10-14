"""MFA must default to the shared auth store, not the university one.

``auth.db`` ids and university ``student_records.db`` ids are different id
spaces that collide: ``admin`` is 19 in auth.db, while university id 19 is a
student. ``MFAService`` used to default to the university database, so any
caller that omitted ``db_path`` — and they all hold *shared* ids — filed the
admin's MFA enrolment onto that student's row. ``_get_connection`` disables
foreign keys, so nothing raised; it just silently wrote to the wrong account.

These tests pin the store each entry point resolves to. If one flips back,
the failure mode is a cross-account MFA leak, not a crash.
"""

from __future__ import annotations

import pytest

from education_system import paths
from education_system.platform.identity.auth.mfa.service import MFAService


def _shared() -> str:
    return str(paths.PLATFORM_AUTH_DB)


def _university() -> str:
    return str(paths.UNIVERSITY_DEFAULT_DB_PATH)


@pytest.mark.unit
def test_the_two_stores_are_different_files():
    # The whole hazard rests on these being distinct; if they ever converge
    # the rest of these assertions stop meaning anything.
    assert _shared() != _university()


@pytest.mark.unit
def test_bare_service_uses_the_shared_auth_store():
    assert MFAService().db_path == _shared()


@pytest.mark.unit
def test_for_shared_auth_uses_the_shared_auth_store():
    assert MFAService.for_shared_auth().db_path == _shared()


@pytest.mark.unit
def test_module_level_helpers_use_the_shared_auth_store(monkeypatch):
    """setup_totp/verify_totp/... construct a bare MFAService internally."""
    from education_system.platform.identity.auth.mfa import service as svc

    seen = []

    class _Spy(MFAService):
        def __init__(self, db_path=None):
            super().__init__(db_path)
            seen.append(self.db_path)

        def setup_totp(self, *a, **k):
            return {"success": True}

    monkeypatch.setattr(svc, "MFAService", _Spy)
    svc.setup_totp(1, "someone")

    assert seen == [_shared()]


@pytest.mark.unit
def test_university_integration_keeps_the_legacy_university_store():
    """``MFAIntegration()`` is the deliberate university-local fallback.

    It is called bare with a *university* id when a login has no shared
    counterpart, so it must not follow MFAService's default.
    """
    from education_system.systems.university.infrastructure.auth.mfa_integration import (
        MFAIntegration,
    )

    assert MFAIntegration().mfa_service.db_path == _university()
    assert MFAIntegration(_shared()).mfa_service.db_path == _shared()
