import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StudentAppGUI:
    def __init__(self, parent=None, auth=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Student App")
        self.root.geometry("1200x800")
        try:
            from education_system.university_system.modules.domain.student_affairs.student_app.services.student_app_service import StudentAppService
            self.service = StudentAppService()
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
        self._create_dashboard_tab(notebook)
        self._create_notifications_tab(notebook)
        self._create_preferences_tab(notebook)
        self._create_quick_links_tab(notebook)

    # -------------------------------------------------------------- Dashboard
    def _create_dashboard_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Dashboard")

        # Welcome
        self.welcome_label = ttk.Label(tab, text="Welcome, Student!", font=("", 16, "bold"))
        self.welcome_label.pack(padx=10, pady=(15, 5))

        content = ttk.Frame(tab)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Today's Timetable
        tt_frame = ttk.LabelFrame(content, text="Today's Timetable")
        tt_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        cols = ("time", "module", "room", "lecturer")
        self.timetable_tree = ttk.Treeview(tt_frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.timetable_tree.heading(c, text=c.replace("_", " ").title())
            self.timetable_tree.column(c, width=120)
        self.timetable_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Right panel: grades + unread
        right = ttk.Frame(content)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        grades_frame = ttk.LabelFrame(right, text="Recent Grades")
        grades_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        grade_cols = ("module", "assessment", "grade", "date")
        self.grades_tree = ttk.Treeview(grades_frame, columns=grade_cols, show="headings", height=5)
        for c in grade_cols:
            self.grades_tree.heading(c, text=c.replace("_", " ").title())
            self.grades_tree.column(c, width=100)
        self.grades_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        unread_frame = ttk.LabelFrame(right, text="Notifications")
        unread_frame.pack(fill=tk.X, pady=(5, 0))
        self.unread_label = ttk.Label(unread_frame, text="Unread notifications: 0",
                                       font=("", 11))
        self.unread_label.pack(padx=10, pady=10)

        ttk.Button(tab, text="Refresh Dashboard", command=self._refresh_dashboard).pack(pady=5)
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        for tree in (self.timetable_tree, self.grades_tree):
            for row in tree.get_children():
                tree.delete(row)
        if not self.service:
            return
        try:
            dashboard = self.service.get_student_dashboard(self.student_id)

            for item in dashboard.get("timetable", []):
                self.timetable_tree.insert("", tk.END, values=(
                    item.get("time") or item.get("start_time", ""),
                    item.get("module") or item.get("module_name", ""),
                    item.get("room", ""), item.get("lecturer", ""),
                ))

            for g in dashboard.get("grades", []):
                self.grades_tree.insert("", tk.END, values=(
                    g.get("module", "") or g.get("module_name", ""),
                    g.get("assessment", "") or g.get("assessment_name", ""),
                    g.get("grade", ""), g.get("date", "") or g.get("date_recorded", ""),
                ))

            self.unread_label.config(
                text=f"Unread notifications: {dashboard.get('unread_notifications', 0)}")
        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")

    # ---------------------------------------------------------- Notifications
    def _create_notifications_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Notifications")

        cols = ("type", "title", "message", "date", "read")
        self.notif_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.notif_tree.heading(c, text=c.replace("_", " ").title())
            self.notif_tree.column(c, width=160)
        self.notif_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Mark Read", command=self._mark_read).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Mark All Read", command=self._mark_all_read).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_notifications).pack(side=tk.RIGHT, padx=2)

        self._refresh_notifications()

    def _refresh_notifications(self):
        for row in self.notif_tree.get_children():
            self.notif_tree.delete(row)
        if not self.service:
            return
        try:
            notifs = self.service.get_notifications(self.student_id)
            for n in notifs:
                self.notif_tree.insert("", tk.END, values=(
                    n.get("type", ""), n.get("title", ""),
                    n.get("message", ""), n.get("date", ""),
                    "Yes" if n.get("read") else "No",
                ))
        except Exception as e:
            logger.error(f"Error loading notifications: {e}")

    def _mark_read(self):
        sel = self.notif_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a notification first.", parent=self.root)
            return
        values = self.notif_tree.item(sel[0], "values")
        try:
            self.service.mark_notification_read(values[1])
            self._refresh_notifications()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _mark_all_read(self):
        try:
            self.service.mark_all_notifications_read(self.student_id)
            self._refresh_notifications()
            messagebox.showinfo("Success", "All notifications marked as read.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ----------------------------------------------------------- Preferences
    def _create_preferences_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Preferences")

        pref_frame = ttk.LabelFrame(tab, text="App Preferences")
        pref_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(pref_frame, text="Theme:").grid(row=0, column=0, padx=10, pady=8, sticky=tk.W)
        self.theme_var = tk.StringVar(value="Light")
        ttk.Combobox(pref_frame, textvariable=self.theme_var, values=[
            "Light", "Dark", "System Default",
        ], state="readonly", width=20).grid(row=0, column=1, padx=10, pady=8)

        self.notif_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(pref_frame, text="Enable Notifications",
                         variable=self.notif_enabled_var).grid(
            row=1, column=0, columnspan=2, padx=10, pady=8, sticky=tk.W)

        ttk.Label(pref_frame, text="Language:").grid(row=2, column=0, padx=10, pady=8, sticky=tk.W)
        self.lang_var = tk.StringVar(value="English")
        ttk.Combobox(pref_frame, textvariable=self.lang_var, values=[
            "English", "Welsh", "French", "Spanish", "Mandarin",
        ], state="readonly", width=20).grid(row=2, column=1, padx=10, pady=8)

        ttk.Button(pref_frame, text="Save Preferences", command=self._save_preferences).grid(
            row=3, column=0, columnspan=2, pady=15)

        self._load_preferences()

    def _load_preferences(self):
        if not self.service:
            return
        try:
            prefs = self.service.get_preferences(self.student_id)
            if not prefs:
                return
            self.theme_var.set(prefs.get("theme", "Light"))
            self.notif_enabled_var.set(prefs.get("notifications_enabled", True))
            self.lang_var.set(prefs.get("language", "English"))
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")

    def _save_preferences(self):
        try:
            self.service.update_preferences(
                self.student_id,
                theme=self.theme_var.get(),
                notifications_enabled=1 if self.notif_enabled_var.get() else 0,
                language=self.lang_var.get(),
            )
            messagebox.showinfo("Success", "Preferences saved.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    # ----------------------------------------------------------- Quick Links
    def _create_quick_links_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Quick Links")

        cols = ("title", "url")
        self.links_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        self.links_tree.heading("title", text="Title")
        self.links_tree.column("title", width=300)
        self.links_tree.heading("url", text="URL")
        self.links_tree.column("url", width=500)
        self.links_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Add", command=self._add_link).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", command=self._remove_link).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_links).pack(side=tk.RIGHT, padx=2)

        self._refresh_links()

    def _refresh_links(self):
        for row in self.links_tree.get_children():
            self.links_tree.delete(row)
        if not self.service:
            return
        try:
            links = self.service.get_quick_links(self.student_id)
            for lnk in links:
                self.links_tree.insert("", tk.END, iid=str(lnk.get("id", "")), values=(
                    lnk.get("link_title") or lnk.get("title", ""),
                    lnk.get("link_url") or lnk.get("url", ""),
                ))
        except Exception as e:
            logger.error(f"Error loading quick links: {e}")

    def _add_link(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Quick Link")
        dlg.geometry("400x200")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Title:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        title_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=title_var).pack(fill=tk.X, padx=10)

        ttk.Label(dlg, text="URL:").pack(padx=10, pady=(10, 0), anchor=tk.W)
        url_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=url_var).pack(fill=tk.X, padx=10)

        def save():
            if not title_var.get() or not url_var.get():
                messagebox.showwarning("Validation", "All fields are required.", parent=dlg)
                return
            try:
                self.service.add_quick_link(
                    self.student_id, title_var.get(), url_var.get()
                )
                dlg.destroy()
                self._refresh_links()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _remove_link(self):
        sel = self.links_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a link first.", parent=self.root)
            return
        values = self.links_tree.item(sel[0], "values")
        if not messagebox.askyesno("Confirm", f"Remove link '{values[0]}'?", parent=self.root):
            return
        try:
            self.service.remove_quick_link(int(sel[0]))
            self._refresh_links()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
