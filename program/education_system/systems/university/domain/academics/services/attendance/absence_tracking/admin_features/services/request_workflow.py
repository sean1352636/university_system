"""RequestWorkflowService — features #8–#13.

Sliced verbatim from the original admin_features.py during the package split.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional

from ..context import AdminContext, audit, logger, safe
from ..export_email import (
    _email_admin,
    _export_rows_to_csv,
    _report_window,
    _rows_to_pdf,
    _rows_to_txt,
)
from ..support_tables import _get_setting, _set_setting
from ..ui_dialogs import (
    ModulePicker,
    Prompt,
    StudentPicker,
    _combo_dialog,
    _pick_module,
    _pick_student,
    _show_table,
    pick_date,
    pick_date_range,
)


class RequestWorkflowService:
    """Bulk approve/reject, attachments, expire, delegate, comments,
    templates."""

    def __init__(self, ctx: AdminContext, module_picker: ModulePicker
                 ) -> None:
        self.ctx = ctx
        self.module_picker = module_picker

    # --- #8 -----------------------------------------------------------
    @safe("Bulk approve")
    def bulk_approve_or_reject(self) -> None:
        mod = self.module_picker.pick(
            "Limit to module (Cancel = all modules)") or None
        action = _combo_dialog(self.ctx.parent, "Decide",
                               "Action for all pending:",
                               ["approved", "rejected"])
        if not action:
            return
        q = ("SELECT id, student_id, module_code, date, reason "
             "FROM absence_requests WHERE status='pending'")
        p: list = []
        if mod:
            q += " AND module_code=?"
            p.append(mod)
        try:
            pending = self.ctx.db.cur.execute(q, p).fetchall()
        except sqlite3.Error:
            logger.exception("pending fetch failed")
            messagebox.showerror("Error", "Could not load pending requests.",
                                 parent=self.ctx.parent)
            return
        if not pending:
            messagebox.showinfo("None", "No pending requests match.",
                                parent=self.ctx.parent)
            return
        if not Prompt.confirm(
                self.ctx.parent, "Confirm bulk decision",
                f"{action.title()} {len(pending)} request(s)?"):
            return
        try:
            for rid, sid, mc, d, reason in pending:
                self.ctx.db.update_request(rid, action)
                if action == "approved":
                    self.ctx.db.record_absence(
                        sid, mc, d, "excused",
                        f"[Bulk-approved] {reason}")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("bulk decide failed action=%s", action)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_request_decide", "absence_requests", "",
              f"action={action} n={len(pending)}")
        messagebox.showinfo("Done",
                            f"{action.title()} {len(pending)} request(s).",
                            parent=self.ctx.parent)

    # --- #9 -----------------------------------------------------------
    @safe("Attach document")
    def attach_document_to_request(self) -> None:
        rid = simpledialog.askinteger("Attachment", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        path = filedialog.askopenfilename(parent=self.ctx.parent)
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_request_attachments
                   (request_id, file_path) VALUES (?,?)""",
                (rid, str(p.resolve())))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("attachment insert failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "request_attach", "absence_requests", rid, p.name)
        messagebox.showinfo("Attached", f"Attached {p.name}.",
                            parent=self.ctx.parent)

    # --- #10 ----------------------------------------------------------
    @safe("Expire pending")
    def expire_old_pending_requests(self) -> None:
        days = simpledialog.askinteger(
            "Expire", "Expire pending older than (days)?",
            parent=self.ctx.parent, minvalue=1, maxvalue=365)
        if days is None:
            return
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        if not Prompt.confirm(
                self.ctx.parent, "Confirm",
                f"Reject every pending request older than {days} day(s)?"):
            return
        try:
            cur = self.ctx.db.cur.execute(
                """UPDATE absence_requests SET status='rejected'
                   WHERE status='pending' AND submitted_at < ?""",
                (cutoff,))
            n = cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("expire pending failed days=%s", days)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "expire_pending", "absence_requests", "",
              f"cutoff={cutoff} n={n}")
        messagebox.showinfo("Expired",
                            f"Rejected {n} stale request(s).",
                            parent=self.ctx.parent)

    # --- #11 ----------------------------------------------------------
    @safe("Delegate approval")
    def delegate_approval_authority(self) -> None:
        try:
            staff = (self.ctx.db.get_users("staff")
                     + self.ctx.db.get_users("instructor"))
        except Exception:
            logger.exception("staff list fetch failed")
            messagebox.showerror("Error", "Could not load staff.",
                                 parent=self.ctx.parent)
            return
        mapping = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in staff}
        if len(mapping) < 2:
            messagebox.showinfo("Need ≥2 staff",
                                "Not enough staff/instructor users.",
                                parent=self.ctx.parent)
            return
        src = _combo_dialog(self.ctx.parent, "Delegate from",
                            "From:", list(mapping.keys()))
        dst = _combo_dialog(self.ctx.parent, "Delegate to",
                            "To:", list(mapping.keys()))
        if not (src and dst):
            return
        if src == dst:
            messagebox.showerror("Same user",
                                 "Source and destination are the same.",
                                 parent=self.ctx.parent)
            return
        start = Prompt.iso_date(self.ctx.parent, "Start",
                                "Active from (YYYY-MM-DD):") \
            or date.today().isoformat()
        end = Prompt.iso_date(
            self.ctx.parent, "End", "Active to (YYYY-MM-DD):",
            initial=(date.today() + timedelta(days=14)).isoformat()
        ) or (date.today() + timedelta(days=14)).isoformat()
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_delegations
                   (from_user, to_user, active_from, active_to)
                   VALUES (?,?,?,?)""",
                (mapping[src], mapping[dst], start, end))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("delegation insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "delegate", "abs_tracker_delegations", "",
              f"{mapping[src]}→{mapping[dst]} {start}..{end}")
        messagebox.showinfo("Delegated",
                            f"{src} → {dst} from {start} to {end}",
                            parent=self.ctx.parent)

    # --- #12 ----------------------------------------------------------
    @safe("Request comments")
    def show_request_comment_thread(self) -> None:
        rid = simpledialog.askinteger("Comments", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT created_at, author, body
                   FROM abs_tracker_request_comments
                   WHERE request_id=? ORDER BY created_at""",
                (rid,)).fetchall()
        except sqlite3.Error:
            logger.exception("comment fetch failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load comments.",
                                 parent=self.ctx.parent)
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title(f"Comments on request {rid}")
        win.geometry("620x460")
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        for ts, author, body in rows:
            txt.insert("end", f"[{ts}] {author}:\n{body}\n\n")
        txt.config(state="disabled")
        entry = tk.Text(win, height=4)
        entry.pack(fill="x", padx=10)

        def post():
            body = entry.get("1.0", "end").strip()
            if not body:
                return
            try:
                self.ctx.db.cur.execute(
                    """INSERT INTO abs_tracker_request_comments
                       (request_id, author, body) VALUES (?,?,?)""",
                    (rid, self.ctx.username or "?", body))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("comment post failed rid=%s", rid)
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "request_comment", "absence_requests",
                  rid, body[:120])
            txt.config(state="normal")
            txt.insert("end",
                       f"[{datetime.now().isoformat(timespec='seconds')}] "
                       f"{self.ctx.username or '?'}:\n{body}\n\n")
            txt.config(state="disabled")
            entry.delete("1.0", "end")

        tk.Button(win, text="Post", command=post, bg="#2563eb", fg="white",
                  relief="flat", padx=12, pady=4).pack(pady=8)

    # --- #13 ----------------------------------------------------------
    @safe("Request templates")
    def manage_request_templates(self) -> None:
        win = tk.Toplevel(self.ctx.parent)
        win.title("Request templates")
        win.geometry("560x420")
        tree = ttk.Treeview(win, columns=("id", "name"), show="headings")
        for c, w in zip(("id", "name"), (60, 400)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            try:
                tree.delete(*tree.get_children())
                for row in self.ctx.db.cur.execute(
                        "SELECT id, name FROM abs_tracker_request_templates "
                        "ORDER BY name"):
                    tree.insert("", "end", values=row)
            except sqlite3.Error:
                logger.exception("template refresh failed")

        def add():
            name = Prompt.non_empty(win, "Template name", "Name:", min_len=1)
            if not name:
                return
            body = simpledialog.askstring("Body", "Template body:",
                                          parent=win) or ""
            try:
                self.ctx.db.cur.execute(
                    """INSERT OR REPLACE INTO abs_tracker_request_templates
                       (name, body) VALUES (?,?)""", (name, body))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("template insert failed name=%s", name)
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "template_add",
                  "abs_tracker_request_templates", "", name)
            refresh()

        def delete():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Pick a template first.",
                                    parent=win)
                return
            tid = tree.item(sel[0])["values"][0]
            try:
                self.ctx.db.cur.execute(
                    "DELETE FROM abs_tracker_request_templates WHERE id=?",
                    (tid,))
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("template delete failed tid=%s", tid)
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "template_delete",
                  "abs_tracker_request_templates", tid, "")
            refresh()

        bar = tk.Frame(win); bar.pack(fill="x", pady=5)
        tk.Button(bar, text="➕ Add", command=add, bg="#16a34a",
                  fg="white", relief="flat", padx=10
                  ).pack(side="left", padx=6)
        tk.Button(bar, text="🗑 Delete", command=delete, bg="#dc2626",
                  fg="white", relief="flat", padx=10
                  ).pack(side="left", padx=6)
        refresh()


# ===========================================================================
# PolicyService — features #14–#18
# ===========================================================================
