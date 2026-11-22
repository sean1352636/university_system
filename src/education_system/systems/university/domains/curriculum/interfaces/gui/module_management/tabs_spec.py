"""Module Management tabs: Specification, the assessment plan, and History
(change requests and the field-by-field change log).

Catalogue managers save directly; a module's leader without catalogue rights
proposes a change instead, which a manager approves on the History tab. The
rules are ``university/application/modules/specification``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk

from education_system.systems.university.application.modules import specification as spec
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management import (  # noqa: E501
    data,
)
from education_system.systems.university.domains.curriculum.interfaces.gui.module_management._widgets import (  # noqa: E501
    _PAD, _clear, _tree,
)

_TEXT_FIELDS = (("aims", "Aims", 3), ("indicative_content", "Indicative content", 4),
                ("teaching_methods", "Teaching & learning methods", 3),
                ("reading_list", "Reading list", 3))
_HOUR_FIELDS = (("contact_hours", "Contact"), ("independent_study_hours", "Independent study"),
                ("placement_hours", "Placement"))


class SpecificationTabs:
    """Mixin for ModuleManagementGUI."""

    # ── specification ────────────────────────────────────────────────

    def _build_specification(self):
        outer = ttk.Frame(self.notebook)
        self.notebook.add(outer, text="Spec")
        bar = ttk.Frame(outer)
        bar.pack(side="top", fill="x", **_PAD)
        if self.can_manage:
            ttk.Button(bar, text="Save specification",
                       command=self.save_specification).pack(side="left")
        else:
            ttk.Button(bar, text="Propose these changes",
                       command=self.save_specification).pack(side="left")
        self.spec_issue_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.spec_issue_var, foreground="#b9770e",
                  wraplength=520, justify="left").pack(side="left", padx=10)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, padding=8)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        self.spec_texts = {}
        row = 0
        for key, label, height in _TEXT_FIELDS:
            ttk.Label(body, text=label + ":", foreground="#555").grid(
                row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
            text = tk.Text(body, height=height, width=50, wrap="word")
            text.grid(row=row, column=1, sticky="ew", pady=3)
            self.spec_texts[key] = text
            row += 1
        hours = ttk.Frame(body)
        hours.grid(row=row, column=1, sticky="w", pady=3)
        ttk.Label(body, text="Study hours:", foreground="#555").grid(
            row=row, column=0, sticky="w", padx=(0, 8))
        self.spec_hours = {}
        for key, label in _HOUR_FIELDS:
            ttk.Label(hours, text=label).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(hours, textvariable=var, width=6).pack(side="left", padx=(2, 10))
            self.spec_hours[key] = var
        self.hours_note_var = tk.StringVar()
        ttk.Label(body, textvariable=self.hours_note_var, foreground="#666").grid(
            row=row + 1, column=1, sticky="w")
        row += 2

        ttk.Label(body, text="Learning outcomes:", foreground="#555").grid(
            row=row, column=0, sticky="nw", pady=(10, 3), padx=(0, 8))
        lo = ttk.Frame(body)
        lo.grid(row=row, column=1, sticky="nsew", pady=(10, 3))
        add = ttk.Frame(lo)
        add.pack(fill="x")
        ttk.Label(add, text="A student can:").pack(side="left")
        self.outcome_var = tk.StringVar()
        ttk.Entry(add, textvariable=self.outcome_var, width=24).pack(
            side="left", padx=4, fill="x", expand=True)
        self.bloom_combo = ttk.Combobox(add, values=spec.BLOOM_LEVELS, width=10, state="readonly")
        self.bloom_combo.set("understand")
        self.bloom_combo.pack(side="left", padx=2)
        ttk.Button(add, text="Add", command=self.add_outcome).pack(side="left", padx=2)
        ttk.Button(add, text="Remove", command=self.delete_outcome).pack(side="left")
        self.outcome_tree = _tree(lo, [("code", "Code"), ("text", "Outcome"),
                                       ("bloom", "Level of learning")], [50, 330, 100], height=6)

    def refresh_specification(self):
        for text in self.spec_texts.values():
            text.delete("1.0", "end")
        for var in self.spec_hours.values():
            var.set("")
        _clear(self.outcome_tree)
        self.spec_issue_var.set("")
        self.hours_note_var.set("")
        if not self.current_code:
            return
        values = data.call(spec.current_values, self.current_code)
        for key, text in self.spec_texts.items():
            text.insert("1.0", values.get(f"spec.{key}") or "")
        for key, var in self.spec_hours.items():
            value = values.get(f"spec.{key}")
            var.set("" if value is None else f"{value:g}")
        credits = values.get("credits") or 0
        self.hours_note_var.set(
            f"{credits} credits = {credits * spec.HOURS_PER_CREDIT} notional hours" if credits
            else "Set the module's credits to check the hours")
        for o in data.call(spec.list_outcomes, self.current_code):
            self.outcome_tree.insert("", "end", iid=str(o["outcome_id"]), values=(
                o["outcome_code"], o["description"], o["bloom_level"] or ""))
        issues = data.call(spec.spec_issues, self.current_code)
        self.spec_issue_var.set(("To complete: " + "; ".join(issues)) if issues else
                                "Specification complete.")

    def _spec_changes(self):
        changes = {f"spec.{k}": t.get("1.0", "end-1c") for k, t in self.spec_texts.items()}
        changes.update({f"spec.{k}": v.get() for k, v in self.spec_hours.items()})
        return changes

    def save_specification(self):
        if not self._require_module():
            return
        changes = self._spec_changes()
        if self.can_manage:
            changed = self._do("Save specification", spec.apply_changes,
                               self.current_code, changes, self.username)
            if changed is not None:
                self._status(f"{self.current_code}: {len(changed)} field(s) saved"
                             if changed else "Nothing changed")
                self._audit("save_specification", module_code=self.current_code,
                            fields=sorted(changed))
        else:
            self._propose(changes)
        self.refresh_specification()
        self.refresh_history()

    def _propose(self, changes):
        if not self._leads_current():
            return
        summary = simpledialog.askstring("Propose a change", "What is the change, and why?",
                                         parent=self.root)
        if not summary:
            return
        request_id = self._do("Propose a change", spec.propose_change, self.current_code,
                              changes, self.username, summary)
        if request_id:
            self._audit("propose_module_change", module_code=self.current_code,
                        request_id=request_id)
            self._info("Change proposed", f"Change request #{request_id} is waiting for a "
                       "catalogue manager to approve it.")

    def _leads_current(self):
        if self.can_manage:
            return True
        from education_system.systems.university.application.modules import (
            delivery as module_delivery,
        )
        if data.call(module_delivery.is_leader, self.current_code, self.username):
            return True
        self._info("Not your module", "Only the module leader or a catalogue manager can "
                   "change this module.")
        return False

    def add_outcome(self):
        if not self._require_module() or not self._leads_current():
            return
        made = self._do("Add learning outcome", spec.add_outcome, self.current_code,
                        self.outcome_var.get(), self.bloom_combo.get(), self.username)
        if made:
            self.outcome_var.set("")
            self._status(f"{self.current_code}: added {made}")
            self.refresh_specification()

    def delete_outcome(self):
        sel = self.outcome_tree.selection()
        if not self._require_module() or not sel or not self._leads_current():
            return
        if self._ask("Remove outcome", "Remove this learning outcome?"):
            self._do("Remove learning outcome", spec.delete_outcome, self.current_code,
                     int(sel[0]), self.username)
            self.refresh_specification()

    # ── assessment plan (inside the Assessment tab) ──────────────────

    def _build_assessment_plan(self, tab):
        ttk.Label(tab, text="Planned assessment pattern (from the specification):",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", **_PAD)
        self.plan_vars = {k: tk.StringVar() for k in ("component", "type", "weight", "size",
                                                     "outcomes")}
        for key, label, width in (("component", "Component", 16), ("type", "Type", 10),
                                  ("weight", "Weight %", 5), ("size", "Size", 8),
                                  ("outcomes", "Outcomes", 9)):
            ttk.Label(bar, text=label).pack(side="left")
            ttk.Entry(bar, textvariable=self.plan_vars[key], width=width).pack(
                side="left", padx=(2, 6))
        ttk.Button(bar, text="Add", command=self.add_component).pack(side="left")
        ttk.Button(bar, text="Remove", command=self.delete_component).pack(side="left", padx=2)
        self.plan_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.plan_var, foreground="#666").pack(anchor="w", padx=8)
        self.plan_tree = _tree(tab, [("component", "Component"), ("type", "Type"),
                                     ("weight", "Weight"), ("size", "Size"),
                                     ("outcomes", "Assesses")],
                               [200, 110, 70, 110, 120], height=5)

    def refresh_plan(self):
        _clear(self.plan_tree)
        self.plan_var.set("")
        if not self.current_code:
            return
        plan = data.call(spec.list_plan, self.current_code)
        for p in plan:
            self.plan_tree.insert("", "end", iid=str(p["id"]), values=(
                p["component"], p["assessment_type"] or "", f"{p['weight']:g}%",
                p["size"] or "", p["outcomes"] or ""))
        total = sum(p["weight"] for p in plan)
        if plan:
            self.plan_var.set(f"Planned weightings total {total:g}%"
                              + ("" if abs(total - 100) < 0.01 else " — must reach 100%")
                              + ".  Outcomes are codes like LO1, LO2.")

    def add_component(self):
        if not self._require_module() or not self._leads_current():
            return
        v = {k: var.get() for k, var in self.plan_vars.items()}
        made = self._do("Add assessment component", spec.add_component, self.current_code,
                        v["component"], v["type"], v["weight"], v["size"], v["outcomes"],
                        self.username)
        if made:
            for var in self.plan_vars.values():
                var.set("")
            self.refresh_plan()
            self.refresh_specification()

    def delete_component(self):
        sel = self.plan_tree.selection()
        if not self._require_module() or not sel or not self._leads_current():
            return
        self._do("Remove assessment component", spec.delete_component, self.current_code,
                 int(sel[0]), self.username)
        self.refresh_plan()
        self.refresh_specification()

    # ── history ──────────────────────────────────────────────────────

    def _build_history(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="History")
        ttk.Label(tab, text="Change requests waiting for a decision:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", **_PAD)
        if self.can_manage:
            ttk.Button(bar, text="Approve", command=lambda: self.decide_request(True)).pack(
                side="left")
            ttk.Button(bar, text="Reject", command=lambda: self.decide_request(False)).pack(
                side="left", padx=4)
        ttk.Button(bar, text="Withdraw my request", command=self.withdraw_request).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Details", command=self.show_request).pack(side="left", padx=4)
        self.all_requests_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="All modules", variable=self.all_requests_var,
                        command=self.refresh_history).pack(side="right")
        self.request_tree = _tree(tab, [("id", "#"), ("module", "Module"), ("by", "Proposed by"),
                                        ("at", "When"), ("summary", "Change")],
                                  [40, 90, 100, 130, 300], height=5)
        ttk.Label(tab, text="Change log:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=8, pady=(8, 0))
        self.history_tree = _tree(tab, [("at", "When"), ("field", "What"), ("old", "Was"),
                                        ("new", "Now"), ("by", "By")],
                                  [130, 160, 170, 170, 90], height=10)

    def refresh_history(self):
        _clear(self.request_tree)
        _clear(self.history_tree)
        code = None if self.all_requests_var.get() else self.current_code
        if code or self.all_requests_var.get():
            self._requests = {r["id"]: r for r in data.call(spec.list_requests, code)}
            for r in self._requests.values():
                self.request_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], r["module_code"], r["proposed_by"], r["proposed_at"], r["summary"]))
        if not self.current_code:
            return
        for i, h in enumerate(data.call(spec.history, self.current_code)):
            field = spec.FIELD_LABELS.get(h["field"], h["field"])
            if h["request_id"]:
                field += f" (request #{h['request_id']})"
            self.history_tree.insert("", "end", iid=str(i), values=(
                h["changed_at"], field, h["old_value"] or "", h["new_value"] or "",
                h["changed_by"] or ""))

    def _selected_request(self):
        sel = self.request_tree.selection()
        if not sel:
            self._info("Change requests", "Select a request first.")
            return None
        return self._requests.get(int(sel[0]))

    def show_request(self):
        req = self._selected_request()
        if not req:
            return
        lines = [f"#{req['id']} {req['module_code']} — {req['summary']}",
                 f"Proposed by {req['proposed_by']} at {req['proposed_at']}", ""]
        for key, (old, new) in req["changes"].items():
            lines.append(f"{spec.FIELD_LABELS.get(key, key)}:\n   was: {old or '—'}\n"
                         f"   now: {new or '—'}")
        self._info(f"Change request #{req['id']}", "\n".join(lines))

    def decide_request(self, approve):
        req = self._selected_request()
        if not req:
            return
        note = None
        if not approve:
            note = simpledialog.askstring("Reject change", "Why is it being rejected?",
                                          parent=self.root)
            if not note:
                return
        elif not self._ask("Approve change", f"Apply change request #{req['id']} to "
                           f"{req['module_code']}?"):
            return
        done = self._do("Decide change request", spec.decide_request, req["id"], approve,
                        self.username, note)
        if done:
            self._audit("approve_module_change" if approve else "reject_module_change",
                        module_code=req["module_code"], request_id=req["id"])
            self._status(f"Request #{req['id']} {done['status']}")
            self.refresh_modules()
        self.refresh_history()

    def withdraw_request(self):
        req = self._selected_request()
        if req and self._do("Withdraw request", spec.withdraw_request, req["id"],
                            self.username) is not None:
            self._status(f"Request #{req['id']} withdrawn")
        self.refresh_history()
