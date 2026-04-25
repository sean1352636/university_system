"""Standalone Tk launcher for Tutor Groups."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.modules.domain.academics.tutor_groups import (
    TutorGroupService,
    TutorGroupError,
)


class _Frame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#ecf0f1")
        self._svc = TutorGroupService()
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#2c3e50", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Tutor Groups", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=8)

        ctrl = tk.Frame(self, bg="#ecf0f1"); ctrl.pack(fill="x", padx=10, pady=6)
        tk.Button(ctrl, text="Create Group", command=self._create).pack(side="left", padx=4)
        tk.Button(ctrl, text="Add Member", command=self._add_member).pack(side="left", padx=4)
        tk.Button(ctrl, text="Assign Tutor", command=self._assign).pack(side="left", padx=4)
        tk.Button(ctrl, text="Schedule Meeting", command=self._meeting).pack(side="left", padx=4)
        tk.Button(ctrl, text="Group Summary", command=self._summary).pack(side="left", padx=4)
        tk.Button(ctrl, text="Refresh", command=self._refresh).pack(side="left", padx=4)

        cols = ("id", "name", "year", "programme", "lead_tutor", "capacity", "active")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c in cols: self._tree.heading(c, text=c.title()); self._tree.column(c, width=120)
        self._tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _selected(self) -> int | None:
        sel = self._tree.focus()
        if not sel: messagebox.showwarning("Select", "Select a group first."); return None
        return int(self._tree.item(sel, "values")[0])

    def _create(self):
        name = simpledialog.askstring("Group", "Name:", parent=self)
        year = simpledialog.askstring("Group", "Academic year (e.g. 2025-26):", parent=self)
        prog = simpledialog.askstring("Group", "Programme:", parent=self)
        lead = simpledialog.askstring("Group", "Lead tutor ID:", parent=self)
        cap = simpledialog.askinteger("Group", "Capacity:", initialvalue=20, parent=self)
        if not all([name, year, prog, lead, cap]): return
        try:
            self._svc.create_group(name, year, prog, lead, capacity=cap); self._refresh()
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _add_member(self):
        gid = self._selected();
        if gid is None: return
        sid = simpledialog.askstring("Member", "Student ID:", parent=self)
        if not sid: return
        try:
            self._svc.add_member(gid, sid); messagebox.showinfo("OK", "Added.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _assign(self):
        gid = self._selected();
        if gid is None: return
        tid = simpledialog.askstring("Tutor", "Tutor ID:", parent=self)
        if not tid: return
        try:
            self._svc.assign_tutor(gid, tid); messagebox.showinfo("OK", "Assigned.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _meeting(self):
        gid = self._selected();
        if gid is None: return
        when = simpledialog.askstring("Meeting", "Scheduled at YYYY-MM-DD HH:MM:", parent=self)
        if not when: return
        try:
            self._svc.schedule_meeting(gid, when); messagebox.showinfo("OK", "Scheduled.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _summary(self):
        gid = self._selected();
        if gid is None: return
        try:
            s = self._svc.group_summary(gid)
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e)); return
        g = s.get("group", {})
        messagebox.showinfo("Group summary",
            f"{g.get('name')}  ({g.get('academic_year')})\n"
            f"Members:           {s.get('member_count', 0)}\n"
            f"Assignments:       {len(s.get('assignments', []))}\n"
            f"Recent meetings:   {len(s.get('recent_meetings', []))}\n"
            f"Upcoming meetings: {len(s.get('upcoming_meetings', []))}")

    def _refresh(self):
        for r in self._tree.get_children(): self._tree.delete(r)
        try:
            for g in self._svc.list_groups(active_only=False):
                self._tree.insert("", "end", values=(
                    g["group_id"], g.get("name"), g.get("academic_year"),
                    g.get("programme"), g.get("lead_tutor_id"), g.get("capacity"),
                    "Yes" if g.get("is_active") else "No",
                ))
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))


def main() -> None:
    root = tk.Tk()
    root.title("Tutor Groups"); root.geometry("960x600")
    _Frame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
