"""Question-level analysis GUI frame."""
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.question_analysis.services.question_analysis_service import (
    QuestionAnalysisService,
)
from education_system.college_system.core.i18n import t


class QuestionAnalysisFrame(tk.Frame):
    """GUI for question-level assessment analysis."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = QuestionAnalysisService(db_path)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("question_analysis.title", "Question-Level Analysis"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_papers_tab()
        self._build_questions_tab()
        self._build_scores_tab()
        self._build_analysis_tab()
        self._build_weaknesses_tab()

    # -- Assessment Papers Tab --

    def _build_papers_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("question_analysis.papers_tab", "Assessment Papers"))

        form = tk.LabelFrame(tab, text=t("question_analysis.add_paper", "Add Paper"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Course ID", "Title", "Total Marks", "Exam Board", "Paper Code", "Date", "Academic Year"]
        self._paper_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=20).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._paper_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_paper).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_papers).pack(side="left", padx=5)

        cols = ("id", "course_id", "title", "total_marks", "exam_board", "paper_code", "assessment_date", "academic_year")
        self._papers_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._papers_tree.heading(c, text=c.replace("_", " ").title())
            self._papers_tree.column(c, width=100)
        self._papers_tree.pack(fill="both", expand=True, padx=10, pady=5)

        sb = ttk.Scrollbar(tab, orient="vertical", command=self._papers_tree.yview)
        self._papers_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _add_paper(self):
        try:
            v = self._paper_vars
            self._svc.create_paper(
                course_id=int(v["Course ID"].get()),
                title=v["Title"].get(),
                total_marks=int(v["Total Marks"].get()),
                exam_board=v["Exam Board"].get() or None,
                paper_code=v["Paper Code"].get() or None,
                assessment_date=v["Date"].get() or None,
                academic_year=v["Academic Year"].get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("question_analysis.paper_added", "Paper added."))
            self._load_papers()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_papers(self):
        for row in self._papers_tree.get_children():
            self._papers_tree.delete(row)
        try:
            for p in self._svc.list_papers():
                self._papers_tree.insert("", "end", values=(
                    p["id"], p["course_id"], p["title"], p["total_marks"],
                    p.get("exam_board", ""), p.get("paper_code", ""),
                    p.get("assessment_date", ""), p.get("academic_year", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Question Setup Tab --

    def _build_questions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("question_analysis.questions_tab", "Question Setup"))

        form = tk.LabelFrame(tab, text=t("question_analysis.add_question", "Add Question"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Paper ID", "Question No", "Topic", "Max Marks", "Subtopic", "Skill Type", "Difficulty", "Spec Ref"]
        self._q_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=18).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._q_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_question).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.load", "Load"), command=self._load_questions).pack(side="left", padx=5)

        cols = ("id", "paper_id", "question_number", "topic", "subtopic", "max_marks", "skill_type", "difficulty")
        self._q_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._q_tree.heading(c, text=c.replace("_", " ").title())
            self._q_tree.column(c, width=100)
        self._q_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_question(self):
        try:
            v = self._q_vars
            self._svc.add_question(
                paper_id=int(v["Paper ID"].get()),
                question_number=v["Question No"].get(),
                topic=v["Topic"].get(),
                max_marks=int(v["Max Marks"].get()),
                subtopic=v["Subtopic"].get() or None,
                skill_type=v["Skill Type"].get() or None,
                difficulty=v["Difficulty"].get() or None,
                specification_ref=v["Spec Ref"].get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("question_analysis.question_added", "Question added."))
            self._load_questions()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_questions(self):
        for row in self._q_tree.get_children():
            self._q_tree.delete(row)
        try:
            pid = self._q_vars["Paper ID"].get()
            if not pid:
                return
            for q in self._svc.list_questions(int(pid)):
                self._q_tree.insert("", "end", values=(
                    q["id"], q["paper_id"], q["question_number"], q["topic"],
                    q.get("subtopic", ""), q["max_marks"],
                    q.get("skill_type", ""), q.get("difficulty", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Score Entry Tab --

    def _build_scores_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("question_analysis.scores_tab", "Score Entry"))

        form = tk.LabelFrame(tab, text=t("question_analysis.record_score", "Record Score"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Question ID", "Student ID", "Marks Awarded"]
        self._score_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=0, column=i * 2, padx=5, pady=5, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=15).grid(row=0, column=i * 2 + 1, padx=5, pady=5)
            self._score_vars[lbl] = var

        tk.Button(form, text=t("common.save", "Save"), command=self._save_score).grid(row=0, column=6, padx=10)

        # Bulk entry section
        bulk = tk.LabelFrame(tab, text=t("question_analysis.bulk_entry", "Bulk Score Entry"), bg="#ecf0f1")
        bulk.pack(fill="x", padx=10, pady=5)

        tk.Label(bulk, text="Paper ID:", bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._bulk_paper_var = tk.StringVar()
        tk.Entry(bulk, textvariable=self._bulk_paper_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(bulk, text="Format: student_id,question_number,marks (one per line)", bg="#ecf0f1").grid(row=1, column=0, columnspan=4, padx=5, sticky="w")
        self._bulk_text = tk.Text(bulk, height=8, width=60)
        self._bulk_text.grid(row=2, column=0, columnspan=4, padx=5, pady=5)
        tk.Button(bulk, text=t("question_analysis.bulk_save", "Bulk Save"), command=self._bulk_save).grid(row=3, column=0, pady=5)

    def _save_score(self):
        try:
            v = self._score_vars
            self._svc.record_score(
                question_id=int(v["Question ID"].get()),
                student_id=int(v["Student ID"].get()),
                marks_awarded=int(v["Marks Awarded"].get()),
            )
            messagebox.showinfo(t("common.success", "Success"), t("question_analysis.score_saved", "Score saved."))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _bulk_save(self):
        try:
            pid = int(self._bulk_paper_var.get())
            text = self._bulk_text.get("1.0", "end").strip()
            if not text:
                return
            scores = []
            for line in text.split("\n"):
                parts = line.strip().split(",")
                if len(parts) == 3:
                    scores.append({
                        "student_id": int(parts[0].strip()),
                        "question_number": parts[1].strip(),
                        "marks": int(parts[2].strip()),
                    })
            count = self._svc.bulk_record_scores(pid, scores)
            messagebox.showinfo(t("common.success", "Success"), f"{count} scores recorded.")
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Analysis Dashboard Tab --

    def _build_analysis_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("question_analysis.analysis_tab", "Analysis Dashboard"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)
        tk.Label(ctrl, text="Paper ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._analysis_paper_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._analysis_paper_var, width=10).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("question_analysis.analyse", "Analyse"), command=self._run_analysis).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("question_analysis.skill_analysis", "By Skill"), command=self._run_skill_analysis).pack(side="left", padx=5)

        cols = ("question_number", "topic", "max_marks", "num_students", "avg_marks", "avg_pct", "facility_index")
        self._analysis_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self._analysis_tree.heading(c, text=c.replace("_", " ").title())
            self._analysis_tree.column(c, width=110)
        self._analysis_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _run_analysis(self):
        for row in self._analysis_tree.get_children():
            self._analysis_tree.delete(row)
        try:
            pid = int(self._analysis_paper_var.get())
            for r in self._svc.get_question_analysis(pid):
                self._analysis_tree.insert("", "end", values=(
                    r["question_number"], r.get("topic", ""), r["max_marks"],
                    r["num_students"], round(r["avg_marks"], 2),
                    r["avg_pct"], r["facility_index"],
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _run_skill_analysis(self):
        for row in self._analysis_tree.get_children():
            self._analysis_tree.delete(row)
        try:
            pid = int(self._analysis_paper_var.get())
            for r in self._svc.get_skill_analysis(pid):
                self._analysis_tree.insert("", "end", values=(
                    "", r.get("skill_type", ""), "", r["num_questions"],
                    r.get("avg_marks_per_q", ""), r.get("avg_pct", ""), "",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Topic Weaknesses Tab --

    def _build_weaknesses_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("question_analysis.weaknesses_tab", "Topic Weaknesses"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)
        tk.Label(ctrl, text="Paper ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._weak_paper_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._weak_paper_var, width=10).pack(side="left", padx=5)
        tk.Label(ctrl, text="Threshold %:", bg="#ecf0f1").pack(side="left", padx=5)
        self._threshold_var = tk.StringVar(value="50")
        tk.Entry(ctrl, textvariable=self._threshold_var, width=5).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("question_analysis.find_weaknesses", "Find Weaknesses"), command=self._find_weaknesses).pack(side="left", padx=5)

        cols = ("topic", "total_max", "avg_marks_per_q", "avg_pct", "num_questions")
        self._weak_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._weak_tree.heading(c, text=c.replace("_", " ").title())
            self._weak_tree.column(c, width=130)
        self._weak_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _find_weaknesses(self):
        for row in self._weak_tree.get_children():
            self._weak_tree.delete(row)
        try:
            pid = int(self._weak_paper_var.get())
            threshold = float(self._threshold_var.get())
            for r in self._svc.get_cohort_weaknesses(pid, threshold):
                self._weak_tree.insert("", "end", values=(
                    r.get("topic", ""), r.get("total_max", ""),
                    r.get("avg_marks_per_q", ""), r.get("avg_pct", ""),
                    r.get("num_questions", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def refresh(self):
        """Refresh all data."""
        self._load_papers()
