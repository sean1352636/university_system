# Project Structure

> Back to [Documentation](../README.md)

This document describes the repository layout. Paths are relative to the
repository root. The installable package lives under `src/`; `tests/`, `docs/`,
`tools/` and `var/` sit beside it.

**Keep this file current.** When a system, domain, plugin, top-level package or
entry point is added, moved or removed, update the matching section in the same
change.

Counts were taken from the working tree on 2026-10-31, including uncommitted
work, and exclude `__pycache__`. To refresh one:

```bash
find <directory> -name '*.py' -not -path '*/__pycache__/*' | wc -l
```

## Repository overview

```text
<repo root>/
├── src/
│   └── education_system/          # Installable Python application (11,435 .py)
│       ├── __main__.py            # python -m education_system
│       ├── paths/                 # Every filesystem path (import from the package, not the parts)
│       │   ├── __init__.py        # re-exports all; backup + ensure_*_directories functions
│       │   ├── core.py            # roots, backup tree, package roots, config permissions
│       │   ├── platform_shared.py # PLATFORM_* paths
│       │   ├── systems/           # one module per system's paths
│       │   ├── registry.py        # SYSTEM_DB_PATHS / ORDER / LABELS / LEARNER_TABLE
│       │   └── _exports.py        # __all__
│       ├── switch.py              # Runtime system/interface switching state
│       ├── alembic.ini
│       ├── api/                   # HTTP routes for all seven systems (865 .py)
│       ├── launcher/              # System selection and launch orchestration (10 .py)
│       ├── migrations/            # Alembic migrations (76 in versions/)
│       ├── platform/              # Shared cross-system platform (382 .py)
│       └── systems/               # The seven education systems (10,096 .py)
├── tests/                         # Test tree, by scope then owner (1,001 .py)
├── tools/                         # Maintainer and architecture tools (62 .py)
├── docs/                          # Documentation (243 files)
├── deploy/                        # docker-stack.yml, kubernetes/
├── docker/                        # Dockerfile, compose, nginx, monitoring config
├── remove/                        # Code awaiting deletion by hand (950 files)
├── var/                           # Runtime state; never application source
├── run.py                         # Launcher script for a source checkout
├── pyproject.toml                 # The only place direct dependencies are declared
├── requirements.lock              # Generated production lock
├── requirements-dev.lock          # Generated development lock
├── Makefile
├── CHANGELOG.md
├── CLAUDE.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── SECURITY.md
```

`remove/` mirrors the original paths of code taken out during cleanups, and
nothing imports from it. The application does not depend on it, and it is
deleted by hand.

## Systems

`systems/registry.py` is the one list of systems. Each system declares its key,
name and interfaces in its own `manifest.py`.

| Package | System | .py files | Launcher flag |
|---|---|---:|---|
| `systems/nursery/` | Nursery / Early Years | 598 | `--nursery` |
| `systems/primary/` | Primary School | 641 | `--primary` |
| `systems/secondary/` | Secondary School | 345 | `--secondary` |
| `systems/sixth_form/` | Sixth Form College | 1,506 | `--college` |
| `systems/fe_college/` | FE College | 165 | `--fecollege` |
| `systems/apprenticeships/` | Apprenticeships | 250 | `--apprenticeships` |
| `systems/university/` | University | 5,768 | `--university` |
| `systems/special_education/` | Special Education (SEND) | 27 | `--specialeducation` (`--send`) |
| `systems/adult_education/` | Adult Education | 25 | `--adulteducation` (`--adult`) |
| `systems/alternative_provision/` | Alternative Provision | 28 | `--alternativeprovision` (`--ap`) |
| `systems/training_provider/` | Training Provider | 26 | `--trainingprovider` (`--tp`) |
| `systems/local_authority/` | Local Authority Education | 26 | `--localauthority` (`--la`) |

`systems/` also holds `registry.py` and `menu_inventory.py`.

Special Education (SEND) is signed in through the shared login like the others. It has a
learner adapter and journey slot (linked to Primary and Secondary for SEND requests and EHCP
updates, 2026-11-09) but no `paths.SYSTEM_DB_PATHS` entry, so the superadmin dashboard still
lists it under `LAUNCH_ONLY_SYSTEMS`; see
[Special Education (SEND) system](#special-education-send-system). Adult Education has a
learner adapter and journey slot (linked to FE College both ways and to University for
Access to HE, 2026-11-09) but no `paths.SYSTEM_DB_PATHS` entry, so it is launch-only on the
dashboard too; see [Adult Education system](#adult-education-system). Alternative Provision has a
learner adapter and journey slot (linked to Primary and Secondary for referrals and
reintegration, 2026-11-09) but still no `paths.SYSTEM_DB_PATHS` entry, so it also stays
launch-only on the dashboard; see [Alternative Provision system](#alternative-provision-system). Training Provider has a
learner adapter and journey slot (linked to Apprenticeships and FE College for training
requests and progression, 2026-11-09) but no `paths.SYSTEM_DB_PATHS` entry either; see
[Training Provider system](#training-provider-system). Local Authority Education has a
child adapter and journey slot (linked to Primary and Secondary for statutory
notifications, EHC decisions and school places, 2026-11-09) and no `paths.SYSTEM_DB_PATHS`
entry either; see [Local Authority Education system](#local-authority-education-system).

### Removed placeholder scaffolds

Five project scaffolds (Adult Education, Alternative Provision, Special Education (SEND),
Training Provider, Local Authority Education) were dropped into `systems/*_system/` on
2026-11-06. They were wired into the platform, then unwired and moved the same day to
`remove/src/education_system/systems/` (their folders kept as they were). The Adult
Education API package went to `remove/src/education_system/api/adult_education/`. Adult
Education's Learners area (services, GUI, CLI and API) had been fully built and is kept
there with it. Special Education (SEND) was rebuilt from scratch on 2026-11-08 as
`systems/special_education/` (below); the old placeholder scaffold stays in `remove/`.
Adult Education was rebuilt the same day as `systems/adult_education/` (below), carrying
over the old Learners-area rules; its old scaffold also stays in `remove/`. Alternative
Provision was rebuilt the same day as `systems/alternative_provision/` (below); its old
scaffold was placeholders only, so nothing was carried over, and it stays in `remove/`.
Training Provider was rebuilt the same day as `systems/training_provider/` (below); its
old scaffold (471 files) was also placeholders only and stays in `remove/`. Local
Authority Education was rebuilt the same day as `systems/local_authority/` (below); its
old scaffold (253 files) was placeholders only and stays in `remove/`.

## Shared platform

`education_system/platform/` contains capabilities shared by more than one
education system. System-specific rules do not belong here.

```text
education_system/platform/
├── branding.py
├── assets/templates/              # Shared templates
├── cross_system/                  # Identity, progression, handover, transitions, bus
│   ├── adapters/                  # One PhaseAdapter per system (registry.py, base.py)
│   ├── secondary_post16.py        # Secondary → Sixth Form / FE / Apprenticeship
│   ├── fe_applications.py         # Sixth Form / Apprenticeship / Adult Education / Training Provider → FE (+ _cli, _gui)
│   ├── adult_education_applications.py  # FE → Adult Education: referral, enrolled /
│   │                              # declined back (+ _cli, _gui: FE's board)
│   ├── training_provider_requests.py  # Apprenticeships / FE → Training Provider: request,
│   │                              # booked / certificate / not passed back (+ _cli, _gui)
│   ├── ap_referrals.py            # Primary / Secondary ⇄ Alternative Provision: referral,
│   │                              # placement (dual/sole), return (+ _cli, _gui: the schools' board)
│   ├── send_referrals.py          # Primary / Secondary ⇄ SEND service: request (advice / EHC
│   │                              # needs assessment), EHCP decisions back (+ _cli, _gui)
│   ├── local_authority_links.py   # Primary / Secondary ⇄ Local Authority: notifications in
│   │                              # (attendance, exclusions, CME, EHE, EHC request), decisions
│   │                              # back, school places out (+ _cli, _gui: the schools' board)
│   ├── sixth_form_transfers.py    # FE → Sixth Form change of provider
│   ├── route_support.py           # transfer() between systems; transfer_within_phase() to another institution
│   ├── sync_failures.py           # Failed best-effort progression syncs: list / retry / abandon
│   ├── apprenticeship_applications.py  # Sixth Form / FE / University / Training Provider → Apprenticeship
│   └── university_applications.py # Sixth Form / FE / Apprenticeship / Adult Education → University
├── delivery/                      # Shared interface delivery
│   ├── idle_settings.py           # EDU_IDLE_TIMEOUT_MINUTES, the school systems' idle logout setting
│   ├── api/                       # API hosting, middleware, mount table, shared routes
│   │   └── university/            # Kernel library for university routes
│   ├── cli/                       # Superadmin and shared CLI delivery
│   ├── gui/                       # Shared administrative GUIs
│   │   └── superadmin_dashboard/  # Superadmin window: app.py (shell/nav/lifecycle), theme.py, i18n.py,
│   │                              #   widgets.py, linked_sections.py, sections/ (one mixin per sidebar section)
│   ├── portals/                   # Browser portal services
│   └── web/                       # Static web UI delivery
├── features/                      # Reusable product capabilities
│   ├── analytics/
│   ├── bank_holidays/
│   ├── calendar/
│   ├── certificates/              # service + GUI; certificates_cli.py is the terminal twin (run(db_path, auth))
│   ├── documents/
│   ├── extras/
│   ├── i18n/
│   ├── messaging/
│   ├── notifications/
│   ├── offline/
│   ├── reporting/
│   └── transcript/
├── governance/
│   ├── academic_misconduct/
│   ├── audit/
│   ├── gdpr/
│   ├── safeguarding/
│   └── security/
├── identity/
│   ├── auth/                      # Shared login, MFA, sessions, central auth.db
│   │   └── policy.py              # Sign-in policy from auth_settings (lockout, session, password age), defaults as fallback
│   ├── menu_access.py             # Role filter mechanics; each system's rule is its domain/access.py
│   ├── staff_directory/
│   └── student_id/
├── integrations/
│   ├── email/
│   ├── external/
│   └── webhooks/
├── kernel/
│   ├── backup/
│   ├── base/
│   ├── core/
│   ├── database/
│   ├── seeding/
│   └── validation/
├── services/                      # Cross-cutting services, including data_retention/
└── testing/                       # Shared test support
```

## HTTP API

Route blueprints live in `education_system/api/`, one package per system, not
inside the systems themselves. The platform owns hosting and must not import
from this package; the dependency runs the other way.

```text
education_system/api/
├── apprenticeships/{routes,schemas}/
├── fe_college/{routes,schemas}/
├── nursery/{routes,schemas}/
├── primary/{routes,schemas}/
├── secondary/routes/             # Generated main-menu routes only, since the rebuild
├── sixth_form/{routes,schemas}/
└── university/                    # One package per API area
    ├── academics/
    ├── admissions/
    ├── assessment/
    ├── finance/
    ├── governance/
    ├── learners/
    ├── operations/
    ├── pastoral/
    ├── progression/
    └── staff/
```

- `platform/delivery/api/registry.py` is the mount table, listing every system's
  prefix and route module. `unified_server.py` and `app.py` serve it.
- `platform/delivery/api/university/` (`core_api.py`, `auth.py`, `pagination.py`,
  `validators.py`, `errors.py`, `config.py`, `openapi_spec.py`) is the library
  those university routes import. It is separate from `api/university/`.
- The university API areas keep the older names: `academics` and `pastoral` were
  split in `domains/`, but not here.
- Campus commerce also has routes at `systems/university/plugins/campus_commerce/api/`.

## System layout

The school systems share one broad shape:

```text
education_system/systems/<system>/
├── manifest.py                    # Key, display name and interfaces
├── assets/                        # Static and template assets, when present
├── domain/                        # Business rules and domain services
├── infrastructure/                # Persistence and external adapters
└── interfaces/
    ├── cli/
    └── gui/
```

Differences by system:

- **Nursery, primary:** top-level `cli_main.py` and `gui_main.py`
  entry points. Nursery also has `menu.py`. Each has `domain/access.py`, the one
  rule for which role may open which screen, used by both GUI and CLI.
  Nursery likewise keeps rules in `domain/` and screens/menus in `interfaces/{gui,cli}/`
  only: its 177 `layout-shim` aliases and the change-password / MFA re-exports were
  removed on 2026-11-05 (in `remove/`). The `cli_main` / `gui_main` dispatch tables
  name modules relative to `interfaces/cli/` and `interfaces/gui/`.
  Primary keeps rules in `domain/` and screens/menus in `interfaces/{gui,cli}/`
  only: the 198 `layout-shim` aliases that let `domain/` paths reach the screens,
  and the change-password / MFA re-exports, were removed on 2026-11-05 (in `remove/`).
  Change password and MFA come straight from the platform (`platform.delivery`).
  `infrastructure/schema_repair.py` (`repair_links`) rebuilds tables the
  sixth-form copies created with links to `students` / `alumni` (primary has
  `pupils`); the affected modules call it from `init_db`.
  Primary GUI screens open as pages in the main window's content area, as in
  the Secondary GUI (`gui_main.show_page`, with an "Open in new window" pop-out).
  `interfaces/gui/kit.py` is the shared widget kit: `show_page` / `page_heading` /
  `close_page`, and pickers bound to the old field's StringVar (`DateField`,
  `TimeField`, `ChoiceField`, `PupilPicker`, `StaffPicker`, `ClassPicker`,
  `YearGroupPicker`, `SubjectPicker`, `AcademicYearPicker`, `NumberField`,
  `MultiPicker`), so forms pick rather than type.
  Year 6 → Year 7 transition: `domain/learners/pupils/year6_transition.py` (destination,
  admissions round, consent, transition report, visits, DSL file-transfer record, checklist;
  stages the platform primary→secondary transition) with screens in
  `interfaces/{gui,cli}/learners/pupils/year6_transition/` (tables: `infrastructure/year6_transition_store.py`); `secondary_transfer.py` finishes
  the same open transition and `cross_system_adapter.export_handover` fills the full handover.
  Referrals to Alternative Provision: `domain/learners/pupils/ap_referrals.py` (on-roll
  pupil list) with screens in `interfaces/{gui,cli}/learners/pupils/ap_referrals/` over
  the platform board (`platform/cross_system/ap_referrals_gui.py` / `_cli.py`); admin
  only (`domain/access.py` `ADMIN_ONLY`). The adapter re-opens its own former pupil
  when the AP sends them back. SEND Service Requests: screens in
  `interfaces/{gui,cli}/learners/pupils/send_requests/` over
  `platform/cross_system/send_referrals_gui.py` / `_cli.py` (admin only); the adapter's
  `receive_send_update` writes EHCP decisions to `domain/pastoral/send` and SEN status
  (the local authority's EHC decisions too). Local Authority: screens in
  `interfaces/{gui,cli}/learners/pupils/local_authority/` over
  `platform/cross_system/local_authority_links_gui.py` / `_cli.py` (admin only); a place
  the authority allocates is an accepted application in `domain/admissions/admissions.py`
  (`transition_id`/`journey_id`/`source` columns), and enrolling it tells the platform.
- **Secondary:** entry points in `app/` (`app/cli_main.py`, `app/gui_main.py`),
  organised by feature module rather than by layer; see [Secondary School system](#secondary-school-system).
- **Sixth form:** no top-level entry points; the launcher imports
  `interfaces/cli/cli_main.py` and `interfaces/gui/gui_main.py`. It is moving to
  vertical slices, so it has both `domain/` (academics, admissions, assessment,
  governance, learners, operations, pastoral, progression, safeguarding, staff)
  and `domains/`:

  ```text
  systems/sixth_form/domains/
  ├── communications/
  ├── finance/
  └── operations/
  ```

- **FE College:** registered in the launcher, the cross-system adapters and the
  API, with `services/` beside the usual folders plus top-level `cli_main.py`,
  `gui_main.py` and `config.py`. Its API resource modules are still empty apart
  from the main-menu routes.
- **Apprenticeships:** adds `application/` and `config/`. The use cases (the
  old `services/`, moved 2026-11-06) are grouped by area under
  `application/{apprentices,employers,programmes,learning,assessments,funding,
  compliance,support,quality,records,communications,workspace,security}/`;
  `application/security/access.py` holds `Actor`. Settings are in
  `config/__init__.py` (was `config.py`), so `from ... import config` is
  unchanged. There are no top-level entry points; the launcher imports
  `interfaces/cli/shell.py` and `interfaces/gui/gui_main.py`. Its database is
  `var/data/apprenticeships/apprenticeships.db`, built by
  `infrastructure/persistence/schema.py` rather than Alembic. See
  `docs/apprenticeships/`. Deployment is the repo-root `deploy/`,
  scripts are in `tools/`, security is the platform's
  `platform/governance/security/` and the web portal is `platform/delivery/web/`. Its tests stay in
  `tests/unit/systems/apprenticeships/` and its
  HTTP routes in `api/apprenticeships/`, like every other system.

Maintenance scripts for FE College and Apprenticeships live in
`tools/college_and_apprenticeships/`.

Naming note: a `domain/**/assets/` package (primary and sixth form
each carry one) is the *fixed-asset register* business domain, with equipment
tags, custodians and warranties, and holds Python code. It is unrelated to the
static `assets/` trees above.

## Secondary School system

The Secondary School was rebuilt from scratch in November 2026 and
restructured on 2026-11-05 (`~/secondary_directory_restructure_plan.txt`) into
**feature modules**, each holding its own rules, screens and terminal menus:

```text
education_system/systems/secondary/
├── manifest.py
├── app/
│   ├── cli_main.py / gui_main.py  # Terminal menu and main window (launcher only)
│   ├── bootstrap.py               # Start-up both share: shared-session check, activity-log
│   │                              #   session, year-end rollover
│   └── routing.py                 # The sidebar catalogue: (label, key), shared by GUI and CLI
├── core/                          # Shared rules; imports no feature module
│   ├── exceptions/errors.py       # ValidationError, PermissionDenied, NotFound
│   ├── permissions/access.py      # Roles, RESTRICTED menu labels, editor sets
│   ├── academic_calendar/school_year.py  # academic_year_start, "2026/27" labels
│   └── utilities/exports.py       # safe_cell
├── infrastructure/
│   ├── database/connection.py     # secondary.db connect / schema registry / IntegrityError
│   ├── authentication/accounts.py # Logins in the shared auth.db
│   ├── logging/activity_log.py    # The activity log (ids only)
│   └── integrations/cross_system_adapter.py  # Cross-system progression adapter
├── ui/
│   ├── gui/                       # components/widgets, layouts/scroll, navigation/pages (registry)
│   └── cli/                       # prompts/prompts, menus/menus (registry)
├── resources/email_templates/     # JSON e-mail templates every module sends from
└── modules/
    ├── pupils/                    # Pupil record (pupils, contacts), directory, enrolment &
    │                              #   leavers, rollover, bulk import, alumni, pupil logins,
    │                              #   SEN details; profile_linked (profile boxes from other modules)
    ├── admissions/                # Applications, offers, waiting lists, appeals
    ├── curriculum/                # Academic year & calendar, year/form groups, form tutors,
    │                              #   teaching groups, subjects, timetable, lesson plans, cover,
    │                              #   homework, Year 9 options, enrichment
    ├── attendance/                # Registers, attendance concerns
    ├── assessment/                # Gradebook, assessment points, targets, A8/P8,
    │                              #   interventions, reports to parents
    ├── examinations/              # Mock exams, exam entries, exam results, GCSE results
    ├── behaviour/                 # Behaviour & rewards, detentions, suspensions & exclusions
    ├── safeguarding/              # Safeguarding records/reports, report a concern
    ├── send/                      # SEND register, plans, reviews, provision, access
    ├── medical/                   # Conditions, care plans, medicines, incidents
    ├── wellbeing/
    ├── staff/                     # Staff directory, departments, staff absence, single
    │                              #   central record, appraisals & CPD
    ├── communication/             # E-mail outbox and templates, parent contacts,
    │                              #   parents' evenings, announcements, letters
    ├── finance/                   # Dinner money, expense claims, budgets (+ My Expense
    │                              #   Claims / My Budgets), pupil premium
    ├── trips/                     # Trips & payments (trips, trips_ops, trips_places)
    ├── library/
    ├── progression/               # Sixth form choices and moves, incoming from primary,
    │                              #   student journey, Year 6 Transition (year6_transition:
    │                              #   cohort/liaison/friendships/enhanced/September start;
    │                              #   year6_events; year6_allocation: Year 7 forms),
    │                              #   ap_referrals (Referrals to Alternative Provision,
    │                              #   admin only; returns from the AP land on Incoming),
    │                              #   send_requests (SEND Service Requests, SENCO only;
    │                              #   EHCP decisions land on modules/send via the adapter),
    │                              #   local_authority (Local Authority: notifications, admin
    │                              #   only; LA school places land on Incoming "from LA")
    ├── portals/                   # Pupil/parent portal (incl. Messages, Money, Wellbeing),
    │                              #   parent logins, staff My Day (+ my_day_linked boxes)
    ├── reporting/                 # Attendance, behaviour, results analysis, census (+ learner
    │                              #   aims: census_aims), data export
    └── administration/            # User accounts, settings (+ sign-in policy), audit log,
                                   #   complaints
        (each module: domain/, gui/, cli/)
```

The sidebar sections (Pupil Management, Pastoral, ...) are unchanged; a
section's entries can come from several modules.

- **Wiring a screen.** Each module lists its pages in `modules/<module>/gui/__init__.py`
  (`PAGES = {key: Page(title, module, draw, state=, links=)}`) and its menus in
  `modules/<module>/cli/__init__.py` (`MENUS = {key: "module" | "module:function"}`).
  Both are plain strings, so a screen is imported only when it is opened.
  `app/gui_main` and `app/cli_main` look the menu key up there. Only entries that are
  not ordinary pages (dialogs, pickers, the My Day landing page, About) are
  methods on the main window. A key with neither shows a "not built yet" page.
- **Boundaries** (`tests/unit/systems/secondary/test_layout.py`): `core/` and
  every `modules/*/domain/` never import tkinter, sqlite3 (SQL belongs in
  `infrastructure/`), `ui/`, `app/`, the platform's delivery layer, or any
  module's `gui/` or `cli/`. A module's rules may use another module's
  `domain/`. `core/` imports no feature module and not `infrastructure/integrations/`.
  Every module has all three folders and no loose modules; `areas/`,
  `interfaces/` and top-level `cli_main.py` / `gui_main.py` must not come back.
- **Linked modules.** The pupil profile, My Day and the portal read the other
  modules through `pupils/domain/profile_linked.py`, `portals/domain/my_day.py`
  and `portals/domain/portal.py` (each section guarded, so one module failing
  never stops the page). School Settings (`administration/domain/settings.py`) feed
  the e-mail templates, letters, reports to parents, the outbox sender and
  reply-to, the census header and the main window footer.
- **Registry checks:** `tests/unit/systems/secondary/test_page_registry.py`.
- **Start-up and navigation:** `test_gui_startup.py` (marked `gui`: the window opens on My
  Day, every sidebar entry opens its page, access, logout/close, `run()`) and
  `test_cli_navigation.py` (main menu, categories, every entry opens and goes back,
  access, Logout / Switch to GUI / Shut down, `run()`). Both keep a `NOT_BUILT` set of
  sidebar entries with no screen yet (`year6_transition`); remove a key when it is built.
- Tests mirror the modules: `tests/unit/systems/secondary/<module>/`.

## Special Education (SEND) system

Rebuilt 2026-11-08 to replace the 443-file placeholder scaffold (33 areas, ~230
"not built yet" buttons). Linked to the shared login the same day:
`python -m education_system --specialeducation --gui` (or `--cli`); accounts `admin7`
(admin) and `senco1` (staff).

Linked to Primary and Secondary 2026-11-09 (`platform/cross_system/send_referrals.py`). SEND
is a service, not a school, so the pupil stays on the school's roll and the case runs
alongside the place (a concurrent enrolment):

- **School → SEND:** *SEND Service Requests* (Cross-System; SENCO / admin only in both
  schools) sends SEND advice and support, or an EHC needs assessment request. The pupil is
  found or added to the register (setting = the school, year, SEN status, census need
  code, contacts) and the request appears under **School Requests**. An assessment request
  also opens an EHCP at *Requested* unless one is already open.
- **SEND → school:** each EHCP stage goes to whichever platform school has the pupil on
  roll now (`receive_send_update` on the school adapters).
  - Secondary: the SENCO register's EHC needs assessment status/dates; Final issued sets SEN
    status E (and the issue date when the school has SEN details), Ceased sets K.
  - Primary: this year's SEND register stage plus a dated note; Final issued sets SEN
    status E, Ceased K.
  - Annual reviews and "No longer SEN" are logged for the school only. Every update is a
    `send_update` note on the school's request (`transitions.add_note`), shown on the
    board.
- Archiving a linked learner closes the case (the board shows *Case closed*); making them
  Active, or a new request, re-opens it.
- SEND saves stay saved if the platform call fails: `RecordType.after_commit` hooks
  (`infrastructure/platform_link.py`) return notices the form shows.
- Not in `paths.SYSTEM_DB_PATHS`.

```text
education_system/systems/special_education/
├── manifest.py                    # key special_education
├── __main__.py                    # hands over to the launcher with SEND pre-selected
├── app/
│   ├── routing.py                 # CATEGORIES (sidebar + CLI menus), PROFILE_TABS
│   ├── gui_main.py                # main window, same layout as secondary
│   └── cli_main.py                # text menu from the same catalogue
├── core/
│   ├── records.py                 # RecordType/Field: tables, validation, CRUD, history
│   ├── access.py                  # Principal from the shared session; admin/staff only
│   └── dates.py
├── infrastructure/
│   ├── database.py                # paths.SPECIAL_EDUCATION_DB, use_database() for tests
│   ├── cross_system_adapter.py    # PhaseAdapter: a school's request in, summary out, close
│   └── platform_link.py           # after_commit hooks: EHCP / review / register → schools
├── modules/                       # one file per area: record types + rules
│   ├── learners.py                # SEND register, parents & carers, learner voice
│   ├── requests.py                # School Requests (from linked schools, or by hand)
│   ├── needs.py                   # needs profile (four broad areas)
│   ├── support_plans.py           # SEN Support plans, targets, reviews
│   ├── ehcp.py                    # EHCP tracker (6/16/20-week), advice, annual reviews,
│   │                              # complaints/mediation/tribunals
│   ├── provision.py               # provision map, equipment, medical & care plans
│   ├── people.py                  # professionals, referrals, meetings
│   ├── funding.py                 # high needs funding, transitions
│   └── reports.py                 # dashboard, due & overdue, register, costs, CSV
└── ui/gui/
    ├── kit.py                     # the shared record list page and record form
    └── pages.py                   # learner profile, chronology, report pages
```

- A new area is a `RecordType` in a `modules/` file plus a `routing.CATEGORIES` line;
  its table, form, list, filters, CSV export and CLI menu come from the record layer.
- Data: `var/data/special_education/special_education.db` (`EDU_SPECIAL_EDUCATION_DATA_DIR`).
- Tests: `tests/unit/systems/special_education/` (each test gets a temp database); the
  school link: `tests/integration/platform/cross_system/test_send_referrals.py`.

## Adult Education system

Rebuilt 2026-11-08 to replace the placeholder scaffold. The old Learners-area rules
(duplicate check, 16+ age, ULN/NI checks, status moves, archive/restore, one main
contact, ID checks, prior qualifications, Adult Skills Fund eligibility) were carried
over. Linked to the shared login the same day:
`python -m education_system --adulteducation --gui` (or `--cli`); accounts `admin8`
(admin) and `aetutor1` (staff).

Linked to FE College and University 2026-11-09 through its adapter
(`infrastructure/cross_system_adapter.py`, journey slot `adult_education`); adult courses
run alongside other study, so links are concurrent enrolments:

- **Adult Education → FE College:** *Refer to FE College* (Teaching & Progress) hosts the
  platform's `fe_applications` board. FE accepts and enrols in its *Incoming referrals*
  screen; the learner arrives as a *19+ Adult Learner* with their prior qualifications,
  achievements and (with consent) support needs.
- **FE College → Adult Education:** FE's *Referrals to Adult Education* (People / Learners
  menu) sends a referral (`platform/cross_system/adult_education_applications.py`). The
  learner is found (journey, ULN, e-mail, name + DOB) or added as an *Enquiry* and the
  referral appears under **Referrals from FE College**. Enrolling the learner on a class
  marks it *Enrolled* and completes the platform referral; *Declined* / *Withdrawn* (with a
  reason) goes back to FE. The FE place stays open.
- **Adult Education → University:** *University Applications (UCAS)* hosts the
  platform's `university_applications` board (Access to HE; UCAS id, choices and consent
  record required). When the university confirms the place, the destination *Higher
  education* is recorded and, with no course still open, the learner is *Completed*.
- University → Adult Education is not built.

```text
education_system/systems/adult_education/
├── manifest.py                    # key adult_education
├── __main__.py                    # hands over to the launcher with Adult Education pre-selected
├── app/
│   ├── routing.py                 # CATEGORIES (sidebar + CLI menus), PROFILE_TABS
│   ├── gui_main.py                # main window, same layout as secondary / SEND
│   └── cli_main.py                # text menu from the same catalogue
├── core/
│   ├── records.py                 # RecordType/Field: tables, validation, CRUD, history
│   ├── access.py                  # Principal from the shared session; admin/staff only
│   └── dates.py
├── infrastructure/
│   ├── database.py                # paths.ADULT_EDUCATION_DB, use_database() for tests
│   ├── cross_system_adapter.py    # platform adapter: FE referrals in, export to FE /
│   │                              # university, destination on leaving
│   └── platform_link.py           # after_commit hooks: referral declined, learner enrolled
├── modules/                       # one file per area: record types + rules
│   ├── learners.py                # learners, contacts, ID checks, prior qualifications
│   ├── funding.py                 # Adult Skills Fund eligibility assessments
│   ├── courses.py                 # courses, classes (timetable), tutors, venues
│   ├── enrolments.py              # enquiries, enrolments + waiting list, fees/payments,
│   │                              # attendance registers, assessments
│   ├── progress.py                # learning goals, goal reviews, destinations
│   ├── referrals.py               # referrals from FE College (platform-linked or by hand)
│   ├── support.py                 # learning support, safeguarding, feedback/complaints
│   └── reports.py                 # dashboard, due & overdue, enrolment, attendance,
│                                  # funding, fees, achievement, destinations, CSV
└── ui/gui/
    ├── kit.py                     # the record list page and record form (own copy)
    └── pages.py                   # directory, learner profile, chronology, take
                                   # register, report pages
```

- Same record layer as SEND: a new area is a `RecordType` plus a `routing.CATEGORIES`
  line. Systems don't import each other, so the kit is a copy, not shared.
- Data: `var/data/adult_education/adult_education.db` (`EDU_ADULT_EDUCATION_DATA_DIR`).
- Tests: `tests/unit/systems/adult_education/` (each test gets a temp database); the
  FE / University links: `tests/integration/platform/cross_system/test_adult_education_links.py`.

## Alternative Provision system

Rebuilt 2026-11-08 to replace the placeholder scaffold (251 files, 31 areas,
~210 "not built yet" buttons, empty docs). Covers pupil referral units, AP schools
and commissioned placements. Linked to the shared login the same day:
`python -m education_system --alternativeprovision --gui` (or `--cli`); accounts `admin9`
(admin) and `keyworker1` (staff).

Linked to Primary and Secondary 2026-11-09 (`platform/cross_system/ap_referrals.py`):

- **School → AP:** *Referrals to Alternative Provision* (Cross-System, admin only in
  both schools) sends a referral with dual or sole registration; it appears as a New
  referral on the AP's Referrals page (pupil created as Referred, with contacts).
- **AP → school:** Accepted / Declined / Withdrawn on the referral tells the school.
  The first placement going Active completes it: dual leaves the pupil on the school's
  roll, sole has the school record a leaver first (if the school refuses, the referral
  stays admitted and re-saving the placement retries).
- **Return:** a reintegration plan saved as Completed acts on *Where on the platform*:
  home school (dual: closes the AP record only), a new Primary admission (a full
  transfer; the same primary re-opens its own former pupil), a new Secondary admission
  (lands on *Incoming from Primary*, marked "(from AP)"), or a school not on the
  platform. A confirmed permanent exclusion from the AP, or setting a linked pupil to
  Left / Reintegrated by hand, closes the AP record.
- AP saves stay saved if the platform call fails: `RecordType.after_commit` hooks
  (`infrastructure/platform_link.py`) return notices the form shows.
- Not in `paths.SYSTEM_DB_PATHS`, so GDPR, retention, Learner 360 analytics and the
  superadmin dashboard don't read the AP database yet.

```text
education_system/systems/alternative_provision/
├── manifest.py                    # key alternative_provision
├── __main__.py                    # hands over to the launcher with AP pre-selected
├── app/
│   ├── routing.py                 # CATEGORIES (sidebar + CLI menus), PROFILE_TABS
│   ├── gui_main.py                # main window, same layout as secondary / SEND
│   └── cli_main.py                # text menu from the same catalogue
├── core/
│   ├── records.py                 # RecordType/Field: tables, validation, CRUD, history
│   ├── access.py                  # Principal from the shared session; admin/staff only
│   └── dates.py                   # incl. school_day() for the sixth-day rule
├── infrastructure/
│   ├── database.py                # paths.ALTERNATIVE_PROVISION_DB, use_database() for tests
│   ├── cross_system_adapter.py    # PhaseAdapter: referral in, handover out, close
│   └── platform_link.py           # after_commit hooks: referral/placement/return → platform
├── modules/                       # one file per area: record types + rules
│   ├── learners.py                # pupils (table "learners"; UPN check letter), contacts
│   ├── referrals.py               # referrals + sixth-day provision, risk assessments
│   ├── placements.py              # providers, placements (part-time / unregistered
│   │                              # provider rules), placement reviews
│   ├── attendance.py              # AM/PM register marks, rates, persistent absence
│   ├── behaviour.py               # incidents (reasonable force), suspensions/exclusions
│   ├── safeguarding.py            # concerns, missing episodes, professionals involved
│   ├── learning.py                # plans (incl. PEP), baseline/progress, qualifications,
│   │                              # wellbeing interventions
│   ├── reintegration.py           # reintegration plans, destinations
│   ├── commissioning.py           # invoices to the commissioner
│   └── reports.py                 # dashboard, due & overdue, roll, attendance,
│                                  # behaviour, costs, outcomes, CSV
└── ui/gui/
    ├── kit.py                     # the record list page and record form (own copy)
    └── pages.py                   # directory, pupil profile, chronology, take
                                   # register, report pages
```

- Same record layer as SEND and Adult Education: a new area is a `RecordType` plus a
  `routing.CATEGORIES` line. Systems don't import each other, so the kit is a copy.
- Data: `var/data/alternative_provision/alternative_provision.db`
  (`EDU_ALTERNATIVE_PROVISION_DATA_DIR`).
- Tests: `tests/unit/systems/alternative_provision/` (each test gets a temp database);
  the school link: `tests/integration/platform/cross_system/test_ap_referrals.py`.

## Training Provider system

Rebuilt 2026-11-08 to replace the placeholder scaffold (471 files of "not built yet"
screens). Covers a commercial training provider: short courses, accredited
qualifications and CPD for individuals and employer clients. Linked to the shared login
the same day: `python -m education_system --trainingprovider --gui` (or `--cli`); accounts
`admin10` (admin) and `tptrainer1` (staff).

Linked to Apprenticeships and FE College through the platform (2026-11-09), never by import:

- **In:** an apprenticeship provider or FE college sends a training request
  (`platform/cross_system/training_provider_requests.py`, a "Training Provider Requests"
  board in each). The adapter finds or adds the learner, sets up the payer (sender or
  employer) as a client, and records it under Sessions & Bookings → Training Requests.
- **Back:** declined/withdrawn (with reason), booked or waiting list, did not attend, not
  passed and certificates go to the sender. An apprenticeship provider gets a certificate as
  off-the-job hours awaiting approval; an FE college gets it on prior attainment.
- **Out:** Progression → "Progress to Apprenticeship" and "Refer to FE College" use the
  platform's `apprenticeship_applications` / `fe_applications` boards (handover specs
  `TRAINING_PROVIDER_TO_*`; certificates travel as achieved qualifications).
- Journey slot `training_provider` (concurrent); not in `paths.SYSTEM_DB_PATHS`.

```text
education_system/systems/training_provider/
├── manifest.py                    # key training_provider
├── __main__.py                    # hands over to the launcher with TP pre-selected
├── app/
│   ├── routing.py                 # CATEGORIES (sidebar + CLI menus), PROFILE_TABS
│   ├── gui_main.py                # main window, same layout as secondary / AP
│   └── cli_main.py                # text menu from the same catalogue
├── core/
│   ├── records.py                 # RecordType/Field: tables, validation, CRUD, history
│   ├── access.py                  # Principal from the shared session; admin/staff only
│   └── dates.py
├── infrastructure/
│   ├── database.py                # paths.TRAINING_PROVIDER_DB, use_database() for tests
│   ├── cross_system_adapter.py    # PhaseAdapter: create_applicant, export_handover, …
│   └── platform_link.py           # after_commit hooks: request/booking/result/certificate
├── modules/                       # one file per area: record types + rules
│   ├── learners.py                # learners (TP ref, ULN check digit, employer funding)
│   ├── requests.py                # training requests from linked senders (or by hand)
│   ├── clients.py                 # employer clients (credit terms/limit, PO, hold),
│   │                              # contracts (discount)
│   ├── courses.py                 # catalogue, trainers (DBS), trainer approvals, venues
│   ├── sessions.py                # sessions (trainer/venue clashes, capacity), bookings
│   │                              # (waiting list, cancellation charges), register
│   ├── assessment.py              # results (pass mark, full attendance), certificates
│   ├── quality.py                 # observations, IQA sampling, feedback & complaints
│   ├── finance.py                 # invoices (VAT, credit limit), payments, raise_invoice
│   └── reports.py                 # dashboard, due & overdue, fill, achievement,
│                                  # bookings, revenue, quality, CSV
└── ui/gui/
    ├── kit.py                     # the record list page and record form (own copy)
    └── pages.py                   # directory, learner profile, chronology, take
                                   # register, issue certificates, raise invoices, reports
```

- Same record layer as SEND, Adult Education and Alternative Provision; systems don't
  import each other, so the kit is a copy.
- Data: `var/data/training_provider/training_provider.db`
  (`EDU_TRAINING_PROVIDER_DATA_DIR`).
- Tests: `tests/unit/systems/training_provider/` (each test gets a temp database);
  links: `tests/integration/platform/cross_system/test_training_provider_links.py`.

## Local Authority Education system

Rebuilt 2026-11-08 to replace the placeholder scaffold (253 files of "not built yet"
screens). Covers a local authority's education duties for the children in its area:
schools register, admissions and appeals, fair access, attendance and penalty notices,
children missing education, elective home education, exclusions, EHC needs assessments
and plans, SEND tribunals and top-up funding, and home-to-school transport. Linked to the
shared login on 2026-11-09: `python -m education_system --localauthority --gui` (or `--cli`);
accounts `admin11` (admin) and `laofficer1` (staff).

Linked to Primary and Secondary through the platform (2026-11-09), never by import
(`platform/cross_system/local_authority_links.py`):

- **In:** a school's "Local Authority" board sends attendance referrals, suspensions and
  permanent exclusions, children missing education, elective home education and EHC needs
  assessment requests. The adapter finds or adds the child, marks the school in the
  register as this platform's primary/secondary (added on first use, URN to follow) and
  records the notification as the area's own record (linked by `transition_id`). They are
  listed under Schools → School Notifications.
- **Back:** attendance stages and closures, penalty notices, exclusion provision and reviews,
  CME and EHE outcomes are notes on the school's notification. EHC decisions (requested,
  assessing/refused, draft, final, no plan, ceased) update the school's SEN record through
  its `receive_send_update`.
- **Places:** an offer *Accepted* or a fair access allocation at a linked school is handed
  over: an accepted application on Primary's Admissions, or Secondary's Incoming pupils.
  Declining it withdraws it there. The authority keeps its record (concurrent enrolment).
- Journey slot `local_authority` (concurrent); not in `paths.SYSTEM_DB_PATHS`.

```text
education_system/systems/local_authority/
├── manifest.py                    # key local_authority
├── __main__.py                    # hands over to the launcher with LA pre-selected
├── app/
│   ├── routing.py                 # CATEGORIES (sidebar + CLI menus), PROFILE_TABS
│   ├── gui_main.py                # main window, same layout as secondary / AP / TP
│   └── cli_main.py                # text menu from the same catalogue
├── core/
│   ├── records.py                 # RecordType/Field: tables, validation, CRUD, history
│   ├── access.py                  # Principal from the shared session; admin/staff only
│   └── dates.py
├── infrastructure/
│   ├── database.py                # paths.LOCAL_AUTHORITY_DB, use_database() for tests
│   ├── cross_system_adapter.py    # PhaseAdapter: notifications in, export for a place
│   └── platform_link.py           # after_commit hooks: places, casework, EHC decisions
├── modules/                       # one file per area: record types + rules
│   ├── children.py                # children (table `learners`; LA ref, UPN check letter,
│   │                              # year group), parents & carers (one main contact)
│   ├── schools.py                 # schools register (unique URN, PAN <= capacity, LA
│   │                              # admits, "on this platform" primary/secondary)
│   ├── admissions.py              # applications (closing dates, offer day, PAN, offer
│   │                              # basis), appeals (hear-by, upheld -> offer), fair access
│   ├── welfare.py                 # attendance cases, penalty notices (£80/£160, 3-year
│   │                              # limit), children missing education, EHE (consent, SAO)
│   ├── exclusions.py              # suspensions (45-day limit), permanent exclusions
│   │                              # (board review, IRP, sixth day)
│   ├── send.py                    # EHC requests (6/16/20 weeks), plans (annual review,
│   │                              # phase transfer), tribunals, top-ups
│   ├── transport.py               # eligibility (distance/SEN/unsafe/low income), routes
│   └── reports.py                 # dashboard, due & overdue, admissions, places,
│                                  # welfare, exclusions, SEND, transport costs, CSV
└── ui/gui/
    ├── kit.py                     # the record list page and record form (own copy)
    └── pages.py                   # directory, child profile, chronology, reports
```

- Same record layer as the other rebuilt systems; systems don't import each other, so the
  kit is a copy. The children table is named `learners` because the kit joins on it.
- Data: `var/data/local_authority/local_authority.db` (`EDU_LOCAL_AUTHORITY_DATA_DIR`).
- Tests: `tests/unit/systems/local_authority/` (each test gets a temp database);
  links: `tests/integration/platform/cross_system/test_local_authority_links.py`.

## University system

```text
education_system/systems/university/
├── manifest.py
├── domains/                      # 18 vertical slices (3,566 .py)
├── application/                  # Use-case orchestration (139 .py)
├── infrastructure/               # Technical adapters (485 .py)
├── plugins/                      # Optional packaged features (676 .py)
├── services/                     # Cross-domain services (135 .py)
├── shared/                       # Engines used across domains (111 .py)
├── shell/                        # System-wide composition and chrome (622 .py)
└── assets/                       # Templates and static assets
```

The dependency runs one way: the shell composes the domains, and a domain must
never import the shell.

### Domains

Each slice owns its rules in `domain/` and its screens in `interfaces/{cli,gui}/`.
Some also have `application/` and `infrastructure/`.

| Slice | .py files | Layers beyond domain and interfaces |
|---|---:|---|
| `admissions/` | 57 | |
| `assessment/` | 352 | |
| `curriculum/` | 207 | |
| `finance/` | 298 | infrastructure |
| `governance/` | 79 | application, infrastructure |
| `health/` | 283 | application, infrastructure |
| `integrity/` | 48 | |
| `learners/` | 125 | application |
| `library/` | 77 | |
| `operations/` | 788 | |
| `progression/` | 47 | infrastructure |
| `quality/` | 26 | |
| `research/` | 46 | |
| `safeguarding/` | 41 | application, infrastructure |
| `staff/` | 154 | infrastructure |
| `student_life/` | 360 | |
| `student_support/` | 246 | |
| `teaching/` | 352 | application |

`domains/admissions/domain/school_visits.py` writes a sixth form school visit into the
Admissions CRM (`campus_tours`, `admission_prospects`, `tour_registrations`). The sixth form
reaches it only through `UniversityAdapter.record_school_visit`, never by import.

`domains/operations/` still has `commerce` folders under `domain/` and
`interfaces/`. Those files are `layout-shim` forwarders to
`plugins/campus_commerce/`, and the real code is in the plugin.

### Application

```text
application/
├── academic_calendar/   ├── chatbot/      ├── graduation/   ├── programmes/
├── alumni/              ├── complaints/   ├── integrity/    ├── research/
├── assessment/          ├── evaluation/   ├── library/      ├── self_service/
├── attendance/          ├── exams/        ├── mail/         ├── statutory/
├── batch/               ├── cases/        ├── modules/      ├── students/
└── teaching/
```

Top-level modules: `case_management.py`, `connector_feeds.py`, `connectors.py`,
`lifecycle_consumers.py`, `lifecycle_handlers.py`, `outbox_dispatcher.py`,
`persistence.py` and `ports.py`.

### Infrastructure

```text
infrastructure/
├── auth/                # University auth façade and implementations
├── database/            # Connections, schemas and schema versions
├── email/               # Outbox, templates and delivery
├── communication/
├── security/
├── utils/
├── ui/                  # Shared GUI helpers
├── async_utils/  batch/  cache/  config/  data_management/  integrity/
├── logging/  monitoring/  performance/  repositories/  search/
├── validation/  workflows/
├── event_bus.py         # The university-wide event bus
├── events.py
├── shared_context.py
├── sql_safety.py
└── unit_of_work.py
```

### Plugins

```text
plugins/
├── registry.py
├── manifest.schema.json
├── campus_commerce/              # Restaurant, shops, bar, gym, betting and more (622 .py)
│   ├── plugin.json
│   ├── api/
│   ├── domain/
│   ├── infrastructure/
│   ├── interfaces/{cli,gui}/
│   └── services/
└── community_services/           # (52 .py)
    ├── plugin.json
    └── interfaces/{cli,gui}/
```

### Services and shared engines

```text
services/
├── bus/                 # Integration bus and jobs
├── events/
├── integrations/
├── pdf_export/
├── boundary_errors.py
├── credential_verifier.py
├── data_exporter.py
├── degraded_states.py
├── feature_gui_factory.py
├── operational_health.py
├── operations.py
├── retention.py
├── staff_provisioning.py
└── student_provisioning.py

shared/                  # Must not import shell/
├── ai/                  # AI engines; their screens are in shell/{cli,gui}/ai/
└── analytics/           # Analytics and reporting engines; windows in shell/gui/analytics/
```

### Shell

```text
shell/
├── cli/
│   ├── menu_router.py   # Top-level menu routing
│   ├── cli_main.py
│   ├── ai/
│   ├── auth/
│   ├── bootstrap/       # Startup and dependency wiring
│   ├── features/
│   ├── logging/
│   ├── menus/
│   ├── routing/
│   └── services/
└── gui/
    ├── main/            # Main window, navigation and portals
    ├── activity_logger/
    ├── admin/
    ├── admin_management_windows_parts/
    ├── ai/
    ├── analytics/
    ├── auth/
    ├── database/
    ├── document_manager/
    ├── email/
    ├── logging/
    ├── logic/
    ├── security/
    ├── services/
    └── tools/
```

The shell has no `api/` folder; university routes are in `education_system/api/university/`.

### Split modules

Some large modules keep their old import path while the code sits in focused
packages beside them:

```text
plugins/campus_commerce/interfaces/gui/betting/
├── betting_shop_gui.py           # Stable import
├── application.py
├── base.py
├── shared.py
├── games/
├── services/
└── tabs/

plugins/campus_commerce/interfaces/gui/nailbar/
├── nailbar_gui.py                # Stable import
├── nailbar_gui_shared.py
└── nailbar_gui_parts/

infrastructure/database/schemas/
├── admin_support_schemas.py      # Stable import
├── admin_support_schemas_shared.py
└── admin_support_schemas_parts/
```

## Migrations

```text
education_system/migrations/
├── env.py                        # Alembic environment
├── feature_schema_sql.py         # Feature-owned schema helpers
├── script.py.mako
├── README
└── versions/                     # 76 migrations on a single chain
```

`877b10b0175b_baseline.py` is the baseline. The chain must have exactly one head;
each new migration's `down_revision` points at the current head. Apprenticeships
builds its own database outside this chain.

## Tests

```text
tests/
├── conftest.py
├── fixtures/                     # Shared fixtures, including university DB isolation
├── unit/
│   ├── launcher/
│   ├── platform/
│   ├── systems/
│   │   ├── apprenticeships/
│   │   ├── adult_education/      # flat: one test file per area
│   │   ├── alternative_provision/ # flat: one test file per area
│   │   ├── training_provider/    # flat: one test file per area
│   │   ├── local_authority/      # flat: one test file per area
│   │   ├── fe_college/
│   │   ├── nursery/
│   │   ├── primary/              # One folder per domain area (academics/, pastoral/, ...)
│   │   │                         # + buttons/ (every main GUI/CLI menu entry)
│   │   ├── secondary/            # One folder per feature module (pupils/, send/, ...)
│   │   ├── sixth_form/           # domain/, domains/, infrastructure/, interfaces/
│   │   ├── special_education/    # flat: one test file per area
│   │   └── university/           # _support/, application/, domains/, infrastructure/,
│   │                             # services/, shell/
│   └── tools/
├── integration/
│   ├── migrations/
│   ├── platform/
│   └── systems/university/
├── contract/{platform,university}/
├── end_to_end/university/
├── smoke/{nursery,primary,sixth_form,university}/
├── security/{authentication,authorization,injection,isolation,resilience}/
└── performance/{benchmarks,load}/
```

Tests belong in `tests/`; test packages are not stored inside production system
packages. Primary School tests run in a sandbox (`tests/unit/systems/primary/conftest.py`,
`primary_sandbox`, made autouse by each area folder's conftest): temp primary and
platform data dirs, copied path constants repointed, and `sqlite3.connect`
refusing anything under the live `var/`. `tests/unit/systems/university/domains/` still has `academics/` and
`pastoral/` folders from before those slices were split, alongside folders for
the current slices.

## Tools

```text
tools/
├── check_layout.py               # Layout ratchet, with layout_baseline.json
├── supply_chain_check.py         # Lock and dependency checks
├── validate_deployment.py
├── project_map.py                # Builds the data for the project map explorer
├── gen_api_layout.py
├── gen_menu_routes.py
├── migrate_mfa_to_auth_db.py
├── seed_apprenticeship_offers.py
├── move_*.py, split_*.py         # One-off layout moves, kept for reference
├── college_and_apprenticeships/  # Setup, import and seed scripts
├── docs/                         # Documentation builders
└── university/                   # Architecture check and university maintenance
```

## Documentation

```text
docs/
├── README.md
├── TESTING.md
├── education_system.md
├── index.html
├── adr/                          # Architecture decision records
├── api/
├── assets/
├── changelogs/
├── operations/
├── platform/
├── reference/
├── shared/
└── {apprenticeships,fe_college,nursery,primary,secondary,sixth_form,university}/
```

## Runtime data

Runtime databases, uploads, reports, caches, logs, backups and secrets belong
under `var/`, not inside importable packages. `var/` is never committed.

```text
var/
├── backups/                      # All backups, including maintenance/
├── data/
│   ├── apprenticeships/
│   ├── fe_college/
│   ├── nursery/
│   ├── platform/                 # Includes db_files/auth.db
│   ├── primary/
│   ├── secondary/
│   ├── sixth_form/
│   └── university/               # Includes db_files/student_records.db
├── logs/
├── run/
├── scratch/
├── secrets/
└── tmp/
```

Use the path constants in `education_system.paths` rather than building runtime
paths by hand. It is the single source of truth for every filesystem path. The
nine per-system `paths.py` modules were consolidated into it because 60 of their
225 names collided: `DATA_DIR`, `STAFF_DB` and `ensure_directories` meant
different files in different packages.

Every constant carries the prefix of the system that owns it, such as
`UNIVERSITY_`, `SIXTH_FORM_` or `PLATFORM_`. Only `SRC_ROOT`, `REPO_ROOT`,
`VAR_DIR` and the deprecated `PROGRAM_ROOT` alias are unprefixed. Anchor runtime
state on `VAR_DIR`. Directories are never created on import; call the relevant
`ensure_*_directories()` at startup, or `ensure_all_directories()`.

`education_system.paths` is a package split by owner (`core`, `platform_shared`,
`systems/<system>`, `registry`), but always import from the package itself:
`paths.X` / `from education_system.paths import X`. Two things depend on that.
Tests monkeypatch `paths.<NAME>`, and the backup and `ensure_*` functions live in
`paths/__init__.py` so they read the patched value. And `importlib.reload(paths)`
reloads every part in order, so `EDU_*_DATA_DIR` overrides still take effect.
A new constant goes in its owner's module **and** in `_exports.py`'s `__all__`.

## Import conventions

- Use absolute imports beginning with `education_system` across architectural
  boundaries.
- Use relative imports only within a cohesive package.
- Import shared capabilities from `education_system.platform`, not from another
  system package. Systems never import each other; cross-system work goes through
  the adapters in `platform/cross_system/`. `tests/contract/cross_system/test_system_boundaries.py`
  fails on any direct import between two of the seven systems.
- Keep domain modules independent of Tkinter, Flask and CLI presentation code.
- Do not add package directories directly to `sys.path`; run with `src/` as the
  application root or install the project. Never put `src/education_system/`
  itself on `sys.path`, because its `platform/` package would shadow the standard
  library `platform` module.

## Primary entry points

`main()` and argument parsing live in `education_system/launcher/main.py`.
`education_system/__main__.py` forwards to it, so an installed package can be
started with `python -m education_system`.

```text
run.py
src/education_system/__main__.py
src/education_system/launcher/main.py
src/education_system/launcher/systems.py
src/education_system/platform/delivery/api/unified_server.py
src/education_system/platform/delivery/api/registry.py
src/education_system/systems/university/shell/cli/menu_router.py
src/education_system/systems/university/shell/gui/main/main_gui.py
src/education_system/systems/sixth_form/interfaces/cli/cli_main.py
src/education_system/systems/sixth_form/interfaces/gui/gui_main.py
src/education_system/systems/apprenticeships/interfaces/cli/shell.py
src/education_system/systems/apprenticeships/interfaces/gui/gui_main.py
src/education_system/systems/{nursery,primary,fe_college}/cli_main.py
src/education_system/systems/{nursery,primary,fe_college}/gui_main.py
src/education_system/systems/secondary/app/cli_main.py
src/education_system/systems/secondary/app/gui_main.py
src/education_system/systems/special_education/app/cli_main.py
src/education_system/systems/special_education/app/gui_main.py
src/education_system/systems/adult_education/app/cli_main.py
src/education_system/systems/adult_education/app/gui_main.py
src/education_system/systems/alternative_provision/app/cli_main.py
src/education_system/systems/alternative_provision/app/gui_main.py
src/education_system/systems/training_provider/app/cli_main.py
src/education_system/systems/training_provider/app/gui_main.py
src/education_system/systems/local_authority/app/cli_main.py
src/education_system/systems/local_authority/app/gui_main.py
```

See [ADR 0018](../adr/0018-repository-layout.md) for layout decisions and the
[University documentation](../university/README.md) for system-specific
architecture and ownership guidance.
