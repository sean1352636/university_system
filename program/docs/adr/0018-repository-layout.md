# 0018 — Repository Layout Consolidation

**Date:** 2026-07-25
**Status:** Proposed
**Extends:** [0006](0006-domain-driven-module-structure.md) (domain-driven module structure), [0007](0007-multi-interface-architecture.md) (multi-interface architecture)

---

## Context

The tree has grown to 6,590 Python files across five systems. The 4-layer DDD split from ADR 0006
and the multi-interface split from ADR 0007 are both still the right calls, but they have been
applied inconsistently as systems were added, moved and renamed. A survey of `main` on 2026-07-25
found nine navigation problems:

1. **Peers live at different depths.** `nursery_system/`, `primarysch_system/` and
   `secondarysch_system/` sit flat under `education_system/`, while `sixthform_system/` and
   `university_system/` are wrapped in `post_16/` and `post_18/`. The age-band wrapper only covers
   2 of 5 systems, so it categorises nothing — it is just an extra level to remember.
2. **Five naming conventions for five systems:** `nursery_system`, `primarysch_system`,
   `secondarysch_system`, `sixthform_system`, `university_system`. `docs/` uses a third set of
   names (`college_system`, `primary_school`, `secondary_school`), and the launcher a fourth
   (`--college`/`--sixthform`, `--secondary`/`--school`).
3. **`modules/` is a dead layer.** Every system has `modules/domain`, `modules/shared`,
   `modules/core`, `modules/services`. `modules/` never holds anything else, so it is a guaranteed
   extra hop on every path.
4. **No canonical per-system shape.** Nursery has `main_gui.py` + `menu.py`; the others have
   `gui_main.py`. Only Sixth Form and University have `infrastructure/`. Only Sixth Form has
   `api/` and `paths.py`. University alone carries `utils/`, `scripts/`, `web/`, `templates/`,
   `backups/` and `logs/`.
5. **Three incompatible domain taxonomies.** Nursery and Primary are flat (~90 sibling directories,
   `bottle_feeds` next to `gdpr` next to `recruitment`); Secondary and Sixth Form use thematic
   packages; University uses 9 categories. The same concept lands in a different place per system —
   `safeguarding` is top-level in Nursery, `pastoral/safeguarding` in Sixth Form, and
   `student_affairs/safeguarding` in University.
6. **`shared/` is 45 unsorted top-level entries**, mixing infrastructure (`auth`, `database`,
   `audit`), business features (`lms`, `messaging`, `transcript`) and delivery (`api`, `cli`, `gui`).
7. **Delivery code is interleaved with logic at leaf level.** `domain/children/` holds
   `children.py`, `children_cli.py` and `children_views.py` — the `children_` prefix is redundant
   inside a directory called `children`, and the CLI/GUI live inside the domain package, which
   works against ADR 0007.
8. **Runtime artefacts live inside the source tree.** `data/`, `logs/`, `backups/` and
   `.benchmarks` appear in six locations. Most of the generated content is untracked, but it sits
   in package directories alongside code — e.g. record-shaped paths such as
   `post_16/sixthform_system/data/admissions_documents/<applicant-id>/` are created at runtime
   inside a package, next to 26 tracked files in the same `data/` tree. Nothing separates the two,
   so staying clean depends on `.gitignore` keeping pace rather than on structure.
9. **Tests are in six separate trees**, and the University tree mirrors a path the Makefile no
   longer matches.

Doing nothing is a real option — the cost of this change is import churn, not risk to behaviour.
But that cost only grows with the file count, and the survey found 31,971 absolute
`education_system.*` import references against just 116 files using relative imports, which is
precisely why every previous move (Sixth Form into `post_16/`, University into `post_18/`) was
expensive enough to be left half-finished.

## Decision

We will consolidate on a single layout: one depth and one naming convention for all five systems,
one canonical per-system shape, one shared domain vocabulary, and a `platform/` package grouped by
role instead of alphabetically.

### Target tree

```
education_system/
├── platform/                  # was shared/ — grouped by role, not alphabetically
│   ├── kernel/                # config, paths, database, logging, errors, base
│   ├── identity/              # auth, mfa, sessions, roles, user_management
│   ├── governance/            # audit, gdpr, safeguarding, security, validation
│   ├── features/              # lms, messaging, calendar, transcript, certificates,
│   │                          #   documents, reporting, analytics, i18n, offline …
│   ├── delivery/              # api/ (unified server + blueprints), cli/, gui/, web/
│   ├── integrations/          # email, webhooks, external services
│   └── cross_system/          # progression transfer queue
│
├── systems/                   # all five peers, one depth, one naming convention
│   ├── nursery/
│   ├── primary/
│   ├── secondary/
│   ├── sixth_form/
│   └── university/
│
├── launcher/
└── migrations/

tests/                         # single tree, mirrors the package
├── platform/                  # grouped like platform/ itself: identity, governance, features …
├── systems/{nursery,primary,secondary,sixth_form,university}/
│                              #   each mirrors its system: domain/<area>/, interfaces/,
│                              #   infrastructure/, plus integration/ and smoke/ siblings
├── tools/                     # tests for tools/
├── launcher/
└── migrations/

docs/                          # renamed to match systems/ exactly
tools/                         # was university_system/scripts/ — repo-wide
var/                           # gitignored: data/, logs/, backups/, .benchmarks/
```

`post_16/` and `post_18/` disappear. The system keys already converged on `secondary` and
`sixth_form` (commit `d92c4727`); this extends the same keys to directory names, doc directories
and launcher flags, so one name means one thing everywhere.

### Canonical per-system shape

Every system gets the same shape, with no per-system exceptions:

```
systems/<name>/
├── __init__.py            # SYSTEM_KEY, display name, declared capabilities
├── app.py                 # bootstrap/wiring (replaces cli_main.py/gui_main.py/menu.py)
├── domain/<area>/<feature>/
│   ├── service.py         # was children.py
│   ├── models.py
│   └── repository.py
├── interfaces/
│   ├── cli/<area>/        # was domain/children/children_cli.py
│   ├── gui/<area>/        # was domain/children/children_views.py
│   ├── {cli,gui}/shell/   # system-level UI belonging to no single area
│   └── api/               # blueprint mounted by platform/delivery/api
├── services/              # cross-domain application services: event bus, analytics,
│                          #   integrations, reporting — not domain logic, not plumbing
├── infrastructure/        # schema, db bootstrap, system-specific adapters
└── assets/templates/      # static templates only; no runtime data
```

`services/` exists because the alternative is worse: cross-domain services either sink into one
arbitrary domain area or float up into `infrastructure/`, where they get mistaken for plumbing.
In University it holds 117 files; in the four smaller systems it may stay empty, which is the
same rule the rest of this section applies — keep the empty package, keep the shape predictable.

Interface code lives in `interfaces/` **without exception**. A `cli/` or `gui/` directory nested
inside `domain/` or `infrastructure/` is the defect this pillar exists to remove; see the
University mapping, where 626 such files across 150 directories move out.

Systems that do not need a layer keep an empty package rather than omitting it, so the shape stays
predictable.

### Shared domain vocabulary

All five systems use the same top-level domain areas:

`academics`, `assessment`, `admissions`, `learners`, `pastoral`, `safeguarding`, `finance`,
`staff`, `operations`, `governance`, `progression`.

`admissions` covers everything before enrolment; `learners` holds the enrolled record itself
(`children`/`pupils`/`students`, contacts, leavers, alumni). That line is what stops the two from
bleeding into each other.

Nursery's flat directories fold into this — `bottle_feeds`/`sleep_log`/`toileting_log` become
`operations/daily_care`; `dsl`/`prevent_duty`/`looked_after` become `safeguarding`. Once you know
where safeguarding lives in one system, you know it in all five.

### Sequencing

Each phase is independently shippable and lands as its own commit with no logic changes, gated on
a full `make test`.

| Phase | Change | Import churn |
|-------|--------|--------------|
| 0 | Move `data/`/`logs/`/`backups/`/`.benchmarks` to `var/`, gitignore them | none |
| 1 | Flatten `post_16/`+`post_18/`, rename the five systems under `systems/` | ~25k refs, fully mechanical |
| 2 | Delete the `modules/` layer | large, mechanical |
| 3 | Consolidate tests into top-level `tests/`; fix the stale Makefile paths | low |
| 4 | Restructure `shared/` → `platform/` subpackages | medium |
| 5 | Split `interfaces/` out of `domain/`, per system | medium, incremental |
| 6 | Align the domain taxonomy | medium, incremental |

Two measures keep phases 1–2 cheap: keep `__init__.py` re-export shims at the old paths for one
release, and convert intra-package imports to relative as each package is moved.

## Consequences

### Positive

- One depth and one name per system: a path is predictable from the system name alone.
- The same feature sits at the same relative path in all five systems, so cross-system work
  (progression transfers, shared GUI patterns) stops requiring a per-system mental map.
- Removing `modules/` and the age-band wrappers cuts two levels from the deepest paths, which
  currently reach 11 segments.
- ADR 0007's interface separation becomes structural rather than a naming convention
  (`*_views.py`), so domain code can no longer quietly import Tkinter.
- Runtime data leaves the package tree entirely, so a single ignored `var/` replaces per-directory
  `.gitignore` upkeep and removes a class of accidental-commit incident.
- Future moves get cheap, because intra-package imports become relative.

### Negative / Trade-offs

- ~32k import references are rewritten. This is mechanical and scriptable, but it is a large diff
  and will conflict with any long-running branch. Land phases during a quiet window.
- Compatibility shims mean two valid import paths for one release; they must be deleted on a
  scheduled date or they become permanent.
- Phases 5 and 6 involve genuine judgement (which area does a feature belong to?), so they cannot
  be fully automated and will take several passes per system.
- `git log --follow` and blame across the renames need `-M`; reviewers unfamiliar with the flags
  will see history as discontinuous.

### Neutral

- Behaviour is unchanged throughout. No phase alters runtime logic, schemas or APIs.
- ADR 0006's 4-layer DDD split and ADR 0003's per-system SQLite databases are unaffected — this
  changes where the layers live, not what they are.
- The repository keeps the historical name `university_system` at the Git level; only the internal
  package layout changes.

---

Supersedes the structural half of `education-system-refactoring-plan (1).md` (repo root), which
covers phases 0–2 in narrative form; this ADR extends it to `shared/`, the interface split and the
domain taxonomy.
