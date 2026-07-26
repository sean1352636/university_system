"""Unified API documentation: Swagger UI and auto-generated OpenAPI spec."""

from __future__ import annotations

import re

from flask import Blueprint, jsonify, make_response, current_app

docs_bp = Blueprint("api_docs", __name__)

_SWAGGER_UI_VERSION = "5.17.14"

_SWAGGER_HTML = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Education System API — Docs</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({{
      url: "/api/v1/openapi.json",
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


def _infer_tag(path: str) -> str:
    """Infer a tag from the URL path for grouping in Swagger UI."""
    # /api/v1/college/students/... → College
    parts = path.strip("/").split("/")
    # Skip api, v1
    for part in parts:
        if part in ("api", "v1"):
            continue
        return part.replace("_", " ").title()
    return "General"


def build_openapi_spec(app=None) -> dict:
    """Auto-generate an OpenAPI 3.0.3 spec by introspecting the Flask URL map."""
    if app is None:
        app = current_app

    paths: dict = {}
    skip_endpoints = {"static", "api_docs.swagger_ui", "api_docs.openapi_json"}

    for rule in app.url_map.iter_rules():
        if rule.endpoint in skip_endpoints:
            continue
        # Skip web frontend routes
        if rule.rule.startswith("/web"):
            continue

        # Convert Flask <param> to OpenAPI {param}
        openapi_path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule.rule)
        methods = {}
        for method in rule.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            methods[method.lower()] = {
                "summary": rule.endpoint.replace("_", " ").replace(".", " — ").title(),
                "tags": [_infer_tag(rule.rule)],
                "responses": {
                    "200": {"description": "Successful response"},
                    "400": {"description": "Bad request"},
                    "401": {"description": "Unauthorized"},
                    "404": {"description": "Not found"},
                },
            }
        if methods:
            paths[openapi_path] = methods

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Education System API",
            "description": (
                "Unified API serving University, College, Secondary School, "
                "and Primary School management systems."
            ),
            "version": "1.0.0",
        },
        "servers": [{"url": "/", "description": "Current server"}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT token obtained from /api/v1/auth/login",
                }
            }
        },
        "security": [{"BearerAuth": []}],
    }


@docs_bp.route("/api/v1/docs", methods=["GET"])
def swagger_ui():
    """Serve the Swagger UI HTML page."""
    response = make_response(_SWAGGER_HTML)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response._custom_csp = True
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self';"
    )
    return response


@docs_bp.route("/api/v1/openapi.json", methods=["GET"])
def openapi_json():
    """Return the auto-generated OpenAPI specification as JSON."""
    return jsonify(build_openapi_spec())
