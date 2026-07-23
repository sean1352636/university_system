"""Standalone Tk launcher for Tutor Groups.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user; key
write actions are stamped with that identity in the log.

Persistence: data lives in the central `student_records.db` (tutor
group / member / meeting tables managed by `TutorGroupService`). Any
stray *.db files alongside this module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

logger = logging.getLogger(__name__)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


from education_system.post_18.university_system.modules.domain.academics.tutor_groups import (  # noqa: E402
    TutorGroupService,
    TutorGroupError,
)


def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars, with a
    fallback to the in-process global auth singleton."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.post_18.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


def _remove_legacy_db():
    """Sweep any stray local SQLite files left alongside this module
    by earlier iterations. Data lives in the central student_records.db."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(here):
        return
    for fname in os.listdir(here):
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy tutor-groups DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


class _Frame(tk.Frame):
    # 8.117.66 — flattened to the main GUI's clam-default neutrals.
    # Pre-8.117.66 the frame had a navy header bar (#2c3e50) with white
    # text on a pale-grey body (#ecf0f1) — visually disconnected from
    # every other workspace tab.
    def __init__(self, parent, user=None):
        super().__init__(parent, bg="#f0f0f0")
        self._svc = TutorGroupService()
        self._user = user
        self._user_display = _user_display_name(user)
        self._build()
        self._refresh()

    def _build(self):
        hdr = tk.Frame(self, bg="#f0f0f0", height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Tutor Groups", font=("Helvetica", 14, "bold"),
                 bg="#f0f0f0", fg="#000000").pack(side="left", padx=20, pady=8)
        role = (self._user or {}).get('role') or ('—' if self._user else 'not signed in')
        tk.Label(hdr, text=f"Signed in: {self._user_display}  ({role})",
                 font=("Helvetica", 9), bg="#f0f0f0",
                 fg="#555555").pack(side="right", padx=20, pady=14)

        ctrl = tk.Frame(self, bg="#f0f0f0"); ctrl.pack(fill="x", padx=10, pady=6)
        tk.Button(ctrl, text="Create Group", command=self._create).pack(side="left", padx=4)
        tk.Button(ctrl, text="Add Member", command=self._add_member).pack(side="left", padx=4)
        tk.Button(ctrl, text="Assign Tutor", command=self._assign).pack(side="left", padx=4)
        tk.Button(ctrl, text="Schedule Meeting", command=self._meeting).pack(side="left", padx=4)
        tk.Button(ctrl, text="List Members", command=self._list_members).pack(side="left", padx=4)
        tk.Button(ctrl, text="List Meetings", command=self._list_meetings).pack(side="left", padx=4)
        tk.Button(ctrl, text="Record Meeting", command=self._record_meeting).pack(side="left", padx=4)
        tk.Button(ctrl, text="List Assignments", command=self._list_assignments).pack(side="left", padx=4)
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
            gid = self._svc.create_group(name, year, prog, lead, capacity=cap)
            logger.info("Tutor group created group_id=%s name=%r year=%s lead=%s by=%s",
                        gid, name, year, lead, self._user_display)
            self._refresh()
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _add_member(self):
        gid = self._selected()
        if gid is None: return
        sid = simpledialog.askstring("Member", "Student ID:", parent=self)
        if not sid: return
        try:
            self._svc.add_member(gid, sid)
            logger.info("Tutor group member added group_id=%s student_id=%s by=%s",
                        gid, sid, self._user_display)
            messagebox.showinfo("OK", "Added.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _assign(self):
        gid = self._selected()
        if gid is None: return
        tid = simpledialog.askstring("Tutor", "Tutor ID:", parent=self)
        if not tid: return
        try:
            self._svc.assign_tutor(gid, tid)
            logger.info("Tutor assigned group_id=%s tutor_id=%s by=%s",
                        gid, tid, self._user_display)
            messagebox.showinfo("OK", "Assigned.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _meeting(self):
        gid = self._selected()
        if gid is None: return
        when = simpledialog.askstring("Meeting", "Scheduled at YYYY-MM-DD HH:MM:", parent=self)
        if not when: return
        try:
            self._svc.schedule_meeting(gid, when)
            logger.info("Tutor group meeting scheduled group_id=%s when=%s by=%s",
                        gid, when, self._user_display)
            messagebox.showinfo("OK", "Scheduled.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _show_list_window(self, title, columns, rows):
        """Open a Toplevel with a Treeview listing ``rows`` (list of tuples)."""
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("760x420")
        tree = ttk.Treeview(win, columns=columns, show="headings")
        for c in columns:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=max(90, 700 // len(columns)))
        for r in rows:
            tree.insert("", "end", values=r)
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        if not rows:
            tk.Label(win, text="No records found.").pack(pady=4)

    def _list_members(self):
        gid = self._selected()
        if gid is None: return
        try:
            members = self._svc.list_members(gid, active_only=False)
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e)); return
        cols = ("membership_id", "student_id", "role", "joined_date", "left_date", "active")
        rows = [(m["membership_id"], m["student_id"], m.get("role"),
                 m.get("joined_date"), m.get("left_date") or "-",
                 "Yes" if m.get("is_active") else "No") for m in members]
        self._show_list_window(f"Members — Group {gid}", cols, rows)

    def _list_meetings(self):
        gid = self._selected()
        if gid is None: return
        try:
            meetings = self._svc.list_meetings(gid, upcoming_only=False)
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e)); return
        cols = ("meeting_id", "scheduled_at", "duration_minutes", "location",
                "attendance_count", "status")
        rows = [(m["meeting_id"], m.get("scheduled_at"), m.get("duration_minutes"),
                 m.get("location") or "-",
                 m.get("attendance_count") if m.get("attendance_count") is not None else "-",
                 m.get("status")) for m in meetings]
        self._show_list_window(f"Meetings — Group {gid}", cols, rows)

    def _record_meeting(self):
        mid = simpledialog.askinteger("Record Meeting", "Meeting ID:", parent=self)
        if mid is None: return
        att = simpledialog.askinteger("Record Meeting", "Attendance count:",
                                      initialvalue=0, minvalue=0, parent=self)
        if att is None: return
        notes = simpledialog.askstring("Record Meeting", "Notes (optional):", parent=self) or ""
        status = simpledialog.askstring("Record Meeting",
                                        "Status (held/cancelled):",
                                        initialvalue="held", parent=self) or "held"
        try:
            self._svc.record_meeting(mid, att, notes=notes, status=status)
            logger.info("Tutor group meeting recorded meeting_id=%s att=%s status=%s by=%s",
                        mid, att, status, self._user_display)
            messagebox.showinfo("OK", "Meeting recorded.")
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e))

    def _list_assignments(self):
        gid = self._selected()
        if gid is None: return
        try:
            rows_raw = self._svc.list_assignments(group_id=gid, active_only=False)
        except TutorGroupError as e:
            messagebox.showerror("Error", str(e)); return
        cols = ("assignment_id", "group_id", "tutor_id", "role",
                "assigned_date", "ended_date", "active")
        rows = [(a["assignment_id"], a["group_id"], a["tutor_id"], a.get("role"),
                 a.get("assigned_date"), a.get("ended_date") or "-",
                 "Yes" if a.get("is_active") else "No") for a in rows_raw]
        self._show_list_window(f"Pastoral Assignments — Group {gid}", cols, rows)

    def _summary(self):
        gid = self._selected()
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
    _remove_legacy_db()
    user = _get_current_user()
    logger.info("Tutor Groups starting user=%s role=%s",
                _user_display_name(user),
                (user or {}).get('role') or 'none')
    root = tk.Tk()
    root.title("Tutor Groups"); root.geometry("960x600")
    _Frame(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
