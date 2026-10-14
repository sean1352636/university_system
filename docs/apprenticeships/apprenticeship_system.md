# Apprenticeship System

Work-based learning: employed apprentices, off-the-job training, and
independent End-Point Assessment.

The sixth system behind the unified launcher. It is not a school with
different vocabulary — an apprenticeship has an employer and an
independent assessment organisation standing outside the training
provider, and almost every design decision below follows from that.

```bash
python -m education_system --apprenticeships --gui
python -m education_system --apprenticeships --cli
```

There is no per-system login. The launcher authenticates against the
shared platform account and hands the session over; an unauthenticated
call raises rather than prompting.

---

## The five roles

Five parties share one database, and three of them are outsiders. Roles
live in `config.ROLE_PERMISSIONS` and are the *only* place a capability
is granted.

| Role | Who they are | What the system is for them |
|---|---|---|
| `admin` | Provider administrator | Programmes, employers, funding, compliance, accounts |
| `staff` | Tutor / assessor / IQA | A caseload: delivery, portfolio assessment, reviews |
| `apprentice` | The learner | Their own record, hours log, portfolio, reviews |
| `employer` | The employing organisation | Their own apprentices, approvals, reviews, feedback |
| `end_point_assessor` | The EPAO | Gateway decisions and grading — nothing formative |

### Two capabilities the provider must never hold

```python
EPAO_EXCLUSIVE = frozenset({"gateway.approve", "epa.grade"})
```

`ROLE_PERMISSIONS[ADMIN]` is built by *subtracting* that set from every
permission. A training provider deciding that its own apprentice has
passed gateway, or grading the assessment it is paid for the apprentice
completing, is exactly what independent End-Point Assessment exists to
prevent — so the provider administrator, who can otherwise do
everything, cannot do those two things. This is load-bearing: do not
"fix" it by granting them.

### Scope is not the same as permission

`services/access.py` defines an `Actor` carrying both the role and the
records it resolves to (`apprentice_id`, `employer_id`, `staff_id`).
Permission answers *may you do this at all*; scope answers *to whom*.

Both are enforced in the service layer, never in a window or a menu. An
unresolved scope produces an impossible filter (`-1`) rather than an
empty one, so a half-provisioned login sees nothing instead of
everything. That direction is deliberate — see
`access.apprentice_filters`.

A login that holds a role but is not linked to a record signs in
successfully and finds empty screens. That is a real state, not an
error, so every screen says so in words rather than showing a blank
table; **System → User Accounts** flags them and offers the link.

---

## The rules that decide whether somebody finishes

### Off-the-job hours

The single most audited number in an apprenticeship. Six hours a week
averaged across the practical period, pro-rated below a 30-hour week.
The target is **computed from the programme dates, never stored**
(`domain/training/off_the_job_hours.target_hours`), so moving a planned
end date re-baselines it.

Only **approved** hours count. Two paths feed the same log:

- an apprentice records an activity and an approver signs it, or
- a tutor marks a register, and the session's hours land already
  approved — attending taught delivery *is* off-the-job training, and
  making the apprentice retype hours their trainer just watched is how
  logs end up under-recorded and funding gets clawed back.

Register-generated entries are keyed on the session, so re-marking a
register corrects the hours it already produced rather than adding a
second entry.

### Portfolio

Evidence is mapped to KSBs, and each mapping carries a coverage
judgement. An apprentice may claim *Not started* or *Developing*; only
an assessor may record **Competent**, because that is the judgement the
gateway check reads. Otherwise a portfolio could declare itself complete
and walk somebody into an assessment nobody had verified them ready for.

### Progress reviews

Tripartite: provider, apprentice and employer. A review is worth nothing
as funding evidence until all three have signed, and each actor may only
sign the line belonging to the party they actually are — refused for
every role, administrators included. The third signature completes the
review automatically.

### Gateway

Seven requirements (`config.GATEWAY_REQUIREMENTS`). Six are **automatic**
— recomputed from the hour log, the functional skills, the portfolio and
the reviews on every read, and impossible to tick by hand. One is
**manual**: the employer's confirmation, which no system can derive.

Recomputing rather than storing is the point: a hand-back of approved
hours or a KSB reopened for more evidence takes the requirement with it,
which is what gateway is there to catch.

The provider requests; the EPAO approves or rejects. A rejection returns
the apprentice to On Programme rather than leaving them in limbo.

### End-Point Assessment

A standard is assessed by several *methods*, each booked, sat and graded
separately. Grading is final — a correction is another sitting, not an
edit. The overall grade is the **lowest** achieved across the methods,
not an average: a distinction in the project does not paper over a bare
pass in the discussion.

Passing the last required method completes the apprenticeship, which is
what releases the withheld completion payment. That happens as a
consequence of the grade rather than as a separate administrative act,
because completion is the event the provider is paid for.

---

## Layout

```
education_system/systems/apprenticeships/
├── config.py                 # Roles, permissions and every closed vocabulary
├── manifest.py               # Key, display name, interfaces
├── domain/                   # Pure rules, one package per area: apprentices,
│                             #   admissions, programmes, employers, training,
│                             #   portfolio, reviews, progress, learner_support,
│                             #   records, quality, workspace, end_point_assessment,
│                             #   funding, compliance, staff, degree_apprenticeships
├── services/                 # Actor-first orchestration; the only write path
├── infrastructure/
│   ├── persistence/          # One SQLite file, schema.py, repositories/
│   ├── storage/              # Uploaded documents, under var/ (never in git)
│   └── integrations/         # Cross-system handover, degree events,
│                             #   read-only university gateway
├── interfaces/
│   ├── cli/                  # shell, menus, prompts, commands/
│   └── gui/                  # gui_main, session, widgets,
│                             #   windows/<role>/ and windows/shared/
└── assets/templates/email/
```

The launcher starts `interfaces/cli/shell.run` and
`interfaces/gui/gui_main.run` directly; there are no top-level
`cli_main.py` / `gui_main.py` modules.

### Feature map

Every feature follows the same four layers, and every one is reachable
from both interfaces. A screen used by more than one role lives once in
`windows/shared/`; the service decides what each role may see and do.

| Feature | Domain | Service | GUI | CLI |
|---|---|---|---|---|
| Attendance and absence | `training/attendance.py` | `training_service` | staff register, dashboards | `training` |
| Individual learning plan | `training/learning_plan.py` | `learning_plan_service` | `shared.learning_plan` | `learning_plan` |
| Action plans | `reviews/action_plans.py` | `action_plan_service` | `shared.actions` | `actions` |
| Assignments | `progress/assignments.py` | `assignment_service` | `shared.assignments` | `assignments` |
| Skills (KSB) matrix | `progress/skills_matrix.py` | `skills_matrix_service` | `shared.skills_matrix` | `skills_matrix` |
| Functional-skills assessments | `learner_support/skills_assessments.py` | `skills_service` | `shared.functional_skills` | `functional_skills` |
| Qualifications | `learner_support/qualifications.py` | `qualification_service` | `shared.qualifications` | `qualifications` |
| Support and adjustments | `learner_support/support_arrangements.py` | `support_service` | `shared.support` | `support` |
| Welfare and risk | `learner_support/welfare.py` | `welfare_service` | `shared.welfare` | `welfare` |
| Documents | `records/documents.py` | `document_service` | `shared.documents` | `documents` |
| Signatures | `records/signatures.py` | `signature_service` | `shared.signatures` | `signatures` |
| Audit (before → after) | `records/audit.py` | `compliance_service` | `admin.audit_log` | `audit` |
| Employer contacts and commitments | `employers/contacts.py` | `employer_contact_service` | `shared.employer_contacts` | `employer_contacts` |
| Employer risk | `employers/risk.py` | `employer_risk_service` | `admin.employer_risk` | `employer_risk` |
| Curriculum and programme versions | `programmes/curriculum.py`, `versions.py` | `programme_service` | `admin.programmes` | `programmes` |
| Admissions stages | `admissions/stages.py` | `admissions_service` | `shared.admissions` | `admissions` |
| Complaints, appeals, surveys | `quality/` | `complaint_`, `appeal_`, `survey_service` | `shared.complaints`, `.appeals`, `.surveys` | same names |
| Tasks, calendar, workload, search | `workspace/items.py` | `task_`, `calendar_`, `workload_`, `search_service` | `shared.tasks`, `.calendar`, `.workload`, `.search` | same names |

The tasks, calendar, workload and search services pull from the others
through small provider functions; a provider that fails is logged and
skipped rather than emptying the list. Rules worth knowing before
changing any of them:

- **EPA independence carries through.** Appeals against an EPA result
  are visible to and decided by the end-point assessor only; the
  provider admin can neither see nor decide them.
- **Welfare is provider-only twice over**: by permission, and by a role
  check in the service, so a mistaken grant in `config.py` still would
  not open it to apprentices, employers or the EPAO. Task lists show a
  concern's severity and category, never its description.
- **Survey results are withheld below three responses**, because an
  average of one or two answers identifies the person.
- **A superseded programme version takes no new starts**, but its
  apprentices keep it and it stays schedulable for training.
- **Admission stages** (Application → Offer → Enrolment) live inside
  admissions; the apprentice status stays `Applicant` until accepted.

Every service function takes `actor` first. That is not decoration:
reads are scoped, writes are refused, and the approval queue an employer
opens holds their own apprentices only.

### Interfaces

The CLI menu tree (`interfaces/cli/menus.py`) and the GUI navigation
tree (`interfaces/gui/gui_main.NAV_BY_ROLE`) are deliberately the same
shape, so an apprentice talked through a task over the phone finds the
same options in the same groups whichever interface they are in.

Both build on one toolkit rather than per-module copies — `widgets.py`
for Tk, `prompts.py` for the terminal — because at sixty windows the
duplication would be the dominant cost. A screen more than one role
opens lives once in `windows/shared/`; the service scopes what each
role sees in it.

There is no web portal. The HTTP routes live outside this package, in
`src/education_system/api/apprenticeships/`: generated from the menu
tree, each answers 501 until it is backed by a service.

`tests/unit/systems/apprenticeships/test_layout.py` keeps star
re-export shims and docstring-only placeholder modules out of the
package. A planned module belongs in these docs until it has code.

---

## Data and accounts

The database is `var/data/apprenticeships/apprenticeships.db`,
one file for every table — the screens are join-heavy by nature, so
splitting them would buy nothing. Paths come from
`education_system/paths.py` under the `APPRENTICESHIPS_` prefix.

The schema is created by `infrastructure/persistence/schema.py`, not by
Alembic. `init_db()` is idempotent and every public service calls it, so
no caller has to bootstrap.

Logins live in the platform's shared `auth.db`. An account only reaches
these screens once it holds a `user_systems` row for `apprenticeships`.
Grant one from **System → User Accounts** as a provider admin, or from
the command line:

```bash
python tools/college_and_apprenticeships/create_admin.py --list
python tools/college_and_apprenticeships/create_admin.py --user alice --role admin
python tools/college_and_apprenticeships/create_admin.py --demo   # dev only
```

Demo logins (`--demo`, weak passwords, dev machines only): `admin5`,
`tutor1`, `apprentice1`, `employer1`, `assessor1`.

Note that `RoleManager.grant_system_access` validates against the school
role hierarchy, which has no entry for apprentice, employer or
end-point assessor — so `services/account_service.py` writes
`user_systems` directly rather than going through it.

### Login ↔ learner record

An apprentice's login is linked to their platform learner record
(`users.journey_id`) automatically. The rules are the platform's
(`platform/cross_system/login_links.py`), and they apply to every system.
This system supplies two things:

- **The pairing:** `ApprenticeshipsAdapter.learner_ids_for_login` matches
  the apprentice record whose `username` is the login's, the same rule
  sign-in uses.
- **The hooks:** `services/login_links.py` calls the platform at the
  moments that pairing can change.

- **When it runs:**
  - an apprentice is created, or their username changes;
  - a login is granted the apprentice role, or linked to a record;
  - degree-apprenticeship access is granted;
  - at sign-in;
  - once at every launch (`sync_all`), which catches up older accounts.
- **What it will not do:**
  - link a login that doesn't hold the apprentice role;
  - link when two apprentice records with the same username belong to
    different learners (it removes an earlier automatic link instead);
  - overwrite or remove a link someone set by hand.
- **Audit:** every change is recorded in `security_audit_log` under the
  actor `apprenticeships:auto-link`.
- **Revoking access:** this leaves the link in place.

---

## Preferences

`services/preferences.py` holds three per-login settings, each chosen
because it has exactly one place it can take effect:

| Setting | Where it lands |
|---|---|
| Date format | `widgets._display` / `prompts.cell` — every cell in both interfaces |
| Rows per table | `widgets.DataTable` height; `prompts.table`'s row budget |
| Idle timeout | The desktop shell's inactivity sign-out |

They are cached in a module global that each entrypoint sets via
`preferences.activate(username)`, because the cell formatters run
thousands of times per screen and have no actor to hand.

---

## Testing

```bash
/home/seancatchpole989/venv/bin/pytest tests/unit/systems/apprenticeships -v --timeout=60
```

`test_services.py` concentrates on the two things most damaging to get
wrong: the role boundaries, and the rules that decide whether somebody
may finish. `test_interfaces.py` checks that every menu and navigation
entry resolves to a real callable, and covers the preference and export
services. Each test runs against a throwaway database — the `db` fixture
repoints `schema.DB_PATH` *and* resets its ready flag, because doing
only the first leaves the next `init_db()` short-circuiting on a stale
cache and the tests writing to the real file.

Creating an apprentice also writes to the platform's shared `auth.db`:
it registers the learner and links their login. The autouse
`platform_auth_db` fixture in the package conftest points that at a temp
file for every test. It repoints `auth.db.PLATFORM_AUTH_DB_FILE` and
resets the cross-system "schema ready" caches, for the same stale-cache
reason as above.

## See also

- [University integration](university_integration.md) — degree apprenticeships
- [`docs/reference/college_and_apprenticeships/`](../reference/college_and_apprenticeships/)
- [`docs/reference/DEFAULT_ACCOUNTS.md`](../reference/DEFAULT_ACCOUNTS.md)
