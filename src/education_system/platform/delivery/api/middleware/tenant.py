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

import ipaddress

import logging
import os
from typing import Callable

from flask import Flask, g, jsonify, request

from education_system.platform.kernel.core.tenant import Tenant, set_current_tenant, clear_current_tenant
from education_system.platform.delivery.api.security_headers import is_development
from education_system.platform.kernel.core.tenant_models import (
    get_all_tenants,
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
         ``127.0.0.1``                  → None  (an address, not a name)

    An IP literal must never be read as a subdomain. Splitting
    ``127.0.0.1`` on dots yields four labels and would otherwise return
    ``"127"`` as a tenant selector — and because a client-supplied
    selector without an authenticated tenant is rejected outright, every
    request that reached the server by IP was answered with
    ``401 Authenticated tenant identity is required``. That is the normal
    way to reach a host on a LAN, from a load balancer, or from a
    container health check, so the whole app was unreachable by address
    while working fine via ``localhost``.
    """
    if not host:
        return None
    # Strip the port. rsplit, so an IPv6 literal's own colons survive.
    hostname = host.strip()
    if hostname.startswith("["):          # [::1]:5000
        hostname = hostname[1:].split("]", 1)[0]
    elif hostname.count(":") == 1:        # host:port
        hostname = hostname.rsplit(":", 1)[0]
    hostname = hostname.rstrip(".")       # trailing dot is a valid FQDN form
    if not hostname:
        return None

    try:
        ipaddress.ip_address(hostname)
        return None                       # an address has no subdomain
    except ValueError:
        pass

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
        configured = os.getenv("MULTI_TENANT_REQUIRED")
        if configured is not None:
            require_tenant = configured.strip().lower() == "true"
        else:
            # Unset: fail closed everywhere except a development APP_ENV.
            #
            # The previous default was an unconditional "true", which made a
            # local or test run reject every non-exempt request with 400
            # "Tenant identity is required" — there is no tenant to present,
            # and no way to create one that the resolver would accept. Hosted
            # deployments set MULTI_TENANT_REQUIRED explicitly (see
            # deploy/docker-stack.yml, deploy/kubernetes/base/configmap.yaml
            # and ADR 0019), so this fallback only ever governs local runs.
            require_tenant = not is_development()

    # Ensure tenant schema exists
    try:
        init_tenant_db(tenants_db_path)
    except Exception as exc:
        logger.warning("Could not init tenant DB (non-fatal): %s", exc)

    if require_tenant:
        # Requiring a tenant identity that cannot be produced rejects 100% of
        # traffic, and the per-request 400 does not say why. Say it once, at
        # startup, where an operator will see it.
        try:
            tenant_count = len(get_all_tenants(active_only=True,
                                               db_path=tenants_db_path))
        except Exception:
            tenant_count = None
        if tenant_count == 0:
            logger.error(
                "Tenant identity is required but no tenants exist in %s. Every "
                "non-exempt request will be rejected with 400. Provision a "
                "tenant via /api/v1/tenants, or set MULTI_TENANT_REQUIRED=false "
                "for a single-tenant install.",
                tenants_db_path or "the default tenants database",
            )

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
