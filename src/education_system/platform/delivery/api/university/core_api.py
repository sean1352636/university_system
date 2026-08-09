"""Minimal web/API student-record application with no GUI/scientific imports."""

from __future__ import annotations

import os

from flask import Flask


def create_core_app(*, validate_schema: bool = True) -> Flask:
    from education_system.platform.delivery.api.security_headers import (
        is_development,
        register_security_headers,
    )
    from education_system.platform.delivery.api.static_files import send_static_asset

    # Flask's built-in static handler has no extension allow-list and no
    # symlink-containment check, so it stays disabled; the hardened
    # /static/<path> route below serves the same directory instead.
    app = Flask(__name__, static_folder=None)

    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("API_SECRET_KEY")
    if not secret:
        if not is_development():
            raise RuntimeError(
                "JWT_SECRET_KEY (or API_SECRET_KEY) must be set in production. "
                "Refusing to start the core app with a hardcoded signing key."
            )
        secret = os.urandom(32).hex()
    app.config["SECRET_KEY"] = secret
    app.config["JSON_SORT_KEYS"] = False

    register_security_headers(app)

    from education_system.platform.governance.security.csrf import register_csrf_middleware

    register_csrf_middleware(app)

    _static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.route("/static/<path:filename>")
    def core_static_asset(filename: str):
        return send_static_asset(_static_dir, filename)

    if validate_schema:
        from education_system.systems.university.infrastructure.database.schema_version import (
            require_supported_schema,
        )
        require_supported_schema()

    # Direct submodule imports remain lightweight because routes/__init__.py is
    # now lazy and no longer imports every optional capability.
    from education_system.systems.university.domains.admissions.interfaces.api.admission_routes import (
        admission_bp,
    )
    from education_system.systems.university.domains.admissions.interfaces.api.admissions_crm_routes import (
        admissions_crm_bp,
    )
    from education_system.systems.university.interfaces.api.routes.operations_routes import (
        operations_bp,
    )
    from education_system.systems.university.interfaces.api.routes.student_lifecycle_routes import (
        student_lifecycle_bp,
    )
    from education_system.systems.university.interfaces.api.routes.web_routes import web_bp

    for blueprint in (
        admission_bp,
        admissions_crm_bp,
        student_lifecycle_bp,
        operations_bp,
        web_bp,
    ):
        app.register_blueprint(blueprint)
    from education_system.systems.university.plugins import (
        register_enabled_plugin_routes,
    )
    register_enabled_plugin_routes(app)
    return app


def main() -> None:
    app = create_core_app()
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )


__all__ = ["create_core_app", "main"]
