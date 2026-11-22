"""Standalone Tk window for institution-wide timetabling.

Launched as a subprocess by the main GUI (``_NEW_FEATURE_MODULES``); the
signed-in user arrives via ``require_launcher_auth``. Staff only. Backed by
``domains.teaching.application.timetabling``; no DB access at import time.
"""
from __future__ import annotations

import json
import logging
import pathlib
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

from education_system.systems.university.domains.teaching.application import timetabling  # noqa: E402
from education_system.systems.university.infrastructure.i18n import get_text as _t  # noqa: E402

logger = logging.getLogger(__name__)

STAFF_ROLES = ("admin", "administrator", "staff")
_ACTIVITIES_HINT = (
    'Activities as a JSON list, e.g.\n'
    '[{"activity_id": "A", "staff_id": "T1", "cohorts": ["C1"], "allowed_slots": ["MON-09"]}]'
)


class TimetablingApp(tk.Frame):
    """Versions on the left; the selected version's schedule and change requests on the right."""

    def __init__(self, parent, user=None):
        super().__init__(parent)
        self._user = user or {}
        self._actor = str(self._user.get("username") or self._user.get("id") or "unknown")
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text=_t("gui.academics.timetabling.title", default="Institutional Timetabling"),
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=16, pady=8)
        tk.Label(header, text=f"Signed in: {self._actor} ({self._user.get('role') or '-'})",
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=16)

        bar = tk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        for label, cmd in (("Refresh", self.refresh), ("Published Schedule", self.show_published),
                           ("Draft from live timetable", self.draft_from_timetable),
                           ("Build Draft", self.build_draft), ("Publish", self.publish),
                           ("Request Change", self.request_change)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=4)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("version_id", "academic_year", "status", "created_by", "created_at", "published_at")
        self._tree = ttk.Treeview(panes, columns=cols, show="headings")
        for col, width in zip(cols, (260, 80, 90, 100, 140, 140)):
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=width, stretch=col == "version_id")
        self._tree.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())
        panes.add(self._tree, weight=3)
        self._detail = tk.Text(panes, wrap="word", state="disabled", width=55)
        panes.add(self._detail, weight=2)

    def _selected_id(self) -> str | None:
        sel = self._tree.focus()
        return self._tree.item(sel, "values")[0] if sel else None

    def _set_detail(self, text: str):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    @staticmethod
    def _format_schedule(schedule) -> str:
        if not schedule:
            return "(empty schedule)"
        return "\n".join(
            f"  {item.get('activity_id') or '-'}  {item.get('slot')}  {item.get('room')}  "
            f"staff={item.get('staff_id') or '-'}  cohorts={', '.join(item.get('cohorts') or [])}"
            for item in schedule)

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        try:
            rows = timetabling.list_versions()
        except Exception as exc:
            logger.exception("Version list failed")
            messagebox.showerror("Error", f"Could not load versions:\n{exc}", parent=self)
            return
        for row in rows:
            self._tree.insert("", "end", values=(
                row["version_id"], row["academic_year"] or "", row["status"] or "",
                row["created_by"] or "", str(row["created_at"] or "")[:19],
                str(row["published_at"] or "")[:19]))
        self._set_detail("")

    def show_detail(self):
        version_id = self._selected_id()
        if not version_id:
            return
        try:
            record = timetabling.version_record(version_id)
            requests = timetabling.list_change_requests(version_id)
        except ValueError as exc:
            self._set_detail(str(exc))
            return
        schedule = record.pop("schedule")
        lines = [f"{key}: {value}" for key, value in record.items()]
        lines.append(f"\nSchedule ({len(schedule)} activities):")
        lines.append(self._format_schedule(schedule))
        lines.append(f"\nChange requests ({len(requests)}):")
        for req in requests:
            lines.append(f"  {req['request_id']}  [{req['status']}] {req['requested_by'] or '-'}: "
                         f"{req['reason']}\n    {req['proposed_json']}")
        self._set_detail("\n".join(lines))

    def show_published(self):
        try:
            schedule = timetabling.published_schedule()
        except Exception as exc:
            messagebox.showerror("Published Schedule", str(exc), parent=self)
            return
        self._set_detail("Published schedule:\n" + self._format_schedule(schedule))

    def build_draft(self):
        raw = simpledialog.askstring("Build Draft", _ACTIVITIES_HINT, parent=self)
        if raw is None:
            return
        slots = simpledialog.askstring("Build Draft", "Slots (comma-separated):", parent=self) or ""
        rooms = simpledialog.askstring("Build Draft", "Rooms (comma-separated):", parent=self) or ""
        year = simpledialog.askstring("Build Draft", "Academic year (e.g. 2027/28):", parent=self) or ""
        try:
            activities = json.loads(raw)
            if not isinstance(activities, list):
                raise ValueError("Activities must be a JSON list")
            version_id = timetabling.optimise(
                activities,
                [s.strip() for s in slots.split(",") if s.strip()],
                [r.strip() for r in rooms.split(",") if r.strip()],
                academic_year=year.strip(), created_by=self._actor)
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Build Draft", str(exc), parent=self)
            return
        messagebox.showinfo("Build Draft", f"Draft version {version_id} created.", parent=self)
        self.refresh()

    def draft_from_timetable(self):
        """Re-solve the live weekly timetable for clashes as a draft version."""
        year = simpledialog.askstring("Draft from live timetable",
                                      "Academic year (e.g. 2026/27):", parent=self)
        if not year:
            return
        try:
            version_id = timetabling.build_from_timetable(academic_year=year.strip(),
                                                          created_by=self._actor)
        except ValueError as exc:
            messagebox.showerror("Draft from live timetable", str(exc), parent=self)
            return
        messagebox.showinfo("Draft from live timetable",
                            f"Draft version {version_id} created from the live timetable. "
                            "Publishing it moves any re-timed sessions and tells the "
                            "students and staff.", parent=self)
        self.refresh()

    def publish(self):
        version_id = self._selected_id()
        if not version_id:
            messagebox.showwarning("Publish", "Select a version first.", parent=self)
            return
        if not messagebox.askyesno("Publish", "Publishing supersedes the live timetable. Continue?",
                                   parent=self):
            return
        try:
            moved = timetabling.publish(version_id, approved_by=self._actor)
        except ValueError as exc:
            messagebox.showerror("Publish", str(exc), parent=self)
            return
        messagebox.showinfo("Publish", f"Published. {moved} weekly session(s) moved on the live "
                            "timetable." if moved else "Published. No live sessions changed.",
                            parent=self)
        self.refresh()

    def request_change(self):
        version_id = self._selected_id()
        if not version_id:
            messagebox.showwarning("Request Change", "Select a version first.", parent=self)
            return
        reason = simpledialog.askstring("Request Change", "Reason:", parent=self)
        if reason is None:
            return
        raw = simpledialog.askstring(
            "Request Change", 'Proposed change JSON, e.g. {"activity_id": "A", "slot": "TUE-09"}',
            parent=self) or "{}"
        try:
            proposed = json.loads(raw)
            if not isinstance(proposed, dict):
                raise ValueError("Proposed change must be a JSON object")
            request_id = timetabling.request_change(
                version_id, proposed, reason=reason.strip(), requested_by=self._actor)
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Request Change", str(exc), parent=self)
            return
        messagebox.showinfo("Request Change", f"Change request {request_id} logged.", parent=self)
        self.show_detail()


def main() -> None:
    from education_system.platform.delivery.gui.window_sizing import install
    from education_system.systems.university.shell.gui.auth.launch_guard import require_launcher_auth

    user = require_launcher_auth("Institutional Timetabling")
    if user is None:
        return
    if str(user.get("role", "")).lower() not in STAFF_ROLES:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Timetabling", "Timetabling is available to staff only.")
        root.destroy()
        return
    install()
    root = tk.Tk()
    root.title(_t("gui.academics.timetabling.title", default="Institutional Timetabling"))
    root.geometry("1400x900")
    root.minsize(1200, 800)
    TimetablingApp(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
