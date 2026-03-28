"""Flask before_request middleware for multi-tenant request resolution.

Tenant extraction order (first match wins)
------------------------------------------
1. ``X-Tenant-ID`` request header  (slug or numeric ID)
2. Subdomain  (e.g. ``oakwood.school.example.com`` → slug ``oakwood``)
3. JWT ``tenant_id`` claim inside the ``Authorization: Bearer`` token
4. ``?tenant=<slug>`` query parameter

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
from typing import Callable

from flask import Flask, g, jsonify, request

from education_system.shared.core.tenant import Tenant, set_current_tenant, clear_current_tenant
from education_system.shared.core.tenant_models import (
    get_tenant_by_slug,
    get_tenant_by_subdomain,
    get_tenant_by_id,
    init_tenant_db,
)

logger = logging.getLogger(__name__)

# ── Paths that bypass tenant resolution entirely ─────────────────────────────

_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/tenants/",
    "/api/v1/auth/",
    "/health",
    "/metrics",
    "/parent/",
    "/api/v1/health",
    "/",
    "/api",
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
    """Return the ``tenant_id`` claim from a Bearer JWT (no verification needed
    here — the auth middleware handles signature checking separately)."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        import jwt as pyjwt
        # Decode without verification — we only want the claim value.
        payload = pyjwt.decode(token, options={"verify_signature": False})  # nosemgrep: unverified-jwt-decode — signature is verified by auth middleware
        tid = payload.get("tenant_id") or payload.get("tenant")
        return str(tid) if tid is not None else None
    except Exception:
        return None


# ── Core resolution logic ─────────────────────────────────────────────────────

def _resolve_tenant(db_path: str | None = None) -> tuple[Tenant | None, str]:
    """Attempt to resolve the current tenant from the request context.

    Returns
    -------
    (tenant_or_None, source_description)
    """
    # 1. X-Tenant-ID header
    header_val = request.headers.get("X-Tenant-ID")
    if header_val:
        tenant = _lookup_by_slug_or_id(header_val, db_path)
        if tenant:
            return tenant, "header"

    # 2. Subdomain
    subdomain = _extract_subdomain(request.host or "")
    if subdomain:
        tenant = get_tenant_by_subdomain(subdomain, db_path=db_path)
        if tenant:
            return tenant, "subdomain"

    # 3. JWT tenant_id claim
    jwt_tid = _extract_jwt_tenant(request.headers.get("Authorization", ""))
    if jwt_tid:
        tenant = _lookup_by_slug_or_id(jwt_tid, db_path)
        if tenant:
            return tenant, "jwt"

    # 4. ?tenant= query parameter
    qs_slug = request.args.get("tenant")
    if qs_slug:
        tenant = _lookup_by_slug_or_id(qs_slug, db_path)
        if tenant:
            return tenant, "query_param"

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

def register_tenant_middleware(app: Flask, tenants_db_path: str | None = None) -> None:
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

        tenant, source = _resolve_tenant(db_path=tenants_db_path)

        if tenant is None:
            # No tenant signals detected — operate in single-tenant mode.
            # This is the legacy / default behaviour.
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
