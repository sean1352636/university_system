"""Equality & Diversity Management GUI (extended).

Implements the 50-feature brief on top of the shared UserAuth context and
the main university database. See the sibling modules (schema, access,
integrations, reports_engine) for supporting logic. No login screen.
"""

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
    Button,
    Checkbutton,
    END,
    Entry,
    Frame,
    IntVar,
    Label,
    OptionMenu,
    Scrollbar,
    StringVar,
    Text,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    ttk,
)

from education_system.university_system.modules.domain.student_affairs.equality_diversity import (
    access,
    integrations,
    reports_engine,
)
from education_system.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS,
    SORTABLE_RECORD_COLUMNS,
    get_connection,
    migrate,
)

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t_real
except Exception:  # pragma: no cover
    def _t_real(key, **kw):
        return kw.get("_default", key.rsplit(".", 1)[-1].replace("_", " "))


# --- feature 47 -- i18n helper with inline defaults -------------------------
def _t(key: str, default: str, **fmt) -> str:
    try:
        val = _t_real(key, **fmt)
        if val == key or val is None:
            raise KeyError
        return val
    except Exception:
        return default.format(**fmt) if fmt else default


PERSON_TYPES = ["Student", "Staff"]
DEPARTMENTS = [
    "Computing", "Engineering", "Business", "Law", "Medicine",
    "Arts & Humanities", "Social Sciences", "Natural Sciences",
    "Education", "Administration", "Other",
]
AGE_GROUPS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+", "Prefer not to say"]
GENDERS = ["Female", "Male", "Non-binary", "Other", "Prefer not to say"]
ETHNICITIES = [
    "White - British", "White - Other", "Asian - Indian", "Asian - Pakistani",
    "Asian - Chinese", "Asian - Other", "Black - African", "Black - Caribbean",
    "Mixed", "Arab", "Other", "Prefer not to say",
]
DISABILITY_STATUS = [
    "No known disability", "Physical", "Sensory", "Mental health",
    "Learning difficulty", "Long-term health condition", "Multiple", "Prefer not to say",
]
RELIGIONS = ["Christian", "Muslim", "Hindu", "Sikh", "Jewish", "Buddhist",
             "No religion", "Other", "Prefer not to say"]
SEXUAL_ORIENTATIONS = ["Heterosexual", "Gay/Lesbian", "Bisexual", "Other", "Prefer not to say"]
INCIDENT_CATEGORIES = [
    "Racial discrimination", "Gender discrimination", "Disability discrimination",
    "Religious discrimination", "Sexual orientation discrimination",
    "Age discrimination", "Harassment", "Bullying", "Other",
]
INCIDENT_STATUS = ["Open", "Under investigation", "Resolved", "Closed"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
SLA_DAYS = {"Low": 30, "Medium": 14, "High": 5, "Critical": 1}

FIELD_OPTIONS = {
    "person_type": PERSON_TYPES,
    "department": DEPARTMENTS,
    "age_group": AGE_GROUPS,
    "gender": GENDERS,
    "ethnicity": ETHNICITIES,
    "disability": DISABILITY_STATUS,
    "religion": RELIGIONS,
    "sexual_orientation": SEXUAL_ORIENTATIONS,
}

# feature 48 — themes
THEMES = {
    "light": {"bg": "#f4f6f9", "panel": "#ffffff", "accent": "#1e3a5f",
              "text": "#1a1a1a", "muted": "#666666", "header_fg": "#ffffff"},
    "dark":  {"bg": "#1c1f24", "panel": "#262b33", "accent": "#4aa3ff",
              "text": "#eaeaea", "muted": "#aaaaaa", "header_fg": "#ffffff"},
    "high":  {"bg": "#000000", "panel": "#000000", "accent": "#ffff00",
              "text": "#ffffff", "muted": "#ffff00", "header_fg": "#000000"},
}

PAGE_SIZE = 50

# ----------------------------------------------------------------------------
#  Main application
# ----------------------------------------------------------------------------


class EqualityDiversityGUI:
    """Top-level E&D GUI."""

    def __init__(self, parent, auth_manager):
        migrate()  # feature: idempotent schema ensure
        self.auth = auth_manager
        self.principal = access.principal_from_auth(auth_manager)
        if not self.principal:
            raise PermissionError("EqualityDiversityGUI requires an authenticated user")

        # Always open in a new Toplevel when a window is passed; only reuse
        # the parent when it is a Frame (i.e. the caller wants to embed).
        if isinstance(parent, (Tk, Toplevel)):
            self.root = Toplevel(parent)
            try:
                self.root.transient(parent)
            except Exception:
                pass
        else:
            self.root = parent
        self.theme_name = "light"
        self.theme = THEMES[self.theme_name]
        # Frames have no ``wm_title`` / accept no ``geometry`` — only set
        # window chrome on Tk/Toplevel hosts. Same shape as
        # Library/Student Records (8.117.34/8.117.38).
        if hasattr(self.root, "wm_title"):
            self.root.title(
                _t("ed.window_title",
                   "E&D System — {user} ({role})",
                   user=self.principal.username, role=self.principal.role or "user"))
            self.root.geometry("1200x720")
        try:
            self.root.configure(bg=self.theme["bg"])
        except Exception:
            pass

        # feature 9 — pagination state
        self.page = 0
        self.sort_col = "id"
        self.sort_desc = True
        self.filter_query: dict = {}      # feature 5
        self.search_var = StringVar()

        self._build_header()
        self._build_tabs()
        self._bind_shortcuts()            # feature 49
        self._start_idle_check()          # feature 39
        # feature 24 — catch up on any due scheduled reports
        try:
            reports_engine.run_due_schedules()
        except Exception:
            pass

    # ---------------------------------------------------------------- theme
    def _apply_theme(self, name: str):
        self.theme_name = name
        self.theme = THEMES[name]
        self.root.configure(bg=self.theme["bg"])
        # Rebuild everything — simplest and reliable
        for child in list(self.root.winfo_children()):
            child.destroy()
        self._build_header()
        self._build_tabs()
        self._bind_shortcuts()

    # --------------------------------------------------------------- header
    def _build_header(self):
        t = self.theme
        header = Frame(self.root, bg=t["accent"], height=60)
        header.pack(fill="x")
        Label(header,
              text=_t("ed.title", "University Equality & Diversity System"),
              bg=t["accent"], fg=t["header_fg"],
              font=("Helvetica", 16, "bold")).pack(side="left", padx=20, pady=15)
        Label(header,
              text=f"{self.principal.username} · {self.principal.role or 'user'}",
              bg=t["accent"], fg=t["header_fg"],
              font=("Helvetica", 10)).pack(side="right", padx=20)
        # theme picker — feature 48
        tf = Frame(header, bg=t["accent"])
        tf.pack(side="right", padx=10)
        for name in THEMES:
            Button(tf, text=name.title(),
                   command=lambda n=name: self._apply_theme(n),
                   bg=t["panel"], fg=t["text"], relief="flat", padx=6
                   ).pack(side="left", padx=2)

    # ------------------------------------------------------------------ tabs
    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        wanted = self.principal.tabs()    # feature 37
        self.tabs: dict[str, Frame] = {}
        for name in wanted:
            f = Frame(self.notebook, bg=self.theme["panel"])
            self.notebook.add(f, text=f"  {name}  ")
            self.tabs[name] = f

        dispatch = {
            "Dashboard": self._build_dashboard_tab,   # features 30, 50, 27
            "Records": self._build_records_tab,
            "Add Record": self._build_add_tab,
            "Incidents": self._build_incidents_tab,
            "Reports": self._build_reports_tab,
            "My Data": self._build_my_data_tab,       # 43–45
            "Admin": self._build_admin_tab,           # 4, 24, 31, 40, 42, 45, 46
        }
        for name, frame in self.tabs.items():
            dispatch[name](frame)

    # ================================================================= Dashboard
    def _build_dashboard_tab(self, root):
        """features 30, 50, 27 — summary dashboard."""
        t = self.theme
        Label(root, text=_t("ed.dashboard", "Dashboard"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", padx=16, pady=(14, 4))

        dq = reports_engine.data_quality()
        comp = integrations.monitoring_completeness()
        acc = reports_engine.accommodations_uptake()

        stats = Frame(root, bg=t["panel"])
        stats.pack(fill="x", padx=16, pady=8)

        def tile(parent, title, value):
            f = Frame(parent, bg=t["accent"], padx=12, pady=10)
            f.pack(side="left", padx=6)
            Label(f, text=value, fg=t["header_fg"], bg=t["accent"],
                  font=("Helvetica", 18, "bold")).pack()
            Label(f, text=title, fg=t["header_fg"], bg=t["accent"],
                  font=("Helvetica", 9)).pack()

        tile(stats, _t("ed.total_records", "Total Records"), dq["total_records"])
        tile(stats, _t("ed.linked_identities", "Linked Identities"), dq["linked"])
        tile(stats, _t("ed.open_incidents", "Open Incidents"), dq["incidents_open"])
        tile(stats, _t("ed.coverage", "Coverage %"),
             f"{comp['coverage_pct']:.1f}%")
        tile(stats, _t("ed.accoms", "Accoms uptake %"), f"{acc['pct']:.0f}%")

        # feature 50 — per-field missingness
        Label(root, text=_t("ed.dq", "Data-quality — missing fields"),
              font=("Helvetica", 12, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", padx=16, pady=(12, 4))
        grid = Frame(root, bg=t["panel"])
        grid.pack(fill="x", padx=16)
        Label(grid, text="Field", width=22, anchor="w",
              bg=t["panel"], fg=t["text"]).grid(row=0, column=0)
        Label(grid, text="Missing", bg=t["panel"], fg=t["text"]).grid(row=0, column=1)
        Label(grid, text="% missing", bg=t["panel"], fg=t["text"]).grid(row=0, column=2)
        for i, (f, (missing, tot)) in enumerate(dq["per_field_missing"].items(), 1):
            pct = (missing / tot * 100) if tot else 0.0
            for c, v in enumerate([f, f"{missing}", f"{pct:.1f}%"]):
                Label(grid, text=v, bg=t["panel"], fg=t["text"],
                      width=22 if c == 0 else 10, anchor="w"
                      ).grid(row=i, column=c, sticky="w")

    # ================================================================= Records
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
    def _build_add_tab(self, root):
        t = self.theme
        container = Frame(root, bg=t["panel"], padx=24, pady=18)
        container.pack(fill="both", expand=True)
        Label(container, text=_t("ed.add_record", "Add monitoring record"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]
              ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        fields = [
            ("Reference Code *", "ref_code", None),
            ("Person Type *", "person_type", PERSON_TYPES),
            ("Department", "department", DEPARTMENTS),
            ("Age Group", "age_group", AGE_GROUPS),
            ("Gender", "gender", GENDERS),
            ("Ethnicity", "ethnicity", ETHNICITIES),
            ("Disability", "disability", DISABILITY_STATUS),
            ("Religion", "religion", RELIGIONS),
            ("Sexual Orientation", "sexual_orientation", SEXUAL_ORIENTATIONS),
            ("Nationality", "nationality", None),
            ("Salary (staff)", "salary", None),
            ("Accommodations", "accommodations", None),
        ]
        self.form_vars: dict[str, StringVar] = {}
        for i, (lbl, key, opts) in enumerate(fields):
            r = (i // 2) + 1
            c = (i % 2) * 2
            Label(container, text=lbl, bg=t["panel"], fg=t["text"]
                  ).grid(row=r, column=c, sticky="w", pady=6, padx=4)
            if opts:
                v = StringVar(value=opts[0])
                OptionMenu(container, v, *opts).grid(
                    row=r, column=c + 1, sticky="ew", pady=6, padx=4)
            else:
                v = StringVar()
                Entry(container, textvariable=v, width=25
                      ).grid(row=r, column=c + 1, sticky="ew", pady=6, padx=4)
            self.form_vars[key] = v
        container.columnconfigure(1, weight=1)
        container.columnconfigure(3, weight=1)

        btn = Frame(container, bg=t["panel"])
        btn.grid(row=10, column=0, columnspan=4, pady=16)
        Button(btn, text=_t("ed.save", "Save"), command=self._save_record,
               bg="#27ae60", fg="white", relief="flat", padx=16, pady=6
               ).pack(side="left", padx=4)
        Button(btn, text=_t("ed.clear", "Clear"),
               command=lambda: [v.set("") for v in self.form_vars.values()],
               bg="#6c757d", fg="white", relief="flat", padx=16, pady=6
               ).pack(side="left", padx=4)

    def _save_record(self):
        ref = self.form_vars["ref_code"].get().strip()
        ptype = self.form_vars["person_type"].get().strip()
        if not ref or not ptype:
            messagebox.showerror("Validation", "Reference code + person type required.")
            return
        # feature 3 duplicate detection
        conn = get_connection()
        try:
            dup = conn.execute(
                "SELECT id FROM ed_people WHERE ref_code=?", (ref,)
            ).fetchone()
        finally:
            conn.close()
        if dup:
            if not messagebox.askyesno(
                "Duplicate",
                f"Ref '{ref}' already exists (id {dup[0]}). "
                "Open merge dialog?"):
                return
            MergeDialog(self, dup[0], self.form_vars)
            return

        salary_raw = self.form_vars["salary"].get().strip()
        try:
            salary = float(salary_raw) if salary_raw else None
        except ValueError:
            salary = None

        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO ed_people (ref_code, person_type, department, "
                "age_group, gender, ethnicity, disability, religion, "
                "sexual_orientation, nationality, salary, accommodations, "
                "date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ref, ptype,
                 self.form_vars["department"].get(),
                 self.form_vars["age_group"].get(),
                 self.form_vars["gender"].get(),
                 self.form_vars["ethnicity"].get(),
                 self.form_vars["disability"].get(),
                 self.form_vars["religion"].get(),
                 self.form_vars["sexual_orientation"].get(),
                 self.form_vars["nationality"].get(),
                 salary,
                 self.form_vars["accommodations"].get(),
                 datetime.now().strftime("%Y-%m-%d %H:%M")),
            )
            new_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "create", "person", new_id,
                           {"ref_code": ref})
        hit = integrations.sync_link(new_id, ref)   # feature 10/29
        messagebox.showinfo(
            "Saved",
            "Record created." + (f"\nLinked to {hit['kind']} {hit.get('name','')}."
                                  if hit else ""))
        for v in self.form_vars.values():
            v.set("")
        if "Records" in self.tabs:
            self._load_records()

    # ================================================================= Incidents
    def _build_incidents_tab(self, root):
        t = self.theme
        left = Frame(root, bg=t["panel"], padx=16, pady=16)
        left.pack(side="left", fill="y")

        Label(left, text=_t("ed.report_incident", "Report an Incident"),
              font=("Helvetica", 13, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", pady=(0, 10))

        Label(left, text="Category", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_category = StringVar(value=INCIDENT_CATEGORIES[0])
        OptionMenu(left, self.inc_category, *INCIDENT_CATEGORIES
                   ).pack(fill="x", pady=(0, 8))

        Label(left, text="Department", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_dept = StringVar(value=DEPARTMENTS[0])
        OptionMenu(left, self.inc_dept, *DEPARTMENTS).pack(fill="x", pady=(0, 8))

        Label(left, text="Severity (sets SLA)",
              bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_sev = StringVar(value="Medium")
        OptionMenu(left, self.inc_sev, *SEVERITIES).pack(fill="x", pady=(0, 8))

        Label(left, text="Respondent (ref)", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_resp = StringVar()
        Entry(left, textvariable=self.inc_resp).pack(fill="x", pady=(0, 8))

        Label(left, text="Witnesses (comma-sep refs)",
              bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_wit = StringVar()
        Entry(left, textvariable=self.inc_wit).pack(fill="x", pady=(0, 8))

        Label(left, text="Description", bg=t["panel"], fg=t["text"]).pack(anchor="w")
        self.inc_desc = Text(left, width=34, height=6, font=("Helvetica", 10))
        self.inc_desc.pack(pady=(0, 8))

        self.inc_anon = IntVar(value=0)
        Checkbutton(left, text="Report anonymously",
                    variable=self.inc_anon, bg=t["panel"], fg=t["text"],
                    selectcolor=t["panel"]).pack(anchor="w")

        Button(left, text=_t("ed.submit", "Submit report"),
               command=self._save_incident,
               bg="#c0392b", fg="white",
               font=("Helvetica", 11, "bold"), relief="flat", padx=12, pady=6
               ).pack(fill="x", pady=(8, 0))

        # right panel – list + detail
        right = Frame(root, bg=t["panel"], padx=16, pady=16)
        right.pack(side="right", fill="both", expand=True)

        Label(right, text=_t("ed.reported", "Reported Incidents"),
              font=("Helvetica", 13, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", pady=(0, 8))

        cols = ("ID", "Date", "Category", "Dept", "Severity",
                "Status", "SLA due", "Assignee")
        self.inc_tree = ttk.Treeview(right, columns=cols, show="headings",
                                     height=14)
        for c in cols:
            self.inc_tree.heading(c, text=c)
            self.inc_tree.column(c, width=95, anchor="w")
        self.inc_tree.pack(fill="both", expand=True)
        self.inc_tree.bind("<Double-1>", self._open_incident_detail)

        br = Frame(right, bg=t["panel"])
        br.pack(fill="x", pady=8)
        Button(br, text="Refresh", command=self._load_incidents,
               bg="#6c757d", fg="white", relief="flat", padx=12
               ).pack(side="left", padx=4)
        if self.principal.can("update_incident"):
            Button(br, text="Update status",
                   command=self._update_incident_status,
                   bg=t["accent"], fg=t["header_fg"], relief="flat", padx=12
                   ).pack(side="left", padx=4)
            Button(br, text="Assign…", command=self._assign_incident,
                   bg="#27ae60", fg="white", relief="flat", padx=12
                   ).pack(side="left", padx=4)
            Button(br, text="Refer to safeguarding",
                   command=self._refer_incident,
                   bg="#c0392b", fg="white", relief="flat", padx=12
                   ).pack(side="left", padx=4)
        self._load_incidents()

    def _save_incident(self):
        desc = self.inc_desc.get("1.0", END).strip()
        if not desc:
            messagebox.showerror("Incident", "Description is required.")
            return
        sev = self.inc_sev.get()
        sla_due = (datetime.now() + timedelta(days=SLA_DAYS[sev])
                   ).strftime("%Y-%m-%d %H:%M")
        reporter = "anonymous" if self.inc_anon.get() else self.principal.username
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO ed_incidents (date_reported, category, department, "
                "description, status, reported_by, severity, sla_deadline, "
                "respondent, witnesses, anonymous) VALUES (?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M"),
                 self.inc_category.get(), self.inc_dept.get(), desc, reporter,
                 sev, sla_due, self.inc_resp.get().strip(),
                 self.inc_wit.get().strip(), int(bool(self.inc_anon.get()))),
            )
            inc_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        integrations.audit(reporter, "create", "incident", inc_id,
                           {"category": self.inc_category.get(), "severity": sev})
        messagebox.showinfo("Submitted", "Incident reported.")
        self.inc_desc.delete("1.0", END)
        self._load_incidents()

    def _load_incidents(self):
        for r in self.inc_tree.get_children():
            self.inc_tree.delete(r)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, date_reported, category, department, severity, "
                "status, sla_deadline, assigned_to FROM ed_incidents "
                "ORDER BY id DESC"
            ).fetchall()
        finally:
            conn.close()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for row in rows:
            tag = "overdue" if row[6] and row[6] < now and row[5] not in ("Resolved", "Closed") else ""
            self.inc_tree.insert("", END, values=row, tags=(tag,) if tag else ())
        self.inc_tree.tag_configure("overdue", background="#ffe6e6")

    def _selected_incident(self) -> int | None:
        sel = self.inc_tree.selection()
        if not sel:
            messagebox.showinfo("Incidents", "Select an incident first.")
            return None
        return int(self.inc_tree.item(sel[0])["values"][0])

    def _open_incident_detail(self, _e=None):
        iid = self._selected_incident()
        if iid is None:
            return
        access.record_view("incident", iid, self.principal.username)  # feature 42
        IncidentDetail(self, iid)

    def _update_incident_status(self):
        iid = self._selected_incident()
        if iid is None:
            return
        win = Toplevel(self.root)
        win.title("Status")
        win.configure(bg=self.theme["panel"])
        v = StringVar(value=INCIDENT_STATUS[0])
        OptionMenu(win, v, *INCIDENT_STATUS).pack(padx=14, pady=10)

        def apply():
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE ed_incidents SET status=? WHERE id=?", (v.get(), iid)
                )
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.principal.username, "status_change",
                               "incident", iid, {"status": v.get()})
            win.destroy()
            self._load_incidents()

        Button(win, text="Apply", command=apply,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=12).pack(pady=6)

    def _assign_incident(self):
        iid = self._selected_incident()
        if iid is None:
            return
        name = _prompt_string(self.root, "Assignee username:")
        if not name:
            return
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE ed_incidents SET assigned_to=? WHERE id=?", (name, iid))
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "assign", "incident", iid,
                           {"assignee": name})
        self._load_incidents()

    def _refer_incident(self):
        iid = self._selected_incident()
        if iid is None:
            return
        reason = _prompt_string(self.root, "Reason for safeguarding referral:")
        if not reason:
            return
        ok = integrations.refer_to_safeguarding(iid, self.principal.username, reason)
        messagebox.showinfo("Referral",
                            "Referred." if ok else "Safeguarding module unavailable.")

    # ================================================================= Reports
    def _build_reports_tab(self, root):
        t = self.theme
        top = Frame(root, bg=t["panel"], pady=12)
        top.pack(fill="x", padx=16)
        Label(top, text=_t("ed.reports", "Reports & Analytics"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w")
        Label(top, text=_t(
            "ed.reports_note",
            "Cells with n<5 are suppressed to protect privacy."),
              bg=t["panel"], fg=t["muted"],
              font=("Helvetica", 9, "italic")
              ).pack(anchor="w", pady=(2, 10))

        # row of quick-reports
        quick = Frame(top, bg=t["panel"])
        quick.pack(anchor="w")
        for lbl, f in [("Gender", "gender"), ("Ethnicity", "ethnicity"),
                       ("Age", "age_group"), ("Disability", "disability"),
                       ("Religion", "religion"), ("Department", "department")]:
            Button(quick, text=lbl,
                   command=lambda x=f: self._render_field_report(x),
                   bg=t["accent"], fg=t["header_fg"],
                   relief="flat", padx=10, pady=4).pack(side="left", padx=3)
        Button(quick, text="Incidents",
               command=self._render_incidents_report,
               bg=t["accent"], fg=t["header_fg"], relief="flat",
               padx=10, pady=4).pack(side="left", padx=3)

        # advanced buttons
        adv = Frame(top, bg=t["panel"])
        adv.pack(anchor="w", pady=(10, 0))
        Button(adv, text="Cross-tab…", command=self._open_crosstab,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Trends…", command=self._open_trends,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Benchmark vs baseline",
               command=self._open_benchmarks,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Pay-gap", command=self._show_pay_gap,
               bg="#27ae60", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(adv, text="Export PDF", command=self._export_last_pdf,
               bg="#1e3a5f", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)

        # Segment-by row — break the quick reports down by course /
        # year_of_study / programme_level. Pulls from columns
        # auto-synced by integrations.sync_from_students.
        seg = Frame(top, bg=t["panel"])
        seg.pack(anchor="w", pady=(10, 0))
        Label(seg, text="Segment by:",
              bg=t["panel"], fg=t["text"],
              font=("Helvetica", 9, "bold")
              ).pack(side="left", padx=(0, 6))
        for axis_label, axis in [("Course", "course"),
                                  ("Year", "year_of_study"),
                                  ("Level", "programme_level")]:
            Button(seg, text=axis_label,
                   command=lambda a=axis: self._open_segment_picker(a),
                   bg="#7c3aed", fg="white", relief="flat", padx=10
                   ).pack(side="left", padx=3)

        # Cross-domain intersections — joins ed_people against
        # attendance, disciplinary records, the risk feed, and grades
        # to surface "are we serving all students equally?" disparities.
        Label(top, text=_t("ed.intersections",
                           "Cross-domain intersections"),
              font=("Helvetica", 11, "bold"),
              bg=t["panel"], fg=t["text"]
              ).pack(anchor="w", pady=(14, 0))
        cross = Frame(top, bg=t["panel"])
        cross.pack(anchor="w", pady=(4, 0))
        Button(cross, text="Attendance × demographic",
               command=lambda: self._open_intersection('attendance'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(cross, text="Discipline × demographic",
               command=lambda: self._open_intersection('discipline'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(cross, text="Risk feed × demographic",
               command=lambda: self._open_intersection('risk'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)
        Button(cross, text="Attainment gap",
               command=lambda: self._open_intersection('attainment'),
               bg="#dc2626", fg="white", relief="flat", padx=10
               ).pack(side="left", padx=3)

        self.report_frame = Frame(root, bg=t["panel"], padx=16, pady=10)
        self.report_frame.pack(fill="both", expand=True)
        self._last_report: tuple[str, list[tuple[str, int]]] | None = None
        Label(self.report_frame,
              text=_t("ed.pick_report", "Pick a report above."),
              bg=t["panel"], fg=t["muted"],
              font=("Helvetica", 11, "italic")).pack(pady=40)

    def _clear_report(self):
        for w in self.report_frame.winfo_children():
            w.destroy()

    def _render_field_report(self, field: str):
        self._clear_report()
        data = reports_engine._field_counts(field)
        self._last_report = (f"Breakdown by {field}", data)
        _render_bar_table(self.report_frame, f"Breakdown by {field}", data,
                          self.theme,
                          drill=lambda cat: self._drill_down(field, cat))
        if reports_engine.charts_available():
            _embed_chart(self.report_frame, field, self.theme)

    def _render_incidents_report(self):
        self._clear_report()
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT category, COUNT(*) FROM ed_incidents "
                "GROUP BY category ORDER BY COUNT(*) DESC"
            ).fetchall()
        finally:
            conn.close()
        self._last_report = ("Incidents by category", rows)
        _render_bar_table(self.report_frame, "Incidents by category",
                          rows, self.theme)

    # ---- university segmentation + cross-domain intersections ----

    def _open_segment_picker(self, axis: str):
        """Pick a demographic field, then render its breakdown
        segmented by the given axis (course / year / programme_level).
        Two-step so the UI doesn't need 6×4 buttons.
        """
        win = Toplevel(self.root)
        win.title(f"Segment by {axis.replace('_', ' ').title()}")
        win.configure(bg=self.theme["panel"])
        Label(win, text=f"Pick a demographic to segment by "
                        f"{axis.replace('_', ' ')}:",
              bg=self.theme["panel"],
              fg=self.theme["text"]).pack(padx=12, pady=(10, 6))
        for label, field in [("Gender", "gender"),
                             ("Ethnicity", "ethnicity"),
                             ("Age", "age_group"),
                             ("Disability", "disability"),
                             ("Religion", "religion"),
                             ("Sexual Orientation", "sexual_orientation")]:
            Button(win, text=label,
                   command=lambda f=field, a=axis:
                       (self._render_segmented_report(f, a),
                        win.destroy()),
                   bg=self.theme["accent"],
                   fg=self.theme["header_fg"],
                   relief="flat", padx=10, pady=4
                   ).pack(fill="x", padx=12, pady=2)

    def _render_segmented_report(self, field: str, segment: str):
        self._clear_report()
        try:
            triples = reports_engine.field_by_segment(field, segment)
        except ValueError as e:
            Label(self.report_frame, text=str(e),
                  bg=self.theme["panel"],
                  fg=self.theme["danger"]).pack(pady=20)
            return
        title = (f"{field.replace('_',' ').title()} by "
                 f"{segment.replace('_',' ').title()}")
        Label(self.report_frame, text=title,
              font=("Helvetica", 12, "bold"),
              bg=self.theme["panel"],
              fg=self.theme["accent"]).pack(anchor="w", pady=(0, 8))
        if not triples:
            Label(self.report_frame,
                  text="No data — sync the roster from the Admin tab "
                       "to populate course / year on records.",
                  bg=self.theme["panel"],
                  fg=self.theme["muted"]).pack(pady=20)
            return
        # Render as a treeview with three columns for clarity.
        from tkinter import ttk as _ttk
        tree = _ttk.Treeview(self.report_frame,
                             columns=("seg", "value", "n"),
                             show="headings", height=14)
        tree.heading("seg", text=segment.replace('_', ' ').title())
        tree.heading("value", text=field.replace('_', ' ').title())
        tree.heading("n", text="Count")
        tree.column("seg", width=180)
        tree.column("value", width=180)
        tree.column("n", width=80, anchor="e")
        for s, v, n in triples:
            tree.insert("", "end", values=(s, v, n))
        tree.pack(fill="both", expand=True, pady=(0, 8))
        self._last_report = (
            title, [(f"{s} / {v}", n) for s, v, n in triples])

    def _open_intersection(self, kind: str):
        """Pick the demographic field, then render the cross-domain
        join. Lets one button drive four different analyses.
        """
        win = Toplevel(self.root)
        win.title(f"Intersection — {kind}")
        win.configure(bg=self.theme["panel"])
        Label(win, text="Break down by:",
              bg=self.theme["panel"],
              fg=self.theme["text"]).pack(padx=12, pady=(10, 6))
        for label, field in [("Gender", "gender"),
                             ("Ethnicity", "ethnicity"),
                             ("Disability", "disability"),
                             ("Age group", "age_group"),
                             ("Religion", "religion")]:
            Button(win, text=label,
                   command=lambda f=field, k=kind:
                       (self._render_intersection(k, f),
                        win.destroy()),
                   bg=self.theme["accent"],
                   fg=self.theme["header_fg"],
                   relief="flat", padx=10, pady=4
                   ).pack(fill="x", padx=12, pady=2)

    def _render_intersection(self, kind: str, field: str):
        self._clear_report()
        from tkinter import ttk as _ttk
        title_map = {
            'attendance': f"Mean attendance % by {field}",
            'discipline': f"Disciplinary rate by {field}",
            'risk':       f"Risk-feed level by {field}",
            'attainment': f"Mean grade score by {field}",
        }
        title = title_map.get(kind, f"{kind} by {field}")
        Label(self.report_frame, text=title,
              font=("Helvetica", 12, "bold"),
              bg=self.theme["panel"],
              fg=self.theme["accent"]).pack(anchor="w", pady=(0, 4))
        Label(self.report_frame,
              text="Joins ed_people → central tables. Categories with "
                   "n<5 are suppressed.",
              bg=self.theme["panel"], fg=self.theme["muted"],
              font=("Helvetica", 9, "italic")
              ).pack(anchor="w", pady=(0, 10))

        if kind == 'attendance':
            data = reports_engine.attendance_by_demographic(field)
            cols = (("cat", field, 200), ("pct", "Mean %", 100),
                    ("n", "n", 80))
            rows = [(c, f"{p:.1f}%", n) for c, p, n in data]
            self._last_report = (title, [(c, int(p)) for c, p, _n in data])
        elif kind == 'discipline':
            data = reports_engine.disciplinary_overrep(field)
            cols = (("cat", field, 200),
                    ("act", "With action", 110),
                    ("tot", "Total", 80),
                    ("rate", "Rate %", 90))
            rows = [(c, a, t, f"{r:.1f}%") for c, a, t, r in data]
            self._last_report = (title, [(c, a) for c, a, _t, _r in data])
        elif kind == 'risk':
            data = reports_engine.risk_feed_distribution(field)
            cols = (("cat", field, 200),
                    ("h", "High", 70), ("m", "Medium", 80),
                    ("l", "Low", 70), ("t", "Total", 80))
            rows = data
            self._last_report = (title,
                                 [(c, h) for c, h, _m, _l, _t in data])
        elif kind == 'attainment':
            data = reports_engine.attainment_gap(field)
            cols = (("cat", field, 200),
                    ("avg", "Mean score", 110),
                    ("n", "n", 80))
            rows = [(c, f"{m:.1f}", n) for c, m, n in data]
            self._last_report = (title,
                                 [(c, int(m)) for c, m, _n in data])
        else:
            Label(self.report_frame, text=f"Unknown intersection: {kind}",
                  bg=self.theme["panel"],
                  fg=self.theme["danger"]).pack(pady=20)
            return

        if not rows:
            Label(self.report_frame,
                  text="No data — either no rows match or the "
                       "underlying tables aren't present in this DB.",
                  bg=self.theme["panel"],
                  fg=self.theme["muted"]).pack(pady=20)
            return
        tree = _ttk.Treeview(
            self.report_frame,
            columns=tuple(c[0] for c in cols),
            show="headings", height=14)
        for cid, ctext, width in cols:
            tree.heading(cid, text=ctext)
            tree.column(cid, width=width,
                        anchor=("e" if cid != "cat" else "w"))
        for r in rows:
            tree.insert("", "end", values=r)
        tree.pack(fill="both", expand=True)

    def _open_crosstab(self):
        win = Toplevel(self.root)
        win.title("Cross-tab")
        win.configure(bg=self.theme["panel"])
        row_v = StringVar(value="gender")
        col_v = StringVar(value="department")
        OptionMenu(win, row_v, *DEMOGRAPHIC_FIELDS).grid(row=0, column=0, padx=6, pady=6)
        Label(win, text="×", bg=self.theme["panel"], fg=self.theme["text"]
              ).grid(row=0, column=1)
        OptionMenu(win, col_v, *DEMOGRAPHIC_FIELDS).grid(row=0, column=2, padx=6, pady=6)
        out = Frame(win, bg=self.theme["panel"])
        out.grid(row=1, column=0, columnspan=3, padx=6, pady=6)

        def run():
            for w in out.winfo_children():
                w.destroy()
            try:
                ct = reports_engine.cross_tab(row_v.get(), col_v.get())
            except ValueError as e:
                messagebox.showerror("Cross-tab", str(e))
                return
            Label(out, text="", bg=self.theme["panel"]
                  ).grid(row=0, column=0)
            for j, c in enumerate(ct["col_keys"], 1):
                Label(out, text=c, bg=self.theme["accent"],
                      fg=self.theme["header_fg"], padx=4
                      ).grid(row=0, column=j, sticky="ew")
            for i, r in enumerate(ct["row_keys"], 1):
                Label(out, text=r, bg=self.theme["accent"],
                      fg=self.theme["header_fg"], padx=4
                      ).grid(row=i, column=0, sticky="ew")
                for j, c in enumerate(ct["col_keys"], 1):
                    v = ct["cells"].get((r, c), 0)
                    Label(out, text=str(v) if v else "·",
                          bg=self.theme["panel"], fg=self.theme["text"],
                          borderwidth=1, relief="solid", padx=6
                          ).grid(row=i, column=j, sticky="ew")

        Button(win, text="Run", command=run,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).grid(row=2, column=0, columnspan=3, pady=6)

    def _open_trends(self):
        win = Toplevel(self.root)
        win.title("Yearly trends")
        win.configure(bg=self.theme["panel"])
        var = StringVar(value="gender")
        OptionMenu(win, var, *DEMOGRAPHIC_FIELDS).pack(padx=8, pady=8)
        tree = ttk.Treeview(win, columns=("Year", "Value", "Count"),
                            show="headings", height=12)
        for c in ("Year", "Value", "Count"):
            tree.heading(c, text=c)
        tree.pack(padx=8, pady=8, fill="both", expand=True)

        def run():
            for r in tree.get_children():
                tree.delete(r)
            for row in reports_engine.yearly_trend(var.get()):
                tree.insert("", END, values=row)

        Button(win, text="Show", command=run,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(pady=6)

    def _open_benchmarks(self):
        win = Toplevel(self.root)
        win.title("Benchmarks")
        win.configure(bg=self.theme["panel"])
        var = StringVar(value="gender")
        OptionMenu(win, var, *["gender", "ethnicity", "disability"]
                   ).pack(padx=8, pady=8)
        tree = ttk.Treeview(win, columns=("Cat", "Observed %", "Baseline %", "Δpp"),
                            show="headings", height=12)
        for c in ("Cat", "Observed %", "Baseline %", "Δpp"):
            tree.heading(c, text=c)
        tree.pack(padx=8, pady=8, fill="both", expand=True)

        def run():
            for r in tree.get_children():
                tree.delete(r)
            for cat, obs, base, delta in reports_engine.benchmark_comparison(var.get()):
                tree.insert("", END, values=(cat, f"{obs:.1f}",
                                             f"{base:.1f}", f"{delta:+.1f}"))

        Button(win, text="Compare", command=run,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(pady=6)

    def _show_pay_gap(self):
        win = Toplevel(self.root)
        win.title("Pay gap (staff)")
        win.configure(bg=self.theme["panel"])
        tree = ttk.Treeview(win, columns=("Group", "Mean salary", "N"),
                            show="headings", height=8)
        for c in ("Group", "Mean salary", "N"):
            tree.heading(c, text=c)
        tree.pack(padx=8, pady=8, fill="both", expand=True)
        for row in reports_engine.pay_gap("gender"):
            tree.insert("", END, values=(row[0], f"£{row[1]:,.0f}", row[2]))

    def _drill_down(self, field: str, value: str):
        rows = reports_engine.drill_down(field, value)
        win = Toplevel(self.root)
        win.title(f"Drill-down: {field}={value}")
        win.configure(bg=self.theme["panel"])
        tree = ttk.Treeview(
            win, columns=("ID", "Ref", "Type", "Dept", "Added"),
            show="headings", height=16)
        for c in ("ID", "Ref", "Type", "Dept", "Added"):
            tree.heading(c, text=c)
        for r in rows:
            tree.insert("", END, values=r)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _export_last_pdf(self):
        if not self._last_report:
            messagebox.showinfo("PDF", "Pick a report first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"ed_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        if not path:
            return
        title, data = self._last_report
        reports_engine.export_pdf(title, data, path)
        messagebox.showinfo("PDF", f"Saved to {path}")

    # ============================================================== My Data
    def _build_my_data_tab(self, root):
        """features 43–45 — student self-service."""
        t = self.theme
        Label(root, text=_t("ed.my_data", "Your monitoring record"),
              font=("Helvetica", 14, "bold"),
              bg=t["panel"], fg=t["accent"]
              ).pack(anchor="w", padx=16, pady=(14, 4))

        ref = str(self.principal.user_id or self.principal.username)
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM ed_people WHERE ref_code=?", (ref,)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(ed_people)")]
        finally:
            conn.close()
        data = dict(zip(cols, row)) if row else {"ref_code": ref}

        form = Frame(root, bg=t["panel"], padx=16, pady=8)
        form.pack(fill="x")
        self.my_vars: dict[str, StringVar] = {}
        for i, key in enumerate(DEMOGRAPHIC_FIELDS):
            Label(form, text=key, bg=t["panel"], fg=t["text"]
                  ).grid(row=i, column=0, sticky="w", padx=4, pady=3)
            opts = FIELD_OPTIONS.get(key)
            v = StringVar(value=str(data.get(key) or (opts[0] if opts else "")))
            self.my_vars[key] = v
            if opts:
                OptionMenu(form, v, *opts).grid(row=i, column=1, sticky="ew", padx=4)
            else:
                Entry(form, textvariable=v).grid(row=i, column=1, sticky="ew", padx=4)
        form.columnconfigure(1, weight=1)

        # feature 45 — consent flags
        consent_box = Frame(root, bg=t["panel"], padx=16, pady=4)
        consent_box.pack(fill="x")
        Label(consent_box, text=_t("ed.consent", "Consent (you can withdraw anytime)"),
              font=("Helvetica", 11, "bold"),
              bg=t["panel"], fg=t["accent"]).pack(anchor="w", pady=(6, 2))
        self.consent_vars: dict[str, IntVar] = {}
        for k in ("share_for_reports", "share_cross_system", "allow_research"):
            v = IntVar(value=1)
            self.consent_vars[k] = v
            Checkbutton(consent_box, text=k.replace("_", " ").title(),
                        variable=v, bg=t["panel"], fg=t["text"],
                        selectcolor=t["panel"]).pack(anchor="w")

        Button(root, text=_t("ed.save", "Save"), command=self._save_my_data,
               bg="#27ae60", fg="white", relief="flat", padx=16, pady=6
               ).pack(anchor="w", padx=16, pady=8)

    def _save_my_data(self):
        ref = str(self.principal.user_id or self.principal.username)
        values = {k: v.get() for k, v in self.my_vars.items()}
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = get_connection()
        try:
            exists = conn.execute(
                "SELECT id FROM ed_people WHERE ref_code=?", (ref,)).fetchone()
            if exists:
                pid = exists[0]
                sets = ", ".join(f"{k}=?" for k in values) + ", self_updated_at=?"
                conn.execute(
                    f"UPDATE ed_people SET {sets} WHERE id=?",
                    (*values.values(), now, pid),
                )
            else:
                cols = ",".join(values.keys()) + ",ref_code,person_type,date_added,self_updated_at"
                marks = ",".join("?" for _ in values) + ",?,?,?,?"
                conn.execute(
                    f"INSERT INTO ed_people ({cols}) VALUES ({marks})",
                    (*values.values(), ref, "Student", now, now),
                )
                pid = conn.execute(
                    "SELECT id FROM ed_people WHERE ref_code=?", (ref,)
                ).fetchone()[0]
            conn.execute(
                "INSERT INTO ed_consent (person_id, consent_flags, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(person_id) DO UPDATE SET "
                "consent_flags=excluded.consent_flags, updated_at=excluded.updated_at",
                (pid,
                 json.dumps({k: bool(v.get()) for k, v in self.consent_vars.items()}),
                 now),
            )
            conn.commit()
        finally:
            conn.close()
        integrations.audit(self.principal.username, "self_update", "person", ref)
        messagebox.showinfo("Saved", "Your record and consent have been updated.")

    # ================================================================= Admin
    def _build_admin_tab(self, root):
        t = self.theme
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Roster sync — auto-populate ed_people from the central
        # students/staff tables instead of re-entering demographics.
        # Lives at the front of the Admin notebook because it's the
        # action admins want first when bootstrapping the module.
        sync_tab = Frame(nb, bg=t["panel"])
        nb.add(sync_tab, text="Roster sync")
        self._build_roster_sync(sync_tab)

        # 31 — audit log viewer
        audit_tab = Frame(nb, bg=t["panel"])
        nb.add(audit_tab, text="Audit log")
        self._build_audit_viewer(audit_tab)

        # 4 + 40 — pending deletions
        del_tab = Frame(nb, bg=t["panel"])
        nb.add(del_tab, text="Pending deletions")
        self._build_deletions(del_tab)

        # 24 — scheduled reports
        sched_tab = Frame(nb, bg=t["panel"])
        nb.add(sched_tab, text="Schedules")
        self._build_schedules(sched_tab)

        # 45 — consent overview
        consent_tab = Frame(nb, bg=t["panel"])
        nb.add(consent_tab, text="Consent")
        self._build_consent_admin(consent_tab)

        # 46 — anonymous tokens
        token_tab = Frame(nb, bg=t["panel"])
        nb.add(token_tab, text="Anon tokens")
        self._build_tokens(token_tab)

        # 42 — view-log explorer
        views_tab = Frame(nb, bg=t["panel"])
        nb.add(views_tab, text="View log")
        self._build_view_log(views_tab)

        # 32/33 — GDPR
        gdpr_tab = Frame(nb, bg=t["panel"])
        nb.add(gdpr_tab, text="GDPR")
        self._build_gdpr(gdpr_tab)

    def _build_roster_sync(self, root):
        """Pull demographics + course/year from the central students
        and staff tables into ed_people. Idempotent: existing rows
        are updated in place; analyst-entered demographic values are
        preserved (we only fill blanks)."""
        t = self.theme
        Label(root, text=_t("ed.roster_sync.title",
                             "Roster sync"),
              font=("Helvetica", 13, "bold"),
              bg=t["panel"], fg=t["accent"]
              ).pack(anchor="w", padx=12, pady=(12, 4))
        Label(root,
              text=_t("ed.roster_sync.desc",
                      "Auto-populates ed_people from the central "
                      "students and staff tables. Pulls gender, age "
                      "(from DOB), course, and year_of_study where "
                      "available, then back-links student_id / "
                      "staff_id. Re-running won't overwrite "
                      "demographic values an analyst has already set "
                      "manually — it only fills blanks."),
              wraplength=720, justify="left",
              bg=t["panel"], fg=t["muted"],
              font=("Helvetica", 10)).pack(anchor="w", padx=12,
                                            pady=(0, 12))

        if not self.principal.is_admin:
            Label(root,
                  text="(admin only)",
                  bg=t["panel"], fg=t["danger"],
                  font=("Helvetica", 10, "italic")
                  ).pack(anchor="w", padx=12)
            return

        button_row = Frame(root, bg=t["panel"])
        button_row.pack(anchor="w", padx=12, pady=(0, 12))

        result_box = Frame(root, bg=t["panel"], padx=12)
        result_box.pack(fill="x", padx=12, pady=(0, 12))

        def _show(result, label):
            for w in result_box.winfo_children():
                w.destroy()
            Label(result_box, text=f"Last sync — {label}",
                  font=("Helvetica", 11, "bold"),
                  bg=t["panel"], fg=t["accent"]
                  ).pack(anchor="w", pady=(6, 4))
            for k, v in result.items():
                Label(result_box, text=f"  {k}: {v}",
                      bg=t["panel"], fg=t["text"]
                      ).pack(anchor="w")

        def _run_students():
            try:
                from education_system.university_system.modules.domain.student_affairs.equality_diversity import (  # noqa: E501
                    integrations,
                )
                r = integrations.sync_from_students()
                _show(r, "students")
            except Exception as e:
                messagebox.showerror("Roster sync",
                                      f"Sync failed:\n{e}")

        def _run_staff():
            try:
                from education_system.university_system.modules.domain.student_affairs.equality_diversity import (  # noqa: E501
                    integrations,
                )
                r = integrations.sync_from_staff()
                _show(r, "staff")
            except Exception as e:
                messagebox.showerror("Roster sync",
                                      f"Sync failed:\n{e}")

        def _run_all():
            try:
                from education_system.university_system.modules.domain.student_affairs.equality_diversity import (  # noqa: E501
                    integrations,
                )
                r = integrations.sync_all_rosters()
                _show({"created": r["total_created"],
                       "updated": r["total_updated"],
                       "students": r["students"],
                       "staff": r["staff"]}, "all rosters")
            except Exception as e:
                messagebox.showerror("Roster sync",
                                      f"Sync failed:\n{e}")

        Button(button_row, text="Sync from students",
               command=_run_students,
               bg=t["accent"], fg=t["header_fg"],
               relief="flat", padx=12, pady=6
               ).pack(side="left", padx=4)
        Button(button_row, text="Sync from staff",
               command=_run_staff,
               bg=t["accent"], fg=t["header_fg"],
               relief="flat", padx=12, pady=6
               ).pack(side="left", padx=4)
        Button(button_row, text="Sync all rosters",
               command=_run_all,
               bg="#16a34a", fg="white",
               relief="flat", padx=12, pady=6
               ).pack(side="left", padx=4)

    def _build_audit_viewer(self, root):
        tree = ttk.Treeview(
            root, columns=("ts", "actor", "action", "entity", "id", "details"),
            show="headings", height=20)
        for c in ("ts", "actor", "action", "entity", "id", "details"):
            tree.heading(c, text=c)
            tree.column(c, width=130 if c == "details" else 95, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT ts, actor, action, entity, entity_id, details "
                    "FROM ed_audit_log ORDER BY id DESC LIMIT 500"
                ).fetchall()
            finally:
                conn.close()
            for r in rows:
                tree.insert("", END, values=r)
        Button(root, text="Refresh", command=refresh,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(pady=4)
        refresh()

    def _build_deletions(self, root):
        tree = ttk.Treeview(
            root, columns=("id", "entity", "entity_id", "requested_by", "requested_at"),
            show="headings")
        for c in ("id", "entity", "entity_id", "requested_by", "requested_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            for r in access.list_pending_deletions():
                tree.insert("", END, values=r)
        refresh()

        def approve():
            sel = tree.selection()
            if not sel:
                return
            qid = int(tree.item(sel[0])["values"][0])
            result = access.approve_deletion(qid, self.principal.username)
            if not result:
                messagebox.showinfo(
                    "Approve",
                    "Cannot approve (already approved or self-approval).")
                return
            entity, entity_id, _snap = result
            if entity == "person":
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE ed_deletions SET status='hard_deleted', "
                        "hard_deleted_at=? WHERE id=?",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), qid))
                    conn.execute("DELETE FROM ed_people WHERE id=?", (entity_id,))
                    conn.commit()
                finally:
                    conn.close()
            integrations.audit(self.principal.username, "hard_delete", entity,
                               entity_id, {"queue_id": qid})
            refresh()

        def restore():
            sel = tree.selection()
            if not sel:
                return
            qid = int(tree.item(sel[0])["values"][0])
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT entity, entity_id FROM ed_deletions WHERE id=?",
                    (qid,)).fetchone()
                if row and row[0] == "person":
                    conn.execute(
                        "UPDATE ed_people SET deleted_at=NULL, deleted_by=NULL "
                        "WHERE id=?", (row[1],))
                conn.execute(
                    "UPDATE ed_deletions SET status='restored' WHERE id=?", (qid,))
                conn.commit()
            finally:
                conn.close()
            integrations.audit(self.principal.username, "restore", "person",
                               row[1] if row else None)
            refresh()

        bf = Frame(root, bg=self.theme["panel"])
        bf.pack(pady=4)
        Button(bf, text="Approve & hard-delete", command=approve,
               bg="#c0392b", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)
        Button(bf, text="Restore", command=restore,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)
        Button(bf, text="Refresh", command=refresh,
               bg="#6c757d", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)

    def _build_schedules(self, root):
        tree = ttk.Treeview(
            root, columns=("id", "name", "cadence", "field", "fmt", "next_run"),
            show="headings")
        for c in ("id", "name", "cadence", "field", "fmt", "next_run"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            for s in reports_engine.list_schedules():
                tree.insert("", END, values=(s.id, s.name, s.cadence, s.field,
                                              s.fmt, s.next_run_at))
        refresh()

        def new():
            ScheduleEditor(self, on_save=refresh)

        def run_now():
            paths = reports_engine.run_due_schedules()
            messagebox.showinfo("Schedules",
                                f"Ran {len(paths)} schedule(s).")
            refresh()

        bf = Frame(root, bg=self.theme["panel"])
        bf.pack(pady=4)
        Button(bf, text="New…", command=new,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)
        Button(bf, text="Run due now", command=run_now,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(side="left", padx=4)
        Button(bf, text="Refresh", command=refresh,
               bg="#6c757d", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)

    def _build_consent_admin(self, root):
        tree = ttk.Treeview(
            root, columns=("person_id", "flags", "updated_at"),
            show="headings")
        for c in ("person_id", "flags", "updated_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT person_id, consent_flags, updated_at FROM ed_consent "
                "ORDER BY updated_at DESC").fetchall()
        finally:
            conn.close()
        for r in rows:
            tree.insert("", END, values=r)

    def _build_tokens(self, root):
        tree = ttk.Treeview(
            root, columns=("token", "issued_by", "issued_at", "used_at"),
            show="headings")
        for c in ("token", "issued_by", "issued_at", "used_at"):
            tree.heading(c, text=c)
            tree.column(c, width=160 if c == "token" else 120)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT token, issued_by, issued_at, used_at "
                    "FROM ed_anonymous_tokens ORDER BY issued_at DESC").fetchall()
            finally:
                conn.close()
            for r in rows:
                tree.insert("", END, values=r)
        refresh()

        def issue():
            n = _prompt_string(self.root, "How many tokens to issue?")
            try:
                n = max(1, int(n or 1))
            except ValueError:
                n = 1
            tokens = []
            conn = get_connection()
            try:
                for _ in range(n):
                    tok = secrets.token_urlsafe(12)
                    tokens.append(tok)
                    conn.execute(
                        "INSERT INTO ed_anonymous_tokens (token, issued_by, issued_at) "
                        "VALUES (?, ?, ?)",
                        (tok, self.principal.username,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Tokens issued", "\n".join(tokens))
            refresh()

        Button(root, text="Issue…", command=issue,
               bg="#27ae60", fg="white", relief="flat",
               padx=10).pack(pady=4)

    def _build_view_log(self, root):
        tree = ttk.Treeview(
            root, columns=("entity", "entity_id", "viewer", "viewed_at"),
            show="headings")
        for c in ("entity", "entity_id", "viewer", "viewed_at"):
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT entity, entity_id, viewer, viewed_at "
                "FROM ed_view_log ORDER BY id DESC LIMIT 500").fetchall()
        finally:
            conn.close()
        for r in rows:
            tree.insert("", END, values=r)

    def _build_gdpr(self, root):
        Label(root, text="Subject-Access Request / Right-to-Erasure",
              bg=self.theme["panel"], fg=self.theme["accent"],
              font=("Helvetica", 12, "bold")).pack(anchor="w", padx=12, pady=8)
        ref_var = StringVar()
        entry_frame = Frame(root, bg=self.theme["panel"])
        entry_frame.pack(fill="x", padx=12)
        Label(entry_frame, text="ref_code:",
              bg=self.theme["panel"], fg=self.theme["text"]
              ).pack(side="left")
        Entry(entry_frame, textvariable=ref_var, width=30).pack(side="left", padx=6)

        def sar():
            data = integrations.sar_export(ref_var.get().strip())
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                initialfile=f"sar_{ref_var.get()}.json")
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str, indent=2)
            messagebox.showinfo("SAR", f"Saved to {path}")

        def erase():
            ref = ref_var.get().strip()
            if not ref or not messagebox.askyesno(
                    "Erase", f"Permanently erase all data for '{ref}'?"):
                return
            n = integrations.erase_person(ref, self.principal.username)
            messagebox.showinfo("Erase", f"Rows removed/updated: {n}")

        bf = Frame(root, bg=self.theme["panel"])
        bf.pack(pady=8)
        Button(bf, text="Export SAR", command=sar,
               bg=self.theme["accent"], fg=self.theme["header_fg"],
               relief="flat", padx=10).pack(side="left", padx=4)
        Button(bf, text="Right-to-erasure", command=erase,
               bg="#c0392b", fg="white", relief="flat",
               padx=10).pack(side="left", padx=4)

    # --------------------------------------------------------------- shortcuts
    def _bind_shortcuts(self):
        """feature 49 — keyboard shortcuts."""
        self.root.bind_all("<Control-n>", lambda _e: self._select_tab("Add Record"))
        self.root.bind_all("<Control-f>", lambda _e: self._select_tab("Records"))
        self.root.bind_all("<Control-e>", lambda _e: self._export_csv())
        self.root.bind_all("<Control-r>", lambda _e: self._select_tab("Reports"))
        self.root.bind_all("<Control-i>", lambda _e: self._select_tab("Incidents"))
        self.root.bind_all("<Escape>", lambda _e: self._reset_query()
                                         if "Records" in self.tabs else None)

    def _select_tab(self, name: str):
        if name in self.tabs:
            self.notebook.select(self.tabs[name])

    # --------------------------------------------------------------- idle
    def _start_idle_check(self):
        def tick():
            if self.principal.is_idle():
                messagebox.showinfo("Session", "Session timed out (inactivity).")
                try:
                    self.root.destroy()
                except Exception:
                    pass
                return
            self.root.after(30_000, tick)
        self.root.after(30_000, tick)


# ----------------------------------------------------------------------------
#  Dialogs
# ----------------------------------------------------------------------------


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


def _prompt_string(parent, prompt: str) -> str | None:
    win = Toplevel(parent)
    win.title(prompt)
    var = StringVar()
    Label(win, text=prompt).pack(padx=12, pady=(8, 2))
    Entry(win, textvariable=var, width=40).pack(padx=12, pady=4)
    result = {"value": None}

    def ok():
        result["value"] = var.get().strip()
        win.destroy()
    Button(win, text="OK", command=ok).pack(pady=6)
    win.grab_set()
    win.wait_window()
    return result["value"]


def _render_bar_table(parent, title, data, theme, drill=None):
    Label(parent, text=title, font=("Helvetica", 13, "bold"),
          bg=theme["panel"], fg=theme["accent"]
          ).pack(anchor="w", pady=(0, 10))
    if not data:
        Label(parent, text="No data.", bg=theme["panel"], fg=theme["muted"]
              ).pack(pady=12)
        return
    total = sum(r[1] for r in data) or 1
    max_count = max(r[1] for r in data)
    grid = Frame(parent, bg=theme["panel"])
    grid.pack(fill="both", expand=True)
    for j, h in enumerate(("Category", "n", "%", "bar")):
        Label(grid, text=h, bg=theme["accent"], fg=theme["header_fg"],
              padx=6).grid(row=0, column=j, sticky="ew", padx=1, pady=1)
    for i, (cat, n) in enumerate(data, 1):
        bar = "█" * max(1, int(n / max_count * 40))
        label = cat or "(blank)"
        Label(grid, text=label, bg=theme["panel"], fg=theme["text"],
              anchor="w", padx=6
              ).grid(row=i, column=0, sticky="ew")
        Label(grid, text=str(n), bg=theme["panel"],
              fg=theme["text"]).grid(row=i, column=1)
        Label(grid, text=f"{n / total * 100:.1f}%",
              bg=theme["panel"], fg=theme["text"]
              ).grid(row=i, column=2)
        lbl = Label(grid, text=bar, bg=theme["panel"],
                    fg=theme["accent"], font=("Courier", 10), anchor="w")
        lbl.grid(row=i, column=3, sticky="ew")
        if drill:
            lbl.bind("<Double-1>", lambda _e, c=label: drill(c))


def _embed_chart(parent, field, theme):
    """feature 19 — embed a matplotlib chart in the report frame."""
    try:
        import matplotlib
        matplotlib.use("TkAgg", force=False)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig = reports_engine.render_chart(field)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, pady=8)
    except Exception:
        pass


# ----------------------------------------------------------------------------
#  Public entry points
# ----------------------------------------------------------------------------


def open_equality_diversity_gui(parent, auth_manager) -> EqualityDiversityGUI:
    """Open the E&D GUI using the already-authenticated session."""
    migrate()
    if not getattr(auth_manager, "current_user", None):
        messagebox.showerror(
            "Equality & Diversity",
            "You must be logged in to access the Equality & Diversity system.")
        raise PermissionError("open_equality_diversity_gui requires an authenticated user")
    return EqualityDiversityGUI(parent, auth_manager)


def submit_anonymous_record(token: str, fields: dict) -> bool:
    """feature 46 — anonymous self-identification via pre-issued token.

    This helper has **no** auth dependency; call from a web form or a public
    kiosk. Returns True on success.
    """
    migrate()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT used_at FROM ed_anonymous_tokens WHERE token=?", (token,)
        ).fetchone()
        if not row or row[0] is not None:
            return False
        ref = f"anon-{secrets.token_hex(4)}"
        conn.execute(
            "INSERT INTO ed_people (ref_code, person_type, gender, ethnicity, "
            "disability, religion, sexual_orientation, age_group, nationality, "
            "date_added) VALUES (?, 'Student', ?, ?, ?, ?, ?, ?, ?, ?)",
            (ref,
             fields.get("gender"), fields.get("ethnicity"),
             fields.get("disability"), fields.get("religion"),
             fields.get("sexual_orientation"), fields.get("age_group"),
             fields.get("nationality"),
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.execute(
            "UPDATE ed_anonymous_tokens SET used_at=? WHERE token=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), token))
        conn.commit()
    finally:
        conn.close()
    integrations.audit("anonymous", "self_id_submit", "person", ref)
    return True
