"""CLI for the retention schedule: categories, the DRY-RUN report and
(only when switched on, opted in and confirmed twice by an admin) a
purge. Purges ship disabled; safeguarding records are never touched.
Reached from the GDPR menu (see ``gdpr_cli._MENU``)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.governance.gdpr import (
    retention as ret,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


@ui.handler
def schedule() -> None:
    rows = ret.list_categories()
    print(f"\n  Purge switch: {'ON' if ret.purge_enabled() else 'OFF'}")
    ui.table(("Category", "Months", "Trigger", "Action", "Opted in",
              "Tables"),
             [(c.category, c.retention_months, c.trigger, c.action,
               "YES" if c.enabled else "no", ", ".join(c.tables)[:40])
              for c in rows], empty="(no categories — load the suggested "
                                    "schedule or add one)")


@ui.handler
def load_suggested() -> None:
    print("  Loads a suggested schedule (all categories disabled). Review "
          "the periods\n  against your own retention policy before relying "
          "on them.")
    if ui.yes_no("Load it?", default=False):
        made = ret.load_suggested_schedule(by=_who())
        print(f"\n  ✓ {len(made)} categor{'y' if len(made) == 1 else 'ies'} "
              "added (disabled).")


@ui.handler
def edit_category() -> None:
    name = ui.ask("Category name", required=True)
    cur = ret.get_category(name)
    trigger = ui.pick("Trigger", list(ret.TRIGGERS),
                      default=cur.trigger if cur else ret.TRIGGER_LEAVING)
    c = ret.save_category({
        "category": name,
        "description": ui.ask("Description",
                              default=(cur.description or "") if cur else ""),
        "tables": ui.ask("Tables (comma separated)",
                         default=", ".join(cur.tables) if cur else "",
                         required=True),
        "retention_months": ui.ask_int("Keep for (months)",
                                       default=cur.retention_months
                                       if cur else None),
        "trigger": trigger,
        "date_column": ui.ask("Date column", default=(cur.date_column or "")
                              if cur else "", required=True)
        if trigger == ret.TRIGGER_RECORD else None,
        "action": ui.pick("Action", list(ret.ACTIONS),
                          default=cur.action if cur else ret.ACTION_ANONYMISE),
        "notes": ui.ask("Notes", default=(cur.notes or "") if cur else ""),
    }, by=_who())
    print(f"\n  ✓ Saved {c.category} "
          f"({'opted in' if c.enabled else 'disabled'}).")


@ui.handler
def delete_category() -> None:
    name = ui.ask("Category name", required=True)
    if ui.yes_no(f"Delete category {name!r}?") and ret.delete_category(name):
        print("\n  ✓ Deleted.")


@ui.handler
def dry_run() -> None:
    print()
    print(ret.dry_run_text(ret.dry_run()))


@ui.handler
def purge_switch() -> None:
    now = ret.purge_enabled()
    print(f"\n  Purge switch is {'ON' if now else 'OFF'} (admin only).")
    if ui.yes_no(f"Turn it {'OFF' if now else 'ON'}?", default=False):
        ret.set_purge_enabled(not now)
        print(f"\n  ✓ Purge switch {'OFF' if now else 'ON'}.")


@ui.handler
def opt_in() -> None:
    name = ui.ask("Category name", required=True)
    cat = ret.get_category(name)
    if cat is None:
        raise ret.ValidationError(f"No category {name!r}")
    on = not cat.enabled
    if ui.yes_no(f"{'Opt in' if on else 'Opt out'} {name!r}?",
                 default=False):
        ret.set_category_enabled(name, on)
        print(f"\n  ✓ {name} {'opted in' if on else 'disabled'}.")


@ui.handler
def apply() -> None:
    name = ui.ask("Category to purge", required=True)
    findings = ret.dry_run([name])
    if not findings:
        raise ret.ValidationError(f"No category {name!r}")
    print()
    print(ret.dry_run_text(findings))
    f = findings[0]
    if f.rows == 0:
        print("\n  Nothing to do.")
        return
    print(f"\n  This will {f.category.action.upper()} {f.rows} row(s). The "
          "database is backed up first.")
    if not ui.yes_no("First confirmation: go ahead?", default=False):
        return
    typed = ui.ask("Second confirmation: type the category name exactly",
                   required=True)
    out = ret.apply_category(name, confirm=typed, actor=_who())
    print(f"\n  ✓ {out['rows']} row(s) for {out['learners']} learner(s). "
          f"Backup: {out['backup']}")


@ui.handler
def log() -> None:
    rows = ret.run_log()
    ui.table(("When", "Category", "Action", "Learners", "Rows", "By",
              "Backup"),
             [(r["run_at"], r["category"],
               r["action"], r["learners"], r["rows_affected"], r["run_by"],
               r["backup_path"]) for r in rows], empty="(no purges run)")


MENU = [
    ("Retention Schedule", schedule),
    ("Load Suggested Schedule (disabled)", load_suggested),
    ("Add / Edit Retention Category", edit_category),
    ("Delete Retention Category", delete_category),
    ("Retention DRY RUN", dry_run),
    ("Retention Purge Switch (admin)", purge_switch),
    ("Opt a Category In / Out (admin)", opt_in),
    ("Run Retention Purge (admin, confirmed twice)", apply),
    ("Retention Run Log", log),
]
