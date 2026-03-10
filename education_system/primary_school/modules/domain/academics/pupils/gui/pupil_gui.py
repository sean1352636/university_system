"""Pupil management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.pupils.services.pupil_service import PupilService
from education_system.primary_school.core.defaults import YEAR_GROUPS
from education_system.primary_school.infrastructure.database.constants import SEND_STATUSES
import traceback


class _PupilDialog(tk.Toplevel):
    """Add / Edit pupil dialog."""

    def __init__(self, parent, db_path, pupil=None):
        super().__init__(parent)
        self.result = None
        self._pupil = pupil
        self.title("Edit Pupil" if pupil else "Add Pupil")
        self.geometry("520x620")
        self.resizable(False, False)
        self.grab_set()

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._entries = {}

        # ── Pupil details ──────────────────────────────────────────
        self._section(scroll_frame, "Pupil Details")
        self._add_field(scroll_frame, "first_name", "First Name *")
        self._add_field(scroll_frame, "last_name", "Last Name *")
        self._add_field(scroll_frame, "preferred_name", "Preferred Name")
        self._add_field(scroll_frame, "date_of_birth", "Date of Birth (YYYY-MM-DD)")
        self._add_combo(scroll_frame, "gender", "Gender", ["", "Male", "Female", "Other"])
        self._add_combo(scroll_frame, "year_group", "Year Group *", YEAR_GROUPS)
        self._add_field(scroll_frame, "class_name", "Class")
        self._add_field(scroll_frame, "ethnicity", "Ethnicity")
        self._add_field(scroll_frame, "first_language", "First Language", default="English")
        self._add_check(scroll_frame, "eal", "English as Additional Language")
        self._add_check(scroll_frame, "pupil_premium", "Pupil Premium")
        self._add_check(scroll_frame, "free_school_meals", "Free School Meals")
        self._add_combo(scroll_frame, "sen_status", "SEN Status", SEND_STATUSES)
        self._add_check(scroll_frame, "looked_after", "Looked After Child")

        # ── Parent / guardian ──────────────────────────────────────
        self._section(scroll_frame, "Parent / Guardian 1")
        self._add_field(scroll_frame, "parent1_name", "Name")
        self._add_field(scroll_frame, "parent1_email", "Email")
        self._add_field(scroll_frame, "parent1_phone", "Phone")

        self._section(scroll_frame, "Parent / Guardian 2")
        self._add_field(scroll_frame, "parent2_name", "Name")
        self._add_field(scroll_frame, "parent2_email", "Email")
        self._add_field(scroll_frame, "parent2_phone", "Phone")

        # ── Emergency contact ──────────────────────────────────────
        self._section(scroll_frame, "Emergency Contact")
        self._add_field(scroll_frame, "emergency_contact_name", "Name")
        self._add_field(scroll_frame, "emergency_contact_phone", "Phone")

        # ── Additional ─────────────────────────────────────────────
        self._section(scroll_frame, "Additional Information")
        self._add_field(scroll_frame, "address", "Address")
        self._add_field(scroll_frame, "medical_notes", "Medical Notes")
        self._add_field(scroll_frame, "dietary_requirements", "Dietary Requirements")
        self._add_check(scroll_frame, "photo_consent", "Photo Consent", default=True)

        if pupil and "status" in pupil:
            self._add_combo(scroll_frame, "status", "Status", ["Active", "Left", "Transferred", "Excluded"])

        # ── Buttons ────────────────────────────────────────────────
        btn_frame = tk.Frame(scroll_frame)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if pupil:
            for key, widget in self._entries.items():
                val = pupil.get(key)
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

    def _section(self, parent, title):
        lbl = tk.Label(parent, text=title, font=("Helvetica", 11, "bold"), anchor="w")
        lbl.pack(fill="x", padx=10, pady=(10, 2))
        ttk.Separator(parent).pack(fill="x", padx=10)

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
        if not data.get("first_name"):
            messagebox.showwarning("Validation", "First name is required.", parent=self)
            return
        if not data.get("last_name"):
            messagebox.showwarning("Validation", "Last name is required.", parent=self)
            return
        if not data.get("year_group"):
            messagebox.showwarning("Validation", "Year group is required.", parent=self)
            return
        self.result = data
        self.destroy()


class PupilFrame(tk.Frame):
    """Main pupil management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = PupilService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Pupil Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Pupil", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Year Group:", bg="#d5dbdb").pack(side="left")
        self._year_filter = ttk.Combobox(toolbar, values=["All"] + YEAR_GROUPS,
                                          state="readonly", width=12)
        self._year_filter.set("All")
        self._year_filter.pack(side="left", padx=3)
        self._year_filter.bind("<<ComboboxSelected>>", lambda e: self._load_pupils())

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=18)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_pupils).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("pupil_id", "first_name", "last_name", "year_group",
                    "class_name", "key_stage", "sen_status", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=100)
        self._tree.column("pupil_id", width=80)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_pupils()

    def refresh(self):
        self._load_pupils()

    def _load_pupils(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        yg = self._year_filter.get()
        year_group = None if yg == "All" else yg
        search = self._search_var.get().strip() or None
        try:
            pupils = self._service.list_pupils(year_group=year_group, search=search)
            for p in pupils:
                self._tree.insert("", tk.END, iid=p["pupil_id"], values=(
                    p["pupil_id"], p["first_name"], p["last_name"],
                    p["year_group"], p.get("class_name", ""),
                    p.get("key_stage", ""), p.get("sen_status", ""), p.get("status", ""),
                ))
            self._status_var.set(f"{len(pupils)} pupil(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load pupils: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._year_filter.set("All")
        self._load_pupils()

    def _selected_pupil_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a pupil first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _PupilDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_pupil(**dlg.result)
                self._load_pupils()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        pid = self._selected_pupil_id()
        if not pid:
            return
        pupil = self._service.get_pupil(pid)
        if not pupil:
            messagebox.showerror("Error", "Pupil not found.")
            return
        dlg = _PupilDialog(self, self._db_path, pupil=pupil)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_pupil(pid, **dlg.result)
                self._load_pupils()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        pid = self._selected_pupil_id()
        if not pid:
            return
        if not messagebox.askyesno("Confirm", f"Delete pupil {pid} and all related records?"):
            return
        try:
            self._service.delete_pupil(pid)
            self._load_pupils()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
