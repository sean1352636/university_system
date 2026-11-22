"""The Module Management window.

Left: the module catalogue. Right: tabs about the selected module —
Overview, Spec (specification and learning outcomes), Programmes (with
core / compulsory / optional designations), Rules (prerequisites and
exclusions), Enrolments (deliveries, waitlist, cohorts), Delivery (terms and
timetable), Team (staff, workload, external examiners), Assessment (plan and
marks), Feedback (student evaluations) and History (change requests and the
change log). Catalogue-wide actions sit in the top bar.

Permissions
-----------
* ``manage_modules`` — everything.
* ``assign_instructors`` — may change a module's teaching team and examiners.
* A module's leader — may propose changes to its details and specification
  (a manager approves them) and edit its learning outcomes and assessment plan.
* ``view_assigned_modules`` alone — otherwise read-only, and the catalogue is
  limited to the modules the user teaches.
"""

from __future__ import annotations

import logging
import tkinter as tk

from education_system.systems.university.application.modules import enrolment as enrolment_rules
from tkinter import filedialog, messagebox, ttk

from education_system.systems.university.domains.curriculum.interfaces.gui.module_management import (
    data,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management._widgets import (  # noqa: E501
    _PAD, _clear, _code_of, _tree,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management.tabs_delivery import (  # noqa: E501
    DeliveryTabs,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management.tabs_enrol import (  # noqa: E501
    EnrolmentTabs,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management.tabs_spec import (  # noqa: E501
    SpecificationTabs,
)

logger = logging.getLogger(__name__)


class ModuleManagementGUI(SpecificationTabs, EnrolmentTabs, DeliveryTabs):
    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth
        user = getattr(auth, "current_user", None) or {}
        self.username = (user.get("username") if isinstance(user, dict)
                         else getattr(user, "username", None))
        self.can_manage = self._has("manage_modules")
        self.can_assign = self.can_manage or self._has("assign_instructors")
        self.mine_only = not self.can_manage
        self.current_code: str | None = None

        self._build()
        self.refresh_modules()

    # ------------------------------------------------------------------ utils

    def _has(self, permission):
        try:
            return bool(self.auth and self.auth.check_permission(permission))
        except Exception:
            logger.debug("permission check failed for %s", permission, exc_info=True)
            return False

    def _info(self, title, text):
        messagebox.showinfo(title, text, parent=self.root)

    def _error(self, title, text):
        messagebox.showerror(title, text, parent=self.root)

    def _ask(self, title, text):
        return messagebox.askyesno(title, text, parent=self.root)

    def _status(self, text):
        self.status_var.set(text)

    def _audit(self, action, **details):
        try:
            from education_system.systems.university.infrastructure.activity_logger import (
                log_activity,
            )
            log_activity(action, "module_management",
                         details=dict(details, user=self.username))
        except Exception:
            logger.debug("activity log unavailable", exc_info=True)

    def _require_module(self):
        if not self.current_code:
            self._info("No module selected", "Select a module in the list first.")
            return False
        return True

    def _run(self, title, fn, *args, **kwargs):
        """Call a data function, turning a failure into an error dialog."""
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            self._error(title, str(exc))
        except Exception as exc:
            logger.exception("%s failed", title)
            self._error(title, f"{title} failed: {exc}")
        return None

    def _do(self, title, fn, *args, **kwargs):
        """Run an application rule ``fn(conn, ...)`` in its own transaction."""
        return self._run(title, data.call, fn, *args, **kwargs)

    # ------------------------------------------------------------------ layout

    def _build(self):
        # Bars first, so the expanding panes below cannot push them off-screen.
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Module Management", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh_modules).pack(side="right", padx=3)
        if self.can_manage:
            ttk.Button(top, text="Fill credits & levels",
                       command=self.fill_credits_levels).pack(side="right", padx=3)
            ttk.Button(top, text="Validate data", command=self.validate).pack(side="right", padx=3)
            ttk.Button(top, text="Import CSV", command=self.import_csv).pack(side="right", padx=3)
        ttk.Button(top, text="Export CSV", command=self.export_csv).pack(side="right", padx=3)
        ttk.Button(top, text="Module report", command=self.show_report).pack(side="right", padx=3)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 2)).pack(side="bottom", fill="x")

        panes = tk.PanedWindow(self.root, orient="horizontal", sashwidth=6)
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, minsize=340, width=440)
        panes.add(right, minsize=600)

        self._build_catalogue(left)

        self.header_var = tk.StringVar(value="Select a module")
        ttk.Label(right, textvariable=self.header_var,
                  font=("Segoe UI", 13, "bold"), padding=(10, 8)).pack(fill="x")
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._build_overview()
        self._build_specification()
        self._build_programmes()
        self._build_prerequisites()
        self._build_enrolments()
        self._build_delivery()
        self._build_team()
        self._build_assessment()
        self._build_feedback()
        self._build_history()

    # ------------------------------------------------------------------ catalogue

    def _build_catalogue(self, parent):
        filters = ttk.Frame(parent)
        filters.pack(fill="x", **_PAD)
        ttk.Label(filters, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_modules())
        ttk.Entry(filters, textvariable=self.search_var, width=22).pack(side="left", padx=4)
        self.show_retired_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text="Show retired", variable=self.show_retired_var,
                        command=self.refresh_modules).pack(side="left", padx=4)
        self.mine_var = tk.BooleanVar(value=self.mine_only)
        mine = ttk.Checkbutton(filters, text="My modules", variable=self.mine_var,
                               command=self.refresh_modules)
        mine.pack(side="left", padx=4)
        if self.mine_only:
            mine.state(["disabled"])

        if self.can_manage:
            actions = ttk.Frame(parent)
            actions.pack(fill="x", **_PAD)
            ttk.Button(actions, text="Add module", command=self.add_module).pack(side="left", padx=2)
            ttk.Button(actions, text="Edit", command=self.edit_module).pack(side="left", padx=2)
            self.retire_btn = ttk.Button(actions, text="Retire", command=self.toggle_retired)
            self.retire_btn.pack(side="left", padx=2)

        self.count_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.count_var, foreground="#666").pack(anchor="w", padx=8)

        self.modules_tree = _tree(
            parent,
            [("code", "Code"), ("name", "Name"), ("credits", "Credits"),
             ("type", "Type"), ("enrolled", "Enrolled")],
            [90, 220, 60, 90, 70], height=25)
        self.modules_tree.tag_configure("retired", foreground="#999")
        self.modules_tree.tag_configure("no_credits", foreground="#b9770e")
        self.modules_tree.bind("<<TreeviewSelect>>", self._on_select)
        if self.can_manage:
            self.modules_tree.bind("<Double-1>", lambda _e: self.edit_module())

    def refresh_modules(self):
        instructor = self.username if self.mine_var.get() else None
        if self.mine_var.get() and not self.username:
            modules = []
        else:
            modules = self._run("Load modules", data.list_modules,
                                self.search_var.get().strip(),
                                include_inactive=self.show_retired_var.get(),
                                instructor=instructor) or []
        keep = self.current_code
        _clear(self.modules_tree)
        for m in modules:
            tags = ()
            if not m["is_active"]:
                tags = ("retired",)
            elif not m["credits"]:
                tags = ("no_credits",)
            self.modules_tree.insert(
                "", "end", iid=m["module_code"], tags=tags,
                values=(m["module_code"], m["module_name"] or "",
                        m["credits"] if m["credits"] is not None else "",
                        m["module_type"] or "", m["enrolled"]))
        self.count_var.set(f"{len(modules)} module(s)"
                           + ("  ·  amber = no credit value" if modules else ""))
        if keep and self.modules_tree.exists(keep):
            self.modules_tree.selection_set(keep)
            self.modules_tree.see(keep)
        else:
            self._select(None)

    def _on_select(self, _event=None):
        sel = self.modules_tree.selection()
        self._select(sel[0] if sel else None)

    def _select(self, code):
        self.current_code = code
        module = data.get_module(code) if code else None
        if code and module is None:
            self.current_code = None
        if module:
            self.header_var.set(f"{module['module_code']} — {module['module_name'] or ''}"
                                + ("   (retired)" if not module["is_active"] else ""))
        else:
            self.header_var.set("Select a module")
        if self.can_manage:
            self.retire_btn.configure(
                text="Reinstate" if module and not module["is_active"] else "Retire")
        self._fill_overview(module)
        for refresh in (self.refresh_specification, self.refresh_programmes,
                        self.refresh_prerequisites, self.refresh_exclusions,
                        self.refresh_enrolments, self.refresh_delivery, self.refresh_team,
                        self.refresh_assessment, self.refresh_feedback, self.refresh_history):
            try:
                refresh()
            except Exception:
                logger.exception("refreshing %s failed", refresh.__name__)
        if code:
            try:
                from education_system.systems.university.services.bus.academic_state import (
                    set_current_selection,
                )
                set_current_selection(module_code=code, source="module_management")
            except Exception:
                logger.debug("selection broadcast unavailable", exc_info=True)

    def add_module(self):
        from education_system.systems.university.infrastructure.ui.module_dialog import (
            open_module_dialog,
        )

        def saved(code):
            self._audit("add_module", module_code=code)
            self.current_code = code
            self.refresh_modules()
            self._status(f"Added {code}")
        open_module_dialog(self.root, mode="add", on_saved=saved)

    def edit_module(self):
        if not self._require_module():
            return
        from education_system.systems.university.infrastructure.ui.module_dialog import (
            open_module_dialog,
        )

        def saved(code):
            self._audit("edit_module", module_code=code)
            self.refresh_modules()
            self._select(code)
            self._status(f"Saved {code}")
        open_module_dialog(self.root, mode="edit", module_code=self.current_code,
                           on_saved=saved, actor=self.username)

    def propose_module_change(self):
        """A module leader's route to changing the module's details."""
        if not self._require_module() or not self._leads_current():
            return
        from education_system.systems.university.infrastructure.ui.module_dialog import (
            open_module_dialog,
        )
        open_module_dialog(self.root, mode="propose", module_code=self.current_code,
                           actor=self.username)
        self.refresh_history()

    def fill_credits_levels(self):
        from education_system.systems.university.application.modules import (
            delivery as module_delivery,
        )
        plan = self._do("Fill credits & levels", module_delivery.fill_plan)
        if plan is None:
            return
        if not plan:
            self._info("Fill credits & levels", "Every active module already has credits "
                       "and a level, or there is nothing to derive them from.")
            return
        credits = sum(1 for p in plan if "credits" in p)
        levels = sum(1 for p in plan if "level" in p)
        sample = "\n".join(f"• {p['module_code']}: "
                           + ", ".join(f"{k} {p[k]}" for k in ("credits", "level") if k in p)
                           for p in plan[:8])
        if not self._ask("Fill credits & levels", (
                f"{credits} module(s) get credits and {levels} get an FHEQ level.\n\n"
                "Credits = the programme's total ÷ its number of modules (the rule Academic "
                "Progress uses); level = year of study + 3.\n\n" + sample
                + ("\n…" if len(plan) > 8 else "") + "\n\nEvery change is recorded in "
                "each module's history. Go ahead?")):
            return
        done = self._do("Fill credits & levels", module_delivery.apply_fill, plan, self.username)
        if done is not None:
            self._audit("fill_module_credits_levels", modules=done)
            self._info("Fill credits & levels", f"Updated {done} module(s).")
            self.refresh_modules()

    def toggle_retired(self):
        if not self._require_module():
            return
        module = data.get_module(self.current_code)
        if module is None:
            return
        code = module["module_code"]
        if module["is_active"]:
            if not self._ask("Retire module",
                             f"Retire {code}?\n\nIt stays on record with its enrolments, "
                             "grades and schedule, but is hidden from the catalogue "
                             "unless 'Show retired' is ticked."):
                return
            done = self._run("Retire module", data.set_active, code, False)
            verb = "Retired"
        else:
            done = self._run("Reinstate module", data.set_active, code, True)
            verb = "Reinstated"
        if done:
            self._audit(verb.lower() + "_module", module_code=code)
            if not self.show_retired_var.get() and verb == "Retired":
                self.current_code = None
            self.refresh_modules()
            self._status(f"{verb} {code}")

    # ------------------------------------------------------------------ overview

    def _build_overview(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Overview")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        if self.can_manage:
            ttk.Button(bar, text="Edit details", command=self.edit_module).pack(side="left")
        else:
            ttk.Button(bar, text="Propose a change (module leader)",
                       command=self.propose_module_change).pack(side="left")
        grid = ttk.Frame(tab)
        grid.pack(fill="x")
        self.overview_vars = {}
        fields = [("module_code", "Code"), ("module_name", "Name"),
                  ("module_type", "Type"), ("credits", "Credits"),
                  ("level", "FHEQ level"),
                  ("semester", "Semester"), ("year", "Year of study"),
                  ("course", "Course"), ("department", "Department"),
                  ("instructor", "Module leader"),
                  ("capacity", "Capacity"), ("enrolled", "Enrolled"),
                  ("is_active", "Status")]
        for row, (key, label) in enumerate(fields):
            ttk.Label(grid, text=label + ":", foreground="#555").grid(
                row=row, column=0, sticky="w", pady=2, padx=(0, 12))
            var = tk.StringVar()
            ttk.Label(grid, textvariable=var).grid(row=row, column=1, sticky="w", pady=2)
            self.overview_vars[key] = var
        ttk.Label(tab, text="Description:", foreground="#555").pack(anchor="w", pady=(10, 2))
        self.description = tk.Text(tab, height=8, wrap="word", relief="flat",
                                   background="#f7f7f7")
        self.description.pack(fill="both", expand=True)
        self.description.configure(state="disabled")

    def _fill_overview(self, module):
        for key, var in self.overview_vars.items():
            value = module.get(key) if module else ""
            if module and key == "credits" and not value:
                value = "0 — not set"
            elif module and key == "is_active":
                value = "Active" if value else "Retired"
            elif module and key == "capacity" and not value:
                value = "Uncapped"
            elif module and key == "instructor" and not value:
                value = "Unassigned"
            elif module and key == "level" and not value:
                value = "not set"
            var.set("" if value is None else str(value))
        self.description.configure(state="normal")
        self.description.delete("1.0", "end")
        if module and module.get("description"):
            self.description.insert("1.0", module["description"])
        self.description.configure(state="disabled")

    # ------------------------------------------------------------------ programmes

    def _build_programmes(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Programmes")
        if self.can_manage:
            bar = ttk.Frame(tab)
            bar.pack(fill="x", **_PAD)
            ttk.Label(bar, text="Course:").pack(side="left")
            self.course_combo = ttk.Combobox(bar, width=40)
            self.course_combo.pack(side="left", padx=4)
            ttk.Button(bar, text="Link", command=self.link_programme).pack(side="left", padx=2)
            ttk.Button(bar, text="Unlink selected",
                       command=self.unlink_programme).pack(side="left", padx=2)
        if self.can_manage:
            self._build_designation_bar(tab)
        else:
            self.designation_note_var = tk.StringVar()
        ttk.Label(tab, foreground="#666", text=(
            "Links from the course curriculum or the module record are shown for "
            "reference; change those where they live.")).pack(anchor="w", padx=8)
        self.programmes_tree = _tree(
            tab, [("code", "Course code"), ("name", "Course name"),
                  ("designation", "Designation"), ("source", "Linked by")],
            [100, 220, 130, 200])

    def refresh_programmes(self):
        _clear(self.programmes_tree)
        if self.can_manage and not self.course_combo["values"]:
            courses = self._run("Load courses", data.course_choices) or []
            self.course_combo["values"] = [f"{c['code']} - {c['name'] or ''}" for c in courses]
        if not self.current_code:
            return
        self._programmes = data.list_programmes(self.current_code)
        designated = self._designations_for_tree()
        for i, p in enumerate(self._programmes):
            self.programmes_tree.insert("", "end", iid=str(i), values=(
                p["course_code"], p["course_name"],
                designated.get(p["course_code"], "not designated"), p["source"]))
        self._refresh_designation_note()

    def link_programme(self):
        if not self._require_module():
            return
        course = _code_of(self.course_combo.get())
        if not course:
            self._info("Link programme", "Choose a course first.")
            return
        added = self._run("Link programme", data.add_programme, self.current_code, course)
        if added is None:
            return
        if added:
            self._audit("link_programme", module_code=self.current_code, course_code=course)
            self._status(f"Linked {self.current_code} to {course}")
        else:
            self._info("Link programme", f"{self.current_code} is already linked to {course}.")
        self.refresh_programmes()

    def unlink_programme(self):
        sel = self.programmes_tree.selection()
        if not self._require_module() or not sel:
            return
        link = self._programmes[int(sel[0])]
        if not link["removable"]:
            self._info("Unlink programme",
                       f"This link comes from the {link['source']}. Change it there "
                       "(Course Management, or the module's Course field).")
            return
        if not self._ask("Unlink programme",
                         f"Remove the link between {self.current_code} and {link['course_code']}?"):
            return
        if self._run("Unlink programme", data.remove_programme,
                     self.current_code, link["course_code"]):
            self._audit("unlink_programme", module_code=self.current_code,
                        course_code=link["course_code"])
        self.refresh_programmes()

    # ------------------------------------------------------------------ prerequisites

    def _build_prerequisites(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Rules")
        if self.can_manage:
            bar = ttk.Frame(tab)
            bar.pack(fill="x", **_PAD)
            ttk.Label(bar, text="Requires:").pack(side="left")
            self.prereq_combo = ttk.Combobox(bar, width=34)
            self.prereq_combo.pack(side="left", padx=4)
            ttk.Label(bar, text="Min grade:").pack(side="left")
            self.min_grade_var = tk.StringVar()
            ttk.Entry(bar, textvariable=self.min_grade_var, width=6).pack(side="left", padx=4)
            self.coreq_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(bar, text="Can be taken alongside",
                            variable=self.coreq_var).pack(side="left", padx=4)
            ttk.Button(bar, text="Add", command=self.add_prerequisite).pack(side="left", padx=2)
            ttk.Button(bar, text="Remove selected",
                       command=self.remove_prerequisite).pack(side="left", padx=2)
        ttk.Label(tab, foreground="#666", text=(
            "Enforced when a student enrols: a prerequisite needs a pass; one that can "
            "be taken alongside is also met by current enrolment.")).pack(anchor="w", padx=8)
        self.prereq_tree = _tree(
            tab, [("code", "Module"), ("name", "Name"), ("grade", "Min grade"),
                  ("kind", "Kind"), ("source", "Rule")],
            [90, 230, 80, 140, 100], height=6)
        self._build_exclusions(tab)

    def refresh_prerequisites(self):
        _clear(self.prereq_tree)
        if not self.current_code:
            return
        if self.can_manage:
            modules = data.list_modules(include_inactive=False)
            self.prereq_combo["values"] = [
                f"{m['module_code']} - {m['module_name'] or ''}" for m in modules
                if m["module_code"] != self.current_code]
        self._prereqs = data.list_prerequisites(self.current_code)
        for i, p in enumerate(self._prereqs):
            self.prereq_tree.insert("", "end", iid=str(i), values=(
                p["code"], p["name"], p["min_grade"] or "Pass",
                "Co-requisite (alongside)" if p["is_corequisite"] else "Prerequisite",
                p["source"]))

    def add_prerequisite(self):
        if not self._require_module():
            return
        prereq = _code_of(self.prereq_combo.get())
        rule = self._run("Add prerequisite", data.add_prerequisite, self.current_code, prereq,
                         min_grade=self.min_grade_var.get(), corequisite=self.coreq_var.get())
        if rule:
            self._audit("add_prerequisite", module_code=self.current_code, requires=prereq)
            self.prereq_combo.set("")
            self.min_grade_var.set("")
            self.coreq_var.set(False)
            self._status(f"{self.current_code} now requires {prereq}")
            self.refresh_prerequisites()

    def remove_prerequisite(self):
        sel = self.prereq_tree.selection()
        if not self._require_module() or not sel:
            return
        rule = self._prereqs[int(sel[0])]
        if not rule["removable"]:
            self._info("Remove prerequisite",
                       "This is a course-level rule; change it in Course Management.")
            return
        if not self._ask("Remove prerequisite",
                         f"Stop requiring {rule['code']} for {self.current_code}?"):
            return
        if self._run("Remove prerequisite", data.remove_prerequisite, rule["id"]):
            self._audit("remove_prerequisite", module_code=self.current_code,
                        requires=rule["code"])
        self.refresh_prerequisites()

    # ------------------------------------------------------------------ enrolments

    def _build_enrolments(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Enrolments")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", **_PAD)
        if self.can_manage:
            ttk.Label(bar, text="Student:").pack(side="left")
            self.student_combo = ttk.Combobox(bar, width=30)
            self.student_combo.pack(side="left", padx=4)
            self._build_enrolment_extras(bar)
            ttk.Button(bar, text="Enrol", command=self.enrol_student).pack(side="left", padx=2)
            ttk.Button(bar, text="Withdraw selected",
                       command=self.withdraw_student).pack(side="left", padx=2)
            ttk.Button(bar, text="Email students",
                       command=self.email_students).pack(side="left", padx=2)
        self.show_withdrawn_var = tk.BooleanVar(value=False)
        if self.can_manage:
            check_bar = self._build_enrolment_bulk(tab)
        else:
            check_bar = bar
        ttk.Checkbutton(check_bar, text="Show withdrawn", variable=self.show_withdrawn_var,
                        command=self.refresh_enrolments).pack(side="right")
        self.enrol_count_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.enrol_count_var, foreground="#666").pack(anchor="w", padx=8)
        self.enrol_tree = _tree(
            tab, [("id", "Student ID"), ("name", "Name"), ("status", "Status"),
                  ("date", "Enrolled on"), ("grade", "Grade"), ("score", "Score")],
            [100, 200, 90, 100, 70, 70], height=8, selectmode="extended")
        self._build_waitlist(tab)

    def refresh_enrolments(self):
        _clear(self.enrol_tree)
        if self.can_manage and not self.student_combo["values"]:
            students = self._run("Load students", data.student_choices) or []
            self.student_combo["values"] = [f"{s['student_id']} - {s['name']}" for s in students]
        if not self.current_code:
            self.enrol_count_var.set("")
            return
        rows = data.list_enrolments(self.current_code,
                                    include_withdrawn=self.show_withdrawn_var.get())
        for r in rows:
            self.enrol_tree.insert("", "end", iid=r["student_id"], values=(
                r["student_id"], r["name"], r["status"], r["enrollment_date"] or "",
                r["grade"] or "", "" if r["score"] is None else r["score"]))
        enrolled = sum(1 for r in rows if r["status"] == data.ENROLLED)
        module = data.get_module(self.current_code) or {}
        cap = module.get("capacity")
        self.enrol_count_var.set(f"{enrolled} enrolled" + (f" of {cap}" if cap else
                                                           " (no capacity limit)"))
        self._refresh_delivery_choices()
        self.refresh_waitlist()

    def enrol_student(self):
        if not self._require_module():
            return
        student_id = _code_of(self.student_combo.get())
        if not student_id:
            self._info("Enrol student", "Choose a student first.")
            return
        section_id = self._selected_delivery_id()
        eligibility = self._do("Check eligibility", enrolment_rules.eligibility,
                               self.current_code, student_id, section_id)
        override = False
        if eligibility is not None and eligibility.only_capacity:
            if self._ask("Module full", f"{eligibility.reason()}\n\nPut {student_id} on the "
                         "waitlist instead? (No = enrol anyway as a staff override)"):
                self.join_waitlist()
                return
        if eligibility is not None and eligibility.blocks:
            if not self._ask("Enrolment rules not met",
                             f"{student_id} does not meet the rules for {self.current_code}:\n\n"
                             f"{eligibility.reason()}\n\nEnrol anyway as a staff override?"):
                return
            override = True
        result = self._run("Enrol student", data.enrol_student, self.current_code, student_id,
                           section_id)
        if result is None:
            return
        if result == "already":
            self._info("Enrol student", f"{student_id} is already enrolled on {self.current_code}.")
            return
        self._audit("enrol_student", module_code=self.current_code, student_id=student_id,
                    result=result, override=override,
                    blocks=eligibility.reason() if override else "")
        self._status(f"{student_id} {result} on {self.current_code}"
                     + (" (override)" if override else ""))
        self.student_combo.set("")
        self.refresh_enrolments()
        self.refresh_modules()

    def withdraw_student(self):
        sel = list(self.enrol_tree.selection())
        if not self._require_module() or not sel:
            return
        who = sel[0] if len(sel) == 1 else f"{len(sel)} students"
        if not self._ask("Withdraw",
                         f"Withdraw {who} from {self.current_code}?\n\n"
                         "Enrolment records and any grades are kept. Freed places go to "
                         "the first eligible students on the waitlist."):
            return
        result = self._run("Withdraw", data.withdraw_and_promote, self.current_code, sel,
                           self.username)
        if result is None:
            return
        for student_id in result["withdrawn"]:
            self._audit("withdraw_student", module_code=self.current_code, student_id=student_id)
        if not result["withdrawn"]:
            self._info("Withdraw", "None of the selected students is currently enrolled.")
        else:
            self._status(f"{len(result['withdrawn'])} withdrawn from {self.current_code}"
                         + (f"; enrolled from the waitlist: {', '.join(result['promoted'])}"
                            if result["promoted"] else ""))
        self.refresh_enrolments()
        self.refresh_modules()

    def email_students(self):
        if not self._require_module():
            return
        recipients = data.student_emails(self.current_code)
        if not recipients:
            self._info("Email students", "No enrolled student on this module has an email address.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Email students on {self.current_code}")
        dialog.transient(self.root)
        dialog.geometry("620x440")
        ttk.Label(dialog, text=f"{len(recipients)} recipient(s)", padding=8).pack(anchor="w")
        form = ttk.Frame(dialog, padding=(8, 0))
        form.pack(fill="x")
        ttk.Label(form, text="Subject:").pack(side="left")
        subject = ttk.Entry(form)
        subject.pack(side="left", fill="x", expand=True, padx=4)
        subject.insert(0, f"{self.current_code}: ")
        buttons = ttk.Frame(dialog, padding=8)
        buttons.pack(side="bottom", fill="x")
        body = tk.Text(dialog, wrap="word")
        body.pack(fill="both", expand=True, padx=8, pady=4)
        code = self.current_code

        def send():
            text = body.get("1.0", "end-1c").strip()
            if not subject.get().strip() or not text:
                messagebox.showwarning("Email students", "Subject and message are required.",
                                       parent=dialog)
                return
            try:
                # The package facade: it reaches email_service.core, which
                # stores and delivers. email_manager.send_email only queues
                # in memory.
                from education_system.systems.university.infrastructure.email import (
                    send_email,
                )
            except Exception as exc:
                messagebox.showerror("Email students", f"Email is unavailable: {exc}",
                                     parent=dialog)
                return
            sent, failed = 0, []
            for r in recipients:
                try:
                    send_email(recipient_email=r["email"], subject=subject.get().strip(),
                               body=text)
                    sent += 1
                except Exception:
                    logger.exception("email to %s failed", r["email"])
                    failed.append(r["student_id"])
            self._audit("email_students", module_code=code, sent=sent, failed=len(failed))
            messagebox.showinfo("Email students",
                                f"Sent {sent} email(s)."
                                + (f"\nFailed: {', '.join(failed)}" if failed else ""),
                                parent=dialog)
            if not failed:
                dialog.destroy()

        ttk.Button(buttons, text="Send", command=send).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

    # ------------------------------------------------------------------ assessment

    def _build_assessment(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Assessment")
        self.assess_summary_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.assess_summary_var, justify="left",
                  padding=(8, 4)).pack(anchor="w")
        ttk.Label(tab, foreground="#666", padding=(8, 0), text=(
            "Assessments and marks are edited in Grade Tracking; this is a summary.")
        ).pack(anchor="w")
        self.assess_tree = _tree(
            tab, [("name", "Assessment"), ("type", "Type"), ("weight", "Weight"),
                  ("max", "Max points"), ("due", "Due"), ("status", "Status")],
            [220, 110, 70, 80, 100, 80], height=6)
        self._build_assessment_plan(tab)

    def refresh_assessment(self):
        self.refresh_plan()
        _clear(self.assess_tree)
        if not self.current_code:
            self.assess_summary_var.set("")
            return
        for a in data.list_assessments(self.current_code):
            self.assess_tree.insert("", "end", values=(
                a["assessment_name"], a["assessment_type"], a["weight"], a["max_points"],
                a["due_date"] or "", a["status"] or ""))
        s = data.grade_summary(self.current_code)
        weight = s["total_weight"]
        weight_note = ""
        if s["assessments"]:
            weight_note = f"   ·   weights total {weight:g}"
            if abs((weight or 0) - 100) > 0.01 and abs((weight or 0) - 1) > 0.001:
                weight_note += "  (does not add up to 100%)"
        average = "—" if s["average"] is None else f"{s['average']:.1f}"
        self.assess_summary_var.set(
            f"{s['assessments']} assessment(s){weight_note}\n"
            f"{s['graded']} final mark(s) recorded   ·   average {average}   ·   "
            f"{s['passed']} passed")

    # ------------------------------------------------------------------ catalogue-wide

    def show_report(self):
        lines = self._run("Module report", data.report_lines)
        if lines is None:
            return
        win = tk.Toplevel(self.root)
        win.title("Module Report")
        win.transient(self.root)
        win.geometry("980x640")
        bar = ttk.Frame(win, padding=8)
        bar.pack(side="bottom", fill="x")
        text = tk.Text(win, wrap="none", font=("Courier New", 10))
        text.pack(fill="both", expand=True)
        report = "\n".join(lines)
        text.insert("1.0", report)
        text.configure(state="disabled")

        def save():
            path = filedialog.asksaveasfilename(parent=win, defaultextension=".txt",
                                                filetypes=[("Text", "*.txt")],
                                                initialfile="module_report.txt")
            if path:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(report)
                messagebox.showinfo("Module report", f"Saved to {path}", parent=win)

        ttk.Button(bar, text="Save as TXT", command=save).pack(side="left")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")

    def export_csv(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="modules_export.csv")
        if not path:
            return
        count = self._run("Export CSV", data.export_csv, path)
        if count is not None:
            self._audit("export_modules_csv", rows=count)
            self._info("Export CSV", f"Exported {count} module(s) to {path}")

    def import_csv(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("CSV", "*.csv")])
        if not path:
            return
        result = self._run("Import CSV", data.import_csv, path)
        if result is None:
            return
        imported, problems = result
        self._audit("import_modules_csv", imported=imported, problems=len(problems))
        self.refresh_modules()
        detail = "\n".join(problems[:20]) + (f"\n… and {len(problems) - 20} more"
                                              if len(problems) > 20 else "")
        self._info("Import CSV", f"Imported {imported} module(s)."
                   + (f"\n\n{len(problems)} row(s) skipped:\n{detail}" if problems else ""))

    def validate(self):
        issues = self._run("Validate data", data.validate)
        if issues is None:
            return
        if not issues:
            self._info("Validate data", "No problems found.")
        else:
            self._info("Validate data", f"{len(issues)} problem(s) found:\n\n• "
                       + "\n• ".join(issues))
