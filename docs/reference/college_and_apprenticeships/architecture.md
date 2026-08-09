# Architecture

Reference for the two systems that arrived from the
`college_and_apprenticeships` starter project. They have since diverged:
**apprenticeships** is built and running; **fe_college** is still a
docstring skeleton. Everything below describes apprenticeships unless it
says otherwise.

For the domain itself — roles, gateway, EPA, off-the-job rules — see
[`docs/apprenticeships/apprenticeship_system.md`](../../apprenticeships/apprenticeship_system.md).

## Layers

The house 4-layer shape, with one addition:

```
interfaces/    CLI, GUI  (and api/, portals/ — scaffolding, see below)
    ↓
services/      Actor-first orchestration. The only write path.
    ↓
infrastructure/persistence/repositories/    SQL in, dataclasses out
    ↓
domain/        Pure rules. No database, no actor, no I/O.
```

Two rules keep the boundary sharp:

- **Every service function takes `actor` first.** Reads are scoped to
  what that actor may see and writes are refused outright, so a new
  screen cannot forget the check. An interface that filters rows itself
  is a bug, not a shortcut.
- **Domain modules are pure.** `gateway.evaluate()` takes the facts and
  returns the judgement; the service gathers the facts. That is what
  lets the rules be tested without a database and reused by the CLI, the
  GUI and the cross-system adapter alike.

`pathways/` and `integrations/` sit alongside these rather than inside
them. Both are currently scaffolding except
`integrations/cross_system_adapter.py`, which is live.

## Where each concern lives

| Concern | Module |
|---|---|
| Roles, permissions, every closed vocabulary | `config.py` |
| Who is asking, and what they may see | `services/access.py` |
| Filesystem paths | `education_system/paths.py` (`APPRENTICESHIPS_` prefix) |
| Schema and connections | `infrastructure/persistence/schema.py` |
| Shared SQL helpers | `infrastructure/persistence/repositories/base.py` |
| Tk toolkit | `interfaces/gui/widgets.py` |
| Terminal toolkit | `interfaces/cli/prompts.py` |
| Audit trail | `compliance_repository.record(...)`, called by services |

## Two decisions worth knowing before you change anything

**Permission is not scope.** `config.ROLE_PERMISSIONS` answers *may you
do this at all*; the `Actor`'s `apprentice_id` / `employer_id` /
`staff_id` answer *to whom*. An unresolved scope produces a filter that
matches nothing (`-1`) rather than no filter at all — failing closed is
the whole point, so do not "helpfully" fall back to the full cohort.

**Two capabilities are withheld from the provider on purpose.**
`config.EPAO_EXCLUSIVE` — `gateway.approve` and `epa.grade` — are
subtracted from the admin role. That is not an oversight to correct.

## Scaffolding

`interfaces/api/` (24 modules) and `interfaces/portals/` (38 modules)
are empty: a docstring each, no route registration, nothing importing
them. Apprenticeships is therefore absent from the unified REST API and
from the web portal. `pathways/` and three of the four
`integrations/*_gateway.py` modules are the same.

They are directory shape agreed up front, not half-finished code. Adding
any of them is new work with its own design decisions, not wiring.

## fe_college

Every module is a docstring stub, laid out in the shape above. It is
registered with nothing — not the launcher, not shared auth, not
`paths`, not the unified API. See [`docs/fe_college/`](../../fe_college/).
