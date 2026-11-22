"""Text menu for the Alternative Provision System.

Built from the same catalogue as the GUI (:mod:`app.routing`), so every
sidebar entry is a numbered menu item here too. Record-type entries get
List / Add / Edit / Delete / Search / Export; the rest have their own
``do_<key>`` handler below.

Launched only by the unified launcher after the shared login
(``python -m education_system --alternativeprovision --cli``).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable

from education_system.platform.delivery.cli.cli_helpers import idle_session
from education_system.systems.alternative_provision import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.alternative_provision.app import routing as menu
from education_system.systems.alternative_provision.core import access, dates
from education_system.systems.alternative_provision.core import records as r

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


class APCLI:
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
        from education_system.systems.alternative_provision.modules import reports
        try:
            d = reports.dashboard()
        except Exception:  # noqa: BLE001 - the menu must still open
            logger.exception("Dashboard figures failed")
            return
        att = "—" if d["attendance"] is None else f"{d['attendance']:g}%"
        print(f"  On roll {d['on_roll']} · open referrals {d['referrals_open']}"
              + (f" ({d['day6_overdue']} past sixth day)" if d["day6_overdue"] else "")
              + f" · placements {d['placements']} ({d['part_time']} part-time) · attendance "
              f"{att} · open concerns {d['concerns_open']} · due in 30 days {len(d['due'])} "
              f"({d['overdue']} overdue)\n")

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
                from education_system.systems.alternative_provision.modules import reports
                path = _ask("Save CSV to", f"{rt.key}_{date.today().isoformat()}.csv")
                print(f"Exported {reports.export_csv(rt, path, rows)} row(s) to {path}")

    def _print_rows(self, rt: r.RecordType, rows: list[dict], show_learner: bool = True) -> None:
        listed = [f for f in rt.fields if f.listed and f.kind not in ("learner", "ref", "long")]
        headers = ["ID"] + (["Pupil"] if show_learner and rt.learner_field else [])
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
                if row is not None:   # a record's pupil doesn't change
                    return current
                from education_system.systems.alternative_provision.modules import learners
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
        from education_system.systems.alternative_provision.modules import learners
        text = _ask("Pupil name or ID")
        if text.isdigit():
            return int(text)
        rows = r.list_records(learners.LEARNERS, search=text)
        if not rows:
            print("No pupil matches.")
            return None
        for row in rows[:20]:
            print(f"  {row['id']:>4}  {learners.pupil_label(row)} · {row['status']}")
        pick = _ask("ID")
        return int(pick) if pick.isdigit() else None

    def do_add_learner(self) -> None:
        from education_system.systems.alternative_provision.modules import learners
        self._form(learners.LEARNERS, None, {})

    def do_learner_profile(self) -> None:
        from education_system.systems.alternative_provision.modules import (
            attendance,
            learners,
            placements,
        )
        lid = self._choose_learner()
        row = r.get(learners.LEARNERS, lid) if lid else None
        if row is None:
            return
        while True:
            dob = r.to_date(row.get("dob"))
            print(f"\n=== {row['first_name']} {row['last_name']} ===")
            print(f"  {row['pupil_ref']} · {row['year_group']} · {row['status']} · "
                  f"{row['sen_status']}{' · looked after' if row.get('looked_after') else ''}")
            live = placements.active_placements(lid)
            rate = attendance.rate(lid)
            print(f"  Born {dates.uk(dob)} · home school {row.get('home_school') or '—'} · "
                  f"{len(live)} active placement(s) · attendance "
                  f"{'—' if rate is None else f'{rate:g}%'}")
            for i, (label, key) in enumerate(menu.PROFILE_TABS, start=1):
                n = len(r.list_records(r.REGISTRY[key], learner_id=lid))
                print(f"  {i:>2}. {label} ({n})")
            print(f"  {len(menu.PROFILE_TABS) + 1:>2}. Chronology\n   e. Edit details   0. Back")
            choice = _ask("Choose").lower()
            if choice in ("0", ""):
                return
            if choice == "e":
                self._form(learners.LEARNERS, row, {})
                row = r.get(learners.LEARNERS, lid) or row
            elif choice.isdigit() and 1 <= int(choice) <= len(menu.PROFILE_TABS):
                self.records(r.REGISTRY[menu.PROFILE_TABS[int(choice) - 1][1]], learner_id=lid)
            elif choice == str(len(menu.PROFILE_TABS) + 1):
                self._history(lid)

    def _history(self, learner_id: int | None) -> None:
        rows = r.history(learner_id=learner_id, limit=100)
        _table(["When", "Who", "What"], [[x["at"], x["actor"], x["summary"]] for x in rows])
        _pause()

    def do_chronology(self) -> None:
        text = _ask("Pupil name or ID (blank = everyone)")
        if not text:
            self._history(None)
            return
        from education_system.systems.alternative_provision.modules import learners
        if text.isdigit():
            self._history(int(text))
            return
        rows = r.list_records(learners.LEARNERS, search=text)
        if len(rows) == 1:
            self._history(rows[0]["id"])
        else:
            for row in rows[:20]:
                print(f"  {row['id']:>4}  {learners.pupil_label(row)}")
            pick = _ask("ID")
            if pick.isdigit():
                self._history(int(pick))

    def do_take_register(self) -> None:
        from education_system.systems.alternative_provision.modules import attendance
        try:
            on = date.fromisoformat(r.parse_date(_ask("Date (DD/MM/YYYY)",
                                                      dates.uk(date.today()))) or "")
        except (ValueError, r.ValidationError) as exc:
            print(f"Not a date: {exc}")
            return
        session = _ask("Session (AM/PM)", "AM" if datetime.now().hour < 12 else "PM").upper()
        if session not in attendance.SESSIONS:
            print("The session is AM or PM.")
            return
        rows = attendance.register(on, session)
        if not rows:
            print("Nobody was on roll on that day.")
            _pause()
            return
        codes = {attendance.short(m).lower(): m for m in attendance.MARKS}
        codes["/"] = attendance.MARKS[0]
        print("\nMarks: " + "  ".join(f"{attendance.short(m)} = {m.rsplit(' (', 1)[0]}"
                                      for m in attendance.MARKS))
        print("Enter keeps the mark shown (or Present if none).")
        marks: dict[int, tuple[str, str]] = {}
        for row in rows:
            shown = attendance.short(row["mark"]) if row["mark"] else "/"
            text = _ask(f"  {row['name']} ({row['pupil_ref']})", shown).lower()
            mark = codes.get(text, row["mark"] or attendance.MARKS[0])
            reason = row["reason"] or ""
            if mark in attendance.ABSENT:
                reason = _ask("    reason", reason)
            marks[row["learner_id"]] = (mark, reason)
        try:
            n = attendance.save_register(on, session, marks, actor=self.principal.username)
        except r.ValidationError as exc:
            print(f"Register not saved: {exc}")
        else:
            print(f"Register saved: {n} mark(s).")
        _pause()

    def do_due_report(self) -> None:
        from education_system.systems.alternative_provision.modules import reports
        items = reports.due_items(60)
        _table(["Due", "", "What", "Pupil"],
               [[dates.uk(i.due), "OVERDUE" if i.overdue else "", i.what, i.learner]
                for i in items], limit=200)
        _pause()

    @staticmethod
    def _counts(groups: dict) -> None:
        for title, counts in groups.items():
            print(f"\n{title}")
            for name, n in sorted(counts.items(), key=lambda x: -x[1]):
                shown = f"{n:g}" if isinstance(n, float) else str(n)
                print(f"  {name:<50} {shown}")
            if not counts:
                print("  (none)")

    def do_roll_report(self) -> None:
        from education_system.systems.alternative_provision.modules import reports
        self._counts(reports.roll_summary())
        _pause()

    def do_attendance_report(self) -> None:
        from education_system.systems.alternative_provision.modules import reports

        def pct(v):
            return "—" if v is None else f"{v:g}%"
        _table(["Pupil", "This school year", "Last 30 days", ""],
               [[x["learner"], pct(x["rate"]), pct(x["last_30"]),
                 "PERSISTENT ABSENCE" if x["persistent"] else ""]
                for x in reports.attendance_report()], limit=200)
        _pause()

    def do_behaviour_report(self) -> None:
        from education_system.systems.alternative_provision.modules import reports
        self._counts(reports.behaviour_summary())
        _pause()

    def do_costs_report(self) -> None:
        from education_system.systems.alternative_provision.modules import reports
        rows = reports.placement_costs()
        _table(["Pupil", "Provider", "Hours", "Commissioned by", "Cost / week"],
               [[x["learner"], x["provider"], f"{x['hours']:g}", x["commissioned_by"],
                 f"£{x['weekly']:,.2f}"] for x in rows], limit=200)
        if rows:
            print(f"\nTotal £{sum(x['weekly'] for x in rows):,.2f} a week")
        _pause()

    def do_outcomes_report(self) -> None:
        from education_system.systems.alternative_provision.modules import reports
        rate = reports.reintegration_rate()
        print("\nReintegration success rate: "
              + ("no reintegrations finished yet" if rate is None else f"{rate}%"))
        self._counts(reports.outcomes())
        _pause()

    def do_about(self) -> None:
        from education_system.systems.alternative_provision.infrastructure import database
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
        logger.warning("Refusing Alternative Provision CLI for user=%s role=%s",
                       principal.username, principal.role)
        return 0
    cli = APCLI(shared_auth, principal)
    try:
        with idle_session(cli.logout):
            return cli.run()
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    print("Launch via: python -m education_system --alternativeprovision --cli")
    raise SystemExit(2)
