"""Shared 'Today' dashboard window.

A read-only Toplevel summarising what's happening today across the three
related systems:

  • classes (per-module attendance recorded vs. enrolled)
  • exams scheduled today
  • pending absence requests (highlighting missed-exam ones)

Open it from any GUI via ``open_today_window(parent)``. It opens its own
SQLite connection and closes it when destroyed.
"""

from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import date as _date
from tkinter import ttk

import logging
logger = logging.getLogger("absence_tracker.today")


def _db_path() -> str:
    from education_system.post_18.university_system.core.paths import (
        DEFAULT_DB_PATH,
    )
    return DEFAULT_DB_PATH


def _classes_today(conn, today: str) -> list[tuple]:
    """Distinct (module, recorded, enrolled) for today's recorded sessions."""
    try:
        return list(conn.execute(
            """SELECT ar.module_code,
                      SUM(CASE WHEN LOWER(ar.status)='present' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN LOWER(ar.status)='absent'  THEN 1 ELSE 0 END),
                      SUM(CASE WHEN LOWER(ar.status)='late'    THEN 1 ELSE 0 END),
                      COUNT(*)
               FROM attendance_records ar
               WHERE ar.date = ?
               GROUP BY ar.module_code
               ORDER BY ar.module_code""",
            (today,)).fetchall())
    except sqlite3.Error:
        logger.exception("today classes query failed")
        return []


def _exams_today(conn, today: str) -> list[tuple]:
    try:
        return list(conn.execute(
            """SELECT module_code,
                      COALESCE(module_name, module_code),
                      start_time, end_time, COALESCE(room,''),
                      COALESCE(students_enrolled, 0)
               FROM exams
               WHERE date = ?
               ORDER BY start_time""", (today,)).fetchall())
    except sqlite3.Error:
        logger.exception("today exams query failed")
        return []


def _pending_requests(conn) -> list[tuple]:
    try:
        return list(conn.execute(
            """SELECT r.id,
                      TRIM(COALESCE(s.first_name,'')||' '
                           ||COALESCE(s.last_name,'')) AS name,
                      r.student_id, r.module_code, r.date,
                      COALESCE(r.is_missed_exam, 0)
               FROM absence_requests r
               LEFT JOIN students s ON s.student_id = r.student_id
               WHERE r.status = 'pending'
               ORDER BY COALESCE(r.is_missed_exam,0) DESC,
                        r.date DESC, r.id DESC
               LIMIT 50""").fetchall())
    except sqlite3.Error:
        logger.exception("today pending-requests query failed")
        return []


def open_today_window(parent: tk.Misc) -> tk.Toplevel:
    win = tk.Toplevel(parent)
    win.title("Today — Cross-system Dashboard")
    win.geometry("780x560")
    win.minsize(600, 400)

    today = _date.today().isoformat()
    header = tk.Frame(win, bg="#0f1f3a", height=48)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text=f"📅  Today  ·  {today}",
             font=("Arial", 14, "bold"),
             bg="#0f1f3a", fg="white").pack(side="left", padx=16, pady=10)
    tk.Button(header, text="Refresh", relief="flat", bg="#2563eb",
              fg="white", padx=12, pady=4,
              command=lambda: _refresh()).pack(side="right", padx=12, pady=10)

    body = ttk.Frame(win, padding=10)
    body.pack(fill="both", expand=True)

    # Three stacked LabelFrames
    classes_lf = ttk.LabelFrame(body, text="Today's classes (recorded so far)",
                                padding=8)
    classes_lf.pack(fill="both", expand=True, pady=(0, 6))
    classes_tree = ttk.Treeview(
        classes_lf,
        columns=("mod", "present", "absent", "late", "total"),
        show="headings", height=5)
    for c, lbl, w in (("mod", "Module", 110), ("present", "Present", 80),
                      ("absent", "Absent", 80), ("late", "Late", 80),
                      ("total", "Recorded", 90)):
        classes_tree.heading(c, text=lbl)
        classes_tree.column(c, width=w, minwidth=50)
    classes_tree.pack(fill="both", expand=True)

    exams_lf = ttk.LabelFrame(body, text="Today's exams", padding=8)
    exams_lf.pack(fill="both", expand=True, pady=6)
    exams_tree = ttk.Treeview(
        exams_lf, columns=("mod", "name", "time", "room", "enrolled"),
        show="headings", height=5)
    for c, lbl, w in (("mod", "Module", 100), ("name", "Name", 200),
                      ("time", "Time", 120), ("room", "Room", 100),
                      ("enrolled", "Enrolled", 80)):
        exams_tree.heading(c, text=lbl)
        exams_tree.column(c, width=w, minwidth=60)
    exams_tree.pack(fill="both", expand=True)

    requests_lf = ttk.LabelFrame(body,
                                 text="Pending absence requests "
                                      "(missed-exam rows highlighted)",
                                 padding=8)
    requests_lf.pack(fill="both", expand=True, pady=(6, 0))
    req_tree = ttk.Treeview(
        requests_lf,
        columns=("rid", "student", "module", "date", "missed"),
        show="headings", height=8)
    for c, lbl, w in (("rid", "Req#", 60), ("student", "Student", 200),
                      ("module", "Module", 100), ("date", "Date", 100),
                      ("missed", "Missed exam?", 110)):
        req_tree.heading(c, text=lbl)
        req_tree.column(c, width=w, minwidth=50)
    req_tree.tag_configure("missed", background="#fde4e4")
    req_tree.pack(fill="both", expand=True)

    conn_holder = {"conn": None}

    def _open_conn():
        try:
            conn_holder["conn"] = sqlite3.connect(_db_path())
        except Exception:
            logger.exception("today: db open failed")
            conn_holder["conn"] = None

    def _close_conn():
        c = conn_holder.get("conn")
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
            conn_holder["conn"] = None

    def _refresh():
        for tree in (classes_tree, exams_tree, req_tree):
            for item in tree.get_children():
                tree.delete(item)
        c = conn_holder["conn"]
        if c is None:
            return
        for (mod, present, absent, late, total) in _classes_today(c, today):
            classes_tree.insert("", "end",
                                values=(mod, present, absent, late, total))
        if not classes_tree.get_children():
            classes_tree.insert("", "end",
                                values=("(no classes recorded yet today)",
                                        "", "", "", ""))
        for (mod, name, st, et, room, enrolled) in _exams_today(c, today):
            exams_tree.insert("", "end",
                              values=(mod, name, f"{st}-{et}", room, enrolled))
        if not exams_tree.get_children():
            exams_tree.insert("", "end",
                              values=("(no exams scheduled today)",
                                      "", "", "", ""))
        for (rid, name, sid, mod, dt, missed) in _pending_requests(c):
            display = (name or "").strip() or sid
            tag = "missed" if missed else ""
            req_tree.insert("", "end",
                            values=(rid, display, mod, dt,
                                    "yes" if missed else ""), tags=(tag,))
        if not req_tree.get_children():
            req_tree.insert("", "end",
                            values=("", "(no pending requests)", "", "", ""))

    win.bind("<Destroy>",
             lambda e, _w=win: e.widget is _w and _close_conn(), add="+")
    _open_conn()
    _refresh()
    return win


__all__ = ["open_today_window"]
