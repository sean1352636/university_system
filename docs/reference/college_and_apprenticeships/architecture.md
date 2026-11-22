# Architecture

Reference for the two systems that arrived from the
`college_and_apprenticeships` starter project. They have since diverged:
both are built and running, and each is registered with the launcher,
shared auth, `paths` and the unified API. Everything below describes
apprenticeships unless it says otherwise.

For the domain itself — roles, gateway, EPA, off-the-job rules — see
[`docs/apprenticeships/apprenticeship_system.md`](../../apprenticeships/apprenticeship_system.md).

## Layers

The house 4-layer shape, with one addition:

```
interfaces/    CLI, GUI  (HTTP routes live outside, see below)
    ↓
application/   Actor-first use cases, by area. The only write path.
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

Adapters onto other systems — the cross-system handover, degree events
and the read-only university gateway — are infrastructure, in
`infrastructure/integrations/`.

## Where each concern lives

| Concern | Module |
|---|---|
| Roles, permissions, every closed vocabulary | `config/__init__.py` |
| Who is asking, and what they may see | `application/security/access.py` |
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

## No scaffolding

The package used to carry about 110 placeholder files: star re-export
shims under `domain/`, docstring-only `interfaces/portals/` and
`pathways/` trees, and three empty `integrations/*_gateway.py` modules.
They were cleared out in September 2026 because they made the tree look
far larger than the working system. `tests/unit/systems/apprenticeships/test_layout.py`
now fails on either kind, so a planned module is written up here rather
than stubbed.

The HTTP routes live outside the package, in
`src/education_system/api/apprenticeships/`, and answer 501 until each
is backed by a service. There is no web portal.

## fe_college

A working system in its own strict 4-layer shape: `domain/`,
`infrastructure/persistence/`, `services/` and `interfaces/`, with
top-level `cli_main.py` and `gui_main.py`. Its HTTP routes are in
`src/education_system/api/fe_college/`, and answer 501 until each is
backed by a service. See [`docs/fe_college/`](../../fe_college/).
