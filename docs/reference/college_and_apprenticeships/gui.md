# GUI

Apprenticeships only. FE College has its own GUI at `systems/fe_college/gui_main.py`.

```bash
python -m education_system --apprenticeships --gui
```

Launched by the unified launcher after the shared login.
`gui_main.run(user_info, role, shared_auth)` raises if handed an
unauthenticated session — there is no per-system login screen.

## Shape

```
interfaces/gui/
├── gui_main.py    # The shell: header, sidebar, content pane, NAV_BY_ROLE
├── session.py     # Login -> Actor, capability summary, dashboard payload
├── widgets.py     # The toolkit every window builds on
└── windows/
    ├── admin/               (11)   apprentice/  (7)
    ├── staff/               (7)    employer/    (6)
    ├── end_point_assessor/  (5)    system/      (3)
    └── shared/              (20)   opened by several roles: tasks, calendar,
                                     search, learning plan, actions, assignments,
                                     documents, signatures, complaints, …
```

A nav entry names its module relative to `windows/`, so a shared screen
is listed as `"education_system.platform.integrations.email"` under each role that opens it rather than
re-exported into each role's package.

One window, three regions: a header, a navigation sidebar and a content
pane every screen renders into. 1400x900, minimum 1200x800, `grid` for
the shell and `pack` inside it — the house convention, clamped to the
real screen by `window_sizing.fit`.

Each window module exposes exactly one entry point:

```python
def render(gui) -> None:
    frame = gui.clear()
    ...
```

`gui.show(module, label)` imports it and calls `render`. A screen that
fails to import or raises must not take the shell down with it: the user
keeps their session and the failure is drawn into the content pane.

`gui` gives a window `actor`, `root`, `clear()`, `refresh()` and
`status_var`.

## Navigation is per role

`NAV_BY_ROLE` gives each of the five roles its own tree. They are not
one menu with bits hidden — an employer and an end-point assessor want
genuinely different screens, and an assessor must not even see the
provider's formative judgements.

A shared **System** group is appended to every role
(`SYSTEM_CATEGORY`, plus `SYSTEM_CATEGORY_ADMIN` for administrators), so
a screen added there cannot be forgotten for one role. An unrecognised
role still gets it, which beats a blank window.

The menu is convenience, not security. Every screen re-checks permission
through the service layer.

The tree mirrors the CLI's `menus.MENUS` deliberately — same categories,
same order, same screens.

## widgets

Forty-five windows would otherwise be forty-five copies of the same
Treeview wiring. Nothing in the toolkit knows about the domain; windows
pass column specs, field specs and callables.

**Layout** — `heading`, `section`, `scrollable`, `button_bar`,
`open_window`.

`button_bar` inserts itself *ahead of* the first expanding sibling and
anchors to the bottom. List screens build heading → filters → table →
actions, and `pack` fills in that order, so on a short window the bar
packed last is allocated nothing and the user sees a screen with no way
to act on it. Letting the table absorb the shortfall costs it visible
rows it already has a scrollbar for; losing rows you can scroll back is
recoverable, losing the New button is not.

**Read-outs** — `kpi_row`, `progress_row`, `field_grid`, `empty_state`,
`money`, `percent`.

**DataTable** — a Treeview with the wiring every list screen needs.
Columns are `(key, heading, width[, anchor])`. `populate` takes rows, a
value function and an `identity` function, so selection returns a domain
id rather than a widget handle: `selected_int()`,
`require_selection_int(action)`, `selected_many()`.

Rows are tagged by status or RAG and coloured from `config.STATUS_COLOURS`
/ `config.RAG_COLOURS`, so red means the same thing on every screen.

`height` left unset takes the user's rows-per-table preference, which is
what a screen's main list wants. A fixed value is for a pane *inside* a
screen, where the surrounding content has already decided how much room
there is to give it.

**FilterBar** — `(key, label, kind[, options])` where kind is `combo`,
`entry` or `check`. `values()` returns the current state as a dict ready
to splat into a service call, with `"All"` and blanks dropped — a filter
the user has not set is simply not applied, which keeps the service
signatures honest.

**FormDialog** — a modal built from a field spec (`key`, `label`,
`kind`, `options`, `value`, `required`, `help`). `on_save` receives the
collected dict; raising from it keeps the dialog open and shows the
message inline, so the user does not lose what they typed. That is the
whole reason saving goes through a callback rather than the caller
reading values back afterwards.

**Errors** — `guard(action)` returns `(ok, result)`, turning a refusal
into a message box:

| Raised | Shown |
|---|---|
| `PermissionDenied` | Warning, verbatim |
| `ValidationError` | Error, verbatim |
| anything else | "Unexpected error", traceback logged |

Also `confirm`, `ask_reason`, `inform`, `warn`.

**Formatting** — `_display` is the single point every cell passes
through, which is why the date-format preference is applied there. An
em dash stands in for anything missing.

## Screen patterns

Three shapes recur:

- **List** — heading, `FilterBar`, `DataTable`, `button_bar`. A local
  `reload()` closure re-reads through the service; nothing caches.
- **Master–detail** — the list's `on_activate` and an Open button both
  call a `_detail(gui, id)` that redraws the whole pane, ending in a
  "← Back" button. Actions inside a detail pane call `_detail` again
  rather than `gui.refresh()`, which would drop the user out to the list
  mid-task.
- **Tabbed** — a `ttk.Notebook` where one screen answers several
  questions about the same thing (compliance, gateway checks, EPA
  results).

## Idle timeout

The shell signs the session out after the user's configured idle period
— keys, clicks and the wheel count as activity, pointer motion does not.
A provider workstation with an employer's whole cohort on screen should
not stay open all afternoon. Set it, or switch it off, under **System →
Settings**.

## Tests

Windows are checked for importability and for exposing `render`;
actually drawing one needs a display and belongs behind the `gui`
marker, which a headless run deselects.
