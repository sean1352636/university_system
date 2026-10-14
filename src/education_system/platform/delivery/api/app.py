"""Application factory.

Builds the Flask app from the declarative mount table in
:mod:`.registry` rather than from a sequence of hand-written
``try/except`` blocks. Serving — choosing a host, a port, a WSGI server —
is the launcher's job and is deliberately not done here; a factory that
also runs a server cannot be imported by a test.

The old ``unified_server.py`` remains as a shim.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, redirect

from education_system.platform.delivery.api import registry
from education_system.platform.delivery.api.versioning import (
    API_VERSION,
    legacy_redirect_rules,
)

logger = logging.getLogger(__name__)


def _mount_systems(app: Flask) -> dict:
    """Register every wired system from the registry."""
    summary = {}
    for mount in registry.SYSTEMS:
        blueprints = mount.load()
        for blueprint in blueprints:
            prefix = registry.reprefix(blueprint.url_prefix, mount.key)
            try:
                app.register_blueprint(
                    blueprint,
                    url_prefix=prefix,
                    name=f"{mount.key}_{blueprint.name}",
                )
            except Exception as exc:
                logger.error("Mount %s: blueprint %s failed: %s",
                             mount.key, blueprint.name, exc)
        summary[mount.key] = len(blueprints)
        if blueprints:
            logger.info("Mounted %d %s blueprint(s) at %s",
                        len(blueprints), mount.label, mount.prefix)
        elif mount.wired:
            # A wired system contributing nothing is a fault, not a
            # quiet no-op. This is the failure mode that hid 62 missing
            # university route modules behind a single log line.
            logger.error("Mount %s is wired but contributed no blueprints: %s",
                         mount.key, mount.error or "unknown reason")
    return summary


def _mount_platform(app: Flask) -> None:
    """Register the non-system blueprints at the version root."""
    import importlib

    from education_system.platform.delivery.api.versioning import API_PREFIX

    for module_path, attr in registry.PLATFORM:
        try:
            module = importlib.import_module(module_path)
            blueprint = getattr(module, attr)
        except Exception as exc:
            logger.error("Platform blueprint %s.%s unavailable: %s",
                         module_path, attr, exc)
            continue
        prefix = blueprint.url_prefix
        if prefix and prefix.startswith("/api/") and not prefix.startswith(API_PREFIX):
            prefix = registry.reprefix(prefix, "").replace("//", "/")
        try:
            app.register_blueprint(blueprint, url_prefix=prefix or API_PREFIX)
        except Exception as exc:
            logger.error("Could not register %s: %s", attr, exc)


def create_app(config: dict | None = None) -> Flask:
    """Build and return the unified application.

    Does not serve. See ``launcher/`` for that.
    """
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("API_MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    if config:
        app.config.update(config)

    from education_system.platform.delivery.api.middleware import apply_all
    apply_all(app)

    _mount_platform(app)
    _mount_systems(app)

    for legacy, target in legacy_redirect_rules().items():
        app.add_url_rule(
            legacy,
            endpoint=f"legacy_{legacy.strip('/').replace('/', '_')}",
            view_func=lambda t=target: redirect(t, code=308),
        )

    @app.get("/api")
    def api_root():
        return jsonify({
            "version": API_VERSION,
            "systems": [
                {"key": m.key, "prefix": m.prefix, "wired": m.wired,
                 "label": m.label}
                for m in registry.SYSTEMS
            ],
        })

    logger.info("Application built (API %s)", API_VERSION)
    return app


__all__ = ["create_app"]
