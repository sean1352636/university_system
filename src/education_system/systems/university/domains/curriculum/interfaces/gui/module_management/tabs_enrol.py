"""Module Management additions to the Programmes, Rules and Enrolments tabs:
programme designations, exclusions, the module waitlist, enrolling a whole
cohort and withdrawing several students at once. Rules are
``university/application/modules/enrolment``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.modules import delivery as module_delivery
from education_system.systems.university.application.modules import enrolment
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management import (  # noqa: E501
    data,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management._widgets import (  # noqa: E501
    _PAD, _clear, _code_of, _tree,
)
from education_system.systems.university.infrastructure.database.schemas.module_catalogue_schema import (  # noqa: E501
    DESIGNATIONS,
)

_NO_DELIVERY = "(no delivery)"


class EnrolmentTabs:
    """Mixin for ModuleManagementGUI."""

    # ── programme designations ───────────────────────────────────────

    def _build_designation_bar(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", **_PAD)
        ttk.Label(bar, text="Selected programme: this module is").pack(side="left")
        self.designation_combo = ttk.Combobox(bar, values=DESIGNATIONS, width=11,
                                              state="readonly")
        self.designation_combo.set("core")
        self.designation_combo.pack(side="left", padx=4)
        ttk.Label(bar, text="in year").pack(side="left")
        self.designation_year = ttk.Spinbox(bar, from_=0, to=7, width=3)
        self.designation_year.set(1)
        self.designation_year.pack(side="left", padx=4)
        ttk.Button(bar, text="Set", command=self.set_designation).pack(side="left", padx=2)
        ttk.Button(bar, text="Clear", command=self.clear_designation).pack(side="left")
        self.designation_note_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.designation_note_var, foreground="#b9770e",
                  wraplength=640, justify="left").pack(anchor="w", padx=8)

    def _designations_for_tree(self):
        """``{course_code: 'Core, year 1'}`` for the Programmes tree."""
        found = data.call(enrolment.designations, self.current_code)
        return {course: (f"{d['category'].title()}"
                         + (f", year {d['year_of_study']}" if d["year_of_study"] is not None
                            else ""))
                for course, d in found.items()}

    def _selected_programme(self):
        sel = self.programmes_tree.selection()
        if not self._require_module() or not sel:
            self._info("Programmes", "Select a programme in the list first.")
            return None
        return self._programmes[int(sel[0])]["course_code"]

    def set_designation(self):
        course = self._selected_programme()
        if course and self._do("Set designation", enrolment.set_designation, self.current_code,
                               course, self.designation_combo.get(),
                               self.designation_year.get(), self.username) is not None:
            self._audit("set_module_designation", module_code=self.current_code,
                        course_code=course, category=self.designation_combo.get())
            self.refresh_programmes()

    def clear_designation(self):
        course = self._selected_programme()
        if course:
            self._do("Clear designation", enrolment.clear_designation, self.current_code, course)
            self.refresh_programmes()

    def _refresh_designation_note(self):
        courses = [p["course_code"] for p in getattr(self, "_programmes", [])]
        issues = [i for c in courses for i in data.call(enrolment.programme_credit_issues, c)]
        self.designation_note_var.set("; ".join(issues))

    # ── exclusions ───────────────────────────────────────────────────

    def _build_exclusions(self, tab):
        ttk.Label(tab, text="Exclusions — modules that overlap too much to take both:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(10, 0))
        if self.can_manage:
            bar = ttk.Frame(tab)
            bar.pack(fill="x", **_PAD)
            self.exclusion_combo = ttk.Combobox(bar, width=34)
            self.exclusion_combo.pack(side="left")
            ttk.Label(bar, text="Why").pack(side="left", padx=(6, 0))
            self.exclusion_reason = tk.StringVar()
            ttk.Entry(bar, textvariable=self.exclusion_reason, width=24).pack(side="left", padx=4)
            ttk.Button(bar, text="Add", command=self.add_exclusion).pack(side="left", padx=2)
            ttk.Button(bar, text="Remove", command=self.remove_exclusion).pack(side="left")
        self.exclusion_tree = _tree(tab, [("code", "Module"), ("name", "Name"),
                                          ("why", "Why"), ("by", "Added by")],
                                    [90, 230, 200, 90], height=4)

    def refresh_exclusions(self):
        _clear(self.exclusion_tree)
        if not self.current_code:
            return
        if self.can_manage:
            self.exclusion_combo["values"] = self.prereq_combo["values"]
        for e in data.call(enrolment.exclusions, self.current_code):
            self.exclusion_tree.insert("", "end", iid=str(e["id"]), values=(
                e["other"], e["other_name"], e["reason"] or "", e["created_by"] or ""))

    def add_exclusion(self):
        if not self._require_module():
            return
        other = _code_of(self.exclusion_combo.get())
        if self._do("Add exclusion", enrolment.add_exclusion, self.current_code, other,
                    self.exclusion_reason.get(), self.username):
            self._audit("add_module_exclusion", module_code=self.current_code, excludes=other)
            self.exclusion_combo.set("")
            self.exclusion_reason.set("")
            self.refresh_exclusions()

    def remove_exclusion(self):
        sel = self.exclusion_tree.selection()
        if self._require_module() and sel and self._ask("Remove exclusion",
                                                         "Allow both modules to be taken?"):
            self._do("Remove exclusion", enrolment.remove_exclusion, int(sel[0]))
            self.refresh_exclusions()

    # ── enrolment extras ─────────────────────────────────────────────

    def _build_enrolment_extras(self, bar):
        """Delivery picker plus cohort / bulk buttons, on the Enrolments bar."""
        ttk.Label(bar, text="Delivery:").pack(side="left", padx=(6, 0))
        self.delivery_combo = ttk.Combobox(bar, width=18, state="readonly")
        self.delivery_combo.pack(side="left", padx=2)

    def _build_enrolment_bulk(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill="x", **_PAD)
        ttk.Button(bar, text="Enrol a cohort…", command=self.enrol_cohort).pack(side="left")
        ttk.Label(bar, text="(select several rows with Ctrl/Shift to withdraw them together)",
                  foreground="#666").pack(side="left", padx=6)
        return bar

    def _selected_delivery_id(self):
        label = self.delivery_combo.get() if hasattr(self, "delivery_combo") else ""
        return next((d["id"] for text, d in getattr(self, "_delivery_choices", [])
                     if text == label), None)

    def _refresh_delivery_choices(self):
        if not hasattr(self, "delivery_combo"):
            return
        open_ = [d for d in data.call(module_delivery.deliveries, self.current_code)
                 if d["status"] == "Open"] if self.current_code else []
        self._delivery_choices = [(f"{d['term']} {d['section_number']} "
                                   f"({d['enrolled']}/{d['capacity']})", d) for d in open_]
        self.delivery_combo["values"] = [_NO_DELIVERY] + [t for t, _ in self._delivery_choices]
        self.delivery_combo.set(self._delivery_choices[0][0] if self._delivery_choices
                                else _NO_DELIVERY)

    def enrol_cohort(self):
        if not self._require_module():
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Enrol a cohort on {self.current_code}")
        dialog.transient(self.root)
        form = ttk.Frame(dialog, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Programme:").grid(row=0, column=0, sticky="w", pady=4)
        courses = [f"{c['code']} - {c['name'] or ''}" for c in data.course_choices()]
        course = ttk.Combobox(form, values=courses, width=38, state="readonly")
        course.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Year of study (blank = all):").grid(row=1, column=0, sticky="w")
        year = tk.StringVar()
        ttk.Entry(form, textvariable=year, width=6).grid(row=1, column=1, sticky="w", pady=4)
        override = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Staff override: enrol even where the rules are not met",
                        variable=override).grid(row=2, column=0, columnspan=2, sticky="w")
        waitlist = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="When the module is full, put the rest on the waitlist",
                        variable=waitlist).grid(row=3, column=0, columnspan=2, sticky="w")
        count = tk.StringVar(value="Choose a programme.")
        ttk.Label(form, textvariable=count, foreground="#555").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=6)
        members = []

        def preview(*_a):
            members[:] = self._run("Find cohort", data.call, enrolment.cohort,
                                   _code_of(course.get()), year.get()) or []
            count.set(f"{len(members)} active student(s) in this cohort.")

        course.bind("<<ComboboxSelected>>", preview)
        year.trace_add("write", preview)

        def run():
            if not members:
                self._info("Enrol a cohort", "That cohort has no active students.")
                return
            if not self._ask("Enrol a cohort", f"Enrol {len(members)} student(s) on "
                             f"{self.current_code}?"):
                return
            result = self._do("Enrol a cohort", enrolment.bulk_enrol, self.current_code,
                              [m["student_id"] for m in members], self._selected_delivery_id(),
                              override=override.get(), waitlist_full=waitlist.get())
            if result is None:
                return
            self._audit("enrol_cohort", module_code=self.current_code,
                        course=_code_of(course.get()), enrolled=len(result["enrolled"]),
                        overridden=len(result["overridden"]))
            dialog.destroy()
            self._report_bulk(result)
            self.refresh_enrolments()
            self.refresh_modules()

        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(buttons, text="Enrol", command=run).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

    def _report_bulk(self, result):
        lines = [f"Enrolled: {len(result['enrolled'])}",
                 f"Already enrolled: {len(result['already'])}",
                 f"Put on the waitlist: {len(result['waitlisted'])}"]
        if result["overridden"]:
            lines.append(f"Enrolled by override: {len(result['overridden'])}")
        if result["blocked"]:
            lines.append(f"\nNot enrolled ({len(result['blocked'])}):")
            lines += [f"• {sid}: {why.splitlines()[0]}" for sid, why in result["blocked"][:15]]
            if len(result["blocked"]) > 15:
                lines.append(f"… and {len(result['blocked']) - 15} more")
        self._info("Enrol a cohort", "\n".join(lines))

    # ── waitlist ─────────────────────────────────────────────────────

    def _build_waitlist(self, tab):
        ttk.Label(tab, text="Waitlist:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 0))
        if self.can_manage:
            bar = ttk.Frame(tab)
            bar.pack(fill="x", **_PAD)
            ttk.Button(bar, text="Add chosen student",
                       command=self.join_waitlist).pack(side="left")
            ttk.Button(bar, text="Enrol selected", command=self.enrol_from_waitlist).pack(
                side="left", padx=2)
            ttk.Button(bar, text="Remove", command=self.remove_from_waitlist).pack(side="left")
            ttk.Button(bar, text="Fill free places", command=self.fill_places).pack(
                side="left", padx=2)
        self.waitlist_tree = _tree(tab, [("pos", "#"), ("id", "Student ID"), ("name", "Name"),
                                         ("added", "Added")], [40, 100, 200, 140], height=4)

    def refresh_waitlist(self):
        _clear(self.waitlist_tree)
        if not self.current_code:
            return
        for w in data.call(enrolment.waitlist, self.current_code):
            self.waitlist_tree.insert("", "end", iid=str(w["id"]), values=(
                w["position"], w["student_id"], w["name"] or "", w["added_at"]))

    def join_waitlist(self):
        if not self._require_module():
            return
        student_id = _code_of(self.student_combo.get())
        if not student_id:
            self._info("Waitlist", "Choose a student in the Student box first.")
            return
        position = self._do("Waitlist", enrolment.join_waitlist, self.current_code,
                            student_id, self._selected_delivery_id())
        if position:
            self._audit("waitlist_student", module_code=self.current_code, student_id=student_id)
            self._status(f"{student_id} is number {position} on the {self.current_code} waitlist")
            self.refresh_waitlist()

    def enrol_from_waitlist(self):
        sel = self.waitlist_tree.selection()
        if not self._require_module() or not sel:
            return
        if self._ask("Enrol from waitlist", "Enrol this student now, ahead of the queue "
                     "order? (a staff override)"):
            if self._do("Enrol from waitlist", enrolment.enrol_from_waitlist, self.current_code,
                        int(sel[0]), self.username):
                self._audit("enrol_from_waitlist", module_code=self.current_code)
            self.refresh_enrolments()
            self.refresh_modules()

    def remove_from_waitlist(self):
        sel = self.waitlist_tree.selection()
        if self._require_module() and sel and self._ask("Waitlist", "Remove from the waitlist?"):
            self._do("Waitlist", enrolment.remove_from_waitlist, int(sel[0]), self.username)
            self.refresh_waitlist()

    def fill_places(self):
        if not self._require_module():
            return
        promoted = self._do("Fill free places", enrolment.promote_all, self.current_code,
                            self.username)
        if promoted is not None:
            self._info("Fill free places", f"Enrolled from the waitlist: {', '.join(promoted)}"
                       if promoted else "No free place, or nobody waiting meets the rules.")
            self.refresh_enrolments()
            self.refresh_modules()
