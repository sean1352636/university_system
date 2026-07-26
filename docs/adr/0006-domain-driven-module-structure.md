# 0006 — Domain-Driven Module Structure

**Date:** 2025-06-01
**Status:** Accepted

---

## Context

As the platform grew from a single University system to four systems totalling 150+ modules,
organising code by technical layer (all models in one directory, all services in another) made
it increasingly hard to find which code handled a specific business concept. A developer fixing
a bug in College attendance had to hunt across multiple top-level directories.

Alternatives considered:
- Flat module list (all modules as siblings in `modules/`) — does not scale past ~20 modules
- Layer-first structure (`models/`, `services/`, `routes/`, `gui/`) — discourages cohesion;
  related code is spread across the tree
- Feature flags with a shared schema — rejected; systems have genuinely different domain rules

## Decision

We will organise modules by domain area within each system. Each system follows the same
top-level domain grouping:

```
modules/domain/
    academics/          — core teaching and learning (students, grades, attendance, timetable…)
    pastoral_care/      — welfare (behaviour, safeguarding, SEND, rewards…)
    staff/              — HR, CPD, cover, staff directory
    admin/              — system administration (users, settings, audit, data export…)
    communication/      — email, notifications, announcements, calendar…
    facilities/         — room booking, assets, visitors, incidents
    {system_specific}/  — e.g. student_life/ (secondary/primary), pupil_life/ (primary)
```

Within each domain module the internal layout is consistent:

```
modules/domain/academics/students/
    services/
        student_service.py   — business logic (see ADR 0005)
    routes/
        student_routes.py    — Flask blueprint
    gui/
        student_gui.py       — tkinter Frame
    cli/
        student_cli.py       — Click/argparse commands
    __init__.py
```

System-specific naming variations are accepted (e.g. `pupils/` in the primary school instead
of `students/`; `pupil_life/` instead of `student_life/`).

The `shared/` top-level package contains infrastructure that is genuinely cross-system:
auth, the unified API server, GUI login/MFA windows, database helpers, email, and seeding.

## Consequences

### Positive
- All code for a business concept (service, routes, GUI, CLI) lives in one directory tree —
  easy to find, easy to delete when a module is removed
- Domain groupings mirror the mental model of school staff; onboarding new developers is faster
- Adding a new module (e.g. `bursary`) follows a clear template: create the directory,
  implement the service, add routes/GUI/CLI as needed
- Domain boundaries discourage tight coupling between unrelated areas

### Negative / Trade-offs
- Cross-domain services (e.g. generating a report that spans grades, attendance, and behaviour)
  must import from multiple domain directories; this is explicit but verbose
- The consistent internal layout (services/, routes/, gui/, cli/) adds directories even for
  modules that only expose one interface
- Some domain boundaries are judgement calls (e.g. is `form_groups` academics or student_life?)

### Neutral
- `modules/domain/` is intentionally plural and explicit rather than just `modules/` to
  distinguish domain modules from infrastructure and cross-cutting modules at the system root

---

*See also: [0005](0005-service-layer-pattern.md) (service convention inside modules), [0007](0007-multi-interface-architecture.md) (multiple interfaces per module)*
