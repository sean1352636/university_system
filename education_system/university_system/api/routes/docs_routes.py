"""API documentation routes: Swagger UI and OpenAPI spec (no auth required)."""

from __future__ import annotations

from flask import Blueprint, jsonify, make_response

from education_system.university_system.api.openapi_spec import get_openapi_spec

docs_bp = Blueprint("docs", __name__)

_SWAGGER_UI_VERSION = "5.17.14"

_SWAGGER_HTML = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>University Management System API — Docs</title>
  <link rel="stylesheet"
        href="https://unpkg.com/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({{
      url: "/api/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset,
      ],
      layout: "BaseLayout",
    }});
  </script>
</body>
</html>
"""


@docs_bp.route("/api/docs", methods=["GET"])
def swagger_ui():
    """Serve the Swagger UI HTML page."""
    response = make_response(_SWAGGER_HTML)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    # Override the default restrictive CSP so the CDN scripts/styles load.
    # The _custom_csp flag tells the global security-headers handler to
    # leave this response's CSP alone.
    response._custom_csp = True
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://unpkg.com; "
        "connect-src 'self';"
    )
    return response


@docs_bp.route("/api/openapi.json", methods=["GET"])
def openapi_json():
    """Return the OpenAPI specification as JSON."""
    return jsonify(get_openapi_spec())
