# API

**Neither system has a REST API.** Apprenticeships has the directory
shape for one; `fe_college` has nothing at all.

This page records what is there, why it is not wired up, and what
building it would involve — so the next person does not have to
rediscover that 24 modules are empty by importing them.

## What exists

```
education_system/api/apprenticeships/
├── routes/    apprentices  compliance  employers  end_point_assessment
│              funding  gateway  off_the_job_hours  portfolios
│              programmes  reports  reviews  training  router
└── schemas/   the same names, minus reports/router
```

Every one of those files is a single docstring. Nothing imports them,
no blueprint is defined, and `platform/delivery/api/unified_server.py`
does not mention apprenticeships. The system is reachable through the
launcher's CLI and GUI only.

They are directory shape agreed up front rather than half-finished code.
Filling them is new work, not a wiring bug.

## What the unified server expects

Systems mount through `_register_system_blueprints(...)`, which takes a
list of Flask blueprints and a list of init functions, then re-prefixes
each blueprint:

```
/api/v1/<system>/<the blueprint's own prefix>
```

So apprenticeships routes would land under `/api/v1/apprenticeships/…`
once `create_unified_app()` collected them. `API_VERSION` and the
prefixing rule live in `unified_server._reprefix`.

## What building it would involve

The service layer is the hard part and it already exists — every
capability the CLI and GUI use is a function in
`systems/apprenticeships/services/` taking `actor` first. A route is
therefore mostly translation. Four things need deciding, and none of
them are mechanical:

**1. Turning a request into an `Actor`.** Everything in this system
depends on `services.access.Actor` carrying both the role and the
records it resolves to. The API would need to build one from the JWT the
platform issues. Note that the JWT has no permissions claim — the role
comes from the token's subject and the scope from
`access.resolve(...)`, which hits the database.

**2. Preserving the scope boundary.** Five roles share one database and
three of them are outsiders. The services enforce that, so a route that
calls them is safe — but a route that reaches a repository directly is
not. That rule has to hold across every endpoint or the API becomes the
soft underbelly of the whole model.

**3. The two withheld capabilities.** `gateway.approve` and `epa.grade`
are removed from the provider admin on purpose
(`config.EPAO_EXCLUSIVE`). Any API-side role mapping has to preserve
that; a route that grants them by accident makes the independence
cosmetic.

**4. Serialisation.** The services return domain dataclasses with
computed properties — `OTJSummary.rag_rating`, `GatewayRecord.outstanding`,
`EPAProgress.overall`. Those properties are the useful part, so the
`schemas/` modules would have to project them explicitly rather than
`asdict()` the dataclass and lose them.

## Suggested first slice

If this gets picked up, the read side is worth doing on its own:

| Route | Service |
|---|---|
| `GET /apprentices` | `apprentice_service.list_apprentices` |
| `GET /apprentices/<id>` | `apprentice_service.get_apprentice` |
| `GET /apprentices/<id>/off-the-job` | `training_service.otj_summary` |
| `GET /apprentices/<id>/portfolio` | `portfolio_service.get_portfolio` |
| `GET /apprentices/<id>/gateway` | `gateway_service.evaluate_gateway` |
| `GET /apprentices/<id>/epa` | `epa_service.epa_progress` |
| `GET /dashboard` | `reporting_service.dashboard` |

All read-only, all already scoped, and enough to prove the actor
plumbing before any write endpoint exists.

## See also

- [`interfaces.md`](interfaces.md) — the two interfaces that *are* built
- [`docs/reference/API_REFERENCE.md`](../API_REFERENCE.md) — the systems
  that are on the unified API
