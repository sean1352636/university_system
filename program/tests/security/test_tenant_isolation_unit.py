"""Tenant DB access must derive scope from the bound context, not a parameter.

Covers task 3.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.security

# tenant_db imports get_current_tenant lazily inside its functions, so the
# patch target is the source module, not tenant_db.
TENANT_SRC = "education_system.platform.kernel.core.tenant.get_current_tenant"


class _Tenant:
    def __init__(self, slug):
        self.slug = slug


def test_unbound_context_refuses_arbitrary_slug():
    from education_system.platform.kernel.core.tenant_db import TenantDatabaseManager

    with patch(TENANT_SRC, return_value=None):
        with pytest.raises(PermissionError):
            # No tenant bound and no explicit opt-in -> must refuse.
            TenantDatabaseManager.get_tenant_connection("acme", "university")


def test_mismatched_bound_tenant_is_rejected():
    from education_system.platform.kernel.core.tenant_db import TenantDatabaseManager

    with patch(TENANT_SRC, return_value=_Tenant("acme")):
        with pytest.raises(PermissionError):
            TenantDatabaseManager.get_tenant_connection("other", "university")


def test_cross_tenant_delete_blocked_when_bound():
    from education_system.platform.kernel.core.tenant_db import TenantDatabaseManager

    with patch(TENANT_SRC, return_value=_Tenant("acme")):
        with pytest.raises(PermissionError):
            TenantDatabaseManager.delete_tenant_data("victim-tenant")


def test_university_get_connection_is_tenant_aware_when_bound(tmp_path):
    """When a tenant is bound, university get_connection resolves its DB path."""
    from education_system.systems.university.infrastructure.database import db

    fake_path = str(tmp_path / "acme_university.db")
    with patch(
        "education_system.platform.kernel.core.tenant.get_current_tenant",
        return_value=_Tenant("acme"),
    ), patch(
        "education_system.platform.kernel.core.tenant.tenant_db_path",
        return_value=fake_path,
    ):
        assert db._resolve_default_target() == fake_path


def test_university_get_connection_default_when_unbound():
    from education_system.systems.university.infrastructure.database import db

    with patch(
        "education_system.platform.kernel.core.tenant.get_current_tenant",
        return_value=None,
    ):
        assert db._resolve_default_target() == db.DEFAULT_DB_PATH
