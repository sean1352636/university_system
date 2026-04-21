import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
from datetime import datetime

from education_system.university_system.modules.shared.constants.paths import LOG_DIR
from education_system.university_system.infrastructure.logging.gui.helpers import _t


class AnalyticsMixin:
    """Mixin providing analytics tab functionality."""

    def setup_analytics_tab(self):
        """Setup the analytics tab"""
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text="📈 " + _t("log_management.tabs.analytics"))

        # Analytics controls
        controls_frame = ttk.LabelFrame(self.analytics_frame, text=_t("log_management.analytics.title"))
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack(padx=10, pady=10)

        # Days selection
        ttk.Label(controls_grid, text=_t("log_management.analytics.analysis_period")).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.analytics_days_var = tk.StringVar(value="7")
        days_combo = ttk.Combobox(controls_grid, textvariable=self.analytics_days_var, width=10,
                                 values=["1", "7", "14", "30", "90"])
        days_combo.grid(row=0, column=1, padx=(0, 10))
        ttk.Label(controls_grid, text=_t("log_management.analytics.days")).grid(row=0, column=2, sticky="w")

        # User selection for user-specific analytics
        ttk.Label(controls_grid, text=_t("log_management.analytics.user_id_optional")).grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.analytics_user_var = tk.StringVar()
        user_entry = ttk.Entry(controls_grid, textvariable=self.analytics_user_var, width=20)
        user_entry.grid(row=1, column=1, columnspan=2, sticky="w")

        # Buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="📊 " + _t("log_management.analytics.buttons.generate_summary"),
                  command=self.generate_analytics_summary).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="👤 " + _t("log_management.analytics.buttons.user_report"),
                  command=self.generate_user_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📈 " + _t("log_management.analytics.buttons.create_chart"),
                  command=self.generate_chart_dialog).pack(side=tk.LEFT)

        # Results display
        results_frame = ttk.LabelFrame(self.analytics_frame, text=_t("log_management.analytics.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Text widget for results
        self.analytics_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                       font=("Courier", 10),
                                                       fg="#000000", bg="#FFFFFF")
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def generate_analytics_summary(self):
        """Generate analytics summary"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.generating_summary"))

        try:
            days = int(self.analytics_days_var.get())
            summary = self.log_manager.analytics.generate_activity_summary(days)

            if "error" in summary:
                self.analytics_text.delete("1.0", tk.END)
                self.analytics_text.insert("1.0", summary["error"])
                return

            # Format summary for display
            output = f"""Activity Summary - Last {days} Days
{'='*50}

Period: {summary['period']}
Total Activities: {summary['total_activities']:,}
Unique Users: {summary['unique_users']}
Success Rate: {summary['success_rate']:.2f}%
Failed Activities: {summary['failed_activities']}
Peak Activity Hour: {summary['peak_activity_hour']}:00

Most Active Users:
{'-'*30}
"""

            for user, count in list(summary['most_active_users'].items())[:10]:
                output += f"{user:<20} {count:>8}\n"

            output += f"\nActivity by Action:\n{'-'*30}\n"
            for action, count in summary['activity_by_action'].items():
                output += f"{action:<20} {count:>8}\n"

            output += f"\nActivity by Module:\n{'-'*30}\n"
            for module, count in summary['activity_by_module'].items():
                output += f"{module:<20} {count:>8}\n"

            self.analytics_text.delete("1.0", tk.END)
            self.analytics_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.summary_generated"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.analytics", error=str(e)))
            self.update_status(_t("log_management.messages.analytics_failed"))

    def generate_user_report(self):
        """Generate user-specific report"""
        user_id = self.analytics_user_var.get()
        if not user_id:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.enter_user_id"))
            return

        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.generating_report", user_id=user_id))

        try:
            days = int(self.analytics_days_var.get())
            report = self.log_manager.analytics.generate_user_activity_report(user_id, days)

            if "error" in report:
                self.analytics_text.delete("1.0", tk.END)
                self.analytics_text.insert("1.0", report["error"])
                return

            # Format report for display
            output = f"""User Activity Report: {report['username']} ({report['user_id']})
{'='*60}

Period: {report['period']}
Total Activities: {report['total_activities']:,}
Success Rate: {report['success_rate']:.2f}%

Modules Used:
{'-'*30}
"""

            for module, count in list(report['modules_used'].items())[:10]:
                output += f"{module:<25} {count:>8}\n"

            output += f"\nActions Performed:\n{'-'*30}\n"
            for action, count in report['actions_performed'].items():
                output += f"{action:<25} {count:>8}\n"

            output += f"\nMost Active Hours:\n{'-'*30}\n"
            sorted_hours = sorted(report['activity_hours'].items(), key=lambda x: x[1], reverse=True)
            for hour, count in sorted_hours[:10]:
                output += f"{hour:02d}:00{'':<20} {count:>8}\n"

            self.analytics_text.delete("1.0", tk.END)
            self.analytics_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.report_generated", user_id=user_id))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.user_report", error=str(e)))
            self.update_status(_t("log_management.messages.report_failed"))

    def generate_chart_dialog(self):
        """Show chart generation dialog"""
        chart_window = tk.Toplevel(self.root)
        chart_window.title(_t("log_management.dialogs.chart_generation.title"))
        chart_window.geometry("400x300")

        ttk.Label(chart_window, text=_t("log_management.dialogs.chart_generation.options"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Days selection
        days_frame = ttk.Frame(chart_window)
        days_frame.pack(pady=10)

        ttk.Label(days_frame, text=_t("log_management.dialogs.chart_generation.period")).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="7")
        ttk.Entry(days_frame, textvariable=days_var, width=10).pack(side=tk.LEFT, padx=5)

        # Save path
        path_frame = ttk.Frame(chart_window)
        path_frame.pack(pady=10, fill=tk.X, padx=20)

        ttk.Label(path_frame, text=_t("log_management.dialogs.chart_generation.save_path")).pack(anchor="w")
        path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def browse_path():
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if filename:
                path_var.set(filename)

        ttk.Button(path_frame, text=_t("log_management.dialogs.chart_generation.browse"), command=browse_path).pack(side=tk.RIGHT, padx=(5, 0))

        # Generate button
        def generate_chart():
            try:
                days = int(days_var.get())
                save_path = path_var.get()

                if not save_path:
                    charts_dir = LOG_DIR / "charts"
                    charts_dir.mkdir(parents=True, exist_ok=True)
                    save_path = str(charts_dir / f"activity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

                result_path = self.log_manager.analytics.create_activity_chart("daily", days, save_path)

                chart_window.destroy()

                if not result_path or not os.path.exists(result_path):
                    messagebox.showwarning(
                        _t("log_management.messages.info"),
                        "No activity data found for the selected period.",
                    )
                    return

                # Display the chart in a new window
                self._show_chart_window(result_path)

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.chart", error=str(e)))

        ttk.Button(chart_window, text=_t("log_management.dialogs.chart_generation.generate"), command=generate_chart).pack(pady=20)

    def _show_chart_window(self, image_path):
        """Display a saved chart image in a new tkinter window."""
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showinfo(
                _t("log_management.messages.success"),
                f"Chart saved to:\n{image_path}",
            )
            return

        win = tk.Toplevel(self.root)
        win.title("Activity Chart")
        win.geometry("900x620")
        win.transient(self.root)

        img = Image.open(image_path)
        # Scale to fit window while preserving aspect ratio
        img.thumbnail((880, 560), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        label = ttk.Label(win, image=photo)
        label.image = photo  # prevent garbage collection
        label.pack(padx=10, pady=(10, 5))

        info_frame = ttk.Frame(win)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(info_frame, text=f"Saved: {image_path}", wraplength=860).pack(side=tk.LEFT)
        ttk.Button(info_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT)
