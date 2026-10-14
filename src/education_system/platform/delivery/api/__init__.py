"""Platform API kernel.

Exports the application factory and nothing else. Everything the factory
needs is reached through the packages below, so importing this package
does not drag in Flask blueprints, database connections or a Socket.IO
server as a side effect.

    kernel/      protocol plumbing: config, errors, problems, pagination,
                 responses, validation, static files, async adapter
    middleware/  request_context, tenant, rate_limit, caching, csrf —
                 and the order they must be applied in
    security/    authentication, jwt, principals, decorators, api_keys,
                 headers
    routes/      the platform's own blueprints (auth, health, tenants,
                 metrics, retention, journey, warehouse, webhooks,
                 admin control)
    graphql/     schema, resolvers, mutations, types
    openapi/     spec generated from the registry, plus the Swagger UI
    realtime/    Socket.IO server and one class per namespace

    registry.py  the single mount table — the whole URL surface as data
    versioning.py  API_VERSION, path helpers, legacy redirects
    app.py       create_app(); serving belongs to the launcher

Per-system route blueprints live with the systems that own them, under
``education_system.systems.<system>.interfaces.api.routes``, and are
declared in ``registry.SYSTEMS``.
"""

from education_system.platform.delivery.api.app import create_app

__all__ = ["create_app"]
