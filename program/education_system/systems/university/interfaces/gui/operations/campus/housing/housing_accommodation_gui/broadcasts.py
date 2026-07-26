"""Resident broadcast / mass communications.

Lets housing staff send a single message to a defined audience of
current residents — typical use cases: fire-drill notice, water
shutoff window, policy update, building-specific reminder.

Audience is resolved live at send time from
``housing_assignments WHERE status='Active'`` joined with the room +
building, filtered by an optional building and/or room type. Every
broadcast is recorded in ``housing_broadcasts`` (subject, body,
audience criteria, sender, recipient count) so admins can review
what's already gone out.

Email delivery delegates to ``shared.utils.email_service.send_email``;
when that's stubbed (no SMTP configured) the broadcast still records
successfully and shows the recipient count — useful for development.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_activity,
)
from education_system.systems.university.infrastructure.utils.email_service import (
    send_email,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    generate_id,
)

logger = logging.getLogger(__name__)


# ── Schema ─────────────────────────────────────────────────────────────

def _init_schema() -> None:
    try:
        conn = get_connection()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS housing_broadcasts (
                    broadcast_id    TEXT PRIMARY KEY,
                    subject         TEXT NOT NULL,
                    body            TEXT NOT NULL,
                    audience_building_id TEXT,
                    audience_room_type   TEXT,
                    recipient_count INTEGER NOT NULL,
                    sent_by         TEXT NOT NULL,
                    sent_at         TEXT NOT NULL
                )
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to init housing_broadcasts schema")
        raise


# ── Entry point ────────────────────────────────────────────────────────

def show_broadcasts(gui_instance) -> None:
    _init_schema()
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Resident Broadcasts",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True, padx=8, pady=4)

    compose = ttk.Frame(nb, padding=8)
    history = ttk.Frame(nb, padding=8)
    nb.add(compose, text="Compose")
    nb.add(history, text="History")

    _build_compose(gui_instance, compose, on_sent=lambda: _reload_history(history))
    _build_history(history)


# ── Compose tab ────────────────────────────────────────────────────────

def _build_compose(gui_instance, parent: ttk.Frame, *, on_sent) -> None:
    ttk.Label(parent,
              text=("Audience is resolved live from current 'Active' "
                    "assignments at send time. Leave filters blank to "
                    "include every current resident."),
              wraplength=820, foreground="#555").pack(anchor="w", pady=(0, 6))

    row1 = ttk.Frame(parent)
    row1.pack(fill="x", pady=2)
    ttk.Label(row1, text="Building:").pack(side="left", padx=(0, 4))
    building_var = tk.StringVar()
    building_combo = ttk.Combobox(row1, textvariable=building_var,
                                    state="readonly", width=30)
    buildings = _load_buildings()
    building_combo['values'] = ["(all buildings)"] + [b[1] for b in buildings]
    building_combo.current(0)
    building_combo.pack(side="left", padx=(0, 12))

    ttk.Label(row1, text="Room type:").pack(side="left")
    type_var = tk.StringVar()
    type_combo = ttk.Combobox(row1, textvariable=type_var,
                                state="readonly", width=18)
    type_combo['values'] = ["(all types)"] + _load_room_types()
    type_combo.current(0)
    type_combo.pack(side="left", padx=(4, 12))

    preview_var = tk.StringVar(value="No audience preview yet.")
    ttk.Label(parent, textvariable=preview_var,
              foreground="#444").pack(anchor="w", pady=(6, 4))

    ttk.Label(parent, text="Subject:").pack(anchor="w")
    subject_var = tk.StringVar()
    ttk.Entry(parent, textvariable=subject_var, width=90).pack(anchor="w",
                                                                 pady=(0, 6))

    ttk.Label(parent, text="Body:").pack(anchor="w")
    body = tk.Text(parent, height=10, width=90, wrap="word")
    body.pack(anchor="w", pady=(0, 6))

    def _selected() -> tuple[str | None, str | None]:
        b_id = (buildings[building_combo.current() - 1][0]
                if building_combo.current() > 0 else None)
        rt = type_var.get() if type_combo.current() > 0 else None
        return b_id, rt

    def preview() -> None:
        b_id, rt = _selected()
        recips = _resolve_audience(b_id, rt)
        preview_var.set(f"{len(recips)} resident(s) match.")

    def send() -> None:
        b_id, rt = _selected()
        subj = subject_var.get().strip()
        msg = body.get("1.0", "end").strip()
        if not subj or not msg:
            messagebox.showwarning("Broadcast",
                                    "Subject and body are both required.",
                                    parent=gui_instance.root)
            return
        recips = _resolve_audience(b_id, rt)
        if not recips:
            messagebox.showinfo("Broadcast",
                                 "No residents match — nothing to send.",
                                 parent=gui_instance.root)
            return
        if not messagebox.askyesno(
                "Broadcast",
                f"Send to {len(recips)} resident(s)?",
                parent=gui_instance.root):
            return

        sender = (gui_instance.auth.current_user.get('username')
                   if gui_instance.auth and gui_instance.auth.current_user
                   else 'housing')
        delivered, failed = _send_to_all(recips, subj, msg)

        try:
            bid = generate_id('BC')
            now = datetime.datetime.now().isoformat(timespec='seconds')
            conn = get_connection()
            try:
                conn.execute('''
                    INSERT INTO housing_broadcasts
                    (broadcast_id, subject, body, audience_building_id,
                     audience_room_type, recipient_count, sent_by, sent_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (bid, subj, msg, b_id, rt, delivered, sender, now))
                conn.commit()
            finally:
                conn.close()
            log_activity(f"Broadcast {bid} sent ({delivered} delivered, "
                         f"{failed} failed) — '{subj[:60]}'")
        except sqlite3.Error:
            logger.exception("Failed to record broadcast")

        messagebox.showinfo(
            "Broadcast",
            f"Sent: {delivered}\nFailed: {failed}\n\n"
            "Note: when SMTP isn't configured, emails are still queued "
            "by the email service stub and the broadcast is logged.",
            parent=gui_instance.root)
        subject_var.set("")
        body.delete("1.0", "end")
        on_sent()

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(4, 0))
    ttk.Button(bar, text="Preview audience", command=preview).pack(side="left")
    ttk.Button(bar, text="Send →", command=send).pack(side="right")


# ── History tab ────────────────────────────────────────────────────────

def _build_history(parent: ttk.Frame) -> None:
    cols = ("bid", "sent_at", "by", "subject", "building", "type", "count")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
    for k, lbl, w in [
        ("bid", "Broadcast ID", 130),
        ("sent_at", "Sent", 150),
        ("by", "By", 120),
        ("subject", "Subject", 320),
        ("building", "Building filter", 130),
        ("type", "Type filter", 110),
        ("count", "Recipients", 90),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    parent.tree = tree                # so _reload_history can find it
    _reload_history(parent)


def _reload_history(parent: ttk.Frame) -> None:
    tree = getattr(parent, 'tree', None)
    if tree is None:
        return
    for it in tree.get_children():
        tree.delete(it)
    try:
        conn = get_connection()
        try:
            rows = conn.execute('''
                SELECT bc.broadcast_id, bc.sent_at, bc.sent_by, bc.subject,
                       COALESCE(b.building_name, '(any)'),
                       COALESCE(bc.audience_room_type, '(any)'),
                       bc.recipient_count
                FROM housing_broadcasts bc
                LEFT JOIN housing_buildings b
                    ON b.building_id = bc.audience_building_id
                ORDER BY bc.sent_at DESC
            ''').fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load broadcast history")
        return
    for row in rows:
        tree.insert("", "end", values=row)


# ── Audience + send ────────────────────────────────────────────────────

def _resolve_audience(building_id: str | None,
                       room_type: str | None) -> list[dict]:
    sql = '''
        SELECT a.student_id,
               s.first_name || ' ' || s.last_name AS name,
               s.email_address,
               r.room_number, b.building_name
        FROM housing_assignments a
        JOIN students          s ON s.student_id  = a.student_id
        JOIN housing_rooms     r ON r.room_id     = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
        WHERE a.status = 'Active'
    '''
    args: list = []
    if building_id:
        sql += " AND b.building_id = ?"
        args.append(building_id)
    if room_type:
        sql += " AND r.room_type = ?"
        args.append(room_type)
    sql += " ORDER BY b.building_name, r.room_number"
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Audience resolve failed")
        return []


def _send_to_all(recips: list[dict], subject: str,
                  body: str) -> tuple[int, int]:
    delivered = 0
    failed = 0
    for r in recips:
        addr = (r.get('email_address') or '').strip()
        if not addr:
            failed += 1
            logger.info("Broadcast skipped: no email for %s",
                        r.get('student_id'))
            continue
        try:
            send_email(addr, subject, body)
            delivered += 1
        except Exception:
            logger.exception("Broadcast send failed for %s", addr)
            failed += 1
    return delivered, failed


# ── Helpers ────────────────────────────────────────────────────────────

def _load_buildings() -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        try:
            return [(r[0], r[1]) for r in conn.execute(
                "SELECT building_id, building_name "
                "FROM housing_buildings ORDER BY building_name")]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load buildings")
        return []


def _load_room_types() -> list[str]:
    try:
        conn = get_connection()
        try:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT room_type FROM housing_rooms "
                "WHERE room_type IS NOT NULL ORDER BY room_type")]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load room types")
        return []
