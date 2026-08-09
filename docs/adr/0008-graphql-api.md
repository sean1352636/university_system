# 0008 — GraphQL API Alongside REST

**Date:** 2026-03-26
**Status:** Proposed

---

## Context

The existing REST API (`/api/v1/{system}/...`) works well for simple CRUD operations but
clients frequently need to fetch related data that spans multiple endpoints. For example, a
student dashboard needs student profile + current grades + attendance summary + upcoming
timetable slots — currently four separate round trips.

A reporting client building a cross-system "at risk" dashboard must make requests to
`/college/students`, `/college/grades`, and `/college/attendance` and join the results in
application code. REST versioning also becomes painful when different clients need different
field sets (mobile app vs. admin portal).

GraphQL would let clients specify exactly the shape of data they need in a single request and
traverse relationships declared in the schema.

## Decision

We propose adding a GraphQL endpoint at `/api/v1/graphql` served by the
[Strawberry](https://strawberry.rocks/) library (Python-first, type-annotated, integrates
with Flask via `strawberry.flask.GraphQLView`).

Key design points:
- **Schema-first via Python types**: Strawberry derives the GraphQL schema from Python
  dataclasses with `@strawberry.type`, keeping types co-located with the service layer
- **Resolvers call existing services**: GraphQL resolvers instantiate `StudentService`,
  `GradeService`, etc. — no new database queries, ensuring business rules are not bypassed
- **Auth via existing JWT middleware**: the `system_required()` decorator is applied to the
  GraphQL view; field-level permissions use Strawberry's `permission_classes`
- **Subscriptions deferred**: real-time subscriptions require WebSocket support (ADR 0009);
  initial implementation covers queries and mutations only
- **REST API preserved**: REST endpoints are not removed; GraphQL is additive

The GraphQL playground (GraphiQL) would be exposed at `/api/v1/graphql` in development mode
and disabled in production (following the same `APP_ENV` guard used for Swagger UI).

## Consequences

### Positive
- Clients fetch exactly the data they need — eliminates over-fetching and multiple round trips
- Strongly typed schema serves as living documentation
- Cross-system queries become natural (resolver for `Student.grades` can span College and
  University schemas if the user has access to both systems)
- Strawberry's Python type annotations integrate cleanly with the existing service layer

### Negative / Trade-offs
- N+1 query problem: naive resolvers will fire one SQL query per list item; DataLoader
  batching must be implemented from the start
- Adds a dependency (`strawberry-graphql[flask]`) and a new paradigm for contributors
  unfamiliar with GraphQL
- Error handling semantics differ from REST (GraphQL returns HTTP 200 with an `errors` key);
  clients must handle both REST and GraphQL error shapes
- Schema design requires upfront thought; poorly designed types are hard to evolve without
  breaking clients

### Neutral
- Existing REST clients are unaffected; migration is opt-in per client
- GraphQL introspection should be disabled in production to avoid leaking schema details

---

*Depends on: [0001](0001-unified-flask-server.md) (Flask server), [0002](0002-shared-authentication.md) (JWT auth)*
*Related: [0009](0009-websocket-realtime.md) (GraphQL subscriptions would use WebSockets)*
