# 0007 — Multi-Interface Architecture (CLI, GUI, API, Web)

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

The platform serves different user populations with different access needs:
- **Admin staff** prefer a desktop GUI with point-and-click navigation
- **Developers and power users** need a scriptable CLI for bulk operations and automation
- **Third-party integrations** (timetable software, payment providers) require a machine-readable API
- **Students and parents** access the system from personal devices via a browser

Serving only one interface would exclude at least one of these groups. Duplicating the business
logic in each interface layer would create four codebases to maintain.

## Decision

We will support four interfaces, all driven by the same service layer:

### 1. CLI (`modules/domain/{domain}/cli/`)
Click-based command groups. Useful for bulk data import, seeding, and automation scripts.
Invoked via `run.py --{system} --cli` or directly via the module entry points.

### 2. GUI (`modules/domain/{domain}/gui/`)
Tkinter-based desktop application. Each module provides a `tk.Frame` subclass. Frames are
loaded into a `ttk.Notebook` tab structure with a scrollable sidebar (Canvas + Frame) for
navigation. The shared login/MFA windows (`shared/gui/login_gui.py`, `mfa_gui.py`) gate
access before the system-specific window opens.

All four system launchers accept `user_info=`, `role=`, and `shared_auth=` keyword arguments
so that the universal login window (`run.py`) can authenticate once and pass credentials into
whichever system the user selects, avoiding a second login prompt.

### 3. REST API (`shared/api/unified_server.py`)
Flask blueprints under `/api/v1/{system}/`. JSON in, JSON out. JWT auth via
`Authorization: Bearer <token>`. Documented via Swagger UI at `/api/v1/docs`.
Consumed by the web portal and available for third-party integration.

### 4. Web Portal (`shared/api/web/`)
Vanilla JS SPA (see ADR 0004) served by the same Flask process. Intended for students and
parents; does not expose admin-only routes.

### Interface selection
`run.py` is the single entry point. Without arguments it shows an interactive prompt. With
`--{system} --gui|--cli|--api` flags it launches the requested interface directly. The `--api`
flag always starts the unified server regardless of which system flag was given.

## Consequences

### Positive
- Each user group gets an appropriate interface without duplicating business logic
- The service layer can be tested in isolation; interface layers are thin adapters
- Adding a new interface (e.g. a mobile REST client) requires no changes to services
- The universal `run.py` launcher provides a single documented entry point

### Negative / Trade-offs
- Each new feature must be exposed in up to four interface layers (service + CLI + GUI + route)
  if full coverage is desired — this is significant per-feature effort
- GUI and CLI interfaces bypass the REST auth middleware; they rely on the shared auth library
  directly, meaning auth policy must be applied consistently in two code paths
- Tkinter is not available in headless server environments; GUI mode fails without a display

### Neutral
- The four interfaces share no UI framework — tkinter for desktop, vanilla JS for web, Click
  for CLI — so front-end skills are not transferable between them
- Swagger UI is auto-generated from Flask-RESTX/OpenAPI metadata and reflects the REST API
  only; GUI and CLI capabilities are documented separately in `docs/reference/MODULE_GUIDES.md`

---

*See also: [0001](0001-unified-flask-server.md) (REST API), [0004](0004-spa-vanilla-js.md) (web portal), [0006](0006-domain-driven-module-structure.md) (module layout)*
