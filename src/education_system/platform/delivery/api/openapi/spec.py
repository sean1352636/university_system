"""OpenAPI spec, generated from the registry and the live URL map.

The previous spec (``university/openapi_spec.py``, 1442 lines) was a
hand-maintained dict. Hand-written specs drift the moment a route is
added, and this one described an API surface that had already been
removed — it documented endpoints that no longer existed.

This walks :func:`registry.iter_routes` over the built app instead, so
the spec cannot describe a route that is not mounted, and cannot omit one
that is. Hand-written detail (descriptions, examples, schemas) belongs in
``DESCRIPTIONS`` below, keyed by endpoint, and is merged in — the parts
that must be written by a person stay written by a person, without
letting the *inventory* drift.
"""

from __future__ import annotations

import logging
import re

from education_system.platform.delivery.api import registry
from education_system.platform.delivery.api.versioning import API_VERSION

logger = logging.getLogger(__name__)

#: Prose for specific endpoints, merged over the generated skeleton.
DESCRIPTIONS: dict[str, dict] = {
    "shared_auth.login": {
        "summary": "Authenticate and receive access + refresh tokens",
        "description": (
            "Returns a JWT carrying the user's accessible systems. When the "
            "account has MFA enabled the response is `mfa_required` plus an "
            "`mfa_token` to complete at `/auth/mfa/verify`."
        ),
    },
    "shared_auth.logout": {
        "summary": "Revoke this session's refresh token",
    },
    "admin_control.shutdown": {
        "summary": "Stop the server (loopback + admin only)",
    },
}

#: Werkzeug writes ``<int:id>``; OpenAPI wants ``{id}``.
_OAS_PATH_RE = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")

_PARAM_TYPES = {"int": "integer", "float": "number", "path": "string",
                "string": "string", "uuid": "string"}


def _parameters_for(rule) -> list[dict]:
    params = []
    for name in rule.arguments:
        converter = rule._converters.get(name)
        kind = type(converter).__name__.replace("Converter", "").lower()
        params.append({
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": _PARAM_TYPES.get(kind, "string")},
        })
    return params


def _tag_for(record: dict) -> str:
    if record["system"]:
        mount = registry.get_mount(record["system"])
        return mount.label if mount else record["system"]
    return record["endpoint"].split(".", 1)[0].replace("_", " ").title()


def generate(app, *, title: str = "Education System API",
             version: str | None = None) -> dict:
    """Build the OpenAPI document for *app*."""
    paths: dict[str, dict] = {}
    tags: set[str] = set()

    for record in registry.iter_routes(app):
        rule = record["rule"]
        if rule.startswith("/static") or "<path:filename>" in rule:
            continue
        # OpenAPI wants {id}; Werkzeug writes <int:id>.
        oas_path = _OAS_PATH_RE.sub(r"{\1}", rule)

        tag = _tag_for(record)
        tags.add(tag)
        entry = paths.setdefault(oas_path, {})
        for method in record["methods"]:
            operation = {
                "tags": [tag],
                "operationId": f"{record['endpoint']}.{method.lower()}",
                "responses": {
                    "200": {"description": "Success"},
                    "401": {"description": "Authentication required"},
                    "403": {"description": "Forbidden"},
                },
            }
            werkzeug_rule = next(
                (r for r in app.url_map.iter_rules() if str(r.rule) == rule), None)
            if werkzeug_rule is not None and werkzeug_rule.arguments:
                operation["parameters"] = _parameters_for(werkzeug_rule)
            operation.update(DESCRIPTIONS.get(record["endpoint"], {}))
            entry[method.lower()] = operation

    return {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": version or API_VERSION,
            "description": (
                "Generated from the live route map. Systems are declared in "
                "`platform/delivery/api/registry.py`; a route absent here is "
                "absent from the running app."
            ),
        },
        "tags": [{"name": t} for t in sorted(tags)],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer",
                               "bearerFormat": "JWT"},
            },
        },
        "security": [{"bearerAuth": []}],
        "paths": dict(sorted(paths.items())),
        "x-mounts": registry.mount_report(),
    }


__all__ = ["generate", "DESCRIPTIONS"]
