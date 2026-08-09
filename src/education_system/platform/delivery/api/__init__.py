"""Shared API platform for all education system Flask apps.

This package owns hosting, middleware, router registration and common protocol
support. It is system-agnostic: the per-system route blueprints live with the
systems that own them, under
``education_system.systems.<system>.interfaces.api.routes``, and are registered
here by ``unified_server``.

Structure:
    platform/delivery/api/
    ├── unified_server.py   # App factory; mounts every system's routes
    ├── async_adapter.py    # Async Flask wrapper
    ├── health.py           # Health check blueprint
    ├── jwt_utils.py        # JWT token management
    ├── middleware.py       # Request ID, timing, logging
    ├── tenant_middleware.py
    ├── rate_limiter.py     # Per-IP rate limiting
    ├── graphql/            # GraphQL schema and resolvers
    ├── web/                # Shared web delivery
    ├── parent_portal/
    └── university/         # University API hosting (api_server, core_api,
                            #   auth, pagination, validators, static assets).
                            #   Its route blueprints moved to
                            #   systems/university/interfaces/api/routes/.
"""
