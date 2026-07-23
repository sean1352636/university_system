"""
Real-time log viewer tab for the Activity Logger GUI.
"""

from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    datetime, timedelta,
    Dict, List,
    _t,
)
from education_system.post_18.university_system.modules.shared.gui.simple_activity_logger_gui.theme import LoggerGUITheme


class LogViewerTab(ttk.Frame):
    """Real-time log viewer tab"""

    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        self.auto_refresh = tk.BooleanVar(value=True)
        self.max_display_logs = 1000
        self.filter_level = tk.StringVar(value="ALL")
        self.filter_user = tk.StringVar()
        self.filter_action = tk.StringVar()
        self.filter_module = tk.StringVar()
        self._after_id = None  # Track timer ID for cleanup
        self._destroyed = False  # Flag to prevent callbacks after destroy

        self.setup_ui()

    def setup_ui(self):
        """Setup log viewer UI"""
        # Control panel
        control_frame = ttk.Frame(self, style='AL.Card.TFrame')
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Left controls
        left_controls = ttk.Frame(control_frame)
        left_controls.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(left_controls, text=_t("activity_logger.log_viewer.filter_level"),
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(5, 2))

        level_combo = ttk.Combobox(left_controls, textvariable=self.filter_level,
                                  values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                                  state="readonly", width=10)
        level_combo.pack(side=tk.LEFT, padx=(0, 10))
        level_combo.bind('<<ComboboxSelected>>', self.on_filter_change)

        ttk.Label(left_controls, text=_t("activity_logger.log_viewer.user"),
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(5, 2))

        user_entry = ttk.Entry(left_controls, textvariable=self.filter_user, width=15)
        user_entry.pack(side=tk.LEFT, padx=(0, 10))
        user_entry.bind('<KeyRelease>', self.on_filter_change)

        ttk.Label(left_controls, text=_t("activity_logger.log_viewer.action"),
                 style='AL.Info.TLabel').pack(side=tk.LEFT, padx=(5, 2))

        action_entry = ttk.Entry(left_controls, textvariable=self.filter_action, width=15)
        action_entry.pack(side=tk.LEFT, padx=(0, 10))
        action_entry.bind('<KeyRelease>', self.on_filter_change)

        # Right controls
        right_controls = ttk.Frame(control_frame)
        right_controls.pack(side=tk.RIGHT)

        ttk.Checkbutton(right_controls, text=_t("activity_logger.log_viewer.auto_refresh"),
                       variable=self.auto_refresh).pack(side=tk.LEFT, padx=5)

        ttk.Button(right_controls, text=_t("activity_logger.log_viewer.refresh"),
                  command=self.refresh_logs).pack(side=tk.LEFT, padx=2)

        ttk.Button(right_controls, text=_t("activity_logger.log_viewer.clear"),
                  command=self.clear_logs).pack(side=tk.LEFT, padx=2)

        ttk.Button(right_controls, text=_t("activity_logger.log_viewer.export"),
                  command=self.export_logs).pack(side=tk.LEFT, padx=2)

        # Log display area with treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Create treeview with columns
        columns = ('timestamp', 'level', 'user', 'action', 'module', 'status', 'details')
        self.log_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        # Configure columns
        self.log_tree.heading('timestamp', text='Timestamp')
        self.log_tree.heading('level', text='Level')
        self.log_tree.heading('user', text='User')
        self.log_tree.heading('action', text='Action')
        self.log_tree.heading('module', text='Module')
        self.log_tree.heading('status', text='Status')
        self.log_tree.heading('details', text='Details')

        # Configure column widths
        self.log_tree.column('timestamp', width=150, minwidth=120)
        self.log_tree.column('level', width=80, minwidth=60)
        self.log_tree.column('user', width=100, minwidth=80)
        self.log_tree.column('action', width=120, minwidth=100)
        self.log_tree.column('module', width=100, minwidth=80)
        self.log_tree.column('status', width=80, minwidth=60)
        self.log_tree.column('details', width=300, minwidth=200)

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.log_tree.xview)
        self.log_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bind double-click to show details
        self.log_tree.bind('<Double-1>', self.show_log_details)

        # Start refresh timer
        self.after_refresh()

    def after_refresh(self):
        """Schedule next refresh"""
        # Don't run if destroyed
        if self._destroyed:
            return

        # Cancel previous timer if exists
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass

        if self.auto_refresh.get():
            self.refresh_logs()

        # Schedule next refresh and store ID
        try:
            if not self._destroyed:
                self._after_id = self.after(2000, self.after_refresh)  # Refresh every 2 seconds
        except tk.TclError:
            # Widget destroyed, stop scheduling
            self._destroyed = True

    def destroy(self):
        """Clean up timers before destroying"""
        self._destroyed = True
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
                self._after_id = None
            except Exception:
                pass
        super().destroy()

    def refresh_logs(self):
        """Refresh log display"""
        try:
            # Query directly from database
            from education_system.post_18.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Build query with filters
                query = "SELECT id, username, action, details, timestamp, ip_address FROM activity_log WHERE 1=1"
                params = []

                if self.filter_user.get().strip():
                    query += " AND username LIKE ?"
                    params.append(f"%{escape_like(self.filter_user.get().strip())}%")

                if self.filter_action.get().strip():
                    query += " AND action LIKE ?"
                    params.append(f"%{escape_like(self.filter_action.get().strip())}%")

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(self.max_display_logs)

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                # Convert to dict format
                logs = []
                for row in rows:
                    logs.append({
                        'id': row[0],
                        'username': row[1],
                        'action': row[2],
                        'details': row[3],
                        'timestamp': row[4],
                        'ip_address': row[5] or 'N/A'
                    })

                self.update_log_display(logs)

        except Exception as e:
            print(f"Error refreshing logs: {e}")
            import traceback
            traceback.print_exc()

    def update_log_display(self, logs: List[Dict]):
        """Update the log display with new logs"""
        # Clear existing items
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        # Add new logs
        for log in reversed(logs):  # Show newest first
            timestamp = log.get('timestamp', '') or ''
            level = log.get('log_level', '') or ''
            user = log.get('username', '') or ''
            action = log.get('action', '') or ''
            module = log.get('module', '') or ''
            status = log.get('status', '') or ''
            # Handle None values from database
            details_raw = log.get('details') or ''
            details = details_raw[:100] + '...' if len(details_raw) > 100 else details_raw

            # Color code based on level and status
            tags = []
            if level in ['ERROR', 'CRITICAL']:
                tags.append('error')
            elif level == 'WARNING':
                tags.append('warning')
            elif status == 'failure':
                tags.append('failure')

            item = self.log_tree.insert('', 'end',
                                       values=(timestamp, level, user, action, module, status, details),
                                       tags=tags)

        # Configure tags for coloring
        self.log_tree.tag_configure('error', foreground='#ff6b6b')
        self.log_tree.tag_configure('warning', foreground='#ffa726')
        self.log_tree.tag_configure('failure', foreground='#ef5350')

    def on_filter_change(self, event=None):
        """Handle filter changes"""
        self.refresh_logs()

    def clear_logs(self):
        """Clear log display"""
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

    def export_logs(self):
        """Export displayed logs"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Export Logs",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if file_path:
                # Get current filter settings
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if hasattr(self.main_app.logger, 'export_logs'):
                    exported_file = self.main_app.logger.export_logs(
                        start_date, end_date,
                        format=file_path.split('.')[-1].lower(),
                        output_file=file_path
                    )
                    messagebox.showinfo("Export Complete", f"Logs exported to: {exported_file}")
                else:
                    messagebox.showwarning("Export Unavailable", "Export functionality requires database logging to be enabled.")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export logs: {str(e)}")

    def show_log_details(self, event):
        """Show detailed log information"""
        selection = self.log_tree.selection()
        if not selection:
            return

        item = self.log_tree.item(selection[0])
        values = item['values']

        # Create details window
        details_window = tk.Toplevel(self)
        details_window.title(_t("activity_logger.dialogs.log_details"))
        details_window.geometry("600x400")
        details_window.configure(bg=LoggerGUITheme.DARK_BG)

        # Create text widget with scrollbar
        text_frame = ttk.Frame(details_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=20, width=70)
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Format log details
        details_text = f"""Log Entry Details
{'='*50}

Timestamp: {values[0]}
Level: {values[1]}
User: {values[2]}
Action: {values[3]}
Module: {values[4]}
Status: {values[5]}

Details:
{values[6]}

{'='*50}
"""

        text_widget.insert(tk.END, details_text)
        text_widget.configure(state='disabled')
