import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

class AdvisingPortalGUI:
    """Academic Advising Portal - schedule meetings, view advisor info, degree planning."""

    def __init__(self, parent=None):
        # When ``parent`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), embed inside it. Frames have no
        # ``wm_title``; Tk/Toplevel do.
        if parent is not None and not hasattr(parent, "wm_title"):
            self.window = parent
        else:
            self.window = tk.Toplevel(parent) if parent else tk.Tk()
            self.window.title("Academic Advising Portal")
            self.window.geometry("1100x700")

        # Try to get auth context
        try:
            from education_system.post_18.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        # Try to get i18n
        try:
            from education_system.post_18.university_system.core.i18n import get_text as _t
            self._t = _t
        except ImportError:
            self._t = lambda key, **kw: key

        self._build_ui()
        self._init_db()
        self._load_data()

    def _init_db(self):
        """Ensure advising tables exist."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS advising_appointments (
                    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    advisor_id TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    appointment_time TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 30,
                    appointment_type TEXT DEFAULT 'general',
                    topic TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    status TEXT DEFAULT 'scheduled'
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS advisors (
                    advisor_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    office TEXT DEFAULT '',
                    specialization TEXT DEFAULT '',
                    available_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri',
                    available_hours TEXT DEFAULT '09:00-17:00'
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS degree_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    advisor_id TEXT,
                    plan_name TEXT NOT NULL,
                    target_graduation TEXT,
                    total_credits_required INTEGER DEFAULT 120,
                    credits_completed INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_date TEXT DEFAULT (date('now')),
                    last_updated TEXT DEFAULT (date('now')),
                    status TEXT DEFAULT 'active'
                )""")
        except Exception as e:
            logger.error(f"DB init error: {e}")

    def _get_student_id(self):
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user = self.auth.current_user
            if isinstance(user, dict):
                return user.get('student_id', user.get('username', 'unknown'))
            return getattr(user, 'student_id', getattr(user, 'username', 'unknown'))
        return 'unknown'

    def _build_ui(self):
        # Main notebook with tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: My Appointments
        self._build_appointments_tab()
        # Tab 2: Schedule Appointment
        self._build_schedule_tab()
        # Tab 3: My Advisor
        self._build_advisor_tab()
        # Tab 4: Degree Plan
        self._build_degree_plan_tab()

    def _build_appointments_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Appointments")

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_appointments).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Cancel Selected", command=self._cancel_appointment).pack(side=tk.LEFT, padx=2)

        # Filter
        ttk.Label(toolbar, text="Status:").pack(side=tk.LEFT, padx=(10,2))
        self.appt_filter = ttk.Combobox(toolbar, values=["All", "scheduled", "completed", "cancelled"], state="readonly", width=12)
        self.appt_filter.set("All")
        self.appt_filter.pack(side=tk.LEFT, padx=2)
        self.appt_filter.bind("<<ComboboxSelected>>", lambda e: self._load_appointments())

        # Treeview
        cols = ("id", "date", "time", "duration", "type", "advisor", "topic", "status")
        self.appt_tree = ttk.Treeview(tab, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 100, 80, 70, 100, 120, 200, 80)):
            self.appt_tree.heading(c, text=c.replace("_", " ").title())
            self.appt_tree.column(c, width=w, minwidth=40)
        self.appt_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        sb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.appt_tree.yview)
        self.appt_tree.configure(yscrollcommand=sb.set)
        sb.place(relx=1.0, rely=0, relheight=1.0, anchor='ne', in_=self.appt_tree)

    def _build_schedule_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Schedule Appointment")

        form = ttk.LabelFrame(tab, text="New Appointment", padding=15)
        form.pack(fill=tk.X, padx=10, pady=10)

        row = 0
        ttk.Label(form, text="Advisor:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.advisor_combo = ttk.Combobox(form, state="readonly", width=30)
        self.advisor_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.date_entry = ttk.Entry(form, width=20)
        self.date_entry.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)
        self.date_entry.insert(0, (date.today() + timedelta(days=1)).isoformat())

        row += 1
        ttk.Label(form, text="Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.time_entry = ttk.Entry(form, width=20)
        self.time_entry.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)
        self.time_entry.insert(0, "10:00")

        row += 1
        ttk.Label(form, text="Duration (mins):").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.duration_combo = ttk.Combobox(form, values=["15", "30", "45", "60"], state="readonly", width=10)
        self.duration_combo.set("30")
        self.duration_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Type:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.type_combo = ttk.Combobox(form, values=["general", "degree_planning", "course_selection", "academic_concern", "career_guidance", "graduate_school"], state="readonly", width=20)
        self.type_combo.set("general")
        self.type_combo.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Topic:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.topic_entry = ttk.Entry(form, width=40)
        self.topic_entry.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Label(form, text="Notes:").grid(row=row, column=0, sticky=tk.NW, pady=3)
        self.notes_text = tk.Text(form, width=40, height=4)
        self.notes_text.grid(row=row, column=1, sticky=tk.W, pady=3, padx=5)

        row += 1
        ttk.Button(form, text="Schedule Appointment", command=self._schedule_appointment).grid(row=row, column=1, sticky=tk.W, pady=10, padx=5)

    def _build_advisor_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Advisors")

        ttk.Label(tab, text="Available Academic Advisors", font=("", 12, "bold")).pack(pady=10)

        cols = ("advisor_id", "name", "department", "email", "office", "specialization", "available_days")
        self.advisor_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (80, 150, 120, 180, 80, 150, 150)):
            self.advisor_tree.heading(c, text=c.replace("_", " ").title())
            self.advisor_tree.column(c, width=w, minwidth=40)
        self.advisor_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _build_degree_plan_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Degree Plan")

        # Plan summary
        self.plan_frame = ttk.LabelFrame(tab, text="My Degree Plan", padding=10)
        self.plan_frame.pack(fill=tk.X, padx=10, pady=10)

        self.plan_info = tk.Text(self.plan_frame, height=6, state=tk.DISABLED, wrap=tk.WORD)
        self.plan_info.pack(fill=tk.X)

        # Course progress
        progress_frame = ttk.LabelFrame(tab, text="Credit Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.progress_label = ttk.Label(progress_frame, text="0 / 120 credits completed (0%)")
        self.progress_label.pack()

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Create New Plan", command=self._create_degree_plan).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_degree_plan).pack(side=tk.LEFT, padx=5)

    def _load_data(self):
        self._load_appointments()
        self._load_advisors()
        self._load_degree_plan()

    def _load_appointments(self):
        for item in self.appt_tree.get_children():
            self.appt_tree.delete(item)
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            student_id = self._get_student_id()
            with get_connection() as conn:
                query = "SELECT * FROM advising_appointments WHERE student_id = ?"
                params = [student_id]
                filt = self.appt_filter.get()
                if filt and filt != "All":
                    query += " AND status = ?"
                    params.append(filt)
                query += " ORDER BY appointment_date DESC, appointment_time DESC"
                rows = conn.execute(query, params).fetchall()
                for r in rows:
                    self.appt_tree.insert("", tk.END, values=(
                        r["appointment_id"], r["appointment_date"], r["appointment_time"],
                        f"{r['duration_minutes']}m", r["appointment_type"], r["advisor_id"],
                        r["topic"], r["status"]
                    ))
        except Exception as e:
            logger.debug(f"Load appointments: {e}")

    def _load_advisors(self):
        for item in self.advisor_tree.get_children():
            self.advisor_tree.delete(item)
        advisor_list = []
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                rows = conn.execute("SELECT * FROM advisors ORDER BY name").fetchall()
                for r in rows:
                    self.advisor_tree.insert("", tk.END, values=(
                        r["advisor_id"], r["name"], r["department"], r["email"],
                        r["office"], r["specialization"], r["available_days"]
                    ))
                    advisor_list.append(f"{r['advisor_id']} - {r['name']}")
        except Exception as e:
            logger.debug(f"Load advisors: {e}")
            # Insert sample advisors if table empty
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    count = conn.execute("SELECT COUNT(*) FROM advisors").fetchone()[0]
                    if count == 0:
                        sample = [
                            ("ADV001", "Dr. Sarah Johnson", "Computer Science", "s.johnson@uni.edu", "B210", "Software Engineering"),
                            ("ADV002", "Prof. Michael Chen", "Data Science", "m.chen@uni.edu", "C305", "Machine Learning"),
                            ("ADV003", "Dr. Emily Williams", "Mathematics", "e.williams@uni.edu", "A118", "Applied Mathematics"),
                        ]
                        for s in sample:
                            conn.execute("INSERT INTO advisors (advisor_id, name, department, email, office, specialization) VALUES (?,?,?,?,?,?)", s)
                        conn.commit()
                        self._load_advisors()
                        return
            except Exception:
                pass
        self.advisor_combo['values'] = advisor_list if advisor_list else ["No advisors available"]
        if advisor_list:
            self.advisor_combo.current(0)

    def _schedule_appointment(self):
        advisor_val = self.advisor_combo.get()
        if not advisor_val or advisor_val == "No advisors available":
            messagebox.showwarning("Warning", "Please select an advisor.")
            return
        advisor_id = advisor_val.split(" - ")[0].strip()
        appt_date = self.date_entry.get().strip()
        appt_time = self.time_entry.get().strip()
        duration = self.duration_combo.get()
        appt_type = self.type_combo.get()
        topic = self.topic_entry.get().strip()
        notes = self.notes_text.get("1.0", tk.END).strip()

        # Validate
        try:
            datetime.strptime(appt_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
            return
        try:
            datetime.strptime(appt_time, "%H:%M")
        except ValueError:
            messagebox.showerror("Error", "Invalid time format. Use HH:MM.")
            return

        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            student_id = self._get_student_id()
            with get_connection() as conn:
                conn.execute("""INSERT INTO advising_appointments
                    (student_id, advisor_id, appointment_date, appointment_time, duration_minutes, appointment_type, topic, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')""",
                    (student_id, advisor_id, appt_date, appt_time, int(duration), appt_type, topic, notes))
                conn.commit()
            messagebox.showinfo("Success", "Appointment scheduled successfully!")
            self.topic_entry.delete(0, tk.END)
            self.notes_text.delete("1.0", tk.END)
            self._load_appointments()
            self.notebook.select(0)  # Switch to appointments tab
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule: {e}")

    def _cancel_appointment(self):
        sel = self.appt_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select an appointment to cancel.")
            return
        vals = self.appt_tree.item(sel[0])['values']
        appt_id = vals[0]
        if vals[7] == 'cancelled':
            messagebox.showinfo("Info", "This appointment is already cancelled.")
            return
        if messagebox.askyesno("Confirm", "Cancel this appointment?"):
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    conn.execute("UPDATE advising_appointments SET status='cancelled' WHERE appointment_id=?", (appt_id,))
                    conn.commit()
                self._load_appointments()
                messagebox.showinfo("Success", "Appointment cancelled.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to cancel: {e}")

    def _load_degree_plan(self):
        self.plan_info.configure(state=tk.NORMAL)
        self.plan_info.delete("1.0", tk.END)
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            student_id = self._get_student_id()
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM degree_plans WHERE student_id = ? AND status = 'active' ORDER BY created_date DESC LIMIT 1",
                    (student_id,)
                ).fetchone()
                if row:
                    pct = (row["credits_completed"] / max(row["total_credits_required"], 1)) * 100
                    self.plan_info.insert(tk.END, f"Plan: {row['plan_name']}\n")
                    self.plan_info.insert(tk.END, f"Target Graduation: {row['target_graduation'] or 'Not set'}\n")
                    self.plan_info.insert(tk.END, f"Credits: {row['credits_completed']} / {row['total_credits_required']}\n")
                    self.plan_info.insert(tk.END, f"Last Updated: {row['last_updated']}\n")
                    if row['notes']:
                        self.plan_info.insert(tk.END, f"Notes: {row['notes']}\n")
                    self.progress_var.set(pct)
                    self.progress_label.configure(text=f"{row['credits_completed']} / {row['total_credits_required']} credits ({pct:.0f}%)")
                else:
                    self.plan_info.insert(tk.END, "No active degree plan found.\nClick 'Create New Plan' to get started.")
                    self.progress_var.set(0)
                    self.progress_label.configure(text="0 / 120 credits (0%)")
        except Exception as e:
            self.plan_info.insert(tk.END, f"Unable to load degree plan: {e}")
        self.plan_info.configure(state=tk.DISABLED)

    def _create_degree_plan(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Degree Plan")
        dialog.geometry("400x300")
        dialog.transient(self.window)

        ttk.Label(dialog, text="Plan Name:").pack(anchor=tk.W, padx=10, pady=(10,0))
        name_entry = ttk.Entry(dialog, width=35)
        name_entry.pack(padx=10, pady=2)
        name_entry.insert(0, "My Degree Plan")

        ttk.Label(dialog, text="Target Graduation (YYYY-MM):").pack(anchor=tk.W, padx=10, pady=(10,0))
        grad_entry = ttk.Entry(dialog, width=20)
        grad_entry.pack(padx=10, pady=2, anchor=tk.W)

        ttk.Label(dialog, text="Total Credits Required:").pack(anchor=tk.W, padx=10, pady=(10,0))
        credits_entry = ttk.Entry(dialog, width=10)
        credits_entry.pack(padx=10, pady=2, anchor=tk.W)
        credits_entry.insert(0, "120")

        ttk.Label(dialog, text="Notes:").pack(anchor=tk.W, padx=10, pady=(10,0))
        notes_text = tk.Text(dialog, width=35, height=3)
        notes_text.pack(padx=10, pady=2)

        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Warning", "Please enter a plan name.", parent=dialog)
                return
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                student_id = self._get_student_id()
                with get_connection() as conn:
                    # Get current credits from enrolled modules
                    try:
                        credits_row = conn.execute(
                            "SELECT COALESCE(SUM(m.credits), 0) FROM student_modules sm JOIN modules m ON sm.module_code = m.module_code WHERE sm.student_id = ? AND sm.status = 'completed'",
                            (student_id,)
                        ).fetchone()
                        completed = credits_row[0] if credits_row else 0
                    except Exception:
                        completed = 0
                    conn.execute("""INSERT INTO degree_plans
                        (student_id, plan_name, target_graduation, total_credits_required, credits_completed, notes)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (student_id, name, grad_entry.get().strip() or None, int(credits_entry.get()), completed, notes_text.get("1.0", tk.END).strip()))
                    conn.commit()
                messagebox.showinfo("Success", "Degree plan created!", parent=dialog)
                dialog.destroy()
                self._load_degree_plan()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}", parent=dialog)

        ttk.Button(dialog, text="Create Plan", command=save).pack(pady=10)

def launch_advising_gui(parent=None):
    return AdvisingPortalGUI(parent=parent)
