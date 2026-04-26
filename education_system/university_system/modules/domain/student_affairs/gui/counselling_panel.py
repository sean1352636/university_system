"""Shared counselling panel embedded by both WellnessGUI (student) and
WellbeingFrame (staff). Backed by ``WellnessService.counseling_appointments``."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.university_system.modules.domain.student_affairs.wellness.services.wellness_service import (
    WellnessService,
)

APPOINTMENT_TYPES = (
    "Individual Counseling",
    "Group Therapy",
    "Crisis Intervention",
    "Academic Stress",
    "Relationship Issues",
    "Anxiety/Depression",
    "General Consultation",
)

STATUS_VALUES = ("Scheduled", "Confirmed", "Completed", "Cancelled", "No-show")


class CounsellingPanel(tk.Frame):
    """Counselling appointments UI. ``role`` is ``"student"`` or ``"staff"``."""

    def __init__(self, parent, auth=None, role="student", service=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._role = role if role in ("student", "staff") else "student"
        self._service = service or WellnessService()

        ttk.Label(
            self,
            text="🔒 All counselling records are confidential.",
            font=("Arial", 10, "italic"),
        ).pack(fill="x", padx=10, pady=(8, 4))

        if self._role == "student":
            self._build_student_view()
        else:
            self._build_staff_view()

    # ------------------------------------------------------------------ student
    def _build_student_view(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=4)

        form = ttk.LabelFrame(body, text="Book Counselling Appointment", padding=10)
        form.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", pady=4)
        self._date_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._date_var, width=22).grid(row=0, column=1, pady=4)

        ttk.Label(form, text="Time (HH:MM):").grid(row=1, column=0, sticky="w", pady=4)
        self._time_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._time_var, width=22).grid(row=1, column=1, pady=4)

        ttk.Label(form, text="Type:").grid(row=2, column=0, sticky="w", pady=4)
        self._type_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self._type_var,
                     values=APPOINTMENT_TYPES, width=20).grid(row=2, column=1, pady=4)

        ttk.Label(form, text="Concerns:").grid(row=3, column=0, sticky="nw", pady=4)
        self._notes = scrolledtext.ScrolledText(form, height=6, width=24)
        self._notes.grid(row=3, column=1, pady=4)

        ttk.Button(form, text="Book Appointment",
                   command=self._book).grid(row=4, column=0, columnspan=2, pady=8)

        appts = ttk.LabelFrame(body, text="My Appointments", padding=10)
        appts.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self._student_list = scrolledtext.ScrolledText(appts, height=20, wrap="word")
        self._student_list.pack(fill="both", expand=True)
        ttk.Button(appts, text="Refresh", command=self._refresh).pack(pady=4)

        self._refresh()

    def _book(self):
        date = self._date_var.get().strip()
        time = self._time_var.get().strip()
        appt_type = self._type_var.get().strip()
        notes = self._notes.get("1.0", "end").strip() or None
        if not (date and time and appt_type):
            messagebox.showwarning("Missing info", "Date, time and type are required.")
            return
        student_id = self._current_user_id()
        if not student_id:
            messagebox.showerror("Error", "Login required to book.")
            return
        try:
            self._service.schedule_counseling(student_id, date, time, appt_type, notes)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to book: {e}")
            return
        messagebox.showinfo("Booked", f"Appointment booked for {date} at {time}.")
        self._date_var.set("")
        self._time_var.set("")
        self._type_var.set("")
        self._notes.delete("1.0", "end")
        self._refresh()

    # -------------------------------------------------------------------- staff
    def _build_staff_view(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=4)
        ttk.Label(toolbar, text="Status filter:").pack(side="left")
        self._status_filter = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._status_filter,
                     values=("All",) + STATUS_VALUES, state="readonly",
                     width=14).pack(side="left", padx=4)
        self._status_filter.trace_add("write", lambda *_: self._refresh())
        ttk.Button(toolbar, text="Refresh", command=self._refresh).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit selected…",
                   command=self._edit_selected).pack(side="left", padx=4)

        cols = ("appointment_id", "student_id", "appointment_date",
                "appointment_time", "appointment_type", "counselor_name", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        widths = {"appointment_id": 60, "student_id": 100, "appointment_date": 100,
                  "appointment_time": 80, "appointment_type": 160,
                  "counselor_name": 130, "status": 90}
        for c in cols:
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=widths.get(c, 100), anchor="w")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
        vsb.pack(side="left", fill="y", pady=4)
        self._tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self._refresh()

    def _edit_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Edit appointment", "Select an appointment first.")
            return
        values = self._tree.item(sel[0], "values")
        appointment_id = int(values[0])
        current_counsellor = values[5] or ""
        current_status = values[6] or "Scheduled"

        dlg = tk.Toplevel(self)
        dlg.title(f"Appointment #{appointment_id}")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        ttk.Label(dlg, text="Counsellor:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        counsellor_var = tk.StringVar(value=current_counsellor)
        ttk.Entry(dlg, textvariable=counsellor_var, width=28).grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(dlg, text="Status:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        status_var = tk.StringVar(value=current_status)
        ttk.Combobox(dlg, textvariable=status_var, values=STATUS_VALUES,
                     state="readonly", width=26).grid(row=1, column=1, padx=8, pady=6)

        ttk.Label(dlg, text="Outcome notes:").grid(row=2, column=0, sticky="nw", padx=8, pady=6)
        notes_box = scrolledtext.ScrolledText(dlg, width=32, height=8)
        notes_box.grid(row=2, column=1, padx=8, pady=6)

        def save():
            try:
                self._service.update_appointment(
                    appointment_id,
                    status=status_var.get() or None,
                    counselor_name=counsellor_var.get().strip() or None,
                    notes=notes_box.get("1.0", "end").strip() or None,
                )
            except Exception as e:
                messagebox.showerror("Error", f"Update failed: {e}")
                return
            dlg.destroy()
            self._refresh()

        ttk.Button(dlg, text="Save", command=save).grid(row=3, column=1, sticky="e",
                                                        padx=8, pady=10)

    # ------------------------------------------------------------------- shared
    def _refresh(self):
        if self._role == "student":
            self._student_list.config(state="normal")
            self._student_list.delete("1.0", "end")
            student_id = self._current_user_id()
            if not student_id:
                self._student_list.insert("end", "Login required.")
                self._student_list.config(state="disabled")
                return
            try:
                appts = self._service.get_counseling_appointments(student_id)
            except Exception as e:
                self._student_list.insert("end", f"Error: {e}")
                self._student_list.config(state="disabled")
                return
            if not appts:
                self._student_list.insert("end", "No appointments scheduled.")
            for a in appts:
                self._student_list.insert("end", "=" * 48 + "\n")
                self._student_list.insert(
                    "end",
                    f"#{a['appointment_id']} — {a['appointment_date']} "
                    f"at {a['appointment_time']}\n"
                    f"Type: {a.get('appointment_type', '')}\n"
                    f"Status: {a.get('status', '')}\n"
                    f"Counsellor: {a.get('counselor_name') or '—'}\n\n",
                )
            self._student_list.config(state="disabled")
            return

        for row in self._tree.get_children():
            self._tree.delete(row)
        status = self._status_filter.get()
        try:
            appts = self._service.list_all_appointments(
                status=None if status in ("", "All") else status
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        for a in appts:
            self._tree.insert("", "end", values=(
                a.get("appointment_id"), a.get("student_id"),
                a.get("appointment_date"), a.get("appointment_time"),
                a.get("appointment_type"), a.get("counselor_name") or "",
                a.get("status") or "",
            ))

    def _current_user_id(self):
        if not self._auth:
            return None
        try:
            user = self._auth.get_current_user()
            return user.get("username") if user else None
        except Exception:
            try:
                return self._auth.current_user.get("username")
            except Exception:
                return None
