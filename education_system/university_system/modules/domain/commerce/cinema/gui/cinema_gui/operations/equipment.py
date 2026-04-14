"""
Cinema Booking System - Equipment Management
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

def show_equipment_page(self):
    """Display equipment management page."""
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.equipment.title"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    # Action buttons
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text="+ Add Equipment", style="Success.TButton", command=self.add_equipment).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.log_maintenance"), style="Primary.TButton", command=self.log_equipment_maintenance).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.update_hours"), style="Secondary.TButton", command=self.update_equipment_hours).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.maintenance.schedule"), style="Secondary.TButton", command=self.show_maintenance_schedule).pack(side="left", padx=5)

    # Equipment alerts
    alerts_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    alerts_frame.pack(fill="x", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        # Check for overdue maintenance
        cursor.execute('''
            SELECT name, equipment_type, screen_number, next_service_due, hours_used, max_hours_before_service
            FROM equipment
            WHERE status = 'operational' AND (
                (next_service_due IS NOT NULL AND date(next_service_due) <= date('now'))
                OR (hours_used >= max_hours_before_service)
            )
        ''')
        alerts = cursor.fetchall()

        if alerts:
            tk.Label(alerts_frame, text=_t("cinema.maintenance.alerts"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#dc3545").pack(anchor="w")
            for alert in alerts:
                name, eq_type, screen, due_date, hours, max_hours = alert
                alert_text = f"\u26a0 {name} (Screen {screen or 'N/A'})"
                if due_date and datetime.strptime(due_date, "%Y-%m-%d") <= datetime.now():
                    alert_text += f" - Overdue since {due_date}"
                if hours >= max_hours:
                    alert_text += f" - {hours}/{max_hours} hours"
                tk.Label(alerts_frame, text=alert_text, bg="#ffffff", fg="#ffc107").pack(anchor="w")
        else:
            tk.Label(alerts_frame, text=_t("cinema.maintenance.no_alerts"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#27ae60").pack(anchor="w")
            tk.Label(alerts_frame, text=_t("cinema.maintenance.all_up_to_date"), bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

        # Equipment list
        tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True, pady=10)

        columns = ("ID", "Name", "Type", "Screen", "Hours", "Last Service", "Next Due", "Status")
        self.equip_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.equip_tree.heading(col, text=col)
            self.equip_tree.column(col, width=90)

        cursor.execute('''
            SELECT id, name, equipment_type, screen_number, hours_used, last_service_date, next_service_due, status
            FROM equipment ORDER BY screen_number, equipment_type
        ''')
        for row in cursor.fetchall():
            status = row[7].upper() if row[7] else "OPERATIONAL"
            self.equip_tree.insert("", "end", values=(row[0], row[1], row[2], row[3] or "-", row[4], row[5] or "-", row[6] or "-", status))

    finally:
        conn.close()

    self.equip_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.equip_tree.yview)
    self.equip_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons for selected equipment
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.btn.view_history"), style="Secondary.TButton", command=self.view_equipment_history).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.edit_equipment"), style="Secondary.TButton", command=self.edit_equipment).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.mark_out_of_service"), style="Danger.TButton", command=self.mark_equipment_out_of_service).pack(side="left", padx=5)

def add_equipment(self):
    """Add new equipment to the system."""
    form = tk.Toplevel(self.root)
    form.title("Add Equipment")
    form.geometry("450x550")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text="Add Equipment", font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    fields = {}

    labels = [("Name:*", "name"), ("Type:*", "type"), ("Screen #:", "screen"), ("Brand:", "brand"),
              ("Model:", "model"), ("Serial #:", "serial"), ("Install Date:", "install"),
              ("Warranty Until:", "warranty"), ("Max Hours:", "max_hours")]

    for i, (label, key) in enumerate(labels):
        tk.Label(frame, text=label, bg="#ffffff", fg="#333333").grid(row=i+1, column=0, sticky="w", pady=5)

        if key == "type":
            type_var = tk.StringVar(value="projector")
            types = ["projector", "sound_system", "hvac", "seating", "screen", "lighting", "other"]
            e = ttk.Combobox(frame, textvariable=type_var, values=types, width=27)
            fields['type_var'] = type_var
        else:
            e = ttk.Entry(frame, width=30)
            if key == "install":
                e.insert(0, datetime.now().strftime("%Y-%m-%d"))
            elif key == "max_hours":
                e.insert(0, "2000")
        e.grid(row=i+1, column=1, pady=5)
        fields[key] = e

    def save():
        if not fields['name'].get().strip():
            messagebox.showwarning(_t("cinema.common.warning"), "Name is required")
            return

        screen = None
        if fields['screen'].get().strip():
            try:
                screen = int(fields['screen'].get())
            except (ValueError, TypeError):
                pass

        max_hours = 2000
        try:
            max_hours = int(fields['max_hours'].get())
        except (ValueError, TypeError):
            pass

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO equipment (name, equipment_type, screen_number, brand, model, serial_number,
                                       install_date, warranty_until, max_hours_before_service)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fields['name'].get(), fields['type_var'].get(), screen, fields['brand'].get(),
                  fields['model'].get(), fields['serial'].get(), fields['install'].get(),
                  fields['warranty'].get(), max_hours))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Equipment added!")
        form.destroy()
        self.show_equipment_page()

    ttk.Button(frame, text="Add Equipment", style="Success.TButton", command=save).grid(row=len(labels)+1, column=0, columnspan=2, pady=20)

def log_equipment_maintenance(self):
    """Log maintenance performed on equipment."""
    selected = self.equip_tree.selection() if hasattr(self, 'equip_tree') else None

    form = tk.Toplevel(self.root)
    form.title("Log Maintenance")
    form.geometry("450x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.btn.log_maintenance"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    # Get equipment list
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, screen_number FROM equipment ORDER BY name")
        equipment_list = cursor.fetchall()
    finally:
        conn.close()

    equip_names = [f"{e[1]} (Screen {e[2] or 'N/A'})" for e in equipment_list]
    equip_ids = {f"{e[1]} (Screen {e[2] or 'N/A'})": e[0] for e in equipment_list}

    fields = {}

    tk.Label(frame, text=_t("cinema.labels.equipment"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    equip_var = tk.StringVar()
    equip_combo = ttk.Combobox(frame, textvariable=equip_var, values=equip_names, width=27, state="readonly")
    equip_combo.grid(row=1, column=1, pady=5)
    if selected:
        equip_id = self.equip_tree.item(selected[0])['values'][0]
        for name, eid in equip_ids.items():
            if eid == equip_id:
                equip_combo.set(name)
                break
    fields['equip_var'] = equip_var

    tk.Label(frame, text=_t("cinema.maintenance.type_label"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    maint_types = ["routine", "repair", "replacement", "inspection", "cleaning", "calibration", "emergency"]
    maint_var = tk.StringVar(value="routine")
    maint_combo = ttk.Combobox(frame, textvariable=maint_var, values=maint_types, width=27)
    maint_combo.grid(row=2, column=1, pady=5)
    fields['maint_var'] = maint_var

    tk.Label(frame, text=_t("cinema.labels.description"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="w", pady=5)
    desc_text = tk.Text(frame, height=4, width=25, bg="#0f3460", fg="white")
    desc_text.grid(row=3, column=1, pady=5)
    fields['desc'] = desc_text

    tk.Label(frame, text=_t("cinema.labels.performed_by"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    performed_e = ttk.Entry(frame, width=30)
    performed_e.grid(row=4, column=1, pady=5)
    fields['performed'] = performed_e

    tk.Label(frame, text=_t("cinema.labels.cost_gbp"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    cost_e = ttk.Entry(frame, width=30)
    cost_e.insert(0, "0")
    cost_e.grid(row=5, column=1, pady=5)
    fields['cost'] = cost_e

    tk.Label(frame, text=_t("cinema.labels.parts_replaced"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="w", pady=5)
    parts_e = ttk.Entry(frame, width=30)
    parts_e.grid(row=6, column=1, pady=5)
    fields['parts'] = parts_e

    tk.Label(frame, text=_t("cinema.labels.hours_at_service"), bg="#ffffff", fg="#333333").grid(row=7, column=0, sticky="w", pady=5)
    hours_e = ttk.Entry(frame, width=30)
    hours_e.grid(row=7, column=1, pady=5)
    fields['hours'] = hours_e

    tk.Label(frame, text=_t("cinema.labels.next_service_hours"), bg="#ffffff", fg="#333333").grid(row=8, column=0, sticky="w", pady=5)
    next_hours_e = ttk.Entry(frame, width=30)
    next_hours_e.grid(row=8, column=1, pady=5)
    fields['next_hours'] = next_hours_e

    def save():
        if not fields['equip_var'].get():
            messagebox.showwarning(_t("cinema.common.warning"), "Please select equipment")
            return

        equip_id = equip_ids.get(fields['equip_var'].get())
        cost = 0
        try:
            cost = float(fields['cost'].get())
        except (ValueError, TypeError):
            pass

        hours_at = None
        if fields['hours'].get().strip():
            try:
                hours_at = int(fields['hours'].get())
            except (ValueError, TypeError):
                pass

        next_hours = None
        if fields['next_hours'].get().strip():
            try:
                next_hours = int(fields['next_hours'].get())
            except (ValueError, TypeError):
                pass

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()

            # Log the maintenance
            cursor.execute('''
                INSERT INTO equipment_maintenance_log
                (equipment_id, maintenance_type, description, performed_by, cost, parts_replaced, hours_at_service, next_service_hours, service_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (equip_id, fields['maint_var'].get(), fields['desc'].get("1.0", tk.END).strip(),
                  fields['performed'].get(), cost, fields['parts'].get(), hours_at, next_hours,
                  datetime.now().strftime("%Y-%m-%d")))

            # Update equipment record
            next_due = None
            if next_hours and hours_at:
                # Calculate next service date based on average usage
                next_due = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

            cursor.execute('''
                UPDATE equipment SET last_service_date = ?, next_service_due = ?
                WHERE id = ?
            ''', (datetime.now().strftime("%Y-%m-%d"), next_due, equip_id))

            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Maintenance logged!")
        form.destroy()
        self.show_equipment_page()

    ttk.Button(frame, text=_t("cinema.btn.log_maintenance"), style="Success.TButton", command=save).grid(row=9, column=0, columnspan=2, pady=20)

def update_equipment_hours(self):
    """Update usage hours for equipment."""
    selected = self.equip_tree.selection() if hasattr(self, 'equip_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select equipment to update")
        return

    equip_id = self.equip_tree.item(selected[0])['values'][0]
    equip_name = self.equip_tree.item(selected[0])['values'][1]
    current_hours = self.equip_tree.item(selected[0])['values'][4]

    dialog = tk.Toplevel(self.root)
    dialog.title("Update Hours")
    dialog.geometry("300x200")
    dialog.configure(bg="#ecf0f1")
    dialog.transient(self.root)
    dialog.grab_set()

    frame = ttk.Frame(dialog, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=f"Update Hours: {equip_name}", bg="#ffffff", fg="#e74c3c", font=("Helvetica", 12, "bold")).pack(pady=10)
    tk.Label(frame, text=f"Current Hours: {current_hours}", bg="#ffffff", fg="#333333").pack()

    tk.Label(frame, text=_t("cinema.labels.new_hours"), bg="#ffffff", fg="#333333").pack(pady=(10, 0))
    hours_e = ttk.Entry(frame, width=20)
    hours_e.insert(0, str(current_hours))
    hours_e.pack(pady=5)

    def update():
        try:
            new_hours = int(hours_e.get())
        except (ValueError, TypeError):
            messagebox.showwarning(_t("cinema.common.warning"), "Invalid hours value")
            return

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE equipment SET hours_used = ? WHERE id = ?", (new_hours, equip_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Hours updated!")
        dialog.destroy()
        self.show_equipment_page()

    ttk.Button(frame, text=_t("cinema.btn.update"), style="Success.TButton", command=update).pack(pady=15)

def view_equipment_history(self):
    """View maintenance history for selected equipment."""
    selected = self.equip_tree.selection() if hasattr(self, 'equip_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select equipment")
        return

    equip_id = self.equip_tree.item(selected[0])['values'][0]
    equip_name = self.equip_tree.item(selected[0])['values'][1]

    form = tk.Toplevel(self.root)
    form.title(f"Maintenance History - {equip_name}")
    form.geometry("700x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=f"Maintenance History: {equip_name}", font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tree_frame = ttk.Frame(frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("Date", "Type", "Description", "Performed By", "Cost", "Parts")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=100)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT service_date, maintenance_type, description, performed_by, cost, parts_replaced
            FROM equipment_maintenance_log
            WHERE equipment_id = ?
            ORDER BY service_date DESC
        ''', (equip_id,))
        for row in cursor.fetchall():
            tree.insert("", "end", values=(row[0], row[1], row[2][:30] if row[2] else "-", row[3] or "-", f"\u00a3{row[4]:.2f}" if row[4] else "-", row[5] or "-"))
    finally:
        conn.close()

    tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

def edit_equipment(self):
    """Edit selected equipment details."""
    selected = self.equip_tree.selection() if hasattr(self, 'equip_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select equipment")
        return

    equip_id = self.equip_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM equipment WHERE id = ?", (equip_id,))
        equip = cursor.fetchone()
    finally:
        conn.close()

    if not equip:
        messagebox.showerror(_t("cinema.common.error"), "Equipment not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Edit Equipment")
    form.geometry("400x400")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.btn.edit_equipment"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    tk.Label(frame, text=f"Name: {equip[1]}", bg="#ffffff", fg="#333333").pack(anchor="w")
    tk.Label(frame, text=f"Type: {equip[2]}", bg="#ffffff", fg="#333333").pack(anchor="w")

    tk.Label(frame, text=_t("cinema.screenings.status_label"), bg="#ffffff", fg="#333333").pack(anchor="w", pady=(10, 0))
    status_var = tk.StringVar(value=equip[14] or "operational")
    statuses = ["operational", "maintenance", "out_of_service", "retired"]
    status_combo = ttk.Combobox(frame, textvariable=status_var, values=statuses, width=25)
    status_combo.pack(pady=5)

    tk.Label(frame, text=_t("cinema.maintenance.next_service"), bg="#ffffff", fg="#333333").pack(anchor="w")
    next_due_e = ttk.Entry(frame, width=28)
    next_due_e.insert(0, equip[11] or "")
    next_due_e.pack(pady=5)

    tk.Label(frame, text=_t("cinema.tickets.notes_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    notes_e = ttk.Entry(frame, width=28)
    notes_e.insert(0, equip[15] or "")
    notes_e.pack(pady=5)

    def save():
        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE equipment SET status = ?, next_service_due = ?, notes = ?
                WHERE id = ?
            ''', (status_var.get(), next_due_e.get() or None, notes_e.get(), equip_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Equipment updated!")
        form.destroy()
        self.show_equipment_page()

    ttk.Button(frame, text=_t("cinema.buttons.save_changes"), style="Success.TButton", command=save).pack(pady=20)

def mark_equipment_out_of_service(self):
    """Mark selected equipment as out of service."""
    selected = self.equip_tree.selection() if hasattr(self, 'equip_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select equipment")
        return

    equip_id = self.equip_tree.item(selected[0])['values'][0]
    equip_name = self.equip_tree.item(selected[0])['values'][1]

    if not messagebox.askyesno(_t("cinema.common.confirm"), f"Mark '{equip_name}' as out of service?"):
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE equipment SET status = 'out_of_service' WHERE id = ?", (equip_id,))
        conn.commit()
    finally:
        conn.close()

    messagebox.showinfo(_t("cinema.common.success"), "Equipment marked as out of service")
    self.show_equipment_page()

def show_maintenance_schedule(self):
    """Show preventive maintenance schedule."""
    form = tk.Toplevel(self.root)
    form.title("Maintenance Schedule")
    form.geometry("800x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.maintenance.preventive_schedule"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    # Next 30 days view
    schedule_frame = ttk.Frame(frame, style="Card.TFrame")
    schedule_frame.pack(fill="both", expand=True, pady=10)

    columns = ("Equipment", "Type", "Screen", "Due Date", "Hours", "Max Hours", "Priority")
    tree = ttk.Treeview(schedule_frame, columns=columns, show="headings", height=12)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=100)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, equipment_type, screen_number, next_service_due, hours_used, max_hours_before_service
            FROM equipment
            WHERE status = 'operational'
            ORDER BY
                CASE WHEN hours_used >= max_hours_before_service THEN 0
                     WHEN next_service_due IS NOT NULL AND date(next_service_due) <= date('now', '+7 days') THEN 1
                     WHEN next_service_due IS NOT NULL AND date(next_service_due) <= date('now', '+30 days') THEN 2
                     ELSE 3 END,
                next_service_due
        ''')
        for row in cursor.fetchall():
            name, eq_type, screen, due_date, hours, max_hours = row
            if hours >= max_hours:
                priority = "CRITICAL"
            elif due_date and datetime.strptime(due_date, "%Y-%m-%d") <= datetime.now():
                priority = "OVERDUE"
            elif due_date and datetime.strptime(due_date, "%Y-%m-%d") <= datetime.now() + timedelta(days=7):
                priority = "HIGH"
            elif due_date and datetime.strptime(due_date, "%Y-%m-%d") <= datetime.now() + timedelta(days=30):
                priority = "MEDIUM"
            else:
                priority = "LOW"

            tree.insert("", "end", values=(name, eq_type, screen or "-", due_date or "-", hours, max_hours, priority))
    finally:
        conn.close()

    tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(schedule_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
