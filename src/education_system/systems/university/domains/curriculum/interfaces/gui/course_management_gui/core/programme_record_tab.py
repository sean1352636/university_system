"""Programme Record — everything about a course as a degree programme.

One sidebar section with a course picker and eight tabs: Specification
(award, codes, mode, entry requirements, progression rule), Exit awards, Fees
& intake, Structure (stages with core / compulsory / optional and credit
totals), Curriculum map (programme outcomes → modules), Cohort (who is
actually on it), Results (continuation, completion, classifications, B3,
survey) and Governance & examiners (governance register, accreditation,
teach-out, versions, programme external examiners).

The rules are ``university/application/programmes/record`` and
``programme_structure``; governance actions call the Programme Governance
service.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk

from education_system.systems.university.application.modules import enrolment as module_enrolment
from education_system.systems.university.application.programmes import record
from education_system.systems.university.application.programmes import structure
from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.core.ext_common import (  # noqa: E501
    _, logger, messagebox,
)

_PAD = {"padx": 6, "pady": 3}
_SPEC_LABELS = (
    ("award_title", "Award title (e.g. BSc (Hons) Computer Science)"),
    ("ucas_code", "UCAS course code"), ("hecos_code", "HECoS subject code"),
    ("mode_of_study", "Mode of study"), ("awarding_body", "Awarding body"),
    ("campus", "Campus / location"), ("typical_offer", "Typical offer (e.g. ABB)"),
    ("required_subjects", "Required subjects"),
    ("english_requirement", "English language requirement"),
    ("pass_mark", "Module pass mark"), ("progression_credits", "Credits needed to progress"),
    ("max_compensated_credits", "Most credits that can be compensated"),
    ("compensation_min_mark", "Lowest mark that can be compensated"),
)


def _tree(parent, columns, widths, height=8, show="headings"):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, **_PAD)
    tree = ttk.Treeview(frame, columns=[c for c, _t in columns], show=show, height=height)
    for (key, title), width in zip(columns, widths):
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def _clear(tree):
    tree.delete(*tree.get_children())


class ProgrammeRecordTabMixin:
    """Mixin for CourseManagementGUI."""

    # ── plumbing ─────────────────────────────────────────────────────

    def _pr_call(self, title, fn, *args, write=False, **kwargs):
        """Run ``fn(conn, ...)``; show a refusal or failure instead of raising."""
        try:
            with self._ext_db(write=write) as conn:
                result = fn(conn, *args, **kwargs)
            # A rule that returns nothing succeeded: say so, so callers can
            # tell success (True) from a refusal or failure (None).
            return True if result is None else result
        except ValueError as exc:
            messagebox.showerror(title, str(exc), parent=self.root)
        except Exception as exc:
            self._ext_report_error(title.lower(), exc, title=title)
        return None

    def _pr_code(self, quiet=False):
        code = self._ext_code_from_label(self._pr_course.get(), getattr(self, "_pr_map", {}))
        if not code and not quiet:
            messagebox.showinfo("Programme Record", "Choose a course first.", parent=self.root)
        return code

    def create_programme_record_tab(self):
        outer = ttk.Frame(self.notebook)
        self.notebook.add(outer, text=_("course_management.tabs.programme_record",
                                        default="Programme Record"))
        top = ttk.Frame(outer)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Course:").pack(side="left")
        labels, self._pr_map = self._ext_course_choices()
        self._pr_course = ttk.Combobox(top, values=labels, width=40, state="readonly")
        self._pr_course.pack(side="left", padx=6)
        self._pr_course.bind("<<ComboboxSelected>>", lambda _e: self._pr_refresh())
        self._pr_edit = self._ext_can_edit()
        self._pr_notebook = ttk.Notebook(outer)
        self._pr_notebook.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        for build in (self._pr_build_spec, self._pr_build_awards, self._pr_build_fees,
                      self._pr_build_structure, self._pr_build_map, self._pr_build_cohort,
                      self._pr_build_results, self._pr_build_governance):
            try:
                build()
            except Exception:
                logger.exception("Programme Record: %s failed", build.__name__)

    def _pr_refresh(self):
        if not self._pr_code(quiet=True):
            return
        for refresh in (self._pr_load_spec, self._pr_load_awards, self._pr_load_fees,
                        self._pr_load_structure, self._pr_load_map, self._pr_load_cohort,
                        self._pr_load_results, self._pr_load_governance):
            try:
                refresh()
            except Exception:
                logger.exception("Programme Record: %s failed", refresh.__name__)

    def _pr_tab(self, title):
        tab = ttk.Frame(self._pr_notebook, padding=4)
        self._pr_notebook.add(tab, text=title)
        return tab

    def _pr_bar(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", **_PAD)
        return bar

    # ── specification ────────────────────────────────────────────────

    def _pr_build_spec(self):
        tab = self._pr_tab("Specification")
        form = ttk.Frame(tab)
        form.pack(fill="x", **_PAD)
        self._pr_spec_vars = {}
        for i, (key, label) in enumerate(_SPEC_LABELS):
            row, col = i % 7, (i // 7) * 2
            ttk.Label(form, text=label + ":").grid(row=row, column=col, sticky="w", padx=(8, 4),
                                                   pady=2)
            var = tk.StringVar()
            if key == "mode_of_study":
                widget = ttk.Combobox(form, textvariable=var, values=("",) + record.schema.MODES,
                                      width=24, state="readonly")
            else:
                widget = ttk.Entry(form, textvariable=var, width=26)
            widget.grid(row=row, column=col + 1, sticky="w", pady=2)
            self._pr_spec_vars[key] = var
        bar = self._pr_bar(tab)
        if self._pr_edit:
            ttk.Button(bar, text="Save specification", command=self._pr_save_spec).pack(side="left")
            ttk.Button(bar, text="Use the standard progression rule",
                       command=self._pr_standard_rule).pack(side="left", padx=4)
        ttk.Button(bar, text="Check a student's progression…",
                   command=self._pr_check_progression).pack(side="left", padx=4)
        self._pr_spec_note = tk.StringVar()
        ttk.Label(tab, textvariable=self._pr_spec_note, foreground="#555", wraplength=900,
                  justify="left").pack(anchor="w", padx=8)

    def _pr_load_spec(self):
        spec = self._pr_call("Specification", record.get_spec, self._pr_code()) or {}
        for key, var in self._pr_spec_vars.items():
            value = spec.get(key)
            var.set("" if value is None else (f"{value:g}" if isinstance(value, float) else value))
        self._pr_spec_note.set(
            f"Last changed by {spec['updated_by']} at {spec['updated_at']}" if spec.get("updated_by")
            else "Standard UK rule: pass mark 40, 120 credits to progress, up to 20 credits "
                 "compensated at marks of 30 or more.")

    def _pr_save_spec(self):
        code = self._pr_code()
        if not code:
            return
        values = {k: v.get() for k, v in self._pr_spec_vars.items()}
        changed = self._pr_call("Save specification", record.save_spec, code, values,
                                self._ext_username(), write=True)
        if changed is not None:
            self._ext_audit("save_programme_spec", "course", course_code=code,
                            fields=sorted(changed))
            self.update_status(f"{code}: {len(changed)} field(s) saved" if changed
                               else "Nothing changed")
            self._pr_load_spec()

    def _pr_standard_rule(self):
        code = self._pr_code()
        if code and self._pr_call("Progression rule", record.use_standard_progression, code,
                                  self._ext_username(), write=True) is not None:
            self._pr_load_spec()

    def _pr_ensure_progression_rule(self, code):
        """True once *code* has a rule, offering the standard one if it has none."""
        has_rule = self._pr_call("Progression", record.has_progression_rule, code)
        if has_rule is None:
            return False
        if has_rule:
            return True
        if not self._pr_edit:
            messagebox.showinfo(
                "Progression", f"{code} has no progression rule yet, so progression can't be "
                "checked. Ask someone who can edit this course to set one.", parent=self.root)
            return False
        rule = record.STANDARD_PROGRESSION
        if not messagebox.askyesno(
                "Progression",
                f"{code} has no progression rule yet.\n\nUse the standard UK rule? Pass mark "
                f"{rule['pass_mark']}, {rule['progression_credits']} credits to progress, up to "
                f"{rule['max_compensated_credits']} credits compensated at marks of "
                f"{rule['compensation_min_mark']} or more.\n\nYou can change it in the "
                "specification afterwards.", parent=self.root):
            return False
        if self._pr_call("Progression rule", record.fill_progression_rule, code,
                         self._ext_username(), write=True) is None:
            return False
        self._pr_load_spec()
        return True

    def _pr_check_progression(self):
        code = self._pr_code()
        if not code or not self._pr_ensure_progression_rule(code):
            return
        student = simpledialog.askstring("Progression", "Student ID:", parent=self.root)
        year = simpledialog.askinteger("Progression", "Which year (stage)?", parent=self.root,
                                       minvalue=0, maxvalue=7)
        if not student or year is None:
            return
        result = self._pr_call("Progression", record.progression, student.strip(), code, year)
        if result:
            messagebox.showinfo("Progression", (
                f"{student} — year {year}: {result['outcome'].upper()}\n\n"
                f"Credits passed {result['passed_credits']:g} of {result['required']}\n"
                f"Failed: {', '.join(result['failed']) or 'none'}\n"
                f"Marks outstanding: {', '.join(result['outstanding']) or 'none'}"),
                parent=self.root)

    # ── exit awards ──────────────────────────────────────────────────

    def _pr_build_awards(self):
        tab = self._pr_tab("Exit awards")
        if self._pr_edit:
            bar = self._pr_bar(tab)
            self._pr_award_vars = {k: tk.StringVar() for k in ("name", "total", "at", "level")}
            for key, label, width in (("name", "Award", 26), ("total", "Total credits", 5),
                                      ("at", "Credits at level", 5), ("level", "Level", 3)):
                ttk.Label(bar, text=label).pack(side="left")
                ttk.Entry(bar, textvariable=self._pr_award_vars[key], width=width).pack(
                    side="left", padx=(2, 6))
            self._pr_award_final = tk.BooleanVar()
            ttk.Checkbutton(bar, text="Final award", variable=self._pr_award_final).pack(
                side="left")
            ttk.Button(bar, text="Add", command=self._pr_add_award).pack(side="left", padx=4)
            bar2 = self._pr_bar(tab)
            ttk.Button(bar2, text="Remove selected", command=self._pr_remove_award).pack(
                side="left")
            ttk.Button(bar2, text="Add the standard UK awards",
                       command=self._pr_standard_awards).pack(side="left", padx=4)
        ttk.Button(self._pr_bar(tab), text="Which award has a student already earned?…",
                   command=self._pr_student_award).pack(side="left")
        self._pr_award_tree = _tree(tab, [("name", "Award"), ("total", "Total credits"),
                                          ("at", "At level"), ("final", "Final")],
                                    [300, 100, 160, 60])

    def _pr_load_awards(self):
        _clear(self._pr_award_tree)
        for a in self._pr_call("Exit awards", record.exit_awards, self._pr_code()) or []:
            self._pr_award_tree.insert("", "end", iid=str(a["id"]), values=(
                a["award_name"], a["total_credits"],
                f"{a['credits_at_level']} at level {a['at_level']}" if a["at_level"] else "—",
                "yes" if a["is_final"] else ""))

    def _pr_add_award(self):
        code = self._pr_code()
        v = {k: var.get() for k, var in self._pr_award_vars.items()}
        if code and self._pr_call("Add exit award", record.add_exit_award, code, v["name"],
                                  v["total"], v["at"], v["level"], self._pr_award_final.get(),
                                  write=True):
            for var in self._pr_award_vars.values():
                var.set("")
            self._pr_load_awards()

    def _pr_remove_award(self):
        sel = self._pr_award_tree.selection()
        if sel and self._pr_call("Remove exit award", record.remove_exit_award, int(sel[0]),
                                 write=True):
            self._pr_load_awards()

    def _pr_standard_awards(self):
        code = self._pr_code()
        added = code and self._pr_call("Exit awards", record.use_standard_exit_awards, code,
                                       write=True)
        if added is not None and code:
            self.update_status(f"{code}: {added} standard award(s) added")
            self._pr_load_awards()

    def _pr_student_award(self):
        code = self._pr_code()
        student = code and simpledialog.askstring("Exit award", "Student ID:", parent=self.root)
        if not student:
            return

        def check(conn):
            return (record.credits_by_level(conn, student.strip()),
                    record.eligible_exit_award(conn, student.strip(), code))
        result = self._pr_call("Exit award", check)
        if result:
            credit, award = result
            levels = ", ".join(f"level {k}: {v:g}" for k, v in sorted(
                (k, v) for k, v in credit.items() if k not in ("total", None)))
            messagebox.showinfo("Exit award", (
                f"{student}: {credit['total']:g} credits earned ({levels or 'none by level'}).\n\n"
                + (f"Already qualifies for: {award['award_name']}" if award
                   else "Does not yet qualify for any exit award.")), parent=self.root)

    # ── fees & intake ────────────────────────────────────────────────

    def _pr_build_fees(self):
        tab = self._pr_tab("Fees & intake")
        ttk.Label(tab, text="Tuition fees (held in Finance):",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        if self._pr_edit:
            bar = self._pr_bar(tab)
            self._pr_fee_year, self._pr_fee_amount = tk.StringVar(), tk.StringVar()
            ttk.Label(bar, text="Year (e.g. 2026/27)").pack(side="left")
            ttk.Entry(bar, textvariable=self._pr_fee_year, width=9).pack(side="left", padx=4)
            self._pr_fee_status = ttk.Combobox(bar, values=record.FEE_STATUSES, width=12,
                                               state="readonly")
            self._pr_fee_status.set("home")
            self._pr_fee_status.pack(side="left", padx=4)
            ttk.Label(bar, text="£").pack(side="left")
            ttk.Entry(bar, textvariable=self._pr_fee_amount, width=9).pack(side="left", padx=2)
            ttk.Button(bar, text="Set fee", command=self._pr_set_fee).pack(side="left", padx=4)
        self._pr_fee_tree = _tree(tab, [("year", "Year"), ("status", "Fee status"),
                                        ("amount", "Annual fee"), ("type", "Finance fee type")],
                                  [100, 110, 110, 260], height=4)
        ttk.Label(tab, text="Intake — target vs applications, offers and starters:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
        if self._pr_edit:
            bar = self._pr_bar(tab)
            self._pr_intake_year, self._pr_intake_target = tk.StringVar(), tk.StringVar()
            ttk.Label(bar, text="Year").pack(side="left")
            ttk.Entry(bar, textvariable=self._pr_intake_year, width=9).pack(side="left", padx=4)
            self._pr_intake_mode = ttk.Combobox(bar, values=record.schema.MODES, width=14,
                                                state="readonly")
            self._pr_intake_mode.set("full-time")
            self._pr_intake_mode.pack(side="left", padx=4)
            ttk.Label(bar, text="Target").pack(side="left")
            ttk.Entry(bar, textvariable=self._pr_intake_target, width=6).pack(side="left", padx=4)
            ttk.Button(bar, text="Set target", command=self._pr_set_target).pack(side="left")
        self._pr_intake_tree = _tree(tab, [("year", "Year"), ("target", "Target"),
                                           ("apps", "Applications"), ("offers", "Offers"),
                                           ("accepted", "Accepted"), ("started", "Started"),
                                           ("pct", "% of target")],
                                     [90, 70, 100, 70, 80, 70, 90], height=5)

    def _pr_load_fees(self):
        code = self._pr_code()
        _clear(self._pr_fee_tree)
        _clear(self._pr_intake_tree)
        for i, f in enumerate(self._pr_call("Fees", record.fees, code) or []):
            self._pr_fee_tree.insert("", "end", iid=str(i), values=(
                f["academic_year"], f["fee_status"], f"£{f['amount']:,.2f}", f["fee_name"] or ""))
        for i, r in enumerate(self._pr_call("Intake", record.intake_report, code) or []):
            self._pr_intake_tree.insert("", "end", iid=str(i), values=(
                r["academic_year"], "—" if r["target"] is None else r["target"], r["applications"],
                r["offers"], r["accepted"], r["started"],
                "—" if r["against_target"] is None else f"{r['against_target']}%"))

    def _pr_set_fee(self):
        code = self._pr_code()
        if code and self._pr_call("Set fee", record.set_fee, code, self._pr_fee_year.get(),
                                  self._pr_fee_status.get(), self._pr_fee_amount.get(),
                                  write=True):
            self._ext_audit("set_programme_fee", "course", course_code=code,
                            year=self._pr_fee_year.get(), fee_status=self._pr_fee_status.get())
            self._pr_load_fees()

    def _pr_set_target(self):
        code = self._pr_code()
        if code and self._pr_call("Intake target", record.set_intake_target, code,
                                  self._pr_intake_year.get(), self._pr_intake_target.get(),
                                  self._pr_intake_mode.get(), self._ext_username(),
                                  write=True):
            self._pr_load_fees()

    # ── structure ────────────────────────────────────────────────────

    def _pr_build_structure(self):
        tab = self._pr_tab("Structure")
        if self._pr_edit:
            bar = self._pr_bar(tab)
            ttk.Label(bar, text="Selected module is").pack(side="left")
            self._pr_designation = ttk.Combobox(bar, values=("core", "compulsory", "optional"),
                                                width=11, state="readonly")
            self._pr_designation.set("core")
            self._pr_designation.pack(side="left", padx=4)
            ttk.Label(bar, text="in year").pack(side="left")
            self._pr_designation_year = ttk.Spinbox(bar, from_=0, to=7, width=3)
            self._pr_designation_year.pack(side="left", padx=4)
            ttk.Button(bar, text="Set", command=self._pr_set_designation).pack(side="left")
        self._pr_structure_tree = _tree(
            tab, [("module", "Module"), ("name", "Name"), ("credits", "Credits"),
                  ("designation", "Designation")], [170, 300, 70, 140], height=16,
            show="tree headings")
        self._pr_structure_tree.column("#0", width=230)
        self._pr_structure_tree.tag_configure("issue", foreground="#b9770e")

    def _pr_load_structure(self):
        tree = self._pr_structure_tree
        _clear(tree)
        for s in self._pr_call("Structure", structure.stages, self._pr_code()) or []:
            head = (f"Year {s['year'] if s['year'] is not None else '?'} — required "
                    f"{s['required_credits']:g} / offered {s['offered_credits']:g} credits")
            parent = tree.insert("", "end", text=head, open=True,
                                 tags=("issue",) if s["issues"] else ())
            for issue in s["issues"]:
                tree.insert(parent, "end", text=f"⚠ {issue}", tags=("issue",))
            for m in s["modules"]:
                tree.insert(parent, "end", iid=f"m:{m['module_code']}:{s['year']}", text="",
                            values=(m["module_code"], m["module_name"], m["credits"],
                                    m["designation"] + ("" if m["active"] else " (retired)")))

    def _pr_set_designation(self):
        code = self._pr_code()
        sel = [i for i in self._pr_structure_tree.selection() if i.startswith("m:")]
        if not code or not sel:
            messagebox.showinfo("Structure", "Select a module row first.", parent=self.root)
            return
        module = sel[0].split(":")[1]
        if self._pr_call("Designation", module_enrolment.set_designation, module, code,
                         self._pr_designation.get(), self._pr_designation_year.get(),
                         self._ext_username(), write=True):
            self._pr_load_structure()

    # ── curriculum map ───────────────────────────────────────────────

    def _pr_build_map(self):
        tab = self._pr_tab("Curriculum map")
        ttk.Label(tab, foreground="#555", text=(
            "Which modules introduce, develop and assess each programme learning outcome. "
            "Programme outcomes are written on the Learning Outcomes page.")).pack(
            anchor="w", padx=8)
        if self._pr_edit:
            bar = self._pr_bar(tab)
            self._pr_map_outcome = ttk.Combobox(bar, width=30, state="readonly")
            self._pr_map_outcome.pack(side="left")
            self._pr_map_module = ttk.Combobox(bar, width=14, state="readonly")
            self._pr_map_module.pack(side="left", padx=4)
            ttk.Label(bar, text="Module outcome").pack(side="left")
            self._pr_map_lo = tk.StringVar()
            ttk.Entry(bar, textvariable=self._pr_map_lo, width=6).pack(side="left", padx=4)
            self._pr_map_cov = ttk.Combobox(bar, values=record.schema.COVERAGE, width=11,
                                            state="readonly")
            self._pr_map_cov.set("assessed")
            self._pr_map_cov.pack(side="left", padx=4)
            ttk.Button(bar, text="Map", command=self._pr_add_mapping).pack(side="left")
            ttk.Button(bar, text="Remove selected", command=self._pr_remove_mapping).pack(
                side="left", padx=4)
        self._pr_map_tree = _tree(tab, [("outcome", "Programme outcome"), ("module", "Module"),
                                        ("lo", "Module outcome"), ("coverage", "Coverage")],
                                  [320, 120, 120, 110], height=9)
        ttk.Label(tab, text="Gaps:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        self._pr_map_gaps = tk.Listbox(tab, height=5)
        self._pr_map_gaps.pack(fill="x", padx=8, pady=(0, 4))

    def _pr_load_map(self):
        _clear(self._pr_map_tree)
        self._pr_map_gaps.delete(0, "end")
        result = self._pr_call("Curriculum map", structure.curriculum_map, self._pr_code())
        if not result:
            return
        names = {o["id"]: f"{o['outcome_code'] or o['id']} — {o['description']}"
                 for o in result["outcomes"]}
        self._pr_outcome_ids = {label: oid for oid, label in names.items()}
        if self._pr_edit:
            self._pr_map_outcome["values"] = list(self._pr_outcome_ids)
            self._pr_map_module["values"] = result["modules"]
        for m in result["mappings"]:
            self._pr_map_tree.insert("", "end", iid=str(m["id"]), values=(
                names.get(m["outcome_id"], m["outcome_id"]), m["module_code"],
                m["module_outcome_code"] or "", m["coverage"]))
        for gap in result["gaps"] or (["No gaps: every outcome is assessed and every module "
                                       "serves one."] if result["outcomes"] else
                                      ["No programme outcomes yet."]):
            self._pr_map_gaps.insert("end", gap)

    def _pr_add_mapping(self):
        outcome = getattr(self, "_pr_outcome_ids", {}).get(self._pr_map_outcome.get())
        if not outcome or not self._pr_map_module.get():
            messagebox.showinfo("Curriculum map", "Choose an outcome and a module.",
                                parent=self.root)
            return
        if self._pr_call("Curriculum map", structure.map_outcome, outcome,
                         self._pr_map_module.get(), self._pr_map_cov.get(),
                         self._pr_map_lo.get().strip().upper(), write=True):
            self._pr_load_map()

    def _pr_remove_mapping(self):
        sel = self._pr_map_tree.selection()
        if sel and self._pr_call("Curriculum map", structure.unmap, int(sel[0]), write=True):
            self._pr_load_map()

    # ── cohort ───────────────────────────────────────────────────────

    def _pr_build_cohort(self):
        tab = self._pr_tab("Cohort")
        self._pr_cohort_note = tk.StringVar()
        ttk.Label(tab, textvariable=self._pr_cohort_note, foreground="#555", wraplength=900,
                  justify="left").pack(anchor="w", padx=8)
        if self._pr_edit:
            bar = self._pr_bar(tab)
            ttk.Button(bar, text="Correct every course's stored count",
                       command=self._pr_fix_counts).pack(side="left")
            ttk.Button(bar, text="File students under course codes…",
                       command=self._pr_fix_names).pack(side="left", padx=4)
        self._pr_cohort_tree = _tree(tab, [("id", "Student"), ("name", "Name"),
                                           ("filed", "Filed as"), ("year", "Year"),
                                           ("status", "Status"), ("reg", "Registration"),
                                           ("started", "Started")],
                                     [90, 170, 130, 50, 90, 110, 120], height=14)

    def _pr_load_cohort(self):
        code = self._pr_code()
        _clear(self._pr_cohort_tree)
        rows = self._pr_call("Cohort", structure.cohort, code) or []
        for r in rows:
            self._pr_cohort_tree.insert("", "end", iid=r["student_id"], values=(
                r["student_id"], r["name"], r["filed_as"], r["year_of_study"] or "",
                r["status"], r["registration"], str(r["started"] or "")[:10]))
        counts = self._pr_call("Cohort", structure.live_counts) or {}
        actual, stored = counts.get(code, (0, 0))
        names = sum(1 for r in rows if r["filed_as"] != code)
        self._pr_cohort_note.set(
            f"{actual} active student(s) of {len(rows)} on record. Stored count says {stored}"
            + (" — out of date." if stored != actual else ".")
            + (f"  {names} filed under the course name rather than {code}." if names else ""))

    def _pr_fix_counts(self):
        changed = self._pr_call("Counts", structure.refresh_counters, write=True)
        if changed is not None:
            self._ext_audit("refresh_course_counts", "course", changed=changed)
            self.update_status(f"Stored counts corrected on {changed} course(s)")
            self._pr_load_cohort()

    def _pr_fix_names(self):
        plan = self._pr_call("Course names", structure.name_fix_plan)
        if not plan:
            return
        lines = [f"• {sid}: '{was}' → {code}" for sid, was, code in plan["fix"]]
        unknown = [f"• {sid}: '{was}' matches no course" for sid, was in plan["unknown"]]
        if not plan["fix"]:
            messagebox.showinfo("Course names", "Nothing to change.\n\n" + "\n".join(unknown),
                                parent=self.root)
            return
        if messagebox.askyesno("Course names", "\n".join(lines) + (
                "\n\nThese need fixing by hand:\n" + "\n".join(unknown) if unknown else "")
                + "\n\nFile these students under the course code?", parent=self.root):
            done = self._pr_call("Course names", structure.apply_name_fix, plan, write=True)
            self._ext_audit("file_students_under_course_code", "course", changed=done)
            self.update_status(f"{done} student record(s) updated")
            self._pr_load_cohort()

    # ── results ──────────────────────────────────────────────────────

    def _pr_build_results(self):
        tab = self._pr_tab("Results")
        ttk.Label(tab, text="By entry year:", font=("Segoe UI", 10, "bold")).pack(anchor="w",
                                                                                  padx=8)
        self._pr_outcome_tree = _tree(tab, [("year", "Entry year"), ("n", "Started"),
                                            ("cont", "Continuing"), ("done", "Completed"),
                                            ("left", "Left"), ("cpct", "Continuation"),
                                            ("comp", "Completion")],
                                      [90, 70, 90, 90, 60, 100, 100], height=4)
        self._pr_class_var = tk.StringVar()
        ttk.Label(tab, textvariable=self._pr_class_var, justify="left").pack(anchor="w", padx=8)
        ttk.Label(tab, text="OfS B3 (from External Quality Assurance):",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
        self._pr_b3_tree = _tree(tab, [("year", "Cohort"), ("metric", "Measure"),
                                       ("value", "Value"), ("of", "n / N")],
                                 [80, 160, 80, 100], height=3)
        ttk.Label(tab, text="Student survey:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(6, 0))
        if self._pr_edit:
            bar = self._pr_bar(tab)
            self._pr_survey = {k: tk.StringVar() for k in ("year", "theme", "pct", "n")}
            for key, label, width in (("year", "Year", 8), ("theme", "Theme", 24),
                                      ("pct", "% agree", 5), ("n", "Respondents", 5)):
                ttk.Label(bar, text=label).pack(side="left")
                ttk.Entry(bar, textvariable=self._pr_survey[key], width=width).pack(
                    side="left", padx=(2, 6))
            ttk.Button(bar, text="Record", command=self._pr_add_survey).pack(side="left")
        self._pr_survey_tree = _tree(tab, [("survey", "Survey"), ("year", "Year"),
                                           ("theme", "Theme"), ("pct", "% agree"),
                                           ("n", "Respondents")],
                                     [70, 80, 260, 80, 90], height=4)

    def _pr_load_results(self):
        code = self._pr_code()
        for tree in (self._pr_outcome_tree, self._pr_b3_tree, self._pr_survey_tree):
            _clear(tree)
        for i, r in enumerate(self._pr_call("Results", structure.cohort_outcomes, code) or []):
            self._pr_outcome_tree.insert("", "end", iid=str(i), values=(
                r["entry_year"], r["started"], r["continuing"], r["completed"], r["left"],
                f"{r['continuation_pct']}%",
                "too early" if r["completion_pct"] is None else f"{r['completion_pct']}%"))
        cls = self._pr_call("Results", structure.classifications, code) or {"total": 0}
        self._pr_class_var.set(
            "Degree classifications: " + (", ".join(f"{k} {v}" for k, v in cls["counts"].items())
                                          + f"   ·   good honours {cls['good_honours_pct']}%"
                                          if cls["total"] else "no ratified awards yet."))
        for i, b in enumerate(self._pr_call("Results", structure.b3_metrics, code) or []):
            self._pr_b3_tree.insert("", "end", iid=str(i), values=(
                b["cohort_year"], b["metric_type"], f"{b['value_pct']:.1f}%",
                f"{b['numerator']} / {b['denominator']}"))
        for i, s in enumerate(self._pr_call("Results", record.survey_results, code) or []):
            self._pr_survey_tree.insert("", "end", iid=str(i), values=(
                s["survey"], s["academic_year"], s["theme"], f"{s['agree_pct']:g}%",
                s["respondents"] or ""))

    def _pr_add_survey(self):
        code = self._pr_code()
        v = {k: var.get() for k, var in self._pr_survey.items()}
        if code and self._pr_call("Survey", record.set_survey_result, code, v["year"], v["theme"],
                                  v["pct"], v["n"], write=True):
            self._pr_load_results()

    # ── governance & examiners ───────────────────────────────────────

    def _pr_build_governance(self):
        tab = self._pr_tab("Governance & examiners")
        self._pr_gov_var = tk.StringVar()
        ttk.Label(tab, textvariable=self._pr_gov_var, justify="left", wraplength=900).pack(
            anchor="w", padx=8, pady=4)
        if self._pr_edit:
            bar = self._pr_bar(tab)
            for label, command in (("Register for governance", self._pr_register),
                                   ("Record accreditation…", self._pr_accreditation),
                                   ("Teach-out plan…", self._pr_teach_out),
                                   ("New version for a year…", self._pr_new_version)):
                ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
        self._pr_gov_tree = _tree(tab, [("what", "Record"), ("detail", "Detail"),
                                        ("status", "Status")], [140, 520, 120], height=6)
        ttk.Label(tab, text="Programme external examiners:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
        if self._pr_edit:
            bar = self._pr_bar(tab)
            self._pr_exam_combo = ttk.Combobox(bar, width=30, state="readonly")
            self._pr_exam_combo.pack(side="left")
            self._pr_exam = {k: tk.StringVar() for k in ("from", "to", "due")}
            for key, label in (("from", "From"), ("to", "To"), ("due", "Report due")):
                ttk.Label(bar, text=label).pack(side="left", padx=(6, 0))
                ttk.Entry(bar, textvariable=self._pr_exam[key], width=10).pack(side="left", padx=2)
            ttk.Button(bar, text="Appoint", command=self._pr_appoint).pack(side="left", padx=4)
            bar2 = self._pr_bar(tab)
            ttk.Button(bar2, text="Record annual report…", command=self._pr_report).pack(
                side="left")
            ttk.Button(bar2, text="Record our response…", command=self._pr_response).pack(
                side="left", padx=4)
        self._pr_exam_tree = _tree(tab, [("name", "Examiner"), ("term", "Term of office"),
                                         ("report", "Report"), ("response", "Response")],
                                   [200, 190, 220, 200], height=4)

    def _pr_load_governance(self):
        code = self._pr_code()
        _clear(self._pr_gov_tree)
        _clear(self._pr_exam_tree)
        pid = self._pr_call("Governance", record.governed_id, code)
        self._pr_gov_id = pid
        if pid:
            from education_system.systems.university.domains.curriculum.domain.programme_governance import (  # noqa: E501
                service as governance,
            )
            try:
                rec = governance.programme_record(pid)
            except Exception as exc:
                self._pr_gov_var.set(f"Governance record unavailable: {exc}")
                rec = None
            if rec:
                self._pr_gov_var.set(f"On the governance register — status {rec['status']}.")
                rows = ([("Version", f"v{v['version_number']} from {v['effective_academic_year']}",
                          v["status"]) for v in rec["versions"]]
                        + [("Accreditation", f"{a['body_name']} {a['accreditation_reference'] or ''}"
                            f" until {a['valid_until'] or 'open'}", a["status"])
                           for a in rec["accreditations"]]
                        + [("Teach-out", f"last intake {t['last_intake_year']}, final delivery "
                            f"{t['final_delivery_year']}", t["status"])
                           for t in rec["teach_out_plans"]])
                for i, row in enumerate(rows):
                    self._pr_gov_tree.insert("", "end", iid=str(i), values=row)
        else:
            self._pr_gov_var.set("Not on the governance register yet: versions, validation, "
                                 "accreditation and teach-out plans need it. Use 'Register for "
                                 "governance'.")
        if self._pr_edit:
            from education_system.systems.university.application.modules import (
                delivery as module_delivery,
            )
            self._pr_examiners = {f"{e['name']} ({e['institution'] or ''})": e["examiner_id"]
                                  for e in self._pr_call("Examiners",
                                                         module_delivery.examiner_choices) or []}
            self._pr_exam_combo["values"] = list(self._pr_examiners)
        for e in self._pr_call("Examiners", record.examiners, code) or []:
            report = ("OVERDUE (due " + e["report_due"] + ")" if e["report_overdue"]
                      else e["report_summary"] or (f"due {e['report_due']}" if e["report_due"]
                                                   else "—"))
            response = e["response"] or ("outstanding" if e["response_outstanding"] else "—")
            self._pr_exam_tree.insert("", "end", iid=str(e["id"]), values=(
                e["name"], f"{e['appointed_from']} → {e['appointed_to']}"
                + (" (current)" if e["current"] else ""), report, response))

    def _pr_register(self):
        code = self._pr_code()
        if code and self._pr_call("Governance", record.register_for_governance, code,
                                  self._ext_username(), write=True):
            self._pr_load_governance()

    def _pr_require_governed(self):
        if not getattr(self, "_pr_gov_id", None):
            messagebox.showinfo("Governance", "Register the course for governance first.",
                                parent=self.root)
            return None
        from education_system.systems.university.domains.curriculum.domain.programme_governance import (  # noqa: E501
            service as governance,
        )
        return governance

    def _pr_ask(self, title, prompts):
        values = {}
        for key, prompt in prompts:
            value = simpledialog.askstring(title, prompt, parent=self.root)
            if value is None:
                return None
            values[key] = value.strip()
        return values

    def _pr_governance_call(self, title, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except ValueError as exc:
            messagebox.showerror(title, str(exc), parent=self.root)
            return False
        except Exception as exc:
            self._ext_report_error(title.lower(), exc, title=title)
            return False
        self._pr_load_governance()
        return True

    def _pr_accreditation(self):
        governance = self._pr_require_governed()
        v = governance and self._pr_ask("Accreditation", (
            ("body", "Professional / accrediting body (e.g. BCS):"),
            ("status", "Status (accredited, provisional, applied, lapsed):"),
            ("ref", "Reference:"), ("until", "Valid until (YYYY-MM-DD):")))
        if v and v["body"]:
            self._pr_governance_call("Accreditation", governance.record_accreditation,
                                     self._pr_gov_id, v["body"], v["status"] or "accredited",
                                     accreditation_reference=v["ref"],
                                     valid_until=v["until"] or None)

    def _pr_teach_out(self):
        governance = self._pr_require_governed()
        v = governance and self._pr_ask("Teach-out plan", (
            ("last", "Last intake year (e.g. 2026/27):"),
            ("final", "Final year of delivery (e.g. 2029/30):"),
            ("comms", "What students are told / promised:"),
            ("staff", "Staffing commitment:")))
        if v and v["last"] and v["final"] and v["comms"]:
            modules = {f"year {s['year']}": [m["module_code"] for m in s["modules"]]
                       for s in self._pr_call("Structure", structure.stages,
                                              self._pr_code()) or []}
            if self._pr_governance_call("Teach-out plan", governance.create_teach_out,
                                        self._pr_gov_id, version_id=None,
                                        last_intake_year=v["last"], final_delivery_year=v["final"],
                                        student_communication=v["comms"],
                                        staffing_commitment=v["staff"] or "",
                                        module_availability=modules,
                                        approved_by=self._ext_username()):
                self._ext_audit("create_teach_out", "course", course_code=self._pr_code())

    def _pr_new_version(self):
        governance = self._pr_require_governed()
        year = governance and simpledialog.askstring(
            "New version", "Effective from academic year (e.g. 2027/28):", parent=self.root)
        code = self._pr_code()
        if not year or not code:
            return

        def snapshot(conn):
            curriculum = {f"year {s['year']}": [
                {k: m[k] for k in ("module_code", "credits", "designation")}
                for m in s["modules"]] for s in structure.stages(conn, code)}
            regulations = {"specification": record.get_spec(conn, code),
                           "exit_awards": record.exit_awards(conn, code)}
            return curriculum, regulations
        parts = self._pr_call("New version", snapshot)
        if parts and self._pr_governance_call(
                "New version", governance.create_version, self._pr_gov_id, year.strip(),
                curriculum=parts[0], regulations=parts[1], created_by=self._ext_username()):
            messagebox.showinfo("New version", "Draft version created from the current structure "
                                "and rules. Validate and approve it in Programme Governance.",
                                parent=self.root)

    def _pr_appoint(self):
        code = self._pr_code()
        examiner = getattr(self, "_pr_examiners", {}).get(self._pr_exam_combo.get())
        if not examiner:
            messagebox.showinfo("External examiner", "Choose an examiner (add new ones in "
                                "External Examiners).", parent=self.root)
            return
        v = {k: var.get() for k, var in self._pr_exam.items()}
        if code and self._pr_call("External examiner", record.appoint_examiner, code, examiner,
                                  v["from"], v["to"], v["due"] or None, write=True):
            self._pr_load_governance()

    def _pr_selected_appointment(self):
        sel = self._pr_exam_tree.selection()
        if not sel:
            messagebox.showinfo("External examiner", "Select an appointment.", parent=self.root)
        return int(sel[0]) if sel else None

    def _pr_report(self):
        appointment = self._pr_selected_appointment()
        summary = appointment and simpledialog.askstring(
            "Annual report", "Summary of the examiner's report:", parent=self.root)
        if summary and self._pr_call("Annual report", record.record_report, appointment,
                                     summary, write=True):
            self._pr_load_governance()

    def _pr_response(self):
        appointment = self._pr_selected_appointment()
        response = appointment and simpledialog.askstring(
            "Response", "The programme team's response:", parent=self.root)
        if response and self._pr_call("Response", record.record_response, appointment, response,
                                      self._ext_username(), write=True):
            self._pr_load_governance()
