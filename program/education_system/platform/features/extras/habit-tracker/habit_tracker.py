"""
Habit Tracker with Points & Consequences
A daily habit tracking application with streak tracking, point system,
calendar view, and statistics.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import calendar
from datetime import datetime, timedelta, date


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habits.db")

POINTS_COMPLETED = 10
POINTS_MISSED = -5


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL DEFAULT 'General',
                created_date TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS habit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
                UNIQUE(habit_id, log_date)
            );
        """)
        conn.commit()
    finally:
        conn.close()


class HabitTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Habit Tracker")
        self.geometry("1000x700")
        self.minsize(900, 600)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Stats.TLabel", font=("Segoe UI", 11))
        style.configure("Points.TLabel", font=("Segoe UI", 14, "bold"), foreground="#2e7d32")
        style.configure("Negative.TLabel", font=("Segoe UI", 14, "bold"), foreground="#c62828")
        style.configure("Streak.TLabel", font=("Segoe UI", 12, "bold"), foreground="#e65100")
        style.configure("Complete.TButton", foreground="#2e7d32")
        style.configure("Missed.TButton", foreground="#c62828")

        init_db()
        self.today = date.today()
        self.cal_year = self.today.year
        self.cal_month = self.today.month
        self.selected_habit_id = None

        self._build_ui()
        self._refresh_habits()
        self._refresh_stats()
        self._apply_missed_penalties()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Habit Tracker", style="Title.TLabel").pack(side=tk.LEFT)
        self.points_label = ttk.Label(top, text="Total Points: 0", style="Points.TLabel")
        self.points_label.pack(side=tk.RIGHT, padx=20)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # -- Today tab --
        today_frame = ttk.Frame(notebook, padding=10)
        notebook.add(today_frame, text="  Today  ")

        add_frame = ttk.LabelFrame(today_frame, text="Add New Habit", padding=10)
        add_frame.pack(fill=tk.X, pady=(0, 10))

        row = ttk.Frame(add_frame)
        row.pack(fill=tk.X)
        ttk.Label(row, text="Habit:").pack(side=tk.LEFT)
        self.habit_name_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.habit_name_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Category:").pack(side=tk.LEFT, padx=(10, 0))
        self.category_var = tk.StringVar(value="General")
        cat_combo = ttk.Combobox(row, textvariable=self.category_var, width=15,
                                 values=["General", "Health", "Fitness", "Learning",
                                         "Productivity", "Mindfulness", "Social", "Finance"])
        cat_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(row, text="Add Habit", command=self._add_habit).pack(side=tk.LEFT, padx=10)

        list_frame = ttk.LabelFrame(today_frame, text=f"Today's Habits - {self.today.strftime('%A, %d %B %Y')}", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("name", "category", "streak", "status", "points")
        self.habit_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=12)
        self.habit_tree.heading("name", text="Habit")
        self.habit_tree.heading("category", text="Category")
        self.habit_tree.heading("streak", text="Streak")
        self.habit_tree.heading("status", text="Today")
        self.habit_tree.heading("points", text="Points")
        self.habit_tree.column("name", width=200)
        self.habit_tree.column("category", width=120)
        self.habit_tree.column("streak", width=80, anchor=tk.CENTER)
        self.habit_tree.column("status", width=100, anchor=tk.CENTER)
        self.habit_tree.column("points", width=80, anchor=tk.CENTER)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.habit_tree.yview)
        self.habit_tree.configure(yscrollcommand=scroll.set)
        self.habit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(today_frame, padding=(0, 10))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Mark Complete", style="Complete.TButton",
                   command=self._mark_complete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Mark Missed", style="Missed.TButton",
                   command=self._mark_missed).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Habit", command=self._remove_habit).pack(side=tk.LEFT, padx=5)

        # -- Calendar tab --
        cal_frame = ttk.Frame(notebook, padding=10)
        notebook.add(cal_frame, text="  Calendar  ")

        cal_top = ttk.Frame(cal_frame)
        cal_top.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(cal_top, text="<", width=3, command=self._prev_month).pack(side=tk.LEFT)
        self.cal_title = ttk.Label(cal_top, text="", style="Heading.TLabel")
        self.cal_title.pack(side=tk.LEFT, padx=20)
        ttk.Button(cal_top, text=">", width=3, command=self._next_month).pack(side=tk.LEFT)

        ttk.Label(cal_top, text="Habit:").pack(side=tk.LEFT, padx=(30, 5))
        self.cal_habit_var = tk.StringVar()
        self.cal_habit_combo = ttk.Combobox(cal_top, textvariable=self.cal_habit_var, width=25, state="readonly")
        self.cal_habit_combo.pack(side=tk.LEFT, padx=5)
        self.cal_habit_combo.bind("<<ComboboxSelected>>", lambda e: self._draw_calendar())

        self.cal_canvas = tk.Canvas(cal_frame, bg="white", highlightthickness=1, highlightbackground="#bbb")
        self.cal_canvas.pack(fill=tk.BOTH, expand=True)
        self.cal_canvas.bind("<Configure>", lambda e: self._draw_calendar())

        legend = ttk.Frame(cal_frame)
        legend.pack(fill=tk.X, pady=(5, 0))
        for color, label in [("#4caf50", "Completed"), ("#ef5350", "Missed"), ("#e0e0e0", "No data")]:
            c = tk.Canvas(legend, width=16, height=16, highlightthickness=0)
            c.create_rectangle(0, 0, 16, 16, fill=color, outline="")
            c.pack(side=tk.LEFT, padx=(10, 2))
            ttk.Label(legend, text=label).pack(side=tk.LEFT)

        # -- Stats tab --
        stats_frame = ttk.Frame(notebook, padding=10)
        notebook.add(stats_frame, text="  Statistics  ")

        self.stats_text = tk.Text(stats_frame, font=("Consolas", 11), wrap=tk.WORD,
                                  state=tk.DISABLED, bg="#fafafa", relief=tk.FLAT)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

    def _get_streak(self, habit_id):
        conn = get_conn()
        try:
            streak = 0
            d = self.today
            while True:
                row = conn.execute(
                    "SELECT completed FROM habit_log WHERE habit_id=? AND log_date=?",
                    (habit_id, d.isoformat())
                ).fetchone()
                if row and row["completed"] == 1:
                    streak += 1
                    d -= timedelta(days=1)
                else:
                    break
            return streak
        finally:
            conn.close()

    def _get_total_points(self):
        conn = get_conn()
        try:
            row = conn.execute("SELECT COALESCE(SUM(points), 0) AS total FROM habit_log").fetchone()
            return row["total"]
        finally:
            conn.close()

    def _refresh_habits(self):
        self.habit_tree.delete(*self.habit_tree.get_children())
        conn = get_conn()
        try:
            habits = conn.execute("SELECT * FROM habits WHERE active=1 ORDER BY name").fetchall()
            today_str = self.today.isoformat()
            habit_names = []
            for h in habits:
                log = conn.execute(
                    "SELECT completed, points FROM habit_log WHERE habit_id=? AND log_date=?",
                    (h["id"], today_str)
                ).fetchone()
                streak = self._get_streak(h["id"])
                status = "Pending"
                pts = 0
                if log:
                    status = "Done" if log["completed"] else "Missed"
                    pts = log["points"]
                self.habit_tree.insert("", tk.END, iid=str(h["id"]),
                                       values=(h["name"], h["category"],
                                               f"{streak} days" if streak else "0",
                                               status, pts))
                habit_names.append(h["name"])
            self.cal_habit_combo["values"] = ["All Habits"] + habit_names
            if not self.cal_habit_var.get():
                self.cal_habit_var.set("All Habits")
            total = self._get_total_points()
            if total >= 0:
                self.points_label.configure(text=f"Total Points: {total}", style="Points.TLabel")
            else:
                self.points_label.configure(text=f"Total Points: {total}", style="Negative.TLabel")
        finally:
            conn.close()

    def _add_habit(self):
        name = self.habit_name_var.get().strip()
        if not name:
            messagebox.showwarning("Input Required", "Please enter a habit name.")
            return
        category = self.category_var.get()
        conn = get_conn()
        try:
            conn.execute("INSERT INTO habits (name, category, created_date) VALUES (?, ?, ?)",
                         (name, category, self.today.isoformat()))
            conn.commit()
            self.habit_name_var.set("")
            self._refresh_habits()
        except sqlite3.IntegrityError:
            messagebox.showwarning("Duplicate", f"Habit '{name}' already exists.")
        finally:
            conn.close()

    def _remove_habit(self):
        sel = self.habit_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a habit to remove.")
            return
        habit_id = int(sel[0])
        name = self.habit_tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm", f"Remove habit '{name}' and all its history?"):
            conn = get_conn()
            try:
                conn.execute("DELETE FROM habit_log WHERE habit_id=?", (habit_id,))
                conn.execute("DELETE FROM habits WHERE id=?", (habit_id,))
                conn.commit()
                self._refresh_habits()
                self._refresh_stats()
            finally:
                conn.close()

    def _mark_complete(self):
        self._log_habit(completed=True)

    def _mark_missed(self):
        self._log_habit(completed=False)

    def _log_habit(self, completed):
        sel = self.habit_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a habit.")
            return
        habit_id = int(sel[0])
        today_str = self.today.isoformat()
        points = POINTS_COMPLETED if completed else POINTS_MISSED
        conn = get_conn()
        try:
            conn.execute("""
                INSERT INTO habit_log (habit_id, log_date, completed, points)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(habit_id, log_date)
                DO UPDATE SET completed=excluded.completed, points=excluded.points
            """, (habit_id, today_str, 1 if completed else 0, points))
            conn.commit()
            self._refresh_habits()
            self._refresh_stats()
            self._draw_calendar()
        finally:
            conn.close()

    def _apply_missed_penalties(self):
        """Apply missed penalties for yesterday if habits weren't logged."""
        yesterday = (self.today - timedelta(days=1)).isoformat()
        conn = get_conn()
        try:
            habits = conn.execute("SELECT id FROM habits WHERE active=1").fetchall()
            for h in habits:
                existing = conn.execute(
                    "SELECT id FROM habit_log WHERE habit_id=? AND log_date=?",
                    (h["id"], yesterday)
                ).fetchone()
                created = conn.execute(
                    "SELECT created_date FROM habits WHERE id=?", (h["id"],)
                ).fetchone()
                if created and created["created_date"] <= yesterday and not existing:
                    conn.execute(
                        "INSERT INTO habit_log (habit_id, log_date, completed, points) VALUES (?, ?, 0, ?)",
                        (h["id"], yesterday, POINTS_MISSED)
                    )
            conn.commit()
        finally:
            conn.close()

    def _prev_month(self):
        if self.cal_month == 1:
            self.cal_month = 12
            self.cal_year -= 1
        else:
            self.cal_month -= 1
        self._draw_calendar()

    def _next_month(self):
        if self.cal_month == 12:
            self.cal_month = 1
            self.cal_year += 1
        else:
            self.cal_month += 1
        self._draw_calendar()

    def _draw_calendar(self):
        self.cal_canvas.delete("all")
        w = self.cal_canvas.winfo_width()
        h = self.cal_canvas.winfo_height()
        if w < 10 or h < 10:
            return

        self.cal_title.configure(
            text=f"{calendar.month_name[self.cal_month]} {self.cal_year}")

        conn = get_conn()
        try:
            habit_name = self.cal_habit_var.get()
            if habit_name and habit_name != "All Habits":
                row = conn.execute("SELECT id FROM habits WHERE name=?", (habit_name,)).fetchone()
                if row:
                    logs = conn.execute(
                        "SELECT log_date, completed FROM habit_log WHERE habit_id=? AND log_date LIKE ?",
                        (row["id"], f"{self.cal_year}-{self.cal_month:02d}-%")
                    ).fetchall()
                else:
                    logs = []
            else:
                # All habits: day is complete if all habits done, missed if any missed
                logs_raw = conn.execute(
                    "SELECT log_date, MIN(completed) as completed FROM habit_log WHERE log_date LIKE ? GROUP BY log_date",
                    (f"{self.cal_year}-{self.cal_month:02d}-%",)
                ).fetchall()
                logs = logs_raw

            day_status = {}
            for log in logs:
                day = int(log["log_date"].split("-")[2])
                day_status[day] = log["completed"]
        finally:
            conn.close()

        days_in_month = calendar.monthrange(self.cal_year, self.cal_month)[1]
        first_weekday = calendar.monthrange(self.cal_year, self.cal_month)[0]  # 0=Mon

        cell_w = w / 7
        header_h = 30
        cell_h = (h - header_h) / 7

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, dn in enumerate(day_names):
            x = i * cell_w + cell_w / 2
            self.cal_canvas.create_text(x, header_h / 2, text=dn, font=("Segoe UI", 10, "bold"))

        day_num = 1
        for row in range(6):
            for col in range(7):
                idx = row * 7 + col
                if idx < first_weekday or day_num > days_in_month:
                    continue
                x1 = col * cell_w + 2
                y1 = header_h + row * cell_h + 2
                x2 = (col + 1) * cell_w - 2
                y2 = header_h + (row + 1) * cell_h - 2

                if day_num in day_status:
                    fill = "#4caf50" if day_status[day_num] else "#ef5350"
                else:
                    fill = "#e0e0e0"

                today_check = (self.cal_year == self.today.year and
                               self.cal_month == self.today.month and
                               day_num == self.today.day)
                outline = "#1565c0" if today_check else "#bbb"
                width = 3 if today_check else 1

                self.cal_canvas.create_rectangle(x1, y1, x2, y2, fill=fill,
                                                  outline=outline, width=width)
                self.cal_canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2,
                                             text=str(day_num), font=("Segoe UI", 12))
                day_num += 1

    def _refresh_stats(self):
        conn = get_conn()
        try:
            habits = conn.execute("SELECT * FROM habits WHERE active=1 ORDER BY name").fetchall()
            lines = []
            lines.append("=" * 60)
            lines.append("  HABIT TRACKER STATISTICS")
            lines.append("=" * 60)
            lines.append("")

            total_pts = self._get_total_points()
            lines.append(f"  Total Points: {total_pts}")
            lines.append(f"  Active Habits: {len(habits)}")
            lines.append("")
            lines.append("-" * 60)

            for h in habits:
                logs = conn.execute(
                    "SELECT COUNT(*) as total, SUM(completed) as done FROM habit_log WHERE habit_id=?",
                    (h["id"],)
                ).fetchone()
                total = logs["total"] or 0
                done = logs["done"] or 0
                rate = (done / total * 100) if total > 0 else 0
                streak = self._get_streak(h["id"])
                h_pts = conn.execute(
                    "SELECT COALESCE(SUM(points), 0) as p FROM habit_log WHERE habit_id=?",
                    (h["id"],)
                ).fetchone()["p"]

                lines.append(f"\n  {h['name']} [{h['category']}]")
                lines.append(f"    Completion Rate:  {rate:.1f}% ({done}/{total} days)")
                lines.append(f"    Current Streak:   {streak} days")
                lines.append(f"    Points Earned:    {h_pts}")
                lines.append(f"    Since:            {h['created_date']}")

            lines.append("\n" + "=" * 60)

            self.stats_text.configure(state=tk.NORMAL)
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", "\n".join(lines))
            self.stats_text.configure(state=tk.DISABLED)
        finally:
            conn.close()


if __name__ == "__main__":
    app = HabitTrackerApp()
    app.mainloop()
