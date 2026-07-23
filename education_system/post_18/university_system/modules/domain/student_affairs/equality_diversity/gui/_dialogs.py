"""Helper dialog classes extracted from gui.py."""
from __future__ import annotations

import os
import secrets
import shutil
import sqlite3
import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING
from tkinter import (
    Button, Checkbutton, END, Entry, Frame, IntVar, Label, OptionMenu,
    Scrollbar, StringVar, Text, Toplevel, filedialog, messagebox, ttk,
)

from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (
    access, integrations, reports_engine,
)
from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS, get_connection,
)

from ._constants import FIELD_OPTIONS, INCIDENT_STATUS, SEVERITIES
from ._helpers import _t, _prompt_string

if TYPE_CHECKING:
    from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.gui import (
        EqualityDiversityGUI,
    )

class RecordEditor:
    """feature 1 — inline edit dialog."""

    def __init__(self, parent: EqualityDiversityGUI, record_id: int, data: dict):
        self.parent = parent
        self.record_id = record_id
        self.win = Toplevel(parent.root)
        self.win.title(f"Edit record #{record_id}")
        self.win.configure(bg=parent.theme["panel"])
        self.vars: dict[str, StringVar] = {}
        editable = ["department", "age_group", "gender", "ethnicity",
                    "disability", "religion", "sexual_orientation",
                    "nationality", "salary", "accommodations"]
        for i, k in enumerate(editable):
            Label(self.win, text=k, bg=parent.theme["panel"],
                  fg=parent.theme["text"]).grid(row=i, column=0, sticky="w",
                                                padx=6, pady=3)
            v = StringVar(value=str(data.get(k) or ""))
            self.vars[k] = v
            opts = FIELD_OPTIONS.get(k)
            if opts:
                OptionMenu(self.win, v, *opts).grid(row=i, column=1, sticky="ew", padx=6)
            else:
                Entry(self.win, textvariable=v).grid(row=i, column=1, sticky="ew", padx=6)
        Button(self.win, text="Save", command=self._save,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).grid(row=len(editable), column=0, columnspan=2, pady=8)

    def _save(self):
        vals = {k: v.get() for k, v in self.vars.items()}
        try:
            vals["salary"] = float(vals["salary"]) if vals["salary"] else None
        except ValueError:
            vals["salary"] = None
        sets = ", ".join(f"{k}=?" for k in vals) + ", updated_at=?, updated_by=?"
        conn = get_connection()
        try:
            conn.execute(
                f"UPDATE ed_people SET {sets} WHERE id=?",
                (*vals.values(),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 self.parent.principal.username, self.record_id))
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.parent.principal.username, "update", "person",
                           self.record_id, vals)
        self.win.destroy()
        self.parent._load_records()




class MergeDialog:
    """feature 3 — merge with existing duplicate."""

    def __init__(self, parent: EqualityDiversityGUI, existing_id: int,
                 new_vars: dict[str, StringVar]):
        self.parent = parent
        self.existing_id = existing_id
        self.win = Toplevel(parent.root)
        self.win.title(f"Merge into #{existing_id}")
        self.win.configure(bg=parent.theme["panel"])
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM ed_people WHERE id=?", (existing_id,)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(ed_people)")]
        finally:
            conn.close()
        old = dict(zip(cols, row))
        Label(self.win, text="Pick which value wins for each field",
              bg=parent.theme["panel"], fg=parent.theme["accent"],
              font=("Helvetica", 11, "bold")
              ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        self.choice: dict[str, StringVar] = {}
        for i, k in enumerate(DEMOGRAPHIC_FIELDS, 1):
            old_v = str(old.get(k) or "")
            new_v = new_vars.get(k, StringVar()).get()
            Label(self.win, text=k, bg=parent.theme["panel"],
                  fg=parent.theme["text"]).grid(row=i, column=0, sticky="w", padx=8)
            v = StringVar(value="new")
            self.choice[k] = v
            OptionMenu(self.win, v, "old", "new").grid(row=i, column=1, padx=6)
            Label(self.win, text=f"old={old_v!r} | new={new_v!r}",
                  bg=parent.theme["panel"], fg=parent.theme["muted"]
                  ).grid(row=i, column=2, sticky="w")
        self.old = old
        self.new_vars = new_vars
        Button(self.win, text="Merge", command=self._apply,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).grid(row=len(DEMOGRAPHIC_FIELDS) + 1, column=0,
                      columnspan=3, pady=8)

    def _apply(self):
        winners = {}
        for k, pick in self.choice.items():
            winners[k] = (self.new_vars[k].get() if pick.get() == "new"
                          else self.old.get(k))
        sets = ", ".join(f"{k}=?" for k in winners) + ", updated_at=?, updated_by=?"
        conn = get_connection()
        try:
            conn.execute(
                f"UPDATE ed_people SET {sets} WHERE id=?",
                (*winners.values(),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 self.parent.principal.username, self.existing_id))
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.parent.principal.username, "merge", "person",
                           self.existing_id, winners)
        self.win.destroy()
        messagebox.showinfo("Merge", "Merged successfully.")




class IncidentDetail:
    """features 11, 13, 17 — attachments, notes, outcomes."""

    def __init__(self, parent: EqualityDiversityGUI, incident_id: int):
        self.parent = parent
        self.iid = incident_id
        self.win = Toplevel(parent.root)
        self.win.title(f"Incident #{incident_id}")
        self.win.geometry("800x600")
        self.win.configure(bg=parent.theme["panel"])
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM ed_incidents WHERE id=?", (incident_id,)
            ).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(ed_incidents)")]
        finally:
            conn.close()
        data = dict(zip(cols, row))

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        det = Frame(nb, bg=parent.theme["panel"])
        nb.add(det, text="Details")
        for i, k in enumerate(["date_reported", "category", "department",
                               "severity", "sla_deadline", "status",
                               "reported_by", "respondent", "witnesses",
                               "assigned_to", "referred_to"]):
            Label(det, text=k, bg=parent.theme["panel"],
                  fg=parent.theme["muted"]).grid(row=i, column=0,
                                                 sticky="w", padx=6, pady=2)
            Label(det, text=str(data.get(k) or ""),
                  bg=parent.theme["panel"], fg=parent.theme["text"]
                  ).grid(row=i, column=1, sticky="w")
        Label(det, text="description", bg=parent.theme["panel"],
              fg=parent.theme["muted"]).grid(row=99, column=0,
                                             sticky="nw", padx=6, pady=4)
        Label(det, text=data.get("description") or "", wraplength=560,
              justify="left", bg=parent.theme["panel"],
              fg=parent.theme["text"]).grid(row=99, column=1, sticky="w")

        # attachments (feature 11)
        att = Frame(nb, bg=parent.theme["panel"])
        nb.add(att, text="Attachments")
        self._build_attachments(att)

        # notes (feature 13)
        notes = Frame(nb, bg=parent.theme["panel"])
        nb.add(notes, text="Investigation notes")
        self._build_notes(notes)

        # outcome (feature 17)
        out = Frame(nb, bg=parent.theme["panel"])
        nb.add(out, text="Outcome")
        self._build_outcome(out, data)

    def _build_attachments(self, root):
        tree = ttk.Treeview(
            root, columns=("id", "name", "uploaded_by", "uploaded_at"),
            show="headings", height=10)
        for c in ("id", "name", "uploaded_by", "uploaded_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=6, pady=6)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT id, file_name, uploaded_by, uploaded_at "
                    "FROM ed_incident_attachments WHERE incident_id=?",
                    (self.iid,)).fetchall()
            finally:
                conn.close()
            for r in rows:
                tree.insert("", END, values=r)
        refresh()

        def upload():
            src = filedialog.askopenfilename()
            if not src:
                return
            store = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "ed_attachments")
            os.makedirs(store, exist_ok=True)
            name = os.path.basename(src)
            dst_name = f"{self.iid}_{secrets.token_hex(4)}_{name}"
            dst = os.path.join(store, dst_name)
            shutil.copy2(src, dst)
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO ed_incident_attachments (incident_id, file_path, "
                    "file_name, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?)",
                    (self.iid, dst, name, self.parent.principal.username,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.parent.principal.username, "attach",
                               "incident", self.iid, {"name": name})
            refresh()

        Button(root, text="Upload…", command=upload,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(pady=4)

    def _build_notes(self, root):
        box = Frame(root, bg=self.parent.theme["panel"])
        box.pack(fill="both", expand=True, padx=6, pady=6)
        listing = Text(box, height=18, wrap="word")
        listing.pack(fill="both", expand=True)

        def refresh():
            listing.configure(state="normal")
            listing.delete("1.0", END)
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT ts, author, note_type, body FROM ed_incident_notes "
                    "WHERE incident_id=? ORDER BY id", (self.iid,)).fetchall()
            finally:
                conn.close()
            for ts, author, ntype, body in rows:
                listing.insert(END, f"[{ts}] {author} ({ntype or 'note'}):\n{body}\n\n")
            listing.configure(state="disabled")
        refresh()

        entry = Text(root, height=4)
        entry.pack(fill="x", padx=6)

        def add():
            body = entry.get("1.0", END).strip()
            if not body:
                return
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO ed_incident_notes (incident_id, author, ts, "
                    "note_type, body) VALUES (?, ?, ?, 'investigation', ?)",
                    (self.iid, self.parent.principal.username,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), body))
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.parent.principal.username, "note",
                               "incident", self.iid)
            entry.delete("1.0", END)
            refresh()

        Button(root, text="Add note", command=add,
               bg=self.parent.theme["accent"],
               fg=self.parent.theme["header_fg"], relief="flat",
               padx=10).pack(pady=4)

    def _build_outcome(self, root, data):
        Label(root, text="Resolution category",
              bg=self.parent.theme["panel"],
              fg=self.parent.theme["text"]).pack(anchor="w", padx=6, pady=(6, 2))
        res_var = StringVar(value=data.get("resolution_category") or "")
        Entry(root, textvariable=res_var).pack(fill="x", padx=6)
        Label(root, text="Outcome", bg=self.parent.theme["panel"],
              fg=self.parent.theme["text"]).pack(anchor="w", padx=6, pady=(6, 2))
        out_txt = Text(root, height=4)
        out_txt.pack(fill="x", padx=6)
        out_txt.insert("1.0", data.get("outcome") or "")
        Label(root, text="Lessons learned", bg=self.parent.theme["panel"],
              fg=self.parent.theme["text"]).pack(anchor="w", padx=6, pady=(6, 2))
        lessons_txt = Text(root, height=4)
        lessons_txt.pack(fill="x", padx=6)
        lessons_txt.insert("1.0", data.get("lessons_learned") or "")

        def save():
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE ed_incidents SET resolution_category=?, outcome=?, "
                    "lessons_learned=? WHERE id=?",
                    (res_var.get(),
                     out_txt.get("1.0", END).strip(),
                     lessons_txt.get("1.0", END).strip(),
                     self.iid))
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.parent.principal.username, "outcome",
                               "incident", self.iid)
            messagebox.showinfo("Saved", "Outcome recorded.")

        Button(root, text="Save outcome", command=save,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(pady=8)




class ScheduleEditor:
    """feature 24 — create a recurring report."""

    def __init__(self, parent: EqualityDiversityGUI, on_save):
        self.parent = parent
        self.on_save = on_save
        self.win = Toplevel(parent.root)
        self.win.title("New schedule")
        self.win.configure(bg=parent.theme["panel"])
        self.name = StringVar()
        self.cadence = StringVar(value="monthly")
        self.field = StringVar(value="gender")
        self.fmt = StringVar(value="pdf")
        self.out = StringVar(value=os.path.expanduser("~"))
        fields = [
            ("Name", self.name, None),
            ("Cadence", self.cadence, list(reports_engine.CADENCES)),
            ("Field", self.field, list(DEMOGRAPHIC_FIELDS)),
            ("Format", self.fmt, ["pdf", "csv"]),
            ("Output dir", self.out, None),
        ]
        for i, (lbl, v, opts) in enumerate(fields):
            Label(self.win, text=lbl, bg=parent.theme["panel"],
                  fg=parent.theme["text"]
                  ).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            if opts:
                OptionMenu(self.win, v, *opts
                           ).grid(row=i, column=1, sticky="ew", padx=6)
            else:
                Entry(self.win, textvariable=v, width=36
                      ).grid(row=i, column=1, sticky="ew", padx=6)
        Button(self.win, text="Create", command=self._save,
               bg="#27ae60", fg="white", relief="flat",
               padx=12).grid(row=len(fields), column=0, columnspan=2, pady=8)

    def _save(self):
        try:
            reports_engine.upsert_schedule(
                self.name.get().strip() or "unnamed",
                self.cadence.get(), self.field.get(), self.fmt.get(),
                self.out.get().strip(),
                self.parent.principal.username)
        except ValueError as e:
            messagebox.showerror("Schedule", str(e))
            return
        self.win.destroy()
        self.on_save()


# ----------------------------------------------------------------------------
#  Helpers
# ----------------------------------------------------------------------------


