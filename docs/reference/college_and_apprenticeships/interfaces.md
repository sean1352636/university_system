# Interfaces

Apprenticeships only — `fe_college` has no interfaces.

Two interface trees live under
`education_system/systems/apprenticeships/interfaces/`, both built.

| Tree | State |
|---|---|
| `cli/` | Built — 35 command modules, five role menus |
| `gui/` | Built — 59 window modules: five role packages, `system/`, and 20 `shared/` screens |

The HTTP routes live outside the package, in
`src/education_system/api/apprenticeships/`, and answer 501 until each
is backed by a service. There is no web portal.

See [`cli.md`](cli.md) and [`gui.md`](gui.md) for each in detail, and
[`api.md`](api.md) for what the API would take.

## One menu tree, two renderings

`interfaces/cli/menus.MENUS` and `interfaces/gui/gui_main.NAV_BY_ROLE`
are deliberately the same shape: the same categories, in the same order,
holding the same screens. An apprentice being talked through a task over
the phone should find the same options in the same groups whichever
interface they are in.

Both append a shared **System** group (`SYSTEM_CATEGORY`, plus
`SYSTEM_CATEGORY_ADMIN` for administrators) rather than repeating it per
role, so a screen added there cannot be forgotten for one role. Both
fall back to that group alone for an unrecognised role, which lands the
user somewhere they can read who they are signed in as and why the rest
is empty.

The menu is convenience, not security. Every screen re-checks permission
through the service layer regardless of what the navigation offered.

## No per-system login

Both entrypoints take an already-authenticated session:

```python
run(user_info=None, role=None, shared_auth=None) -> int
```

An unauthenticated call raises rather than prompting — it is a bug in
the caller, not an invitation to ask for a password. The launcher
authenticates against the shared platform account, then hands over.

Both call `services.access.resolve(...)` to build the `Actor`, and
`services.preferences.activate(username)` to load the interface
preferences once. Preferences are cached in a module global because the
cell formatters read them thousands of times a screen and have no actor
to hand.

## Handing control back

Neither interface calls `sys.exit`. Switching interface, switching
system and logging out are *requests* the launcher's dispatcher
consumes:

```python
switch.request_switch("apprenticeships", "cli")   # or "gui"
switch.request_logout("gui")
switch.request_exit()
```

## One toolkit each, not one per module

At sixty windows and thirty-five command modules, copying the Treeview
wiring, the modal scaffolding and the "catch ValidationError, show a
messagebox" dance into every file would be the dominant cost. So:

- `interfaces/gui/widgets.py` — windows, tables, filter bars, form
  dialogs, `guard()`, formatting
- `interfaces/cli/prompts.py` — input, tables, menus, `run_action()`

Neither knows anything about the domain. Screens pass column specs,
field specs and callables.

Two conventions the command modules rely on: typing `cancel` at any
prompt raises `prompts.Abort` and aborts the whole flow, and end-of-file
does the same — so the CLI degrades sensibly when stdin is a pipe rather
than a person.

## Failures

| Where | What the user sees |
|---|---|
| `PermissionDenied` | The refusal, verbatim — it is their business |
| `ValidationError` | The message, verbatim — it is correctable |
| Anything else | "Unexpected error", with a logged traceback |

Handled in exactly two places — `widgets.guard()` and
`prompts.run_action()` — so no screen has to get it right individually.
A crash in one command returns to the menu rather than dropping the user
out of the session, and a screen that fails to render leaves the shell
standing.

## Preferences

`services/preferences.py` holds three per-login settings, each chosen
because it has exactly one place it can take effect: date format
(`widgets._display` / `prompts.cell`), rows per table
(`widgets.DataTable` height, `prompts.table`'s row budget) and the
desktop idle timeout. A setting a screen would quietly ignore is worse
than no setting, so nothing else is offered.

## No placeholders

`tests/unit/systems/apprenticeships/test_layout.py` fails on a
docstring-only module or a star re-export anywhere in the package. The
`interfaces/portals/` tree that used to hold 38 empty modules was
removed in September 2026; a portal is new work with its own design
decisions, and gets written up here before it is stubbed.
