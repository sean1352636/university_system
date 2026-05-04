"""
Log Analyzer - A standalone tkinter GUI for analyzing text-based log files.

Features: auto-detect log levels, filter by level, regex search,
error frequency chart, timeline, statistics, pattern highlighting,
export filtered results.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import re
import os
from datetime import datetime
from collections import Counter, defaultdict


# Log level patterns and colors
LOG_LEVELS = {
    "CRITICAL": {"pattern": r"\bCRITICAL\b", "color": "#b71c1c", "bg": "#ffcdd2"},
    "ERROR": {"pattern": r"\bERROR\b", "color": "#c62828", "bg": "#ffebee"},
    "WARNING": {"pattern": r"\b(?:WARNING|WARN)\b", "color": "#e65100", "bg": "#fff3e0"},
    "INFO": {"pattern": r"\bINFO\b", "color": "#1565c0", "bg": "#e3f2fd"},
    "DEBUG": {"pattern": r"\bDEBUG\b", "color": "#2e7d32", "bg": "#e8f5e9"},
}

# Timestamp patterns to try
TIMESTAMP_PATTERNS = [
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})",       # 2024-01-15 10:30:00
    r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})",            # 15/Jan/2024:10:30:00
    r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",            # 01/15/2024 10:30:00
    r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})",            # Jan 15 10:30:00
    r"(\d{2}:\d{2}:\d{2})",                                # 10:30:00
]

TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
]


class BarChart(tk.Canvas):
    """Simple bar chart drawn on a tkinter Canvas."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="white", highlightthickness=1,
                         highlightbackground="#cccccc", **kwargs)
        self._data = {}
        self._colors = {}

    def set_data(self, data, colors=None):
        self._data = data
        self._colors = colors or {}
        self._draw()

    def _draw(self):
        self.delete("all")
        if not self._data:
            self.create_text(
                self.winfo_width() // 2 or 150, self.winfo_height() // 2 or 80,
                text="No data to display", font=("Segoe UI", 10), fill="#999"
            )
            return

        w = self.winfo_width() or 400
        h = self.winfo_height() or 200

        margin_left = 60
        margin_right = 20
        margin_top = 25
        margin_bottom = 40

        chart_w = w - margin_left - margin_right
        chart_h = h - margin_top - margin_bottom

        if chart_w <= 0 or chart_h <= 0:
            return

        max_val = max(self._data.values()) if self._data.values() else 1
        n_bars = len(self._data)
        if n_bars == 0:
            return

        bar_width = min(chart_w // n_bars - 4, 80)
        gap = (chart_w - bar_width * n_bars) / (n_bars + 1)

        # Title
        self.create_text(w // 2, 10, text="Log Level Distribution",
                         font=("Segoe UI", 10, "bold"), fill="#333")

        # Draw bars
        for i, (label, value) in enumerate(self._data.items()):
            x = margin_left + gap + i * (bar_width + gap)
            bar_h = (value / max_val) * chart_h if max_val > 0 else 0
            y_top = margin_top + chart_h - bar_h
            y_bottom = margin_top + chart_h

            color = self._colors.get(label, "#4285F4")

            self.create_rectangle(x, y_top, x + bar_width, y_bottom,
                                  fill=color, outline="#333", width=1)

            # Value label
            self.create_text(x + bar_width / 2, y_top - 8,
                             text=str(value), font=("Segoe UI", 9, "bold"), fill="#333")

            # Category label
            self.create_text(x + bar_width / 2, y_bottom + 12,
                             text=label, font=("Segoe UI", 8), fill="#333")

        # Y-axis line
        self.create_line(margin_left, margin_top, margin_left, margin_top + chart_h, fill="#333")
        # X-axis line
        self.create_line(margin_left, margin_top + chart_h,
                         margin_left + chart_w, margin_top + chart_h, fill="#333")


class TimelineChart(tk.Canvas):
    """Timeline showing error distribution over time."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="white", highlightthickness=1,
                         highlightbackground="#cccccc", **kwargs)
        self._data = {}

    def set_data(self, time_buckets):
        """time_buckets: dict of {time_label: count}"""
        self._data = time_buckets
        self._draw()

    def _draw(self):
        self.delete("all")
        if not self._data:
            self.create_text(
                self.winfo_width() // 2 or 150, self.winfo_height() // 2 or 60,
                text="No timeline data", font=("Segoe UI", 10), fill="#999"
            )
            return

        w = self.winfo_width() or 400
        h = self.winfo_height() or 150

        margin = 40
        chart_w = w - margin * 2
        chart_h = h - margin * 2

        if chart_w <= 0 or chart_h <= 0:
            return

        max_val = max(self._data.values()) if self._data.values() else 1
        n = len(self._data)

        if n < 2:
            return

        step = chart_w / (n - 1) if n > 1 else chart_w

        points = []
        labels_to_draw = []
        for i, (label, value) in enumerate(self._data.items()):
            x = margin + i * step
            y = margin + chart_h - (value / max_val) * chart_h if max_val > 0 else margin + chart_h
            points.append((x, y))
            if i % max(1, n // 8) == 0:
                labels_to_draw.append((x, label))

        # Draw area under line
        area_points = [(margin, margin + chart_h)]
        area_points.extend(points)
        area_points.append((margin + chart_w, margin + chart_h))
        flat = []
        for p in area_points:
            flat.extend(p)
        if len(flat) >= 6:
            self.create_polygon(*flat, fill="#ffcdd2", outline="")

        # Draw line
        if len(points) >= 2:
            flat_line = []
            for p in points:
                flat_line.extend(p)
            self.create_line(*flat_line, fill="#c62828", width=2, smooth=True)

        # Draw dots
        for x, y in points:
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#c62828", outline="white")

        # X-axis labels
        for x, label in labels_to_draw:
            self.create_text(x, margin + chart_h + 14, text=label,
                             font=("Segoe UI", 7), fill="#666", angle=0)

        # Title
        self.create_text(w // 2, 12, text="Error Timeline",
                         font=("Segoe UI", 10, "bold"), fill="#333")


class LogAnalyzerApp:
    """Main Log Analyzer application."""

    def __init__(self, root, embedded=False):
        self.root = root
        self.embedded = embedded
        if not embedded:
            self.root.title("Log Analyzer")
            self.root.geometry("1150x750")
            self.root.minsize(900, 600)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        self.style.configure("Stat.TLabel", font=("Segoe UI", 11))
        self.style.configure("StatVal.TLabel", font=("Segoe UI", 11, "bold"))

        self._all_lines = []
        self._filtered_lines = []
        self._file_path = None

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(toolbar, text="Log Analyzer", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="Open Log File", command=self._open_file).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Reload", command=self._reload_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Export Filtered", command=self._export_filtered).pack(side=tk.LEFT, padx=4)

        self.file_label = ttk.Label(toolbar, text="No file loaded")
        self.file_label.pack(side=tk.RIGHT)

        # Filter bar
        filter_frame = ttk.LabelFrame(self.root, text="Filters")
        filter_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

        filter_inner = ttk.Frame(filter_frame)
        filter_inner.pack(fill=tk.X, padx=8, pady=6)

        # Level checkboxes
        ttk.Label(filter_inner, text="Levels:").pack(side=tk.LEFT)
        self.level_vars = {}
        for level in LOG_LEVELS:
            var = tk.BooleanVar(value=True)
            self.level_vars[level] = var
            cb = ttk.Checkbutton(filter_inner, text=level, variable=var,
                                 command=self._apply_filters)
            cb.pack(side=tk.LEFT, padx=(6, 0))

        self.show_other_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_inner, text="OTHER", variable=self.show_other_var,
                        command=self._apply_filters).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(filter_inner, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Search / regex
        ttk.Label(filter_inner, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_inner, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=4)
        search_entry.bind("<Return>", lambda e: self._apply_filters())

        self.regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_inner, text="Regex", variable=self.regex_var).pack(side=tk.LEFT)
        ttk.Button(filter_inner, text="Apply", command=self._apply_filters).pack(side=tk.LEFT, padx=4)
        ttk.Button(filter_inner, text="Clear", command=self._clear_filters).pack(side=tk.LEFT)

        # Main content
        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # Top: log viewer
        log_frame = ttk.Frame(main_pane)
        main_pane.add(log_frame, weight=3)

        self.log_text = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9),
                                                   wrap=tk.NONE, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for levels
        for level, config in LOG_LEVELS.items():
            self.log_text.tag_configure(level, foreground=config["color"],
                                        background=config["bg"])
        self.log_text.tag_configure("stacktrace", foreground="#6a1b9a",
                                    font=("Consolas", 9, "italic"))
        self.log_text.tag_configure("exception", foreground="#b71c1c",
                                    font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("search_match", background="#fff176")

        # Bottom: stats and charts
        bottom_frame = ttk.Frame(main_pane)
        main_pane.add(bottom_frame, weight=1)

        bottom_nb = ttk.Notebook(bottom_frame)
        bottom_nb.pack(fill=tk.BOTH, expand=True)

        # Statistics tab
        stats_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(stats_frame, text="Statistics")
        self._build_stats_panel(stats_frame)

        # Chart tab
        chart_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(chart_frame, text="Level Chart")
        self.bar_chart = BarChart(chart_frame, height=180)
        self.bar_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.bar_chart.bind("<Configure>", lambda e: self._update_charts())

        # Timeline tab
        timeline_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(timeline_frame, text="Error Timeline")
        self.timeline_chart = TimelineChart(timeline_frame, height=180)
        self.timeline_chart.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.timeline_chart.bind("<Configure>", lambda e: self._update_timeline())

        # Patterns tab
        patterns_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(patterns_frame, text="Top Errors")
        self.patterns_text = scrolledtext.ScrolledText(patterns_frame, font=("Consolas", 9),
                                                       state="disabled", height=8)
        self.patterns_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _build_stats_panel(self, parent):
        grid = ttk.Frame(parent)
        grid.pack(padx=12, pady=8, fill=tk.X)

        self.stat_labels = {}
        stats = [
            ("total_lines", "Total Lines"),
            ("filtered_lines", "Filtered Lines"),
            ("critical", "CRITICAL"),
            ("errors", "Errors"),
            ("warnings", "Warnings"),
            ("info", "Info"),
            ("debug", "Debug"),
            ("other", "Other"),
            ("error_rate", "Error Rate"),
            ("file_size", "File Size"),
        ]

        for i, (key, label) in enumerate(stats):
            row = i // 5
            col = (i % 5) * 2
            ttk.Label(grid, text=f"{label}:", style="Stat.TLabel").grid(
                row=row, column=col, sticky="e", padx=(12, 4), pady=2)
            lbl = ttk.Label(grid, text="0", style="StatVal.TLabel")
            lbl.grid(row=row, column=col + 1, sticky="w", padx=(0, 12), pady=2)
            self.stat_labels[key] = lbl

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open Log File",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"),
                       ("All files", "*.*")]
        )
        if not path:
            return
        self._file_path = path
        self._load_file(path)

    def _reload_file(self):
        if self._file_path and os.path.exists(self._file_path):
            self._load_file(self._file_path)
        else:
            messagebox.showinfo("Reload", "No file loaded to reload.")

    def _load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self._all_lines = f.readlines()

            self.file_label.config(text=f"{os.path.basename(path)} ({len(self._all_lines)} lines)")

            # Get file size
            size = os.path.getsize(path)
            if size > 1024 * 1024:
                self.stat_labels["file_size"].config(text=f"{size / (1024*1024):.1f} MB")
            elif size > 1024:
                self.stat_labels["file_size"].config(text=f"{size / 1024:.1f} KB")
            else:
                self.stat_labels["file_size"].config(text=f"{size} B")

            self._apply_filters()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")

    def _classify_line(self, line):
        """Return the log level of a line."""
        upper = line.upper()
        for level, config in LOG_LEVELS.items():
            if re.search(config["pattern"], upper):
                return level
        return "OTHER"

    def _apply_filters(self):
        if not self._all_lines:
            return

        # Filter by level
        enabled_levels = {lvl for lvl, var in self.level_vars.items() if var.get()}
        if self.show_other_var.get():
            enabled_levels.add("OTHER")

        search_text = self.search_var.get().strip()
        use_regex = self.regex_var.get()

        if use_regex and search_text:
            try:
                search_pattern = re.compile(search_text, re.IGNORECASE)
            except re.error as e:
                messagebox.showerror("Regex Error", f"Invalid regex: {e}")
                return
        else:
            search_pattern = None

        self._filtered_lines = []
        level_counts = Counter()

        for line in self._all_lines:
            level = self._classify_line(line)
            level_counts[level] += 1

            if level not in enabled_levels:
                continue

            if search_text:
                if search_pattern:
                    if not search_pattern.search(line):
                        continue
                else:
                    if search_text.lower() not in line.lower():
                        continue

            self._filtered_lines.append((line, level))

        self._display_lines()
        self._update_stats(level_counts)
        self._update_charts()
        self._update_timeline()
        self._find_top_errors()

    def _display_lines(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)

        for line, level in self._filtered_lines:
            start = self.log_text.index("end-1c")
            self.log_text.insert(tk.END, line)
            end = self.log_text.index("end-1c")

            if level in LOG_LEVELS:
                self.log_text.tag_add(level, start, end)

            # Highlight stack traces
            if re.search(r'^\s+(?:at |File "|Traceback|    )', line):
                self.log_text.tag_add("stacktrace", start, end)

            # Highlight exception class names
            if re.search(r'\b\w*(Exception|Error|Failure)\b', line):
                for m in re.finditer(r'\b\w*(Exception|Error|Failure)\b', line):
                    ms = f"{start}+{m.start()}c"
                    me = f"{start}+{m.end()}c"
                    self.log_text.tag_add("exception", ms, me)

        # Highlight search matches
        search_text = self.search_var.get().strip()
        if search_text and not self.regex_var.get():
            start_idx = "1.0"
            while True:
                pos = self.log_text.search(search_text, start_idx, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(search_text)}c"
                self.log_text.tag_add("search_match", pos, end_pos)
                start_idx = end_pos

        self.log_text.config(state="disabled")

    def _update_stats(self, level_counts):
        total = len(self._all_lines)
        filtered = len(self._filtered_lines)

        self.stat_labels["total_lines"].config(text=str(total))
        self.stat_labels["filtered_lines"].config(text=str(filtered))
        self.stat_labels["critical"].config(text=str(level_counts.get("CRITICAL", 0)))
        self.stat_labels["errors"].config(text=str(level_counts.get("ERROR", 0)))
        self.stat_labels["warnings"].config(text=str(level_counts.get("WARNING", 0)))
        self.stat_labels["info"].config(text=str(level_counts.get("INFO", 0)))
        self.stat_labels["debug"].config(text=str(level_counts.get("DEBUG", 0)))
        self.stat_labels["other"].config(text=str(level_counts.get("OTHER", 0)))

        error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
        rate = (error_count / total * 100) if total > 0 else 0
        self.stat_labels["error_rate"].config(text=f"{rate:.1f}%")

        self._level_counts = level_counts

    def _update_charts(self):
        if not hasattr(self, '_level_counts'):
            return

        chart_data = {}
        chart_colors = {}
        for level in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
            count = self._level_counts.get(level, 0)
            if count > 0:
                chart_data[level] = count
                chart_colors[level] = LOG_LEVELS[level]["color"]

        self.bar_chart.set_data(chart_data, chart_colors)

    def _update_timeline(self):
        """Build a timeline of errors by extracting timestamps."""
        error_times = defaultdict(int)

        for line, level in self._filtered_lines:
            if level not in ("ERROR", "CRITICAL"):
                continue

            # Try to extract a timestamp
            for pattern in TIMESTAMP_PATTERNS:
                m = re.search(pattern, line)
                if m:
                    ts = m.group(1)
                    # Bucket by hour or just by the extracted time
                    # Try to parse and bucket by hour
                    parsed = False
                    for fmt in TIMESTAMP_FORMATS:
                        try:
                            dt = datetime.strptime(ts, fmt)
                            bucket = dt.strftime("%H:%M")
                            error_times[bucket] += 1
                            parsed = True
                            break
                        except ValueError:
                            continue

                    if not parsed:
                        # Use raw time string as bucket
                        error_times[ts[:8]] += 1
                    break

        if error_times:
            sorted_times = dict(sorted(error_times.items()))
            self.timeline_chart.set_data(sorted_times)
        else:
            self.timeline_chart.set_data({})

    def _find_top_errors(self):
        """Find and display the most common error messages."""
        error_messages = Counter()

        for line, level in self._filtered_lines:
            if level not in ("ERROR", "CRITICAL"):
                continue
            # Normalize the line by removing timestamps and variable data
            cleaned = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*', '<TIMESTAMP>', line)
            cleaned = re.sub(r'\b\d+\b', '<N>', cleaned)
            cleaned = cleaned.strip()
            if cleaned:
                error_messages[cleaned] += 1

        self.patterns_text.config(state="normal")
        self.patterns_text.delete("1.0", tk.END)

        if not error_messages:
            self.patterns_text.insert("1.0", "No errors found in filtered results.")
        else:
            self.patterns_text.insert("1.0", f"Top {min(20, len(error_messages))} most frequent errors:\n")
            self.patterns_text.insert(tk.END, "=" * 80 + "\n\n")

            for msg, count in error_messages.most_common(20):
                self.patterns_text.insert(tk.END, f"  [{count}x] {msg}\n")

        self.patterns_text.config(state="disabled")

    def _clear_filters(self):
        self.search_var.set("")
        for var in self.level_vars.values():
            var.set(True)
        self.show_other_var.set(True)
        self._apply_filters()

    def _export_filtered(self):
        if not self._filtered_lines:
            messagebox.showinfo("Export", "No filtered data to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export Filtered Results",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                for line, level in self._filtered_lines:
                    f.write(line)
            messagebox.showinfo("Exported", f"Exported {len(self._filtered_lines)} lines to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = LogAnalyzerApp(root)
    root.mainloop()
