# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Education System project.
ADRs document significant architectural decisions, their context, and their consequences.

## What is an ADR?

An ADR captures a single architectural decision: what was decided, why it was decided, and what
the trade-offs are. Each ADR has a status: **Proposed**, **Accepted**, **Deprecated**, or
**Superseded**.

## Process

1. Copy `template.md` to a new file named `NNNN-short-title.md` (zero-padded four-digit number).
2. Fill in all sections. Keep it concise — aim for 50-100 lines.
3. Open a pull request. The ADR is **Proposed** until merged.
4. On merge, change status to **Accepted**.
5. If a decision is later reversed, mark it **Deprecated** and link the superseding ADR.

---

## Index

### Accepted (implemented decisions)

| ID | Title | Date |
|----|-------|------|
| [0001](0001-unified-flask-server.md) | Unified Flask Server for All Systems | 2025-06-01 |
| [0002](0002-shared-authentication.md) | Centralised Authentication Module | 2025-06-01 |
| [0003](0003-sqlite-per-system.md) | SQLite Per-System Databases | 2025-06-01 |
| [0004](0004-spa-vanilla-js.md) | Vanilla JS Single-Page Application for Web Portal | 2025-06-01 |
| [0005](0005-service-layer-pattern.md) | Service Layer with _conn() Pattern | 2025-06-01 |
| [0006](0006-domain-driven-module-structure.md) | Domain-Driven Module Structure | 2025-06-01 |
| [0007](0007-multi-interface-architecture.md) | Multi-Interface Architecture (CLI, GUI, API, Web) | 2025-06-01 |

### Proposed (under consideration)

| ID | Title | Date |
|----|-------|------|
| [0008](0008-graphql-api.md) | GraphQL API Alongside REST | 2026-03-26 |
| [0009](0009-websocket-realtime.md) | WebSocket / Socket.IO for Real-Time Features | 2026-03-26 |
| [0010](0010-multi-tenancy.md) | Database-per-Tenant Multi-Tenancy Strategy | 2026-03-26 |
| [0011](0011-data-retention-gdpr.md) | Automated GDPR Data Retention Policies | 2026-03-26 |
| [0012](0012-centralized-structured-logging.md) | Centralised Structured Logging (ELK-compatible) | 2026-03-26 |

---

## Template

See [template.md](template.md) for the standard ADR template.
