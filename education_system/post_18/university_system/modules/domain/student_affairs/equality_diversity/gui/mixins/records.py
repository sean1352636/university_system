"""Split from equality_diversity/gui.py — assembled in package __init__.py."""
from __future__ import annotations

import csv
import json
import os
import secrets
import shutil
import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import (
    Button, Checkbutton, END, Entry, Frame, IntVar, Label, OptionMenu,
    Scrollbar, StringVar, Text, Tk, Toplevel, filedialog, messagebox, ttk,
)

from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (
    access, integrations, reports_engine,
)
from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS, SORTABLE_RECORD_COLUMNS, get_connection, migrate,
)

from .._constants import (
    PERSON_TYPES, DEPARTMENTS, AGE_GROUPS, GENDERS, ETHNICITIES,
    DISABILITY_STATUS, RELIGIONS, SEXUAL_ORIENTATIONS,
    INCIDENT_CATEGORIES, INCIDENT_STATUS, SEVERITIES, SLA_DAYS,
    FIELD_OPTIONS, THEMES, PAGE_SIZE,
)
from .._helpers import _t, _prompt_string, _render_bar_table, _embed_chart
from .._dialogs import RecordEditor, MergeDialog, IncidentDetail, ScheduleEditor


class _RecordsMixin:
    """Methods extracted from EqualityDiversityGUI (records)."""

    def _build_records_tab(self, root):
        t = self.theme
        top = Frame(root, bg=t["panel"], pady=8)
        top.pack(fill="x", padx=10)

        Label(top, text=_t("ed.search", "Search:"),
              bg=t["panel"], fg=t["text"]).pack(side="left")
        Entry(top, textvariable=self.search_var, width=26
              ).pack(side="left", padx=5)
        Button(top, text=_t("ed.search_btn", "Search"),
               command=self._do_search,
               bg=t["accent"], fg=t["header_fg"], relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(top, text=_t("ed.filters", "Filters…"),
               command=self._open_filter_builder,  # feature 5
               bg=t["accent"], fg=t["header_fg"], relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(top, text=_t("ed.saved", "Saved Searches…"),
               command=self._open_saved_searches,  # feature 6
               bg=t["accent"], fg=t["header_fg"], relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(top, text=_t("ed.reset", "Reset"), command=self._reset_query,
               bg="#6c757d", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)

        right = Frame(top, bg=t["panel"])
        right.pack(side="right")
        if self.principal.can("edit_record"):
            Button(right, text=_t("ed.edit", "Edit"), command=self._edit_selected,
                   bg=t["accent"], fg=t["header_fg"], relief="flat", padx=10
                   ).pack(side="left", padx=3)
        if self.principal.can("bulk_import"):
            Button(right, text=_t("ed.import", "Bulk Import"),
                   command=self._bulk_import,     # feature 2
                   bg="#27ae60", fg="white", relief="flat", padx=10
                   ).pack(side="left", padx=3)
        if self.principal.can("delete_record"):
            Button(right, text=_t("ed.delete", "Request Delete"),
                   command=self._delete_record_requested,
                   bg="#c0392b", fg="white", relief="flat", padx=10
                   ).pack(side="left", padx=3)
        Button(right, text=_t("ed.export", "Export CSV"),
               command=self._export_csv,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(right, text=_t("ed.cols", "Columns…"),
               command=self._open_column_chooser,  # feature 7
               bg="#6c757d", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)

        # tree
        tree_wrap = Frame(root)
        tree_wrap.pack(fill="both", expand=True, padx=10, pady=5)
        self.columns = self._load_column_prefs()
        self.tree = ttk.Treeview(tree_wrap, columns=self.columns,
                                 show="headings", height=20)
        for col in self.columns:
            self.tree.heading(col, text=col.replace("_", " ").title(),
                              command=lambda c=col: self._sort_by(c))  # feature 8
            self.tree.column(col, width=110, anchor="w")
        vsb = Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        # feature 9 — pagination bar
        nav = Frame(root, bg=t["panel"])
        nav.pack(fill="x", padx=10, pady=4)
        self.page_label = Label(nav, text="", bg=t["panel"], fg=t["text"])
        Button(nav, text="◀ Prev", command=lambda: self._change_page(-1),
               bg="#6c757d", fg="white", relief="flat", padx=10
               ).pack(side="left")
        self.page_label.pack(side="left", padx=10)
        Button(nav, text="Next ▶", command=lambda: self._change_page(1),
               bg="#6c757d", fg="white", relief="flat", padx=10
               ).pack(side="left")

        self._load_records()

    # --------- feature 7 column prefs -----------------------------------

    def _load_column_prefs(self) -> list[str]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT prefs FROM ed_column_prefs WHERE owner=?",
                (self.principal.username,),
            ).fetchone()
        finally:
            conn.close()
        if row:
            try:
                cols = json.loads(row[0])
                return [c for c in cols if c in SORTABLE_RECORD_COLUMNS]
            except Exception:
                pass
        return list(SORTABLE_RECORD_COLUMNS)

    def _save_column_prefs(self, cols: list[str]):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO ed_column_prefs (owner, prefs) VALUES (?, ?) "
                "ON CONFLICT(owner) DO UPDATE SET prefs=excluded.prefs",
                (self.principal.username, json.dumps(cols)),
            )
            conn.commit()
        finally:
            conn.close()

    def _open_column_chooser(self):
        win = Toplevel(self.root)
        win.title(_t("ed.col_chooser", "Choose columns"))
        win.configure(bg=self.theme["panel"])
        vars_: dict[str, IntVar] = {}
        for c in SORTABLE_RECORD_COLUMNS:
            v = IntVar(value=1 if c in self.columns else 0)
            vars_[c] = v
            Checkbutton(win, text=c, variable=v, bg=self.theme["panel"],
                        fg=self.theme["text"], selectcolor=self.theme["panel"]
                        ).pack(anchor="w", padx=12)

        def apply():
            chosen = [c for c, v in vars_.items() if v.get()]
            if not chosen:
                messagebox.showerror("Columns", "Pick at least one column.")
                return
            self._save_column_prefs(chosen)
            win.destroy()
            self._apply_theme(self.theme_name)  # rebuild to pick up new cols

        Button(win, text="Apply", command=apply,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=12, pady=4).pack(pady=8)

    # -------- feature 8 sort --------------------------------------------

    def _sort_by(self, col: str):
        if col not in SORTABLE_RECORD_COLUMNS:
            return
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False
        self.page = 0
        self._load_records()

    # -------- loading + pagination --------------------------------------

    def _build_where(self) -> tuple[str, list]:
        clauses = ["deleted_at IS NULL"]
        params: list = []
        s = self.search_var.get().strip()
        if s:
            clauses.append("(ref_code LIKE ? OR department LIKE ? "
                           "OR person_type LIKE ? OR ethnicity LIKE ?)")
            like = f"%{s}%"
            params += [like, like, like, like]
        for f, v in self.filter_query.items():
            if f not in DEMOGRAPHIC_FIELDS or not v:
                continue
            clauses.append(f"{f} = ?")
            params.append(v)
        return " AND ".join(clauses), params

    def _load_records(self):
        self.principal.touch()
        for r in self.tree.get_children():
            self.tree.delete(r)
        cols_sql = ", ".join(self.columns)
        where_sql, params = self._build_where()
        order = f"{self.sort_col} {'DESC' if self.sort_desc else 'ASC'}"
        conn = get_connection()
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM ed_people WHERE {where_sql}", params
            ).fetchone()[0] or 0
            offset = self.page * PAGE_SIZE
            rows = conn.execute(
                f"SELECT {cols_sql} FROM ed_people WHERE {where_sql} "
                f"ORDER BY {order} LIMIT {PAGE_SIZE} OFFSET {offset}",
                params,
            ).fetchall()
        finally:
            conn.close()
        # feature 38 — mask sensitive fields
        for row in rows:
            masked = []
            for col, val in zip(self.columns, row):
                masked.append(self.principal.mask(col, val if val is not None else ""))
            self.tree.insert("", END, values=masked)
        max_page = max((total - 1) // PAGE_SIZE, 0)
        self.page_label.configure(
            text=_t("ed.page", "Page {p}/{m} · {n} records",
                    p=self.page + 1, m=max_page + 1, n=total))

    def _change_page(self, delta: int):
        self.page = max(0, self.page + delta)
        self._load_records()

    def _do_search(self):
        self.page = 0
        self._load_records()

    def _reset_query(self):
        self.search_var.set("")
        self.filter_query = {}
        self.page = 0
        self._load_records()

    # -------- feature 5 advanced filter builder -------------------------

    def _open_filter_builder(self):
        win = Toplevel(self.root)
        win.title(_t("ed.filter_builder", "Advanced filters"))
        win.configure(bg=self.theme["panel"])
        vars_: dict[str, StringVar] = {}
        for i, f in enumerate(DEMOGRAPHIC_FIELDS):
            Label(win, text=f, bg=self.theme["panel"], fg=self.theme["text"]
                  ).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            opts = ["(any)"] + FIELD_OPTIONS.get(f, [])
            var = StringVar(value=self.filter_query.get(f) or "(any)")
            vars_[f] = var
            if len(opts) > 1:
                OptionMenu(win, var, *opts).grid(row=i, column=1, sticky="ew", padx=8)
            else:
                Entry(win, textvariable=var).grid(row=i, column=1, sticky="ew", padx=8)

        def apply():
            self.filter_query = {k: (v.get() if v.get() != "(any)" else None)
                                 for k, v in vars_.items()}
            self.page = 0
            win.destroy()
            self._load_records()

        def save_as():
            name = _prompt_string(self.root,
                                  _t("ed.save_search", "Save as name:"))
            if not name:
                return
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO ed_saved_searches (owner, name, query, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (self.principal.username, name,
                     json.dumps({k: v.get() for k, v in vars_.items()}),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                messagebox.showerror("Saved Searches", "Name already taken.")
            finally:
                conn.close()

        bf = Frame(win, bg=self.theme["panel"])
        bf.grid(row=len(DEMOGRAPHIC_FIELDS), column=0, columnspan=2, pady=8)
        Button(bf, text="Apply", command=apply,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(side="left", padx=4)
        Button(bf, text="Save as…", command=save_as,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=4)

    # -------- feature 6 saved searches -----------------------------------

    def _open_saved_searches(self):
        win = Toplevel(self.root)
        win.title(_t("ed.saved_searches", "Saved searches"))
        win.configure(bg=self.theme["panel"])
        lb = tk.Listbox(win, width=40)
        lb.pack(padx=8, pady=8)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, name, query FROM ed_saved_searches "
                "WHERE owner=? ORDER BY name",
                (self.principal.username,),
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            lb.insert(END, r[1])

        def apply():
            sel = lb.curselection()
            if not sel:
                return
            _id, _name, q = rows[sel[0]]
            try:
                data = json.loads(q)
            except Exception:
                return
            self.filter_query = {k: (v if v and v != "(any)" else None)
                                 for k, v in data.items()}
            self.page = 0
            win.destroy()
            self._load_records()

        def delete():
            sel = lb.curselection()
            if not sel:
                return
            _id = rows[sel[0]][0]
            conn2 = get_connection()
            try:
                conn2.execute("DELETE FROM ed_saved_searches WHERE id=?", (_id,))
                conn2.commit()
            finally:
                conn2.close()
            win.destroy()
            self._open_saved_searches()

        Button(win, text="Apply", command=apply,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(side="left", padx=6, pady=6)
        Button(win, text="Delete", command=delete,
               bg="#c0392b", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=6, pady=6)

    # -------- feature 1 edit ---------------------------------------------

    def _selected_record_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Records", "Select a row first.")
            return None
        try:
            return int(self.tree.item(sel[0])["values"][self.columns.index("id")])
        except (ValueError, IndexError):
            messagebox.showerror("Records", "Row is missing an ID column.")
            return None

    def _edit_selected(self):
        rid = self._selected_record_id()
        if rid is None:
            return
        if not self.principal.can("edit_record"):
            messagebox.showwarning("Access", "You don't have edit permission.")
            return
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM ed_people WHERE id=?", (rid,)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(ed_people)")]
        finally:
            conn.close()
        if not row:
            return
        data = dict(zip(cols, row))
        RecordEditor(self, rid, data)

    # -------- feature 2 bulk import --------------------------------------

    def _bulk_import(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        errors: list[str] = []
        created = 0
        duplicates: list[str] = []
        conn = get_connection()
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, 2):
                    ref = (row.get("ref_code") or "").strip()
                    ptype = (row.get("person_type") or "").strip()
                    if not ref or ptype not in PERSON_TYPES:
                        errors.append(f"line {i}: missing ref_code or bad person_type")
                        continue
                    try:
                        conn.execute(
                            "INSERT INTO ed_people (ref_code, person_type, department, "
                            "age_group, gender, ethnicity, disability, religion, "
                            "sexual_orientation, nationality, date_added) VALUES "
                            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (ref, ptype,
                             row.get("department"), row.get("age_group"),
                             row.get("gender"), row.get("ethnicity"),
                             row.get("disability"), row.get("religion"),
                             row.get("sexual_orientation"), row.get("nationality"),
                             datetime.now().strftime("%Y-%m-%d %H:%M")),
                        )
                        created += 1
                    except sqlite3.IntegrityError:
                        duplicates.append(ref)
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "bulk_import", "person",
                           None, {"created": created,
                                  "duplicates": duplicates,
                                  "errors": errors})
        messagebox.showinfo(
            "Bulk import",
            f"Created: {created}\nDuplicates skipped: {len(duplicates)}\nErrors: {len(errors)}"
            + (("\nFirst errors: " + "; ".join(errors[:5])) if errors else ""),
        )
        self._load_records()

    # -------- features 4, 40 soft-delete with two-person rule ------------

    def _delete_record_requested(self):
        rid = self._selected_record_id()
        if rid is None:
            return
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM ed_people WHERE id=?", (rid,)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(ed_people)")]
        finally:
            conn.close()
        if not row:
            return
        snapshot = json.dumps(dict(zip(cols, row)), default=str)
        # soft delete + queue for approval
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE ed_people SET deleted_at=?, deleted_by=? WHERE id=?",
                (now, self.principal.username, rid),
            )
            conn.commit()
        finally:
            conn.close()
        qid = access.request_deletion("person", rid, snapshot,
                                      self.principal.username)
        integrations.audit(self.principal.username, "soft_delete", "person", rid,
                           {"queue_id": qid})
        messagebox.showinfo(
            "Delete queued",
            f"Record soft-deleted and queued for admin approval (#{qid}). "
            "It can be restored until hard-deletion.",
        )
        self._load_records()

    # -------- export CSV -------------------------------------------------

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"ed_records_{datetime.now().strftime('%Y%m%d')}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        where, params = self._build_where()
        conn = get_connection()
        try:
            cur = conn.execute(f"SELECT * FROM ed_people WHERE {where}", params)
            rows = cur.fetchall()
            headers = [d[0] for d in cur.description]
        finally:
            conn.close()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        integrations.audit(self.principal.username, "export_csv", "person",
                           None, {"rows": len(rows), "path": path})
        messagebox.showinfo("Exported", f"{len(rows)} rows → {path}")

    # ================================================================= Add

