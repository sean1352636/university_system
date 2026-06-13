"""
Cinema Booking System - Incident Management

Functions for reporting, viewing, updating, and exporting
incident reports with filtering and statistics.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import csv
from datetime import datetime, timedelta

try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key, default=None):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

from education_system.university_system.modules.domain.commerce.cinema.gui.cinema_gui.database import DB_FILE

def show_incidents_page(self):
    """Display incident reporting and management page."""
    self.clear_content()
    ttk.Label(self.content_frame, text=_t("cinema.incidents.title"), style="Subtitle.TLabel").pack(anchor="w", pady=10)

    # Action buttons
    btn_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    btn_frame.pack(fill="x", pady=10)
    ttk.Button(btn_frame, text=_t("cinema.btn.report_incident"), style="Danger.TButton", command=self.report_incident).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.incidents.statistics"), style="Secondary.TButton", command=self.show_incident_stats).pack(side="left", padx=5)
    ttk.Button(btn_frame, text=_t("cinema.btn.export_report"), style="Secondary.TButton", command=self.export_incident_report).pack(side="left", padx=5)

    # Filter tabs
    filter_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    filter_frame.pack(fill="x", pady=5)

    self.incident_filter = getattr(self, 'incident_filter', 'open')
    filters = [("Open", "open"), ("Resolved", "resolved"), ("All", "all")]

    for text, value in filters:
        style = "Primary.TButton" if self.incident_filter == value else "Secondary.TButton"
        ttk.Button(filter_frame, text=text, style=style,
                  command=lambda v=value: self.set_incident_filter(v)).pack(side="left", padx=2)

    # Severity filter
    tk.Label(filter_frame, text=_t("cinema.incidents.severity"), bg="#ecf0f1", fg="#333333").pack(side="left", padx=(20, 5))
    self.severity_filter = getattr(self, 'severity_filter', 'all')
    severities = ["all", "critical", "high", "medium", "low"]
    sev_var = tk.StringVar(value=self.severity_filter)
    sev_combo = ttk.Combobox(filter_frame, textvariable=sev_var, values=severities, width=10, state="readonly")
    sev_combo.pack(side="left")
    sev_combo.bind("<<ComboboxSelected>>", lambda e: [setattr(self, 'severity_filter', sev_var.get()), self.show_incidents_page()])

    # Incidents list
    tree_frame = ttk.Frame(self.content_frame, style="Card.TFrame")
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Date/Time", "Type", "Severity", "Location", "Description", "Status")
    self.incident_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
    for col in columns:
        self.incident_tree.heading(col, text=col)
        self.incident_tree.column(col, width=100)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        query = "SELECT id, incident_datetime, incident_type, severity, location, description, status FROM incidents WHERE 1=1"
        params = []

        if self.incident_filter == 'open':
            query += " AND status = 'open'"
        elif self.incident_filter == 'resolved':
            query += " AND status = 'resolved'"

        if self.severity_filter != 'all':
            query += " AND severity = ?"
            params.append(self.severity_filter)

        query += " ORDER BY incident_datetime DESC"

        cursor.execute(query, params)
        for row in cursor.fetchall():
            severity_colors = {"critical": "#dc3545", "high": "#f4a261", "medium": "#ffc107", "low": "#4ecca3"}
            self.incident_tree.insert("", "end", values=(row[0], row[1], row[2], row[3].upper(), row[4] or "-", row[5][:30] if row[5] else "", row[6].upper()))
    finally:
        conn.close()

    self.incident_tree.pack(fill="both", expand=True, side="left")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.incident_tree.yview)
    self.incident_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # Action buttons for selected incident
    action_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
    action_frame.pack(fill="x", pady=10)
    ttk.Button(action_frame, text=_t("cinema.members.view_details"), style="Secondary.TButton", command=self.view_incident_details).pack(side="left", padx=5)
    ttk.Button(action_frame, text=_t("cinema.btn.update_resolve"), style="Success.TButton", command=self.update_incident).pack(side="left", padx=5)

    # Quick stats
    stats_frame = ttk.Frame(self.content_frame, style="Card.TFrame", padding=10)
    stats_frame.pack(fill="x", pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'open'")
        open_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'open' AND severity IN ('critical', 'high')")
        urgent_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE date(incident_datetime) = date('now')")
        today_count = cursor.fetchone()[0]
    finally:
        conn.close()

    stats_text = f"Open: {open_count} | Urgent (Critical/High): {urgent_count} | Today: {today_count}"
    tk.Label(stats_frame, text=stats_text, bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

def set_incident_filter(self, filter_value):
    """Set the incident filter."""
    self.incident_filter = filter_value
    self.show_incidents_page()

def report_incident(self):
    """Report a new incident."""
    form = tk.Toplevel(self.root)
    form.title("Report Incident")
    form.geometry("500x650")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.incidents.report"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").grid(row=0, column=0, columnspan=2, pady=10)

    fields = {}

    tk.Label(frame, text=_t("cinema.labels.incident_type"), bg="#ffffff", fg="#333333").grid(row=1, column=0, sticky="w", pady=5)
    types = ["spill", "medical", "disruption", "equipment_failure", "security", "injury", "complaint", "theft", "other"]
    type_var = tk.StringVar(value="spill")
    type_combo = ttk.Combobox(frame, textvariable=type_var, values=types, width=27)
    type_combo.grid(row=1, column=1, pady=5)
    fields['type_var'] = type_var

    tk.Label(frame, text=_t("cinema.labels.severity_required"), bg="#ffffff", fg="#333333").grid(row=2, column=0, sticky="w", pady=5)
    severities = ["low", "medium", "high", "critical"]
    sev_var = tk.StringVar(value="low")
    sev_combo = ttk.Combobox(frame, textvariable=sev_var, values=severities, width=27)
    sev_combo.grid(row=2, column=1, pady=5)
    fields['sev_var'] = sev_var

    tk.Label(frame, text=_t("cinema.labels.description_required"), bg="#ffffff", fg="#333333").grid(row=3, column=0, sticky="nw", pady=5)
    desc_text = tk.Text(frame, height=4, width=25, bg="#0f3460", fg="white")
    desc_text.grid(row=3, column=1, pady=5)
    fields['desc'] = desc_text

    tk.Label(frame, text=_t("cinema.common.location"), bg="#ffffff", fg="#333333").grid(row=4, column=0, sticky="w", pady=5)
    loc_e = ttk.Entry(frame, width=30)
    loc_e.grid(row=4, column=1, pady=5)
    fields['location'] = loc_e

    tk.Label(frame, text=_t("cinema.labels.screen_number"), bg="#ffffff", fg="#333333").grid(row=5, column=0, sticky="w", pady=5)
    screen_e = ttk.Entry(frame, width=30)
    screen_e.grid(row=5, column=1, pady=5)
    fields['screen'] = screen_e

    tk.Label(frame, text=_t("cinema.labels.witnesses"), bg="#ffffff", fg="#333333").grid(row=6, column=0, sticky="w", pady=5)
    wit_e = ttk.Entry(frame, width=30)
    wit_e.grid(row=6, column=1, pady=5)
    fields['witnesses'] = wit_e

    tk.Label(frame, text="Immediate Action:", bg="#ffffff", fg="#333333").grid(row=7, column=0, sticky="nw", pady=5)
    action_text = tk.Text(frame, height=3, width=25, bg="#0f3460", fg="white")
    action_text.grid(row=7, column=1, pady=5)
    fields['action'] = action_text

    tk.Label(frame, text=_t("cinema.labels.customer_involved"), bg="#ffffff", fg="#333333").grid(row=8, column=0, sticky="w", pady=5)
    cust_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, variable=cust_var).grid(row=8, column=1, sticky="w", pady=5)
    fields['cust_var'] = cust_var

    tk.Label(frame, text=_t("cinema.labels.customer_name"), bg="#ffffff", fg="#333333").grid(row=9, column=0, sticky="w", pady=5)
    cust_name_e = ttk.Entry(frame, width=30)
    cust_name_e.grid(row=9, column=1, pady=5)
    fields['cust_name'] = cust_name_e

    tk.Label(frame, text=_t("cinema.labels.customer_contact"), bg="#ffffff", fg="#333333").grid(row=10, column=0, sticky="w", pady=5)
    cust_contact_e = ttk.Entry(frame, width=30)
    cust_contact_e.grid(row=10, column=1, pady=5)
    fields['cust_contact'] = cust_contact_e

    def save():
        desc = fields['desc'].get("1.0", tk.END).strip()
        if not desc:
            messagebox.showwarning(_t("cinema.common.warning"), "Description is required")
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
                INSERT INTO incidents (incident_type, severity, description, location, screen_number,
                                       incident_datetime, witnesses, immediate_action_taken,
                                       customer_involved, customer_name, customer_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fields['type_var'].get(), fields['sev_var'].get(), desc, fields['location'].get(),
                  screen, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fields['witnesses'].get(),
                  fields['action'].get("1.0", tk.END).strip(), 1 if fields['cust_var'].get() else 0,
                  fields['cust_name'].get(), fields['cust_contact'].get()))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Incident reported!")
        form.destroy()
        self.show_incidents_page()

    ttk.Button(frame, text=_t("cinema.incidents.report"), style="Danger.TButton", command=save).grid(row=11, column=0, columnspan=2, pady=20)

def view_incident_details(self):
    """View details of selected incident."""
    selected = self.incident_tree.selection() if hasattr(self, 'incident_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select an incident")
        return

    incident_id = self.incident_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        incident = cursor.fetchone()
    finally:
        conn.close()

    if not incident:
        messagebox.showerror(_t("cinema.common.error"), "Incident not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Incident Details")
    form.geometry("500x550")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    severity_colors = {"critical": "#dc3545", "high": "#f4a261", "medium": "#ffc107", "low": "#4ecca3"}
    sev_color = severity_colors.get(incident[2], "#aaaaaa")

    tk.Label(frame, text=f"Incident #{incident[0]}", font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)
    tk.Label(frame, text=f"Severity: {incident[2].upper()}", bg="#ffffff", fg=sev_color, font=("Helvetica", 11, "bold")).pack()

    # Create scrollable text area for details
    details_frame = ttk.Frame(frame, style="Card.TFrame")
    details_frame.pack(fill="both", expand=True, pady=10)

    text_widget = tk.Text(details_frame, bg="#0f3460", fg="white", wrap="word", height=20)
    text_widget.pack(fill="both", expand=True)

    details_text = f"""
Type: {incident[1]}
Date/Time: {incident[6]}
Location: {incident[4] or 'N/A'}
Screen: {incident[5] or 'N/A'}

DESCRIPTION:
{incident[3]}

WITNESSES:
{incident[8] or 'None listed'}

IMMEDIATE ACTION TAKEN:
{incident[9] or 'None recorded'}

STATUS: {incident[19].upper()}
"""

    if incident[10]:  # resolution
        details_text += f"""
RESOLUTION:
{incident[10]}

Resolved By: Staff #{incident[11] or 'N/A'}
Resolved At: {incident[12] or 'N/A'}
"""

    if incident[13]:  # customer involved
        details_text += f"""
CUSTOMER INVOLVED: Yes
Customer Name: {incident[14] or 'N/A'}
Customer Contact: {incident[15] or 'N/A'}
"""

    if incident[16]:  # follow up required
        details_text += f"""
FOLLOW-UP REQUIRED: Yes
Follow-up Notes: {incident[17] or 'N/A'}
Follow-up Completed: {'Yes' if incident[18] else 'No'}
"""

    text_widget.insert("1.0", details_text)
    text_widget.configure(state="disabled")

def update_incident(self):
    """Update or resolve an incident."""
    selected = self.incident_tree.selection() if hasattr(self, 'incident_tree') else None
    if not selected:
        messagebox.showwarning(_t("cinema.common.warning"), "Please select an incident")
        return

    incident_id = self.incident_tree.item(selected[0])['values'][0]

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        incident = cursor.fetchone()
    finally:
        conn.close()

    if not incident:
        messagebox.showerror(_t("cinema.common.error"), "Incident not found")
        return

    form = tk.Toplevel(self.root)
    form.title("Update Incident")
    form.geometry("450x450")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.btn.update_incident"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)
    tk.Label(frame, text=f"Incident #{incident_id}: {incident[1]}", bg="#ffffff", fg="#333333").pack()

    tk.Label(frame, text=_t("cinema.labels.resolution"), bg="#ffffff", fg="#333333").pack(anchor="w", pady=(15, 0))
    resolution_text = tk.Text(frame, height=5, width=40, bg="#0f3460", fg="white")
    resolution_text.pack(pady=5)
    if incident[10]:
        resolution_text.insert("1.0", incident[10])

    tk.Label(frame, text=_t("cinema.screenings.status_label"), bg="#ffffff", fg="#333333").pack(anchor="w")
    status_var = tk.StringVar(value=incident[19] or "open")
    statuses = ["open", "in_progress", "resolved", "closed"]
    status_combo = ttk.Combobox(frame, textvariable=status_var, values=statuses, width=25)
    status_combo.pack(pady=5)

    follow_up_var = tk.BooleanVar(value=bool(incident[16]))
    ttk.Checkbutton(frame, text=_t("cinema.labels.followup_required"), variable=follow_up_var).pack(anchor="w", pady=10)

    tk.Label(frame, text=_t("cinema.labels.followup_notes"), bg="#ffffff", fg="#333333").pack(anchor="w")
    follow_notes_e = ttk.Entry(frame, width=40)
    follow_notes_e.pack(pady=5)
    if incident[17]:
        follow_notes_e.insert(0, incident[17])

    def save():
        resolved_datetime = None
        if status_var.get() in ['resolved', 'closed'] and incident[19] not in ['resolved', 'closed']:
            resolved_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE incidents SET resolution = ?, status = ?, resolved_datetime = ?,
                                     follow_up_required = ?, follow_up_notes = ?
                WHERE id = ?
            ''', (resolution_text.get("1.0", tk.END).strip(), status_var.get(), resolved_datetime,
                  1 if follow_up_var.get() else 0, follow_notes_e.get(), incident_id))
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(_t("cinema.common.success"), "Incident updated!")
        form.destroy()
        self.show_incidents_page()

    ttk.Button(frame, text=_t("cinema.buttons.save_changes"), style="Success.TButton", command=save).pack(pady=20)

def show_incident_stats(self):
    """Show incident statistics."""
    form = tk.Toplevel(self.root)
    form.title("Incident Statistics")
    form.geometry("600x500")
    form.configure(bg="#ecf0f1")
    form.transient(self.root)
    form.grab_set()

    frame = ttk.Frame(form, style="Card.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(frame, text=_t("cinema.incidents.statistics"), font=("Helvetica", 14, "bold"), bg="#ffffff", fg="#e74c3c").pack(pady=10)

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()

        # By type
        type_frame = ttk.Frame(frame, style="Card.TFrame")
        type_frame.pack(fill="x", pady=10)
        tk.Label(type_frame, text=_t("cinema.analytics.by_type"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#27ae60").pack(anchor="w")

        cursor.execute('''
            SELECT incident_type, COUNT(*) FROM incidents
            WHERE incident_datetime >= date('now', '-30 days')
            GROUP BY incident_type ORDER BY COUNT(*) DESC
        ''')
        for itype, count in cursor.fetchall():
            tk.Label(type_frame, text=f"  {itype}: {count}", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

        # By severity
        sev_frame = ttk.Frame(frame, style="Card.TFrame")
        sev_frame.pack(fill="x", pady=10)
        tk.Label(sev_frame, text=_t("cinema.analytics.by_severity"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#27ae60").pack(anchor="w")

        cursor.execute('''
            SELECT severity, COUNT(*) FROM incidents
            WHERE incident_datetime >= date('now', '-30 days')
            GROUP BY severity ORDER BY
            CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
        ''')
        severity_colors = {"critical": "#dc3545", "high": "#f4a261", "medium": "#ffc107", "low": "#4ecca3"}
        for sev, count in cursor.fetchall():
            color = severity_colors.get(sev, "#aaaaaa")
            tk.Label(sev_frame, text=f"  {sev.upper()}: {count}", bg="#ffffff", fg=color).pack(anchor="w")

        # Resolution stats
        res_frame = ttk.Frame(frame, style="Card.TFrame")
        res_frame.pack(fill="x", pady=10)
        tk.Label(res_frame, text=_t("cinema.labels.resolution_stats"), font=("Helvetica", 11, "bold"), bg="#ffffff", fg="#27ae60").pack(anchor="w")

        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'open'")
        open_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'resolved'")
        resolved_count = cursor.fetchone()[0]
        cursor.execute('''
            SELECT AVG(julianday(resolved_datetime) - julianday(incident_datetime)) * 24
            FROM incidents WHERE resolved_datetime IS NOT NULL
        ''')
        avg_resolution = cursor.fetchone()[0] or 0

        tk.Label(res_frame, text=f"  Open: {open_count}", bg="#ffffff", fg="#ffc107").pack(anchor="w")
        tk.Label(res_frame, text=f"  Resolved: {resolved_count}", bg="#ffffff", fg="#27ae60").pack(anchor="w")
        tk.Label(res_frame, text=f"  Avg Resolution Time: {avg_resolution:.1f} hours", bg="#ffffff", fg="#7f8c8d").pack(anchor="w")

    finally:
        conn.close()

def export_incident_report(self):
    """Export incidents to CSV."""
    filepath = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv")],
        initialfile=f"incidents_{datetime.now().strftime('%Y%m%d')}.csv"
    )
    if not filepath:
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, incident_datetime, incident_type, severity, location, description, status, resolution
            FROM incidents ORDER BY incident_datetime DESC
        ''')
        incidents = cursor.fetchall()
    finally:
        conn.close()

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Date/Time', 'Type', 'Severity', 'Location', 'Description', 'Status', 'Resolution'])
        writer.writerows(incidents)

    messagebox.showinfo(_t("cinema.common.success"), f"Report exported to {filepath}")
