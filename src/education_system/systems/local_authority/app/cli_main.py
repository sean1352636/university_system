"""Text menu for the Local Authority Education System.

Built from the same catalogue as the GUI (:mod:`app.routing`), so every
sidebar entry is a numbered menu item here too. Record-type entries get
List / Add / Edit / Delete / Search / Export; the rest have their own
``do_<key>`` handler below.

Launched only by the unified launcher after the shared login
(``python -m education_system --localauthority --cli``).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable

from education_system.platform.delivery.cli.cli_helpers import idle_session
from education_system.systems.local_authority import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.local_authority.app import routing as menu
from education_system.systems.local_authority.core import access, dates
from education_system.systems.local_authority.core import records as r

logger = logging.getLogger(__name__)


def _ask(prompt: str, default: str = "") -> str:
    try:
        text = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        return default
    return text or default


def _pause() -> None:
    _ask("\nPress Enter to continue")


def _table(headers: list[str], rows: list[list[str]], limit: int = 60) -> None:
    rows = [[str(c) for c in row] for row in rows]
    widths = [min(max([len(h)] + [len(row[i]) for row in rows]), 40)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for row in rows[:limit]:
        print("  ".join(c[:w].ljust(w) for c, w in zip(row, widths)))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more (use Search)")
    if not rows:
        print("(none)")


class LACLI:
    def __init__(self, auth, principal: access.Principal) -> None:
        menu.load_areas()
        self.auth = auth
        self.principal = principal

    def logout(self) -> None:
        from education_system import switch as _switch
        try:
            self.auth.logout()
        except Exception:
            logger.exception("Logout failed")
        _switch.request_logout("cli")

    # ── main loop ────────────────────────────────────────────────────
    def run(self) -> int:
        from education_system import switch as _switch
        from education_system.launcher.roles import is_superadmin
        from education_system.launcher.system_switch import pick_system_cli
        user = getattr(self.auth, "current_user", None) or {}
        show_system_switch = is_superadmin(user)
        categories = [(c, [e for e in items if self.principal.can_open(e[0])])
                      for c, items in menu.CATEGORIES]
        categories = [(c, items) for c, items in categories if items]
        while True:
            print(f"\n=== {SYSTEM_NAME} ===")
            print(f"Signed in: {self.principal.username or '?'} "
                  f"({self.principal.role or 'no role'})")
            self._summary()
            for i, (cat, _items) in enumerate(categories, start=1):
                print(f"  {i:2d}) {cat}")
            print("   G) Switch to GUI")
            if show_system_switch:
                print("   S) Switch System")
            print("   L) Logout (return to login)")
            print("   Q) Shut down")
            choice = _ask("Select").lower()
            if choice == "g":
                _switch.request_switch(SYSTEM_KEY, "gui")
                return 0
            if choice == "s" and show_system_switch:
                target = pick_system_cli(user, SYSTEM_KEY)
                if target:
                    _switch.request_switch(target, "cli")
                    return 0
                continue
            if choice == "l":
                self.logout()
                return 0
            if choice == "q":
                if _ask(f"Shut down the {SYSTEM_NAME}? (y/N)").lower() != "y":
                    continue
                try:
                    self.auth.logout()
                except Exception:
                    logger.exception("Logout failed")
                _switch.request_exit()
                return 0
            if choice.isdigit() and 1 <= int(choice) <= len(categories):
                self._category(*categories[int(choice) - 1])
            else:
                print("Invalid selection.")

    def _summary(self) -> None:
        from education_system.systems.local_authority.modules import reports
        try:
            d = reports.dashboard()
        except Exception:  # noqa: BLE001 - the menu must still open
            logger.exception("Dashboard figures failed")
            return
        print(f"  Children {d['children']} ({d['not_in_education']} of school age not in "
              f"education, {d['cme_open']} CME, {d['ehe']} EHE) · applications awaiting "
              f"{d['applications_open']} · attendance cases {d['attendance_cases']} · EHC plans "
              f"{d['ehc_plans']} ({d['ehc_open']} assessments open) · due in 30 days "
              f"{len(d['due'])} ({d['overdue']} overdue)\n")

    def _category(self, label: str, items: list[tuple[str, str]]) -> None:
        while True:
            print(f"\n--- {label} ---")
            for i, (lbl, _key) in enumerate(items, start=1):
                print(f"  {i}. {lbl}")
            print("  0. Back")
            choice = _ask("Choose")
            if choice in ("0", "b", ""):
                return
            if choice.isdigit() and 1 <= int(choice) <= len(items):
                lbl, key = items[int(choice) - 1]
                self.open(key, lbl)

    def open(self, key: str, label: str) -> None:
        handler: Callable[[], None] | None = getattr(self, f"do_{key}", None)
        if handler is not None:
            handler()
        elif key in r.REGISTRY:
            self.records(r.REGISTRY[key])
        else:
            print(f"{label} hasn't been built yet.")
            _pause()

    # ── generic record menu ──────────────────────────────────────────
    def records(self, rt: r.RecordType, learner_id: int | None = None) -> None:
        search = ""
        while True:
            rows = r.list_records(rt, learner_id=learner_id, search=search)
            print(f"\n--- {rt.title}{f' (search: {search})' if search else ''} ---")
            self._print_rows(rt, rows, show_learner=learner_id is None)
            can_delete = self.principal.can_delete(rt.key)
            print("\n  a. Add   e. Edit   " + ("d. Delete   " if can_delete else "")
                  + "s. Search   x. Export CSV   0. Back")
            choice = _ask("Choose").lower()
            if choice in ("0", "b", ""):
                return
            if choice == "a":
                fixed = ({rt.learner_field.name: learner_id}
                         if learner_id and rt.learner_field else {})
                self._form(rt, None, fixed)
            elif choice == "e":
                row = self._pick(rt, rows)
                if row:
                    self._form(rt, row, {})
            elif choice == "d" and can_delete:
                row = self._pick(rt, rows)
                if row and _ask(f"Delete {rt.label_for(row)}? (y/n)").lower() == "y":
                    try:
                        r.delete(rt, row["id"], actor=self.principal.username)
                        print("Deleted.")
                    except r.ValidationError as exc:
                        print(f"Not deleted: {exc}")
            elif choice == "s":
                search = _ask("Search text (blank clears)")
            elif choice == "x":
                from education_system.systems.local_authority.modules import reports
                path = _ask("Save CSV to", f"{rt.key}_{date.today().isoformat()}.csv")
                print(f"Exported {reports.export_csv(rt, path, rows)} row(s) to {path}")

    def _print_rows(self, rt: r.RecordType, rows: list[dict], show_learner: bool = True) -> None:
        listed = [f for f in rt.fields if f.listed and f.kind not in ("learner", "ref", "long")]
        headers = ["ID"] + (["Child"] if show_learner and rt.learner_field else [])
        headers += [f.label for f in listed] + [label for label, _ in rt.computed]
        out = []
        for row in rows:
            line = [row["id"]] + ([row.get("learner_name") or ""]
                                  if show_learner and rt.learner_field else [])
            line += [r.fmt(f, row.get(f.name)) for f in listed]
            out.append(line + [fn(row) for _, fn in rt.computed])
        _table(headers, out)

    @staticmethod
    def _pick(rt: r.RecordType, rows: list[dict]) -> dict | None:
        text = _ask(f"{rt.singular.capitalize()} ID")
        if not text.isdigit():
            return None
        row = next((x for x in rows if x["id"] == int(text)), None) or r.get(rt, int(text))
        if row is None:
            print("No such record.")
        return row

    def _form(self, rt: r.RecordType, row: dict | None, fixed: dict) -> int | None:
        print(f"\n{'Edit' if row else 'New'} {rt.singular} (Enter keeps the value shown; "
              "'-' clears it)")
        values: dict = dict(fixed)
        for f in rt.fields:
            if not f.form or f.name in fixed:
                continue
            current = row.get(f.name) if row else f.initial()
            values[f.name] = self._ask_field(f, current, row, values)
        try:
            new_id = r.save(rt, values, record_id=(row or {}).get("id"),
                            actor=self.principal.username)
        except r.ValidationError as exc:
            print(f"Not saved: {exc}")
            return None
        print(f"Saved ({rt.singular} #{new_id}).")
        for line in r.take_notices():   # what the save did on the platform
            print(f"  {line}")
        return new_id

    def _ask_field(self, f: r.Field, current, row: dict | None, values: dict):
        star = " *" if f.required else ""
        if f.kind in ("choice", "learner", "ref"):
            if f.kind == "choice":
                pairs = [(c, c) for c in f.choices]
            elif f.kind == "learner":
                if row is not None:   # a record's child doesn't change
                    return current
                from education_system.systems.local_authority.modules import children as learners
                pairs = learners.learner_options()
            else:
                target = r.REGISTRY[f.ref]  # type: ignore[index]
                lid = values.get("learner_id") or (row or {}).get("learner_id")
                pairs = r.options(target, learner_id=lid if target.learner_field else None)
            print(f"{f.label}{star}:")
            for i, (_v, label) in enumerate(pairs, start=1):
                print(f"   {i}. {label}")
            shown = next((str(i) for i, (v, _l) in enumerate(pairs, 1) if v == current), "")
            text = _ask("   number", shown)
            if text == "-":
                return None
            if text.isdigit() and 1 <= int(text) <= len(pairs):
                return pairs[int(text) - 1][0]
            return current
        shown = r.fmt(f, current) if f.kind == "date" else ("" if current is None else str(current))
        if f.kind == "bool":
            shown = "y" if current else "n"
        hint = " (DD/MM/YYYY)" if f.kind == "date" else " (y/n)" if f.kind == "bool" else ""
        text = _ask(f"{f.label}{star}{hint}", shown)
        if text == "-":
            return None
        if f.kind == "bool":
            return 1 if text.lower().startswith("y") else 0
        return text

    # ── custom entries ───────────────────────────────────────────────
    def _choose_learner(self) -> int | None:
        from education_system.systems.local_authority.modules import children as learners
        text = _ask("Child name or ID")
        if text.isdigit():
            return int(text)
        rows = r.list_records(learners.LEARNERS, search=text)
        if not rows:
            print("No child matches.")
            return None
        for row in rows[:20]:
            print(f"  {row['id']:>4}  {learners.child_label(row)} · {row['status']}")
        pick = _ask("ID")
        return int(pick) if pick.isdigit() else None

    def do_add_learner(self) -> None:
        from education_system.systems.local_authority.modules import children
        new_id = self._form(children.CHILDREN, None, {})
        if new_id:
            self.profile(new_id)

    def do_learner_profile(self) -> None:
        lid = self._choose_learner()
        if lid:
            self.profile(lid)

    def profile(self, learner_id: int) -> None:
        from education_system.systems.local_authority.modules import children, schools
        while True:
            row = r.get(children.CHILDREN, learner_id)
            if row is None:
                print("No such child.")
                return
            year = children.year_group(r.to_date(row["dob"]))
            print(f"\n=== {row['first_name']} {row['last_name']} ({row['child_ref']}) · {year} · "
                  f"{row['status']} ===")
            print(f"  Education: {row['education']}"
                  + (f" - {schools.school_name(row['school_id'])}" if row.get("school_id")
                     else "") + f" · SEN: {row['sen_status']}")
            for i, (label, _key) in enumerate(menu.PROFILE_TABS, start=1):
                print(f"  {i}. {label}")
            n = len(menu.PROFILE_TABS)
            print(f"  {n + 1}. Chronology\n  {n + 2}. Edit details\n  0. Back")
            choice = _ask("Choose")
            if choice in ("0", "b", ""):
                return
            if not choice.isdigit():
                continue
            c = int(choice)
            if 1 <= c <= n:
                self.records(r.REGISTRY[menu.PROFILE_TABS[c - 1][1]], learner_id=learner_id)
            elif c == n + 1:
                for h in r.history(learner_id=learner_id, limit=40):
                    print(f"  {h['at']}  {h['actor']:<12} {h['summary']}")
                _pause()
            elif c == n + 2:
                self._form(children.CHILDREN, row, {})

    def do_chronology(self) -> None:
        from education_system.systems.local_authority.modules import children
        names = dict(children.learner_options(include_archived=True))
        for h in r.history(limit=60):
            print(f"  {h['at']}  {h['actor']:<12} {names.get(h.get('learner_id'), ''):<28} "
                  f"{h['summary']}")
        _pause()

    # ── reports ──────────────────────────────────────────────────────
    def do_due_report(self) -> None:
        from education_system.systems.local_authority.modules import reports
        items = reports.due_items(60)
        _table(["Due", "", "What", "Child"],
               [[dates.uk(i.due), "OVERDUE" if i.overdue else "", i.what, i.learner]
                for i in items], limit=200)
        _pause()

    def do_school_notifications(self) -> None:
        from education_system.systems.local_authority.modules import reports
        items = reports.school_notifications()
        _table(["Date", "What", "Child", "School", "Status"],
               [[i.on, i.what, i.learner, i.school, i.status] for i in items], limit=200)
        _pause()

    @staticmethod
    def _print_counts(groups: dict) -> None:
        for title, counts in groups.items():
            print(f"\n{title}:")
            for name, n in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"  {name:<50} {n:g}" if isinstance(n, float) else f"  {name:<50} {n}")
            if not counts:
                print("  (none)")

    def do_admissions_report(self) -> None:
        from education_system.systems.local_authority.modules import reports
        rate = reports.first_preference_rate()
        print(f"\nNormal-round offers of a first preference: "
              f"{'—' if rate is None else f'{rate}%'}")
        self._print_counts(reports.admissions_summary())
        _pause()

    def do_places_report(self) -> None:
        from education_system.systems.local_authority.modules import reports
        _table(["School", "Phase", "PAN", "1st prefs", "Offers", "Capacity", "On roll",
                "Surplus", ""],
               [[x["school"], x["phase"], "" if x["pan"] is None else x["pan"],
                 x["first_prefs"], x["offers"], x["capacity"] or "", x["on_roll"] or "",
                 x["surplus"], "OVERSUBSCRIBED" if x["over"] else ""]
                for x in reports.school_places()])
        _pause()

    def do_welfare_report(self) -> None:
        from education_system.systems.local_authority.modules import reports
        self._print_counts(reports.welfare_summary())
        _pause()

    def do_exclusions_report(self) -> None:
        from education_system.systems.local_authority.modules import reports
        self._print_counts(reports.exclusions_summary())
        _pause()

    def do_send_report(self) -> None:
        from education_system.systems.local_authority.modules import reports
        t = reports.send_timeliness()
        print(f"\nFinal EHC plans within 20 weeks: {t['on_time']} of {t['issued']}"
              + (f" ({t['rate']}%)" if t["rate"] is not None else "")
              + f" · high-needs top-ups £{reports.high_needs_cost():,.0f} a year")
        self._print_counts(reports.send_summary())
        _pause()

    def do_transport_report(self) -> None:
        from education_system.systems.local_authority.modules import transport
        rows = transport.route_costs()
        _table(["Route", "Operator", "Vehicle", "Children", "Per day", "Per year", "Per child"],
               [[x["route"], x["operator"], x["vehicle"], x["children"], f"£{x['daily']:,.2f}",
                 f"£{x['annual']:,.0f}", "—" if x["per_child"] is None
                 else f"£{x['per_child']:,.0f}"] for x in rows])
        if rows:
            print(f"Total £{sum(x['annual'] for x in rows):,.0f} a year")
        _pause()

    def do_about(self) -> None:
        from education_system.systems.local_authority.infrastructure import database
        print(f"\n{SYSTEM_NAME}\n  Database: {database.db_path()}\n"
              f"  User: {self.principal.username} ({self.principal.role})\n"
              f"  {len(r.REGISTRY)} record types in {len(menu.CATEGORIES)} menu groups")
        _pause()


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Run the menu for a session the unified login already signed in."""
    access.require_shared_session(shared_auth, "cli")
    principal = access.from_auth(shared_auth, role)
    if not principal.is_staff:
        print(f"\n  {access.refusal(principal)}\n")
        logger.warning("Refusing Local Authority Education CLI for user=%s role=%s",
                       principal.username, principal.role)
        return 0
    cli = LACLI(shared_auth, principal)
    try:
        with idle_session(cli.logout):
            return cli.run()
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    print("Launch via: python -m education_system --localauthority --cli")
    raise SystemExit(2)
