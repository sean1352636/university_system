"""Tenant context management for multi-tenancy support.

Provides thread-local and contextvars storage for the current tenant, plus
a helper to resolve database paths per tenant.

When no tenant is set (single-tenant / legacy mode) all functions fall back
to the default behaviour — the system is fully backward-compatible.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Tenant dataclass ─────────────────────────────────────────────────────────

@dataclass
class Tenant:
    """Represents a single tenant (institution) in the multi-tenant system."""

    id: int
    name: str
    slug: str                       # URL-safe identifier, e.g. "oakwood-academy"
    subdomain: str                  # e.g. "oakwood" (used for subdomain routing)
    config: dict = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r} active={self.is_active}>"


# ── Storage: contextvars (async-safe) + thread-local fallback ────────────────

_tenant_var: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)
_thread_local = threading.local()


def get_current_tenant() -> Optional[Tenant]:
    """Return the active Tenant for the current context, or None."""
    tenant = _tenant_var.get(None)
    if tenant is not None:
        return tenant
    # Fall back to thread-local (useful in plain-thread contexts)
    return getattr(_thread_local, "tenant", None)


def set_current_tenant(tenant: Tenant) -> None:
    """Bind *tenant* as the active tenant for the current context/thread."""
    _tenant_var.set(tenant)
    _thread_local.tenant = tenant


def clear_current_tenant() -> None:
    """Remove any tenant binding for the current context/thread."""
    _tenant_var.set(None)
    _thread_local.tenant = None


@contextmanager
def tenant_context(tenant: Tenant):
    """Context manager that sets a tenant for the duration of a block.

    Example::

        with tenant_context(my_tenant):
            do_something()
    """
    token = _tenant_var.set(tenant)
    _thread_local.tenant = tenant
    try:
        yield tenant
    finally:
        _tenant_var.reset(token)
        _thread_local.tenant = None


# ── DB path resolution ───────────────────────────────────────────────────────

#: Maps system_key → default DB path resolver (lazy imports inside)
_DEFAULT_PATH_RESOLVERS: dict[str, str] = {
    "sixth_form": None,
    "secondary": None,
    "primary": None,
    "university": None,
    "auth": None,
}

# Base directory for tenant-specific databases.
#
# This was derived by walking up from ``__file__`` to a ``shared/`` directory
# that has not existed since the ADR 0018 move; it resolved to
# ``education_system/platform/shared/data/tenants``, i.e. it would have written
# tenant databases inside the importable package. Runtime state belongs under
# ``program/var`` (ADR 0018), alongside the tenant registry itself
# (``PLATFORM_DB_FILES_DIR/tenants.db``).
import os as _os
from education_system.paths import VAR_DIR as _VAR_DIR

_TENANTS_BASE = str(_VAR_DIR / "data" / "tenants")


def tenant_db_path(system_key: str) -> str:
    """Resolve the database path for *system_key* in the current tenant context.

    Multi-tenant mode
    -----------------
    When a tenant is active the path is::

        program/var/data/tenants/<tenant_slug>/<system_key>.db

    Single-tenant (default) mode
    ----------------------------
    When no tenant is set the default path for the system is returned, which
    is identical to the pre-multi-tenancy behaviour.
    """
    tenant = get_current_tenant()
    if tenant is not None:
        tenant_dir = _os.path.join(_TENANTS_BASE, tenant.slug)
        return _os.path.join(tenant_dir, f"{system_key}.db")

    # ── Fall back to each system's own default path ───────────────────────
    return _get_default_db_path(system_key)


def _get_default_db_path(system_key: str) -> str:
    """Return the default (single-tenant) database path for *system_key*."""
    try:
        if system_key == "university":
            from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
            return str(UNIVERSITY_DEFAULT_DB_PATH)
        if system_key == "auth":
            from education_system.platform.identity.auth.db import AUTH_DB_FILE
            return str(AUTH_DB_FILE)
    except ImportError:
        pass

    # Generic fallback: var/data/platform/db_files/<system_key>.db
    from education_system.paths import PLATFORM_DB_FILES_DIR

    return _os.path.join(str(PLATFORM_DB_FILES_DIR), f"{system_key}.db")
