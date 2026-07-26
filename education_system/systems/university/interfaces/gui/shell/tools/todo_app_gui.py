"""
Enhanced To-Do List Application
Features: Priorities, Due Dates, Categories, Search, Sort, Edit, Notes, Export
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import csv
from pathlib import Path
from datetime import datetime, date
from typing import Optional

# Import i18n for internationalization
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    # Fallback if i18n module is not available
    def _t(key, default=None, **kwargs):
        """Fallback translation function"""
        if default:
            return default
        return key.split('.')[-1].replace('_', ' ').title()


class DatePicker(tk.Toplevel):
    """Simple date picker dialog."""

    def __init__(self, parent, initial_date=None):
        super().__init__(parent)
        self.title(_t("todo.date_picker.title"))
        self.geometry("280x320")
        self.resizable(False, False)
        self.transient(parent)

        self.selected_date = initial_date
        self.current_date = initial_date or date.today()
        self.viewing_year = self.current_date.year
        self.viewing_month = self.current_date.month

        self.setup_ui()
        self.center_on_parent(parent)

        # Grab focus after window is visible
        self.wait_visibility()
        self.grab_set()

    def center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def setup_ui(self):
        # Header with month/year navigation
        header = tk.Frame(self, bg="#4a90d9")
        header.pack(fill="x", pady=(0, 5))

        tk.Button(header, text="<", command=self.prev_month,
                  bg="#4a90d9", fg="white", relief="flat", font=("Helvetica", 12, "bold"),
                  cursor="hand2").pack(side="left", padx=5, pady=5)

        self.month_label = tk.Label(header, text="", bg="#4a90d9", fg="white",
                                     font=("Helvetica", 12, "bold"))
        self.month_label.pack(side="left", expand=True, pady=5)

        tk.Button(header, text=">", command=self.next_month,
                  bg="#4a90d9", fg="white", relief="flat", font=("Helvetica", 12, "bold"),
                  cursor="hand2").pack(side="right", padx=5, pady=5)

        # Weekday headers
        days_frame = tk.Frame(self)
        days_frame.pack(fill="x", padx=10)
        for day in [_t("todo.date_picker.days.mo"), _t("todo.date_picker.days.tu"),
                     _t("todo.date_picker.days.we"), _t("todo.date_picker.days.th"),
                     _t("todo.date_picker.days.fr"), _t("todo.date_picker.days.sa"),
                     _t("todo.date_picker.days.su")]:
            tk.Label(days_frame, text=day, font=("Helvetica", 10, "bold"),
                    width=3, fg="#666").pack(side="left", expand=True)

        # Calendar grid
        self.cal_frame = tk.Frame(self)
        self.cal_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)

        tk.Button(btn_frame, text=_t("todo.buttons.clear"), command=self.clear_date,
                  bg="#e74c3c", fg="white", relief="flat", padx=15, pady=5,
                  cursor="hand2").pack(side="left")
        tk.Button(btn_frame, text=_t("todo.buttons.today"), command=self.select_today,
                  bg="#27ae60", fg="white", relief="flat", padx=15, pady=5,
                  cursor="hand2").pack(side="left", padx=10)
        tk.Button(btn_frame, text=_t("todo.buttons.cancel"), command=self.destroy,
                  bg="#95a5a6", fg="white", relief="flat", padx=15, pady=5,
                  cursor="hand2").pack(side="right")

        self.refresh_calendar()

    def refresh_calendar(self):
        for widget in self.cal_frame.winfo_children():
            widget.destroy()

        month_names = [_t("todo.date_picker.months.january"), _t("todo.date_picker.months.february"),
                       _t("todo.date_picker.months.march"), _t("todo.date_picker.months.april"),
                       _t("todo.date_picker.months.may"), _t("todo.date_picker.months.june"),
                       _t("todo.date_picker.months.july"), _t("todo.date_picker.months.august"),
                       _t("todo.date_picker.months.september"), _t("todo.date_picker.months.october"),
                       _t("todo.date_picker.months.november"), _t("todo.date_picker.months.december")]
        self.month_label.config(text=f"{month_names[self.viewing_month-1]} {self.viewing_year}")

        # Calculate first day and days in month
        first_day = date(self.viewing_year, self.viewing_month, 1)
        first_weekday = first_day.weekday()

        if self.viewing_month == 12:
            days_in_month = (date(self.viewing_year + 1, 1, 1) - first_day).days
        else:
            days_in_month = (date(self.viewing_year, self.viewing_month + 1, 1) - first_day).days

        day_num = 1
        for week in range(6):
            if day_num > days_in_month:
                break
            row_frame = tk.Frame(self.cal_frame)
            row_frame.pack(fill="x")

            for weekday in range(7):
                if week == 0 and weekday < first_weekday:
                    tk.Label(row_frame, text="", width=3).pack(side="left", expand=True)
                elif day_num <= days_in_month:
                    d = day_num
                    is_today = (self.viewing_year == date.today().year and
                               self.viewing_month == date.today().month and d == date.today().day)
                    is_selected = (self.selected_date and
                                  self.viewing_year == self.selected_date.year and
                                  self.viewing_month == self.selected_date.month and
                                  d == self.selected_date.day)

                    bg = "#4a90d9" if is_selected else ("#e8f4fc" if is_today else "white")
                    fg = "white" if is_selected else "black"

                    btn = tk.Button(row_frame, text=str(d), width=3,
                                   bg=bg, fg=fg, relief="flat",
                                   command=lambda day=d: self.select_date(day),
                                   cursor="hand2")
                    btn.pack(side="left", expand=True, pady=1)
                    day_num += 1
                else:
                    tk.Label(row_frame, text="", width=3).pack(side="left", expand=True)

    def prev_month(self):
        if self.viewing_month == 1:
            self.viewing_month = 12
            self.viewing_year -= 1
        else:
            self.viewing_month -= 1
        self.refresh_calendar()

    def next_month(self):
        if self.viewing_month == 12:
            self.viewing_month = 1
            self.viewing_year += 1
        else:
            self.viewing_month += 1
        self.refresh_calendar()

    def select_date(self, day):
        self.selected_date = date(self.viewing_year, self.viewing_month, day)
        self.destroy()

    def select_today(self):
        self.selected_date = date.today()
        self.destroy()

    def clear_date(self):
        self.selected_date = None
        self.destroy()


class TaskEditDialog(tk.Toplevel):
    """Dialog for editing task details."""

    PRIORITIES = [
        (_t("todo.priority.high"), "#e74c3c"),
        (_t("todo.priority.medium"), "#f39c12"),
        (_t("todo.priority.low"), "#27ae60"),
        (_t("todo.priority.none"), "#95a5a6")
    ]

    def __init__(self, parent, task=None, categories=None):
        super().__init__(parent)
        self.title(_t("todo.dialog.edit_task") if task else _t("todo.dialog.add_task"))
        self.geometry("450x500")
        self.resizable(False, False)
        self.transient(parent)

        self.task = task or {}
        self.categories = categories or []
        self.result = None
        self.selected_due_date = None

        if task and task.get("due_date"):
            try:
                self.selected_due_date = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        self.setup_ui()
        self.center_on_parent(parent)

        # Grab focus after window is visible
        self.wait_visibility()
        self.grab_set()

    def center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def setup_ui(self):
        main = tk.Frame(self, bg="white", padx=20, pady=15)
        main.pack(fill="both", expand=True)

        # Task Title
        tk.Label(main, text=_t("todo.fields.task_title"), font=("Helvetica", 11, "bold"),
                bg="white", anchor="w").pack(fill="x", pady=(0, 5))
        self.title_entry = tk.Entry(main, font=("Helvetica", 12), relief="flat",
                                    bg="#f8f8f8", highlightthickness=2,
                                    highlightcolor="#4a90d9", highlightbackground="#ddd")
        self.title_entry.pack(fill="x", ipady=8, pady=(0, 15))
        self.title_entry.insert(0, self.task.get("text", ""))

        # Priority
        tk.Label(main, text=_t("todo.fields.priority"), font=("Helvetica", 11, "bold"),
                bg="white", anchor="w").pack(fill="x", pady=(0, 5))
        priority_frame = tk.Frame(main, bg="white")
        priority_frame.pack(fill="x", pady=(0, 15))

        self.priority_var = tk.StringVar(value=self.task.get("priority", "None"))
        for priority, color in self.PRIORITIES:
            rb = tk.Radiobutton(priority_frame, text=priority, variable=self.priority_var,
                               value=priority, bg="white", activebackground="white",
                               font=("Helvetica", 10), fg=color, selectcolor="white",
                               cursor="hand2")
            rb.pack(side="left", padx=(0, 15))

        # Due Date
        tk.Label(main, text=_t("todo.fields.due_date"), font=("Helvetica", 11, "bold"),
                bg="white", anchor="w").pack(fill="x", pady=(0, 5))
        date_frame = tk.Frame(main, bg="white")
        date_frame.pack(fill="x", pady=(0, 15))

        self.date_label = tk.Label(date_frame, text=self.format_date(self.selected_due_date),
                                   font=("Helvetica", 11), bg="#f8f8f8", anchor="w",
                                   padx=10, pady=8, relief="flat")
        self.date_label.pack(side="left", fill="x", expand=True)

        tk.Button(date_frame, text=_t("todo.buttons.pick"), command=self.pick_date,
                 bg="#4a90d9", fg="white", relief="flat", padx=12, pady=5,
                 cursor="hand2").pack(side="right", padx=(10, 0))

        # Category
        tk.Label(main, text=_t("todo.fields.category"), font=("Helvetica", 11, "bold"),
                bg="white", anchor="w").pack(fill="x", pady=(0, 5))
        cat_frame = tk.Frame(main, bg="white")
        cat_frame.pack(fill="x", pady=(0, 15))

        self.category_var = tk.StringVar(value=self.task.get("category", ""))
        self.category_combo = ttk.Combobox(cat_frame, textvariable=self.category_var,
                                           font=("Helvetica", 11), values=self.categories)
        self.category_combo.pack(side="left", fill="x", expand=True)

        # Notes
        tk.Label(main, text=_t("todo.fields.notes"), font=("Helvetica", 11, "bold"),
                bg="white", anchor="w").pack(fill="x", pady=(0, 5))
        self.notes_text = tk.Text(main, font=("Helvetica", 11), height=5,
                                  relief="flat", bg="#f8f8f8", highlightthickness=2,
                                  highlightcolor="#4a90d9", highlightbackground="#ddd")
        self.notes_text.pack(fill="x", pady=(0, 20))
        self.notes_text.insert("1.0", self.task.get("notes", ""))

        # Buttons
        btn_frame = tk.Frame(main, bg="white")
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text=_t("todo.buttons.cancel"), command=self.destroy,
                 bg="#95a5a6", fg="white", relief="flat", padx=25, pady=8,
                 font=("Helvetica", 11), cursor="hand2").pack(side="right")
        tk.Button(btn_frame, text=_t("todo.buttons.save"), command=self.save,
                 bg="#27ae60", fg="white", relief="flat", padx=25, pady=8,
                 font=("Helvetica", 11), cursor="hand2").pack(side="right", padx=(0, 10))

        self.title_entry.focus_set()
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())

    def format_date(self, d):
        if not d:
            return _t("todo.date.no_date_set")
        today = date.today()
        if d == today:
            return _t("todo.date.today", date=d.strftime('%b %d'))
        elif d == date(today.year, today.month, today.day + 1 if today.day < 28 else 1):
            return _t("todo.date.tomorrow", date=d.strftime('%b %d'))
        return d.strftime("%b %d, %Y")

    def pick_date(self):
        picker = DatePicker(self, self.selected_due_date)
        self.wait_window(picker)
        self.selected_due_date = picker.selected_date
        self.date_label.config(text=self.format_date(self.selected_due_date))

    def save(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror(_t("todo.errors.title"), _t("todo.errors.task_title_required"), parent=self)
            return

        self.result = {
            "text": title,
            "priority": self.priority_var.get(),
            "due_date": self.selected_due_date.strftime("%Y-%m-%d") if self.selected_due_date else None,
            "category": self.category_var.get().strip(),
            "notes": self.notes_text.get("1.0", "end-1c").strip(),
            "completed": self.task.get("completed", False),
            "created_at": self.task.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        }
        self.destroy()


class TodoApp:
    """Enhanced To-Do List Application."""

    PRIORITY_COLORS = {
        "High": "#e74c3c",
        "Medium": "#f39c12",
        "Low": "#27ae60",
        "None": "#95a5a6"
    }

    def __init__(self, root):
        self.root = root
        self.root.title(_t("todo.title"))
        self.root.geometry("600x700")
        self.root.configure(bg="#f5f5f5")
        self.root.minsize(500, 500)

        self.data_file = Path.home() / ".todo_data_v2.json"
        self.tasks = []
        self.categories = []
        self.filter_category = "All"
        self.filter_status = "All"
        self.filter_priority = "All"
        self.search_query = ""
        self.sort_by = "created"  # created, priority, due_date, alpha
        self.sort_reverse = False

        self.load_data()
        self.setup_ui()
        self.refresh_task_list()
        self.setup_keyboard_shortcuts()

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts."""
        self.root.bind("<Control-n>", lambda e: self.add_task())
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.root.bind("<Control-e>", lambda e: self.export_tasks())
        self.root.bind("<F5>", lambda e: self.refresh_task_list())

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#4a90d9", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_content = tk.Frame(header, bg="#4a90d9")
        header_content.pack(expand=True)

        title = tk.Label(header_content, text=_t("todo.header.title"),
                        font=("Helvetica", 22, "bold"),
                        bg="#4a90d9", fg="white")
        title.pack(side="left")

        shortcuts_hint = tk.Label(header_content, text=_t("todo.header.shortcuts"),
                                 font=("Helvetica", 9), bg="#4a90d9", fg="#b8d4ed")
        shortcuts_hint.pack(side="right", padx=20)

        # Toolbar
        toolbar = tk.Frame(self.root, bg="#e8e8e8", pady=10, padx=15)
        toolbar.pack(fill="x")

        # Add Task Button
        add_btn = tk.Button(toolbar, text=_t("todo.buttons.new_task"), font=("Helvetica", 11, "bold"),
                           bg="#27ae60", fg="white", relief="flat", padx=15, pady=6,
                           cursor="hand2", command=self.add_task)
        add_btn.pack(side="left")

        # Search
        search_frame = tk.Frame(toolbar, bg="#e8e8e8")
        search_frame.pack(side="left", padx=20, fill="x", expand=True)

        tk.Label(search_frame, text="🔍", bg="#e8e8e8", font=("Helvetica", 12)).pack(side="left")
        self.search_entry = tk.Entry(search_frame, font=("Helvetica", 11), relief="flat",
                                     bg="white", highlightthickness=1, highlightbackground="#ddd")
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=5)
        self.search_entry.bind("<KeyRelease>", self.on_search)

        # Export Button
        export_btn = tk.Button(toolbar, text=_t("todo.buttons.export_csv"), font=("Helvetica", 10),
                              bg="#3498db", fg="white", relief="flat", padx=10, pady=5,
                              cursor="hand2", command=self.export_tasks)
        export_btn.pack(side="right")

        # Filter Bar
        filter_bar = tk.Frame(self.root, bg="#f0f0f0", pady=8, padx=15)
        filter_bar.pack(fill="x")

        # Status Filter
        tk.Label(filter_bar, text=_t("todo.filters.status"), bg="#f0f0f0", font=("Helvetica", 10)).pack(side="left")
        self.status_var = tk.StringVar(value="All")
        status_menu = ttk.Combobox(filter_bar, textvariable=self.status_var, width=10,
                                   values=[_t("todo.filters.all"), _t("todo.filters.active"), _t("todo.filters.completed")], state="readonly")
        status_menu.pack(side="left", padx=(5, 15))
        status_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Priority Filter
        tk.Label(filter_bar, text=_t("todo.filters.priority"), bg="#f0f0f0", font=("Helvetica", 10)).pack(side="left")
        self.priority_filter_var = tk.StringVar(value="All")
        priority_menu = ttk.Combobox(filter_bar, textvariable=self.priority_filter_var, width=10,
                                     values=[_t("todo.filters.all"), _t("todo.priority.high"), _t("todo.priority.medium"), _t("todo.priority.low"), _t("todo.priority.none")], state="readonly")
        priority_menu.pack(side="left", padx=(5, 15))
        priority_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Category Filter
        tk.Label(filter_bar, text=_t("todo.filters.category"), bg="#f0f0f0", font=("Helvetica", 10)).pack(side="left")
        self.category_filter_var = tk.StringVar(value="All")
        self.category_menu = ttk.Combobox(filter_bar, textvariable=self.category_filter_var, width=12,
                                          values=[_t("todo.filters.all")] + self.categories, state="readonly")
        self.category_menu.pack(side="left", padx=(5, 15))
        self.category_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Sort Options
        tk.Label(filter_bar, text=_t("todo.filters.sort"), bg="#f0f0f0", font=("Helvetica", 10)).pack(side="left")
        self.sort_var = tk.StringVar(value=_t("todo.sort.created"))
        sort_menu = ttk.Combobox(filter_bar, textvariable=self.sort_var, width=10,
                                 values=[_t("todo.sort.created"), _t("todo.sort.priority"), _t("todo.sort.due_date"), _t("todo.sort.az")], state="readonly")
        sort_menu.pack(side="left", padx=(5, 5))
        sort_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_sort())

        self.sort_order_btn = tk.Button(filter_bar, text="↓", font=("Helvetica", 10, "bold"),
                                        bg="#f0f0f0", relief="flat", cursor="hand2",
                                        command=self.toggle_sort_order)
        self.sort_order_btn.pack(side="left")

        # Task List Area
        list_frame = tk.Frame(self.root, bg="#f5f5f5", padx=15, pady=10)
        list_frame.pack(fill="both", expand=True)

        # Canvas for scrollable task list
        self.canvas = tk.Canvas(list_frame, bg="#f5f5f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)

        self.task_container = tk.Frame(self.canvas, bg="#f5f5f5")

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.task_container, anchor="nw")

        self.task_container.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # Footer with Stats
        self.footer = tk.Frame(self.root, bg="#e8e8e8", height=60)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        stats_frame = tk.Frame(self.footer, bg="#e8e8e8")
        stats_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.stats_label = tk.Label(stats_frame, text="", font=("Helvetica", 11),
                                    bg="#e8e8e8", fg="#555")
        self.stats_label.pack(side="left")

        # Progress bar
        self.progress_frame = tk.Frame(stats_frame, bg="#ddd", height=8, width=150)
        self.progress_frame.pack(side="left", padx=20)
        self.progress_frame.pack_propagate(False)

        self.progress_bar = tk.Frame(self.progress_frame, bg="#27ae60", height=8)
        self.progress_bar.pack(side="left", fill="y")

        clear_btn = tk.Button(stats_frame, text=_t("todo.buttons.clear_completed"), font=("Helvetica", 10),
                             bg="#e74c3c", fg="white", relief="flat", padx=12, pady=5,
                             cursor="hand2", command=self.clear_completed)
        clear_btn.pack(side="right")

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_search(self, event=None):
        self.search_query = self.search_entry.get().strip().lower()
        self.refresh_task_list()

    def apply_filters(self):
        self.filter_status = self.status_var.get()
        self.filter_priority = self.priority_filter_var.get()
        self.filter_category = self.category_filter_var.get()
        self.refresh_task_list()

    def apply_sort(self):
        sort_map = {
            _t("todo.sort.created"): "created",
            _t("todo.sort.priority"): "priority",
            _t("todo.sort.due_date"): "due_date",
            _t("todo.sort.az"): "alpha"
        }
        self.sort_by = sort_map.get(self.sort_var.get(), "created")
        self.refresh_task_list()

    def toggle_sort_order(self):
        self.sort_reverse = not self.sort_reverse
        self.sort_order_btn.config(text="↑" if self.sort_reverse else "↓")
        self.refresh_task_list()

    def get_filtered_tasks(self):
        """Get tasks filtered and sorted."""
        tasks = list(self.tasks)

        # Apply search
        if self.search_query:
            tasks = [t for t in tasks if self.search_query in t.get("text", "").lower() or
                     self.search_query in t.get("notes", "").lower() or
                     self.search_query in t.get("category", "").lower()]

        # Apply status filter
        if self.filter_status == "Active":
            tasks = [t for t in tasks if not t.get("completed")]
        elif self.filter_status == "Completed":
            tasks = [t for t in tasks if t.get("completed")]

        # Apply priority filter
        if self.filter_priority != "All":
            tasks = [t for t in tasks if t.get("priority") == self.filter_priority]

        # Apply category filter
        if self.filter_category != "All":
            tasks = [t for t in tasks if t.get("category") == self.filter_category]

        # Sort
        priority_order = {"High": 0, "Medium": 1, "Low": 2, "None": 3}

        if self.sort_by == "priority":
            tasks.sort(key=lambda t: priority_order.get(t.get("priority", "None"), 3))
        elif self.sort_by == "due_date":
            tasks.sort(key=lambda t: t.get("due_date") or "9999-99-99")
        elif self.sort_by == "alpha":
            tasks.sort(key=lambda t: t.get("text", "").lower())
        else:  # created
            tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

        if self.sort_reverse:
            tasks.reverse()

        return tasks

    def add_task(self, event=None):
        """Open dialog to add new task."""
        dialog = TaskEditDialog(self.root, categories=self.categories)
        self.root.wait_window(dialog)

        if dialog.result:
            self.tasks.append(dialog.result)
            if dialog.result.get("category") and dialog.result["category"] not in self.categories:
                self.categories.append(dialog.result["category"])
                self.update_category_menu()
            self.save_data()
            self.refresh_task_list()

    def edit_task(self, task):
        """Open dialog to edit task."""
        dialog = TaskEditDialog(self.root, task=task, categories=self.categories)
        self.root.wait_window(dialog)

        if dialog.result:
            idx = self.tasks.index(task)
            self.tasks[idx] = dialog.result
            if dialog.result.get("category") and dialog.result["category"] not in self.categories:
                self.categories.append(dialog.result["category"])
                self.update_category_menu()
            self.save_data()
            self.refresh_task_list()

    def toggle_task(self, task):
        task["completed"] = not task.get("completed", False)
        self.save_data()
        self.refresh_task_list()

    def delete_task(self, task):
        if messagebox.askyesno(_t("todo.confirm.delete_title"), _t("todo.confirm.delete_message", task=task['text'][:50])):
            self.tasks.remove(task)
            self.save_data()
            self.refresh_task_list()

    def clear_completed(self):
        completed = [t for t in self.tasks if t.get("completed")]
        if not completed:
            messagebox.showinfo(_t("todo.info.title"), _t("todo.info.no_completed_tasks"))
            return

        if messagebox.askyesno(_t("todo.confirm.title"), _t("todo.confirm.clear_completed", count=len(completed))):
            self.tasks = [t for t in self.tasks if not t.get("completed")]
            self.save_data()
            self.refresh_task_list()

    def update_category_menu(self):
        self.category_menu.config(values=[_t("todo.filters.all")] + sorted(self.categories))

    def refresh_task_list(self):
        """Refresh the task list display."""
        for widget in self.task_container.winfo_children():
            widget.destroy()

        filtered_tasks = self.get_filtered_tasks()

        if not filtered_tasks:
            if self.tasks:
                msg = _t("todo.messages.no_tasks_match")
            else:
                msg = _t("todo.messages.no_tasks_yet")

            empty_label = tk.Label(self.task_container, text=msg,
                                  font=("Helvetica", 14), bg="#f5f5f5", fg="#999", pady=50)
            empty_label.pack()
        else:
            for task in filtered_tasks:
                self.create_task_widget(task)

        # Update stats
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.get("completed"))
        showing = len(filtered_tasks)

        if showing != total:
            self.stats_label.config(text=_t("todo.stats.showing_filtered", showing=showing, total=total, completed=completed))
        else:
            self.stats_label.config(text=_t("todo.stats.completed", completed=completed, total=total))

        # Update progress bar
        progress_pct = (completed / total * 100) if total > 0 else 0
        self.progress_bar.config(width=int(1.5 * progress_pct))

    def create_task_widget(self, task):
        """Create a task widget."""
        is_completed = task.get("completed", False)
        priority = task.get("priority", "None")
        priority_color = self.PRIORITY_COLORS.get(priority, "#95a5a6")

        # Main frame with priority indicator
        outer_frame = tk.Frame(self.task_container, bg="#f5f5f5")
        outer_frame.pack(fill="x", pady=3)

        # Priority indicator bar
        priority_bar = tk.Frame(outer_frame, bg=priority_color, width=4)
        priority_bar.pack(side="left", fill="y")

        # Task content frame
        frame = tk.Frame(outer_frame, bg="white" if not is_completed else "#f8f8f8",
                        pady=8, padx=12)
        frame.pack(side="left", fill="x", expand=True)

        # Top row: checkbox, title, buttons
        top_row = tk.Frame(frame, bg=frame.cget("bg"))
        top_row.pack(fill="x")

        # Checkbox
        check_var = tk.BooleanVar(value=is_completed)
        checkbox = tk.Checkbutton(top_row, variable=check_var, bg=frame.cget("bg"),
                                  activebackground=frame.cget("bg"),
                                  command=lambda: self.toggle_task(task))
        checkbox.pack(side="left")

        # Task text
        fg_color = "#999" if is_completed else "#333"
        font_style = ("Helvetica", 12, "overstrike") if is_completed else ("Helvetica", 12)

        task_label = tk.Label(top_row, text=task.get("text", ""), font=font_style,
                             bg=frame.cget("bg"), fg=fg_color, anchor="w", cursor="hand2")
        task_label.pack(side="left", fill="x", expand=True, padx=8)
        task_label.bind("<Double-Button-1>", lambda e: self.edit_task(task))

        # Buttons
        edit_btn = tk.Button(top_row, text="✎", font=("Helvetica", 12),
                            bg=frame.cget("bg"), fg="#3498db", relief="flat",
                            cursor="hand2", command=lambda: self.edit_task(task))
        edit_btn.pack(side="right", padx=2)

        delete_btn = tk.Button(top_row, text="×", font=("Helvetica", 14, "bold"),
                              bg=frame.cget("bg"), fg="#e74c3c", relief="flat",
                              cursor="hand2", command=lambda: self.delete_task(task))
        delete_btn.pack(side="right")

        # Bottom row: metadata (due date, category, notes indicator)
        has_metadata = task.get("due_date") or task.get("category") or task.get("notes")

        if has_metadata:
            bottom_row = tk.Frame(frame, bg=frame.cget("bg"))
            bottom_row.pack(fill="x", pady=(5, 0))

            # Due date
            if task.get("due_date"):
                due = task["due_date"]
                try:
                    due_date = datetime.strptime(due, "%Y-%m-%d").date()
                    today = date.today()
                    if due_date < today:
                        due_text = _t("todo.due.overdue", date=due_date.strftime('%b %d'))
                        due_fg = "#e74c3c"
                    elif due_date == today:
                        due_text = _t("todo.due.today")
                        due_fg = "#e67e22"
                    else:
                        due_text = _t("todo.due.date", date=due_date.strftime('%b %d'))
                        due_fg = "#666"
                except ValueError:
                    due_text = _t("todo.due.date", date=due)
                    due_fg = "#666"

                tk.Label(bottom_row, text=due_text, font=("Helvetica", 9),
                        bg=frame.cget("bg"), fg=due_fg).pack(side="left", padx=(25, 10))

            # Category
            if task.get("category"):
                tk.Label(bottom_row, text=f"📁 {task['category']}", font=("Helvetica", 9),
                        bg=frame.cget("bg"), fg="#888").pack(side="left", padx=(0, 10))

            # Notes indicator
            if task.get("notes"):
                tk.Label(bottom_row, text=_t("todo.task.has_notes"), font=("Helvetica", 9),
                        bg=frame.cget("bg"), fg="#888").pack(side="left")

    def export_tasks(self):
        """Export tasks to CSV file."""
        if not self.tasks:
            messagebox.showinfo(_t("todo.info.title"), _t("todo.info.no_tasks_to_export"))
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="todo_export.csv"
        )

        if filepath:
            try:
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        _t("todo.export.task"),
                        _t("todo.export.priority"),
                        _t("todo.export.due_date"),
                        _t("todo.export.category"),
                        _t("todo.export.notes"),
                        _t("todo.export.completed"),
                        _t("todo.export.created")
                    ])
                    for task in self.tasks:
                        writer.writerow([
                            task.get("text", ""),
                            task.get("priority", "None"),
                            task.get("due_date", ""),
                            task.get("category", ""),
                            task.get("notes", ""),
                            _t("todo.export.yes") if task.get("completed") else _t("todo.export.no"),
                            task.get("created_at", "")
                        ])
                messagebox.showinfo(_t("todo.success.title"), _t("todo.success.export", count=len(self.tasks), path=filepath))
            except Exception as e:
                messagebox.showerror(_t("todo.errors.title"), _t("todo.errors.export_failed", error=str(e)))

    def load_data(self):
        """Load tasks and categories from file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    self.tasks = data.get("tasks", [])
                    self.categories = data.get("categories", [])

                    # Migrate old format if needed
                    if isinstance(data, list):
                        self.tasks = data
                        for task in self.tasks:
                            if "priority" not in task:
                                task["priority"] = "None"
                            if "created_at" not in task:
                                task["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            except (json.JSONDecodeError, IOError):
                self.tasks = []
                self.categories = []

        # Extract categories from tasks
        for task in self.tasks:
            cat = task.get("category", "")
            if cat and cat not in self.categories:
                self.categories.append(cat)

    def save_data(self):
        """Save tasks and categories to file."""
        data = {
            "tasks": self.tasks,
            "categories": sorted(set(self.categories))
        }
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()
