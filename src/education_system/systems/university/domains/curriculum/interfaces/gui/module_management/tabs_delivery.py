"""Module Management tabs: Team (teaching team, workload, external
examiners), Delivery (terms / sections and the weekly timetable) and
Feedback (student evaluation results). Rules are
``university/application/modules/delivery``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.modules import delivery
from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management import (  # noqa: E501
    data,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management._widgets import (  # noqa: E501
    _PAD, _clear, _code_of, _tree,
)
from education_system.systems.university.infrastructure.database.schemas.module_catalogue_schema import (  # noqa: E501
    STAFF_ROLES,
)


def _pick(choices, label):
    """The row in *choices* whose display text is *label*."""
    return next((c for text, c in choices if text == label), None)


class DeliveryTabs:
    """Mixin for ModuleManagementGUI."""

    # ── team ─────────────────────────────────────────────────────────

    def _build_team(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Team")
        self.leader_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.leader_var, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=8, pady=(4, 2))
        if self.can_assign:
            bar = ttk.Frame(tab)
            bar.pack(fill="x", **_PAD)
            self.member_combo = ttk.Combobox(bar, width=26, state="readonly")
            self.member_combo.pack(side="left")
            self.role_combo = ttk.Combobox(bar, values=STAFF_ROLES, width=10, state="readonly")
            self.role_combo.set("lecturer")
            self.role_combo.pack(side="left", padx=4)
            ttk.Label(bar, text="Hours").pack(side="left")
            self.hours_var = tk.StringVar(value="0")
            ttk.Entry(bar, textvariable=self.hours_var, width=5).pack(side="left", padx=2)
            ttk.Label(bar, text="Year").pack(side="left")
            self.team_year_var = tk.StringVar()
            ttk.Entry(bar, textvariable=self.team_year_var, width=8).pack(side="left", padx=2)
            ttk.Button(bar, text="Add", command=self.add_member).pack(side="left", padx=2)
            ttk.Button(bar, text="Remove", command=self.remove_member).pack(side="left")
        self.team_tree = _tree(tab, [("user", "Username"), ("name", "Name"), ("role", "Role"),
                                     ("hours", "Hours"), ("year", "Year")],
                               [100, 170, 90, 60, 80], height=5)
        self.team_tree.bind("<<TreeviewSelect>>", lambda _e: self.show_workload())
        self.workload_var = tk.StringVar(value="Select a team member to see their workload.")
        ttk.Label(tab, textvariable=self.workload_var, foreground="#555", justify="left",
                  wraplength=640).pack(anchor="w", padx=8)

        ttk.Label(tab, text="External examiners:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 0))
        if self.can_assign:
            ebar = ttk.Frame(tab)
            ebar.pack(fill="x", **_PAD)
            self.examiner_combo = ttk.Combobox(ebar, width=40, state="readonly")
            self.examiner_combo.pack(side="left")
            ttk.Label(ebar, text="Year").pack(side="left", padx=(6, 0))
            self.examiner_year_var = tk.StringVar()
            ttk.Entry(ebar, textvariable=self.examiner_year_var, width=8).pack(side="left", padx=2)
            ttk.Button(ebar, text="Assign", command=self.assign_examiner).pack(side="left", padx=2)
            ttk.Button(ebar, text="Unassign", command=self.unassign_examiner).pack(side="left")
        self.examiner_note_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.examiner_note_var, foreground="#666").pack(
            anchor="w", padx=8)
        self.examiner_tree = _tree(tab, [("name", "Examiner"), ("inst", "Institution"),
                                         ("year", "Year"), ("until", "Appointed until")],
                                   [180, 200, 80, 110], height=3)

    def refresh_team(self):
        _clear(self.team_tree)
        _clear(self.examiner_tree)
        if self.can_assign:
            if not self.member_combo["values"]:
                self._staff = [(f"{u['username']} - {u['name'] or u['role']}", u)
                               for u in data.call(delivery.staff_choices)]
                self.member_combo["values"] = [t for t, _ in self._staff]
            self._examiners = [(f"{e['name']} ({e['institution'] or 'no institution'})", e)
                               for e in data.call(delivery.examiner_choices)]
            self.examiner_combo["values"] = [t for t, _ in self._examiners]
            self.examiner_note_var.set(
                "" if self._examiners else "No active external examiners on record — add them "
                "in External Examiners first.")
        if not self.current_code:
            self.leader_var.set("")
            return
        leader = data.call(delivery.leader, self.current_code)
        self.leader_var.set(f"Module leader: {leader or 'none'}")
        for m in data.call(delivery.team, self.current_code):
            self.team_tree.insert("", "end", iid=str(m["id"]), values=(
                m["username"], m["name"] or "", m["role"], f"{m['hours'] or 0:g}",
                m["academic_year"] or "all years"))
        for e in data.call(delivery.module_examiners, self.current_code):
            self.examiner_tree.insert("", "end", iid=str(e["id"]), values=(
                e["name"], e["institution"] or "", e["academic_year"] or "all years",
                e["appointment_end"] or "open-ended"))

    # Older callers (and the instructor shortcut on Overview) use this name.
    refresh_staffing = refresh_team

    def show_workload(self):
        sel = self.team_tree.selection()
        if not sel:
            return
        username = self.team_tree.item(sel[0], "values")[0]
        load = data.call(delivery.workload, username)
        lines = ", ".join(f"{r['module_code']} {r['role']} {r['hours'] or 0:g} h"
                          for r in load["rows"][:12])
        self.workload_var.set(f"{username}: {load['total_hours']:g} hours across "
                              f"{len(load['rows'])} module role(s) — {lines}")

    def add_member(self):
        if not self._require_module():
            return
        username = _code_of(self.member_combo.get())
        if not username:
            self._info("Add to team", "Choose a member of staff first.")
            return
        made = self._do("Add to team", delivery.add_member, self.current_code, username,
                        self.role_combo.get(), self.hours_var.get(), self.team_year_var.get(),
                        self.username)
        if made:
            self._audit("add_module_staff", module_code=self.current_code, user=username,
                        role=self.role_combo.get())
            self.refresh_modules()
            self.refresh_team()

    def remove_member(self):
        sel = self.team_tree.selection()
        if not self._require_module() or not sel:
            return
        if self._ask("Remove from team", "Remove this person from the module team?"):
            self._do("Remove from team", delivery.remove_member, self.current_code,
                     int(sel[0]), self.username)
            self.refresh_modules()
            self.refresh_team()

    def assign_examiner(self):
        if not self._require_module():
            return
        examiner = _pick(self._examiners, self.examiner_combo.get())
        if not examiner:
            self._info("Assign external examiner", "Choose an examiner first.")
            return
        if self._do("Assign external examiner", delivery.assign_examiner, self.current_code,
                    examiner["examiner_id"], self.examiner_year_var.get(), self.username):
            self.refresh_team()

    def unassign_examiner(self):
        sel = self.examiner_tree.selection()
        if self._require_module() and sel:
            self._do("Unassign external examiner", delivery.unassign_examiner,
                     self.current_code, int(sel[0]), self.username)
            self.refresh_team()

    # ── delivery: terms / sections and timetable ─────────────────────

    def _build_delivery(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Delivery")
        ttk.Label(tab, foreground="#666", wraplength=640, justify="left", text=(
            "A module can run in several terms. Once it has an open delivery, students "
            "enrol on a delivery and its capacity and timetable fit are enforced.")).pack(
            anchor="w", padx=8)
        if self.can_manage:
            bar = ttk.Frame(tab)
            bar.pack(fill="x", **_PAD)
            self.term_combo = ttk.Combobox(bar, width=18, state="readonly")
            self.term_combo.pack(side="left")
            ttk.Label(bar, text="Places").pack(side="left", padx=(6, 0))
            self.places_var = tk.StringVar(value="30")
            ttk.Entry(bar, textvariable=self.places_var, width=5).pack(side="left", padx=2)
            self.mode_combo = ttk.Combobox(bar, values=delivery.DELIVERY_MODES, width=9,
                                           state="readonly")
            self.mode_combo.set(delivery.DELIVERY_MODES[0])
            self.mode_combo.pack(side="left", padx=2)
            ttk.Label(bar, text="Where").pack(side="left")
            self.location_var = tk.StringVar()
            ttk.Entry(bar, textvariable=self.location_var, width=10).pack(side="left", padx=2)
            ttk.Button(bar, text="Add delivery", command=self.add_delivery).pack(side="left")
            bar2 = ttk.Frame(tab)
            bar2.pack(fill="x", **_PAD)
            ttk.Button(bar2, text="Change places", command=self.change_places).pack(side="left")
            for status in delivery.DELIVERY_STATUSES:
                ttk.Button(bar2, text=f"Mark {status.lower()}",
                           command=lambda s=status: self.set_delivery_status(s)).pack(
                    side="left", padx=2)
        self.delivery_tree = _tree(tab, [("term", "Term"), ("sec", "Section"),
                                         ("lead", "Taught by"), ("places", "Enrolled / places"),
                                         ("mode", "Mode"), ("where", "Where"),
                                         ("status", "Status")],
                                   [120, 60, 90, 110, 80, 90, 70], height=4)

        ttk.Label(tab, text="Weekly timetable:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 0))
        if self.can_manage:
            tbar = ttk.Frame(tab)
            tbar.pack(fill="x", **_PAD)
            self.day_combo = ttk.Combobox(tbar, values=delivery.DAYS, width=9, state="readonly")
            self.day_combo.pack(side="left")
            self.start_var, self.end_var = tk.StringVar(value="09:00"), tk.StringVar(value="10:00")
            ttk.Entry(tbar, textvariable=self.start_var, width=6).pack(side="left", padx=2)
            ttk.Label(tbar, text="–").pack(side="left")
            ttk.Entry(tbar, textvariable=self.end_var, width=6).pack(side="left", padx=2)
            self.session_combo = ttk.Combobox(tbar, values=delivery.SESSION_TYPES, width=9,
                                              state="readonly")
            self.session_combo.set("Lecture")
            self.session_combo.pack(side="left", padx=2)
            self.room_combo = ttk.Combobox(tbar, width=12, state="readonly")
            self.room_combo.pack(side="left", padx=2)
            self.slot_instructor_combo = ttk.Combobox(tbar, width=14, state="readonly")
            self.slot_instructor_combo.pack(side="left", padx=2)
            tbar2 = ttk.Frame(tab)
            tbar2.pack(fill="x", **_PAD)
            ttk.Label(tbar2, text="Semester").pack(side="left")
            self.slot_semester_var = tk.StringVar()
            ttk.Entry(tbar2, textvariable=self.slot_semester_var, width=10).pack(side="left", padx=2)
            ttk.Label(tbar2, text="Runs until (YYYY-MM-DD)").pack(side="left")
            self.until_var = tk.StringVar()
            ttk.Entry(tbar2, textvariable=self.until_var, width=11).pack(side="left", padx=2)
            tbar3 = ttk.Frame(tab)
            tbar3.pack(fill="x", **_PAD)
            ttk.Label(tbar3, text="Delivery").pack(side="left")
            self.slot_delivery_combo = ttk.Combobox(tbar3, width=20, state="readonly")
            self.slot_delivery_combo.pack(side="left", padx=2)
            ttk.Label(tbar3, text="Weeks (e.g. 1-5,7-11)").pack(side="left")
            self.weeks_var = tk.StringVar()
            ttk.Entry(tbar3, textvariable=self.weeks_var, width=9).pack(side="left", padx=2)
            ttk.Label(tbar3, text="Online link").pack(side="left")
            self.online_var = tk.StringVar()
            ttk.Entry(tbar3, textvariable=self.online_var, width=18).pack(side="left", padx=2)
            ttk.Button(tbar3, text="Add session", command=self.add_slot).pack(side="left", padx=4)
            ttk.Button(tbar3, text="Withdraw session", command=self.cancel_slot).pack(side="left")
        self.slot_tree = _tree(tab, [("day", "Day"), ("time", "Time"), ("type", "Type"),
                                     ("room", "Room"), ("who", "Instructor"),
                                     ("sem", "Semester"), ("weeks", "Weeks"),
                                     ("delivery", "Delivery"), ("online", "Online")],
                               [70, 90, 70, 80, 100, 65, 60, 100, 50], height=5)

    def refresh_delivery(self):
        _clear(self.delivery_tree)
        _clear(self.slot_tree)
        if self.can_manage and not self.term_combo["values"]:
            self._terms = [(t["name"], t) for t in data.call(delivery.term_choices)]
            self.term_combo["values"] = [t for t, _ in self._terms]
            self._rooms = [(r["label"] or f"Room {r['id']}", r)
                           for r in data.call(delivery.room_choices)]
            self.room_combo["values"] = ["(no room)"] + [t for t, _ in self._rooms]
            self._instructors = [(i["name"], i) for i in data.call(delivery.instructor_choices)]
            self.slot_instructor_combo["values"] = ["(no instructor)"] + [
                t for t, _ in self._instructors]
        if not self.current_code:
            return
        self._deliveries = data.call(delivery.deliveries, self.current_code)
        for d in self._deliveries:
            self.delivery_tree.insert("", "end", iid=str(d["id"]), values=(
                d["term"], d["section_number"], d["instructor"] or "",
                f"{d['enrolled']} / {d['capacity']}", d["delivery_mode"], d["location"] or "",
                d["status"]))
        for s in data.call(delivery.slots, self.current_code):
            self.slot_tree.insert("", "end", iid=str(s["id"]), values=(
                s["day_of_week"], f"{s['start_time']}–{s['end_time']}", s["session_type"] or "",
                s["room"] or "", s["instructor"] or "", s["semester"] or "",
                s["week_pattern"] or "all", s["delivery"] or "all", "yes" if s["online_url"] else ""))
        if self.can_manage:
            self._slot_deliveries = [(f"{d['term']} {d['section_number']}", d)
                                     for d in self._deliveries]
            self.slot_delivery_combo["values"] = ["(all deliveries)"] + [
                t for t, _ in self._slot_deliveries]
            if not self.slot_delivery_combo.get():
                self.slot_delivery_combo.set("(all deliveries)")

    def add_delivery(self):
        if not self._require_module():
            return
        term = _pick(self._terms, self.term_combo.get())
        if not term:
            self._info("Add delivery", "Choose a term first.")
            return
        leader = data.call(delivery.leader, self.current_code)
        if self._do("Add delivery", delivery.add_delivery, self.current_code, term["id"],
                    self.places_var.get(), leader, self.mode_combo.get(),
                    self.location_var.get(), self.username):
            self._audit("add_module_delivery", module_code=self.current_code, term=term["name"])
            self.refresh_delivery()
            self.refresh_enrolments()

    def _selected_delivery(self):
        sel = self.delivery_tree.selection()
        if not self._require_module() or not sel:
            self._info("Delivery", "Select a delivery first.")
            return None
        return int(sel[0])

    def change_places(self):
        section = self._selected_delivery()
        if section is None:
            return
        from tkinter import simpledialog
        places = simpledialog.askinteger("Change places", "How many places?", parent=self.root,
                                         minvalue=1)
        if places:
            self._do("Change places", delivery.update_delivery, self.current_code, section,
                     capacity=places, actor=self.username)
            self.refresh_delivery()

    def set_delivery_status(self, status):
        section = self._selected_delivery()
        if section is not None:
            self._do("Change delivery status", delivery.update_delivery, self.current_code,
                     section, status=status, actor=self.username)
            self.refresh_delivery()
            self.refresh_enrolments()

    def add_slot(self):
        if not self._require_module():
            return
        room = _pick(self._rooms, self.room_combo.get())
        instructor = _pick(self._instructors, self.slot_instructor_combo.get())
        args = (self.current_code, self.day_combo.get(), self.start_var.get().strip(),
                self.end_var.get().strip())
        kwargs = dict(session_type=self.session_combo.get(), room_id=room and room["id"],
                      instructor_id=instructor and instructor["id"],
                      semester=self.slot_semester_var.get().strip() or None,
                      until=self.until_var.get().strip() or None,
                      section_id=(_pick(self._slot_deliveries, self.slot_delivery_combo.get())
                                  or {}).get("id"),
                      week_pattern=self.weeks_var.get().strip() or None,
                      online_url=self.online_var.get().strip() or None, actor=self.username)
        try:
            made = data.call(delivery.add_slot, *args, **kwargs)
        except ValueError as exc:
            if not str(exc).startswith("Clashes with"):
                self._error("Add session", str(exc))
                return
            if not self._ask("Timetable clash or warning", f"{exc}\n\nAdd the session anyway?"):
                return
            made = self._do("Add session", delivery.add_slot, *args, force=True, **kwargs)
        except Exception as exc:
            self._error("Add session", f"Add session failed: {exc}")
            return
        if made:
            self._audit("add_module_session", module_code=self.current_code,
                        day=self.day_combo.get(), start=self.start_var.get())
            sent = timetable_occurrences.send_emails(made["emails"])
            self._status(f"Session added; {sent} student/staff email(s) sent")
            self.refresh_delivery()

    def cancel_slot(self):
        sel = self.slot_tree.selection()
        if not self._require_module() or not sel:
            return
        if self._ask("Withdraw session", "Stop this weekly session altogether? Registers "
                     "already taken are kept and the students are told. (To call off a "
                     "single week, use the Timetable window's Whole term tab.)"):
            done = self._do("Withdraw session", delivery.cancel_slot, self.current_code,
                            int(sel[0]), self.username)
            if done:
                timetable_occurrences.send_emails(done["emails"])
            self.refresh_delivery()

    # ── feedback ─────────────────────────────────────────────────────

    def _build_feedback(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Feedback")
        ttk.Label(tab, text="Student evaluations of this module:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        self.eval_tree = _tree(tab, [("year", "Year"), ("sem", "Semester"),
                                     ("open", "Open"), ("resp", "Responses"),
                                     ("rate", "Completion"), ("score", "Mean score")],
                               [80, 80, 170, 80, 90, 90], height=5)
        ttk.Label(tab, text="You said, we did:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 0))
        self.ysw_tree = _tree(tab, [("year", "Year"), ("theme", "Theme"), ("said", "You said"),
                                    ("did", "We did"), ("status", "Status")],
                              [70, 100, 220, 220, 70], height=6)
        ttk.Label(tab, foreground="#666", text=(
            "Evaluations are run from Course Evaluation; this is a read-only summary.")).pack(
            anchor="w", padx=8)

    def refresh_feedback(self):
        _clear(self.eval_tree)
        _clear(self.ysw_tree)
        if not self.current_code:
            return
        for e in data.call(delivery.evaluations, self.current_code):
            score = "—" if e["mean_score"] is None else (
                f"{e['mean_score']:.2f}" + (f" / {e['scale_max']:g}" if e["scale_max"] else ""))
            self.eval_tree.insert("", "end", iid=str(e["evaluation_id"]), values=(
                e["academic_year"], e["semester"], (f"{e['start_date']} → {e['end_date']}" if e['end_date'] else e['start_date']),
                e["response_count"] or 0, f"{(e['completion_rate'] or 0):.0f}%", score))
        for i, y in enumerate(data.call(delivery.you_said_we_did, self.current_code)):
            self.ysw_tree.insert("", "end", iid=str(i), values=(
                y["academic_year"], y["theme"], y["you_said"], y["we_did"] or "", y["status"]))
