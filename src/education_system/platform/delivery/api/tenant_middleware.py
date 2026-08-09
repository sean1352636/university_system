"""Flask before_request middleware for multi-tenant request resolution.

Tenant identity is authoritative only when it comes from the authenticated
session/JWT.  Headers, subdomains and query parameters are treated as
untrusted consistency assertions and can never select a tenant.

When no tenant is found and the path is not exempt:
* 404 — tenant not in the database
* 403 — tenant exists but is_active = False

Exempt path prefixes (tenant resolution is skipped entirely)
------------------------------------------------------------
* ``/api/v1/tenants/``   — tenant management CRUD
* ``/health``
* ``/metrics``
* ``/parent/``           — parent portal (uses its own auth flow)
* ``/api/v1/auth/``      — login / token endpoints

When no tenant is resolved AND the path is not exempt the request is allowed
through **without** a tenant context (single-tenant / legacy mode).  This
preserves full backward-compatibility.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

from flask import Flask, g, jsonify, request

from education_system.platform.kernel.core.tenant import Tenant, set_current_tenant, clear_current_tenant
from education_system.platform.kernel.core.tenant_models import (
    get_tenant_by_slug,
    get_tenant_by_subdomain,
    get_tenant_by_id,
    init_tenant_db,
)

logger = logging.getLogger(__name__)

# ── Paths that bypass tenant resolution entirely ─────────────────────────────

_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/tenants",
    "/api/v1/auth",
    "/api/auth",
    "/health",
    "/metrics",
    "/parent/",
    "/api/v1/health",
    "/api/health",
)


def _is_exempt(path: str) -> bool:
    """Return True if *path* should skip tenant resolution."""
    for prefix in _EXEMPT_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


# ── Subdomain extraction ──────────────────────────────────────────────────────

def _extract_subdomain(host: str) -> str | None:
    """Extract the leftmost subdomain label from *host*.

    e.g. ``oakwood.school.example.com`` → ``"oakwood"``
         ``school.example.com``         → None  (only one level of sub)
         ``localhost``                  → None
    """
    if not host:
        return None
    # Strip port
    hostname = host.split(":")[0]
    parts = hostname.split(".")
    # Need at least 3 labels (sub.domain.tld) to have a meaningful subdomain
    if len(parts) >= 3:
        return parts[0]
    return None


# ── JWT claim extraction ──────────────────────────────────────────────────────

def _extract_jwt_tenant(auth_header: str) -> str | None:
    """Return a tenant claim from a *verified* bearer token."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        payload = None
        try:
            from education_system.platform.delivery.api.auth import decode_token
            payload = decode_token(token)
        except Exception:
            try:
                from flask import current_app
                from education_system.platform.delivery.api.university.auth import decode_token as uni_decode
                payload = uni_decode(token, current_app.config.get("API_CONFIG", {}))
            except Exception:
                return None
        tid = payload.get("tenant_id") or payload.get("tenant")
        return str(tid) if tid is not None else None
    except Exception:
        return None


# ── Core resolution logic ─────────────────────────────────────────────────────

def _authenticated_tenant_id() -> str | None:
    """Get tenant identity only from request authentication context."""
    current = getattr(g, "current_user", None)
    if isinstance(current, dict):
        value = current.get("tenant_id") or current.get("tenant") or current.get("institution_id")
        if value is not None:
            return str(value)
    return _extract_jwt_tenant(request.headers.get("Authorization", ""))


def _resolve_tenant(db_path: str | None = None) -> tuple[Tenant | None, str]:
    """Attempt to resolve the current tenant from the request context.

    Returns
    -------
    (tenant_or_None, source_description)
    """
    authenticated_tid = _authenticated_tenant_id()
    if authenticated_tid:
        tenant = _lookup_by_slug_or_id(authenticated_tid, db_path)
        if tenant:
            return tenant, "authenticated_session"

    return None, "none"


def _lookup_by_slug_or_id(value: str, db_path: str | None) -> Tenant | None:
    """Try slug lookup first, then numeric ID lookup."""
    tenant = get_tenant_by_slug(value, db_path=db_path)
    if tenant:
        return tenant
    if value.isdigit():
        return get_tenant_by_id(int(value), db_path=db_path)
    return None


# ── Middleware registration ───────────────────────────────────────────────────

def register_tenant_middleware(
    app: Flask,
    tenants_db_path: str | None = None,
    *,
    require_tenant: bool | None = None,
) -> None:
    """Attach tenant resolution hooks to *app*.

    Call this once during application factory setup, after other middleware.

    Parameters
    ----------
    app:
        The Flask application.
    tenants_db_path:
        Override path for the central tenants database.  Defaults to the
        standard location (``shared/data/db_files/tenants.db``).
    """
    if require_tenant is None:
        require_tenant = os.getenv("MULTI_TENANT_REQUIRED", "true").lower() == "true"

    # Ensure tenant schema exists
    try:
        init_tenant_db(tenants_db_path)
    except Exception as exc:
        logger.warning("Could not init tenant DB (non-fatal): %s", exc)

    @app.before_request
    def resolve_tenant():
        """Identify the tenant for this request and bind it to ``g``."""
        # Always start clean
        clear_current_tenant()
        g.tenant = None

        path = request.path
        if _is_exempt(path):
            return  # No tenant resolution needed

        header_tenant = request.headers.get("X-Tenant-ID")
        query_tenant = request.args.get("tenant")
        subdomain = _extract_subdomain(request.host or "")
        authenticated_tid = _authenticated_tenant_id()
        if not authenticated_tid:
            # Client-controlled tenant selectors are never sufficient.
            if header_tenant or query_tenant or subdomain:
                return jsonify({"error": "Authenticated tenant identity is required"}), 401
        for supplied in (header_tenant, query_tenant, subdomain):
            if supplied and authenticated_tid:
                asserted = _lookup_by_slug_or_id(supplied, tenants_db_path)
                claimed = _lookup_by_slug_or_id(authenticated_tid, tenants_db_path)
                if asserted is None or claimed is None or asserted.id != claimed.id:
                    return jsonify({"error": "Tenant identity mismatch"}), 403

        tenant, source = _resolve_tenant(db_path=tenants_db_path)

        if tenant is None:
            signalled = bool(
                header_tenant or query_tenant or subdomain or authenticated_tid
            )
            if signalled:
                return jsonify({"error": "Tenant not found"}), 404
            if require_tenant:
                return jsonify({"error": "Tenant identity is required"}), 400
            # Explicit compatibility mode for self-hosted single-tenant installs.
            return

        if not tenant.is_active:
            logger.warning(
                "Request to inactive tenant slug=%r from %s",
                tenant.slug, request.remote_addr,
            )
            return jsonify({"error": "Tenant is inactive"}), 403

        # Bind tenant for the duration of this request
        set_current_tenant(tenant)
        g.tenant = tenant
        logger.debug(
            "Resolved tenant slug=%r via %s for %s %s",
            tenant.slug, source, request.method, path,
        )

    @app.after_request
    def clear_tenant_context(response):
        """Clean up tenant context and add tenant header to response."""
        tenant = getattr(g, "tenant", None)
        if tenant:
            response.headers["X-Tenant-Slug"] = tenant.slug
        clear_current_tenant()
        return response

    logger.info("Tenant middleware registered")
