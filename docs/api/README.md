# Education System — API Reference

This directory contains machine-readable **OpenAPI 3.0.3** specifications
for the Education System REST API. They were generated from the live
Flask URL maps by `tools/university/generate_openapi_spec.py` and committed so
they're available offline, in version control, and to SDK generators /
contract tests / API gateways.

The committed files predate the current API layout: they still use the old
`college` prefix and don't cover Nursery, FE College or Apprenticeships. For the
current surface, use the runtime spec below.

## Files

| File | Endpoints | Source app | Purpose |
|------|-----------|------------|---------|
| [`openapi.json`](openapi.json) | 1363 | `unified_server.create_unified_app()` | The **production** spec — covers shared infrastructure (auth, MFA, parent portal, retention, LMS, webhooks, GraphQL, tenants) plus the four systems mounted when it was generated (university, sixth form under the old `college` prefix, secondary school, primary school). |
| [`openapi-college.json`](openapi-college.json) | 470 | Historical standalone app (removed) | Sixth form spec from when each system had its own server. Nothing regenerates it now. |
| [`openapi-secondary.json`](openapi-secondary.json) | 319 | Historical standalone app (removed) | Secondary school spec from when each system had its own server. Nothing regenerates it now. |
| [`openapi-primary.json`](openapi-primary.json) | 203 | Historical standalone app (removed) | Primary school spec from when each system had its own server. Nothing regenerates it now. |

## Generating / regenerating

```bash
# Generate the unified spec
PYTHONPATH=src python tools/university/generate_openapi_spec.py --system unified

# CI mode — exit non-zero if any spec is stale (no writes)
PYTHONPATH=src python tools/university/generate_openapi_spec.py --check
```

The script calls `create_unified_app()`, passes the resulting Flask app to
`education_system.platform.delivery.api.docs.build_openapi_spec`, and writes the
JSON output sorted-and-indented so diffs are stable.

> **Known problem:** since the script moved under `tools/university/`, its
> `REPO_ROOT` resolves to `tools/`, so it targets `tools/docs/api/` rather than
> `docs/api/`. Its `university` builder also imports
> `platform/delivery/api/university/api_server.py`, which no longer exists. Fix
> both before relying on it to refresh the committed files.

## Runtime equivalents

The same generator runs **inside** the Flask app:

| URL | Returns |
|-----|---------|
| `GET /api/v1/openapi.json` | The current spec, generated on every request |
| `GET /api/v1/docs` | Swagger UI (loads the JSON above) |

If you're tweaking routes locally, hit `/api/v1/openapi.json` for the
freshest spec; commit the generated file when the change lands.

## Known limitations

- **There is no standalone university spec** — the standalone
  per-system servers are gone. University routes are served only by the
  unified app, so use `/api/v1/openapi.json`.
- **Endpoint summaries are auto-generated from URL paths**, not from
  per-route docstrings. The current generator (`src/education_system/platform/delivery/api/openapi/ui.py`)
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
- [`tools/university/generate_openapi_spec.py`](../../tools/university/generate_openapi_spec.py) — the generator script
- [`src/education_system/platform/delivery/api/openapi/ui.py`](../../src/education_system/platform/delivery/api/openapi/ui.py) — the runtime spec builder
