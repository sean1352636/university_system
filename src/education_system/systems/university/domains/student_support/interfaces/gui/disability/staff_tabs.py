"""Staff side of the Disability & Accessibility portal: the request queue and
the renewal queue.

Both go through ``domain/disability/portal`` (which checks the signed-in
user and audits every opened request); errors are shown as they are.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import messagebox, scrolledtext, ttk

from education_system.systems.university.domains.student_support.domain.disability import access, portal

logger = logging.getLogger(__name__)

TITLE = "Disability & Accessibility Services"


def _show_error(parent, exc):
    if isinstance(exc, (PermissionError, ValueError)):
        messagebox.showerror(TITLE, str(exc), parent=parent)
    else:
        logger.exception("Disability services action failed")
        messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=parent)


def _dialog(parent, title, size="560x420"):
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(size)
    win.transient(parent.winfo_toplevel())
    return win


def _open_file(path):
    import webbrowser
    from pathlib import Path
    webbrowser.open(Path(path).resolve().as_uri())


class RequestsPanel(ttk.Frame):
    """Every open request, oldest first; open one to see it and its documents."""

    COLUMNS = (("request_id", "#", 50), ("student_id", "Student", 90),
               ("student_name", "Name", 170), ("accommodation_type", "Type", 150),
               ("status", "Status", 100), ("submitted_date", "Submitted", 110),
               ("documents", "Docs", 50), ("unread", "Unread", 60))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        self._rows: dict[str, dict] = {}

        top = ttk.Frame(self)
        top.pack(fill=tk.X)
        self.stats_var = tk.StringVar()
        ttk.Label(top, textvariable=self.stats_var, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.all_var = tk.BooleanVar(value=False)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)
        ttk.Checkbutton(top, text="Show decided requests too", variable=self.all_var,
                        command=self.refresh).pack(side=tk.RIGHT, padx=8)

        # Action bar before the table so it stays visible on short screens.
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(8, 4))
        decider = access.may_decide(auth)
        for text, cmd, needs in (("Open", self.open_selected, False),
                                 ("Mark under review", self.under_review, True),
                                 ("Approve…", self.approve, True),
                                 ("Deny…", self.deny, True),
                                 ("Messages…", self.messages, False),
                                 ("Open document…", self.open_document, False)):
            btn = ttk.Button(bar, text=text, command=cmd)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            if needs and not decider:
                btn.config(state="disabled")
        if not decider:
            ttk.Label(bar, text="Deciding needs a disability adviser or accommodation approver.",
                      foreground="#555555").pack(side=tk.LEFT, padx=8)

        detail = ttk.LabelFrame(self, text="Request", padding=6)
        detail.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self.detail = scrolledtext.ScrolledText(detail, height=9, wrap=tk.WORD, state="disabled")
        self.detail.pack(fill=tk.X)

        table = ttk.Frame(self)
        table.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in self.COLUMNS], show="headings",
                                 height=10, selectmode="browse")
        for key, label, width in self.COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=tk.W)
        sb = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        self.refresh()

    # ---------------------------------------------------------------- data
    def refresh(self):
        try:
            rows = portal.queue(self.auth, include_closed=self.all_var.get())
            stats = portal.statistics(self.auth)
        except Exception as exc:
            _show_error(self, exc)
            return
        self.stats_var.set(f"Waiting: {stats['pending_requests']}    Active adjustments: "
                           f"{stats['active_accommodations']}    Ending within 30 days: "
                           f"{stats['expiring_soon']}")
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        for r in rows:
            iid = str(r["request_id"])
            self._rows[iid] = r
            self.tree.insert("", tk.END, iid=iid, values=(
                r["request_id"], r["student_id"], r.get("student_name") or "",
                r["accommodation_type"], r["status"], str(r.get("submitted_date") or "")[:10],
                r.get("documents") or 0, r.get("unread") or 0))
        self._set_detail("Open a request to see what the student asked for. Opening it is "
                         "recorded in the audit log.")

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a request first.", parent=self)
            return None
        return int(sel[0])

    def _set_detail(self, text):
        self.detail.config(state="normal")
        self.detail.delete("1.0", tk.END)
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")

    # ------------------------------------------------------------- actions
    def open_selected(self):
        rid = self._selected()
        if rid is None:
            return
        try:
            req = portal.request_detail(self.auth, rid)
        except Exception as exc:
            _show_error(self, exc)
            return
        docs = req.get("documents") or []
        lines = [
            f"Request #{req['request_id']} — {req['accommodation_type']} — {req['status']}",
            f"Student {req['student_id']}  {req.get('student_name') or ''}  "
            f"{req.get('student_email') or ''}",
            f"Submitted {req.get('submitted_date') or req.get('requested_date') or ''}",
            "",
            req.get("description") or "",
        ]
        notes = req.get("reviewer_notes") or req.get("review_notes")
        if notes:
            lines += ["", f"Reviewer notes: {notes}"]
        lines += ["", f"Documents ({len(docs)}):"] + [
            f"  • {d['filename']} ({d.get('document_type') or 'document'}, "
            f"{str(d.get('upload_date') or '')[:10]})" for d in docs]
        self._set_detail("\n".join(lines))

    def under_review(self):
        rid = self._selected()
        if rid is None:
            return
        try:
            portal.mark_under_review(self.auth, rid)
        except Exception as exc:
            _show_error(self, exc)
            return
        self.refresh()

    def approve(self):
        rid = self._selected()
        if rid is None:
            return
        win = _dialog(self, f"Approve request #{rid}", "460x300")
        form = ttk.Frame(win, padding=12)
        form.pack(fill=tk.BOTH, expand=True)
        start = tk.StringVar(value=date.today().isoformat())
        months = tk.StringVar(value="12")
        ttk.Label(form, text="Starts (YYYY-MM-DD)").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=start, width=14).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(form, text="Lasts (months)").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(form, from_=1, to=60, textvariable=months, width=6).grid(
            row=1, column=1, sticky=tk.W)
        ttk.Label(form, text="Note to the student (optional)").grid(row=2, column=0, columnspan=2,
                                                                    sticky=tk.W, pady=(8, 2))
        note = tk.Text(form, height=5, width=48, wrap=tk.WORD)
        note.grid(row=3, column=0, columnspan=2, sticky=tk.EW)

        def ok():
            try:
                acc_id = portal.approve(self.auth, rid, start_date=start.get().strip() or None,
                                        months=months.get() or 12,
                                        notes=note.get("1.0", tk.END).strip() or None)
            except Exception as exc:
                _show_error(win, exc)
                return
            win.destroy()
            messagebox.showinfo(TITLE, f"Approved. Accommodation #{acc_id} is active and has "
                                       "been passed to exams and assessments.", parent=self)
            self.refresh()

        btns = ttk.Frame(form)
        btns.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky=tk.E)
        ttk.Button(btns, text="Approve", command=ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT)

    def deny(self):
        rid = self._selected()
        if rid is None:
            return
        win = _dialog(self, f"Deny request #{rid}", "460x260")
        form = ttk.Frame(win, padding=12)
        form.pack(fill=tk.BOTH, expand=True)
        ttk.Label(form, text="Reason (sent to the student)").pack(anchor=tk.W)
        reason = tk.Text(form, height=6, width=48, wrap=tk.WORD)
        reason.pack(fill=tk.BOTH, expand=True, pady=4)

        def ok():
            try:
                portal.deny(self.auth, rid, reason.get("1.0", tk.END))
            except Exception as exc:
                _show_error(win, exc)
                return
            win.destroy()
            self.refresh()

        btns = ttk.Frame(form)
        btns.pack(anchor=tk.E, pady=(6, 0))
        ttk.Button(btns, text="Deny", command=ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT)

    def messages(self):
        rid = self._selected()
        if rid is None:
            return
        win = _dialog(self, f"Messages — request #{rid}", "620x480")
        box = scrolledtext.ScrolledText(win, wrap=tk.WORD, state="disabled", height=14)
        reply_frame = ttk.Frame(win, padding=8)
        reply_frame.pack(side=tk.BOTTOM, fill=tk.X)
        box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        reply = tk.Text(reply_frame, height=4, wrap=tk.WORD)
        reply.pack(fill=tk.X)

        def load():
            try:
                rows = portal.messages(self.auth, rid)
            except Exception as exc:
                _show_error(win, exc)
                return False
            box.config(state="normal")
            box.delete("1.0", tk.END)
            for m in rows or []:
                who = "Student" if m["sender_type"] == "student" else f"Staff ({m['sender_id']})"
                box.insert(tk.END, f"[{m['sent_date']}] {who}:\n{m['message']}\n\n")
            if not rows:
                box.insert(tk.END, "No messages yet.")
            box.config(state="disabled")
            return True

        def send():
            try:
                portal.send_message(self.auth, rid, reply.get("1.0", tk.END))
            except Exception as exc:
                _show_error(win, exc)
                return
            reply.delete("1.0", tk.END)
            load()

        btns = ttk.Frame(reply_frame)
        btns.pack(anchor=tk.E, pady=(6, 0))
        ttk.Button(btns, text="Send to student", command=send).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.LEFT)
        if not load():
            win.destroy()
            return
        win.bind("<Destroy>", lambda e: self.refresh() if e.widget is win else None, add="+")

    def open_document(self):
        rid = self._selected()
        if rid is None:
            return
        try:
            docs = portal.request_detail(self.auth, rid).get("documents") or []
        except Exception as exc:
            _show_error(self, exc)
            return
        if not docs:
            messagebox.showinfo(TITLE, "The student hasn't uploaded any documents.", parent=self)
            return
        win = _dialog(self, f"Documents — request #{rid}", "520x300")
        lb = tk.Listbox(win, height=10)
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for d in docs:
            lb.insert(tk.END, f"{d['filename']} — {d.get('document_type') or ''} "
                              f"({str(d.get('upload_date') or '')[:10]})")

        def open_it():
            sel = lb.curselection()
            if not sel:
                return
            try:
                _open_file(portal.document_path(self.auth, rid, docs[sel[0]]["doc_id"]))
            except Exception as exc:
                _show_error(win, exc)

        ttk.Button(win, text="Open", command=open_it).pack(side=tk.LEFT, padx=8, pady=(0, 8))
        ttk.Button(win, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=8,
                                                                pady=(0, 8))


class RenewalsPanel(ttk.Frame):
    """Renewal requests waiting for a decision."""

    COLUMNS = (("renewal_id", "#", 50), ("student_id", "Student", 90),
               ("accommodation_type", "Adjustment", 170), ("expiration_date", "Ends", 100),
               ("renewal_request_date", "Asked", 110), ("notes", "Student's note", 320))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))
        decider = access.may_decide(auth)
        self.months = tk.StringVar(value="12")
        ttk.Label(bar, text="Extend by (months)").pack(side=tk.LEFT)
        ttk.Spinbox(bar, from_=1, to=60, textvariable=self.months, width=5).pack(
            side=tk.LEFT, padx=(4, 10))
        for text, cmd in (("Approve renewal", lambda: self.decide(True)),
                          ("Deny renewal…", lambda: self.decide(False))):
            btn = ttk.Button(bar, text=text, command=cmd)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            if not decider:
                btn.config(state="disabled")
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)

        table = ttk.Frame(self)
        table.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in self.COLUMNS], show="headings",
                                 selectmode="browse")
        for key, label, width in self.COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=tk.W)
        sb = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.refresh()

    def refresh(self):
        try:
            rows = portal.pending_renewals(self.auth)
        except Exception as exc:
            _show_error(self, exc)
            return
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", tk.END, iid=str(r["renewal_id"]), values=(
                r["renewal_id"], r["student_id"], r["accommodation_type"],
                r.get("expiration_date") or "No end date",
                str(r.get("renewal_request_date") or "")[:10], r.get("notes") or ""))

    def decide(self, approve_it):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a renewal first.", parent=self)
            return
        notes = None
        if not approve_it:
            from tkinter import simpledialog
            notes = simpledialog.askstring(TITLE, "Reason (sent to the student):", parent=self)
            if notes is None:
                return
        try:
            portal.decide_renewal(self.auth, int(sel[0]), approve_it, notes,
                                  months=self.months.get() or 12)
        except Exception as exc:
            _show_error(self, exc)
            return
        self.refresh()
