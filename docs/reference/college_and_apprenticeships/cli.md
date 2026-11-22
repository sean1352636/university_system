# CLI

Apprenticeships only. FE College has its own CLI at `systems/fe_college/cli_main.py`.

```bash
python -m education_system --apprenticeships --cli
```

Launched by the unified launcher after the shared login. There is no
per-system login: `shell.run(user_info, role, shared_auth)` raises if
handed an unauthenticated session.

## Shape

```
interfaces/cli/
├── shell.py       # The loop: main menu, category menus, dispatch
├── menus.py       # role -> [(category, [(label, "module:function")])]
├── prompts.py     # Input, output, tables, menus, error handling
└── commands/      # 14 modules, one per area
```

`shell._dispatch` imports `commands.<module>` and calls
`<function>(actor)`. A lookup that fails is a wiring mistake rather than
anything the user can fix, so it is logged with a traceback and reported
as a single line.

`tests/unit/systems/apprenticeships/test_interfaces.py` parametrises over
every entry in `MENUS` and asserts the target resolves — otherwise a
typo stays invisible until somebody picks it.

## Commands

| Module | Exposes |
|---|---|
| `reports` | `dashboard`, `menu` |
| `admissions` | `menu` |
| `apprentices` | `menu`, `caseload`, `my_details` |
| `employers` | `menu` |
| `programmes` | `menu` |
| `training` | `menu`, `my_plan`, `plan_menu` |
| `off_the_job_hours` | `menu`, `approval_menu`, `my_menu` |
| `portfolios` | `menu`, `my_menu` |
| `reviews` | `menu`, `my_menu`, `feedback_menu` |
| `gateway` | `menu`, `my_gateway`, `epao_menu` |
| `end_point_assessment` | `menu`, `booking_menu`, `results_menu`, `resit_menu`, `my_menu` |
| `admin` | `staff_menu`, `funding_menu`, `compliance_menu` |
| `email` | `menu` |
| `system` | `about`, `change_password`, `mfa`, `settings`, `user_accounts` |

Several areas expose more than one entry point because the same service
serves genuinely different jobs: a programme manager reading the whole
off-the-job log, an approver clearing a queue, and an apprentice looking
at their own total want different screens over one table.

Menus are assembled per actor, so an option the role cannot use is not
offered rather than offered and refused:

```python
entries = [("List apprentices", partial(_list, actor))]
if actor.can("apprentice.manage"):
    entries.append(("Enrol an apprentice", partial(_create, actor)))
```

## prompts

**Input** — `ask`, `ask_int`, `ask_float`, `ask_yes_no`, `choose`
(numbered list of objects), `choose_value` (closed set of strings),
`pause`.

Typing `cancel` at any prompt raises `prompts.Abort` and aborts the
whole flow; end-of-file does the same, so a command degrades sensibly
when stdin is a pipe rather than a person.

**Output** — `title`, `note`, `ok`, `fail`, `rule`, `details`
(label/value block), `table`, `bar` (text progress bar), `money`,
`cell`.

`table` takes `(heading, width)` pairs; a negative width right-aligns
the column, which is what numbers want. Values longer than their column
are truncated rather than wrapped, because a table that keeps its shape
is easier to scan than one that preserves every character. Long tables
stop at the user's rows-per-table preference and say how many were held
back — scrolling a thousand rows off the top of a terminal loses them, a
footer that names the number does not.

`cell` is the single point every value passes through, which is why the
date-format preference is applied there.

**Menus** — `run_menu(heading, entries)` runs a numbered submenu loop.
Each handler runs inside `run_action`, so a crash in one command prints
and returns to the menu rather than dropping the user out of the CLI:

| Raised | Shown |
|---|---|
| `Abort` | "Cancelled." |
| `PermissionDenied` | The refusal, verbatim |
| `ValidationError` | The message, verbatim |
| anything else | "Unexpected error", traceback logged |

## Shared helpers

`commands/apprentices.py` is the home of the cohort helpers the other
modules borrow — `pick()`, `label()`, `names()` and `table()`. Evidence
rows and off-the-job entries carry an `apprentice_id` and no name, so a
queue screen needs the cohort to caption itself; keeping that lookup in
one place means one definition of "an apprentice this actor may see"
rather than eight.

Other cross-module reads follow the same pattern:
`off_the_job_hours.show_summary`, `portfolios.show_coverage`,
`gateway.show_record`, `admin.show_funding`, `admin.show_compliance`.

## The session menu

The main loop offers, beyond the role's categories:

```
G) Switch to GUI     S) Switch System (superadmins)
L) Logout            Q) Shut down
```

Each is a request handed back to the launcher via `switch`, not a
`sys.exit`.
