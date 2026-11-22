"""Personal emergency evacuation plans (PEEPs) — the register and editor.

Estates, health & safety and disability services staff see the register
(filter by building or review due), open and print plans, and send the
review reminders; those who manage plans add, edit, review and archive them.
Anyone else sees their own plan. Everything goes through
``domain/disability/peeps``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from education_system.systems.university.domains.student_support.domain.disability import peeps
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.domains.student_support.interfaces.gui.disability.forms import (
    ask_form,
    fill_tree,
    make_tree,
    selected_id,
    show_error,
)

TITLE = "Evacuation Plans (PEEPs)"
COLUMNS = [("peep_id", "#", 50), ("person_type", "Type", 70), ("person_ref", "Who", 110),
           ("person_name", "Name", 170), ("buildings", "Buildings", 240),
           ("evacuation_method", "Evacuation", 180), ("status", "Status", 70),
           ("review_date", "Review due", 90), ("overdue", "Overdue", 70)]


def _plan_text(plan) -> str:
    where = "\n".join(f"  • {loc['building']}: {loc.get('rooms') or 'all areas'}"
                      for loc in plan.get("locations", []))
    buddies = "\n".join(f"  • {b['name']} {b.get('contact') or ''} {b.get('notes') or ''}"
                        for b in plan.get("buddies", []))
    return "\n".join([
        f"PEEP #{plan['peep_id']} — {plan.get('person_name') or plan['person_ref']} "
        f"({plan['person_type']} {plan['person_ref']})",
        f"Status: {plan['status']}    Review due: {plan.get('review_date') or '—'}    "
        f"Last reviewed: {plan.get('last_reviewed_at') or 'never'} "
        f"{plan.get('last_reviewed_by') or ''}",
        "", "Buildings and rooms:", where or "  —",
        "", f"Assistance needed:\n  {plan.get('assistance_needed') or '—'}",
        f"Evacuation method: {plan.get('evacuation_method') or '—'}",
        f"Equipment: {plan.get('equipment') or '—'}",
        f"Refuge points: {plan.get('refuge_points') or '—'}",
        f"Alerted by: {plan.get('alarm_method') or '—'}",
        "", "Buddies:", buddies or "  —",
        "", f"Notes: {plan.get('other_notes') or '—'}",
        f"Plan manager: {plan.get('manager_username') or '—'}"])


def _parse_locations(text) -> list[dict]:
    """One building per line: ``Building: room, room``."""
    out = []
    for line in str(text or "").splitlines():
        building, _, rooms = line.partition(":")
        if building.strip():
            out.append({"building": building.strip(), "rooms": rooms.strip()})
    return out


def _parse_buddies(text) -> list[dict]:
    """One buddy per line: ``Name; contact; notes``."""
    out = []
    for line in str(text or "").splitlines():
        parts = [p.strip() for p in line.split(";")]
        if parts and parts[0]:
            out.append({"name": parts[0], "contact": parts[1] if len(parts) > 1 else "",
                        "notes": parts[2] if len(parts) > 2 else ""})
    return out


class PeepsPanel(ttk.Frame):
    """``PeepsPanel(master, auth)`` — the register, or the person's own plan."""

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        self.viewer = access.is_peep_viewer(auth)
        self.manager = access.may_manage_peeps(auth)
        if self.viewer:
            self._build_register()
            self.refresh()
        else:
            self._build_own()

    # ------------------------------------------------------------- own plan
    def _build_own(self):
        ttk.Label(self, text="My Personal Emergency Evacuation Plan",
                  font=("Arial", 12, "bold")).pack(anchor="w")
        text = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=24)
        text.pack(fill=tk.BOTH, expand=True, pady=6)
        try:
            plans = peeps.my_plans(self.auth)
        except Exception as exc:
            show_error(self, TITLE, exc)
            plans = []
        text.insert("1.0", "\n\n".join(_plan_text(p) for p in plans) if plans else
                    "You have no evacuation plan. If you would need help to leave a building "
                    "in an emergency, ask disability services (students) or your line "
                    "manager / health & safety (staff) to make one with you.")
        text.config(state="disabled")

    # ------------------------------------------------------------- register
    def _build_register(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Building:").pack(side=tk.LEFT)
        self.building_var = tk.StringVar()
        ttk.Combobox(top, textvariable=self.building_var, width=28,
                     values=[""] + peeps.known_buildings()).pack(side=tk.LEFT, padx=4)
        self.due_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text=f"Review due within {peeps.REMINDER_DAYS} days",
                        variable=self.due_var).pack(side=tk.LEFT, padx=8)
        self.archived_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Archived", variable=self.archived_var).pack(side=tk.LEFT)
        ttk.Button(top, text="Apply", command=self.refresh).pack(side=tk.LEFT, padx=6)
        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var).pack(side=tk.RIGHT)

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(6, 4))
        for text, command, needs in (("Open", self.open_selected, False),
                                     ("New plan…", self.new_plan, True),
                                     ("Edit…", self.edit_plan, True),
                                     ("Mark reviewed…", self.mark_reviewed, True),
                                     ("Archive…", self.archive, True),
                                     ("Print (PDF)", self.print_pdf, False),
                                     ("Send review reminders", self.reminders, True)):
            btn = ttk.Button(bar, text=text, command=command)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            if needs and not self.manager:
                btn.config(state="disabled")

        detail = ttk.LabelFrame(self, text="Plan", padding=6)
        detail.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, pady=(6, 0))
        self.detail = scrolledtext.ScrolledText(detail, height=11, wrap=tk.WORD,
                                                state="disabled")
        self.detail.pack(fill=tk.BOTH)
        frame, self.tree = make_tree(self, COLUMNS, height=10)
        frame.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())

    def refresh(self):
        try:
            rows = peeps.register(
                self.auth, building=self.building_var.get().strip() or None,
                status="archived" if self.archived_var.get() else None,
                review_due_days=peeps.REMINDER_DAYS if self.due_var.get() else None)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        for row in rows:
            row["overdue"] = "Yes" if row.get("review_overdue") else ""
        fill_tree(self.tree, rows, COLUMNS, key="peep_id")
        self.count_var.set(f"{len(rows)} plan{'s' if len(rows) != 1 else ''}")
        self._show("Open a plan to see it. Opening one is recorded in the audit log.")

    def _show(self, text):
        self.detail.config(state="normal")
        self.detail.delete("1.0", tk.END)
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")

    def _selected(self):
        return selected_id(self.tree, self, TITLE, "a plan")

    def open_selected(self):
        pid = self._selected()
        if not pid:
            return
        try:
            self._show(_plan_text(peeps.plan_detail(self.auth, pid)))
        except Exception as exc:
            show_error(self, TITLE, exc)

    def _form(self, title, plan=None, new=False):
        plan = plan or {}
        fields = []
        if new:
            fields += [("person_type", "For a", "combo", (list(peeps.PERSON_TYPES), "student")),
                       ("person_ref", "Student number / staff username", "entry", "")]
        locations = "\n".join(f"{loc['building']}: {loc.get('rooms') or ''}"
                              for loc in plan.get("locations", []))
        buddies = "\n".join(f"{b['name']}; {b.get('contact') or ''}; {b.get('notes') or ''}"
                            for b in plan.get("buddies", []))
        fields += [
            ("locations", "Buildings used (one per line — Building: rooms)", "text", locations),
            ("assistance_needed", "Assistance needed", "text",
             plan.get("assistance_needed") or ""),
            ("evacuation_method", "Evacuation method", "combo",
             (list(peeps.EVACUATION_METHODS), plan.get("evacuation_method") or "")),
            ("equipment", "Equipment (e.g. evacuation chair)", "entry",
             plan.get("equipment") or ""),
            ("refuge_points", "Refuge points", "entry", plan.get("refuge_points") or ""),
            ("alarm_method", "How alerted", "combo",
             (list(peeps.ALARM_METHODS), plan.get("alarm_method") or "")),
            ("buddies", "Buddies (one per line — Name; contact; notes)", "text", buddies),
            ("review_date", "Review date (YYYY-MM-DD)", "entry", plan.get("review_date") or ""),
            ("status", "Status", "combo", (["draft", "active"], plan.get("status") or "draft")),
            ("manager_username", "Plan manager (username, blank = you)", "entry",
             plan.get("manager_username") or ""),
            ("other_notes", "Other notes", "text", plan.get("other_notes") or "")]
        data = ask_form(self, title, fields, width=56)
        if data:
            data["locations"] = _parse_locations(data["locations"])
            data["buddies"] = _parse_buddies(data["buddies"])
        return data

    def new_plan(self):
        data = self._form("New evacuation plan", new=True)
        if not data:
            return
        try:
            peeps.create_plan(self.auth, data.pop("person_type"), data.pop("person_ref"), data)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        self.refresh()

    def edit_plan(self):
        pid = self._selected()
        if not pid:
            return
        try:
            plan = peeps.plan_detail(self.auth, pid)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        data = self._form(f"Edit PEEP #{pid}", plan)
        if not data:
            return
        try:
            peeps.update_plan(self.auth, pid, data)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        self.refresh()

    def mark_reviewed(self):
        pid = self._selected()
        if not pid:
            return
        data = ask_form(self, "Mark reviewed", [
            ("next_review", "Next review (YYYY-MM-DD, blank = a year)", "entry", "")])
        if data is None:
            return
        try:
            nxt = peeps.mark_reviewed(self.auth, pid, next_review=data["next_review"])
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        messagebox.showinfo(TITLE, f"Reviewed. Next review: {nxt}.", parent=self)
        self.refresh()

    def archive(self):
        pid = self._selected()
        if not pid:
            return
        data = ask_form(self, "Archive plan", [("reason", "Reason", "entry", "")])
        if not data:
            return
        try:
            peeps.archive_plan(self.auth, pid, data["reason"])
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        self.refresh()

    def print_pdf(self):
        pid = self._selected()
        if not pid:
            return
        try:
            path = peeps.plan_pdf(self.auth, pid)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        messagebox.showinfo(TITLE, f"Saved: {path}", parent=self)

    def reminders(self):
        try:
            sent = peeps.send_review_reminders(self.auth)
        except Exception as exc:
            show_error(self, TITLE, exc)
            return
        messagebox.showinfo(TITLE, f"Reminders sent for {sent} plan{'s' if sent != 1 else ''} "
                                   "(each review date is reminded once).", parent=self)
