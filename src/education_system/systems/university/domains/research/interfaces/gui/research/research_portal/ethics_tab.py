"""Ethics tab: applications, supervisor endorsement, reviewer allocation,
reviews, the chair's decision, conditions, amendments and renewals.

Everything goes through ``university/application/research/ethics``; the
buttons offered follow who is signed in and the application's status, and
the rules check permissions again.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.research import ethics as rules
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
)


def _project_choices(parent, who):
    from education_system.systems.university.application.research import (
        projects as research_projects,
    )
    if not who.is_staff:
        return []
    return [("", "(none)")] + (common.call(parent, research_projects.choices, who, quiet=True)
                               or [])


class EthicsTab(common.RecordTab):
    columns = [("reference", "Reference", 110), ("title", "Title", 230),
               ("status", "Status", 120), ("risk", "Risk", 60), ("kind", "Kind", 90)]
    statuses = rules.STATUSES

    def new_actions(self):
        actions = [("New application", self.new_application)]
        if self.who.reviews_ethics:
            actions.append(("My reviews", self.my_reviews))
        return actions

    # ── list and record ──
    def load(self, conn, search, status):
        return rules.listing(conn, self.who, status, search)

    def row_id(self, row):
        return row["review_id"]

    def values(self, row):
        return (row.get("reference"), row.get("title"), common.nice(row.get("status")),
                row.get("risk_level"), row.get("kind") or "application")

    def fetch(self, conn, record_id):
        return rules.record(conn, self.who, int(record_id))

    def render(self, r):
        allocations = [f"{a['reviewer']}: {common.nice(a['status'])}"
                       + (f" – {common.nice(a['recommendation'])}" if a.get("recommendation")
                          else "")
                       + (f"\n    {a['comments']}" if a.get("comments") else "")
                       + (f"\n    Conflict: {a['conflict_detail']}" if a.get("conflict_detail")
                          else "")
                       for a in r["allocations"]]
        conditions = [("✓ " if c["met_at"] else "✗ ") + c["condition_text"]
                      + (f"  (met {c['met_at'][:10]}: {c.get('evidence') or ''})"
                         if c["met_at"] else "") for c in r["conditions"]]
        children = [f"{c['reference']} – {c['kind']} – {common.nice(c['status'])}"
                    for c in r["children"]]
        history = [f"{h['at']}  {h['actor'] or ''}  {common.nice(h['action'])}"
                   for h in r["history"]]
        self.detail.show(f"{r.get('reference')} – {r.get('title')}", [
            ("Application", [
                ("Status", common.nice(r["status"])),
                ("Kind", r.get("kind") or "application"),
                ("Route", r.get("route")),
                ("Reviews needed", r.get("reviews_needed")),
                ("Applicant", r.get("applicant_id")),
                ("Principal investigator", r.get("principal_investigator_id")),
                ("Supervisor", r.get("supervisor_id")),
                ("Supervisor endorsed", r.get("supervisor_endorsed_at")),
                ("Department", r.get("department")),
                ("Category", r.get("category")),
                ("Risk", r.get("risk_level")),
                ("Project", r.get("project_id")),
                ("Study dates", f"{r.get('start_date') or '?'} to {r.get('end_date') or '?'}"),
                ("Submitted", r.get("submission_date")),
                ("Decided", r.get("decision_date")),
                ("Approval expires", r.get("approval_expiry_date")),
            ]),
            ("Summary", r.get("summary") or "—"),
            ("Participants", r.get("participants") or "—"),
            ("Data handling", r.get("data_handling") or "—"),
            ("Notes", r.get("notes") or "—"),
            ("Decision comments", r.get("reviewer_comments") or "—"),
            ("Reviews", allocations),
            ("Conditions", conditions),
            ("Amendments and renewals", children),
            ("History", history),
        ])

    # ── who may do what ──
    def _owner(self, r):
        w = self.who
        return w.me in (r.get("applicant_id"), r.get("principal_investigator_id"),
                        r.get("created_by")) or w.username == r.get("principal_investigator_id")

    def actions(self, r):
        status, owner, w = r["status"], self._owner(r), self.who
        acts = []
        if owner and status in ("draft", "revisions_required"):
            acts += [("Edit", self.edit), ("Submit", self.submit)]
        if (owner or w.is_office) and status in rules.OPEN:
            acts.append(("Withdraw", self.withdraw))
        if status == "awaiting_supervisor" and (w.username == r.get("supervisor_id")
                                                or w.is_office):
            acts += [("Endorse", self.endorse), ("Return to student", self.return_back)]
        if w.chairs_ethics and status in ("submitted", "under_review"):
            acts += [("Allocate reviewer", self.allocate), ("Decide", self.decide)]
        if owner and status == "approved":
            acts += [("Request amendment", self.amend), ("Request renewal", self.renew),
                     ("Close study", self.close_study)]
        if owner and status == "expired":
            acts.append(("Request renewal", self.renew))
        if (owner or w.chairs_ethics) and any(not c["met_at"] for c in r["conditions"]):
            acts.append(("Mark condition met", self.meet_condition))
        mine = [a for a in r["allocations"] if a["reviewer"] == w.username
                and a["status"] == "allocated"]
        if mine:
            acts += [("Submit my review", lambda a=mine[0]: self._review(a["allocation_id"])),
                     ("Declare conflict", lambda a=mine[0]: self._conflict(a["allocation_id"]))]
        return acts

    # ── forms ──
    def _fields(self, creating):
        fields = [Field("title", "Study title", required=True),
                  Field("category", "Category", "combo", list(rules.CATEGORIES)),
                  Field("risk_level", "Risk level", "combo", list(rules.RISK_LEVELS)),
                  Field("start_date", "Start date", "date"),
                  Field("end_date", "End date", "date"),
                  Field("department", "Department")]
        projects = _project_choices(self, self.who)
        if projects:
            fields.append(Field("project_id", "Project", "combo", projects))
        if creating and self.who.is_student:
            fields.insert(1, Field("supervisor_id", "Supervisor", "staff",
                                   common.staff_choices(self), required=True))
        elif creating:
            fields.insert(1, Field("principal_investigator_id", "Principal investigator",
                                   "staff", common.staff_choices(self),
                                   hint="blank = you"))
        fields += [Field("summary", "Summary", "multiline"),
                   Field("participants", "Participants", "multiline"),
                   Field("data_handling", "Data handling", "multiline"),
                   Field("notes", "Notes", "multiline")]
        return fields

    def new_application(self):
        data = common.ask(self, "New ethics application", self._fields(True), columns=2)
        if data is None:
            return
        data = {k: v for k, v in data.items() if v not in ("", None) or k == "project_id"}
        new_id = common.call(self, rules.create, self.who, data, write=True)
        if new_id:
            self.open_record(new_id)
            self.portal.changed()

    def edit(self):
        r = self.record
        values = {k: r.get(k) for k in ("title", "category", "risk_level", "start_date",
                                        "end_date", "department", "project_id", "summary",
                                        "participants", "data_handling", "notes")}
        data = common.ask(self, f"Edit {r['reference']}", self._fields(False), values, columns=2)
        if data is not None:
            self.write(rules.update, self.who, r["review_id"], data)

    def submit(self):
        self.write(rules.submit, self.who, self.record["review_id"],
                   done="Submitted. The next person in the process has been told.")

    def withdraw(self):
        reason = common.ask_text(self, "Withdraw application", "Reason")
        if reason:
            self.write(rules.withdraw, self.who, self.record["review_id"], reason)

    def close_study(self):
        if common.confirm(self, "Close this study? Its approval will no longer be needed."):
            self.write(rules.close, self.who, self.record["review_id"])

    def endorse(self):
        note = common.ask_text(self, "Endorse application", "Note (optional)", required=False)
        if note is not None:
            self.write(rules.endorse, self.who, self.record["review_id"], True, note)

    def return_back(self):
        note = common.ask_text(self, "Return to student", "What needs changing")
        if note:
            self.write(rules.endorse, self.who, self.record["review_id"], False, note)

    def allocate(self):
        data = common.ask(self, "Allocate reviewer", [
            Field("reviewer", "Reviewer", "staff", common.staff_choices(self), required=True)])
        if data:
            self.write(rules.allocate, self.who, self.record["review_id"], data["reviewer"])

    def decide(self):
        data = common.ask(self, f"Decide {self.record['reference']}", [
            Field("decision", "Decision", "combo", list(rules.DECISIONS), required=True),
            Field("comments", "Comments", "multiline", required=True),
            Field("conditions", "Conditions (one per line)", "multiline"),
            Field("expiry", "Approval expires", "date", hint="blank = study end date")])
        if data:
            conditions = [c for c in data["conditions"].splitlines() if c.strip()]
            self.write(rules.decide, self.who, self.record["review_id"], data["decision"],
                       data["comments"], conditions, data["expiry"] or None)

    def amend(self):
        text = common.ask_text(self, "Request amendment", "Describe the change")
        if text:
            new_id = common.call(self, rules.amend, self.who, self.record["review_id"], text,
                                 write=True)
            if new_id:
                self.open_record(new_id)
                common.info(self, "Amendment started as a draft: edit it, then submit it.")

    def renew(self):
        data = common.ask(self, "Request renewal", [
            Field("end", "New end date", "date", required=True)])
        if data:
            new_id = common.call(self, rules.renew, self.who, self.record["review_id"],
                                 data["end"], write=True)
            if new_id:
                self.open_record(new_id)
                common.info(self, "Renewal started as a draft: submit it for review.")

    def meet_condition(self):
        unmet = [(c["condition_id"], c["condition_text"][:80])
                 for c in self.record["conditions"] if not c["met_at"]]
        data = common.ask(self, "Condition met", [
            Field("condition", "Condition", "combo", unmet, required=True),
            Field("evidence", "Evidence", "multiline", required=True)])
        if data:
            self.write(rules.meet_condition, self.who, int(data["condition"]), data["evidence"])

    # ── reviewing ──
    def _review(self, allocation_id, parent=None):
        data = common.ask(parent or self, "Submit review", [
            Field("recommendation", "Recommendation", "combo", list(rules.RECOMMENDATIONS),
                  required=True),
            Field("comments", "Comments", "multiline", required=True)])
        if data:
            return self.write(rules.submit_review, self.who, allocation_id,
                              data["recommendation"], data["comments"])
        return None

    def _conflict(self, allocation_id, parent=None):
        detail = common.ask_text(parent or self, "Declare a conflict of interest",
                                 "What is the conflict")
        if detail:
            return self.write(rules.declare_conflict, self.who, allocation_id, detail,
                              done="Conflict declared; the chair will allocate someone else.")
        return None

    def my_reviews(self):
        MyReviews(self)


class MyReviews(tk.Toplevel):
    """The signed-in reviewer's open reviews."""

    def __init__(self, tab: EthicsTab):
        super().__init__(tab)
        self.tab = tab
        self.title("My ethics reviews")
        self.transient(tab.winfo_toplevel())
        self.geometry("820x420")
        bar = ttk.Frame(self, padding=6)
        bar.pack(side="bottom", fill="x")             # before the list
        for label, command in (("Open application", self.open), ("Submit review", self.review),
                               ("Declare conflict", self.conflict), ("Close", self.destroy)):
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=3)
        self.tree = common.make_tree(self, [("reference", "Reference", 120),
                                            ("title", "Title", 340), ("risk", "Risk", 70),
                                            ("allocated", "Allocated", 150)])
        self.refresh()

    def refresh(self):
        rows = common.call(self, rules.my_reviews, self.tab.who) or []
        common.fill(self.tree, rows, lambda r: r["allocation_id"],
                    lambda r: (r["reference"], r["title"], r["risk_level"], r["allocated_at"]))
        self._rows = {str(r["allocation_id"]): r for r in rows}

    def _pick(self):
        key = common.selected(self.tree)
        if key is None:
            common.info(self, "Select a review first.")
        return key

    def open(self):
        key = self._pick()
        if key:
            self.tab.open_record(self._rows[key]["review_id"])

    def review(self):
        key = self._pick()
        if key and self.tab._review(int(key), parent=self) is not None:
            self.refresh()

    def conflict(self):
        key = self._pick()
        if key and self.tab._conflict(int(key), parent=self) is not None:
            self.refresh()
