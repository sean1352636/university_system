"""Secret handling: no hardcoded/default signing keys, fail-closed in prod.

Covers task 6 (remove secrets from source; prohibit empty/default signing
keys; fail startup when required production secrets are absent).
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.security


def test_no_emergency_unlock_default_in_source():
    """The break-glass password must not have a hardcoded default anywhere."""
    from education_system.systems.university.infrastructure.auth.managers import (
        account_security,
    )

    src = account_security.__file__
    with open(src, encoding="utf-8") as f:
        text = f.read()
    assert "UnlockMe2024" not in text, "hardcoded emergency-unlock password still present"


def test_csrf_middleware_requires_secret_in_production(as_production):
    from education_system.platform.governance.security import csrf

    class _FakeApp:
        config = {"SESSION_COOKIE_NAME": "session"}

        def before_request(self, fn):
            return fn

    with as_production(CSRF_SECRET=None):
        with pytest.raises(RuntimeError, match="CSRF_SECRET"):
            csrf.register_csrf_middleware(_FakeApp())


def test_csrf_middleware_ok_in_development(as_development):
    from education_system.platform.governance.security import csrf

    class _FakeApp:
        config = {"SESSION_COOKIE_NAME": "session"}

        def before_request(self, fn):
            return fn

    with as_development(CSRF_SECRET=None):
        csrf.register_csrf_middleware(_FakeApp())  # must not raise


def test_api_key_pepper_fails_closed_in_production(as_production):
    from education_system.platform.delivery.api import api_keys

    with as_production(API_KEY_PEPPER=None):
        with pytest.raises(RuntimeError, match="API_KEY_PEPPER"):
            api_keys._resolve_pepper()


def test_base_config_secret_fails_closed_in_production(as_production):
    from education_system.platform.delivery.api import base_config

    with as_production(API_SECRET_KEY=None):
        with pytest.raises(RuntimeError, match="API_SECRET_KEY"):
            base_config._secret_key()


def test_log_hmac_key_fails_closed_in_production(as_production):
    from education_system.platform.governance.security import log_integrity

    with as_production(LOG_HMAC_KEY=None):
        with pytest.raises(RuntimeError, match="LOG_HMAC_KEY"):
            log_integrity._resolve_key()


def test_core_api_refuses_default_signing_key_in_production(as_production):
    from education_system.platform.delivery.api.university import core_api

    with as_production(JWT_SECRET_KEY=None, API_SECRET_KEY=None):
        with pytest.raises(RuntimeError):
            core_api.create_core_app(validate_schema=False)
