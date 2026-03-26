"""REST endpoints for tenant management.

Blueprint prefix: ``/api/v1/tenants/``

All endpoints require a valid JWT (``Authorization: Bearer <token>``).
Mutating endpoints (POST, PUT, DELETE) additionally require ``superadmin``
role.

Endpoints
---------
GET    /api/v1/tenants/                   — list all tenants
POST   /api/v1/tenants/                   — create + provision a new tenant
GET    /api/v1/tenants/<slug>             — get tenant details
PUT    /api/v1/tenants/<slug>             — update tenant config / metadata
DELETE /api/v1/tenants/<slug>             — deactivate tenant (soft delete)
POST   /api/v1/tenants/<slug>/provision   — (re-)provision tenant databases
GET    /api/v1/tenants/<slug>/stats       — user counts + DB sizes per system
POST   /api/v1/tenants/<slug>/users       — assign a user to a tenant
"""

from __future__ import annotations

import logging
import re

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.auth import token_required
from education_system.shared.core.tenant_models import (
    add_user_to_tenant,
    create_tenant,
    deactivate_tenant,
    get_all_tenants,
    get_tenant_by_slug,
    get_tenant_users,
    init_tenant_db,
    update_tenant,
)
from education_system.shared.core.tenant_config import (
    TenantConfig,
    get_tenant_config,
    update_tenant_config,
)
from education_system.shared.core.tenant_db import TenantDatabaseManager

logger = logging.getLogger(__name__)

# ── Blueprint ─────────────────────────────────────────────────────────────────

tenant_bp = Blueprint("tenants", __name__)

_tenants_db_path: str | None = None


def init_tenant_routes(tenants_db_path: str | None = None) -> None:
    """Configure the blueprint.  Call once during application setup."""
    global _tenants_db_path
    _tenants_db_path = tenants_db_path
    init_tenant_db(tenants_db_path)


# ── Access control helpers ────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


def _is_superadmin() -> bool:
    """Return True if the current JWT user has superadmin role."""
    user = getattr(g, "current_user", None)
    if not user:
        return False
    systems: list[dict] = user.get("systems", [])
    return any(s.get("role") == "superadmin" for s in systems)


def _require_superadmin():
    """Return a 403 response if the caller is not a superadmin, else None."""
    if not _is_superadmin():
        return jsonify({"error": "Superadmin role required"}), 403
    return None


def _tenant_to_dict(tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "subdomain": tenant.subdomain,
        "config": tenant.config,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at,
    }


# ── GET /api/v1/tenants/ ──────────────────────────────────────────────────────

@tenant_bp.route("/", methods=["GET"])
@token_required
def list_tenants():
    """Return all tenants.  Superadmin sees all; others see active only."""
    active_only = not _is_superadmin()
    tenants = get_all_tenants(active_only=active_only, db_path=_tenants_db_path)
    return jsonify({
        "tenants": [_tenant_to_dict(t) for t in tenants],
        "total": len(tenants),
    })


# ── POST /api/v1/tenants/ ─────────────────────────────────────────────────────

@tenant_bp.route("/", methods=["POST"])
@token_required
def create_tenant_endpoint():
    """Create a new tenant and provision its databases.

    Request body::

        {
            "name":      "Oakwood Academy",
            "slug":      "oakwood-academy",
            "subdomain": "oakwood",          // optional, defaults to slug
            "config":    { ... },            // optional TenantConfig dict
            "systems":   ["college", ...]    // optional, defaults to all
        }
    """
    err = _require_superadmin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name: str = (data.get("name") or "").strip()
    slug: str = (data.get("slug") or "").strip().lower()
    subdomain: str = (data.get("subdomain") or slug).strip().lower()
    config: dict = data.get("config") or {}
    systems: list[str] | None = data.get("systems") or None

    # Validate
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not slug:
        return jsonify({"error": "slug is required"}), 400
    if not _SLUG_RE.match(slug):
        return jsonify({"error": "slug must be lowercase alphanumeric with hyphens (3-64 chars)"}), 400

    # Duplicate check
    if get_tenant_by_slug(slug, db_path=_tenants_db_path):
        return jsonify({"error": f"Tenant with slug '{slug}' already exists"}), 409

    try:
        tenant = create_tenant(
            name=name,
            slug=slug,
            subdomain=subdomain,
            config=config,
            db_path=_tenants_db_path,
        )
    except Exception as exc:
        logger.error("create_tenant failed: %s", exc)
        return jsonify({"error": "Failed to create tenant", "detail": str(exc)}), 500

    # Provision databases (non-blocking — errors are logged, not fatal)
    try:
        provisioned = TenantDatabaseManager.provision_tenant(slug, systems=systems)
        logger.info("Tenant %r provisioned: %s", slug, provisioned)
    except Exception as exc:
        logger.error("provision_tenant failed for %r: %s", slug, exc)
        provisioned = {}

    return jsonify({
        "tenant": _tenant_to_dict(tenant),
        "provisioned": provisioned,
    }), 201


# ── GET /api/v1/tenants/<slug> ────────────────────────────────────────────────

@tenant_bp.route("/<slug>", methods=["GET"])
@token_required
def get_tenant_endpoint(slug: str):
    """Return full tenant details including config."""
    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    # Non-superadmins can only view active tenants
    if not tenant.is_active and not _is_superadmin():
        return jsonify({"error": "Tenant not found"}), 404

    cfg = get_tenant_config(slug, db_path=_tenants_db_path)
    result = _tenant_to_dict(tenant)
    result["tenant_config"] = cfg.to_dict()
    return jsonify(result)


# ── PUT /api/v1/tenants/<slug> ────────────────────────────────────────────────

@tenant_bp.route("/<slug>", methods=["PUT"])
@token_required
def update_tenant_endpoint(slug: str):
    """Update tenant name, subdomain, or configuration.

    Request body (all fields optional)::

        {
            "name":      "New Name",
            "subdomain": "new-sub",
            "config":    { ... }
        }
    """
    err = _require_superadmin()
    if err:
        return err

    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name")
    subdomain = data.get("subdomain")
    config = data.get("config")

    updated = update_tenant(
        tenant.id,
        name=name,
        subdomain=subdomain,
        config=config,
        db_path=_tenants_db_path,
    )
    if not updated:
        return jsonify({"error": "Update failed"}), 500

    refreshed = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    return jsonify({"tenant": _tenant_to_dict(refreshed)})


# ── DELETE /api/v1/tenants/<slug> ─────────────────────────────────────────────

@tenant_bp.route("/<slug>", methods=["DELETE"])
@token_required
def deactivate_tenant_endpoint(slug: str):
    """Soft-delete a tenant (marks is_active=0).  Does not remove data."""
    err = _require_superadmin()
    if err:
        return err

    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    deactivated = deactivate_tenant(tenant.id, db_path=_tenants_db_path)
    if not deactivated:
        return jsonify({"error": "Deactivation failed"}), 500

    return jsonify({"message": f"Tenant '{slug}' deactivated", "slug": slug})


# ── POST /api/v1/tenants/<slug>/provision ─────────────────────────────────────

@tenant_bp.route("/<slug>/provision", methods=["POST"])
@token_required
def provision_tenant_endpoint(slug: str):
    """(Re-)provision databases for an existing tenant.

    Optional request body::

        {"systems": ["college", "school"]}   // subset to provision
    """
    err = _require_superadmin()
    if err:
        return err

    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    data = request.get_json(silent=True) or {}
    systems = data.get("systems") or None

    try:
        provisioned = TenantDatabaseManager.provision_tenant(slug, systems=systems)
    except Exception as exc:
        logger.error("provision_tenant failed for %r: %s", slug, exc)
        return jsonify({"error": "Provisioning failed", "detail": str(exc)}), 500

    return jsonify({"slug": slug, "provisioned": provisioned})


# ── GET /api/v1/tenants/<slug>/stats ──────────────────────────────────────────

@tenant_bp.route("/<slug>/stats", methods=["GET"])
@token_required
def tenant_stats_endpoint(slug: str):
    """Return user counts and DB file sizes for a tenant."""
    err = _require_superadmin()
    if err:
        return err

    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    # DB sizes
    db_sizes = TenantDatabaseManager.get_tenant_db_sizes(slug)

    # User count
    users = get_tenant_users(tenant.id, active_only=False, db_path=_tenants_db_path)
    active_users = [u for u in users if u.get("is_active")]

    return jsonify({
        "slug": slug,
        "db_sizes_bytes": db_sizes,
        "db_sizes_human": {
            k: _human_size(v) for k, v in db_sizes.items()
        },
        "total_users": len(users),
        "active_users": len(active_users),
        "users_by_role": _count_by_role(users),
    })


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


def _count_by_role(users: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for u in users:
        role = u.get("role", "member")
        counts[role] = counts.get(role, 0) + 1
    return counts


# ── POST /api/v1/tenants/<slug>/users ─────────────────────────────────────────

@tenant_bp.route("/<slug>/users", methods=["POST"])
@token_required
def assign_user_to_tenant(slug: str):
    """Assign a user (by user_id) to a tenant with an optional role.

    Request body::

        {
            "user_id": 42,
            "role":    "admin"    // optional, default "member"
        }
    """
    err = _require_superadmin()
    if err:
        return err

    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "user_id must be an integer"}), 400

    role = str(data.get("role") or "member")

    success = add_user_to_tenant(
        tenant.id, user_id, role=role, db_path=_tenants_db_path
    )
    if not success:
        return jsonify({"error": "Failed to assign user to tenant"}), 500

    return jsonify({
        "message": f"User {user_id} assigned to tenant '{slug}' as '{role}'",
        "tenant_id": tenant.id,
        "user_id": user_id,
        "role": role,
    }), 201


# ── GET /api/v1/tenants/<slug>/users ─────────────────────────────────────────

@tenant_bp.route("/<slug>/users", methods=["GET"])
@token_required
def list_tenant_users(slug: str):
    """List all users assigned to a tenant."""
    err = _require_superadmin()
    if err:
        return err

    tenant = get_tenant_by_slug(slug, db_path=_tenants_db_path)
    if not tenant:
        return jsonify({"error": f"Tenant '{slug}' not found"}), 404

    active_only = request.args.get("active_only", "true").lower() != "false"
    users = get_tenant_users(tenant.id, active_only=active_only, db_path=_tenants_db_path)

    return jsonify({
        "tenant_slug": slug,
        "users": users,
        "total": len(users),
    })
