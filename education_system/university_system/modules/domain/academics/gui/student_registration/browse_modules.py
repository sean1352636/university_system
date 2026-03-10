"""
Browse Modules Mixin

Provides the registration dashboard and the available-modules browser
with search, filtering, and module detail views.
"""

from .common_imports import *


class BrowseModulesMixin:
    """Mixin that adds dashboard and module browsing capabilities."""

    # ------------------------------------------------------------------ #
    #  Dashboard
    # ------------------------------------------------------------------ #
    def show_registration_dashboard(self, parent):
        """Display stat cards and quick-action buttons on the dashboard tab."""
        header = ttk.Label(
            parent, text="Registration Dashboard",
            font=('Arial', 16, 'bold'),
        )
        header.pack(pady=(15, 10))

        # --- Stat cards ------------------------------------------------ #
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill='x', padx=20, pady=10)

        enrolled_count = 0
        available_count = 0
        total_credits = 0

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Enrolled modules for this student
            cursor.execute(
                "SELECT COUNT(*) FROM student_modules "
                "WHERE student_id = ? AND status = 'Enrolled'",
                (self.student_id,),
            )
            enrolled_count = cursor.fetchone()[0]

            # Total available modules
            cursor.execute("SELECT COUNT(*) FROM modules")
            available_count = cursor.fetchone()[0]

            # Total credits enrolled
            cursor.execute(
                "SELECT COALESCE(SUM(m.credits), 0) "
                "FROM student_modules sm "
                "JOIN modules m ON sm.module_code = m.module_code "
                "WHERE sm.student_id = ? AND sm.status = 'Enrolled'",
                (self.student_id,),
            )
            total_credits = cursor.fetchone()[0]
            conn.close()
        except Exception as exc:
            logger.error("Dashboard stats error: %s", exc)

        cards = [
            ("Enrolled Modules", str(enrolled_count), 'success'),
            ("Available Modules", str(available_count), 'info'),
            ("Total Credits", str(total_credits), 'primary'),
        ]
        for idx, (title, value, color) in enumerate(cards):
            card = create_stat_card(stats_frame, title, value, color)
            card.grid(row=0, column=idx, padx=15, pady=5, sticky='nsew')
            stats_frame.columnconfigure(idx, weight=1)

        # --- Quick actions --------------------------------------------- #
        actions_frame = ttk.LabelFrame(parent, text="Quick Actions")
        actions_frame.pack(fill='x', padx=20, pady=15)

        ttk.Button(
            actions_frame, text="Browse Modules",
            command=lambda: self.notebook.select(1),
        ).pack(side='left', padx=15, pady=10)

        ttk.Button(
            actions_frame, text="My Enrollment",
            command=lambda: self.notebook.select(2),
        ).pack(side='left', padx=15, pady=10)

    # ------------------------------------------------------------------ #
    #  Available modules browser
    # ------------------------------------------------------------------ #
    def show_available_modules(self, parent):
        """Show a searchable treeview of all modules."""
        # --- Search / filter bar --------------------------------------- #
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
        self.module_search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame, textvariable=self.module_search_var, width=30,
        )
        search_entry.pack(side='left', padx=(0, 5))

        ttk.Button(
            search_frame, text="Search",
            command=self._refresh_available_modules,
        ).pack(side='left', padx=(0, 10))

        ttk.Label(search_frame, text="Department:").pack(side='left', padx=(10, 5))
        self.dept_filter_var = tk.StringVar(value="All")
        self.dept_combo = ttk.Combobox(
            search_frame, textvariable=self.dept_filter_var,
            state='readonly', width=20,
        )
        self.dept_combo.pack(side='left', padx=(0, 5))
        self.dept_combo.bind('<<ComboboxSelected>>', lambda _e: self._refresh_available_modules())

        # --- Treeview -------------------------------------------------- #
        columns = ('Code', 'Name', 'Credits', 'Department', 'Capacity')
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.modules_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', height=15,
        )
        widths = {'Code': 100, 'Name': 250, 'Credits': 70, 'Department': 150, 'Capacity': 100}
        for col in columns:
            self.modules_tree.heading(col, text=col)
            self.modules_tree.column(col, width=widths.get(col, 100), anchor='w')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.modules_tree.yview)
        self.modules_tree.configure(yscrollcommand=vsb.set)

        self.modules_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # --- Buttons --------------------------------------------------- #
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(5, 10))

        ttk.Button(
            btn_frame, text="Enroll in Selected Module",
            command=self._enroll_selected_module,
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame, text="View Details",
            command=self._view_selected_module,
        ).pack(side='left', padx=5)

        # Populate
        self._load_departments()
        self._refresh_available_modules()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _load_departments(self):
        """Populate the department filter combo box."""
        departments = ["All"]
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT department FROM modules ORDER BY department")
            departments += [row[0] for row in cursor.fetchall() if row[0]]
            conn.close()
        except Exception as exc:
            logger.error("Load departments error: %s", exc)
        self.dept_combo['values'] = departments

    def _refresh_available_modules(self):
        """Reload the modules treeview with current search/filter criteria."""
        self.modules_tree.delete(*self.modules_tree.get_children())
        search_text = self.module_search_var.get().strip().lower()
        dept = self.dept_filter_var.get()

        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = (
                "SELECT module_code, module_name, credits, department, max_capacity "
                "FROM modules ORDER BY module_code"
            )
            cursor.execute(query)
            for row in cursor.fetchall():
                code, name, credits_val, department, capacity = row
                # Apply search filter
                if search_text and search_text not in (code or '').lower() and search_text not in (name or '').lower():
                    continue
                # Apply department filter
                if dept != "All" and department != dept:
                    continue
                # Current enrollment count
                cursor.execute(
                    "SELECT COUNT(*) FROM student_modules "
                    "WHERE module_code = ? AND status = 'Enrolled'",
                    (code,),
                )
                enrolled = cursor.fetchone()[0]
                cap_display = f"{enrolled}/{capacity}" if capacity else str(enrolled)
                self.modules_tree.insert(
                    '', 'end', values=(code, name, credits_val, department, cap_display),
                )
            conn.close()
        except Exception as exc:
            logger.error("Refresh modules error: %s", exc)
            messagebox.showerror("Error", f"Failed to load modules: {exc}")

    def _enroll_selected_module(self):
        """Enroll in the module currently selected in the treeview."""
        sel = self.modules_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a module to enroll in.")
            return
        module_code = self.modules_tree.item(sel[0], 'values')[0]
        self.enroll_in_module(module_code)

    def _view_selected_module(self):
        """Open a details dialog for the selected module."""
        sel = self.modules_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a module to view.")
            return
        module_code = self.modules_tree.item(sel[0], 'values')[0]
        self.show_module_details(module_code)

    def show_module_details(self, module_code):
        """Open a top-level dialog showing full details for *module_code*."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT module_code, module_name, credits, department, "
                "max_capacity, description FROM modules WHERE module_code = ?",
                (module_code,),
            )
            row = cursor.fetchone()

            cursor.execute(
                "SELECT COUNT(*) FROM student_modules "
                "WHERE module_code = ? AND status = 'Enrolled'",
                (module_code,),
            )
            enrolled_count = cursor.fetchone()[0]
            conn.close()
        except Exception as exc:
            logger.error("Module details error: %s", exc)
            messagebox.showerror("Error", f"Failed to load details: {exc}")
            return

        if not row:
            messagebox.showwarning("Not Found", f"Module {module_code} not found.")
            return

        code, name, credits_val, department, capacity, description = row

        dlg = tk.Toplevel(self.parent_frame)
        dlg.title(f"Module Details - {code}")
        dlg.geometry("450x350")
        dlg.transient(self.parent_frame)
        dlg.grab_set()

        ttk.Label(dlg, text=name, font=('Arial', 14, 'bold')).pack(pady=(15, 5))

        info_frame = ttk.Frame(dlg)
        info_frame.pack(fill='x', padx=20, pady=10)

        details = [
            ("Module Code:", code),
            ("Department:", department or "N/A"),
            ("Credits:", str(credits_val)),
            ("Capacity:", f"{enrolled_count}/{capacity}" if capacity else "Unlimited"),
        ]
        for label_text, value_text in details:
            row_frame = ttk.Frame(info_frame)
            row_frame.pack(fill='x', pady=2)
            ttk.Label(row_frame, text=label_text, font=('Arial', 10, 'bold'), width=15, anchor='w').pack(side='left')
            ttk.Label(row_frame, text=value_text, font=('Arial', 10)).pack(side='left')

        if description:
            ttk.Label(dlg, text="Description:", font=('Arial', 10, 'bold')).pack(anchor='w', padx=20, pady=(10, 2))
            desc_label = ttk.Label(dlg, text=description, wraplength=400, justify='left')
            desc_label.pack(anchor='w', padx=20)

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=15)
        ttk.Button(
            btn_frame, text="Enroll",
            command=lambda: (self.enroll_in_module(code), dlg.destroy()),
        ).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Close", command=dlg.destroy).pack(side='left', padx=10)
