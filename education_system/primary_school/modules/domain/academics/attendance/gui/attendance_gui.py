"""Attendance management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from education_system.primary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService
from education_system.primary_school.infrastructure.database.constants import ATTENDANCE_STATUSES
import traceback


class _MarkRegisterDialog(tk.Toplevel):
    """Dialog for marking a whole-class register."""

    def __init__(self, parent, db_path, service, class_name, register_date, session):
        super().__init__(parent)
        self.result = None
        self._service = service
        self.title(f"Mark Register - {class_name} ({session}) {register_date}")
        self.geometry("600x500")
        self.resizable(True, True)
        self.grab_set()

        self._rows = []

        # Header
        hdr = tk.Frame(self, bg="#1a5276", height=35)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"{class_name} | {register_date} | {session}",
                 fg="white", bg="#1a5276", font=("Helvetica", 11, "bold")).pack(side="left", padx=10)

        # Scrollable pupil list
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Column headers
        row_hdr = tk.Frame(scroll_frame)
        row_hdr.pack(fill="x", padx=5, pady=2)
        tk.Label(row_hdr, text="Pupil ID", width=10, anchor="w", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(row_hdr, text="Name", width=25, anchor="w", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(row_hdr, text="Status", width=15, anchor="w", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(row_hdr, text="Note", width=20, anchor="w", font=("Helvetica", 10, "bold")).pack(side="left")

        try:
            pupils = self._service.get_class_register(class_name, register_date)
        except Exception:
            traceback.print_exc()
            pupils = []

        for pupil in pupils:
            row = tk.Frame(scroll_frame)
            row.pack(fill="x", padx=5, pady=1)

            pid = pupil.get("pupil_id", "")
            name = f"{pupil.get('first_name', '')} {pupil.get('last_name', '')}".strip()

            tk.Label(row, text=str(pid), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=name, width=25, anchor="w").pack(side="left")

            status_var = tk.StringVar(value="Present")
            status_combo = ttk.Combobox(row, textvariable=status_var,
                                         values=ATTENDANCE_STATUSES, state="readonly", width=15)
            status_combo.pack(side="left", padx=2)

            note_entry = tk.Entry(row, width=20)
            note_entry.pack(side="left", padx=2)

            self._rows.append({
                "pupil_id": pid,
                "pupil_name": name,
                "status_var": status_var,
                "note_entry": note_entry,
            })

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=8, padx=10)
        tk.Button(btn_frame, text="Mark All Present",
                  command=lambda: self._set_all("Present")).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Save Register", command=self._save, width=14).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=10).pack(side="right", padx=5)

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _set_all(self, status):
        for row in self._rows:
            row["status_var"].set(status)

    def _save(self):
        records = []
        for row in self._rows:
            records.append({
                "pupil_id": row["pupil_id"],
                "status": row["status_var"].get(),
                "note": row["note_entry"].get().strip(),
            })
        self.result = records
        self.destroy()


class _AttendanceDialog(tk.Toplevel):
    """Add / Edit individual attendance record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Attendance" if record else "Add Attendance")
        self.geometry("450x350")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "pupil_id", "Pupil ID *")
        self._add_field(frm, "date", "Date * (YYYY-MM-DD)", default=str(date.today()))
        self._add_combo(frm, "session", "Session *", ["AM", "PM"])
        self._add_combo(frm, "status", "Status *", ATTENDANCE_STATUSES)
        self._add_field(frm, "note", "Note")
        self._add_field(frm, "class_name", "Class Name")

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, tk.BooleanVar):
                    widget.set(bool(val))
                elif isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label, default=""):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _add_check(self, parent, key, label, default=False):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(frm, text=label, variable=var).pack(anchor="w")
        self._entries[key] = var

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, tk.BooleanVar):
                data[key] = int(widget.get())
            elif isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("date"):
            messagebox.showwarning("Validation", "Date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class AttendanceFrame(tk.Frame):
    """Main attendance management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = AttendanceService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Attendance Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Mark Register", command=self._on_mark_register).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Class:", bg="#d5dbdb").pack(side="left")
        self._class_filter = ttk.Combobox(toolbar, values=["All"], state="readonly", width=12)
        self._class_filter.set("All")
        self._class_filter.pack(side="left", padx=3)
        self._class_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Date:", bg="#d5dbdb").pack(side="left", padx=(5, 0))
        self._date_var = tk.StringVar(value=str(date.today()))
        date_entry = tk.Entry(toolbar, textvariable=self._date_var, width=12)
        date_entry.pack(side="left", padx=3)

        tk.Label(toolbar, text="Session:", bg="#d5dbdb").pack(side="left", padx=(5, 0))
        self._session_filter = ttk.Combobox(toolbar, values=["All", "AM", "PM"],
                                             state="readonly", width=6)
        self._session_filter.set("All")
        self._session_filter.pack(side="left", padx=3)
        self._session_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left", padx=3)
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("pupil_id", "pupil_name", "date", "session", "status", "note")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        class_name = self._class_filter.get()
        class_name = None if class_name == "All" else class_name
        register_date = self._date_var.get().strip() or None
        session = self._session_filter.get()
        session = None if session == "All" else session
        try:
            records = self._service.get_attendance(
                class_name=class_name, date=register_date, session=session
            )
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("attendance_id", ""), values=(
                    r.get("pupil_id", ""),
                    r.get("pupil_name", ""),
                    r.get("date", ""),
                    r.get("session", ""),
                    r.get("status", ""),
                    r.get("note", ""),
                ))
            self._status_var.set(f"{len(records)} record(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load attendance: {e}")

    def _clear_search(self):
        self._class_filter.set("All")
        self._date_var.set(str(date.today()))
        self._session_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _AttendanceDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.record_attendance(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        aid = self._selected_id()
        if not aid:
            return
        results = self._service.get_attendance()
        record = next((r for r in results if str(r.get("id")) == str(aid)), None)
        if not record:
            messagebox.showerror("Error", "Attendance record not found.")
            return
        dlg = _AttendanceDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_attendance(aid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        aid = self._selected_id()
        if not aid:
            return
        if not messagebox.askyesno("Confirm", f"Delete attendance record {aid}?"):
            return
        try:
            # Note: attendance service does not support delete
            messagebox.showwarning("Not Supported", "Deleting attendance records is not supported.")
            return
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_mark_register(self):
        class_name = self._class_filter.get()
        if class_name == "All":
            messagebox.showwarning("Selection", "Please select a class before marking register.")
            return
        register_date = self._date_var.get().strip() or str(date.today())
        session = self._session_filter.get()
        if session == "All":
            session = "AM"
        dlg = _MarkRegisterDialog(self, self._db_path, self._service,
                                   class_name, register_date, session)
        self.wait_window(dlg)
        if dlg.result:
            try:
                for rec in dlg.result:
                    self._service.record_attendance(
                        pupil_id=rec["pupil_id"],
                        date=register_date,
                        session=session,
                        status=rec["status"],
                        note=rec["note"],
                    )
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))
