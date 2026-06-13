"""
Course Evaluation Operations GUI — features 26-50.

Five tabs, mirroring the five service modules:

  • Action Loop   (29-33)
  • Extra Stats   (26-28)
  • Integrations  (34-38)
  • Compliance    (39-43)
  • Admin Ops     (44-50)
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.evaluation import (
    admin as admin_svc,
    compliance,
    extra_analytics,
    integrations,
    workflow,
)
from education_system.university_system.modules.domain.academics.services.evaluation.db_schema import (
    initialize_evaluation_database,
)


_W, _H = 1400, 900
_MIN_W, _MIN_H = 1200, 800


class OperationsGUI:
    def __init__(self, parent, auth=None):
        initialize_evaluation_database()
        self.auth = auth
        self.user = self._user_id(auth)
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Course Evaluation — Operations")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{_W}x{_H}+{(sw - _W)//2}+{(sh - _H)//2}")
        self.root.minsize(_MIN_W, _MIN_H)
        self.root.configure(bg="#f0f0f0")

        self.selected_evaluation_id: int | None = None
        self.selected_template_id: int | None = None
        self._evals_cache: list[dict] = []
        self._templates_cache: list[dict] = []

        self._build()

    @staticmethod
    def _user_id(auth) -> str:
        if not auth:
            return "system"
        u = getattr(auth, "current_user", None)
        if isinstance(u, dict):
            return u.get("username", "system")
        return str(u) if u else "system"

    # ---- header ------------------------------------------------------
    def _build(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(outer)
        head.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(head, text="Operations",
                  font=("TkDefaultFont", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(head, text="  Evaluation:").pack(side=tk.LEFT, padx=(12, 0))
        self.eval_combo = ttk.Combobox(head, state="readonly", width=46)
        self.eval_combo.pack(side=tk.LEFT, padx=4)
        self.eval_combo.bind("<<ComboboxSelected>>", self._on_eval)
        ttk.Label(head, text="  Template:").pack(side=tk.LEFT)
        self.tpl_combo = ttk.Combobox(head, state="readonly", width=40)
        self.tpl_combo.pack(side=tk.LEFT, padx=4)
        self.tpl_combo.bind("<<ComboboxSelected>>", self._on_tpl)
        ttk.Button(head, text="Refresh", command=self._refresh_header).pack(side=tk.LEFT, padx=6)

        self.nb = ttk.Notebook(outer)
        self.nb.pack(fill=tk.BOTH, expand=True)
        self._build_workflow_tab()
        self._build_stats_tab()
        self._build_integrations_tab()
        self._build_compliance_tab()
        self._build_admin_tab()
        self._refresh_header()

    # ---- header refresh ---------------------------------------------
    def _refresh_header(self):
        with get_connection() as conn:
            evs = conn.execute(
                """SELECT evaluation_id, module_code, academic_year, semester, instructor_id
                   FROM course_evaluations ORDER BY created_at DESC"""
            ).fetchall()
            tps = conn.execute(
                """SELECT template_id, template_name, template_type FROM evaluation_templates
                   ORDER BY created_at DESC"""
            ).fetchall()
        self._evals_cache = [dict(r) for r in evs]
        self._templates_cache = [dict(r) for r in tps]
        self.eval_combo["values"] = [
            f"#{e['evaluation_id']}  {e['module_code']}  {e['academic_year']} {e['semester']}  · {e['instructor_id']}"
            for e in self._evals_cache
        ]
        self.tpl_combo["values"] = [
            f"#{t['template_id']}  {t['template_name']}  [{t['template_type']}]"
            for t in self._templates_cache
        ]
        if self._evals_cache and self.selected_evaluation_id is None:
            self.eval_combo.current(0)
            self.selected_evaluation_id = self._evals_cache[0]["evaluation_id"]
        if self._templates_cache and self.selected_template_id is None:
            self.tpl_combo.current(0)
            self.selected_template_id = self._templates_cache[0]["template_id"]
        self._refresh_all_tabs()

    def _on_eval(self, _=None):
        i = self.eval_combo.current()
        if 0 <= i < len(self._evals_cache):
            self.selected_evaluation_id = self._evals_cache[i]["evaluation_id"]
            self._refresh_all_tabs()

    def _on_tpl(self, _=None):
        i = self.tpl_combo.current()
        if 0 <= i < len(self._templates_cache):
            self.selected_template_id = self._templates_cache[i]["template_id"]
            self._refresh_all_tabs()

    def _refresh_all_tabs(self):
        self._refresh_ysw()
        self._refresh_replies()
        self._refresh_review_queue()
        self._refresh_redflags()
        self._refresh_imp_plans()
        self._refresh_dashboards()
        self._refresh_lms()
        self._refresh_hooks()
        self._refresh_audit()
        self._refresh_trash()

    def _need_eval(self):
        if not self.selected_evaluation_id:
            messagebox.showinfo("Evaluation", "Pick an evaluation in the header.")
            return None
        return self.selected_evaluation_id

    def _need_tpl(self):
        if not self.selected_template_id:
            messagebox.showinfo("Template", "Pick a template in the header.")
            return None
        return self.selected_template_id

    # ============================================================ 29-33
    def _build_workflow_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Action Loop")

        # --- you said / we did (29)
        ysw = ttk.LabelFrame(tab, text="You said / we did (29)", padding=6)
        ysw.pack(fill=tk.X, pady=4)
        bar = ttk.Frame(ysw); bar.pack(fill=tk.X)
        ttk.Label(bar, text="Theme:").pack(side=tk.LEFT)
        self.ysw_theme = ttk.Entry(bar, width=20); self.ysw_theme.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="You said:").pack(side=tk.LEFT)
        self.ysw_text = ttk.Entry(bar, width=50); self.ysw_text.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Add", command=self._add_ysw).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Resolve selected…", command=self._resolve_ysw).pack(side=tk.LEFT, padx=4)
        cols = ("id", "theme", "you_said", "we_did", "status", "created_at")
        self.ysw_tree = ttk.Treeview(ysw, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (50, 120, 360, 360, 70, 140)):
            self.ysw_tree.heading(c, text=c.replace("_", " ").title())
            self.ysw_tree.column(c, width=w, anchor=tk.W)
        self.ysw_tree.pack(fill=tk.X, pady=4)

        # --- instructor replies (30)
        rep = ttk.LabelFrame(tab, text="Instructor reply (30)", padding=6)
        rep.pack(fill=tk.X, pady=4)
        ttk.Label(rep, text="Reply text:").pack(anchor=tk.W)
        self.rep_text = scrolledtext.ScrolledText(rep, height=3)
        self.rep_text.pack(fill=tk.X)
        ttk.Button(rep, text="Post reply", command=self._post_reply).pack(anchor=tk.W, pady=2)
        cols = ("id", "theme", "reply", "by", "at")
        self.rep_tree = ttk.Treeview(rep, columns=cols, show="headings", height=3)
        for c, w in zip(cols, (50, 120, 700, 100, 140)):
            self.rep_tree.heading(c, text=c.title()); self.rep_tree.column(c, width=w, anchor=tk.W)
        self.rep_tree.pack(fill=tk.X, pady=4)

        # --- review queue (31)
        rev = ttk.LabelFrame(tab, text="Department-head review queue (31)", padding=6)
        rev.pack(fill=tk.X, pady=4)
        bar2 = ttk.Frame(rev); bar2.pack(fill=tk.X)
        ttk.Label(bar2, text="Reviewer:").pack(side=tk.LEFT)
        self.rev_reviewer = ttk.Entry(bar2, width=20); self.rev_reviewer.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Queue for review", command=self._queue_review).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Sign-off approved", command=lambda: self._sign_off("approved")).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Sign-off rejected", command=lambda: self._sign_off("rejected")).pack(side=tk.LEFT, padx=4)
        cols = ("id", "eval_id", "reviewer", "status", "comment", "signed_off_at")
        self.rev_tree = ttk.Treeview(rev, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (50, 70, 120, 90, 360, 160)):
            self.rev_tree.heading(c, text=c.replace("_", " ").title())
            self.rev_tree.column(c, width=w, anchor=tk.W)
        self.rev_tree.pack(fill=tk.X, pady=4)

        # --- red flags (32) and improvement plans (33) side-by-side
        bottom = ttk.Frame(tab); bottom.pack(fill=tk.BOTH, expand=True, pady=4)
        rf = ttk.LabelFrame(bottom, text="Red-flag comments (32)", padding=6)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        ttk.Button(rf, text="Refresh", command=self._refresh_redflags).pack(anchor=tk.W)
        ttk.Button(rf, text="Acknowledge selected",
                   command=self._ack_redflag).pack(anchor=tk.W, pady=2)
        cols = ("id", "answer_id", "category", "routed_to", "ack")
        self.rf_tree = ttk.Treeview(rf, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (50, 80, 110, 110, 60)):
            self.rf_tree.heading(c, text=c.title()); self.rf_tree.column(c, width=w, anchor=tk.W)
        self.rf_tree.pack(fill=tk.BOTH, expand=True, pady=2)

        imp = ttk.LabelFrame(bottom, text="Improvement plans (33)", padding=6)
        imp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar3 = ttk.Frame(imp); bar3.pack(fill=tk.X)
        ttk.Label(bar3, text="Template:").pack(side=tk.LEFT)
        self.imp_tpl = ttk.Combobox(bar3, state="readonly", width=25)
        self.imp_tpl.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Add template…", command=self._add_imp_template).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Create plan from template",
                   command=self._create_plan).pack(side=tk.LEFT, padx=4)
        cols = ("id", "template_id", "author", "created_at")
        self.imp_tree = ttk.Treeview(imp, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (50, 100, 120, 160)):
            self.imp_tree.heading(c, text=c.title()); self.imp_tree.column(c, width=w, anchor=tk.W)
        self.imp_tree.pack(fill=tk.BOTH, expand=True, pady=2)

    def _add_ysw(self):
        eid = self._need_eval()
        theme = self.ysw_theme.get().strip()
        text = self.ysw_text.get().strip()
        if not (eid and theme and text):
            return
        workflow.ysw_create(eid, theme, text, owner=self.user)
        self.ysw_theme.delete(0, tk.END); self.ysw_text.delete(0, tk.END)
        self._refresh_ysw()

    def _resolve_ysw(self):
        sel = self.ysw_tree.selection()
        if not sel:
            return
        ysw_id = int(self.ysw_tree.item(sel[0])["values"][0])
        from tkinter import simpledialog
        we_did = simpledialog.askstring("Resolve", "What did you do?")
        if we_did:
            workflow.ysw_resolve(ysw_id, we_did)
            self._refresh_ysw()

    def _refresh_ysw(self):
        for i in self.ysw_tree.get_children():
            self.ysw_tree.delete(i)
        for r in workflow.ysw_list():
            self.ysw_tree.insert("", tk.END, values=(
                r["ysw_id"], r["theme"], (r["you_said"] or "")[:100],
                (r.get("we_did") or "")[:100], r["status"], r["created_at"]))

    def _post_reply(self):
        eid = self._need_eval()
        if not eid:
            return
        txt = self.rep_text.get("1.0", tk.END).strip()
        if not txt:
            return
        workflow.reply(eid, txt, posted_by=self.user)
        self.rep_text.delete("1.0", tk.END)
        self._refresh_replies()

    def _refresh_replies(self):
        for i in self.rep_tree.get_children():
            self.rep_tree.delete(i)
        if not self.selected_evaluation_id:
            return
        for r in workflow.list_replies(self.selected_evaluation_id):
            self.rep_tree.insert("", tk.END, values=(
                r["reply_id"], r.get("theme") or "", r["reply_text"][:200],
                r.get("posted_by") or "", r["posted_at"]))

    def _queue_review(self):
        eid = self._need_eval()
        reviewer = self.rev_reviewer.get().strip()
        if not (eid and reviewer):
            return
        workflow.queue_for_review(eid, reviewer)
        self._refresh_review_queue()

    def _sign_off(self, status: str):
        sel = self.rev_tree.selection()
        if not sel:
            return
        qid = int(self.rev_tree.item(sel[0])["values"][0])
        from tkinter import simpledialog
        comment = simpledialog.askstring("Sign-off", "Comment (optional):") or ""
        workflow.sign_off(qid, status=status, comment=comment)
        self._refresh_review_queue()

    def _refresh_review_queue(self):
        for i in self.rev_tree.get_children():
            self.rev_tree.delete(i)
        for r in workflow.list_review_queue():
            self.rev_tree.insert("", tk.END, values=(
                r["queue_id"], r["evaluation_id"], r["reviewer"],
                r["status"], (r.get("comment") or "")[:120], r.get("signed_off_at") or ""))

    def _refresh_redflags(self):
        for i in self.rf_tree.get_children():
            self.rf_tree.delete(i)
        for r in workflow.list_redflags():
            self.rf_tree.insert("", tk.END, values=(
                r["flag_id"], r["answer_id"], r["category"],
                r["routed_to"], "yes" if r["acknowledged"] else "no"))

    def _ack_redflag(self):
        sel = self.rf_tree.selection()
        if not sel:
            return
        fid = int(self.rf_tree.item(sel[0])["values"][0])
        workflow.acknowledge_redflag(fid)
        self._refresh_redflags()

    def _refresh_imp_plans(self):
        for i in self.imp_tree.get_children():
            self.imp_tree.delete(i)
        templates = workflow.list_improvement_templates()
        self.imp_tpl["values"] = [f"#{t['imp_template_id']}  {t['name']}" for t in templates]
        if self.selected_evaluation_id:
            for p in workflow.list_plans(self.selected_evaluation_id):
                self.imp_tree.insert("", tk.END, values=(
                    p["plan_id"], p.get("template_id"), p.get("author") or "", p["created_at"]))

    def _add_imp_template(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Template name", "Name:")
        if not name:
            return
        body = simpledialog.askstring("Template body", "Body:")
        if body is None:
            return
        workflow.add_improvement_template(name, body)
        self._refresh_imp_plans()

    def _create_plan(self):
        eid = self._need_eval()
        if not eid:
            return
        sel = self.imp_tpl.get()
        if not sel:
            return
        try:
            tpl_id = int(sel.split()[0].lstrip("#"))
        except ValueError:
            return
        workflow.create_plan(eid, template_id=tpl_id, author=self.user)
        self._refresh_imp_plans()

    # ============================================================ 26-28
    def _build_stats_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Extra Stats")

        # 26 demographic cut
        demo = ttk.LabelFrame(tab, text="Demographic cut with k-anonymity (26)", padding=6)
        demo.pack(fill=tk.X, pady=4)
        bar = ttk.Frame(demo); bar.pack(fill=tk.X)
        ttk.Label(bar, text="Dimension:").pack(side=tk.LEFT)
        self.demo_dim = ttk.Entry(bar, width=15); self.demo_dim.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="k:").pack(side=tk.LEFT)
        self.demo_k = ttk.Spinbox(bar, from_=1, to=99, width=4)
        self.demo_k.delete(0, tk.END); self.demo_k.insert(0, str(extra_analytics.get_k_anonymity()))
        self.demo_k.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Run cut", command=self._run_demo).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Save k as default",
                   command=self._save_k).pack(side=tk.LEFT, padx=4)
        cols = ("bucket", "n", "mean", "stdev", "suppressed")
        self.demo_tree = ttk.Treeview(demo, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (180, 60, 80, 80, 100)):
            self.demo_tree.heading(c, text=c.title()); self.demo_tree.column(c, width=w, anchor=tk.W)
        self.demo_tree.pack(fill=tk.X, pady=4)

        # 27 dashboards
        dash = ttk.LabelFrame(tab, text="Custom dashboards (27)", padding=6)
        dash.pack(fill=tk.X, pady=4)
        bar2 = ttk.Frame(dash); bar2.pack(fill=tk.X)
        ttk.Label(bar2, text="Name:").pack(side=tk.LEFT)
        self.dash_name = ttk.Entry(bar2, width=20); self.dash_name.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="Role:").pack(side=tk.LEFT)
        self.dash_role = ttk.Entry(bar2, width=14); self.dash_role.insert(0, "*"); self.dash_role.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="Widgets (JSON list):").pack(side=tk.LEFT)
        self.dash_widgets = ttk.Entry(bar2, width=50)
        self.dash_widgets.insert(0, '[{"type":"response_rate"},{"type":"wordcloud"}]')
        self.dash_widgets.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Save", command=self._save_dashboard).pack(side=tk.LEFT, padx=4)
        cols = ("id", "owner", "role", "name", "widgets", "updated_at")
        self.dash_tree = ttk.Treeview(dash, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (50, 100, 100, 160, 460, 140)):
            self.dash_tree.heading(c, text=c.title()); self.dash_tree.column(c, width=w, anchor=tk.W)
        self.dash_tree.pack(fill=tk.X, pady=4)
        ttk.Button(dash, text="Delete selected", command=self._delete_dashboard).pack(anchor=tk.W)

        # 28 significance
        sig = ttk.LabelFrame(tab, text="Significance test (28)", padding=6)
        sig.pack(fill=tk.X, pady=4)
        bar3 = ttk.Frame(sig); bar3.pack(fill=tk.X)
        ttk.Label(bar3, text="Question ID:").pack(side=tk.LEFT)
        self.sig_qid = ttk.Entry(bar3, width=8); self.sig_qid.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar3, text="Compare against:").pack(side=tk.LEFT)
        self.sig_against = ttk.Entry(bar3, width=15); self.sig_against.insert(0, "institution")
        self.sig_against.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Run t-test", command=self._run_sig).pack(side=tk.LEFT, padx=4)
        self.sig_label = ttk.Label(sig, text="No test run yet.", font=("TkDefaultFont", 10, "bold"))
        self.sig_label.pack(anchor=tk.W, pady=4)

    def _run_demo(self):
        eid = self._need_eval()
        if not eid:
            return
        try:
            k = int(self.demo_k.get())
        except ValueError:
            return
        rows = extra_analytics.demographic_cut(eid, self.demo_dim.get().strip(), k=k)
        for i in self.demo_tree.get_children():
            self.demo_tree.delete(i)
        for r in rows:
            self.demo_tree.insert("", tk.END, values=(
                r["bucket"], r["n"],
                r.get("mean") if r.get("mean") is not None else "—",
                r.get("stdev") if r.get("stdev") is not None else "—",
                "yes" if r["suppressed"] else "no",
            ))

    def _save_k(self):
        try:
            extra_analytics.set_k_anonymity(int(self.demo_k.get()))
            messagebox.showinfo("k-anonymity", "Default saved.")
        except ValueError as e:
            messagebox.showerror("k-anonymity", str(e))

    def _save_dashboard(self):
        try:
            widgets = json.loads(self.dash_widgets.get())
            extra_analytics.save_dashboard(
                self.user, self.dash_name.get().strip() or "Untitled",
                widgets, role=self.dash_role.get().strip() or "*",
            )
        except (ValueError, json.JSONDecodeError) as e:
            messagebox.showerror("Dashboard", str(e)); return
        self._refresh_dashboards()

    def _refresh_dashboards(self):
        for i in self.dash_tree.get_children():
            self.dash_tree.delete(i)
        for d in extra_analytics.list_dashboards():
            self.dash_tree.insert("", tk.END, values=(
                d["dashboard_id"], d["owner"], d["role"], d["name"],
                json.dumps(d["layout"])[:200], d["updated_at"]))

    def _delete_dashboard(self):
        sel = self.dash_tree.selection()
        if not sel:
            return
        did = int(self.dash_tree.item(sel[0])["values"][0])
        extra_analytics.delete_dashboard(did)
        self._refresh_dashboards()

    def _run_sig(self):
        eid = self._need_eval()
        if not eid:
            return
        try:
            qid = int(self.sig_qid.get())
        except ValueError:
            messagebox.showinfo("Significance", "Enter a numeric question_id."); return
        res = extra_analytics.significance(eid, qid, against=self.sig_against.get().strip() or "institution")
        flag = "★ SIGNIFICANT" if res["significant"] else "not significant"
        warn = "  ⚠ underpowered" if res["underpowered"] else ""
        self.sig_label.config(
            text=f"t={res['t']}  df={res['df']}  p={res['p_value']}  ({flag}){warn}  "
                 f"n_course={res['n_course']} / n_scope={res['n_scope']}"
        )

    # ============================================================ 34-38
    def _build_integrations_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Integrations")

        # 34: LMS
        lms = ttk.LabelFrame(tab, text="LMS deep link (34)", padding=6)
        lms.pack(fill=tk.X, pady=4)
        bar = ttk.Frame(lms); bar.pack(fill=tk.X)
        ttk.Label(bar, text="LMS:").pack(side=tk.LEFT)
        self.lms_kind = ttk.Combobox(bar, state="readonly",
                                     values=("canvas", "moodle", "blackboard"), width=12)
        self.lms_kind.current(0); self.lms_kind.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Base URL:").pack(side=tk.LEFT)
        self.lms_base = ttk.Entry(bar, width=30)
        self.lms_base.insert(0, "https://canvas.example.edu"); self.lms_base.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Course ID:").pack(side=tk.LEFT)
        self.lms_course = ttk.Entry(bar, width=10); self.lms_course.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Eval URL:").pack(side=tk.LEFT)
        self.lms_eval = ttk.Entry(bar, width=30); self.lms_eval.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Generate", command=self._gen_lms).pack(side=tk.LEFT, padx=4)
        self.lms_tree = ttk.Treeview(lms, columns=("id", "lms", "url"), show="headings", height=3)
        for c, w in zip(("id", "lms", "url"), (50, 100, 1100)):
            self.lms_tree.heading(c, text=c.title()); self.lms_tree.column(c, width=w, anchor=tk.W)
        self.lms_tree.pack(fill=tk.X, pady=4)

        # 35 / 36 / 37
        ops_row = ttk.Frame(tab); ops_row.pack(fill=tk.X, pady=4)

        sis = ttk.LabelFrame(ops_row, text="SIS sync (35)", padding=6)
        sis.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        ttk.Label(sis, text="Current roster (one ID per line):").pack(anchor=tk.W)
        self.sis_box = scrolledtext.ScrolledText(sis, height=4); self.sis_box.pack(fill=tk.X)
        ttk.Button(sis, text="Sync now", command=self._do_sis).pack(anchor=tk.W, pady=2)
        self.sis_label = ttk.Label(sis, text="No sync yet."); self.sis_label.pack(anchor=tk.W)

        hr = ttk.LabelFrame(ops_row, text="HR export (36)", padding=6)
        hr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        ttk.Label(hr, text="Instructor ID:").pack(anchor=tk.W)
        self.hr_inst = ttk.Entry(hr); self.hr_inst.pack(fill=tk.X)
        ttk.Label(hr, text="Academic year:").pack(anchor=tk.W)
        self.hr_year = ttk.Entry(hr); self.hr_year.pack(fill=tk.X)
        ttk.Button(hr, text="Build packet", command=self._do_hr).pack(anchor=tk.W, pady=2)
        self.hr_box = scrolledtext.ScrolledText(hr, height=6); self.hr_box.pack(fill=tk.BOTH, expand=True)

        cal = ttk.LabelFrame(ops_row, text="Calendar hold (37)", padding=6)
        cal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        ttk.Label(cal, text="Instructor:").pack(anchor=tk.W)
        self.cal_inst = ttk.Entry(cal); self.cal_inst.pack(fill=tk.X)
        bar2 = ttk.Frame(cal); bar2.pack(fill=tk.X)
        ttk.Label(bar2, text="Start:").pack(side=tk.LEFT)
        self.cal_start = ttk.Entry(bar2, width=12); self.cal_start.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="End:").pack(side=tk.LEFT)
        self.cal_end = ttk.Entry(bar2, width=12); self.cal_end.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Add hold", command=self._do_hold).pack(side=tk.LEFT, padx=4)

        # 38: webhooks
        wh = ttk.LabelFrame(tab, text="Webhooks & event bus (38)", padding=6)
        wh.pack(fill=tk.BOTH, expand=True, pady=4)
        bar3 = ttk.Frame(wh); bar3.pack(fill=tk.X)
        ttk.Label(bar3, text="Event:").pack(side=tk.LEFT)
        self.wh_event = ttk.Combobox(bar3, state="readonly", values=(
            "evaluation.opened", "evaluation.closed", "response.submitted",
            "redflag.raised", "results.released",
        ), width=22)
        self.wh_event.current(0); self.wh_event.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar3, text="URL:").pack(side=tk.LEFT)
        self.wh_url = ttk.Entry(bar3, width=40); self.wh_url.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar3, text="Secret:").pack(side=tk.LEFT)
        self.wh_secret = ttk.Entry(bar3, width=18); self.wh_secret.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Subscribe", command=self._do_subscribe).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Emit test event",
                   command=self._do_emit).pack(side=tk.LEFT, padx=4)

        self.wh_tree = ttk.Treeview(wh, columns=("id", "event", "url", "active"),
                                    show="headings", height=4)
        for c, w in zip(("id", "event", "url", "active"), (50, 180, 800, 70)):
            self.wh_tree.heading(c, text=c.title()); self.wh_tree.column(c, width=w, anchor=tk.W)
        self.wh_tree.pack(fill=tk.X, pady=4)

        ttk.Label(wh, text="Delivery log (latest first):").pack(anchor=tk.W)
        self.wh_log = scrolledtext.ScrolledText(wh, height=6, font=("TkFixedFont", 9))
        self.wh_log.pack(fill=tk.BOTH, expand=True)

    def _gen_lms(self):
        eid = self._need_eval()
        if not eid:
            return
        try:
            integrations.lms_deep_link(
                eid, self.lms_kind.get(),
                base_url=self.lms_base.get(),
                course_id=self.lms_course.get(),
                eval_url=self.lms_eval.get(),
            )
        except ValueError as e:
            messagebox.showerror("LMS", str(e)); return
        self._refresh_lms()

    def _refresh_lms(self):
        for i in self.lms_tree.get_children():
            self.lms_tree.delete(i)
        if not self.selected_evaluation_id:
            return
        for r in integrations.list_lms_links(self.selected_evaluation_id):
            self.lms_tree.insert("", tk.END, values=(r["link_id"], r["lms"], r["deep_link_url"]))

    def _do_sis(self):
        eid = self._need_eval()
        if not eid:
            return
        ids = [ln.strip() for ln in self.sis_box.get("1.0", tk.END).splitlines() if ln.strip()]
        res = integrations.sis_sync(eid, ids)
        self.sis_label.config(text=f"+{res['added']}  −{res['removed']}  total={res['total']}")

    def _do_hr(self):
        if not (self.hr_inst.get().strip() and self.hr_year.get().strip()):
            return
        packet = integrations.hr_export_instructor(
            self.hr_inst.get().strip(), self.hr_year.get().strip())
        self.hr_box.delete("1.0", tk.END)
        self.hr_box.insert("1.0", json.dumps(packet, indent=2, default=str))

    def _do_hold(self):
        eid = self._need_eval()
        if not eid:
            return
        integrations.add_calendar_hold(
            eid, self.cal_inst.get().strip(),
            self.cal_start.get().strip(), self.cal_end.get().strip())
        messagebox.showinfo("Hold", "Calendar hold added.")

    def _do_subscribe(self):
        try:
            integrations.subscribe(self.wh_event.get(),
                                   self.wh_url.get().strip(),
                                   secret=self.wh_secret.get().strip())
        except ValueError as e:
            messagebox.showerror("Webhook", str(e)); return
        self._refresh_hooks()

    def _do_emit(self):
        eid = self.selected_evaluation_id
        n = integrations.emit(self.wh_event.get(),
                              {"evaluation_id": eid, "test": True})
        messagebox.showinfo("Emit", f"Delivered to {n} subscriber(s).")
        self._refresh_hooks()

    def _refresh_hooks(self):
        for i in self.wh_tree.get_children():
            self.wh_tree.delete(i)
        with get_connection() as conn:
            for r in conn.execute("SELECT * FROM evaluation_webhooks ORDER BY hook_id DESC"):
                self.wh_tree.insert("", tk.END, values=(
                    r["hook_id"], r["event"], r["url"],
                    "yes" if r["active"] else "no"))
        self.wh_log.delete("1.0", tk.END)
        for r in integrations.webhook_log(limit=40):
            self.wh_log.insert(tk.END, f"#{r['log_id']} {r['created_at']}  {r['event']}  → "
                                       f"hook {r['hook_id']}  {r['payload_json'][:120]}\n")

    # ============================================================ 39-43
    def _build_compliance_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Compliance")

        # 39 anonymity audit
        an = ttk.LabelFrame(tab, text="Anonymity audit (39)", padding=6)
        an.pack(fill=tk.X, pady=4)
        ttk.Button(an, text="Run anonymity assertion",
                   command=self._anon_check).pack(side=tk.LEFT)
        ttk.Button(an, text="Refresh tail",
                   command=self._refresh_audit).pack(side=tk.LEFT, padx=4)
        self.anon_label = ttk.Label(an, text="—"); self.anon_label.pack(side=tk.LEFT, padx=12)
        self.audit_box = scrolledtext.ScrolledText(an, height=5, font=("TkFixedFont", 9))
        self.audit_box.pack(fill=tk.X, pady=4)

        # 40 gdpr
        gd = ttk.LabelFrame(tab, text="GDPR data-subject (40)", padding=6)
        gd.pack(fill=tk.X, pady=4)
        bar = ttk.Frame(gd); bar.pack(fill=tk.X)
        ttk.Label(bar, text="Subject identifier:").pack(side=tk.LEFT)
        self.gdpr_id = ttk.Entry(bar, width=30); self.gdpr_id.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Export…", command=self._gdpr_export).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Delete (detach)", command=self._gdpr_delete).pack(side=tk.LEFT, padx=4)

        # 41 role redaction
        rr = ttk.LabelFrame(tab, text="Role-based redaction (41)", padding=6)
        rr.pack(fill=tk.X, pady=4)
        bar2 = ttk.Frame(rr); bar2.pack(fill=tk.X)
        ttk.Label(bar2, text="Role:").pack(side=tk.LEFT)
        self.rr_role = ttk.Entry(bar2, width=14); self.rr_role.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="Field:").pack(side=tk.LEFT)
        self.rr_field = ttk.Entry(bar2, width=18); self.rr_field.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="Action:").pack(side=tk.LEFT)
        self.rr_action = ttk.Combobox(bar2, state="readonly", values=("hide", "mask"), width=6)
        self.rr_action.current(0); self.rr_action.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Add rule", command=self._add_role_rule).pack(side=tk.LEFT, padx=4)

        # 42 MFA gates
        mfa = ttk.LabelFrame(tab, text="MFA gates (42)", padding=6)
        mfa.pack(fill=tk.X, pady=4)
        bar3 = ttk.Frame(mfa); bar3.pack(fill=tk.X)
        ttk.Label(bar3, text="Route:").pack(side=tk.LEFT)
        self.mfa_route = ttk.Entry(bar3, width=30); self.mfa_route.pack(side=tk.LEFT, padx=4)
        self.mfa_required = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar3, text="Required",
                        variable=self.mfa_required).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Save gate", command=self._add_mfa).pack(side=tk.LEFT, padx=4)

        # 43 retention
        ret = ttk.LabelFrame(tab, text="Retention policies (43)", padding=6)
        ret.pack(fill=tk.X, pady=4)
        bar4 = ttk.Frame(ret); bar4.pack(fill=tk.X)
        ttk.Label(bar4, text="Target:").pack(side=tk.LEFT)
        self.ret_target = ttk.Combobox(bar4, state="readonly", values=(
            "drafts", "raw_answers", "responses", "invitations",
            "anon_answers", "anon_responses",
        ), width=18)
        self.ret_target.current(0); self.ret_target.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar4, text="Keep days:").pack(side=tk.LEFT)
        self.ret_days = ttk.Spinbox(bar4, from_=1, to=3650, width=8); self.ret_days.insert(0, "365")
        self.ret_days.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar4, text="Save policy", command=self._add_retention).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar4, text="Run purge now", command=self._purge_now).pack(side=tk.LEFT, padx=4)

    def _anon_check(self):
        a = compliance.anonymity_assertion()
        self.anon_label.config(
            text="✅ safe" if a["anonymous_form_layer_safe"] else "⚠ leak detected"
        )
        self._refresh_audit()

    def _refresh_audit(self):
        self.audit_box.delete("1.0", tk.END)
        for r in compliance.audit_tail():
            self.audit_box.insert(tk.END, f"#{r['audit_id']} {r['created_at']}  "
                                          f"{r['actor']:<12} {r['action']:<24} {r['detail']}\n")

    def _gdpr_export(self):
        sid = self.gdpr_id.get().strip()
        if not sid:
            return
        packet = compliance.gdpr_export(sid)
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(packet, fh, indent=2, default=str)
        messagebox.showinfo("GDPR", f"Wrote {path}")
        self._refresh_audit()

    def _gdpr_delete(self):
        sid = self.gdpr_id.get().strip()
        if not sid:
            return
        res = compliance.gdpr_delete(sid)
        messagebox.showinfo("GDPR", json.dumps(res, indent=2))
        self._refresh_audit()

    def _add_role_rule(self):
        try:
            compliance.set_role_redaction(
                self.rr_role.get().strip(), self.rr_field.get().strip(),
                self.rr_action.get())
            messagebox.showinfo("Redaction", "Rule added.")
        except ValueError as e:
            messagebox.showerror("Redaction", str(e))

    def _add_mfa(self):
        if self.mfa_route.get().strip():
            compliance.require_mfa(self.mfa_route.get().strip(),
                                   self.mfa_required.get())
            messagebox.showinfo("MFA", "Gate saved.")

    def _add_retention(self):
        try:
            compliance.set_retention(self.ret_target.get(), int(self.ret_days.get()))
            messagebox.showinfo("Retention", "Policy saved.")
        except ValueError as e:
            messagebox.showerror("Retention", str(e))

    def _purge_now(self):
        res = compliance.purge_due()
        messagebox.showinfo("Purge", json.dumps(res, indent=2))

    # ============================================================ 44-50
    def _build_admin_tab(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Admin Ops")

        # 44 import
        imp = ttk.LabelFrame(tab, text="Bulk import (44)", padding=6)
        imp.pack(fill=tk.X, pady=4)
        ttk.Button(imp, text="Import CSV file…",
                   command=self._import_csv).pack(side=tk.LEFT)
        self.import_label = ttk.Label(imp, text="—"); self.import_label.pack(side=tk.LEFT, padx=12)

        # 45 approvals
        appr = ttk.LabelFrame(tab, text="Approval workflow (45)", padding=6)
        appr.pack(fill=tk.X, pady=4)
        bar = ttk.Frame(appr); bar.pack(fill=tk.X)
        ttk.Label(bar, text="Stage:").pack(side=tk.LEFT)
        self.appr_stage = ttk.Combobox(bar, state="readonly",
                                       values=("draft", "review", "approved", "rejected"), width=12)
        self.appr_stage.current(1); self.appr_stage.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Comment:").pack(side=tk.LEFT)
        self.appr_comment = ttk.Entry(bar, width=40); self.appr_comment.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Advance template", command=self._advance_approval).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Show history", command=self._show_approvals).pack(side=tk.LEFT, padx=4)
        self.appr_box = scrolledtext.ScrolledText(appr, height=4, font=("TkFixedFont", 9))
        self.appr_box.pack(fill=tk.X, pady=4)

        # 46 a/b
        ab = ttk.LabelFrame(tab, text="A/B test wording (46)", padding=6)
        ab.pack(fill=tk.X, pady=4)
        bar2 = ttk.Frame(ab); bar2.pack(fill=tk.X)
        ttk.Label(bar2, text="Question ID:").pack(side=tk.LEFT)
        self.ab_qid = ttk.Entry(bar2, width=8); self.ab_qid.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="Variant A:").pack(side=tk.LEFT)
        self.ab_a = ttk.Entry(bar2, width=30); self.ab_a.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar2, text="Variant B:").pack(side=tk.LEFT)
        self.ab_b = ttk.Entry(bar2, width=30); self.ab_b.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Create test", command=self._create_ab).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Results for…", command=self._show_ab).pack(side=tk.LEFT, padx=4)
        self.ab_box = scrolledtext.ScrolledText(ab, height=4, font=("TkFixedFont", 9))
        self.ab_box.pack(fill=tk.X, pady=4)

        # 47 trash
        tr = ttk.LabelFrame(tab, text="Soft-delete trash (47)", padding=6)
        tr.pack(fill=tk.X, pady=4)
        bar3 = ttk.Frame(tr); bar3.pack(fill=tk.X)
        ttk.Button(bar3, text="Soft-delete current template",
                   command=self._soft_delete_tpl).pack(side=tk.LEFT)
        ttk.Button(bar3, text="Soft-delete current evaluation",
                   command=self._soft_delete_eval).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar3, text="Refresh", command=self._refresh_trash).pack(side=tk.LEFT, padx=4)
        cols = ("kind", "id", "name", "deleted_at")
        self.trash_tree = ttk.Treeview(tr, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (90, 60, 360, 160)):
            self.trash_tree.heading(c, text=c.title()); self.trash_tree.column(c, width=w, anchor=tk.W)
        self.trash_tree.pack(fill=tk.X, pady=4)
        ttk.Button(tr, text="Restore selected",
                   command=self._restore_selected).pack(anchor=tk.W)

        # 48 print/pdf + 49 bias linter + 50 pulses side by side
        bottom = ttk.Frame(tab); bottom.pack(fill=tk.BOTH, expand=True, pady=4)

        pdf = ttk.LabelFrame(bottom, text="Print / PDF report (48)", padding=6)
        pdf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        ttk.Button(pdf, text="Preview report",
                   command=self._preview_report).pack(anchor=tk.W)
        ttk.Button(pdf, text="Save report…",
                   command=self._save_report).pack(anchor=tk.W, pady=2)
        self.pdf_box = scrolledtext.ScrolledText(pdf, height=14, font=("TkFixedFont", 9))
        self.pdf_box.pack(fill=tk.BOTH, expand=True)

        bias = ttk.LabelFrame(bottom, text="Bias-language linter (49)", padding=6)
        bias.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        ttk.Button(bias, text="Lint current template",
                   command=self._lint_template).pack(anchor=tk.W)
        ttk.Label(bias, text="Ad-hoc text:").pack(anchor=tk.W)
        self.bias_text = scrolledtext.ScrolledText(bias, height=3); self.bias_text.pack(fill=tk.X)
        ttk.Button(bias, text="Lint text",
                   command=self._lint_text).pack(anchor=tk.W, pady=2)
        cols = ("category", "snippet", "suggestion")
        self.bias_tree = ttk.Treeview(bias, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (130, 230, 360)):
            self.bias_tree.heading(c, text=c.title()); self.bias_tree.column(c, width=w, anchor=tk.W)
        self.bias_tree.pack(fill=tk.BOTH, expand=True)

        pul = ttk.LabelFrame(bottom, text="Pulse / micro-surveys (50)", padding=6)
        pul.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        bar4 = ttk.Frame(pul); bar4.pack(fill=tk.X)
        ttk.Label(bar4, text="Module:").pack(side=tk.LEFT)
        self.pul_mod = ttk.Entry(bar4, width=12); self.pul_mod.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar4, text="Cadence d:").pack(side=tk.LEFT)
        self.pul_cad = ttk.Spinbox(bar4, from_=1, to=90, width=4); self.pul_cad.insert(0, "7")
        self.pul_cad.pack(side=tk.LEFT, padx=4)
        ttk.Label(bar4, text="Question:").pack(side=tk.LEFT)
        self.pul_q = ttk.Entry(bar4, width=40); self.pul_q.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar4, text="Add pulse",
                   command=self._add_pulse).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar4, text="Refresh",
                   command=self._refresh_pulses).pack(side=tk.LEFT, padx=4)
        cols = ("id", "module", "question", "cadence", "next_run", "active")
        self.pul_tree = ttk.Treeview(pul, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (50, 80, 320, 70, 160, 60)):
            self.pul_tree.heading(c, text=c.title()); self.pul_tree.column(c, width=w, anchor=tk.W)
        self.pul_tree.pack(fill=tk.BOTH, expand=True)

        self._refresh_pulses()

    # ---- admin handlers
    def _import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All", "*")])
        if not path:
            return
        try:
            res = admin_svc.import_csv(path)
        except Exception as e:
            messagebox.showerror("Import", str(e)); return
        self.import_label.config(text=f"seen={res['seen']}  imported={res['imported']}  errored={res['errored']}")

    def _advance_approval(self):
        tpl = self._need_tpl()
        if not tpl:
            return
        try:
            admin_svc.set_stage(tpl, self.appr_stage.get(),
                                actor=self.user, comment=self.appr_comment.get().strip())
        except ValueError as e:
            messagebox.showerror("Approval", str(e)); return
        self._show_approvals()

    def _show_approvals(self):
        tpl = self._need_tpl()
        if not tpl:
            return
        self.appr_box.delete("1.0", tk.END)
        for r in admin_svc.approval_history(tpl):
            self.appr_box.insert(tk.END,
                f"{r['updated_at']}  {r['stage']:<10} by {r.get('actor') or '—':<14} {r.get('comment') or ''}\n")
        self.appr_box.insert(tk.END, f"\nCurrent stage: {admin_svc.current_stage(tpl)}")

    def _create_ab(self):
        try:
            ab = admin_svc.create_ab_test(int(self.ab_qid.get()),
                                          self.ab_a.get(), self.ab_b.get())
            messagebox.showinfo("A/B", f"Created test #{ab}.")
        except ValueError as e:
            messagebox.showerror("A/B", str(e))

    def _show_ab(self):
        try:
            ab = int(self.ab_qid.get())  # treat field as ab_id when results requested
        except ValueError:
            return
        try:
            res = admin_svc.ab_results(ab)
        except ValueError as e:
            messagebox.showerror("A/B", str(e)); return
        self.ab_box.delete("1.0", tk.END)
        self.ab_box.insert("1.0", json.dumps(res, indent=2, default=str))

    def _soft_delete_tpl(self):
        tpl = self._need_tpl()
        if tpl:
            admin_svc.soft_delete_template(tpl)
            self._refresh_trash()

    def _soft_delete_eval(self):
        eid = self._need_eval()
        if eid:
            admin_svc.soft_delete_evaluation(eid)
            self._refresh_trash()

    def _refresh_trash(self):
        for i in self.trash_tree.get_children():
            self.trash_tree.delete(i)
        data = admin_svc.list_trash()
        for t in data["templates"]:
            self.trash_tree.insert("", tk.END, values=(
                "template", t["template_id"], t["template_name"], t["deleted_at"]))
        for e in data["evaluations"]:
            self.trash_tree.insert("", tk.END, values=(
                "evaluation", e["evaluation_id"], e["module_code"], e["deleted_at"]))

    def _restore_selected(self):
        sel = self.trash_tree.selection()
        if not sel:
            return
        kind, _id = self.trash_tree.item(sel[0])["values"][:2]
        if kind == "template":
            admin_svc.restore_template(int(_id))
        else:
            admin_svc.restore_evaluation(int(_id))
        self._refresh_trash()

    def _preview_report(self):
        eid = self._need_eval()
        if not eid:
            return
        try:
            self.pdf_box.delete("1.0", tk.END)
            self.pdf_box.insert("1.0", admin_svc.render_results_text(eid))
        except ValueError as e:
            messagebox.showerror("Report", str(e))

    def _save_report(self):
        eid = self._need_eval()
        if not eid:
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf"), ("Text", "*.txt")])
        if not path:
            return
        try:
            out = admin_svc.export_results_pdf(eid, path)
            messagebox.showinfo("Report", f"Wrote {out}")
        except ValueError as e:
            messagebox.showerror("Report", str(e))

    def _lint_template(self):
        tpl = self._need_tpl()
        if not tpl:
            return
        for i in self.bias_tree.get_children():
            self.bias_tree.delete(i)
        for f in admin_svc.lint_template(tpl):
            self.bias_tree.insert("", tk.END,
                                  values=(f["category"], f["snippet"], f["suggestion"]))

    def _lint_text(self):
        for i in self.bias_tree.get_children():
            self.bias_tree.delete(i)
        for f in admin_svc.lint_text(self.bias_text.get("1.0", tk.END)):
            self.bias_tree.insert("", tk.END,
                                  values=(f["category"], f["snippet"], f["suggestion"]))

    def _add_pulse(self):
        mod = self.pul_mod.get().strip()
        q = self.pul_q.get().strip()
        if not (mod and q):
            return
        try:
            cad = int(self.pul_cad.get())
        except ValueError:
            return
        admin_svc.create_pulse(mod, q, cadence_days=cad)
        self.pul_mod.delete(0, tk.END); self.pul_q.delete(0, tk.END)
        self._refresh_pulses()

    def _refresh_pulses(self):
        for i in self.pul_tree.get_children():
            self.pul_tree.delete(i)
        for p in admin_svc.list_pulses():
            self.pul_tree.insert("", tk.END, values=(
                p["pulse_id"], p["module_code"], (p["question_text"] or "")[:80],
                p["cadence_days"], p["next_run"], "yes" if p["active"] else "no"))


def launch_operations_gui(parent=None, auth=None):
    return OperationsGUI(parent, auth)


__all__ = ["OperationsGUI", "launch_operations_gui"]
