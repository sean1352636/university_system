"""Barbershop — Staff + Student portals.

Staff: today's appointment queue + status transitions
(scheduled → confirmed → completed / no_show / cancelled), plus a
service/staff reference view.
Student: browse services, book an appointment, see my bookings, cancel.

Admins retain the full `BarberGUI`.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3,
    DEFAULT_DB_PATH,
)


_APPT_STATUSES = ['scheduled', 'confirmed', 'completed', 'no_show', 'cancelled']


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


class BarberStaffPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        user = (auth.current_user if auth else None) or {}
        self.staff_label = (user.get('display_name')
                            or user.get('username', 'staff'))

        self.window = tk.Toplevel(parent)
        self.window.title("Barbershop — Staff Portal")
        self.window.geometry("1120x700")
        self.window.minsize(960, 580)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.scope_var = tk.StringVar(value='Today')
        self.info_var = tk.StringVar(value="")

        self._build_ui()
        self._load_appointments()
        self._load_services()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#6e2c00', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"Barbershop — Staff ({self.staff_label})",
                 font=('Arial', 14, 'bold'), bg='#6e2c00', fg='white'
                 ).pack(side='left', padx=18, pady=12)
        tk.Button(header, text="Close", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=10, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_appts_tab(nb)
        self._build_services_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_appts_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Appointments")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Scope:").pack(side='left', padx=(0, 4))
        ttk.Combobox(bar, textvariable=self.scope_var, state='readonly',
                     values=['Today', 'Upcoming', 'Past', 'All'], width=12
                     ).pack(side='left', padx=(0, 12))
        ttk.Button(bar, text="Apply",
                   command=self._load_appointments).pack(side='left')
        ttk.Button(bar, text="Refresh",
                   command=self._load_appointments).pack(side='right')

        status_bar = ttk.Frame(frame)
        status_bar.pack(fill='x', pady=(0, 6))
        ttk.Label(status_bar, text="Advance selected:").pack(side='left')
        for st in ['confirmed', 'completed', 'no_show', 'cancelled']:
            ttk.Button(status_bar, text=st.replace('_', ' ').title(),
                       command=lambda s=st: self._set_status(s)
                       ).pack(side='left', padx=2)

        cols = ('date', 'time', 'customer', 'service', 'staff',
                'price', 'status')
        self.tree = ttk.Treeview(frame, columns=cols,
                                 show='headings', selectmode='browse')
        for key, title, width in [
            ('date', 'Date', 110), ('time', 'Time', 80),
            ('customer', 'Customer', 180),
            ('service', 'Service', 200),
            ('staff', 'Barber', 140),
            ('price', 'Price £', 90),
            ('status', 'Status', 120),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width,
                             anchor='w' if key in ('customer', 'service',
                                                   'staff')
                                           else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.tag_configure('today', background='#fef9e7')
        self.tree.tag_configure('done', background='#d5f5e3')
        self.tree.tag_configure('cancelled', foreground='#888')

    def _build_services_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Services & Staff")

        services = ttk.LabelFrame(frame, text="Services", padding=4)
        services.pack(fill='both', expand=True, pady=(0, 6))
        s_cols = ('name', 'type', 'duration', 'price', 'available')
        self.svc_tree = ttk.Treeview(services, columns=s_cols,
                                     show='headings', height=8)
        for key, title, width in [
            ('name', 'Service', 240), ('type', 'Type', 140),
            ('duration', 'Duration (min)', 120),
            ('price', 'Price £', 100), ('available', 'Available', 100),
        ]:
            self.svc_tree.heading(key, text=title)
            self.svc_tree.column(key, width=width,
                                 anchor='w' if key in ('name', 'type')
                                               else 'center')
        self.svc_tree.pack(fill='both', expand=True)

        staff = ttk.LabelFrame(frame, text="Staff", padding=4)
        staff.pack(fill='both', expand=True)
        st_cols = ('name', 'employee_id', 'specialties', 'active')
        self.staff_tree = ttk.Treeview(staff, columns=st_cols,
                                       show='headings', height=6)
        for key, title, width in [
            ('name', 'Name', 200), ('employee_id', 'Employee ID', 140),
            ('specialties', 'Specialties', 360),
            ('active', 'Active', 80),
        ]:
            self.staff_tree.heading(key, text=title)
            self.staff_tree.column(key, width=width,
                                   anchor='w' if key in ('name', 'specialties')
                                                 else 'center')
        self.staff_tree.pack(fill='both', expand=True)

    # ------------------------------------------------------------------

    def _load_appointments(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        today = datetime.now().date().isoformat()
        clauses = []
        params = []
        scope = self.scope_var.get()
        if scope == 'Today':
            clauses.append("appointment_date = ?")
            params.append(today)
        elif scope == 'Upcoming':
            clauses.append("appointment_date >= ?")
            params.append(today)
        elif scope == 'Past':
            clauses.append("appointment_date < ?")
            params.append(today)

        sql = (
            "SELECT appointment_id, appointment_date, appointment_time, "
            "       customer_name, service_name, staff_name, price, status "
            "FROM barber_appointments"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += (" ORDER BY appointment_date "
                + ("DESC" if scope == 'Past' else "ASC")
                + ", appointment_time"
                + (" DESC" if scope == 'Past' else "")
                + " LIMIT 500")

        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)
            return
        for aid, date, time_, cust, svc, staff, price, status in rows:
            tag = ()
            if status == 'completed':
                tag = ('done',)
            elif date == today:
                tag = ('today',)
            elif status == 'cancelled':
                tag = ('cancelled',)
            price_str = f"{price:.2f}" if price is not None else ''
            self.tree.insert('', 'end', iid=str(aid), values=(
                date or '', (time_ or '')[:5],
                cust or '', svc or '', staff or '',
                price_str, status or ''
            ), tags=tag)
        self.info_var.set(f"{len(rows)} appointment(s).")

    def _set_status(self, new_status):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select an appointment first.",
                                parent=self.window)
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE barber_appointments "
                    "SET status = ?, updated_at = ? "
                    "WHERE appointment_id = ?",
                    (new_status,
                     datetime.now().isoformat(timespec='seconds'),
                     int(sel[0]))
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Update Failed", str(e),
                                 parent=self.window)
            return
        self.info_var.set(f"Appointment {sel[0]} → {new_status}.")
        self._load_appointments()

    def _load_services(self):
        for i in self.svc_tree.get_children():
            self.svc_tree.delete(i)
        for i in self.staff_tree.get_children():
            self.staff_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, service_type, duration_minutes, price, "
                    "       is_available "
                    "FROM barber_services ORDER BY name"
                )
                for row in cur.fetchall():
                    price_str = (f"{row[3]:.2f}"
                                 if row[3] is not None else '')
                    self.svc_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '',
                        row[2] or '', price_str,
                        'Yes' if row[4] else 'No'
                    ))
                cur.execute(
                    "SELECT name, employee_id, specialties, is_active "
                    "FROM barber_staff ORDER BY name"
                )
                for row in cur.fetchall():
                    self.staff_tree.insert('', 'end', values=(
                        row[0] or '', row[1] or '',
                        row[2] or '', 'Yes' if row[3] else 'No'
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)


class BarberStudentPortal:
    def __init__(self, parent, auth):
        self.auth = auth
        user = (auth.current_user if auth else None) or {}
        self.user_id = user.get('id') or user.get('user_id')
        self.customer_name = user.get('display_name') or user.get('username', '')
        self.customer_email = user.get('email', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Barbershop — My Portal")
        self.window.geometry("1020x660")
        self.window.minsize(880, 560)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.info_var = tk.StringVar(value="")
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#6e2c00', height=56)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text=f"Barbershop — {self.customer_name}",
                 font=('Arial', 14, 'bold'), bg='#6e2c00', fg='white'
                 ).pack(side='left', padx=18, pady=14)
        tk.Button(header, text="Refresh", bg='#4a1d00', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._refresh_all).pack(side='right', padx=8, pady=12)
        tk.Button(header, text="Close", bg='#4a1d00', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self.window.destroy).pack(side='right', padx=8, pady=12)

        nb = ttk.Notebook(self.window)
        nb.pack(fill='both', expand=True, padx=10, pady=(8, 4))
        self._build_services_tab(nb)
        self._build_mine_tab(nb)

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.info_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    def _build_services_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="Book")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Pick a service and click Book.",
                  font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Button(bar, text="Book Appointment",
                   command=self._book).pack(side='right')

        cols = ('name', 'type', 'duration', 'price')
        self.svc_tree = ttk.Treeview(frame, columns=cols,
                                     show='headings', selectmode='browse')
        for key, title, width in [
            ('name', 'Service', 280), ('type', 'Type', 160),
            ('duration', 'Duration (min)', 140), ('price', 'Price £', 120),
        ]:
            self.svc_tree.heading(key, text=title)
            self.svc_tree.column(key, width=width,
                                 anchor='w' if key in ('name', 'type')
                                               else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.svc_tree.yview)
        self.svc_tree.configure(yscrollcommand=vsb.set)
        self.svc_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _build_mine_tab(self, nb):
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text="My Appointments")

        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="My upcoming and past appointments",
                  font=('Arial', 11, 'bold')).pack(side='left')
        ttk.Button(bar, text="Cancel Selected",
                   command=self._cancel).pack(side='right')

        cols = ('appt_id', 'date', 'time', 'service', 'barber',
                'price', 'status')
        self.mine_tree = ttk.Treeview(frame, columns=cols,
                                      show='headings', selectmode='browse')
        for key, title, width in [
            ('appt_id', 'ID', 70), ('date', 'Date', 110),
            ('time', 'Time', 80), ('service', 'Service', 220),
            ('barber', 'Barber', 150), ('price', 'Price £', 100),
            ('status', 'Status', 120),
        ]:
            self.mine_tree.heading(key, text=title)
            self.mine_tree.column(key, width=width,
                                  anchor='w' if key in ('service', 'barber')
                                                else 'center')
        vsb = ttk.Scrollbar(frame, orient='vertical',
                            command=self.mine_tree.yview)
        self.mine_tree.configure(yscrollcommand=vsb.set)
        self.mine_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_all(self):
        self._load_services()
        self._load_mine()

    def _load_services(self):
        for i in self.svc_tree.get_children():
            self.svc_tree.delete(i)
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT service_id, name, service_type, "
                    "       duration_minutes, price "
                    "FROM barber_services "
                    "WHERE COALESCE(is_available, 1) = 1 "
                    "ORDER BY name"
                )
                for row in cur.fetchall():
                    price_str = (f"{row[4]:.2f}"
                                 if row[4] is not None else '')
                    self.svc_tree.insert('', 'end', iid=str(row[0]), values=(
                        row[1] or '', row[2] or '',
                        row[3] or '', price_str
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _book(self):
        sel = self.svc_tree.selection()
        if not sel:
            messagebox.showinfo("No Service",
                                "Pick a service first.",
                                parent=self.window)
            return
        sid = int(sel[0])
        BookAppointmentDialog(self.window, service_id=sid,
                              customer_id=self.user_id,
                              customer_name=self.customer_name,
                              customer_email=self.customer_email,
                              on_save=self._refresh_all)

    def _load_mine(self):
        for i in self.mine_tree.get_children():
            self.mine_tree.delete(i)
        if not self.user_id:
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT appointment_id, appointment_date, "
                    "       appointment_time, service_name, staff_name, "
                    "       price, status "
                    "FROM barber_appointments "
                    "WHERE customer_id = ? "
                    "ORDER BY appointment_date DESC, appointment_time DESC "
                    "LIMIT 500",
                    (self.user_id,)
                )
                for row in cur.fetchall():
                    price_str = (f"{row[5]:.2f}"
                                 if row[5] is not None else '')
                    self.mine_tree.insert('', 'end', iid=str(row[0]), values=(
                        row[0], row[1] or '', (row[2] or '')[:5],
                        row[3] or '', row[4] or '', price_str, row[6] or ''
                    ))
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.window)

    def _cancel(self):
        sel = self.mine_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Pick an appointment to cancel.",
                                parent=self.window)
            return
        aid = int(sel[0])
        if not messagebox.askyesno("Cancel Appointment",
                                   "Cancel this appointment?",
                                   parent=self.window):
            return
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE barber_appointments "
                    "SET status = 'cancelled', updated_at = ? "
                    "WHERE appointment_id = ? AND customer_id = ? "
                    "  AND status NOT IN ('completed', 'cancelled')",
                    (datetime.now().isoformat(timespec='seconds'),
                     aid, self.user_id)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Cancel Failed", str(e),
                                 parent=self.window)
            return
        self._refresh_all()


class BookAppointmentDialog:
    def __init__(self, parent, service_id, customer_id, customer_name,
                 customer_email, on_save):
        self.service_id = service_id
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.customer_email = customer_email
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Book Appointment")
        self.dialog.geometry("440x380")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        default_date = (datetime.now() + timedelta(days=1)).date().isoformat()
        self.date_var = tk.StringVar(value=default_date)
        self.time_var = tk.StringVar(value='10:00')
        self.staff_var = tk.StringVar(value='Any')
        self.phone_var = tk.StringVar()
        self.notes_text = None

        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=0, column=0,
                                                          sticky='w', pady=4)
        ttk.Entry(frame, textvariable=self.date_var, width=28).grid(
            row=0, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Time (HH:MM):").grid(row=1, column=0,
                                                      sticky='w', pady=4)
        ttk.Entry(frame, textvariable=self.time_var, width=28).grid(
            row=1, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Preferred barber:").grid(row=2, column=0,
                                                         sticky='w', pady=4)
        staff_vals = self._load_staff()
        ttk.Combobox(frame, textvariable=self.staff_var,
                     values=['Any'] + staff_vals, width=26).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Phone:").grid(row=3, column=0,
                                               sticky='w', pady=4)
        ttk.Entry(frame, textvariable=self.phone_var, width=28).grid(
            row=3, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Special requests:"
                  ).grid(row=4, column=0, sticky='nw', pady=4)
        self.notes_text = tk.Text(frame, width=28, height=4, wrap='word')
        self.notes_text.grid(row=4, column=1, sticky='w', pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, pady=(12, 0), sticky='e')
        ttk.Button(btns, text="Book",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _load_staff(self):
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM barber_staff "
                    "WHERE COALESCE(is_active, 1) = 1 "
                    "ORDER BY name"
                )
                return [r[0] for r in cur.fetchall() if r[0]]
        except Exception:
            return []

    def _save(self):
        date = self.date_var.get().strip()
        time_ = self.time_var.get().strip()
        try:
            datetime.strptime(date, '%Y-%m-%d')
            datetime.strptime(time_, '%H:%M')
        except ValueError:
            messagebox.showerror("Invalid",
                                 "Date must be YYYY-MM-DD, time HH:MM.",
                                 parent=self.dialog)
            return

        staff_name = self.staff_var.get().strip()
        staff_id = None
        svc = None
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, duration_minutes, price "
                    "FROM barber_services WHERE service_id = ?",
                    (self.service_id,)
                )
                svc = cur.fetchone()
                if staff_name and staff_name != 'Any':
                    cur.execute(
                        "SELECT staff_id FROM barber_staff WHERE name = ?",
                        (staff_name,)
                    )
                    srow = cur.fetchone()
                    if srow:
                        staff_id = srow[0]
        except Exception as e:
            messagebox.showerror("Database Error", str(e),
                                 parent=self.dialog)
            return
        if not svc:
            messagebox.showerror("Invalid", "Service not found.",
                                 parent=self.dialog)
            return
        svc_name, duration, price = svc

        now = datetime.now().isoformat(timespec='seconds')
        appt_number = f"BA-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            with _connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO barber_appointments "
                    "(appointment_number, customer_id, customer_name, "
                    " customer_email, customer_phone, staff_id, staff_name, "
                    " service_id, service_name, appointment_date, "
                    " appointment_time, duration_minutes, price, status, "
                    " payment_status, special_requests, "
                    " created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "        'scheduled', 'pending', ?, ?, ?)",
                    (appt_number, self.customer_id, self.customer_name,
                     self.customer_email, self.phone_var.get().strip(),
                     staff_id, staff_name if staff_name != 'Any' else None,
                     self.service_id, svc_name,
                     date, time_, duration, price,
                     self.notes_text.get('1.0', 'end').strip(),
                     now, now)
                )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Booking Failed", str(e),
                                 parent=self.dialog)
            return
        messagebox.showinfo("Booked",
                            f"{svc_name} booked for {date} at {time_}. "
                            f"Reference: {appt_number}.",
                            parent=self.dialog)
        self.dialog.destroy()
        if self.on_save:
            self.on_save()


def launch_barber_staff_portal(parent, auth):
    return BarberStaffPortal(parent, auth)


def launch_barber_student_portal(parent, auth):
    return BarberStudentPortal(parent, auth)
