"""Per-tenant configuration management.

Each tenant can override global defaults via a ``TenantConfig`` that is
persisted as JSON inside the ``tenants.config_json`` column.

Usage::

    cfg = get_tenant_config("oakwood-academy")
    if cfg.feature_flags.get("parent_portal"):
        ...
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Sub-dataclasses ───────────────────────────────────────────────────────────

@dataclass
class BrandingConfig:
    """Visual / identity settings for a tenant."""
    school_name: str = ""
    logo_url: str = ""
    primary_color: str = "#1a73e8"   # Google-blue default
    secondary_color: str = "#fbbc04"
    favicon_url: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "BrandingConfig":
        return cls(
            school_name=d.get("school_name", ""),
            logo_url=d.get("logo_url", ""),
            primary_color=d.get("primary_color", "#1a73e8"),
            secondary_color=d.get("secondary_color", "#fbbc04"),
            favicon_url=d.get("favicon_url", ""),
        )

    def to_dict(self) -> dict:
        return {
            "school_name": self.school_name,
            "logo_url": self.logo_url,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "favicon_url": self.favicon_url,
        }


@dataclass
class LimitsConfig:
    """Resource / capacity limits for a tenant."""
    max_students: int = 5000
    max_staff: int = 500
    max_storage_mb: int = 10240        # 10 GB default
    max_api_requests_per_minute: int = 1000

    @classmethod
    def from_dict(cls, d: dict) -> "LimitsConfig":
        return cls(
            max_students=int(d.get("max_students", 5000)),
            max_staff=int(d.get("max_staff", 500)),
            max_storage_mb=int(d.get("max_storage_mb", 10240)),
            max_api_requests_per_minute=int(d.get("max_api_requests_per_minute", 1000)),
        )

    def to_dict(self) -> dict:
        return {
            "max_students": self.max_students,
            "max_staff": self.max_staff,
            "max_storage_mb": self.max_storage_mb,
            "max_api_requests_per_minute": self.max_api_requests_per_minute,
        }


# ── Main config dataclass ─────────────────────────────────────────────────────

@dataclass
class TenantConfig:
    """Full per-tenant configuration.

    Attributes
    ----------
    branding:
        Visual / identity settings.
    feature_flags:
        Mapping of feature-key → bool.  Use ``cfg.feature_flags.get("x", True)``
        to fall back to enabled when not explicitly set.
    limits:
        Capacity / resource limits.
    modules:
        List of enabled module keys.  Empty list = all modules enabled.
    extra:
        Arbitrary additional configuration keys (forward-compat).
    """

    branding: BrandingConfig = field(default_factory=BrandingConfig)
    feature_flags: dict[str, bool] = field(default_factory=dict)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    modules: list[str] = field(default_factory=list)   # empty = all enabled
    extra: dict[str, Any] = field(default_factory=dict)

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: dict) -> "TenantConfig":
        return cls(
            branding=BrandingConfig.from_dict(d.get("branding", {})),
            feature_flags=dict(d.get("feature_flags", {})),
            limits=LimitsConfig.from_dict(d.get("limits", {})),
            modules=list(d.get("modules", [])),
            extra={k: v for k, v in d.items()
                   if k not in ("branding", "feature_flags", "limits", "modules")},
        )

    def to_dict(self) -> dict:
        d: dict = {
            "branding": self.branding.to_dict(),
            "feature_flags": self.feature_flags,
            "limits": self.limits.to_dict(),
            "modules": self.modules,
        }
        d.update(self.extra)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    # ── Convenience helpers ───────────────────────────────────────────────

    def is_module_enabled(self, module_key: str) -> bool:
        """Return True if *module_key* is enabled for this tenant.

        When ``modules`` is empty every module is considered enabled.
        """
        if not self.modules:
            return True
        return module_key in self.modules

    def is_feature_enabled(self, feature_key: str, default: bool = True) -> bool:
        """Return the feature flag value, falling back to *default*."""
        return bool(self.feature_flags.get(feature_key, default))


# ── DB-backed accessors ───────────────────────────────────────────────────────

def get_tenant_config(tenant_slug: str, db_path: str | None = None) -> TenantConfig:
    """Load and return the ``TenantConfig`` for *tenant_slug*.

    Falls back to a default ``TenantConfig`` if the tenant is not found or
    its config JSON is malformed.
    """
    from education_system.shared.core.tenant_models import get_tenant_by_slug

    tenant = get_tenant_by_slug(tenant_slug, db_path=db_path)
    if tenant is None:
        logger.warning("get_tenant_config: tenant %r not found, using defaults", tenant_slug)
        return TenantConfig()

    try:
        return TenantConfig.from_dict(tenant.config or {})
    except Exception as exc:
        logger.error(
            "get_tenant_config: failed to parse config for %r: %s", tenant_slug, exc
        )
        return TenantConfig()


def update_tenant_config(
    tenant_slug: str,
    config: dict | TenantConfig,
    db_path: str | None = None,
) -> bool:
    """Persist updated configuration for *tenant_slug*.

    *config* may be a plain dict or a ``TenantConfig`` instance.
    Returns True on success, False if the tenant was not found.
    """
    from education_system.shared.core.tenant_models import (
        get_tenant_by_slug,
        update_tenant,
    )

    if isinstance(config, TenantConfig):
        config_dict = config.to_dict()
    else:
        config_dict = dict(config)

    tenant = get_tenant_by_slug(tenant_slug, db_path=db_path)
    if tenant is None:
        logger.warning("update_tenant_config: tenant %r not found", tenant_slug)
        return False

    return update_tenant(tenant.id, config=config_dict, db_path=db_path)
