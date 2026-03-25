import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AchievementBadgeGUI:
    def __init__(self, parent=None, auth=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Achievement Badges")
        self.root.geometry("1200x800")
        try:
            from education_system.university_system.modules.domain.achievement_badges.services.achievement_badge_service import AchievementBadgeService
            self.service = AchievementBadgeService()
        except Exception as e:
            logger.error(f"Service init error: {e}")
            self.service = None

        self.auth = auth
        if not self.auth:
            try:
                from education_system.university_system.infrastructure.shared_context import get_auth
                self.auth = get_auth()
            except Exception:
                pass

        # Resolve student_id from auth
        self.student_id = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user = self.auth.current_user
            if isinstance(user, dict):
                self.student_id = user.get('student_id') or user.get('username', '')

        self.setup_ui()

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_my_badges_tab(notebook)
        self._create_available_badges_tab(notebook)
        self._create_leaderboard_tab(notebook)
        self._create_manage_tab(notebook)

    # ------------------------------------------------------------- My Badges
    def _create_my_badges_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="My Badges")

        self.badge_count_label = ttk.Label(tab, text="Total Badges Earned: 0",
                                            font=("", 12, "bold"))
        self.badge_count_label.pack(padx=10, pady=10)

        cols = ("name", "category", "points", "date")
        self.my_badges_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.my_badges_tree.heading(c, text=c.replace("_", " ").title())
            self.my_badges_tree.column(c, width=180)
        self.my_badges_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_my_badges).pack(side=tk.RIGHT, padx=2)

        self._refresh_my_badges()

    def _refresh_my_badges(self):
        for row in self.my_badges_tree.get_children():
            self.my_badges_tree.delete(row)
        if not self.service:
            return
        try:
            badges = self.service.get_student_badges(self.student_id)
            self.badge_count_label.config(text=f"Total Badges Earned: {len(badges)}")
            for b in badges:
                self.my_badges_tree.insert("", tk.END, values=(
                    b.get("name", ""), b.get("category", ""),
                    b.get("points", 0), b.get("awarded_at") or b.get("date", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading my badges: {e}")

    # -------------------------------------------------------- Available Badges
    def _create_available_badges_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Available Badges")

        cols = ("name", "category", "criteria", "points")
        self.available_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.available_tree.heading(c, text=c.replace("_", " ").title())
            self.available_tree.column(c, width=180)
        self.available_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_available).pack(side=tk.RIGHT, padx=2)

        self._refresh_available()

    def _refresh_available(self):
        for row in self.available_tree.get_children():
            self.available_tree.delete(row)
        if not self.service:
            return
        try:
            badges = self.service.list_badges()
            for b in badges:
                self.available_tree.insert("", tk.END, values=(
                    b.get("name", ""), b.get("category", ""),
                    b.get("criteria", ""), b.get("points", 0),
                ))
        except Exception as e:
            logger.error(f"Error loading available badges: {e}")

    # ----------------------------------------------------------- Leaderboard
    def _create_leaderboard_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Leaderboard")

        cols = ("rank", "student", "points", "badges")
        self.leaderboard_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.leaderboard_tree.heading(c, text=c.replace("_", " ").title())
            self.leaderboard_tree.column(c, width=180)
        self.leaderboard_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_leaderboard).pack(side=tk.RIGHT, padx=2)

        self._refresh_leaderboard()

    def _refresh_leaderboard(self):
        for row in self.leaderboard_tree.get_children():
            self.leaderboard_tree.delete(row)
        if not self.service:
            return
        try:
            entries = self.service.get_leaderboard()
            for entry in entries:
                self.leaderboard_tree.insert("", tk.END, values=(
                    entry.get("rank", ""), entry.get("student", ""),
                    entry.get("points", 0), entry.get("badges", 0),
                ))
        except Exception as e:
            logger.error(f"Error loading leaderboard: {e}")

    # ---------------------------------------------------------------- Manage
    def _create_manage_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Manage")

        cols = ("badge_id", "name", "category", "criteria", "points")
        self.manage_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.manage_tree.heading(c, text=c.replace("_", " ").title())
            self.manage_tree.column(c, width=150)
        self.manage_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Create", command=self._create_badge).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Award", command=self._award_badge).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_manage).pack(side=tk.RIGHT, padx=2)

        self._refresh_manage()

    def _refresh_manage(self):
        for row in self.manage_tree.get_children():
            self.manage_tree.delete(row)
        if not self.service:
            return
        try:
            badges = self.service.list_badges(active_only=False)
            for b in badges:
                self.manage_tree.insert("", tk.END, values=(
                    b.get("id") or b.get("badge_id", ""), b.get("name", ""),
                    b.get("category", ""), b.get("criteria", ""),
                    b.get("points", 0),
                ))
        except Exception as e:
            logger.error(f"Error loading badge definitions: {e}")

    def _create_badge(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Create Badge")
        dlg.geometry("450x400")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Name:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=name_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Category:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        cat_var = tk.StringVar()
        ttk.Combobox(dlg, textvariable=cat_var, values=[
            "Academic", "Attendance", "Community", "Leadership",
            "Research", "Sports", "Volunteering",
        ], state="readonly").pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Criteria:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        criteria_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=criteria_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="Points:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        points_var = tk.StringVar(value="10")
        ttk.Entry(dlg, textvariable=points_var).pack(fill=tk.X, padx=10)

        def save():
            if not name_var.get() or not cat_var.get() or not criteria_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                pts = int(points_var.get())
            except ValueError:
                messagebox.showwarning("Validation", "Points must be a number.", parent=dlg)
                return
            try:
                self.service.create_badge(
                    name=name_var.get(),
                    category=cat_var.get(),
                    criteria=criteria_var.get(),
                    points=pts,
                )
                dlg.destroy()
                self._refresh_manage()
                self._refresh_available()
                messagebox.showinfo("Success", "Badge created.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _award_badge(self):
        sel = self.manage_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a badge first.", parent=self.root)
            return
        values = self.manage_tree.item(sel[0], "values")

        dlg = tk.Toplevel(self.root)
        dlg.title("Award Badge")
        dlg.geometry("400x200")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Badge: {values[1]}", font=("", 10, "bold")).pack(padx=10, pady=10)

        ttk.Label(dlg, text="Student ID:").pack(padx=10, anchor=tk.W)
        student_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=student_var).pack(fill=tk.X, padx=10)

        def award():
            if not student_var.get():
                messagebox.showwarning("Validation", "Enter a student ID.", parent=dlg)
                return
            try:
                self.service.award_badge(values[0], student_var.get())
                dlg.destroy()
                messagebox.showinfo("Success", f"Badge '{values[1]}' awarded.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Award", command=award).pack(pady=15)
