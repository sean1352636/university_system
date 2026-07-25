"""Clinical GUI panels for the Health Portal.

Self-contained Tkinter panels that close the GUI gaps for the clinical
tables that already have CLI coverage but no GUI: allergies, prescriptions,
lab results, care plans, medical conditions, referrals, screening schedules
and wellness participation.

Each panel is a standalone Frame-building class.  It builds its widgets into
a parent frame and talks to the *same* persistence the health CLI uses --
the shared ``student_records.db`` reached through
``infrastructure.database.db.get_connection`` and the same table shapes the
CLI writes (see ``domain/health/records/clinical`` etc.).  The interactive
CLI functions cannot be driven from a GUI (they read via ``input()``), so
the panels issue the identical SQL against the identical tables and reuse the
genuinely reusable, non-interactive service helpers:
``calculate_screening_due_date`` / ``calculate_next_screening_date`` (screening
date maths) and the module-level ``log_audit_event`` audit writer.

Constructor for every panel::

    Panel(parent, auth, get_connection=None)

* ``parent``          -- a ttk/tk container to build into.
* ``auth``            -- the auth/app context the other portal panels use
                         (needs ``current_user`` and ``check_permission``).
* ``get_connection``  -- optional zero-arg callable returning a DB
                         connection; defaults to the central
                         ``infrastructure.database.db.get_connection`` so the
                         panel hits the same DB as the CLI.  Tests inject a
                         connection factory pointed at a temp DB copy.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection as _central_get_connection,
)
from education_system.systems.university.domain.pastoral.health.records.db.audit import (
    log_audit_event,
)
from education_system.systems.university.domain.pastoral.health.records.screening.schedules import (
    calculate_screening_due_date,
    calculate_next_screening_date,
)


# --------------------------------------------------------------------------
# Shared base
# --------------------------------------------------------------------------
class _ClinicalPanelBase:
    """Common plumbing: form building, tree building, DB + audit helpers."""

    #: Overridden by subclasses.
    title = "Clinical"

    def __init__(self, parent, auth, get_connection=None):
        self.parent = parent
        self.auth = auth
        self._get_connection = get_connection or _central_get_connection
        self.vars = {}
        self.widgets = {}
        self.tree = None
        self.build()

    # -- infrastructure ----------------------------------------------------
    def _conn(self):
        return self._get_connection()

    def _user_id(self):
        try:
            return self.auth.current_user.get("id")
        except Exception:
            return None

    def _can(self, permission):
        try:
            return bool(self.auth.check_permission(permission))
        except Exception:
            return False

    def _audit(self, action, resource_type, resource_id, details=None):
        try:
            log_audit_event(self._user_id(), action, resource_type,
                            resource_id, details)
        except Exception:
            pass

    def _verify_student(self, cursor, student_id):
        cursor.execute(
            "SELECT COUNT(*) FROM students WHERE student_id = ?",
            (student_id,),
        )
        return cursor.fetchone()[0] > 0

    def _err(self, msg):
        messagebox.showerror("Error", msg)

    def _info(self, msg):
        messagebox.showinfo("Success", msg)

    # -- widget builders ---------------------------------------------------
    def _header(self):
        ttk.Label(self.parent, text=self.title,
                  font=("Arial", 16, "bold")).pack(anchor="w", padx=10, pady=(10, 6))

    def _build_form(self, container, fields):
        """Build a labelled form. ``fields`` is a list of dicts with keys:
        key, label, kind ('entry'|'combo'|'text'|'date'|'check'), values,
        default, width.  Returns nothing; vars are stored on ``self.vars``.
        """
        for row, spec in enumerate(fields):
            key = spec["key"]
            kind = spec.get("kind", "entry")
            ttk.Label(container, text=spec["label"]).grid(
                row=row, column=0, sticky=tk.W, pady=4, padx=(0, 8))
            if kind == "text":
                widget = tk.Text(container, width=spec.get("width", 46),
                                 height=spec.get("height", 3))
                widget.grid(row=row, column=1, sticky=tk.W, pady=4)
                self.widgets[key] = widget
                continue
            if kind == "check":
                var = tk.BooleanVar(value=spec.get("default", False))
                ttk.Checkbutton(container, variable=var).grid(
                    row=row, column=1, sticky=tk.W, pady=4)
                self.vars[key] = var
                continue

            var = tk.StringVar(value=spec.get("default", ""))
            if kind == "date" and not spec.get("default"):
                var.set(datetime.now().strftime("%Y-%m-%d"))
            if kind == "combo":
                values = spec.get("values", [])
                widget = ttk.Combobox(container, textvariable=var,
                                      values=values, width=spec.get("width", 28),
                                      state="readonly")
                if values and not var.get():
                    var.set(values[0])
            else:
                widget = ttk.Entry(container, textvariable=var,
                                   width=spec.get("width", 30))
            widget.grid(row=row, column=1, sticky=tk.W, pady=4)
            self.vars[key] = var
            self.widgets[key] = widget

    def _form_value(self, key):
        if key in self.vars:
            return self.vars[key].get()
        widget = self.widgets.get(key)
        if isinstance(widget, tk.Text):
            return widget.get("1.0", tk.END).strip()
        return ""

    def _make_tree(self, columns):
        """columns: list of (heading, width). Returns the Treeview."""
        frame = ttk.Frame(self.parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))
        headings = [c[0] for c in columns]
        tree = ttk.Treeview(frame, columns=headings, show="headings", height=12)
        for heading, width in columns:
            tree.heading(heading, text=heading)
            tree.column(heading, width=width, anchor=tk.W)
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = tree
        return tree

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _search_row(self, parent):
        """Standard 'Student ID' filter + Refresh row. Stores var on
        self.vars['_search_student']."""
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=10, pady=(6, 0))
        ttk.Label(bar, text="Filter by Student ID:").pack(side=tk.LEFT)
        var = tk.StringVar()
        self.vars["_search_student"] = var
        ttk.Entry(bar, textvariable=var, width=18).pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        return var

    # -- subclass hooks ----------------------------------------------------
    def build(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def refresh(self):  # pragma: no cover - overridden
        raise NotImplementedError


# --------------------------------------------------------------------------
# Allergies
# --------------------------------------------------------------------------
class AllergiesPanel(_ClinicalPanelBase):
    title = "Allergies"
    SEVERITY = ["Mild", "Moderate", "Severe", "Life-threatening"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Add Allergy", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "allergen", "label": "Allergen:"},
            {"key": "severity", "label": "Severity:", "kind": "combo",
             "values": self.SEVERITY},
            {"key": "reaction", "label": "Reaction:"},
            {"key": "diagnosed_date", "label": "Diagnosed (YYYY-MM-DD):",
             "kind": "date"},
            {"key": "provider", "label": "Provider:"},
            {"key": "verified", "label": "Verified:", "kind": "check"},
        ])
        ttk.Button(form, text="Add Allergy", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 100), ("Allergen", 160),
            ("Severity", 120), ("Reaction", 200), ("Provider", 140),
            ("Verified", 70),
        ])
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to add allergies.")
            return
        student_id = self._form_value("student_id").strip()
        allergen = self._form_value("allergen").strip()
        if not student_id or not allergen:
            self._err("Student ID and Allergen are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            cur.execute(
                """INSERT INTO allergies
                   (student_id, allergen, severity, reaction_description,
                    diagnosed_date, provider, verified, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, allergen, self._form_value("severity"),
                 self._form_value("reaction"),
                 self._form_value("diagnosed_date"),
                 self._form_value("provider"),
                 1 if self.vars["verified"].get() else 0,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("add_allergy", "allergy", new_id)
            self._info("Allergy record added successfully!")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to add allergy: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, allergen, severity, "
                     "reaction_description, provider, verified FROM allergies")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=(
                    row[0], row[1], row[2], row[3], row[4], row[5],
                    "Yes" if row[6] else "No"))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load allergies: {exc}")

    def update_selected(self):
        pass


# --------------------------------------------------------------------------
# Prescriptions
# --------------------------------------------------------------------------
class PrescriptionsPanel(_ClinicalPanelBase):
    title = "Prescriptions"
    STATUS = ["active", "completed", "discontinued", "on_hold"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Add Prescription", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "medication_name", "label": "Medication:"},
            {"key": "dosage", "label": "Dosage:"},
            {"key": "frequency", "label": "Frequency:"},
            {"key": "prescribed_date", "label": "Prescribed (YYYY-MM-DD):",
             "kind": "date"},
            {"key": "start_date", "label": "Start (YYYY-MM-DD):", "kind": "date"},
            {"key": "end_date", "label": "End (blank=ongoing):"},
            {"key": "prescriber", "label": "Prescriber:"},
            {"key": "pharmacy", "label": "Pharmacy:"},
            {"key": "notes", "label": "Notes:", "kind": "text"},
        ])
        ttk.Button(form, text="Add Prescription", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Medication", 150), ("Dosage", 90),
            ("Frequency", 110), ("Start", 90), ("End", 90), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text="Update Status", command=self.update_status).pack(
            side=tk.LEFT)
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to add prescriptions.")
            return
        student_id = self._form_value("student_id").strip()
        med = self._form_value("medication_name").strip()
        if not student_id or not med:
            self._err("Student ID and Medication are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            end_date = self._form_value("end_date").strip() or None
            cur.execute(
                """INSERT INTO prescriptions
                   (student_id, medication_name, dosage, frequency,
                    prescribed_date, start_date, end_date, prescriber,
                    pharmacy, status, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, med, self._form_value("dosage"),
                 self._form_value("frequency"),
                 self._form_value("prescribed_date"),
                 self._form_value("start_date"), end_date,
                 self._form_value("prescriber"), self._form_value("pharmacy"),
                 "active", self._form_value("notes"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("add_prescription", "prescription", new_id)
            self._info("Prescription added successfully!")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to add prescription: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, medication_name, dosage, frequency,"
                     " start_date, end_date, status FROM prescriptions")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY prescribed_date DESC, id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=(
                    row[0], row[1], row[2], row[3], row[4], row[5],
                    row[6] or "Ongoing", row[7]))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load prescriptions: {exc}")

    def update_status(self):
        rid = _selected_id(self.tree)
        if rid is None:
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to update prescriptions.")
            return
        _status_dialog(self.parent, "Update Prescription Status", self.STATUS,
                       lambda new: self._apply_status(rid, new))

    def _apply_status(self, rid, new_status):
        try:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("UPDATE prescriptions SET status = ? WHERE id = ?",
                        (new_status, rid))
            conn.commit()
            conn.close()
            self._audit("update_prescription_status", "prescription", rid)
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to update prescription: {exc}")


# --------------------------------------------------------------------------
# Lab results
# --------------------------------------------------------------------------
class LabResultsPanel(_ClinicalPanelBase):
    title = "Lab Results"
    STATUS = ["Final", "Preliminary", "Corrected", "Cancelled"]
    FLAG = ["", "H", "L"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Add Lab Result", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "test_name", "label": "Test name:"},
            {"key": "test_code", "label": "Test code:"},
            {"key": "result_value", "label": "Result value:"},
            {"key": "reference_range", "label": "Reference range:"},
            {"key": "units", "label": "Units:"},
            {"key": "status", "label": "Status:", "kind": "combo",
             "values": self.STATUS},
            {"key": "ordered_date", "label": "Ordered (YYYY-MM-DD):",
             "kind": "date"},
            {"key": "collected_date", "label": "Collected (YYYY-MM-DD):",
             "kind": "date"},
            {"key": "resulted_date", "label": "Resulted (YYYY-MM-DD):",
             "kind": "date"},
            {"key": "ordering_provider", "label": "Ordering provider:"},
            {"key": "lab_name", "label": "Lab name:"},
            {"key": "abnormal_flag", "label": "Abnormal flag:", "kind": "combo",
             "values": self.FLAG},
        ])
        ttk.Button(form, text="Add Lab Result", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Test", 160), ("Result", 100),
            ("Ref Range", 110), ("Units", 70), ("Resulted", 100), ("Flag", 100),
        ])
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to add lab results.")
            return
        student_id = self._form_value("student_id").strip()
        test_name = self._form_value("test_name").strip()
        if not student_id or not test_name:
            self._err("Student ID and Test name are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            flag = self._form_value("abnormal_flag").strip().upper()
            if flag not in ("H", "L"):
                flag = ""
            cur.execute(
                """INSERT INTO lab_results
                   (student_id, test_name, test_code, result_value,
                    reference_range, units, status, ordered_date, collected_date,
                    resulted_date, ordering_provider, lab_name, abnormal_flag,
                    created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, test_name, self._form_value("test_code"),
                 self._form_value("result_value"),
                 self._form_value("reference_range"), self._form_value("units"),
                 self._form_value("status"), self._form_value("ordered_date"),
                 self._form_value("collected_date"),
                 self._form_value("resulted_date"),
                 self._form_value("ordering_provider"),
                 self._form_value("lab_name"), flag,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("add_lab_result", "lab_result", new_id)
            if flag in ("H", "L"):
                self._audit("critical_lab_value", "lab_result", new_id,
                            f"Abnormal {test_name}")
                self._info("Lab result added. ABNORMAL flag set - "
                           "notify the ordering provider.")
            else:
                self._info("Lab result added successfully!")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to add lab result: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, test_name, result_value,"
                     " reference_range, units, resulted_date, abnormal_flag"
                     " FROM lab_results")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY resulted_date DESC, id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                flag = row[7]
                flag_text = {"H": "HIGH", "L": "LOW"}.get(flag, "Normal")
                self.tree.insert("", tk.END, values=(
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                    flag_text))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load lab results: {exc}")


# --------------------------------------------------------------------------
# Medical conditions
# --------------------------------------------------------------------------
class ConditionsPanel(_ClinicalPanelBase):
    title = "Medical Conditions"
    SEVERITY = ["Mild", "Moderate", "Severe"]
    STATUS = ["active", "resolved", "managed", "inactive"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Add Condition", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "condition_name", "label": "Condition:"},
            {"key": "icd_code", "label": "ICD-10 code:"},
            {"key": "severity", "label": "Severity:", "kind": "combo",
             "values": self.SEVERITY},
            {"key": "diagnosed_date", "label": "Diagnosed (YYYY-MM-DD):",
             "kind": "date"},
            {"key": "provider", "label": "Provider:"},
            {"key": "notes", "label": "Notes:", "kind": "text"},
        ])
        ttk.Button(form, text="Add Condition", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Condition", 170), ("ICD", 90),
            ("Severity", 100), ("Diagnosed", 100), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text="Update Status", command=self.update_status).pack(
            side=tk.LEFT)
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to add conditions.")
            return
        student_id = self._form_value("student_id").strip()
        name = self._form_value("condition_name").strip()
        if not student_id or not name:
            self._err("Student ID and Condition are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            cur.execute(
                """INSERT INTO medical_conditions
                   (student_id, condition_name, icd_code, severity,
                    diagnosed_date, status, provider, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, name, self._form_value("icd_code"),
                 self._form_value("severity"),
                 self._form_value("diagnosed_date"), "active",
                 self._form_value("provider"), self._form_value("notes"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("add_medical_condition", "medical_condition", new_id)
            self._info("Medical condition added successfully!")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to add condition: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, condition_name, icd_code, severity,"
                     " diagnosed_date, status FROM medical_conditions")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY diagnosed_date DESC, id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=tuple(row))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load conditions: {exc}")

    def update_status(self):
        rid = _selected_id(self.tree)
        if rid is None:
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to update conditions.")
            return
        _status_dialog(self.parent, "Update Condition Status", self.STATUS,
                       lambda new: self._apply_status(rid, new))

    def _apply_status(self, rid, new_status):
        try:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("UPDATE medical_conditions SET status = ? WHERE id = ?",
                        (new_status, rid))
            conn.commit()
            conn.close()
            self._audit("update_condition_status", "medical_condition", rid)
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to update condition: {exc}")


# --------------------------------------------------------------------------
# Care plans
# --------------------------------------------------------------------------
class CarePlansPanel(_ClinicalPanelBase):
    title = "Care Plans"
    STATUS = ["active", "completed", "on_hold", "discontinued"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Create Care Plan", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "plan_name", "label": "Plan name:"},
            {"key": "description", "label": "Description:", "kind": "text"},
            {"key": "start_date", "label": "Start (YYYY-MM-DD):", "kind": "date"},
            {"key": "end_date", "label": "End (blank=ongoing):"},
            {"key": "provider", "label": "Provider:"},
            {"key": "goals", "label": "Goals:", "kind": "text"},
            {"key": "interventions", "label": "Interventions:", "kind": "text"},
        ])
        ttk.Button(form, text="Create Care Plan", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Plan", 200), ("Start", 100),
            ("End", 100), ("Provider", 140), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text="Update Status", command=self.update_status).pack(
            side=tk.LEFT)
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to create care plans.")
            return
        student_id = self._form_value("student_id").strip()
        plan_name = self._form_value("plan_name").strip()
        if not student_id or not plan_name:
            self._err("Student ID and Plan name are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            end_date = self._form_value("end_date").strip() or None
            cur.execute(
                """INSERT INTO care_plans
                   (student_id, condition_id, plan_name, description, start_date,
                    end_date, provider, status, goals, interventions, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, None, plan_name, self._form_value("description"),
                 self._form_value("start_date"), end_date,
                 self._form_value("provider"), "active",
                 self._form_value("goals"), self._form_value("interventions"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("create_care_plan", "care_plan", new_id)
            self._info("Care plan created successfully!")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to create care plan: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, plan_name, start_date, end_date,"
                     " provider, status FROM care_plans")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY start_date DESC, id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=(
                    row[0], row[1], row[2], row[3], row[4] or "Ongoing",
                    row[5], row[6]))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load care plans: {exc}")

    def update_status(self):
        rid = _selected_id(self.tree)
        if rid is None:
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to update care plans.")
            return
        _status_dialog(self.parent, "Update Care Plan Status", self.STATUS,
                       lambda new: self._apply_status(rid, new))

    def _apply_status(self, rid, new_status):
        try:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("UPDATE care_plans SET status = ? WHERE id = ?",
                        (new_status, rid))
            conn.commit()
            conn.close()
            self._audit("update_care_plan", "care_plan", rid)
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to update care plan: {exc}")


# --------------------------------------------------------------------------
# Referrals
# --------------------------------------------------------------------------
class ReferralsPanel(_ClinicalPanelBase):
    title = "Referrals"
    SPECIALTY = ["Cardiology", "Dermatology", "Endocrinology",
                 "Gastroenterology", "Neurology", "Orthopedics", "Psychiatry",
                 "Pulmonology", "Urology", "Other"]
    URGENCY = ["Routine", "Urgent", "STAT"]
    STATUS = ["pending", "scheduled", "completed", "cancelled", "no_show"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Create Referral", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "referring_provider", "label": "Referring provider:"},
            {"key": "specialist_provider", "label": "Specialist provider:"},
            {"key": "specialty", "label": "Specialty:", "kind": "combo",
             "values": self.SPECIALTY},
            {"key": "reason", "label": "Reason:", "kind": "text"},
            {"key": "urgency", "label": "Urgency:", "kind": "combo",
             "values": self.URGENCY},
            {"key": "notes", "label": "Notes:", "kind": "text"},
        ])
        ttk.Button(form, text="Create Referral", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Specialist", 150), ("Specialty", 120),
            ("Urgency", 90), ("Referred", 100), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text="Track / Update Status",
                   command=self.update_status).pack(side=tk.LEFT)
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to create referrals.")
            return
        student_id = self._form_value("student_id").strip()
        specialist = self._form_value("specialist_provider").strip()
        if not student_id or not specialist:
            self._err("Student ID and Specialist provider are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            cur.execute(
                """INSERT INTO referrals
                   (student_id, referring_provider, specialist_provider,
                    specialty, reason, urgency, referral_date, status, notes,
                    created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, self._form_value("referring_provider"), specialist,
                 self._form_value("specialty"), self._form_value("reason"),
                 self._form_value("urgency"),
                 datetime.now().strftime("%Y-%m-%d"), "pending",
                 self._form_value("notes"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("create_referral", "referral", new_id)
            self._info(f"Referral created successfully! (ID {new_id})")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to create referral: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, specialist_provider, specialty,"
                     " urgency, referral_date, status FROM referrals")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY referral_date DESC, id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=tuple(row))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load referrals: {exc}")

    def update_status(self):
        rid = _selected_id(self.tree)
        if rid is None:
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to update referrals.")
            return
        _status_dialog(self.parent, "Update Referral Status", self.STATUS,
                       lambda new: self._apply_status(rid, new))

    def _apply_status(self, rid, new_status):
        try:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("UPDATE referrals SET status = ? WHERE id = ?",
                        (new_status, rid))
            conn.commit()
            conn.close()
            self._audit("update_referral_status", "referral", rid)
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to update referral: {exc}")


# --------------------------------------------------------------------------
# Screening
# --------------------------------------------------------------------------
class ScreeningPanel(_ClinicalPanelBase):
    title = "Screening Schedules"
    TYPES = ["Annual Physical Exam", "Blood Pressure Screening",
             "Cholesterol Screening", "Diabetes Screening",
             "Mental Health Screening", "STI Screening"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Schedule Screening", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "screening_type", "label": "Screening type:", "kind": "combo",
             "values": self.TYPES},
            {"key": "age", "label": "Patient age (for due date):",
             "default": "20"},
            {"key": "due_date", "label": "Due date (blank=auto):"},
            {"key": "provider", "label": "Provider:"},
        ])
        ttk.Button(form, text="Schedule", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))

        bar = ttk.Frame(self.parent)
        bar.pack(fill=tk.X, padx=10, pady=(6, 0))
        ttk.Label(bar, text="Show:").pack(side=tk.LEFT)
        self.vars["_scope"] = tk.StringVar(value="due")
        ttk.Combobox(bar, textvariable=self.vars["_scope"],
                     values=["due", "overdue", "all"], width=10,
                     state="readonly").pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)

        self._make_tree([
            ("ID", 50), ("Student", 90), ("Type", 200), ("Due", 100),
            ("Status", 90), ("Provider", 140),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text="Record Results",
                   command=self.record_results).pack(side=tk.LEFT)
        self.refresh()

    def add(self):
        if not self._can("manage_health_records"):
            self._err("You don't have permission to schedule screenings.")
            return
        student_id = self._form_value("student_id").strip()
        screening_type = self._form_value("screening_type").strip()
        if not student_id or not screening_type:
            self._err("Student ID and Screening type are required.")
            return
        due_date = self._form_value("due_date").strip()
        if not due_date:
            try:
                age = int(self._form_value("age") or 20)
            except ValueError:
                age = 20
            due_date = calculate_screening_due_date(screening_type, age)
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            cur.execute(
                """INSERT INTO screening_schedules
                   (student_id, screening_type, due_date, status, provider,
                    created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, screening_type, due_date, "due",
                 self._form_value("provider"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("create_screening_schedule", "screening_schedule", new_id)
            self._info(f"Screening scheduled (due {due_date}).")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to schedule screening: {exc}")

    def refresh(self):
        self._clear_tree()
        scope = self.vars.get("_scope")
        scope = scope.get() if scope else "due"
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            conn = self._conn()
            cur = conn.cursor()
            query = ("SELECT id, student_id, screening_type, due_date, status,"
                     " provider FROM screening_schedules")
            params = []
            if scope == "due":
                query += " WHERE status = 'due'"
            elif scope == "overdue":
                query += " WHERE status = 'due' AND due_date < ?"
                params.append(today)
            query += " ORDER BY due_date ASC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=tuple(row))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load screenings: {exc}")

    def record_results(self):
        rid = _selected_id(self.tree)
        if rid is None:
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to record results.")
            return
        dialog = tk.Toplevel(self.parent)
        dialog.title("Record Screening Results")
        dialog.transient(self.parent.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Completed date (YYYY-MM-DD):").grid(
            row=0, column=0, sticky=tk.W, pady=4)
        completed = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(frame, textvariable=completed, width=20).grid(
            row=0, column=1, pady=4)
        ttk.Label(frame, text="Results:").grid(row=1, column=0, sticky=tk.NW,
                                                pady=4)
        results = tk.Text(frame, width=40, height=4)
        results.grid(row=1, column=1, pady=4)

        def save():
            self._save_results(rid, completed.get(),
                               results.get("1.0", tk.END).strip())
            dialog.destroy()

        ttk.Button(frame, text="Save", command=save).grid(
            row=2, column=1, sticky=tk.E, pady=(8, 0))

    def _save_results(self, rid, completed_date, results_text):
        try:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("SELECT screening_type FROM screening_schedules WHERE id = ?",
                        (rid,))
            row = cur.fetchone()
            screening_type = row[0] if row else ""
            next_due = calculate_next_screening_date(screening_type)
            cur.execute(
                """UPDATE screening_schedules
                   SET completed_date = ?, status = 'completed', results = ?,
                       next_due_date = ?
                   WHERE id = ?""",
                (completed_date, results_text, next_due, rid),
            )
            conn.commit()
            conn.close()
            self._audit("record_screening_results", "screening", rid)
            self._info(f"Results recorded. Next due {next_due}.")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to record results: {exc}")


# --------------------------------------------------------------------------
# Wellness
# --------------------------------------------------------------------------
class WellnessPanel(_ClinicalPanelBase):
    title = "Wellness Programs"
    STATUS = ["enrolled", "completed", "withdrawn"]

    def build(self):
        self._header()
        form = ttk.LabelFrame(self.parent, text="Enroll in Program", padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "program_name", "label": "Program name:"},
        ])
        ttk.Button(form, text="Enroll", command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Program", 220), ("Enrolled", 110),
            ("Status", 110), ("Progress", 90),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text="Update Progress",
                   command=self.update_progress).pack(side=tk.LEFT)
        self.refresh()

    def add(self):
        student_id = self._form_value("student_id").strip()
        program = self._form_value("program_name").strip()
        if not student_id or not program:
            self._err("Student ID and Program name are required.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if not self._verify_student(cur, student_id):
                self._err("Student ID not found.")
                conn.close()
                return
            cur.execute(
                """SELECT status FROM wellness_participation
                   WHERE student_id = ? AND program_name = ?""",
                (student_id, program))
            if cur.fetchone():
                self._err("Already enrolled in this program.")
                conn.close()
                return
            cur.execute(
                """INSERT INTO wellness_participation
                   (student_id, program_name, enrollment_date, status,
                    created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, program, datetime.now().strftime("%Y-%m-%d"),
                 "enrolled", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self._audit("enroll_wellness_program", "wellness_participation",
                        new_id)
            self._info(f"Enrolled in {program}!")
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to enroll: {exc}")

    def refresh(self):
        self._clear_tree()
        try:
            conn = self._conn()
            cur = conn.cursor()
            sid = self._form_value("_search_student").strip()
            query = ("SELECT id, student_id, program_name, enrollment_date,"
                     " status, progress_score FROM wellness_participation")
            params = []
            if sid:
                query += " WHERE student_id = ?"
                params.append(sid)
            query += " ORDER BY enrollment_date DESC, id DESC LIMIT 200"
            cur.execute(query, params)
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=(
                    row[0], row[1], row[2], row[3], row[4],
                    f"{row[5]}%"))
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load wellness enrolments: {exc}")

    def update_progress(self):
        rid = _selected_id(self.tree)
        if rid is None:
            return
        dialog = tk.Toplevel(self.parent)
        dialog.title("Update Progress")
        dialog.transient(self.parent.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Progress score (0-100):").grid(
            row=0, column=0, sticky=tk.W, pady=4)
        score = tk.StringVar(value="0")
        ttk.Entry(frame, textvariable=score, width=8).grid(row=0, column=1,
                                                           pady=4)

        def save():
            self._save_progress(rid, score.get())
            dialog.destroy()

        ttk.Button(frame, text="Save", command=save).grid(
            row=1, column=1, sticky=tk.E, pady=(8, 0))

    def _save_progress(self, rid, raw_score):
        try:
            value = max(0, min(100, int(raw_score)))
        except (ValueError, TypeError):
            self._err("Progress must be a number 0-100.")
            return
        try:
            conn = self._conn()
            cur = conn.cursor()
            if value >= 100:
                cur.execute(
                    """UPDATE wellness_participation
                       SET progress_score = ?, status = 'completed',
                           completion_date = ?
                       WHERE id = ?""",
                    (value, datetime.now().strftime("%Y-%m-%d"), rid))
            else:
                cur.execute(
                    "UPDATE wellness_participation SET progress_score = ? WHERE id = ?",
                    (value, rid))
            conn.commit()
            conn.close()
            self._audit("track_wellness_progress", "wellness_participation", rid)
            self.refresh()
        except Exception as exc:
            self._err(f"Failed to update progress: {exc}")


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------
def _selected_id(tree):
    """Return the ID (first column) of the selected tree row, or None with a
    warning."""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a row first.")
        return None
    try:
        return tree.item(selection[0])["values"][0]
    except (IndexError, KeyError):
        return None


def _status_dialog(parent, title, options, on_save):
    """Modal combobox dialog for choosing a new status."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text="New status:").grid(row=0, column=0, sticky=tk.W,
                                               pady=4, padx=(0, 8))
    var = tk.StringVar(value=options[0])
    ttk.Combobox(frame, textvariable=var, values=options, state="readonly",
                 width=20).grid(row=0, column=1, pady=4)

    def save():
        on_save(var.get())
        dialog.destroy()

    ttk.Button(frame, text="Save", command=save).grid(
        row=1, column=1, sticky=tk.E, pady=(8, 0))
    return dialog


#: Registry the orchestrator can iterate to wire nav buttons.  Each entry is
#: ``(nav_label, PanelClass)``.
CLINICAL_PANELS = [
    ("Allergies", AllergiesPanel),
    ("Prescriptions", PrescriptionsPanel),
    ("Lab Results", LabResultsPanel),
    ("Medical Conditions", ConditionsPanel),
    ("Care Plans", CarePlansPanel),
    ("Referrals", ReferralsPanel),
    ("Screening", ScreeningPanel),
    ("Wellness", WellnessPanel),
]
