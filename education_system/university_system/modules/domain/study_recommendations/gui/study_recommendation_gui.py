import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StudyRecommendationGUI:
    def __init__(self, parent=None, auth=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Study Recommendations")
        self.root.geometry("1200x800")
        try:
            from education_system.university_system.modules.domain.study_recommendations.services.study_recommendation_service import StudyRecommendationService
            self.service = StudyRecommendationService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None

        # Get auth and student_id
        if auth:
            self.auth = auth
        else:
            try:
                from education_system.university_system.infrastructure.shared_context import get_auth
                self.auth = get_auth()
            except Exception:
                self.auth = None

        self.student_id = self._get_student_id()
        self.setup_ui()

    def _get_student_id(self):
        """Get the current student's ID."""
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            cu = self.auth.current_user
            # Try student_id, then id, then username
            for key in ('student_id', 'id', 'username'):
                val = cu.get(key)
                if val:
                    return str(val)
        return None

    def setup_ui(self):
        if not self.student_id:
            ttk.Label(self.root, text="Please log in to access study recommendations.",
                     font=('Arial', 14)).pack(pady=40)
            return

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_recommendations_tab(notebook)
        self._create_study_profile_tab(notebook)
        self._create_study_log_tab(notebook)
        self._create_stats_tab(notebook)

    # -------------------------------------------------------- Recommendations
    def _create_recommendations_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Recommendations")

        cols = ("module", "type", "title", "priority")
        self.recs_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.recs_tree.heading(c, text=c.replace("_", " ").title())
            self.recs_tree.column(c, width=180)
        self.recs_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Generate", command=self._generate_recommendations).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Mark Complete", command=self._mark_complete).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_recommendations).pack(side=tk.RIGHT, padx=2)

        self._refresh_recommendations()

    def _refresh_recommendations(self):
        for row in self.recs_tree.get_children():
            self.recs_tree.delete(row)
        if not self.service or not self.student_id:
            return
        try:
            recs = self.service.get_recommendations(self.student_id)
            for r in recs:
                self.recs_tree.insert("", tk.END, values=(
                    r.get("module_code", ""), r.get("recommendation_type", ""),
                    r.get("title", ""), r.get("priority", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading recommendations: {e}")

    def _generate_recommendations(self):
        if not self.student_id:
            return
        try:
            self.service.generate_recommendations(self.student_id)
            self._refresh_recommendations()
            messagebox.showinfo("Success", "Recommendations generated.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _mark_complete(self):
        sel = self.recs_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a recommendation first.", parent=self.root)
            return
        values = self.recs_tree.item(sel[0], "values")
        try:
            # Find the recommendation by title to get its ID
            recs = self.service.get_recommendations(self.student_id, active_only=True)
            for r in recs:
                if r.get("title") == values[2]:
                    self.service.mark_recommendation_completed(r['id'])
                    break
            self._refresh_recommendations()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ---------------------------------------------------------- Study Profile
    def _create_study_profile_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Study Profile")

        profile_frame = ttk.LabelFrame(tab, text="Your Study Profile")
        profile_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(profile_frame, text="Learning Style:").grid(
            row=0, column=0, padx=10, pady=8, sticky=tk.W)
        self.learning_style_var = tk.StringVar()
        ttk.Combobox(profile_frame, textvariable=self.learning_style_var, values=[
            "visual", "auditory", "reading", "kinesthetic", "mixed",
        ], state="readonly", width=25).grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(profile_frame, text="Study Hours per Week:").grid(
            row=1, column=0, padx=10, pady=8, sticky=tk.W)
        self.hours_var = tk.StringVar(value="20")
        ttk.Entry(profile_frame, textvariable=self.hours_var, width=27).grid(
            row=1, column=1, padx=10, pady=8)

        ttk.Label(profile_frame, text="Strengths:").grid(
            row=2, column=0, padx=10, pady=(8, 0), sticky=tk.NW)
        self.strengths_text = tk.Text(profile_frame, height=4, width=40)
        self.strengths_text.grid(row=2, column=1, padx=10, pady=8)

        ttk.Label(profile_frame, text="Weaknesses:").grid(
            row=3, column=0, padx=10, pady=(8, 0), sticky=tk.NW)
        self.weaknesses_text = tk.Text(profile_frame, height=4, width=40)
        self.weaknesses_text.grid(row=3, column=1, padx=10, pady=8)

        ttk.Button(profile_frame, text="Save Profile", command=self._save_profile).grid(
            row=4, column=0, columnspan=2, pady=15)

        self._load_profile()

    def _load_profile(self):
        if not self.service or not self.student_id:
            return
        try:
            profile = self.service.get_profile(self.student_id)
            if profile:
                self.learning_style_var.set(profile.get("learning_style", "mixed"))
                self.hours_var.set(str(profile.get("study_hours_per_week", 20)))
                self.strengths_text.delete("1.0", tk.END)
                self.strengths_text.insert("1.0", profile.get("strengths", "") or "")
                self.weaknesses_text.delete("1.0", tk.END)
                self.weaknesses_text.insert("1.0", profile.get("weaknesses", "") or "")
        except Exception as e:
            logger.error(f"Error loading profile: {e}")

    def _save_profile(self):
        if not self.student_id:
            return
        try:
            hours = float(self.hours_var.get())
        except ValueError:
            messagebox.showwarning("Validation", "Hours must be a number.", parent=self.root)
            return
        try:
            self.service.create_profile(
                student_id=self.student_id,
                learning_style=self.learning_style_var.get() or "mixed",
                study_hours_per_week=hours,
                strengths=self.strengths_text.get("1.0", tk.END).strip(),
                weaknesses=self.weaknesses_text.get("1.0", tk.END).strip(),
            )
            messagebox.showinfo("Success", "Profile saved.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ------------------------------------------------------------- Study Log
    def _create_study_log_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Study Log")

        cols = ("date", "module", "topic", "duration", "rating")
        self.log_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.log_tree.heading(c, text=c.replace("_", " ").title())
            self.log_tree.column(c, width=150)
        self.log_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Log Session", command=self._log_session).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_log).pack(side=tk.RIGHT, padx=2)

        self._refresh_log()

    def _refresh_log(self):
        for row in self.log_tree.get_children():
            self.log_tree.delete(row)
        if not self.service or not self.student_id:
            return
        try:
            sessions = self.service.get_study_history(self.student_id)
            for s in sessions:
                self.log_tree.insert("", tk.END, values=(
                    s.get("studied_at", "")[:10] if s.get("studied_at") else "",
                    s.get("module_code", ""),
                    s.get("topic", ""),
                    f"{s.get('duration_minutes', 0)} min",
                    s.get("effectiveness_rating", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading study log: {e}")

    def _log_session(self):
        if not self.student_id:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Log Study Session")
        dlg.geometry("450x400")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Date (YYYY-MM-DD):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dlg, textvariable=date_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Module:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        module_var = tk.StringVar()
        module_combo = ttk.Combobox(dlg, textvariable=module_var, state='readonly')
        module_combo.pack(fill=tk.X, padx=10)

        # Load modules: student's enrolled modules, or all if admin
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            role = ''
            if self.auth and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()

            with get_connection() as conn:
                if role == 'admin':
                    rows = conn.execute(
                        "SELECT module_code, module_name FROM modules ORDER BY module_code"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT m.module_code, m.module_name FROM modules m "
                        "JOIN student_modules sm ON m.module_code = sm.module_code "
                        "WHERE sm.student_id = ? ORDER BY m.module_code",
                        (self.student_id,)
                    ).fetchall()

            module_combo['values'] = [f"{r[0]} - {r[1]}" for r in rows]
        except Exception:
            pass

        ttk.Label(dlg, text="Topic:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        topic_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=topic_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Duration (minutes):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        duration_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=duration_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Effectiveness Rating (1-5):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        rating_var = tk.IntVar(value=3)
        rating_frame = ttk.Frame(dlg)
        rating_frame.pack(padx=10, anchor=tk.W)
        for v in range(1, 6):
            ttk.Radiobutton(rating_frame, text=str(v), variable=rating_var, value=v).pack(side=tk.LEFT, padx=5)

        def save():
            if not module_var.get() or not topic_var.get() or not duration_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                dur = int(duration_var.get())
            except ValueError:
                messagebox.showwarning("Validation", "Duration must be a number.", parent=dlg)
                return
            try:
                # Extract module code from "CIS0001 - Module Name" format
                module_selection = module_var.get()
                module_code = module_selection.split(' - ')[0].strip() if ' - ' in module_selection else module_selection

                self.service.log_study_session(
                    student_id=self.student_id,
                    module_code=module_code,
                    topic=topic_var.get(),
                    duration_minutes=dur,
                    effectiveness_rating=rating_var.get(),
                )
                dlg.destroy()
                self._refresh_log()
                messagebox.showinfo("Success", "Study session logged.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    # ----------------------------------------------------------------- Stats
    def _create_stats_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Stats")

        stats_frame = ttk.LabelFrame(tab, text="Study Statistics")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.stats_labels = {}
        stat_names = ["Total Hours", "Total Sessions", "Avg Effectiveness", "Current Streak"]
        for i, name in enumerate(stat_names):
            ttk.Label(stats_frame, text=f"{name}:", font=("", 12, "bold")).grid(
                row=i, column=0, padx=20, pady=12, sticky=tk.W)
            lbl = ttk.Label(stats_frame, text="--", font=("", 12))
            lbl.grid(row=i, column=1, padx=20, pady=12, sticky=tk.W)
            self.stats_labels[name] = lbl

        ttk.Button(stats_frame, text="Refresh Statistics", command=self._refresh_stats).grid(
            row=len(stat_names), column=0, columnspan=2, pady=15)

        self._refresh_stats()

    def _refresh_stats(self):
        if not self.service or not self.student_id:
            return
        try:
            stats = self.service.get_study_stats(self.student_id)
            self.stats_labels["Total Hours"].config(
                text=f"{stats.get('total_hours', 0):.1f} hours")
            self.stats_labels["Total Sessions"].config(
                text=str(stats.get("total_sessions", 0)))
            self.stats_labels["Avg Effectiveness"].config(
                text=f"{stats.get('avg_effectiveness', 0):.1f} / 5.0")

            streak = self.service.get_study_streak(self.student_id)
            self.stats_labels["Current Streak"].config(
                text=f"{streak} days")
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
