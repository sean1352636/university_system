# 0001 — Unified Flask Server for All Systems

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

The education platform serves four distinct systems: University, Sixth Form College, Secondary
School, and Primary School. Each system originally had its own Flask app and startup script.
Running four separate servers created operational overhead (four ports, four processes, four
CORS configurations, four auth stacks) and made a single web portal or mobile client difficult
to build.

Alternatives considered:
- Keep four separate Flask apps behind an nginx reverse proxy
- Use a Python microservices framework (nameko, FastAPI with separate services)
- Merge all code into one monolithic Flask app with no namespacing

## Decision

We will use a single Flask application defined in `education_system/shared/api/unified_server.py`
that registers all four systems' blueprints under versioned, system-scoped URL prefixes:

```
/api/v1/auth/*         — shared authentication (login, refresh, MFA)
/api/v1/health/*       — health checks
/api/v1/university/*   — University routes
/api/v1/college/*      — Sixth Form College routes
/api/v1/school/*       — Secondary School routes
/api/v1/primary/*      — Primary School routes
/api/v1/docs           — Swagger UI / OpenAPI spec
```

Blueprint names are prefixed with the system label (e.g. `college_students`, `school_grades`)
to avoid Flask's name-collision errors when the same logical blueprint exists in multiple
systems. The `_reprefix()` helper rewrites a blueprint's `url_prefix` from `/api/students`
to `/api/v1/college/students` at registration time.

Security headers (CSP, X-Frame-Options, HSTS in production, SameSite cookies) are applied via
a single `after_request` hook in `_init_security()`, ensuring consistent hardening across all
systems without repetition.

## Consequences

### Positive
- One process, one port (default 5000) — simpler Docker/nginx configuration
- Single CORS policy and security header configuration
- Shared auth endpoint; JWT contains the user's `systems` list so the web portal can switch
  contexts without re-authenticating
- Swagger UI at `/api/v1/docs` aggregates all four systems' routes in one spec

### Negative / Trade-offs
- A crash or runaway query in one system affects all systems (no process isolation)
- Blueprint name collision prevention requires a naming convention (`{system}_{blueprint}`)
- A system with a large number of blueprints adds startup latency for all systems

### Neutral
- `run.py --college --api` and `run.py --university --api` both start the same unified server;
  the `--system` flag no longer selects an isolated process

---

*See also: [0002](0002-shared-authentication.md) (shared auth), [0004](0004-spa-vanilla-js.md) (web portal)*
