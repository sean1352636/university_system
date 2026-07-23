"""
Database query and search tab for the Activity Logger GUI.
"""

from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    json,
    datetime, timedelta,
    Dict, List,
    _t,
)
from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui.theme import LoggerGUITheme


class QueryTab(ttk.Frame):
    """Database query and search tab"""

    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app

        self.setup_ui()

    def setup_ui(self):
        """Setup query interface"""
        # Header
        header_frame = ttk.Frame(self, style='AL.Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(header_frame, text=_t("activity_logger.query.title"),
                 style='AL.Title.TLabel').pack(side=tk.LEFT, padx=5)

        # Query builder
        query_frame = ttk.LabelFrame(self, text=_t("activity_logger.query.builder"), padding=10)
        query_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Date range
        date_frame = ttk.Frame(query_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text=_t("activity_logger.query.date_range"), style='AL.Heading.TLabel').pack(side=tk.LEFT)

        self.date_from = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        self.date_to = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(date_frame, text=_t("activity_logger.query.from"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(20, 5))
        ttk.Entry(date_frame, textvariable=self.date_from, width=12).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(date_frame, text=_t("activity_logger.query.to"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        ttk.Entry(date_frame, textvariable=self.date_to, width=12).pack(side=tk.LEFT, padx=(0, 10))

        # Quick date buttons
        quick_dates = [
            (_t("activity_logger.query.today"), 0),
            (_t("activity_logger.query.last_7_days"), 7),
            (_t("activity_logger.query.last_30_days"), 30),
            (_t("activity_logger.query.last_90_days"), 90)
        ]

        for text, days in quick_dates:
            ttk.Button(date_frame, text=text,
                      command=lambda d=days: self.set_quick_date(d)).pack(side=tk.LEFT, padx=2)

        # Filters
        filter_frame = ttk.Frame(query_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        # First row of filters
        filter_row1 = ttk.Frame(filter_frame)
        filter_row1.pack(fill=tk.X, pady=(0, 5))

        self.filter_user = tk.StringVar()
        self.filter_action = tk.StringVar()
        self.filter_module = tk.StringVar()
        self.filter_status = tk.StringVar(value="ALL")

        ttk.Label(filter_row1, text=_t("activity_logger.query.user"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row1, textvariable=self.filter_user, width=15).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(filter_row1, text=_t("activity_logger.query.action"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row1, textvariable=self.filter_action, width=15).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(filter_row1, text=_t("activity_logger.query.module"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row1, textvariable=self.filter_module, width=15).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(filter_row1, text=_t("activity_logger.query.status"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(filter_row1, textvariable=self.filter_status,
                    values=["ALL", "success", "failure"],
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))

        # Second row of filters
        filter_row2 = ttk.Frame(filter_frame)
        filter_row2.pack(fill=tk.X)

        self.filter_level = tk.StringVar(value="ALL")
        self.filter_security = tk.StringVar(value="ALL")
        self.search_text = tk.StringVar()

        ttk.Label(filter_row2, text=_t("activity_logger.query.log_level"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(filter_row2, textvariable=self.filter_level,
                    values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(filter_row2, text=_t("activity_logger.query.security_level"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(filter_row2, textvariable=self.filter_security,
                    values=["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(filter_row2, text=_t("activity_logger.query.search"), style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row2, textvariable=self.search_text, width=20).pack(side=tk.LEFT, padx=(0, 10))

        # Query buttons
        button_frame = ttk.Frame(query_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text=_t("activity_logger.query.execute"),
                  command=self.execute_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("activity_logger.query.clear"),
                  command=self.clear_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("activity_logger.query.export"),
                  command=self.export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("activity_logger.query.save_query"),
                  command=self.save_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("activity_logger.query.load_query"),
                  command=self.load_query).pack(side=tk.LEFT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(self, text=_t("activity_logger.query.results"), padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Results info
        info_frame = ttk.Frame(results_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        self.results_info = tk.StringVar(value=_t("activity_logger.query.no_query"))
        ttk.Label(info_frame, textvariable=self.results_info,
                 style='AL.Info.TLabel').pack(side=tk.LEFT)

        # Results treeview
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('timestamp', 'level', 'user', 'action', 'module', 'status', 'ip_address', 'details')
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure columns
        column_configs = [
            ('timestamp', _t("activity_logger.columns.timestamp"), 150),
            ('level', _t("activity_logger.columns.level"), 80),
            ('user', _t("activity_logger.columns.user"), 100),
            ('action', _t("activity_logger.columns.action"), 120),
            ('module', _t("activity_logger.columns.module"), 100),
            ('status', _t("activity_logger.columns.status"), 80),
            ('ip_address', _t("activity_logger.columns.ip_address"), 120),
            ('details', _t("activity_logger.columns.details"), 300)
        ]

        for col_id, heading, width in column_configs:
            self.results_tree.heading(col_id, text=heading)
            self.results_tree.column(col_id, width=width, minwidth=80)

        # Add scrollbars
        v_scrollbar_results = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar_results = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar_results.set, xscrollcommand=h_scrollbar_results.set)

        # Pack results treeview and scrollbars
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar_results.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar_results.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind double-click to show details
        self.results_tree.bind('<Double-1>', self.show_result_details)

        self.current_results = []

    def set_quick_date(self, days: int):
        """Set quick date range"""
        if days == 0:
            # Today
            today = datetime.now().strftime("%Y-%m-%d")
            self.date_from.set(today)
            self.date_to.set(today)
        else:
            # Last N days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            self.date_from.set(start_date.strftime("%Y-%m-%d"))
            self.date_to.set(end_date.strftime("%Y-%m-%d"))

    def execute_query(self):
        """Execute the database query"""
        try:
            # Database logging is handled by the centralized activity logger
            # No special db_logger attribute needed

            # Build filters
            filters = {}

            # Date range
            if self.date_from.get():
                filters['date_from'] = self.date_from.get()
            if self.date_to.get():
                filters['date_to'] = self.date_to.get()

            # Other filters
            if self.filter_user.get().strip():
                filters['username'] = self.filter_user.get().strip()
            if self.filter_action.get().strip():
                filters['action'] = self.filter_action.get().strip()
            if self.filter_module.get().strip():
                filters['module'] = self.filter_module.get().strip()
            if self.filter_status.get() != "ALL":
                filters['status'] = self.filter_status.get()
            if self.filter_level.get() != "ALL":
                filters['log_level'] = self.filter_level.get()
            if self.filter_security.get() != "ALL":
                filters['security_level'] = self.filter_security.get()

            # Execute query - check if logger and db_logger are available
            if not self.main_app.logger or not hasattr(self.main_app.logger, 'db_logger') or not self.main_app.logger.db_logger:
                messagebox.showwarning(_t("common.warning"), _t("activity_logger.query.db_not_available"))
                self.current_results = []
                self.display_results([])
                return

            results = self.main_app.logger.db_logger.query_logs(filters, limit=5000)

            # Handle search text (post-filter)
            if self.search_text.get().strip():
                search_term = self.search_text.get().strip().lower()
                filtered_results = []
                for result in results:
                    # Search in details, action, module, username
                    searchable_text = f"{result.get('details', '')} {result.get('action', '')} {result.get('module', '')} {result.get('username', '')}".lower()
                    if search_term in searchable_text:
                        filtered_results.append(result)
                results = filtered_results

            self.current_results = results
            self.display_results(results)

        except Exception as e:
            messagebox.showerror("Query Error", f"Failed to execute query: {str(e)}")

    def display_results(self, results: List[Dict]):
        """Display query results"""
        # Clear existing results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Update info
        self.results_info.set(f"Found {len(results)} log entries")

        # Add results to tree.
        # dict.get returns the default only when the key is missing —
        # NULL columns produce a real `None`, so coerce every cell to
        # a string before len()/slicing.
        def _s(value) -> str:
            return '' if value is None else str(value)

        for result in results:
            details = _s(result.get('details'))
            details_cell = (details[:100] + '...') if len(details) > 100 else details
            values = (
                _s(result.get('timestamp')),
                _s(result.get('log_level')),
                _s(result.get('username')),
                _s(result.get('action')),
                _s(result.get('module')),
                _s(result.get('status')),
                _s(result.get('ip_address')),
                details_cell,
            )

            # Color code based on level and status
            tags = []
            level = result.get('log_level', '')
            status = result.get('status', '')

            if level in ['ERROR', 'CRITICAL']:
                tags.append('error')
            elif level == 'WARNING':
                tags.append('warning')
            elif status == 'failure':
                tags.append('failure')

            self.results_tree.insert('', 'end', values=values, tags=tags)

        # Configure tag colors
        self.results_tree.tag_configure('error', foreground='#ff6b6b')
        self.results_tree.tag_configure('warning', foreground='#ffa726')
        self.results_tree.tag_configure('failure', foreground='#ef5350')

    def clear_results(self):
        """Clear query results"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        self.results_info.set(_t("activity_logger.query.no_query"))
        self.current_results = []

    def export_results(self):
        """Export query results"""
        if not self.current_results:
            messagebox.showwarning(_t("common.warning"), _t("activity_logger.query.no_results"))
            return

        try:
            file_path = filedialog.asksaveasfilename(
                title="Export Query Results",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt")
                ]
            )

            if file_path:
                if file_path.endswith('.csv'):
                    # Export as CSV
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        if self.current_results:
                            fieldnames = self.current_results[0].keys()
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            for result in self.current_results:
                                # Convert complex fields to strings
                                row = {}
                                for key, value in result.items():
                                    if isinstance(value, (dict, list)):
                                        row[key] = json.dumps(value)
                                    else:
                                        row[key] = value
                                writer.writerow(row)

                elif file_path.endswith('.txt'):
                    # Export as formatted text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"Query Results Export\n{'='*50}\n\n")
                        f.write(f"Total Results: {len(self.current_results)}\n")
                        f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                        for i, result in enumerate(self.current_results, 1):
                            f.write(f"Entry #{i}\n{'-'*20}\n")
                            for key, value in result.items():
                                f.write(f"{key}: {value}\n")
                            f.write("\n")

                else:
                    # Export as JSON
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.current_results, f, indent=2, default=str)

                messagebox.showinfo("Export Complete", f"Results exported to: {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export results: {str(e)}")

    def save_query(self):
        """Save current query parameters"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Save Query",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )

            if file_path:
                query_data = {
                    'date_from': self.date_from.get(),
                    'date_to': self.date_to.get(),
                    'filter_user': self.filter_user.get(),
                    'filter_action': self.filter_action.get(),
                    'filter_module': self.filter_module.get(),
                    'filter_status': self.filter_status.get(),
                    'filter_level': self.filter_level.get(),
                    'filter_security': self.filter_security.get(),
                    'search_text': self.search_text.get(),
                    'saved_date': datetime.now().isoformat()
                }

                with open(file_path, 'w') as f:
                    json.dump(query_data, f, indent=2)

                messagebox.showinfo("Query Saved", f"Query saved to: {file_path}")

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save query: {str(e)}")

    def load_query(self):
        """Load saved query parameters"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Query",
                filetypes=[("JSON files", "*.json")]
            )

            if file_path:
                with open(file_path, 'r') as f:
                    query_data = json.load(f)

                # Set query parameters
                self.date_from.set(query_data.get('date_from', ''))
                self.date_to.set(query_data.get('date_to', ''))
                self.filter_user.set(query_data.get('filter_user', ''))
                self.filter_action.set(query_data.get('filter_action', ''))
                self.filter_module.set(query_data.get('filter_module', ''))
                self.filter_status.set(query_data.get('filter_status', 'ALL'))
                self.filter_level.set(query_data.get('filter_level', 'ALL'))
                self.filter_security.set(query_data.get('filter_security', 'ALL'))
                self.search_text.set(query_data.get('search_text', ''))

                messagebox.showinfo("Query Loaded", f"Query loaded from: {file_path}")

        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load query: {str(e)}")

    def show_result_details(self, event):
        """Show detailed information for selected result"""
        selection = self.results_tree.selection()
        if not selection:
            return

        # Get the index of selected item
        item_index = self.results_tree.index(selection[0])

        if item_index < len(self.current_results):
            result = self.current_results[item_index]

            # Create details window
            details_window = tk.Toplevel(self)
            details_window.title(_t("activity_logger.dialogs.log_entry_details"))
            details_window.geometry("700x500")
            details_window.configure(bg=LoggerGUITheme.DARK_BG)

            # Create text widget with scrollbar
            text_frame = ttk.Frame(details_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True)

            # Format details
            details_text = f"""COMPLETE LOG ENTRY DETAILS
{'='*60}

"""

            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    details_text += f"{key.replace('_', ' ').title()}:\n{json.dumps(value, indent=2)}\n\n"
                else:
                    details_text += f"{key.replace('_', ' ').title()}: {value}\n"

            text_widget.insert(tk.END, details_text)
            text_widget.configure(state='disabled')
