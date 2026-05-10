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
    "college": None,
    "school": None,
    "primary": None,
    "university": None,
    "auth": None,
}

# Base directory for tenant-specific databases
import os as _os
_SHARED_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))  # …/shared/
)
_TENANTS_BASE = _os.path.join(
    _os.path.dirname(_SHARED_ROOT),  # …/education_system/
    "shared", "data", "tenants",
)


def tenant_db_path(system_key: str) -> str:
    """Resolve the database path for *system_key* in the current tenant context.

    Multi-tenant mode
    -----------------
    When a tenant is active the path is::

        <education_system>/shared/data/tenants/<tenant_slug>/<system_key>.db

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
            from education_system.university_system.core.paths import DEFAULT_DB_PATH
            return str(DEFAULT_DB_PATH)
        if system_key == "auth":
            from education_system.shared.auth.db import AUTH_DB_FILE
            return str(AUTH_DB_FILE)
    except ImportError:
        pass

    # Generic fallback: shared/data/db_files/<system_key>.db
    return _os.path.join(
        _SHARED_ROOT, "data", "db_files", f"{system_key}.db"
    )
