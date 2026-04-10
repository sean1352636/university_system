# Education System — API Reference

This directory contains machine-readable **OpenAPI 3.0.3** specifications
for the Education System REST API. They're auto-generated from the live
Flask URL maps by `scripts/generate_openapi_spec.py` and committed so
they're available offline, in version control, and to SDK generators /
contract tests / API gateways.

## Files

| File | Endpoints | Source app | Purpose |
|------|-----------|------------|---------|
| [`openapi.json`](openapi.json) | 882 | `unified_server.create_unified_app()` | The **production** spec — covers shared infrastructure (auth, MFA, parent portal, retention, LMS, webhooks, GraphQL, tenants), university routes, and college routes mounted at their canonical prefixes. |
| [`openapi-college.json`](openapi-college.json) | 470 | `college/api_server.create_app()` | Standalone college API spec for deployments that run only the college subsystem. Same routes as in the unified spec but mounted at the college standalone server's URL prefixes. |

## Generating / regenerating

```bash
# Generate everything (writes only files that have changed)
PYTHONPATH=. python scripts/generate_openapi_spec.py

# Generate one system
PYTHONPATH=. python scripts/generate_openapi_spec.py --system unified
PYTHONPATH=. python scripts/generate_openapi_spec.py --system college

# CI mode — exit non-zero if any spec is stale (no writes)
PYTHONPATH=. python scripts/generate_openapi_spec.py --check
```

The script imports each subsystem's `create_app()` (or
`create_unified_app()`), passes the resulting Flask app to
`education_system.shared.api.docs.build_openapi_spec`, and writes the
JSON output sorted-and-indented so diffs are stable.

## Runtime equivalents

The same generator runs **inside** the Flask app:

| URL | Returns |
|-----|---------|
| `GET /api/v1/openapi.json` | The current spec, generated on every request |
| `GET /api/v1/docs` | Swagger UI (loads the JSON above) |

If you're tweaking routes locally, hit `/api/v1/openapi.json` for the
freshest spec; commit the generated file when the change lands.

## Known limitations

- **Standalone secondary and primary specs are not currently generated.**
  The standalone `secondary/api_server.py` and `primary/api_server.py`
  factories import legacy module paths
  (`education_system.secondary_school_system`,
  `education_system.primary_system`) that don't exist in the current
  package layout. These need to be renamed to `secondary_school` /
  `primary_school` before standalone specs can be generated. See the
  per-system `api_server.py` files for the affected imports.
- **Standalone university spec is not generated separately** — running
  `university/api_server.create_app()` after the unified app in the
  same process raises a Flask blueprint name collision (`'health'`).
  University routes are fully covered by `openapi.json`.
- **Endpoint summaries are auto-generated from URL paths**, not from
  per-route docstrings. The current generator (`shared/api/docs.py`)
  doesn't introspect view-function docstrings; if you want richer
  summaries, that's the file to extend.
- **Request/response schemas are not yet documented** — every operation
  declares the standard `200 / 400 / 401 / 404` response envelope but
  no body schemas. Adding `components.schemas` and per-route `parameters`
  is the natural next step if you want SDK generation.

## How the spec is used

| Consumer | How |
|----------|-----|
| Swagger UI | Served at `/api/v1/docs` for interactive exploration |
| External SDK generators | Point at the committed `openapi.json` |
| API gateways (e.g. Kong, AWS API Gateway) | Import the JSON to mirror the route surface |
| Contract tests | Compare the live `/api/v1/openapi.json` against the committed file via `--check` mode |
| Documentation site | Render the spec into static HTML via `redoc-cli` or similar |

## See also

- [`../reference/API_REFERENCE.md`](../reference/API_REFERENCE.md) — high-level human-readable API reference (route prefix index)
- [`../shared/AUTHENTICATION.md`](../shared/AUTHENTICATION.md) — how the JWT auth flow used by all endpoints works
- [`scripts/generate_openapi_spec.py`](../../scripts/generate_openapi_spec.py) — the generator script
- [`education_system/shared/api/docs.py`](../../education_system/shared/api/docs.py) — the runtime spec builder
