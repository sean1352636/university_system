# 0005 — Service Layer with _conn() Pattern

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

Early versions of the platform mixed database access directly inside CLI handlers, GUI
callbacks, and Flask route functions. This made unit testing difficult (routes had to be called
to test business logic), made it impossible to reuse logic across the CLI and GUI, and led to
inconsistent connection lifecycle management — some code paths leaked connections or omitted
`PRAGMA foreign_keys = ON`.

Alternatives considered:
- SQLAlchemy ORM — adds a significant dependency and learning curve; the project favours
  explicit SQL for auditability and fine-grained control
- Repository pattern with injected connection — adds indirection without clear benefit for a
  single-database-per-system design
- Simple module-level helper functions — no state, harder to test with a mock db_path

## Decision

We will organise all database-backed business logic into service classes following a consistent
pattern:

```python
class StudentService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)   # returns sqlite3.Connection

    def create_student(self, ...) -> dict:
        conn = self._conn()
        try:
            ...
            conn.commit()
            return result
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise StudentError(...) from e
        finally:
            conn.close()
```

Rules:
1. Each service class exposes a `_conn()` method that calls `connect(self._db_path)`.
2. Every method that touches the database opens a connection at the top, and closes it in a
   `finally` block — no shared long-lived connections.
3. Domain exceptions (e.g. `StudentError`, `ValidationError`) are raised rather than leaking
   `sqlite3` exceptions to callers.
4. `db_path=None` causes `connect()` to fall back to the system default path; tests pass an
   explicit path to a temporary database.
5. Services live in `modules/domain/{domain}/services/` — one service class per aggregate.

The `connect(db_path)` function is defined in each system's
`infrastructure/database/db.py` and sets `row_factory = sqlite3.Row` and
`PRAGMA foreign_keys = ON` before returning the connection.

## Consequences

### Positive
- Database access is isolated to service classes — CLI, GUI, and API layers call service
  methods and never hold raw connections
- Testing: pass `db_path=":memory:"` or a tmp path to any service; no monkey-patching needed
- Connection leaks are contained: the `finally: conn.close()` rule is enforced by code review
- Domain exceptions give callers a stable error contract regardless of the underlying SQL

### Negative / Trade-offs
- A new connection is opened per method call — for bulk operations this is slightly less
  efficient than a single long-lived connection; mitigated by SQLite's fast open cost
- No built-in transaction spanning multiple service calls (e.g. enrol a student and create
  a ledger entry atomically requires a dedicated method or a transaction service)
- Boilerplate is repeated across many service classes; this is intentional for clarity but
  increases the volume of code

### Neutral
- Flask route handlers typically instantiate a service with the system's configured `db_path`
  and call one or two methods per request; services are stateless between requests

---

*See also: [0003](0003-sqlite-per-system.md) (SQLite databases), [0006](0006-domain-driven-module-structure.md) (where services live)*
