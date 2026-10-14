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
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import (
    get_connection as _central_get_connection,
)
from education_system.systems.university.domains.pastoral.domain.health.records.db.audit import (
    log_audit_event,
)
# Referral notifications live with the domain, so the CLI and this panel send
# students the same three emails through the university email system.
from education_system.systems.university.domains.pastoral.domain.health.records.referrals.referrals import (
    _referral_email_context,
    notify_referral_created,
    notify_referral_status_changed,
    notify_referral_updated,
)
from education_system.systems.university.domains.pastoral.domain.health.records.screening.schedules import (
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
            logger.debug("Suppressed exception", exc_info=True)

    def _verify_student(self, cursor, student_id):
        cursor.execute(
            "SELECT COUNT(*) FROM students WHERE student_id = ?",
            (student_id,),
        )
        return cursor.fetchone()[0] > 0

    def _err(self, msg):
        messagebox.showerror(_t('gui.pastoral.health.health_portal.clinical_panels.dialogs.error', default="Error"), msg)

    def _info(self, msg):
        messagebox.showinfo(_t('gui.pastoral.health.health_portal.clinical_panels.dialogs.success', default="Success"), msg)

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
        ttk.Label(bar, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.filter_by_student_id', default="Filter by Student ID:")).pack(side=tk.LEFT)
        var = tk.StringVar()
        self.vars["_search_student"] = var
        ttk.Entry(bar, textvariable=var, width=18).pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(bar, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.refresh', default="Refresh"), command=self.refresh).pack(side=tk.LEFT)
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.add_allergy', default="Add Allergy"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.add_allergy', default="Add Allergy"), command=self.add).grid(
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.add_prescription', default="Add Prescription"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.add_prescription', default="Add Prescription"), command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Medication", 150), ("Dosage", 90),
            ("Frequency", 110), ("Start", 90), ("End", 90), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.update_status', default="Update Status"), command=self.update_status).pack(
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.add_lab_result', default="Add Lab Result"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.add_lab_result', default="Add Lab Result"), command=self.add).grid(
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.add_condition', default="Add Condition"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.add_condition', default="Add Condition"), command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Condition", 170), ("ICD", 90),
            ("Severity", 100), ("Diagnosed", 100), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.update_status', default="Update Status"), command=self.update_status).pack(
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.create_care_plan', default="Create Care Plan"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.create_care_plan', default="Create Care Plan"), command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Plan", 200), ("Start", 100),
            ("End", 100), ("Provider", 140), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.update_status', default="Update Status"), command=self.update_status).pack(
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.create_referral', default="Create Referral"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.create_referral', default="Create Referral"), command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Specialist", 150), ("Specialty", 120),
            ("Urgency", 90), ("Referred", 100), ("Status", 100),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.update_referral', default="Update Referral"),
                   command=self.update_referral).pack(side=tk.LEFT)
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.track_update_status', default="Track / Update Status"),
                   command=self.update_status).pack(side=tk.LEFT, padx=(6, 0))
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
            # Read back what was committed so the email states the stored
            # record rather than what we think we wrote.
            context = _referral_email_context(cur, new_id)
            conn.close()
            self._audit("create_referral", "referral", new_id)

            emailed = notify_referral_created(context) if context else False
            note = (f"\n\nConfirmation emailed to {context['student_email']}."
                    if emailed else
                    "\n\nNote: the confirmation email could not be sent.")
            self._info(f"Referral created successfully! (ID {new_id}){note}")
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
        # Merged with the appointment date: moving a referral to 'scheduled'
        # without recording *when* leaves the student with a status change and
        # no date, which is the one thing that email needs to carry. The CLI
        # has always asked for it here; the GUI made you go to Update Referral
        # separately, so the two flows now match.
        _referral_status_dialog(
            self.parent, "Update Referral Status", self.STATUS,
            lambda new, appt: self._apply_status(rid, new, appt))

    def _actor(self):
        """Username to attribute a change to in the student's email."""
        user = getattr(self.auth, "current_user", None) or {}
        return user.get("username", "the Health Centre")

    def update_referral(self):
        """Edit a referral's clinical details and email the student the diff.

        Separate from Track / Update Status: that has its own workflow and its
        own email. Fields are pre-filled with the current values, and only the
        ones that actually differ are written, audited or reported.
        """
        rid = _selected_id(self.tree)
        if rid is None:
            return
        if not self._can("manage_health_records"):
            self._err("You don't have permission to update referrals.")
            return

        try:
            conn = self._conn()
            cur = conn.cursor()
            before = _referral_email_context(cur, rid)
            conn.close()
        except Exception as exc:
            self._err(f"Failed to load referral: {exc}")
            return

        if not before:
            self._err("Referral not found.")
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Update Referral #{rid}")
        dialog.transient(self.parent.winfo_toplevel())
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"{before['student_name']} ({before['student_id']})",
                  font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        current_notes = "" if before["notes"] == "None recorded." else before["notes"]
        current_appt = ("" if before["appointment_date"] == "Not yet scheduled"
                        else before["appointment_date"])

        widgets = {}
        rows = [
            ("referring_provider", "Referring provider:", "entry", before["referring_provider"], None),
            ("specialist_provider", "Specialist provider:", "entry", before["specialist_provider"], None),
            ("specialty", "Specialty:", "combo", before["specialty"], self.SPECIALTY),
            ("urgency", "Urgency:", "combo", before["urgency"], self.URGENCY),
            ("reason", "Reason:", "entry", before["reason"], None),
            ("notes", "Notes:", "entry", current_notes, None),
            ("appointment_date", "Appointment date (YYYY-MM-DD):", "entry", current_appt, None),
        ]
        for index, (key, label, kind, value, values) in enumerate(rows, start=1):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky=tk.W,
                                              pady=3, padx=(0, 8))
            var = tk.StringVar(value=value or "")
            if kind == "combo":
                widget = ttk.Combobox(frame, textvariable=var, values=values,
                                      state="readonly", width=32)
            else:
                widget = ttk.Entry(frame, textvariable=var, width=34)
            widget.grid(row=index, column=1, sticky=tk.W, pady=3)
            widgets[key] = var

        def save():
            values = {k: v.get().strip() for k, v in widgets.items()}

            appointment_date = values["appointment_date"] or None
            if appointment_date:
                try:
                    datetime.strptime(appointment_date, "%Y-%m-%d")
                except ValueError:
                    self._err(f"'{appointment_date}' is not a valid date. Use YYYY-MM-DD.")
                    return

            changes = []
            for label, old, new in [
                ("Referring provider", before["referring_provider"], values["referring_provider"]),
                ("Specialist", before["specialist_provider"], values["specialist_provider"]),
                ("Specialty", before["specialty"], values["specialty"]),
                ("Urgency", before["urgency"], values["urgency"]),
                ("Reason", before["reason"], values["reason"]),
                ("Notes", current_notes, values["notes"]),
                ("Appointment date", current_appt or None, appointment_date),
            ]:
                if (old or "") != (new or ""):
                    changes.append((label, old, new))

            if not changes:
                self._info("Nothing was changed.")
                dialog.destroy()
                return

            summary = "\n".join(
                f"  - {label}: '{old or 'not set'}' -> '{new or 'not set'}'"
                for label, old, new in changes)
            if not messagebox.askyesno(
                    "Confirm changes",
                    f"Apply these changes to referral #{rid}?\n\n{summary}\n\n"
                    "The student will be emailed this list.",
                    parent=dialog):
                return

            try:
                conn = self._conn()
                cur = conn.cursor()
                cur.execute(
                    """UPDATE referrals
                       SET referring_provider = ?, specialist_provider = ?,
                           specialty = ?, reason = ?, urgency = ?, notes = ?,
                           appointment_date = ?
                       WHERE id = ?""",
                    (values["referring_provider"], values["specialist_provider"],
                     values["specialty"], values["reason"], values["urgency"],
                     values["notes"], appointment_date, rid))
                conn.commit()
                after = _referral_email_context(cur, rid)
                conn.close()
            except Exception as exc:
                self._err(f"Failed to update referral: {exc}")
                return

            self._audit("update_referral", "referral", rid,
                        "; ".join(f"{label}: {old} -> {new}"
                                  for label, old, new in changes))

            emailed = False
            if after:
                emailed = notify_referral_updated(after, changes, self._actor())

            dialog.destroy()
            self._info(
                f"Referral #{rid} updated ({len(changes)} change(s))."
                + (f"\n\nUpdate emailed to {after['student_email']}."
                   if emailed else
                   "\n\nNote: the update email could not be sent."))
            self.refresh()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(rows) + 1, column=0, columnspan=2, sticky=tk.E, pady=(12, 0))
        ttk.Button(buttons, text="Save changes", command=save).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

    def _apply_status(self, rid, new_status, appointment_date=None):
        try:
            conn = self._conn()
            cur = conn.cursor()
            # Capture the status being replaced — the email names both.
            cur.execute("SELECT status FROM referrals WHERE id = ?", (rid,))
            row = cur.fetchone()
            previous_status = row[0] if row else "unknown"

            if appointment_date:
                cur.execute(
                    "UPDATE referrals SET status = ?, appointment_date = ? WHERE id = ?",
                    (new_status, appointment_date, rid))
            else:
                cur.execute("UPDATE referrals SET status = ? WHERE id = ?",
                            (new_status, rid))
            conn.commit()
            context = _referral_email_context(cur, rid)
            conn.close()
            self._audit("update_referral_status", "referral", rid,
                        f"Status changed from {previous_status} to {new_status}")

            emailed = False
            if context:
                emailed = notify_referral_status_changed(
                    context, previous_status, self._actor())
            self._info(
                f"Referral status updated to '{new_status}'."
                + (f"\n\nStatus change emailed to {context['student_email']}."
                   if emailed else
                   "\n\nNote: the status-change email could not be sent."))
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.schedule_screening', default="Schedule Screening"), padding=12)
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
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.schedule', default="Schedule"), command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))

        bar = ttk.Frame(self.parent)
        bar.pack(fill=tk.X, padx=10, pady=(6, 0))
        ttk.Label(bar, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.show', default="Show:")).pack(side=tk.LEFT)
        self.vars["_scope"] = tk.StringVar(value=_t('gui.pastoral.health.health_portal.clinical_panels.values.due', default="due"))
        ttk.Combobox(bar, textvariable=self.vars["_scope"],
                     values=["due", "overdue", "all"], width=10,
                     state="readonly").pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(bar, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.refresh', default="Refresh"), command=self.refresh).pack(side=tk.LEFT)

        self._make_tree([
            ("ID", 50), ("Student", 90), ("Type", 200), ("Due", 100),
            ("Status", 90), ("Provider", 140),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.record_results', default="Record Results"),
                   command=self.record_results).pack(side=tk.LEFT)
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.send_reminders', default="Send Reminders"),
                   command=self.send_screening_reminders).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.send_overdue', default="Send Overdue Notices"),
                   command=self.send_overdue_notices).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.population_report', default="Population Report"),
                   command=self.show_population_report).pack(side=tk.LEFT, padx=(6, 0))
        self.refresh()

    # ------------------------------------------------------------------
    # Notifications — same domain helpers and templates as the health CLI,
    # so a student gets identical wording whichever interface was used.
    # ------------------------------------------------------------------
    def _collect_screenings(self, overdue):
        """Rows for a reminder run.

        *overdue* selects past-due screenings; otherwise it is everything
        falling due within the next seven days, matching the CLI's windows.
        """
        today = datetime.now().strftime('%Y-%m-%d')
        horizon = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        comparison = "ss.due_date < ?" if overdue else "ss.due_date <= ?"
        bound = today if overdue else horizon

        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - conditional between literals
            rows = conn.execute(
                "SELECT ss.id, ss.student_id, s.first_name, s.last_name,"
                "       ss.screening_type, ss.due_date, ss.provider, s.email_address"
                " FROM screening_schedules ss"
                " JOIN students s ON ss.student_id = s.student_id"
                f" WHERE {comparison} AND ss.status = 'due'"
                " ORDER BY ss.due_date", (bound,)).fetchall()
        finally:
            conn.close()

        students = []
        for (sid, student_id, first, last, screening_type,
             due_date, provider, email) in rows:
            entry = {
                'screening_id': sid, 'student_id': student_id,
                'student_name': f"{first or ''} {last or ''}".strip() or student_id,
                'screening_type': screening_type, 'due_date': due_date,
                'provider': provider, 'email': email,
            }
            if overdue:
                try:
                    entry['days_overdue'] = (
                        datetime.now() - datetime.strptime(due_date, '%Y-%m-%d')).days
                except (ValueError, TypeError):
                    entry['days_overdue'] = 0
            students.append(entry)
        return students

    def _run_notification(self, students, notify, noun):
        """Confirm, send one email per student, and report honestly.

        Students with no address on file are never counted as sent — the
        summary distinguishes "could not be reached" from "failed".
        """
        if not students:
            self._info(f"No {noun} to send.")
            return
        reachable = [s for s in students if (s.get('email') or '').strip()]
        unreachable = len(students) - len(reachable)

        detail = "\n".join(
            f"  • {s['student_name']} ({s['student_id']}) — "
            f"{s['screening_type']} due {s['due_date']}" for s in students[:12])
        if len(students) > 12:
            detail += f"\n  … and {len(students) - 12} more"

        message = (f"Send {noun} to {len(reachable)} student(s)?\n\n{detail}")
        if unreachable:
            message += (f"\n\n{unreachable} of {len(students)} have no email "
                        "address on file and cannot be contacted.")
        if not messagebox.askyesno("Confirm", message):
            return

        sent = failed = 0
        for student in reachable:
            if notify(student):
                sent += 1
            else:
                failed += 1

        self._audit('send_screening_notifications', 'screening', sent)
        summary = f"{noun.capitalize()}: {sent} sent"
        if failed:
            summary += f", {failed} failed"
        if unreachable:
            summary += f", {unreachable} with no address on file"
        self._info(summary + ".")

    def send_screening_reminders(self):
        """Email students whose screening falls due in the next seven days."""
        if not self._can("manage_health_records"):
            self._err("You don't have permission to send screening reminders.")
            return
        try:
            from education_system.systems.university.domains.pastoral.domain.health.records.screening.reminders import (
                notify_screening_due,
            )
            self._run_notification(self._collect_screenings(overdue=False),
                                   notify_screening_due, "screening reminders")
        except Exception as exc:
            self._err(f"Failed to send screening reminders: {exc}")

    def send_overdue_notices(self):
        """Email students whose screening is past its due date."""
        if not self._can("manage_health_records"):
            self._err("You don't have permission to send overdue notices.")
            return
        try:
            from education_system.systems.university.domains.pastoral.domain.health.records.screening.reminders import (
                notify_screening_overdue,
            )
            self._run_notification(self._collect_screenings(overdue=True),
                                   notify_screening_overdue, "overdue notices")
        except Exception as exc:
            self._err(f"Failed to send overdue notices: {exc}")

    # ------------------------------------------------------------------
    # Population report
    # ------------------------------------------------------------------
    def _population_report_text(self):
        """Build the same aggregate report the CLI prints."""
        lines = ["POPULATION SCREENING REPORT", "=" * 40,
                 f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
                 "Period: last 12 months", ""]
        conn = self._conn()
        try:
            compliance = conn.execute(
                "SELECT screening_type, COUNT(*),"
                "       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END),"
                "       SUM(CASE WHEN due_date < date('now') AND status = 'due'"
                "                THEN 1 ELSE 0 END)"
                " FROM screening_schedules"
                " WHERE due_date >= date('now', '-365 days')"
                " GROUP BY screening_type ORDER BY COUNT(*) DESC").fetchall()
            if compliance:
                lines.append("Screening Compliance Rates (Last 12 Months):")
                lines.append(f"{'Screening Type':<25} {'Total':<8} {'Completed':<10} "
                             f"{'Overdue':<8} {'Rate':<8}")
                lines.append("-" * 65)
                for screening, total, completed, overdue in compliance:
                    rate = (completed / total * 100) if total else 0
                    lines.append(f"{screening:<25} {total:<8} {completed:<10} "
                                 f"{overdue:<8} {rate:.1f}%")
            else:
                lines.append("No screenings scheduled in the last 12 months.")

            age_rows = conn.execute(
                "SELECT CASE WHEN s.age < 25 THEN '18-24'"
                "            WHEN s.age < 35 THEN '25-34'"
                "            WHEN s.age < 45 THEN '35-44'"
                "            ELSE '45+' END AS age_group,"
                "       COUNT(DISTINCT ss.student_id),"
                "       AVG(CASE WHEN ss.status = 'completed' THEN 1.0 ELSE 0.0 END) * 100"
                " FROM screening_schedules ss"
                " JOIN students s ON ss.student_id = s.student_id"
                " WHERE ss.due_date >= date('now', '-365 days')"
                " GROUP BY age_group ORDER BY age_group").fetchall()
            if age_rows:
                lines += ["", "Compliance by Age Group:",
                          f"{'Age Group':<12} {'Students':<10} {'Compliance':<12}",
                          "-" * 35]
                for age_group, students, compliance_pct in age_rows:
                    lines.append(f"{age_group:<12} {students:<10} {compliance_pct:.1f}%")
        finally:
            conn.close()
        return "\n".join(lines)

    def show_population_report(self):
        """Show the aggregate report, with the option to email the admins."""
        if not self._can("manage_health_records"):
            self._err("You don't have permission to view screening reports.")
            return
        try:
            content = self._population_report_text()
        except Exception as exc:
            self._err(f"Failed to build the report: {exc}")
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title("Population Screening Report")
        dialog.transient(self.parent.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        text = scrolledtext.ScrolledText(frame, wrap=tk.NONE, width=90, height=26,
                                         font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True)
        text.insert('1.0', content)
        text.config(state='disabled')

        def email_to_admin():
            try:
                from education_system.systems.university.domains.pastoral.domain.health.records.screening.reminders import (
                    send_screening_report_to_admins,
                )
            except Exception as exc:
                self._err(f"Email system unavailable: {exc}")
                return
            user = getattr(self.auth, 'current_user', None) or {}
            sent, failed, addresses = send_screening_report_to_admins(
                "Population Screening Report", content,
                user.get('username', 'University Health Portal'))
            if not sent and not failed:
                messagebox.showwarning(
                    "No admin address",
                    "No admin email address is configured, so the report was "
                    "not sent. Set an email against an admin user and try again.",
                    parent=dialog)
                return
            self._audit('email_screening_report', 'screening', sent)
            messagebox.showinfo(
                "Report sent",
                f"Emailed to: {', '.join(addresses)}"
                + (f"\n{failed} could not be sent." if failed else ""),
                parent=dialog)

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(buttons, text="Email to Admin",
                   command=email_to_admin).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

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
        dialog.title(_t('gui.pastoral.health.health_portal.clinical_panels.windows.record_screening_results', default="Record Screening Results"))
        dialog.transient(self.parent.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.completed_date_yyyy_mm_dd', default="Completed date (YYYY-MM-DD):")).grid(
            row=0, column=0, sticky=tk.W, pady=4)
        completed = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(frame, textvariable=completed, width=20).grid(
            row=0, column=1, pady=4)
        ttk.Label(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.results', default="Results:")).grid(row=1, column=0, sticky=tk.NW,
                                                pady=4)
        results = tk.Text(frame, width=40, height=4)
        results.grid(row=1, column=1, pady=4)

        def save():
            self._save_results(rid, completed.get(),
                               results.get("1.0", tk.END).strip())
            dialog.destroy()

        ttk.Button(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.save', default="Save"), command=save).grid(
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
        form = ttk.LabelFrame(self.parent, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.enroll_in_program', default="Enroll in Program"), padding=12)
        form.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._build_form(form, [
            {"key": "student_id", "label": "Student ID:"},
            {"key": "program_name", "label": "Program name:"},
        ])
        ttk.Button(form, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.enroll', default="Enroll"), command=self.add).grid(
            row=99, column=1, sticky=tk.W, pady=(8, 0))
        self._search_row(self.parent)
        self._make_tree([
            ("ID", 50), ("Student", 90), ("Program", 220), ("Enrolled", 110),
            ("Status", 110), ("Progress", 90),
        ])
        btns = ttk.Frame(self.parent)
        btns.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(btns, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.update_progress', default="Update Progress"),
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
        dialog.title(_t('gui.pastoral.health.health_portal.clinical_panels.windows.update_progress', default="Update Progress"))
        dialog.transient(self.parent.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.progress_score_0_100', default="Progress score (0-100):")).grid(
            row=0, column=0, sticky=tk.W, pady=4)
        score = tk.StringVar(value="0")
        ttk.Entry(frame, textvariable=score, width=8).grid(row=0, column=1,
                                                           pady=4)

        def save():
            self._save_progress(rid, score.get())
            dialog.destroy()

        ttk.Button(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.save', default="Save"), command=save).grid(
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
        messagebox.showwarning(_t('gui.pastoral.health.health_portal.clinical_panels.dialogs.no_selection', default="No Selection"), _t('gui.pastoral.health.health_portal.clinical_panels.dialogs.please_select_a_row_first', default="Please select a row first."))
        return None
    try:
        return tree.item(selection[0])["values"][0]
    except (IndexError, KeyError):
        return None


def _referral_status_dialog(parent, title, options, on_save):
    """Status dialog that also captures an appointment date.

    The date field is only enabled for 'scheduled' — the one status where a
    date is meaningful — and is required there, because a scheduled referral
    with no date tells the student nothing useful. ``on_save`` is called with
    ``(new_status, appointment_date_or_None)``.
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.new_status', default="New status:")).grid(
        row=0, column=0, sticky=tk.W, pady=4, padx=(0, 8))
    status_var = tk.StringVar(value=options[0])
    ttk.Combobox(frame, textvariable=status_var, values=options,
                 state="readonly", width=20).grid(row=0, column=1, pady=4, sticky=tk.W)

    ttk.Label(frame, text="Appointment date (YYYY-MM-DD):").grid(
        row=1, column=0, sticky=tk.W, pady=4, padx=(0, 8))
    date_var = tk.StringVar()
    date_entry = ttk.Entry(frame, textvariable=date_var, width=22)
    date_entry.grid(row=1, column=1, pady=4, sticky=tk.W)

    hint = ttk.Label(frame, text="Required when the status is 'scheduled'.",
                     foreground="#666666")
    hint.grid(row=2, column=1, sticky=tk.W)

    def sync_date_state(*_args):
        if status_var.get() == "scheduled":
            date_entry.state(["!disabled"])
        else:
            date_var.set("")
            date_entry.state(["disabled"])

    status_var.trace_add("write", sync_date_state)
    sync_date_state()

    def save():
        new_status = status_var.get()
        appointment_date = date_var.get().strip() or None
        if new_status == "scheduled":
            if not appointment_date:
                messagebox.showwarning(
                    "Appointment date required",
                    "A scheduled referral needs a date — the student is told "
                    "when to attend.", parent=dialog)
                return
            try:
                datetime.strptime(appointment_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showwarning(
                    "Invalid date",
                    f"'{appointment_date}' is not a valid date. Use YYYY-MM-DD.",
                    parent=dialog)
                return
        on_save(new_status, appointment_date)
        dialog.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=3, column=1, sticky=tk.E, pady=(10, 0))
    ttk.Button(buttons, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.save', default="Save"), command=save).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
    return dialog


def _status_dialog(parent, title, options, on_save):
    """Modal combobox dialog for choosing a new status."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.labels.new_status', default="New status:")).grid(row=0, column=0, sticky=tk.W,
                                               pady=4, padx=(0, 8))
    var = tk.StringVar(value=options[0])
    ttk.Combobox(frame, textvariable=var, values=options, state="readonly",
                 width=20).grid(row=0, column=1, pady=4)

    def save():
        on_save(var.get())
        dialog.destroy()

    ttk.Button(frame, text=_t('gui.pastoral.health.health_portal.clinical_panels.buttons.save', default="Save"), command=save).grid(
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
