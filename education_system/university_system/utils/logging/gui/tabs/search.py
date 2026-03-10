import tkinter as tk
from tkinter import ttk, messagebox
import json

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.utils.logging.gui.helpers import _t


class SearchMixin:
    """Mixin providing search tab functionality."""

    def setup_search_tab(self):
        """Setup the search tab"""
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text="🔍 " + _t("log_management.tabs.search"))

        # Search controls frame
        search_controls = ttk.LabelFrame(self.search_frame, text=_t("log_management.search.title"))
        search_controls.pack(fill=tk.X, padx=10, pady=5)

        # Create search form
        form_frame = ttk.Frame(search_controls)
        form_frame.pack(padx=10, pady=10)

        # Row 1
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text=_t("log_management.search.from_date")).pack(side=tk.LEFT, padx=(0, 5))
        self.date_from_var = tk.StringVar()
        self.date_from_entry = ttk.Entry(row1, textvariable=self.date_from_var, width=12)
        self.date_from_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row1, text=_t("log_management.search.to_date")).pack(side=tk.LEFT, padx=(0, 5))
        self.date_to_var = tk.StringVar()
        self.date_to_entry = ttk.Entry(row1, textvariable=self.date_to_var, width=12)
        self.date_to_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row1, text=_t("log_management.search.user_id")).pack(side=tk.LEFT, padx=(0, 5))
        self.user_id_var = tk.StringVar()
        self.user_id_entry = ttk.Entry(row1, textvariable=self.user_id_var, width=15)
        self.user_id_entry.pack(side=tk.LEFT)

        # Row 2
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text=_t("log_management.search.username")).pack(side=tk.LEFT, padx=(0, 5))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(row2, textvariable=self.username_var, width=15)
        self.username_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row2, text=_t("log_management.search.action")).pack(side=tk.LEFT, padx=(0, 5))
        self.action_var = tk.StringVar()
        self.action_combo = ttk.Combobox(row2, textvariable=self.action_var, width=12,
                                        values=["", "login", "logout", "create", "read", "update", "delete"])
        self.action_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row2, text=_t("log_management.search.module")).pack(side=tk.LEFT, padx=(0, 5))
        self.module_var = tk.StringVar()
        self.module_entry = ttk.Entry(row2, textvariable=self.module_var, width=15)
        self.module_entry.pack(side=tk.LEFT)

        # Row 3
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text=_t("log_management.search.status")).pack(side=tk.LEFT, padx=(0, 5))
        self.status_var = tk.StringVar()
        self.status_combo = ttk.Combobox(row3, textvariable=self.status_var, width=12,
                                        values=["", "success", "failure"])
        self.status_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row3, text=_t("log_management.search.search_text")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_text_var = tk.StringVar()
        self.search_text_entry = ttk.Entry(row3, textvariable=self.search_text_var, width=25)
        self.search_text_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row3, text=_t("log_management.search.limit")).pack(side=tk.LEFT, padx=(0, 5))
        self.limit_var = tk.StringVar(value="100")
        self.limit_entry = ttk.Entry(row3, textvariable=self.limit_var, width=8)
        self.limit_entry.pack(side=tk.LEFT)

        # Search buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="🔍 " + _t("log_management.search.buttons.search"), command=self.perform_search).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🗑️ " + _t("log_management.search.buttons.clear"), command=self.clear_search).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="💾 " + _t("log_management.search.buttons.save_search"), command=self.save_search).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📁 " + _t("log_management.search.buttons.load_search"), command=self.load_search).pack(side=tk.LEFT)

        # Results frame
        results_frame = ttk.LabelFrame(self.search_frame, text=_t("log_management.search.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Results treeview
        result_columns = ("ID", "Time", "User", "Action", "Module", "Status", "Details")
        result_column_texts = [
            _t("log_management.search.columns.id"),
            _t("log_management.search.columns.time"),
            _t("log_management.search.columns.user"),
            _t("log_management.search.columns.action"),
            _t("log_management.search.columns.module"),
            _t("log_management.search.columns.status"),
            _t("log_management.search.columns.details")
        ]
        self.search_tree = ttk.Treeview(results_frame, columns=result_columns, show="headings")

        for col, col_text in zip(result_columns, result_column_texts):
            self.search_tree.heading(col, text=col_text)
            self.search_tree.column(col, width=100)

        # Results scrollbars
        search_v_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                       command=self.search_tree.yview)
        search_h_scroll = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL,
                                       command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=search_v_scroll.set,
                                  xscrollcommand=search_h_scroll.set)

        # Pack results components
        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        search_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        search_h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Results info
        self.search_info_label = ttk.Label(results_frame, text=_t("log_management.search.no_search"))
        self.search_info_label.pack(pady=5)

        # Double-click to view details
        self.search_tree.bind("<Double-1>", self.view_log_details)

    def perform_search(self):
        """Perform log search based on form inputs"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.searching_logs"))

        try:
            # Build filters from form
            filters = {}

            if self.date_from_var.get():
                filters['date_from'] = self.date_from_var.get()
            if self.date_to_var.get():
                filters['date_to'] = self.date_to_var.get()
            if self.user_id_var.get():
                filters['user_id'] = self.user_id_var.get()
            if self.username_var.get():
                filters['username'] = self.username_var.get()
            if self.action_var.get():
                filters['action'] = self.action_var.get()
            if self.module_var.get():
                filters['module'] = self.module_var.get()
            if self.status_var.get():
                filters['status'] = self.status_var.get()
            if self.search_text_var.get():
                filters['search_text'] = self.search_text_var.get()

            # Get limit
            try:
                limit = int(self.limit_var.get())
            except ValueError:
                limit = 100

            # Perform search
            results = self.log_manager.db.search_logs(filters, limit=limit)

            # Ensure results is a list
            if results is None:
                results = []

            # Clear existing results
            for item in self.search_tree.get_children():
                self.search_tree.delete(item)

            # Add results to tree
            for i, log in enumerate(results, 1):
                timestamp = log.get('timestamp', '')[:19] if log.get('timestamp') else ''
                user = log.get('username', '')
                action = log.get('action', '')
                module = log.get('module', '')
                status = log.get('status', '')
                details = log.get('details', '') or ''

                # Truncate details if too long
                if details and len(details) > 50:
                    details = details[:47] + "..."

                self.search_tree.insert("", "end", values=(
                    i, timestamp, user, action, module, status, details
                ))

            # Update info label
            self.search_info_label.config(text=_t("log_management.search.found_results", count=len(results)))
            self.update_status(_t("log_management.messages.search_completed", count=len(results)))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.search", error=str(e)))
            self.update_status(_t("log_management.messages.search_failed"))

    def clear_search(self):
        """Clear search form"""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.user_id_var.set("")
        self.username_var.set("")
        self.action_var.set("")
        self.module_var.set("")
        self.status_var.set("")
        self.search_text_var.set("")
        self.limit_var.set("100")

        # Clear results
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        self.search_info_label.config(text=_t("log_management.search.search_cleared"))

    def save_search(self):
        """Save current search filters"""
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.auth_required"))
            return

        name = tk.simpledialog.askstring(_t("log_management.dialogs.save_search.title"), _t("log_management.dialogs.save_search.prompt"))
        if not name:
            return

        try:
            filters = {}
            if self.date_from_var.get(): filters['date_from'] = self.date_from_var.get()
            if self.date_to_var.get(): filters['date_to'] = self.date_to_var.get()
            if self.user_id_var.get(): filters['user_id'] = self.user_id_var.get()
            if self.username_var.get(): filters['username'] = self.username_var.get()
            if self.action_var.get(): filters['action'] = self.action_var.get()
            if self.module_var.get(): filters['module'] = self.module_var.get()
            if self.status_var.get(): filters['status'] = self.status_var.get()
            if self.search_text_var.get(): filters['search_text'] = self.search_text_var.get()

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO saved_searches (name, user_id, search_params)
                VALUES (?, ?, ?)
            ''', (name, self.auth.current_user['id'], json.dumps(filters)))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.dialogs.save_search.saved", name=name))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.save_search", error=str(e)))

    def load_search(self):
        """Load a saved search"""
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.auth_required"))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM saved_searches
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (self.auth.current_user['id'],))

            searches = cursor.fetchall()
            conn.close()

            if not searches:
                messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.dialogs.load_search.no_searches"))
                return

            # Create selection dialog
            search_window = tk.Toplevel(self.root)
            search_window.title(_t("log_management.dialogs.load_search.title"))
            search_window.geometry("400x300")

            ttk.Label(search_window, text=_t("log_management.dialogs.load_search.select")).pack(pady=10)

            # Listbox for searches
            search_listbox = tk.Listbox(search_window)
            search_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for search in searches:
                search_listbox.insert(tk.END, f"{search['name']} ({search['created_at'][:19]})")

            def load_selected():
                selection = search_listbox.curselection()
                if not selection:
                    return

                selected_search = searches[selection[0]]
                filters = json.loads(selected_search['search_params'])

                # Load filters into form
                self.date_from_var.set(filters.get('date_from', ''))
                self.date_to_var.set(filters.get('date_to', ''))
                self.user_id_var.set(filters.get('user_id', ''))
                self.username_var.set(filters.get('username', ''))
                self.action_var.set(filters.get('action', ''))
                self.module_var.set(filters.get('module', ''))
                self.status_var.set(filters.get('status', ''))
                self.search_text_var.set(filters.get('search_text', ''))

                search_window.destroy()
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.dialogs.load_search.loaded", name=selected_search['name']))

            ttk.Button(search_window, text=_t("log_management.dialogs.load_search.load"), command=load_selected).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.load_search", error=str(e)))
