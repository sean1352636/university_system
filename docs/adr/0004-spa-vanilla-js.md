# 0004 — Vanilla JS Single-Page Application for Web Portal

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

The platform needed a browser-based interface so users without a Python environment could
access the system — particularly students and parents accessing from personal devices.
The interface must:
- Work with the unified REST API (`/api/v1/{system}/...`)
- Support MFA login flow
- Allow system-switching without a full page reload
- Ship without a build step (no npm, webpack, or bundler required)

Alternatives considered:
- **React (Vite/CRA)** — large dependency tree, requires a build pipeline, not a good fit for
  a project that values zero-infrastructure deployment
- **Vue 3 (Vite)** — similar concerns; also requires Node.js at build time
- **HTMX + Jinja2 server-side rendering** — considered; rejected because the REST API already
  returns JSON, adding server-side templating would duplicate rendering logic
- **Vanilla JS SPA** — no build step, no external runtime dependencies, works from any static
  file server or directly served by Flask

## Decision

We will implement the web portal as a vanilla JavaScript SPA served by Flask at
`education_system/shared/api/web/static/js/app.js` with a single `index.html` shell.

Architecture inside `app.js`:

- **State object** — holds `token`, `refreshToken`, `user`, `activeSystem`, and MFA state in
  memory; persisted to `localStorage` across page reloads
- **`apiFetch(path, opts)`** — thin wrapper around `fetch()` that injects the `Authorization`
  header and transparently retries once after a token refresh on HTTP 401
- **`render()`** — single top-level function that inspects `state` and calls the appropriate
  view function (`renderLogin()`, `renderMfa()`, `renderSystemSelect()`, `renderDashboard()`)
- **Views** — each view builds HTML by constructing DOM nodes or setting `innerHTML` on the
  `#app` element; no virtual DOM, no diffing
- **Routing** — browser hash (`#dashboard`, `#students`, etc.) is used for in-app navigation;
  `hashchange` triggers a re-render
- **Session heartbeat** — `setInterval` pings `/api/v1/health/ping` every 60 s to keep the
  session alive and detect expiry

The Flask route `GET /` serves `index.html`; all other `/` paths return the same file so
deep-link bookmarks resolve correctly.

## Consequences

### Positive
- Zero build toolchain — the JS file is edited directly and served as-is
- No Node.js or npm dependency at any stage
- Fast initial load — a single ~1 000-line JS file and minimal CSS
- Full control over behaviour with no framework upgrade treadmill

### Negative / Trade-offs
- Grows harder to maintain as features are added — no component model, no state management
  library, no type safety
- No tree-shaking or minification by default (a future build step could add this)
- `innerHTML` string building is verbose and error-prone compared to JSX or templating
- Accessibility (ARIA, keyboard navigation) requires manual discipline

### Neutral
- A future migration to a framework (e.g. Vue 3 with `<script setup>`) would not require
  changing the REST API, only replacing the client files
- The SPA shares the same CSP as the API server (set in `_init_security()`), which restricts
  `script-src` to `'self'`

---

*See also: [0001](0001-unified-flask-server.md) (Flask server that serves the SPA)*
