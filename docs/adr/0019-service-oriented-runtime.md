# 0019 — Service-oriented production runtime

**Status:** Accepted

The platform uses a strangler architecture: the unified authenticated API is
the gateway while externally exposed, high-scale or differently trusted
capabilities are extracted behind versioned HTTP/event contracts. The first
extracted service is credential verification. It is independently deployable,
read-only, has its own health contract, and never exposes student identifiers
or credential metadata.

Domain code remains organised behind application services and typed operation
results. Cross-domain side effects use the integration bus/outbox boundary.
New services must own their writes, accept correlation and tenant identity,
publish idempotent events, expose liveness/readiness probes, and avoid direct
writes to another service's tables. Extraction proceeds incrementally; this
avoids a distributed monolith and preserves local deployment support.

Database-per-tenant remains the isolation boundary. The gateway must run with
`MULTI_TENANT_REQUIRED=true` in hosted environments. Public verification is a
deliberate tenant-neutral lookup by opaque signed hash.
