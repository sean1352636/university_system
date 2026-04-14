"""
Cinema Booking System - Shift Scheduling
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_shift_scheduling_page(self):
    """Display shift scheduling with weekly calendar view."""
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.shift_scheduling.title"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    # Week navigation
    nav_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    nav_frame.pack(fill="x", pady=5)

    self.shift_week_offset = getattr(self, 'shift_week_offset', 0)

    def prev_week():
        self.shift_week_offset -= 7
        self.show_shift_scheduling_page()

    def next_week():
        self.shift_week_offset += 7
        self.show_shift_scheduling_page()

    ttk.Button(nav_frame, text=_t("cinema.btn.prev_week"), style="Secondary.TButton", command=prev_week).pack(side="left", padx=5)

    start_date = datetime.now() + timedelta(days=self.shift_week_offset)
    start_of_week = start_date - timedelta(days=start_date.weekday())
    week_label = f"Week of {start_of_week.strftime('%b %d, %Y')}"
    tk.Label(nav_frame, text=week_label, font=("Helvetica", 12, "bold"), bg="#ecf0f1", fg="#27ae60").pack(side="left", padx=20)

    ttk.Button(nav_frame, text=_t("cinema.common.next_week") + " >", style="Secondary.TButton", command=next_week).pack(side="left", padx=5)
    ttk.Button(nav_frame, text=_t("cinema.labels.today"), style="Primary.TButton", command=lambda: [setattr(self, 'shift_week_offset', 0), self.show_shift_scheduling_page()]).pack(side="left", padx=20)

    # Action buttons
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text="+ Add Shift", style="Success.TButton", command=self.add_shift).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.staff.availability"), style="Secondary.TButton", command=self.show_staff_availability).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.booking.swap_requests"), style="Warning.TButton", command=self.show_swap_requests).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.auto_schedule"), style="Secondary.TButton", command=self.auto_schedule_shifts).pack(side="left", padx=5)

    # Weekly calendar grid
    calendar_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    calendar_frame.pack(fill="both", expand=True, pady=10)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Header row with dates
    for i, day in enumerate(days):
        day_date = start_of_week + timedelta(days=i)
        header_text = f"{day}\n{day_date.strftime('%m/%d')}"
        tk.Label(calendar_frame, text=header_text, font=("Helvetica", 10, "bold"),
                bg="#0f3460", fg="white", width=14, height=2, relief="ridge").grid(row=0, column=i, sticky="nsew", padx=1, pady=1)

    # Get shifts for the week
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        week_end = start_of_week + timedelta(days=7)
        cursor.execute('''
            SELECT sh.id, sh.shift_date, sh.start_time, sh.end_time, sh.position, sh.status, st.name, sh.staff_id
            FROM shifts sh
            JOIN staff st ON sh.staff_id = st.id
            WHERE sh.shift_date >= ? AND sh.shift_date < ?
            ORDER BY sh.start_time
        ''', (start_of_week.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))
        shifts = cursor.fetchall()
    finally:
        conn.close()

    # Organize shifts by day
    shifts_by_day = {i: [] for i in range(7)}
    for shift in shifts:
        try:
            shift_date = datetime.strptime(shift[1], "%Y-%m-%d")
            day_idx = (shift_date - start_of_week).days
            if 0 <= day_idx < 7:
                shifts_by_day[day_idx].append(shift)
        except (ValueError, TypeError):
            pass

    # Display shifts in grid
    max_shifts = max(len(v) for v in shifts_by_day.values()) if shifts_by_day else 1
    max_shifts = max(max_shifts, 5)  # Minimum 5 rows

    for row in range(max_shifts):
        for col in range(7):
            cell_frame = tk.Frame(calendar_frame, bg="#ffffff", width=100, height=50, relief="ridge", bd=1)
            cell_frame.grid(row=row+1, column=col, sticky="nsew", padx=1, pady=1)
            cell_frame.grid_propagate(False)

            if row < len(shifts_by_day[col]):
                shift = shifts_by_day[col][row]
                shift_id, _, start_time, end_time, position, status, staff_name, staff_id = shift

                status_colors = {"scheduled": "#4ecca3", "confirmed": "#3498db", "completed": "#888888", "cancelled": "#dc3545"}
                color = status_colors.get(status, "#4ecca3")

                shift_text = f"{staff_name}\n{start_time}-{end_time}"
                label = tk.Label(cell_frame, text=shift_text, bg="#ffffff", fg=color,
                                font=("Helvetica", 8), wraplength=90, cursor="hand2")
                label.pack(expand=True)
                label.bind("<Button-1>", lambda e, sid=shift_id: self.edit_shift(sid))

    # Configure grid weights
    for i in range(7):
        calendar_frame.columnconfigure(i, weight=1)
    for i in range(max_shifts + 1):
        calendar_frame.rowconfigure(i, weight=1)

    # Stats summary
    stats_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    stats_frame.pack(fill="x", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shifts WHERE shift_date >= ? AND shift_date < ? AND status = 'scheduled'",
                      (start_of_week.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))
        scheduled_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT staff_id) FROM shifts WHERE shift_date >= ? AND shift_date < ?",
                      (start_of_week.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))
        staff_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM shift_swap_requests WHERE status = 'pending'")
        pending_swaps = cursor.fetchone()[0]
    finally:
        conn.close()

    tk.Label(stats_frame, text=f"This Week: {scheduled_count} shifts | {staff_count} staff members | {pending_swaps} pending swap requests",
            bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

def add_shift(self):
    """Add a new shift assignment."""
    form = tk.Toplevel(self.root)
    form.title("Add Shift")
    form.geometry("450x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.shift_scheduling.add_shift"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    # Get staff list
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, role FROM staff WHERE status = 'active' ORDER BY name")
        staff_list = cursor.fetchall()
    finally:
        conn.close()

    staff_names = [f"{s[1]} ({s[2]})" for s in staff_list]
    staff_ids = {f"{s[1]} ({s[2]})": s[0] for s in staff_list}

    fields = {}

    tk.Label(frame, text=_t("cinema.labels.staff_member_label"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    staff_var = tk.StringVar()
    staff_combo = ttk.Combobox(frame, textvariable=staff_var, values=staff_names, width=27, state="readonly")
    staff_combo.grid(row=1, column=1, pady=5)
    if staff_names:
        staff_combo.current(0)
    fields['staff_var'] = staff_var

    tk.Label(frame, text="Date (YYYY-MM-DD):", bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    date_e = ttk.Entry(frame, width=30)
    date_e.insert(0, datetime.now().strftime("%Y-%m-%d"))
    date_e.grid(row=2, column=1, pady=5)
    fields['date'] = date_e

    tk.Label(frame, text="Start Time (HH:MM):", bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    start_e = ttk.Entry(frame, width=30)
    start_e.insert(0, "09:00")
    start_e.grid(row=3, column=1, pady=5)
    fields['start'] = start_e

    tk.Label(frame, text="End Time (HH:MM):", bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    end_e = ttk.Entry(frame, width=30)
    end_e.insert(0, "17:00")
    end_e.grid(row=4, column=1, pady=5)
    fields['end'] = end_e

    tk.Label(frame, text=_t("cinema.labels.position"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    position_var = tk.StringVar(value="general")
    positions = ["general", "cashier", "concessions", "usher", "projectionist", "manager", "cleaner"]
    position_combo = ttk.Combobox(frame, textvariable=position_var, values=positions, width=27)
    position_combo.grid(row=5, column=1, pady=5)
    fields['position_var'] = position_var

    tk.Label(frame, text=_t("cinema.labels.screen_assigned"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="w", pady=5)
    screen_e = ttk.Entry(frame, width=30)
    screen_e.grid(row=6, column=1, pady=5)
    fields['screen'] = screen_e

    tk.Label(frame, text=_t("cinema.labels.break_start"), bg="#ffffff", fg="#333333").grid(row=7, column=0, sticky="w", pady=5)
    break_start_e = ttk.Entry(frame, width=30)
    break_start_e.insert(0, "12:00")
    break_start_e.grid(row=7, column=1, pady=5)
    fields['break_start'] = break_start_e

    tk.Label(frame, text=_t("cinema.labels.break_end"), bg="#ffffff", fg="#333333").grid(row=8, column=0, sticky="w", pady=5)
    break_end_e = ttk.Entry(frame, width=30)
    break_end_e.insert(0, "12:30")
    break_end_e.grid(row=8, column=1, pady=5)
    fields['break_end'] = break_end_e

    tk.Label(frame, text=_t("cinema.tickets.notes_label"), bg="#ffffff", fg="#333333").grid(row=9, column=0, sticky="w", pady=5)
    notes_e = ttk.Entry(frame, width=30)
    notes_e.grid(row=9, column=1, pady=5)
    fields['notes'] = notes_e

    def save():
        if not fields['staff_var'].get():
            messagebox.showwarning(_t("cinema.common.warning"), "Please select a staff member")
            return

        staff_id = staff_ids.get(fields['staff_var'].get())
        if not staff_id:
            messagebox.showwarning(_t("cinema.common.warning"), "Invalid staff selection")
            return

        screen = None
        if fields['screen'].get().strip():
            try:
                screen = int(fields['screen'].get())
            except (ValueError, TypeError):
                pass

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shifts (staff_id, shift_date, start_time, end_time, position, screen_assigned, break_start, break_end, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (staff_id, fields['date'].get(), fields['start'].get(), fields['end'].get(),
                  fields['position_var'].get(), screen, fields['break_start'].get(), fields['break_end'].get(), fields['notes'].get()))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Shift added successfully!")
        form.destroy()
        self.show_shift_scheduling_page()

    ttk.Button(frame, text=_t("cinema.shift_scheduling.add_shift"), style="Success.TButton", command=save).grid(row=10, column=0, columnspan=2, pady=20)

def edit_shift(self, shift_id):
    """Edit an existing shift."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sh.*, st.name FROM shifts sh
            JOIN staff st ON sh.staff_id = st.id
            WHERE sh.id = ?
        ''', (shift_id,))
        shift = cursor.fetchone()
    finally:
        conn.close()

    if not shift:
        messagebox.showerror(_t("cinema.common.error"), "Shift not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Edit Shift")
    form.geometry("400x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=f"Edit Shift - {shift[12]}", font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    info_text = f"Date: {shift[2]}\nTime: {shift[3]} - {shift[4]}\nPosition: {shift[5]}\nStatus: {shift[10]}"
    tk.Label(frame, text=info_text, bg="#ffffff", fg="#333333", justify="left").pack(anchor="w", pady=10)

    tk.Label(frame, text=_t("cinema.labels.update_status"), bg="#ffffff", fg="#333333").pack(anchor="w")
    status_var = tk.StringVar(value=shift[10])
    statuses = ["scheduled", "confirmed", "completed", "cancelled"]
    status_combo = ttk.Combobox(frame, textvariable=status_var, values=statuses, width=25)
    status_combo.pack(pady=5)

    def update():
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE shifts SET status = ? WHERE id = ?", (status_var.get(), shift_id))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Shift updated!")
        form.destroy()
        self.show_shift_scheduling_page()

    def delete():
        if messagebox.askyesno(_t("cinema.common.confirm"), "Delete this shift?"):
            conn = sqlite3.connect(DB_FILE)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo(_t("cinema.messages.success.deleted"), "Shift deleted")
            form.destroy()
            self.show_shift_scheduling_page()

    def request_swap():
        form.destroy()
        self.request_shift_swap(shift_id)

    btn_frame = ttk.Frame(frame, style="Card.TFrame")
    btn_frame.pack(fill="x", pady=20)
    ttk.Button(btn_frame, text=_t("cinema.btn.update"), style="Success.TButton", command=update).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.request_swap"), style="Warning.TButton", command=request_swap).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.buttons.delete"), style="Danger.TButton", command=delete).pack(side="left", padx=5)

def show_staff_availability(self):
    """Show and manage staff availability."""
    form = tk.Toplevel(self.root)
    form.title("Staff Availability")
    form.geometry("700x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.staff.availability"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    # Staff selector
    select_frame = ttk.Frame(frame, style="Card.TFrame")
    select_frame.pack(fill="x", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM staff WHERE status = 'active' ORDER BY name")
        staff_list = cursor.fetchall()
    finally:
        conn.close()

    staff_names = [s[1] for s in staff_list]
    staff_ids = {s[1]: s[0] for s in staff_list}

    tk.Label(select_frame, text="Select Staff:", bg="#ffffff", fg="#333333").pack(side="left")
    staff_var = tk.StringVar()
    staff_combo = ttk.Combobox(select_frame, textvariable=staff_var, values=staff_names, width=25, state="readonly")
    staff_combo.pack(side="left", padx=10)

    # Availability grid
    avail_frame = ttk.Frame(frame, style="Card.TFrame")
    avail_frame.pack(fill="both", expand=True, pady=10)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    avail_vars = {}

    for i, day in enumerate(days):
        tk.Label(avail_frame, text=day, bg="#ffffff", fg="#333333", width=12).grid(row=i, column=0, pady=3)

        avail_var = tk.BooleanVar(value=True)
        avail_check = ttk.Checkbutton(avail_frame, text=_t("cinema.status.available"), variable=avail_var)
        avail_check.grid(row=i, column=1, padx=5)

        from_e = ttk.Entry(avail_frame, width=8)
        from_e.insert(0, "09:00")
        from_e.grid(row=i, column=2, padx=5)

        tk.Label(avail_frame, text="to", bg="#ffffff", fg="#333333").grid(row=i, column=3)

        to_e = ttk.Entry(avail_frame, width=8)
        to_e.insert(0, "22:00")
        to_e.grid(row=i, column=4, padx=5)

        avail_vars[i] = {'available': avail_var, 'from': from_e, 'to': to_e}

    def load_availability():
        staff_name = staff_var.get()
        if not staff_name:
            return
        staff_id = staff_ids.get(staff_name)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT day_of_week, is_available, available_from, available_until FROM staff_availability WHERE staff_id = ?", (staff_id,))
            avails = cursor.fetchall()
        finally:
            conn.close()

        for day_idx, is_avail, from_time, to_time in avails:
            if day_idx in avail_vars:
                avail_vars[day_idx]['available'].set(bool(is_avail))
                avail_vars[day_idx]['from'].delete(0, tk.END)
                avail_vars[day_idx]['from'].insert(0, from_time or "09:00")
                avail_vars[day_idx]['to'].delete(0, tk.END)
                avail_vars[day_idx]['to'].insert(0, to_time or "22:00")

    def save_availability():
        staff_name = staff_var.get()
        if not staff_name:
            messagebox.showwarning(_t("cinema.common.warning"), "Please select a staff member")
            return
        staff_id = staff_ids.get(staff_name)

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            for day_idx, vars in avail_vars.items():
                cursor.execute("DELETE FROM staff_availability WHERE staff_id = ? AND day_of_week = ?", (staff_id, day_idx))
                cursor.execute('''
                    INSERT INTO staff_availability (staff_id, day_of_week, is_available, available_from, available_until)
                    VALUES (?, ?, ?, ?, ?)
                ''', (staff_id, day_idx, 1 if vars['available'].get() else 0, vars['from'].get(), vars['to'].get()))

            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t("cinema.common.success"), "Availability saved!")

    staff_combo.bind("<<ComboboxSelected>>", lambda e: load_availability())

    ttk.Button(frame, text=_t("cinema.btn.save_availability"), style="Success.TButton", command=save_availability).pack(pady=10)

def request_shift_swap(self, shift_id):
    """Request a shift swap."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sh.*, st.name FROM shifts sh
            JOIN staff st ON sh.staff_id = st.id
            WHERE sh.id = ?
        ''', (shift_id,))
        shift = cursor.fetchone()

        # Get other shifts that can be swapped
        cursor.execute('''
            SELECT sh.id, sh.shift_date, sh.start_time, sh.end_time, st.name, st.id
            FROM shifts sh
            JOIN staff st ON sh.staff_id = st.id
            WHERE sh.id != ? AND sh.status = 'scheduled' AND sh.shift_date >= date('now')
            ORDER BY sh.shift_date, sh.start_time
        ''', (shift_id,))
        other_shifts = cursor.fetchall()
    finally:
        conn.close()

    if not shift:
        messagebox.showerror(_t("cinema.common.error"), "Shift not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Request Shift Swap")
    form.geometry("500x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.shifts.request_swap"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=f"Your Shift: {shift[2]} {shift[3]}-{shift[4]}", bg="#ffffff", fg="#333333").pack(anchor="w")

    tk.Label(frame, text="Select shift to swap with:", bg="#ffffff", fg="#333333").pack(anchor="w", pady=(15, 5))

    swap_options = [f"{s[1]} {s[2]}-{s[3]} - {s[4]}" for s in other_shifts]
    swap_ids = {f"{s[1]} {s[2]}-{s[3]} - {s[4]}": (s[0], s[5]) for s in other_shifts}

    swap_var = tk.StringVar()
    swap_combo = ttk.Combobox(frame, textvariable=swap_var, values=swap_options, width=45, state="readonly")
    swap_combo.pack(pady=5)

    tk.Label(frame, text=_t("cinema.labels.swap_reason"), bg="#ffffff", fg="#333333").pack(anchor="w", pady=(15, 5))
    reason_text = tk.Text(frame, height=4, width=45, bg="#0f3460", fg="white")
    reason_text.pack(pady=5)

    def submit():
        if not swap_var.get():
            messagebox.showwarning(_t("cinema.common.warning"), "Please select a shift to swap with")
            return

        target_shift_id, target_staff_id = swap_ids.get(swap_var.get(), (None, None))
        if not target_shift_id:
            return

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shift_swap_requests (requester_id, original_shift_id, requested_with_id, target_shift_id, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (shift[1], shift_id, target_staff_id, target_shift_id, reason_text.get("1.0", tk.END).strip()))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Swap request submitted! Awaiting approval.")
        form.destroy()

    ttk.Button(frame, text=_t("cinema.btn.submit_request"), style="Success.TButton", command=submit).pack(pady=20)

def show_swap_requests(self):
    """Show pending shift swap requests."""
    form = tk.Toplevel(self.root)
    form.title("Shift Swap Requests")
    form.geometry("800x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.shifts.swap_requests"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tree_frame = ttk.Frame(frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Requester", "Original Shift", "Target Staff", "Target Shift", "Status")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sr.id, req.name, sh1.shift_date || ' ' || sh1.start_time,
                   tgt.name, sh2.shift_date || ' ' || sh2.start_time, sr.status
            FROM shift_swap_requests sr
            JOIN staff req ON sr.requester_id = req.id
            JOIN shifts sh1 ON sr.original_shift_id = sh1.id
            LEFT JOIN staff tgt ON sr.requested_with_id = tgt.id
            LEFT JOIN shifts sh2 ON sr.target_shift_id = sh2.id
            ORDER BY sr.created_at DESC
        ''')
        for row in cursor.fetchall():
            tree.insert("", "end", values=row)
    finally:
        conn.close()

    tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    def approve():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning(_t("cinema.common.warning"), "Select a request")
            return
        req_id = tree.item(selected[0])['values'][0]

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            # Get swap details
            cursor.execute("SELECT original_shift_id, target_shift_id FROM shift_swap_requests WHERE id = ?", (req_id,))
            orig_id, target_id = cursor.fetchone()

            # Get staff IDs from shifts
            cursor.execute("SELECT staff_id FROM shifts WHERE id = ?", (orig_id,))
            orig_staff = cursor.fetchone()[0]
            cursor.execute("SELECT staff_id FROM shifts WHERE id = ?", (target_id,))
            target_staff = cursor.fetchone()[0]

            # Swap the staff assignments
            cursor.execute("UPDATE shifts SET staff_id = ? WHERE id = ?", (target_staff, orig_id))
            cursor.execute("UPDATE shifts SET staff_id = ? WHERE id = ?", (orig_staff, target_id))

            cursor.execute("UPDATE shift_swap_requests SET status = 'approved', resolved_at = ? WHERE id = ?",
                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.approved"), "Shift swap approved!")
        form.destroy()
        self.show_swap_requests()

    def deny():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning(_t("cinema.common.warning"), "Select a request")
            return
        req_id = tree.item(selected[0])['values'][0]

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE shift_swap_requests SET status = 'denied', resolved_at = ? WHERE id = ?",
                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo("Denied", _t("cinema.messages.shift_swap_denied"))
        form.destroy()
        self.show_swap_requests()

    btn_frame = ttk.Frame(frame, style="Card.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.approve"), style="Success.TButton", command=approve).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.deny"), style="Danger.TButton", command=deny).pack(side="left", padx=5)

def auto_schedule_shifts(self):
    """Auto-schedule shifts based on staff availability."""
    if not messagebox.askyesno(_t("cinema.screenings.auto_schedule"), "This will create shifts for next week based on staff availability.\n\nContinue?"):
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        # Get next week dates
        today = datetime.now()
        next_monday = today + timedelta(days=(7 - today.weekday()))

        # Get all active staff with their availability
        cursor.execute("SELECT id, name FROM staff WHERE status = 'active'")
        staff_list = cursor.fetchall()

        shifts_created = 0
        for staff_id, staff_name in staff_list:
            cursor.execute("SELECT day_of_week, available_from, available_until FROM staff_availability WHERE staff_id = ? AND is_available = 1", (staff_id,))
            availabilities = cursor.fetchall()

            for day_of_week, avail_from, avail_until in availabilities:
                shift_date = next_monday + timedelta(days=day_of_week)

                # Check if shift already exists
                cursor.execute("SELECT COUNT(*) FROM shifts WHERE staff_id = ? AND shift_date = ?",
                              (staff_id, shift_date.strftime("%Y-%m-%d")))
                if cursor.fetchone()[0] == 0:
                    cursor.execute('''
                        INSERT INTO shifts (staff_id, shift_date, start_time, end_time, position)
                        VALUES (?, ?, ?, ?, 'general')
                    ''', (staff_id, shift_date.strftime("%Y-%m-%d"), avail_from or "09:00", avail_until or "17:00"))
                    shifts_created += 1

        conn.commit()
    finally:
        conn.close()

    messagebox.showinfo("Auto-Schedule Complete", f"Created {shifts_created} shifts for next week.")
    self.show_shift_scheduling_page()
