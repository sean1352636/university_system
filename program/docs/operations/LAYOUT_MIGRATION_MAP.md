# Layout Migration Map

Companion to [ADR 0018 — Repository Layout Consolidation](../adr/0018-repository-layout.md).

This document records where **every** existing file lands in the proposed layout. The empty
directory skeleton at `program/` in the repository root was generated from this mapping —
every directory in it exists because at least one real file maps into it.

**Coverage as of 2026-07-25:** 8,413 files under `education_system/` classified, **0 unmapped**,
producing 1,706 destination directories and 1,597 distinct source-directory → destination-directory
pairs. The full pair list is in [`layout-migration-map.tsv`](layout-migration-map.tsv).

**Flattening is the recurring defect in this map.** Three times a rule collapsed a whole sub-tree
into one directory, and each time filenames collided: `interfaces/gui/` (20 source dirs),
`assets/templates/` (63 dirs, 20 colliding names — `refund_receipt.json` alone lives in 11
category directories), and `var/data/` (109 MB of NLTK corpora and per-language locales, 98
colliding names). Any new rule that maps `<dir>/**` to a single destination should be assumed
wrong until the collision check passes.

A source directory may appear on more than one row when its files split across destinations — see
[University tests](#university-tests) for the largest such case.

---

## Top-level routing

| Source | Destination |
|--------|-------------|
| `education_system/shared/**` | `education_system/platform/**` |
| `education_system/<system>/modules/domain/**` | `education_system/systems/<system>/domain/<area>/**` |
| `education_system/<system>/modules/shared/{cli,gui}/**` | `education_system/systems/<system>/interfaces/{cli,gui}/shell/**` |
| `education_system/<system>/modules/shared/utils/**` | `education_system/systems/<system>/infrastructure/utils/**` |
| `education_system/<system>/modules/shared/services/**` | `education_system/systems/<system>/services/**` |
| `education_system/<system>/modules/shared/{config,constants}/**` | `education_system/systems/<system>/infrastructure/config/**` |
| `education_system/<system>/modules/services/**` | `education_system/systems/<system>/services/bus/**` |
| `**/domain/**/{cli,gui}/**`, `**/infrastructure/**/{cli,gui}/**` | `education_system/systems/<system>/interfaces/{cli,gui}/**` |
| `education_system/<system>/{core,infrastructure,utils}/**` | `education_system/systems/<system>/infrastructure/**` |
| `education_system/<system>/api/**` | `education_system/systems/<system>/interfaces/api/**` |
| `education_system/<system>/{cli_main,gui_main,main_gui,menu}.py` | `education_system/systems/<system>/app.py` |
| `education_system/<system>/{templates,web}/**` | `education_system/systems/<system>/assets/**` |
| `education_system/<system>/tests/**` | `tests/systems/<system>/**` — mirroring the *new* code tree, not the old test tree |
| `education_system/shared/tests/**` | `tests/platform/**` |
| `education_system/post_18/university_system/scripts/**` | `tools/university/**` |
| `**/{data,logs,backups,.benchmarks}/**` | `var/**` (gitignored) |
| `**/README.md` | `docs/**` |
| `education_system/post_1{6,8}/__init__.py` | *deleted* — the age-band wrappers disappear |

## `shared/` → `platform/`

The 45 unsorted entries regroup by role:

| Destination | Absorbs |
|-------------|---------|
| `platform/kernel/` | `base`, `core`, `database`, `validation`, `seeding`, `backup`, `branding.py` |
| `platform/identity/` | `auth`, `student_id`, `staff_directory` |
| `platform/governance/` | `audit`, `gdpr`, `safeguarding`, `security`, `academic_misconduct` |
| `platform/features/` | `analytics`, `bank_holidays`, `calendar`, `certificates`, `documents`, `i18n`, `lms`, `messaging`, `notifications`, `reporting`, `transcript`, `offline`, `extras` |
| `platform/delivery/` | `api` (incl. `api/web`), `cli`, `gui`, `admin_portal` → `portals/admin`, `student_portal` → `portals/student` |
| `platform/integrations/` | `email`, `integrations` → `external`, `webhooks` |
| `platform/cross_system/` | `cross_system` |
| `platform/services/`, `platform/testing/`, `platform/assets/` | `services`, `testing`, `templates` |

## Domain areas

Eleven areas, identical in all five systems:

`academics` · `assessment` · `admissions` · `learners` · `pastoral` · `safeguarding` ·
`finance` · `staff` · `operations` · `governance` · `progression`

`admissions` covers everything before enrolment (applications, offers, intake, settling-in);
`learners` holds the enrolled record itself (`children` / `pupils` / `students`, contacts, leavers,
alumni). That line is what stops the two from bleeding into each other.

Recurring sub-areas that earn their own level because every system has them:
`academics/attendance`, `academics/enrichment`, `pastoral/health`, `pastoral/send`,
`operations/communications`, `operations/reporting`, `governance/audit`, `governance/compliance`.

### Nursery and Primary (flat → areas)

The ~90 sibling directories per system fold in. Representative calls:

| Area | Nursery features absorbed |
|------|---------------------------|
| `operations/daily_care` | `bottle_feeds`, `collections`, `daily_diary`, `kitchen`, `meals`, `sleep_log`, `toileting_log` |
| `pastoral/health` | `accident_log`, `accident_report`, `allergies`, `existing_injuries`, `first_aid`, `medication_log` |
| `operations/communications` | `activity_feed`, `daily_updates`, `email_centre`, `messaging`, `newsletters`, `parent_contacts`, `parent_meetings`, `parent_requests` |
| `assessment` | `cohort_tracking`, `development_tracking`, `evidence`, `eyfs_profile`, `observations`, `progress_check_2yr` |
| `safeguarding` | `concerns`, `dsl`, `looked_after`, `prevent_duty`, `safeguarding` |
| `operations` | `inventory`, `occupancy`, `ratios`, `ratio_alerts`, `rooms`, `sessions`, `visitors` |

Primary follows the same rules, with `ks1_sats`/`ks2_sats`/`mtc`/`phonics*`/`reading_levels` →
`assessment`, and `wraparound` → `operations/daily_care`.

### Secondary and Sixth Form (themes → areas)

Their existing themes map almost 1:1 — `academics`, `assessment`, `finance`, `governance`,
`pastoral`, `progression` keep their names; `reports` → `operations/reporting`;
`pupils`/`students` → `learners`. The one theme that splits is **`staff_comms`**, which today
mixes two unrelated concerns: staff records (`appraisals`, `cpd`, `dbs_checks`, `departments`,
`recruitment`, `staff*`) → `staff`, and communications (`announcements`, `messages`, `notices`,
`notifications`, `letter_templates`, `parent_contacts`, `parents_evenings`) →
`operations/communications`.

### University (9 categories → areas)

| Current category | Destination |
|------------------|-------------|
| `academics` | `academics` (with `grading`, `academic_progress`, `external_examiners`, `mitigating_circumstances` → `assessment`; `placements`, `apprenticeships` → `progression`) |
| `admissions` | `admissions` (`hesa_export` → `governance/compliance`) |
| `analytics` | `operations/reporting` |
| `campus` | `operations/campus` |
| `commerce` | `operations/commerce` |
| `finance` | `finance` |
| `health` | `pastoral/health` |
| `operations` | `operations` (`communications` → `operations/communications`, `legal` → `governance/legal`, `staff_hr` → `staff`) |
| `student_affairs` | `pastoral` (`safeguarding` → `safeguarding`, `student_id` → `learners`, `events`/`student_union` → `pastoral/student_life`, `employer_portal`/`portfolio` → `progression`, `international_compliance` → `governance/compliance`) |

### University pillars

The 3,481 code files land in five pillars rather than four. `services/` is the addition — it holds
cross-domain application services that are neither business logic nor technical plumbing:

| Pillar | Files | Holds |
|--------|------:|-------|
| `interfaces/` | 1,912 | every `cli/`, `gui/` and `api/` in the system |
| `domain/` | 1,054 | the eleven areas — business logic only |
| `infrastructure/` | 395 | flat: `auth`, `database`, `email`, `logging`, `security`, `ai`, `search`, `utils`, … (32 entries) |
| `services/` | 117 | `bus` (cross-domain events), `analytics`, `integrations`, `pdf_export`, `dashboard`, `business_intelligence`, `ai_features`, `communication` |
| `assets/` | 2 | templates, web |

`interfaces/` holding 55% of the system is a fact about this codebase, not an artefact of the
mapping — the Tkinter surface really is that large. `interfaces/cli/` and `interfaces/gui/` each
carry the same eleven area names plus `shell/` for system-level UI that belongs to no single area
(`main`, `database`, `email`, `enhanced_reporting`, `batch_operations`, `advanced_search`,
`document_manager`, `activity_logger`, `student_analytics`, `admin`, `auth`, `security`, `tools`,
`logic`, plus `ai`, `logging` and `services` hoisted out of infrastructure and the bus).

**The interface split is applied in full.** Every `cli/` and `gui/` directory nested inside
`domain/` or `infrastructure/` — 626 files across 150 directories — moves to
`interfaces/{cli,gui}/<area>/<feature>/`. Zero remain. That is what makes the ADR 0007 split
structural rather than a naming convention; an earlier draft of this map claimed it while leaving
those 626 files in place.

Three consequences worth stating plainly:

- **`modules/shared/` no longer collapses into `interfaces/`.** Its `utils/` (69 files:
  `document_manager`, `activity_logger`, `batch_operations`) are infrastructure and its `services/`
  (93 files) are services. Routing them to `interfaces/` put them in the wrong pillar *and*
  contradicted the test mapping, which already sent their tests to `infrastructure/`.
- **`modules/shared/gui/` keeps its shape.** Twenty source directories with real nesting
  (`enhanced_reporting/{tabs,mixins,dialogs,standalone}`, `database/{dialogs,operations,scheduling}`,
  `email/email_gui/chat_dialogs`, `batch_operations/mixins`) previously flattened into a single
  274-file directory. They now land under `interfaces/gui/shell/` with their sub-structure intact.
  The largest directory anywhere in the tree is now 34 files.
- **`domain/_services/` is gone.** The underscore-prefixed node was the only one of its kind; its
  24 bus files move to `services/bus/` and its 89 CLI/GUI files to `interfaces/{cli,gui}/shell/services/`.

Two smaller corrections: `domain/learners/` gains `alumni` (from
`student_affairs/services/alumni_management`), so the area that anchors the admissions↔learners line
holds 22 files rather than 7; and `domain/pastoral/wellness` + `student_wellbeing` merge into
`pastoral/wellbeing/`.

### `infrastructure/` stays flat — a rejected change worth recording

An earlier draft of this map regrouped `infrastructure/`'s 20-odd children into six buckets
(`data`, `platform`, `comms`, `observability`, `intelligence`, `utils`), by analogy with
`shared/` → `platform/`. **It was tried and reverted.** The analogy does not hold: `shared/` was
being renamed wholesale, so every reference to it changed anyway, whereas `infrastructure/` keeps
its name and its own `__init__.py` loads its children by name:

```python
from education_system.systems.university.infrastructure import auth      # -> platform/auth
from education_system.systems.university.infrastructure import database  # -> data/database
```

Seventeen statements of that shape broke, sixteen of them inside `infrastructure/__init__.py`'s
lazy loader. Flattening back fixed all seventeen without editing any of them.

The lesson generalises to the phases still to come — see below.

`workflows` (7 files) may belong in `services/` rather than `infrastructure/` — unresolved, but it
is a single-directory question, not a regrouping.

## `from <package> import <submodule>` — the rewrite blind spot

A path-based import rewrite matches dotted chains (`education_system.a.b.c`). It cannot see a
submodule named after the `import` keyword:

```python
from education_system.systems.university.infrastructure import auth
#                                                              ^^^^ invisible to the rewrite
```

If a move changes which package a submodule lives in, every import of this shape silently breaks —
and it breaks at **runtime**, not at parse time, so `ast.parse` and syntax checks report nothing.
This is the one failure mode that survived a 31,908-substitution rewrite with 0 syntax errors.

Two rules for the remaining phases:

1. **A phase that only renames a package is safe.** All references to it are dotted and get
   rewritten. `shared/` → `platform/` is this kind.
2. **A phase that re-parents submodules inside a package that keeps its name is not.** Grep for
   `from <that package> import` before and after, and check every imported name still resolves.

The scan is cheap. Restrict it to `ast.ImportFrom` nodes whose module is a **directory** (not a
`.py` file), then check each imported name against `<pkg>/<name>.py` and `<pkg>/<name>/`. Without
the directory restriction the check reports every `from module import function` in the codebase as
a failure — roughly 39,000 false positives against 21 real ones.

### Reconciled with ADR 0018

Three places where this mapping had moved past the ADR are now closed — ADR 0018 (still
**Proposed**) was amended to match, rather than the map bent back to fit it:

1. The canonical per-system shape gains the `services/` pillar and states the no-exceptions rule
   for interface code.
2. The shared domain vocabulary gains `learners`, taking it from ten areas to eleven.
3. The target tests tree matches what is built: `tests/{platform, systems/*, tools, launcher,
   migrations}`, with `integration/` and `smoke/` inside each system rather than at the root, and
   no `e2e/`.

---

## University tests

The 589 test files are the one case where a directory-level mapping was not enough. The old
`tests/` tree mirrored the *old* domain layout, so a straight 1:1 copy would have left the tests
describing a structure the code no longer has — `tests/domain/academics/grading/` next to
`domain/assessment/grading/`, and 27 top-level `tests/domain/` children against 11 code areas.

**The rule is: the test tree mirrors the code tree, one level for one level.** A module at
`domain/<area>/<feature>/` has its tests at `tests/systems/university/domain/<area>/<feature>/`.
Cross-cutting suites (`integration/`, `smoke/`, `_support/`) stay as top-level siblings because they
belong to no single module. GUI and CLI tests follow the code into `interfaces/`, which is what
keeps the ADR 0007 split honest on the test side too.

Twelve source directories held loose, unrelated test files and split across destinations, so they
appear on several rows in the TSV. The largest splits:

| Source | Splits into |
|--------|-------------|
| `tests/domain/student_affairs/` (49) | `pastoral/` · `safeguarding/` · `progression/` · `governance/compliance/` · `interfaces/gui/pastoral/` |
| `tests/domain/academics/` (7 loose) | `academics/services/{library, lms, plagiarism, module_scheduling, admissions_selection}` · `pastoral/services/early_warning` |
| `tests/domain/campus/` (6 loose) | one dir each under `operations/campus/` |
| `tests/domain/commerce/` (6 loose) | `operations/commerce/{cinema, restaurant}` |
| `tests/domain/{musicshop, nailbar, phoneshop, mail, research}` | `*_core.py` → domain, `*_gui.py` → `interfaces/gui/` |

Merges in the other direction, where one concept was tested from two places:

| Merged | Into |
|--------|------|
| `tests/sal/` (13) + `tests/shared/utils/simple_activity_logger/` (14) | `infrastructure/activity_logger/` — "SAL" is Simple Activity Logger |
| `tests/domain/staff_hr/` (5) + `tests/domain/operations/staff_hr/…` (6) | `domain/staff/staff_hr/` |
| `tests/domain/housing/` (2) + `tests/domain/campus/housing/…` (4) | `domain/operations/campus/housing/` |
| `tests/domain/commerce/restaurant/` (17) + 4 loose `test_commerce_*.py` | `domain/operations/commerce/restaurant/` |

Six test directories named something no module is called were renamed to their subject, established
by reading what each imports: `virtual` → `virtual_classroom`, `exam_portal` → `exam_management`,
`scheduling` → `module_scheduling`, and `accreditation`/`transfer_credits`/`catalog` →
`interfaces/cli/academics/` (all three test `domain/academics/cli`).

Two items leave the system tree entirely: `tests/logs/app.log` → `var/` (gitignored), and the 13
tests covering `scripts/` → `tests/tools/university/`, following the code they exercise.

### Known wrinkles

- `infrastructure/utils/` (24 files) could not merge into `infrastructure/core/`: four filenames
  collide exactly — `test_console_output.py`, `test_paths.py`, `test_sql_safety.py`,
  `test_exceptions.py`. Either that is duplicate coverage or one set tests a shim; resolve before
  the move, not during it.
- `tests/services/cli/` (25) lands as one bucket at `interfaces/cli/services/`, but its contents are
  per-feature (`test_barber_cli.py`, `test_cinema_cli.py`, …) and would split cleanly under
  `interfaces/cli/operations/commerce/`.
- Nothing is wired up yet: `conftest.py` paths, `pyproject.toml` ignore lists, and import roots are
  untouched.

---

## The other four systems' tests

The same mirror rule applies, but only where there is enough to mirror. Test volume is wildly
uneven across the platform:

| System | Test files | Code files | Domain dirs | Split? |
|--------|-----------:|-----------:|------------:|--------|
| University | 567 | 3,501 | 103 | yes — see above |
| Sixth Form | 19 | 559 | 131 | **yes** |
| Nursery | 7 | 389 | 89 | not yet |
| Primary | 4 | 421 | 99 | not yet |
| Secondary | 4 | 437 | 109 | not yet |

**Sixth Form splits now.** Nineteen files across eight destinations, every one of them verified
against the code skeleton: `academics/{academic_year, library, timetable_optimiser}`,
`learners/advanced_search` (3 files), `admissions/enrolments`, `finance/finance_hub`,
`assessment/risk_analytics`, `progression/ucas_workflow`, `governance/automation_rules`,
`operations/communications/parent_portal`, plus `interfaces/{api,cli,gui}`, `infrastructure/` and
`smoke/`.

**Nursery, Primary and Secondary stay flat.** Four to seven files each, and for Primary and
Secondary none of them is a domain test — `test_cli_main`, `test_gui_viewmodel`, `test_paths`,
`test_smoke` are interface and infrastructure smoke checks. Splitting 4 files across 11 areas would
produce empty scaffolding, so the map keeps them flat at `tests/systems/<system>/`.

**Target rule for all five systems:** tests mirror the code tree. A system adopts subdirectories
once its suite justifies them — roughly when domain tests start appearing. Nursery is closest: its
three newest files already have obvious homes (`test_collections.py` →
`operations/daily_care/collections`, `test_ratio_alerts.py` → `operations/ratio_alerts`,
`test_sessions.py` → `operations/sessions`). Route new tests there as they are written rather than
moving them twice.

## `shared/tests/` → `platform/`

Fifty-four files that mapped flat to `tests/platform/`, now grouped to match the eight platform
groups — the same defect that affected university, at a scale that already justifies the fix:

| Group | Files | Notes |
|-------|------:|-------|
| `identity/auth` | 10 | includes `test_security.py`, whose imports are all `auth.*` despite the name |
| `features/` | 15 | `lms` (7), `analytics` (2), then one each for `bank_holidays`, `calendar`, `certificates`, `documents`, `messaging`, `notifications`, `offline` |
| `governance/` | 8 | `security` (6), `audit`, `gdpr` |
| `cross_system/` | 4 | includes `test_identity_backfill.py` — `identity_backfill` lives in `cross_system` |
| `delivery/` | 5 | `api` (3), `gui`, `portals/admin` |
| `services/` | 3 | `kernel/` 2, `integrations/email` 1, `identity/student_id` 1 |

Two files leave `platform/` entirely, because their subjects do not move in this migration:
`test_launcher.py` → `tests/launcher/` and `test_migrations.py` → `tests/migrations/`, mirroring
`education_system/launcher/` and `education_system/migrations/` staying put.

`test_shared_services.py` stays at the `tests/platform/` root — it spans `analytics` and `audit`
and has no single home.

---

## Files with no home in the new tree

Five on-disk paths have no home in a package directory. Four are untracked; **one is committed**:

| File | Disposition |
|------|-------------|
| `post_18/university_system/.keys/.encryption_master_key` | → `var/secrets/` (gitignored). A live key inside a package directory is one stray `git add -f` away from being committed. |
| `.../modules/domain/student_affairs/safeguarding/.safeguard.key` | → `var/secrets/`. Same defect, one level deeper — a mode-`600` key **nested inside a domain module**, which is why the first pass routed it as source code. Untracked only because `*.key` happens to be in `.gitignore`. |
| `.../modules/domain/student_affairs/safeguarding/secure_uploads/` | → `var/data/university/secure_uploads/`. Runtime uploads, not source. **Its one file is tracked in git** (`20260521082258_49f60741_hello.txt.enc`) — it looks like a test artefact, but it is a committed file in a secure-uploads directory and should be removed from history, not just moved. |
| `post_18/university_system/.env` | *deleted* — config belongs at the repository root, next to the existing `.env.example`. |
| `secondarysch_system/.claude/settings.local.json` | *deleted* — stray per-directory settings file. |

`var/` being a single ignored tree at the root is what makes this hold: there is no longer a
plausible-looking package path for a secret or a runtime artefact to hide in. Enforcing that
required adding a plain `var/` rule to `.gitignore` — the existing rules were extension-based
(`*.db`, `*.log`, `*.key`) and missed the bulk of it: NLTK corpora (`.zip`, `.pickle`), HTML
reports, per-language locale JSON, and date-suffixed log files like `app.2026-06-25`.

When the tree is staged, secret **material** is not duplicated: the destination directory is
created and the mapping recorded, but the key bytes stay where they are. A key copied to a second
location is a key twice as likely to leak, and a layout preview gains nothing from holding it.
