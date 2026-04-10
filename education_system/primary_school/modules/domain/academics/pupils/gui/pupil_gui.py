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

        # Admin/staff: double-click a row to view full pupil details
        self._tree.bind("<Double-1>", self._on_double_click_pupil)

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

    # ------------------------------------------------------------------
    # Details viewer (admin/staff double-click)
    # ------------------------------------------------------------------

    def _user_role(self) -> str:
        """Return the current user's role (or empty string if not logged in)."""
        if self._auth and getattr(self._auth, "current_user", None):
            return self._auth.current_user.get("role", "")
        return ""

    def _on_double_click_pupil(self, _event=None):
        """Open the pupil details window — only for admin/staff users."""
        if self._user_role() not in ("admin", "staff", "instructor", "teacher"):
            return
        sel = self._tree.selection()
        if not sel:
            return
        self._show_pupil_details(sel[0])

    def _show_pupil_details(self, pupil_id: str):
        """Display a read-only details window for the given pupil ID."""
        pupil = self._service.get_pupil(pupil_id)
        if not pupil:
            messagebox.showerror("Error", "Pupil not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Pupil Details — {pupil.get('pupil_id', '')}")
        win.geometry("720x640")
        win.transient(self.winfo_toplevel())

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Personal tab
        personal_tab = ttk.Frame(notebook)
        notebook.add(personal_tab, text="Personal")

        personal_text = tk.Text(personal_tab, wrap="word", font=("Courier", 10),
                                padx=15, pady=15, bd=0)
        personal_text.pack(fill="both", expand=True)

        na = "—"
        full_name = " ".join(
            p for p in (pupil.get("first_name"), pupil.get("last_name")) if p
        ) or na
        yes_no = lambda v: "Yes" if v else "No"

        personal_lines = [
            "PUPIL RECORD",
            "=" * 60,
            "",
            "Personal Information",
            f"  Pupil ID:        {pupil.get('pupil_id') or na}",
            f"  First name:      {pupil.get('first_name') or na}",
            f"  Last name:       {pupil.get('last_name') or na}",
            f"  Preferred name:  {pupil.get('preferred_name') or na}",
            f"  Full name:       {full_name}",
            f"  Date of birth:   {pupil.get('date_of_birth') or na}",
            f"  Gender:          {pupil.get('gender') or na}",
            f"  Ethnicity:       {pupil.get('ethnicity') or na}",
            f"  First language:  {pupil.get('first_language') or na}",
            "",
            "School Details",
            f"  Year group:      {pupil.get('year_group') or na}",
            f"  Class:           {pupil.get('class_name') or na}",
            f"  Key stage:       {pupil.get('key_stage') or na}",
            f"  SEN status:      {pupil.get('sen_status') or na}",
            f"  EAL:             {yes_no(pupil.get('eal'))}",
            f"  Pupil Premium:   {yes_no(pupil.get('pupil_premium'))}",
            f"  Free Sch. Meals: {yes_no(pupil.get('free_school_meals'))}",
            f"  Looked after:    {yes_no(pupil.get('looked_after'))}",
            f"  Photo consent:   {yes_no(pupil.get('photo_consent'))}",
            f"  Status:          {pupil.get('status') or na}",
            "",
            "Address & Notes",
            f"  Address:         {pupil.get('address') or na}",
            f"  Medical notes:   {pupil.get('medical_notes') or na}",
            f"  Dietary req:     {pupil.get('dietary_requirements') or na}",
            "",
            "Record",
            f"  Created:         {pupil.get('created_at') or na}",
            f"  Updated:         {pupil.get('updated_at') or na}",
        ]
        personal_text.insert("end", "\n".join(personal_lines))
        personal_text.config(state="disabled")

        # Parents/guardians tab
        contacts_tab = ttk.Frame(notebook)
        notebook.add(contacts_tab, text="Contacts")
        contacts_text = tk.Text(contacts_tab, wrap="word", font=("Courier", 10),
                                padx=15, pady=15, bd=0)
        contacts_text.pack(fill="both", expand=True)
        contacts_lines = [
            "Parent / Guardian 1",
            f"  Name:   {pupil.get('parent1_name') or na}",
            f"  Email:  {pupil.get('parent1_email') or na}",
            f"  Phone:  {pupil.get('parent1_phone') or na}",
            "",
            "Parent / Guardian 2",
            f"  Name:   {pupil.get('parent2_name') or na}",
            f"  Email:  {pupil.get('parent2_email') or na}",
            f"  Phone:  {pupil.get('parent2_phone') or na}",
            "",
            "Emergency Contact",
            f"  Name:   {pupil.get('emergency_contact_name') or na}",
            f"  Phone:  {pupil.get('emergency_contact_phone') or na}",
        ]
        contacts_text.insert("end", "\n".join(contacts_lines))
        contacts_text.config(state="disabled")

        # Footer
        footer = tk.Frame(win, pady=8)
        footer.pack(fill="x")
        if self._user_role() == "admin":
            ttk.Button(
                footer, text="Edit",
                command=lambda: (win.destroy(), self._tree.selection_set(pupil_id),
                                 self._on_edit()),
            ).pack(side="left", padx=10)
        ttk.Button(footer, text="Close", command=win.destroy).pack(side="right", padx=10)
