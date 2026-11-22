
from education_system.systems.university.infrastructure.i18n import get_text as _t
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, tf, run_async, show_error, list_trip_staff,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.export_dialog'


def _section(rows, title, header, sections):
    sections.append((title, header, rows))


def gather_export(auth, *, trips_on, participants_on, expenses_on, staff_on, medical_on):
    """Collect the export through the trip domain. Runs on a worker thread.

    Returns ``(sections, failures)``: ``sections`` is ``[(title, header,
    rows)]`` and ``failures`` the plain-language reasons a section (or a
    trip within it) could not be exported. Participant rows never carry
    health details — only per-trip counts; the medical sheet is a separate,
    audited section (``medical.participant_health``) for the trips the user
    may see.
    """
    sections, failures = [], []
    trips_mod, regs, medical = tm('trips'), tm('registrations'), tm('medical')
    try:
        trips = trips_mod.list_trips(include_archived=True)
    except Exception as exc:
        return sections, [f"Trips: {exc}"]

    if trips_on:
        _section([[t['id'], t['trip_name'], t.get('description'), t.get('destination'), t['start_date'],
                   t.get('end_date'), t.get('max_participants'), t.get('current_participants'), t.get('cost'),
                   t.get('status'), t.get('trip_type'), t.get('country'), t.get('created_at'),
                   t.get('updated_at'), t.get('updated_by')] for t in trips],
                 '=== TRIPS DATA ===',
                 ['Trip ID', 'Name', 'Description', 'Destination', 'Start Date', 'End Date',
                  'Max Participants', 'Places Taken', 'Cost', 'Status', 'Type', 'Country',
                  'Created At', 'Updated At', 'Updated By'], sections)

    if participants_on:
        rows, counts = [], []
        for t in trips:
            try:
                people = regs.list_participants(auth, t['id'], include_ended=True)
            except PermissionError:
                failures.append(f"Participants of '{t['trip_name']}': not permitted")
                continue
            except Exception as exc:
                failures.append(f"Participants of '{t['trip_name']}': {exc}")
                continue
            for p in people:
                rows.append([p['id'], t['trip_name'], p.get('student_id'), p.get('name'), p.get('email'),
                             p.get('registration_date'), p.get('payment_status'), p.get('status'),
                             p.get('amount_paid'), p.get('amount_refunded'), p.get('waitlist_position'),
                             p.get('emergency_contact')])
            try:
                c = medical.counts(t['id'])
                counts.append([t['id'], t['trip_name'], c['medical_info'], c['dietary_requirements'],
                               c['accessibility_needs']])
            except Exception as exc:
                failures.append(f"Health counts for '{t['trip_name']}': {exc}")
        _section(rows, '=== PARTICIPANTS DATA ===',
                 ['Participant ID', 'Trip Name', 'Student ID', 'Name', 'Email', 'Registration Date',
                  'Payment Status', 'Status', 'Amount Paid', 'Amount Refunded', 'Waitlist Position',
                  'Emergency Contact'], sections)
        _section(counts, '=== HEALTH DETAILS RECORDED (COUNTS ONLY) ===',
                 ['Trip ID', 'Trip Name', 'Medical', 'Dietary', 'Accessibility'], sections)

    if expenses_on:
        rows = []
        for t in trips:
            try:
                for e in tm('expenses').list_expenses(auth, t['id']):
                    rows.append([e['id'], t['trip_name'], e['category'], e['description'], e['amount'],
                                 e['date'], e.get('recorded_by')])
            except PermissionError:
                failures.append(f"Expenses of '{t['trip_name']}': not permitted")
            except Exception as exc:
                failures.append(f"Expenses of '{t['trip_name']}': {exc}")
        _section(rows, '=== EXPENSES DATA ===',
                 ['Expense ID', 'Trip Name', 'Category', 'Description', 'Amount', 'Date', 'Recorded By'],
                 sections)

    if staff_on:
        rows = []
        for t in trips:
            try:
                for s in list_trip_staff(t['id']):
                    rows.append([s['id'], t['trip_name'], s['name'], s['role'], s.get('assigned_date'),
                                 'yes' if s.get('first_aider') else 'no', s.get('dbs_status') or ''])
            except Exception as exc:
                failures.append(f"Staff of '{t['trip_name']}': {exc}")
        _section(rows, '=== STAFF ASSIGNMENTS DATA ===',
                 ['Assignment ID', 'Trip Name', 'Staff Name', 'Role', 'Assigned Date', 'First Aider', 'DBS'],
                 sections)

    if medical_on:
        rows = []
        for t in trips:
            if t.get('status') == 'archived':
                continue
            try:
                if not medical.may_view_medical(auth, t['id']):
                    continue
                for p in medical.participant_health(auth, t['id']):
                    rows.append([t['trip_name'], p['name'], p.get('student_id'), p.get('status'),
                                 p.get('medical_info'), p.get('dietary_requirements'),
                                 p.get('accessibility_needs'), p.get('emergency_contact')])
            except Exception as exc:
                failures.append(f"Medical sheet for '{t['trip_name']}': {exc}")
        _section(rows, '=== MEDICAL & DIETARY SHEET (RESTRICTED - SPECIAL CATEGORY DATA) ===',
                 ['Trip Name', 'Name', 'Student ID', 'Status', 'Medical', 'Dietary', 'Accessibility',
                  'Emergency Contact'], sections)
    return sections, failures


class ExportDataDialog(Dialog):
    def __init__(self, parent, auth):
        self.auth = auth
        super().__init__(parent, _t(f"{_K}.windows.export", default="Export Trip Data"))

    def body(self, master):
        ttk.Label(master, text=_t(f"{_K}.labels.select_data_to_export", default="Select data to export:"), font=('Arial', 10, 'bold')).pack(pady=(0, 10))
        self.export_trips_var = tk.BooleanVar(value=True)
        self.export_participants_var = tk.BooleanVar(value=True)
        self.export_expenses_var = tk.BooleanVar()
        self.export_staff_var = tk.BooleanVar()
        self.export_medical_var = tk.BooleanVar()

        ttk.Checkbutton(master, text=_t(f"{_K}.buttons.trip_information", default="Trip Information"), variable=self.export_trips_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(master, text=_t(f"{_K}.buttons.participant_data", default="Participant Data"), variable=self.export_participants_var).pack(anchor=tk.W, pady=2)
        if self.auth.check_permission('view_financial_reports') or self.auth.check_permission('manage_trip_expenses'):
            ttk.Checkbutton(master, text=_t(f"{_K}.buttons.expense_data", default="Expense Data"), variable=self.export_expenses_var).pack(anchor=tk.W, pady=2)
        if self.auth.check_permission('manage_trips'):
            ttk.Checkbutton(master, text=_t(f"{_K}.buttons.staff_assignments", default="Staff Assignments"), variable=self.export_staff_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(master, text=_t(f"{_K}.buttons.medical_sheet", default="Medical & dietary sheet (restricted, audited)"),
                        variable=self.export_medical_var).pack(anchor=tk.W, pady=2)
        ttk.Label(master, text=_t(f"{_K}.labels.health_note",
                                  default="Participant data includes only counts of health details. The medical sheet "
                                          "is exported only for trips you lead or as the health team, and every read is audited."),
                  foreground="gray", wraplength=380, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))

        ttk.Label(master, text=_t(f"{_K}.labels.export_format", default="Export format:"), font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(20, 5))
        self.format_var = tk.StringVar(value="CSV")
        ttk.Radiobutton(master, text=_t(f"{_K}.buttons.csv_comma_separated_values", default="CSV (Comma Separated Values)"), variable=self.format_var, value="CSV").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(master, text=_t(f"{_K}.buttons.tsv_tab_separated_values", default="TSV (Tab Separated Values)"), variable=self.format_var, value="TSV").pack(anchor=tk.W, pady=2)
        return None

    def validate(self):
        if not any(v.get() for v in (self.export_trips_var, self.export_participants_var,
                                     self.export_expenses_var, self.export_staff_var,
                                     self.export_medical_var)):
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.please_select_at_least_one_data_type_to_export", default="Please select at least one data type to export."), parent=self)
            return False
        if self.export_medical_var.get() and not messagebox.askyesno(
                _t(f"{_K}.dialogs.medical_warning_title", default="Special-category data"),
                _t(f"{_K}.dialogs.medical_warning",
                   default="The medical & dietary sheet contains special-category health data.\n\n"
                           "Your access will be recorded in the audit log. Keep the file secure, share it "
                           "only with people who need it for the trip, and delete it after the trip.\n\n"
                           "Export it?"), icon=messagebox.WARNING, parent=self):
            return False
        return True

    def apply(self):
        extension = "csv" if self.format_var.get() == "CSV" else "tsv"
        delimiter = "," if extension == "csv" else "\t"
        filename = filedialog.asksaveasfilename(
            parent=self.parent, defaultextension=f".{extension}",
            filetypes=[(f"{self.format_var.get()} files", f"*.{extension}"), ("All files", "*.*")],
            initialfile=f"trip_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}")
        if not filename:
            return
        options = dict(trips_on=self.export_trips_var.get(),
                       participants_on=self.export_participants_var.get(),
                       expenses_on=self.export_expenses_var.get(),
                       staff_on=self.export_staff_var.get() and self.auth.check_permission('manage_trips'),
                       medical_on=self.export_medical_var.get())
        auth, parent = self.auth, self.parent

        def work():
            sections, failures = gather_export(auth, **options)
            with open(filename, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh, delimiter=delimiter)
                for title, header, rows in sections:
                    writer.writerow([title])
                    writer.writerow(header)
                    writer.writerows(rows)
                    writer.writerow([])
            return sections, failures

        def done(result):
            sections, failures = result
            if failures:
                messagebox.showwarning(
                    _t(f"{_K}.dialogs.partial", default="Export Incomplete"),
                    tf(f"{_K}.dialogs.partial_body",
                       "The file was written to:\n{path}\n\nbut these parts could not be exported:\n{items}",
                       path=filename, items="\n".join(f"• {f}" for f in failures[:25])
                       + (f"\n... and {len(failures) - 25} more" if len(failures) > 25 else "")),
                    parent=parent)
            else:
                messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"),
                                    f"Data exported successfully to:\n{filename}", parent=parent)

        run_async(parent, work, done,
                  lambda exc: show_error(parent, exc, _t(f"{_K}.dialogs.error", default="Error")))
