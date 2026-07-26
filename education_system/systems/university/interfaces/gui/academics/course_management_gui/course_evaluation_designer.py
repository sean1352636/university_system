"""
Course Evaluation Survey Designer GUI.

Single Tk window with six tabs implementing features 1-8 from the
course-evaluation roadmap:

  • Library         — pre-built templates, clone / export
  • Question Bank   — reusable questions with tags
  • Designer        — question types, required toggle, branching rules
  • Locales         — per-language translations with fallback
  • Accessibility   — WCAG-flavoured static audit
  • Versions        — snapshot history + unified diff
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.evaluation import (
    analytics,
    authoring,
    respondent,
    scheduling,
)
from education_system.systems.university.domain.academics.services.evaluation.db_schema import (
    initialize_evaluation_database,
)


# Window-sizing convention used elsewhere in the codebase (Finance/Library):
# 1400x900 with minsize(1200, 800) — never zoomed/fullscreen.
_WINDOW_W, _WINDOW_H = 1400, 900
_MIN_W, _MIN_H = 1200, 800


class SurveyDesignerGUI:
    def __init__(self, parent, auth=None):
        initialize_evaluation_database()
        self.auth = auth
        self.user = self._user_id(auth)
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Course Evaluation — Survey Designer")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{_WINDOW_W}x{_WINDOW_H}+{(sw - _WINDOW_W)//2}+{(sh - _WINDOW_H)//2}")
        self.root.minsize(_MIN_W, _MIN_H)
        self.root.configure(bg="#f0f0f0")

        self.selected_template_id: int | None = None

        self._build()

    # ---- header ----
    @staticmethod
    def _user_id(auth) -> str:
        if not auth:
            return "system"
        u = getattr(auth, "current_user", None)
        if isinstance(u, dict):
            return u.get("username", "system")
        return str(u) if u else "system"

    def _build(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="Survey Designer",
                  font=("TkDefaultFont", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text="  Template:").pack(side=tk.LEFT)
        self.template_combo = ttk.Combobox(header, state="readonly", width=50)
        self.template_combo.pack(side=tk.LEFT, padx=6)
        self.template_combo.bind("<<ComboboxSelected>>", self._on_template_change)
        ttk.Button(header, text="Refresh", command=self._refresh_templates).pack(side=tk.LEFT, padx=2)
        ttk.Label(header, text="  Evaluation:").pack(side=tk.LEFT, padx=(12, 0))
        self.eval_combo = ttk.Combobox(header, state="readonly", width=40)
        self.eval_combo.pack(side=tk.LEFT, padx=4)
        self.eval_combo.bind("<<ComboboxSelected>>", self._on_eval_change)
        self.selected_evaluation_id: int | None = None
        self._evaluations_cache: list[dict] = []

        self.nb = ttk.Notebook(outer)
        self.nb.pack(fill=tk.BOTH, expand=True)
        self._build_library_tab()
        self._build_bank_tab()
        self._build_designer_tab()
        self._build_locales_tab()
        self._build_a11y_tab()
        self._build_versions_tab()
        self._build_distribution_tab()
        self._build_respondent_tab()
        self._build_analytics_tab()

        self._refresh_templates()

    # ------------------------------------------------------------ Library
    def _build_library_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="1. Library")

        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, pady=4)
        ttk.Button(actions, text="Clone Template…", command=self._clone_template).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Export to JSON…", command=self._export_template).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Snapshot Current Version",
                   command=self._snapshot_version).pack(side=tk.LEFT, padx=4)

        cols = ("id", "name", "type", "description", "created_by", "created_at")
        self.lib_tree = ttk.Treeview(tab, columns=cols, show="headings", height=22)
        for c, w in zip(cols, (50, 220, 110, 380, 120, 160)):
            self.lib_tree.heading(c, text=c.replace("_", " ").title())
            self.lib_tree.column(c, width=w, anchor=tk.W)
        self.lib_tree.pack(fill=tk.BOTH, expand=True, pady=6)
        self.lib_tree.bind("<<TreeviewSelect>>", self._on_library_select)

    def _on_library_select(self, _event=None):
        sel = self.lib_tree.selection()
        if not sel:
            return
        tid = int(self.lib_tree.item(sel[0])["values"][0])
        self.selected_template_id = tid
        # Sync the combobox without re-firing event
        for i, t in enumerate(self._templates_cache):
            if t["template_id"] == tid:
                self.template_combo.current(i)
                break
        self._on_template_change()

    def _clone_template(self):
        if not self.selected_template_id:
            messagebox.showinfo("Clone", "Select a template first.")
            return
        new_name = _ask_string(self.root, "Clone Template", "New template name:")
        if not new_name:
            return
        nid = authoring.clone_template(self.selected_template_id, new_name, created_by=self.user)
        messagebox.showinfo("Clone", f"Created template #{nid}.")
        self._refresh_templates()

    def _export_template(self):
        if not self.selected_template_id:
            messagebox.showinfo("Export", "Select a template first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(authoring.export_template(self.selected_template_id))
        messagebox.showinfo("Export", f"Wrote {path}.")

    # ------------------------------------------------------------ Bank
    def _build_bank_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="2. Question Bank")

        top = ttk.LabelFrame(tab, text="Filter", padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Search:").grid(row=0, column=0, sticky=tk.W)
        self.bank_search = ttk.Entry(top, width=30)
        self.bank_search.grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Tag:").grid(row=0, column=2, sticky=tk.W, padx=(8, 0))
        self.bank_tag = ttk.Entry(top, width=15)
        self.bank_tag.grid(row=0, column=3, padx=4)
        ttk.Label(top, text="Dept:").grid(row=0, column=4, sticky=tk.W, padx=(8, 0))
        self.bank_dept = ttk.Entry(top, width=15)
        self.bank_dept.grid(row=0, column=5, padx=4)
        ttk.Button(top, text="Search", command=self._refresh_bank).grid(row=0, column=6, padx=6)
        ttk.Button(top, text="New Question…", command=self._new_bank_question).grid(row=0, column=7)
        ttk.Button(top, text="Add to Current Template",
                   command=self._add_bank_to_template).grid(row=0, column=8, padx=6)

        cols = ("id", "text", "type", "category", "department", "tags")
        self.bank_tree = ttk.Treeview(tab, columns=cols, show="headings", height=22)
        for c, w in zip(cols, (50, 460, 100, 130, 120, 220)):
            self.bank_tree.heading(c, text=c.title())
            self.bank_tree.column(c, width=w, anchor=tk.W)
        self.bank_tree.pack(fill=tk.BOTH, expand=True, pady=6)

    def _refresh_bank(self):
        for i in self.bank_tree.get_children():
            self.bank_tree.delete(i)
        rows = authoring.list_bank(
            tag=self.bank_tag.get().strip() or None,
            department=self.bank_dept.get().strip() or None,
            search=self.bank_search.get().strip() or None,
        )
        for r in rows:
            tags = ", ".join(authoring.get_bank_tags(r["bank_id"]))
            self.bank_tree.insert("", tk.END, values=(
                r["bank_id"], r["question_text"], r["question_type"],
                r.get("question_category") or "", r.get("department") or "", tags,
            ))

    def _new_bank_question(self):
        dlg = _NewBankDialog(self.root)
        self.root.wait_window(dlg.top)
        if dlg.result:
            authoring.add_bank_question(created_by=self.user, **dlg.result)
            self._refresh_bank()

    def _add_bank_to_template(self):
        if not self.selected_template_id:
            messagebox.showinfo("Add", "Pick a template in the header first.")
            return
        sel = self.bank_tree.selection()
        if not sel:
            messagebox.showinfo("Add", "Select a bank question first.")
            return
        bank_id = int(self.bank_tree.item(sel[0])["values"][0])
        authoring.insert_bank_question_into_template(bank_id, self.selected_template_id)
        messagebox.showinfo("Add", "Question copied into the template.")
        self._refresh_questions()

    # ------------------------------------------------------------ Designer
    def _build_designer_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="3. Designer")

        left = ttk.Frame(tab)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.LabelFrame(tab, text="Edit Question", padding=8)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))

        cols = ("id", "order", "text", "type", "required", "branch")
        self.q_tree = ttk.Treeview(left, columns=cols, show="headings", height=24)
        for c, w in zip(cols, (50, 60, 460, 100, 80, 220)):
            self.q_tree.heading(c, text=c.title())
            self.q_tree.column(c, width=w, anchor=tk.W)
        self.q_tree.pack(fill=tk.BOTH, expand=True)
        self.q_tree.bind("<<TreeviewSelect>>", self._on_question_select)

        # --- right panel
        ttk.Label(right, text="Type:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.q_type = ttk.Combobox(right, state="readonly",
                                   values=list(authoring.SUPPORTED_TYPES), width=18)
        self.q_type.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(right, text="Scale min/max:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.q_min = ttk.Spinbox(right, from_=0, to=100, width=5)
        self.q_min.grid(row=1, column=1, sticky=tk.W, pady=2)
        self.q_max = ttk.Spinbox(right, from_=0, to=100, width=5)
        self.q_max.grid(row=1, column=1, sticky=tk.E, pady=2)

        ttk.Label(right, text="Options (one/line):").grid(row=2, column=0, sticky=tk.NW, pady=2)
        self.q_options = tk.Text(right, width=28, height=6)
        self.q_options.grid(row=2, column=1, sticky=tk.W, pady=2)

        self.q_required = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Required", variable=self.q_required).grid(
            row=3, column=1, sticky=tk.W, pady=4)

        ttk.Button(right, text="Save Type / Required",
                   command=self._save_question).grid(row=4, column=0, columnspan=2,
                                                      sticky=tk.EW, pady=(8, 4))

        ttk.Separator(right).grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=8)
        ttk.Label(right, text="Branching — show this question only if:",
                  font=("TkDefaultFont", 9, "bold")).grid(row=6, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(right, text="Parent Q ID:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.b_parent = ttk.Entry(right, width=10)
        self.b_parent.grid(row=7, column=1, sticky=tk.W, pady=2)
        ttk.Label(right, text="Operator:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.b_op = ttk.Combobox(right, state="readonly",
                                 values=list(authoring.SUPPORTED_OPS), width=8)
        self.b_op.grid(row=8, column=1, sticky=tk.W, pady=2)
        ttk.Label(right, text="Value:").grid(row=9, column=0, sticky=tk.W, pady=2)
        self.b_val = ttk.Entry(right, width=18)
        self.b_val.grid(row=9, column=1, sticky=tk.W, pady=2)
        ttk.Button(right, text="Set Branching",
                   command=self._save_branching).grid(row=10, column=0, columnspan=2,
                                                       sticky=tk.EW, pady=(6, 2))
        ttk.Button(right, text="Clear Branching",
                   command=self._clear_branching).grid(row=11, column=0, columnspan=2, sticky=tk.EW)

    def _on_question_select(self, _event=None):
        q = self._current_question()
        if not q:
            return
        self.q_type.set(q.get("question_type", "likert"))
        self.q_min.delete(0, tk.END); self.q_min.insert(0, q.get("scale_min", 1))
        self.q_max.delete(0, tk.END); self.q_max.insert(0, q.get("scale_max", 5))
        self.q_options.delete("1.0", tk.END)
        try:
            opts = json.loads(q.get("options_json") or "[]")
        except json.JSONDecodeError:
            opts = []
        self.q_options.insert("1.0", "\n".join(str(o) for o in opts))
        self.q_required.set(bool(q.get("is_required", 1)))
        self.b_parent.delete(0, tk.END)
        if q.get("parent_question_id"):
            self.b_parent.insert(0, str(q["parent_question_id"]))
        self.b_op.set(q.get("show_if_op") or "")
        self.b_val.delete(0, tk.END)
        self.b_val.insert(0, q.get("show_if_value") or "")

    def _save_question(self):
        q = self._current_question()
        if not q:
            return
        qid = q["question_id"]
        opts_raw = [ln.strip() for ln in self.q_options.get("1.0", tk.END).splitlines() if ln.strip()]
        try:
            authoring.set_question_type(
                qid, self.q_type.get() or "likert",
                options=opts_raw or None,
                scale_min=int(self.q_min.get() or 1),
                scale_max=int(self.q_max.get() or 5),
            )
            authoring.set_required(qid, self.q_required.get())
        except ValueError as e:
            messagebox.showerror("Save", str(e))
            return
        self._refresh_questions()

    def _save_branching(self):
        q = self._current_question()
        if not q:
            return
        try:
            authoring.set_branching(
                q["question_id"],
                int(self.b_parent.get()),
                self.b_op.get() or "eq",
                self.b_val.get(),
            )
        except (ValueError, TypeError) as e:
            messagebox.showerror("Branching", str(e))
            return
        self._refresh_questions()

    def _clear_branching(self):
        q = self._current_question()
        if not q:
            return
        authoring.clear_branching(q["question_id"])
        self._refresh_questions()

    # ------------------------------------------------------------ Locales
    def _build_locales_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="4. Locales")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X, pady=4)
        ttk.Label(top, text="Question (designer selection):").pack(side=tk.LEFT)
        self.loc_qid_lbl = ttk.Label(top, text="—", font=("TkDefaultFont", 10, "bold"))
        self.loc_qid_lbl.pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Reload", command=self._refresh_locales).pack(side=tk.LEFT, padx=6)

        editor = ttk.LabelFrame(tab, text="Add / Update translation", padding=8)
        editor.pack(fill=tk.X, pady=6)
        ttk.Label(editor, text="Locale (e.g. fr, es, zh):").grid(row=0, column=0, sticky=tk.W)
        self.loc_code = ttk.Entry(editor, width=8); self.loc_code.grid(row=0, column=1, sticky=tk.W)
        ttk.Label(editor, text="Translated text:").grid(row=1, column=0, sticky=tk.NW, pady=4)
        self.loc_text = tk.Text(editor, height=3, width=90)
        self.loc_text.grid(row=1, column=1, sticky=tk.W, pady=4)
        ttk.Label(editor, text="Aria-label (optional):").grid(row=2, column=0, sticky=tk.W)
        self.loc_aria = ttk.Entry(editor, width=90); self.loc_aria.grid(row=2, column=1, sticky=tk.W)
        ttk.Button(editor, text="Save translation",
                   command=self._save_locale).grid(row=3, column=1, sticky=tk.E, pady=6)

        cols = ("locale", "text", "aria")
        self.loc_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (80, 700, 300)):
            self.loc_tree.heading(c, text=c.title())
            self.loc_tree.column(c, width=w, anchor=tk.W)
        self.loc_tree.pack(fill=tk.BOTH, expand=True)

    def _refresh_locales(self):
        for i in self.loc_tree.get_children():
            self.loc_tree.delete(i)
        q = self._current_question()
        if not q:
            self.loc_qid_lbl.config(text="—  (select a question in tab 3)")
            return
        self.loc_qid_lbl.config(text=f"#{q['question_id']} · {q['question_text'][:80]}")
        for code, d in authoring.get_locales(q["question_id"]).items():
            self.loc_tree.insert("", tk.END,
                                 values=(code, d["question_text"], d.get("aria_label") or ""))

    def _save_locale(self):
        q = self._current_question()
        if not q:
            messagebox.showinfo("Locale", "Pick a question in the Designer tab first.")
            return
        code = self.loc_code.get().strip().lower()
        text = self.loc_text.get("1.0", tk.END).strip()
        if not code or not text:
            messagebox.showinfo("Locale", "Locale code and text are required.")
            return
        authoring.set_locale_text(q["question_id"], code, text,
                                  aria_label=self.loc_aria.get().strip() or None)
        self._refresh_locales()

    # ------------------------------------------------------------ A11y
    def _build_a11y_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="5. Accessibility")

        controls = ttk.Frame(tab)
        controls.pack(fill=tk.X, pady=4)
        ttk.Label(controls, text="FG color:").pack(side=tk.LEFT)
        self.a_fg = ttk.Entry(controls, width=10); self.a_fg.insert(0, "#000000"); self.a_fg.pack(side=tk.LEFT, padx=4)
        ttk.Label(controls, text="BG color:").pack(side=tk.LEFT)
        self.a_bg = ttk.Entry(controls, width=10); self.a_bg.insert(0, "#f0f0f0"); self.a_bg.pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Run Audit", command=self._run_audit).pack(side=tk.LEFT, padx=8)
        self.a_summary = ttk.Label(controls, text="No audit run yet.")
        self.a_summary.pack(side=tk.LEFT, padx=12)

        cols = ("severity", "rule", "qid", "message")
        self.a_tree = ttk.Treeview(tab, columns=cols, show="headings", height=22)
        for c, w in zip(cols, (90, 180, 60, 800)):
            self.a_tree.heading(c, text=c.title())
            self.a_tree.column(c, width=w, anchor=tk.W)
        self.a_tree.pack(fill=tk.BOTH, expand=True, pady=6)

    def _run_audit(self):
        if not self.selected_template_id:
            messagebox.showinfo("Audit", "Select a template first.")
            return
        findings = authoring.audit_template(
            self.selected_template_id,
            fg=self.a_fg.get().strip() or "#000000",
            bg=self.a_bg.get().strip() or "#f0f0f0",
        )
        for i in self.a_tree.get_children():
            self.a_tree.delete(i)
        for f in findings:
            self.a_tree.insert("", tk.END, values=(f["severity"], f["rule"],
                                                    f.get("question_id") or "",
                                                    f["message"]))
        errors = sum(1 for f in findings if f["severity"] == "error")
        warns = sum(1 for f in findings if f["severity"] == "warning")
        ratio = authoring.contrast_ratio(self.a_fg.get() or "#000000",
                                          self.a_bg.get() or "#f0f0f0")
        self.a_summary.config(
            text=f"{len(findings)} findings  ·  {errors} errors  ·  {warns} warnings  ·  contrast {ratio:.2f}:1"
        )

    # ------------------------------------------------------------ Versions
    def _build_versions_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="6. Versions")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=4)
        ttk.Button(top, text="Snapshot Now…", command=self._snapshot_version).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Diff Selected (2)", command=self._diff_versions).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Refresh", command=self._refresh_versions).pack(side=tk.LEFT, padx=4)

        cols = ("version_id", "version_number", "changed_by", "changed_at", "summary")
        self.v_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12, selectmode="extended")
        for c, w in zip(cols, (90, 100, 140, 180, 700)):
            self.v_tree.heading(c, text=c.replace("_", " ").title())
            self.v_tree.column(c, width=w, anchor=tk.W)
        self.v_tree.pack(fill=tk.X, pady=4)

        self.v_diff = scrolledtext.ScrolledText(tab, height=22, font=("TkFixedFont", 9))
        self.v_diff.pack(fill=tk.BOTH, expand=True, pady=4)

    def _snapshot_version(self):
        if not self.selected_template_id:
            messagebox.showinfo("Snapshot", "Select a template first.")
            return
        summary = _ask_string(self.root, "Snapshot", "Change summary (optional):") or ""
        vid = authoring.save_version(self.selected_template_id,
                                     change_summary=summary, changed_by=self.user)
        messagebox.showinfo("Snapshot", f"Saved version (id {vid}).")
        self._refresh_versions()

    def _diff_versions(self):
        sel = self.v_tree.selection()
        if len(sel) != 2:
            messagebox.showinfo("Diff", "Select exactly two versions.")
            return
        a, b = (int(self.v_tree.item(s)["values"][0]) for s in sel)
        try:
            text = authoring.diff_versions(a, b)
        except ValueError as e:
            messagebox.showerror("Diff", str(e)); return
        self.v_diff.delete("1.0", tk.END)
        self.v_diff.insert("1.0", text or "(no differences)")

    def _refresh_versions(self):
        for i in self.v_tree.get_children():
            self.v_tree.delete(i)
        if not self.selected_template_id:
            return
        for v in authoring.list_versions(self.selected_template_id):
            self.v_tree.insert("", tk.END, values=(
                v["version_id"], v["version_number"],
                v.get("changed_by") or "", v.get("changed_at") or "",
                v.get("change_summary") or "",
            ))

    # ------------------------------------------------------------ helpers
    def _refresh_templates(self):
        self._templates_cache = authoring.list_templates()
        labels = [f"#{t['template_id']}  {t['template_name']}  [{t['template_type']}]"
                  for t in self._templates_cache]
        self.template_combo["values"] = labels
        if self._templates_cache:
            keep = self.selected_template_id
            idx = 0
            if keep is not None:
                for i, t in enumerate(self._templates_cache):
                    if t["template_id"] == keep:
                        idx = i
                        break
            self.template_combo.current(idx)
            self.selected_template_id = self._templates_cache[idx]["template_id"]
        else:
            self.selected_template_id = None
            self.template_combo.set("")

        # Library tab
        for i in self.lib_tree.get_children():
            self.lib_tree.delete(i)
        for t in self._templates_cache:
            self.lib_tree.insert("", tk.END, values=(
                t["template_id"], t["template_name"], t["template_type"],
                (t.get("description") or "")[:120],
                t.get("created_by") or "", t.get("created_at") or "",
            ))

        self._refresh_bank()
        self._refresh_questions()
        self._refresh_locales()
        self._refresh_versions()
        self._refresh_evaluations()

    def _on_template_change(self, _event=None):
        idx = self.template_combo.current()
        if 0 <= idx < len(self._templates_cache):
            self.selected_template_id = self._templates_cache[idx]["template_id"]
            self._refresh_questions()
            self._refresh_locales()
            self._refresh_versions()

    def _refresh_questions(self):
        for i in self.q_tree.get_children():
            self.q_tree.delete(i)
        if not self.selected_template_id:
            return
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluation_questions WHERE template_id=? ORDER BY display_order",
                (self.selected_template_id,),
            ).fetchall()
        for r in rows:
            d = dict(r)
            branch = ""
            if d.get("parent_question_id"):
                branch = f"if #{d['parent_question_id']} {d.get('show_if_op') or 'eq'} {d.get('show_if_value') or ''}"
            self.q_tree.insert("", tk.END, iid=str(d["question_id"]), values=(
                d["question_id"], d.get("display_order", 0),
                d.get("question_text", "")[:120],
                d.get("question_type", ""),
                "yes" if d.get("is_required", 1) else "no",
                branch,
            ))

    def _current_question(self) -> dict | None:
        sel = self.q_tree.selection()
        if not sel or not self.selected_template_id:
            return None
        qid = int(sel[0])
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_questions WHERE question_id=?", (qid,),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------ Distribution (9-14)
    def _build_distribution_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="7. Distribution")

        # --- window + embargo
        win = ttk.LabelFrame(tab, text="Window & embargo", padding=8)
        win.pack(fill=tk.X, pady=4)
        ttk.Label(win, text="Start (YYYY-MM-DD):").grid(row=0, column=0, sticky=tk.W)
        self.win_start = ttk.Entry(win, width=14); self.win_start.grid(row=0, column=1, padx=4)
        ttk.Label(win, text="End:").grid(row=0, column=2, sticky=tk.W)
        self.win_end = ttk.Entry(win, width=14); self.win_end.grid(row=0, column=3, padx=4)
        self.win_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Auto open/close", variable=self.win_auto).grid(row=0, column=4, padx=8)
        ttk.Button(win, text="Save window", command=self._save_window).grid(row=0, column=5, padx=4)
        ttk.Button(win, text="Run auto-transition now",
                   command=self._run_auto_transition).grid(row=0, column=6, padx=4)
        self.embargo_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(win, text="Embargo results until grades submitted",
                        variable=self.embargo_var, command=self._save_embargo).grid(
            row=1, column=0, columnspan=4, sticky=tk.W, pady=(6, 0))
        ttk.Button(win, text="Mark grades submitted",
                   command=self._mark_grades_submitted).grid(row=1, column=5, columnspan=2, sticky=tk.W, pady=(6, 0))

        # --- reminders
        rem = ttk.LabelFrame(tab, text="Reminder cadence", padding=8)
        rem.pack(fill=tk.X, pady=4)
        ttk.Label(rem, text="Offset days from start:").grid(row=0, column=0, sticky=tk.W)
        self.rem_offset = ttk.Spinbox(rem, from_=-30, to=30, width=5); self.rem_offset.grid(row=0, column=1, padx=4)
        ttk.Label(rem, text="Channel:").grid(row=0, column=2, sticky=tk.W)
        self.rem_chan = ttk.Combobox(rem, state="readonly", values=("email", "sms", "portal"), width=8)
        self.rem_chan.current(0); self.rem_chan.grid(row=0, column=3, padx=4)
        ttk.Label(rem, text="Message:").grid(row=0, column=4, sticky=tk.W)
        self.rem_msg = ttk.Entry(rem, width=30); self.rem_msg.grid(row=0, column=5, padx=4)
        ttk.Button(rem, text="Add reminder", command=self._add_reminder).grid(row=0, column=6, padx=4)

        self.rem_tree = ttk.Treeview(rem, columns=("id", "offset", "channel", "message", "sent_at"),
                                     show="headings", height=4)
        for c, w in zip(("id", "offset", "channel", "message", "sent_at"), (50, 70, 80, 380, 160)):
            self.rem_tree.heading(c, text=c.title()); self.rem_tree.column(c, width=w, anchor=tk.W)
        self.rem_tree.grid(row=1, column=0, columnspan=7, sticky=tk.EW, pady=6)
        ttk.Button(rem, text="Delete selected",
                   command=self._delete_reminder).grid(row=2, column=0, sticky=tk.W)

        # --- bulk invites + tokens + QR
        inv = ttk.LabelFrame(tab, text="Bulk invitations · tokenised links · QR", padding=8)
        inv.pack(fill=tk.BOTH, expand=True, pady=4)
        left = ttk.Frame(inv); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(inv); right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))

        ttk.Label(left, text="Student IDs (one per line):").pack(anchor=tk.W)
        self.inv_ids = scrolledtext.ScrolledText(left, height=6)
        self.inv_ids.pack(fill=tk.X)
        bar = ttk.Frame(left); bar.pack(fill=tk.X, pady=4)
        ttk.Label(bar, text="Cohort:").pack(side=tk.LEFT)
        self.inv_cohort = ttk.Entry(bar, width=18); self.inv_cohort.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Send invites", command=self._send_invites).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Snapshot as roster",
                   command=self._roster_from_box).pack(side=tk.LEFT, padx=4)

        self.inv_tree = ttk.Treeview(left, columns=("recipient", "cohort", "used", "url"),
                                     show="headings", height=8)
        for c, w in zip(("recipient", "cohort", "used", "url"), (120, 100, 60, 540)):
            self.inv_tree.heading(c, text=c.title()); self.inv_tree.column(c, width=w, anchor=tk.W)
        self.inv_tree.pack(fill=tk.BOTH, expand=True, pady=4)
        self.inv_tree.bind("<<TreeviewSelect>>", self._render_qr)

        ttk.Label(right, text="QR / ASCII:").pack(anchor=tk.W)
        self.qr_box = scrolledtext.ScrolledText(right, width=42, height=22, font=("TkFixedFont", 8))
        self.qr_box.pack(fill=tk.BOTH, expand=True)

    # --- distribution callbacks
    def _require_eval(self) -> int | None:
        if not self.selected_evaluation_id:
            messagebox.showinfo("Evaluation", "Pick an evaluation in the header first.")
            return None
        return self.selected_evaluation_id

    def _save_window(self):
        eid = self._require_eval()
        if not eid:
            return
        try:
            scheduling.set_window(eid, self.win_start.get().strip(),
                                  self.win_end.get().strip(),
                                  auto_open=self.win_auto.get())
        except Exception as e:
            messagebox.showerror("Window", str(e)); return
        messagebox.showinfo("Window", "Saved.")
        self._refresh_evaluations()

    def _run_auto_transition(self):
        res = scheduling.auto_transition()
        messagebox.showinfo("Auto-transition",
                            f"Opened: {res['opened']}\nClosed: {res['closed']}")

    def _save_embargo(self):
        eid = self._require_eval()
        if not eid:
            return
        scheduling.set_embargo(eid, self.embargo_var.get())

    def _mark_grades_submitted(self):
        eid = self._require_eval()
        if not eid:
            return
        scheduling.mark_grades_submitted(eid)
        messagebox.showinfo("Grades", "Grades submission timestamp recorded.")

    def _add_reminder(self):
        eid = self._require_eval()
        if not eid:
            return
        try:
            offset = int(self.rem_offset.get())
        except ValueError:
            messagebox.showerror("Reminder", "Offset must be a number."); return
        scheduling.schedule_reminder(eid, offset,
                                     channel=self.rem_chan.get() or "email",
                                     message=self.rem_msg.get().strip())
        self._refresh_reminders()

    def _delete_reminder(self):
        sel = self.rem_tree.selection()
        if not sel:
            return
        rid = int(self.rem_tree.item(sel[0])["values"][0])
        scheduling.delete_reminder(rid)
        self._refresh_reminders()

    def _send_invites(self):
        eid = self._require_eval()
        if not eid:
            return
        ids = [ln.strip() for ln in self.inv_ids.get("1.0", tk.END).splitlines() if ln.strip()]
        if not ids:
            messagebox.showinfo("Invites", "No recipient IDs entered."); return
        issued = scheduling.bulk_invite(eid, ids, cohort=self.inv_cohort.get().strip())
        messagebox.showinfo("Invites", f"Issued {len(issued)} new tokens.")
        self._refresh_invitations()

    def _roster_from_box(self):
        eid = self._require_eval()
        if not eid:
            return
        ids = [ln.strip() for ln in self.inv_ids.get("1.0", tk.END).splitlines() if ln.strip()]
        n = scheduling.set_roster(eid, ids)
        messagebox.showinfo("Roster", f"Stored roster of {n} students.")

    def _render_qr(self, _event=None):
        sel = self.inv_tree.selection()
        if not sel:
            return
        token = self.inv_tree.item(sel[0])["values"][3].rsplit("/", 1)[-1]
        self.qr_box.delete("1.0", tk.END)
        self.qr_box.insert("1.0", scheduling.qr_for_token(token))

    def _refresh_reminders(self):
        for i in self.rem_tree.get_children():
            self.rem_tree.delete(i)
        if not self.selected_evaluation_id:
            return
        for r in scheduling.list_reminders(self.selected_evaluation_id):
            self.rem_tree.insert("", tk.END, values=(
                r["reminder_id"], r["offset_days"], r["channel"],
                r.get("message") or "", r.get("sent_at") or "",
            ))

    def _refresh_invitations(self):
        for i in self.inv_tree.get_children():
            self.inv_tree.delete(i)
        if not self.selected_evaluation_id:
            return
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT recipient_id, cohort, used, token FROM evaluation_invitations
                   WHERE evaluation_id=? ORDER BY created_at DESC""",
                (self.selected_evaluation_id,),
            ).fetchall()
        for r in rows:
            self.inv_tree.insert("", tk.END, values=(
                r["recipient_id"], r["cohort"] or "",
                "yes" if r["used"] else "no",
                scheduling.invitation_url(r["token"]),
            ))

    # ------------------------------------------------------------ Respondent UX (15-19)
    def _build_respondent_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="8. Respondent UX")

        top = ttk.Frame(tab); top.pack(fill=tk.X, pady=4)
        ttk.Button(top, text="Compute / refresh ETC",
                   command=self._refresh_etc).pack(side=tk.LEFT, padx=4)
        self.etc_label = ttk.Label(top, text="Estimated time: —",
                                   font=("TkDefaultFont", 11, "bold"))
        self.etc_label.pack(side=tk.LEFT, padx=12)
        ttk.Label(top, text="  Mobile viewport (px):").pack(side=tk.LEFT)
        self.viewport = ttk.Spinbox(top, from_=320, to=1920, width=6); self.viewport.insert(0, "1200")
        self.viewport.pack(side=tk.LEFT)
        self.viewport_label = ttk.Label(top, text=" → 4 cols")
        self.viewport_label.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Preview layout", command=self._preview_responsive).pack(side=tk.LEFT, padx=8)

        # Sentiment preview
        sent = ttk.LabelFrame(tab, text="Sentiment preview (feature 19)", padding=8)
        sent.pack(fill=tk.X, pady=6)
        ttk.Label(sent, text="Draft comment:").pack(anchor=tk.W)
        self.sent_text = scrolledtext.ScrolledText(sent, height=4)
        self.sent_text.pack(fill=tk.X)
        self.sent_label = ttk.Label(sent, text="", font=("TkDefaultFont", 11))
        self.sent_label.pack(anchor=tk.W, pady=4)
        ttk.Button(sent, text="Preview sentiment",
                   command=self._preview_sentiment).pack(anchor=tk.W)

        # Redaction
        red = ttk.LabelFrame(tab, text="Profanity & PII redaction (feature 18)", padding=8)
        red.pack(fill=tk.BOTH, expand=True, pady=6)
        ttk.Label(red, text="Text to redact:").pack(anchor=tk.W)
        self.red_in = scrolledtext.ScrolledText(red, height=3)
        self.red_in.pack(fill=tk.X)
        ttk.Button(red, text="Redact", command=self._do_redact).pack(anchor=tk.W, pady=2)
        ttk.Label(red, text="Result:").pack(anchor=tk.W)
        self.red_out = scrolledtext.ScrolledText(red, height=3, foreground="#444")
        self.red_out.pack(fill=tk.X)

        rules_bar = ttk.Frame(red); rules_bar.pack(fill=tk.X, pady=4)
        ttk.Label(rules_bar, text="Custom rule (regex):").pack(side=tk.LEFT)
        self.red_pat = ttk.Entry(rules_bar, width=30); self.red_pat.pack(side=tk.LEFT, padx=4)
        ttk.Label(rules_bar, text="Replacement:").pack(side=tk.LEFT)
        self.red_repl = ttk.Entry(rules_bar, width=15); self.red_repl.insert(0, "[redacted]")
        self.red_repl.pack(side=tk.LEFT, padx=4)
        ttk.Button(rules_bar, text="Add rule", command=self._add_redaction).pack(side=tk.LEFT, padx=4)

    def _refresh_etc(self):
        if not self.selected_template_id:
            messagebox.showinfo("ETC", "Pick a template first."); return
        mins = respondent.estimate_minutes(self.selected_template_id)
        self.etc_label.config(text=f"Estimated time: ~{mins} min")
        if self.selected_evaluation_id:
            respondent.store_estimate(self.selected_evaluation_id, mins)

    def _preview_responsive(self):
        try:
            vp = int(self.viewport.get())
        except ValueError:
            return
        cols = respondent.responsive_columns(vp)
        self.viewport_label.config(text=f" → {cols} col{'s' if cols != 1 else ''}")

    def _preview_sentiment(self):
        txt = self.sent_text.get("1.0", tk.END).strip()
        self.sent_label.config(text=respondent.sentiment_preview(txt) if txt else "")

    def _do_redact(self):
        txt = self.red_in.get("1.0", tk.END)
        self.red_out.delete("1.0", tk.END)
        self.red_out.insert("1.0", respondent.redact(txt))

    def _add_redaction(self):
        pat = self.red_pat.get().strip()
        if not pat:
            return
        try:
            respondent.add_redaction_rule(pat, self.red_repl.get().strip() or "[redacted]")
            messagebox.showinfo("Redaction", "Rule added.")
        except Exception as e:
            messagebox.showerror("Redaction", str(e))

    # ------------------------------------------------------------ Analytics (20-25)
    def _build_analytics_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="9. Analytics")

        top = ttk.Frame(tab); top.pack(fill=tk.X)
        ttk.Button(top, text="Refresh dashboard", command=self._refresh_dashboard).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Run sentiment scoring",
                   command=self._run_sentiment).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Flag suspicious",
                   command=self._run_flag_suspicious).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="  Department prefix for benchmark:").pack(side=tk.LEFT, padx=(12, 0))
        self.bench_dept = ttk.Entry(top, width=8); self.bench_dept.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Run benchmark", command=self._run_benchmark).pack(side=tk.LEFT, padx=4)

        cols = ("eval_id", "module", "year", "sem", "instructor", "responses",
                "roster", "percent")
        self.dash_tree = ttk.Treeview(tab, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (60, 80, 80, 60, 100, 80, 80, 70)):
            self.dash_tree.heading(c, text=c.title()); self.dash_tree.column(c, width=w, anchor=tk.W)
        self.dash_tree.pack(fill=tk.X, pady=4)

        mid = ttk.Frame(tab); mid.pack(fill=tk.BOTH, expand=True, pady=4)

        wc = ttk.LabelFrame(mid, text="Word cloud / topics (free-text)", padding=6)
        wc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.wc_box = scrolledtext.ScrolledText(wc, height=20, font=("TkFixedFont", 10))
        self.wc_box.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(mid); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tr = ttk.LabelFrame(right, text="Cross-term trend", padding=6)
        tr.pack(fill=tk.BOTH, expand=True)
        tr_bar = ttk.Frame(tr); tr_bar.pack(fill=tk.X)
        ttk.Button(tr_bar, text="Module trend", command=self._show_module_trend).pack(side=tk.LEFT)
        ttk.Button(tr_bar, text="Instructor trend",
                   command=self._show_instructor_trend).pack(side=tk.LEFT, padx=4)
        self.trend_box = scrolledtext.ScrolledText(tr, height=10, font=("TkFixedFont", 10))
        self.trend_box.pack(fill=tk.BOTH, expand=True)

        flags = ttk.LabelFrame(right, text="Suspicious-response flags", padding=6)
        flags.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.flag_tree = ttk.Treeview(flags, columns=("response_id", "flag", "score"),
                                      show="headings", height=6)
        for c, w in zip(("response_id", "flag", "score"), (100, 160, 80)):
            self.flag_tree.heading(c, text=c.title()); self.flag_tree.column(c, width=w, anchor=tk.W)
        self.flag_tree.pack(fill=tk.BOTH, expand=True)

    def _refresh_dashboard(self):
        for i in self.dash_tree.get_children():
            self.dash_tree.delete(i)
        for d in analytics.dashboard_summary():
            self.dash_tree.insert("", tk.END, values=(
                d["evaluation_id"], d["module_code"], d["academic_year"],
                d["semester"], d["instructor_id"], d["responses"],
                d["roster"], f"{d['percent']}%",
            ))

    def _run_sentiment(self):
        eid = self._require_eval()
        if not eid:
            return
        res = analytics.score_all_text(eid)
        messagebox.showinfo("Sentiment",
                            f"{res['total']} comments scored.\n"
                            f"+{res['counts']['positive']} / ·{res['counts']['neutral']} / −{res['counts']['negative']}\n"
                            f"Net: {res['net']:+.2f}")
        # also refresh wordcloud
        self._refresh_wordcloud()

    def _refresh_wordcloud(self):
        self.wc_box.delete("1.0", tk.END)
        if not self.selected_evaluation_id:
            return
        freq = analytics.word_frequencies(self.selected_evaluation_id, top=40)
        if not freq:
            self.wc_box.insert("1.0", "(no free-text answers yet)")
            return
        top_n = max(c for _, c in freq) or 1
        for w, c in freq:
            bar = "█" * max(1, int((c / top_n) * 30))
            self.wc_box.insert(tk.END, f"{w:<18} {bar}  {c}\n")
        topics = analytics.cluster_topics(self.selected_evaluation_id, k=4)
        self.wc_box.insert(tk.END, "\nTopics:\n")
        for t in topics:
            self.wc_box.insert(tk.END,
                               f"  · {t['label']}  (×{t['size']}) — {', '.join(t['members'])}\n")

    def _run_flag_suspicious(self):
        eid = self._require_eval()
        if not eid:
            return
        flagged = analytics.flag_suspicious(eid)
        for i in self.flag_tree.get_children():
            self.flag_tree.delete(i)
        for f in flagged:
            self.flag_tree.insert("", tk.END,
                                  values=(f["response_id"], f["flag"], f["score"]))
        messagebox.showinfo("Flags", f"{len(flagged)} flag(s) recorded.")

    def _run_benchmark(self):
        eid = self._require_eval()
        if not eid:
            return
        try:
            res = analytics.benchmark(eid, department=self.bench_dept.get().strip() or None)
        except ValueError as e:
            messagebox.showerror("Benchmark", str(e)); return
        msg = (f"Course avg:       {res['course_avg']}\n"
               f"Department avg:   {res['department_avg']}  Δ {res['vs_department']}\n"
               f"Institution avg:  {res['institution_avg']}  Δ {res['vs_institution']}")
        messagebox.showinfo("Benchmark", msg)

    def _show_module_trend(self):
        eid = self._require_eval()
        if not eid:
            return
        with get_connection() as conn:
            row = conn.execute(
                "SELECT module_code FROM course_evaluations WHERE evaluation_id=?", (eid,),
            ).fetchone()
        if not row:
            return
        rows = analytics.module_trend(row["module_code"])
        self._render_trend(rows, title=f"Module {row['module_code']}")

    def _show_instructor_trend(self):
        eid = self._require_eval()
        if not eid:
            return
        with get_connection() as conn:
            row = conn.execute(
                "SELECT instructor_id FROM course_evaluations WHERE evaluation_id=?", (eid,),
            ).fetchone()
        if not row:
            return
        rows = analytics.instructor_trend(row["instructor_id"])
        self._render_trend(rows, title=f"Instructor {row['instructor_id']}")

    def _render_trend(self, rows: list[dict], *, title: str):
        self.trend_box.delete("1.0", tk.END)
        self.trend_box.insert(tk.END, f"{title}\n" + "-" * 60 + "\n")
        if not rows:
            self.trend_box.insert(tk.END, "(no data)")
            return
        for r in rows:
            avg = r["avg_score"]
            bar = "█" * (int(avg * 5) if avg else 0)
            self.trend_box.insert(
                tk.END,
                f"{r['academic_year']:<10}{(r['semester'] or ''):<6} "
                f"{(avg or 0):>5.2f} {bar:<25} (n={r['responses']})\n",
            )

    # ------------------------------------------------------------ Evaluation selector wiring
    def _refresh_evaluations(self):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT evaluation_id, module_code, academic_year, semester,
                          instructor_id, embargo_until_grades
                   FROM course_evaluations ORDER BY created_at DESC"""
            ).fetchall()
        self._evaluations_cache = [dict(r) for r in rows]
        labels = [f"#{e['evaluation_id']}  {e['module_code']}  {e['academic_year']} {e['semester']}  · {e['instructor_id']}"
                  for e in self._evaluations_cache]
        self.eval_combo["values"] = labels
        if self._evaluations_cache:
            keep = self.selected_evaluation_id
            idx = 0
            if keep is not None:
                for i, e in enumerate(self._evaluations_cache):
                    if e["evaluation_id"] == keep:
                        idx = i
                        break
            self.eval_combo.current(idx)
            self.selected_evaluation_id = self._evaluations_cache[idx]["evaluation_id"]
            self.embargo_var.set(bool(self._evaluations_cache[idx].get("embargo_until_grades")))
        else:
            self.selected_evaluation_id = None
            self.eval_combo.set("")
        self._refresh_reminders()
        self._refresh_invitations()
        self._refresh_dashboard()
        self._refresh_wordcloud()

    def _on_eval_change(self, _event=None):
        idx = self.eval_combo.current()
        if 0 <= idx < len(self._evaluations_cache):
            e = self._evaluations_cache[idx]
            self.selected_evaluation_id = e["evaluation_id"]
            self.embargo_var.set(bool(e.get("embargo_until_grades")))
            self._refresh_reminders()
            self._refresh_invitations()
            self._refresh_wordcloud()


# ---- small dialogs -------------------------------------------------------

def _ask_string(parent, title: str, prompt: str) -> str | None:
    top = tk.Toplevel(parent)
    top.title(title)
    top.transient(parent)
    top.grab_set()
    ttk.Label(top, text=prompt).pack(padx=16, pady=(16, 4))
    var = tk.StringVar()
    entry = ttk.Entry(top, textvariable=var, width=40)
    entry.pack(padx=16, pady=4)
    entry.focus_set()
    result = {"value": None}

    def ok():
        result["value"] = var.get().strip()
        top.destroy()

    btns = ttk.Frame(top); btns.pack(pady=8)
    ttk.Button(btns, text="OK", command=ok).pack(side=tk.LEFT, padx=4)
    ttk.Button(btns, text="Cancel", command=top.destroy).pack(side=tk.LEFT, padx=4)
    entry.bind("<Return>", lambda _e: ok())
    parent.wait_window(top)
    return result["value"]


class _NewBankDialog:
    def __init__(self, parent):
        self.result: dict | None = None
        self.top = tk.Toplevel(parent)
        self.top.title("New Bank Question")
        self.top.transient(parent)
        self.top.grab_set()

        frm = ttk.Frame(self.top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Question text:").grid(row=0, column=0, sticky=tk.NW, pady=2)
        self.text = tk.Text(frm, width=60, height=3)
        self.text.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(frm, text="Type:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.qtype = ttk.Combobox(frm, state="readonly",
                                  values=list(authoring.SUPPORTED_TYPES), width=18)
        self.qtype.current(0)
        self.qtype.grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(frm, text="Category:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.cat = ttk.Entry(frm, width=30)
        self.cat.grid(row=2, column=1, sticky=tk.W, pady=2)

        ttk.Label(frm, text="Department:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.dept = ttk.Entry(frm, width=30)
        self.dept.grid(row=3, column=1, sticky=tk.W, pady=2)

        ttk.Label(frm, text="Tags (comma):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.tags = ttk.Entry(frm, width=40)
        self.tags.grid(row=4, column=1, sticky=tk.W, pady=2)

        ttk.Label(frm, text="Options (one/line):").grid(row=5, column=0, sticky=tk.NW, pady=2)
        self.opts = tk.Text(frm, width=40, height=5)
        self.opts.grid(row=5, column=1, sticky=tk.W, pady=2)

        btns = ttk.Frame(frm); btns.grid(row=6, column=1, sticky=tk.E, pady=8)
        ttk.Button(btns, text="Save", command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(side=tk.LEFT, padx=4)

    def _save(self):
        text = self.text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("New Question", "Question text is required.")
            return
        opts = [ln.strip() for ln in self.opts.get("1.0", tk.END).splitlines() if ln.strip()]
        self.result = {
            "text": text,
            "qtype": self.qtype.get(),
            "category": self.cat.get().strip(),
            "department": self.dept.get().strip(),
            "tags": [t.strip() for t in self.tags.get().split(",") if t.strip()],
            "options": opts or None,
        }
        self.top.destroy()


def launch_survey_designer(parent=None, auth=None):
    gui = SurveyDesignerGUI(parent, auth)
    return gui


__all__ = ["SurveyDesignerGUI", "launch_survey_designer"]
