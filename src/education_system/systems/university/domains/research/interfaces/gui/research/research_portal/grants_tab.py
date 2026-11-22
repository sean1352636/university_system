"""Grants: costing, internal approval, submission, award, spend, reports.

Every action goes through ``university/application/research/grants``, which
decides who may do it; the buttons offered follow the same rules so people
only see what they can actually do.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.application.research import grants as rg
from education_system.systems.university.application.research import projects as rp
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
    money,
    nice,
)


class GrantsTab(common.RecordTab):
    columns = [("name", "Grant", 220), ("funder", "Funder", 110), ("pi", "PI", 100),
               ("status", "Status", 110), ("amount", "Requested / awarded", 120),
               ("deadline", "Deadline", 85)]
    statuses = rg.STATUSES

    def __init__(self, parent, portal):
        self.mine_only = tk.BooleanVar(value=False)
        super().__init__(parent, portal)

    def new_actions(self):
        return [("New application", self.on_new)] if self.who.is_staff else []

    def extra_toolbar(self, bar):
        ttk.Checkbutton(bar, text="Waiting for my approval", variable=self.mine_only,
                        command=self.refresh).pack(side="left", padx=6)

    # ── data ──
    def load(self, conn, search, status):
        if self.mine_only.get():
            rows = rg.approvals_for(conn, self.who)
            needle = (search or "").lower()
            return [r for r in rows if not needle or needle in
                    f"{r['grant_name']} {r['funding_agency']}".lower()]
        return rg.listing(conn, self.who, status, search)

    def row_id(self, row):
        return row["application_id"]

    def values(self, row):
        amount = row.get("awarded_amount") if row["status"] in ("awarded", "active", "closed") \
            else row.get("requested_amount")
        return (row["grant_name"], row["funding_agency"], row["principal_investigator_id"],
                nice(row["status"]), money(amount), row.get("application_deadline") or "")

    def fetch(self, conn, record_id):
        return rg.record(conn, self.who, int(record_id))

    # ── detail ──
    def render(self, g):
        cost = g["costing"]
        lines = [f"{rg.COST_CATEGORIES[ln['category']]}: {ln['item']} — {money(ln['amount'])}"
                 f"  (line {ln['line_id']})" for ln in cost["lines"]]
        sections = [
            ("Application", [("Funder", g["funding_agency"]), ("Scheme", g.get("scheme")),
                             ("Principal investigator", g["principal_investigator_id"]),
                             ("Co-investigators", g.get("co_investigators")),
                             ("Department", g.get("department")),
                             ("Project", g.get("project_id")),
                             ("Funder deadline", g.get("application_deadline")),
                             ("Status", nice(g["status"])),
                             ("Needs ethics approval", "yes" if g.get("ethics_required") else "no"),
                             ("Needs data management plan",
                              "yes" if g.get("dmp_required") else "no")]),
            ("Costing (full economic cost)", lines + [
                ("fEC", money(cost["fec"])), ("Funder rate", f"{cost['rate']:.0f}%"),
                ("Price to funder (requested)", money(cost["price"])),
                ("University contribution", money(cost["university_contribution"]))]),
            ("Internal approval", [("Head of department", _signed(g, "hod")),
                                   ("Research office", _signed(g, "office")),
                                   ("Returned with", g.get("decision_note"))]),
        ]
        if g.get("decision_date"):
            sections.append(("Funder decision", [
                ("Decision", nice(g.get("decision_status"))), ("Date", g["decision_date"]),
                ("Awarded", money(g.get("awarded_amount"))),
                ("Period", f"{g.get('grant_period_start') or '—'} to "
                           f"{g.get('grant_period_end') or '—'}"),
                ("Award reference", g.get("award_reference"))]))
        if g["blockers"]:
            sections.append(("Before the award can be accepted",
                             [(f"• {b}", "", "bad") for b in g["blockers"]]))
        sections += self._money_sections(g)
        sections.append(("History", [f"{h['at']}  {h['actor'] or ''}  {nice(h['action'])}"
                                     for h in g["history"]]))
        self.detail.show(g["grant_name"], sections)

    def _money_sections(self, g):
        b = g["budget"]
        out = []
        if b["lines"]:
            pace = "" if b["time_pct"] is None else f"  ·  {b['time_pct']}% of the time gone"
            tag = "warn" if b["time_pct"] is not None and b["spent_pct"] > b["time_pct"] + 10 \
                else ""
            out.append(("Budget", [
                f"{nice(ln['category'])} (line {ln['budget_id']}): approved "
                f"{money(ln['approved_amount'])}, spent {money(ln['spent_amount'])}, left "
                f"{money(float(ln['approved_amount'] or 0) - float(ln['spent_amount'] or 0))}"
                for ln in b["lines"]] + [("Total", f"{money(b['total'])}, spent "
                                                  f"{money(b['spent'])} ({b['spent_pct']}%)"
                                                  f"{pace}", tag)]))
        if g["spend"]:
            out.append(("Spend", [f"{s['spent_on']}  {money(s['amount'])}  {nice(s['category'])}"
                                  f"  {s['description']}  ({s['recorded_by']})"
                                  for s in g["spend"][:30]]))
        if g["reports"]:
            out.append(("Reports", [
                (f"{nice(r['kind'])} due {r['due_date']} (report {r['report_id']})",
                 f"submitted {r['submitted_at']}" if r["submitted_at"] else "outstanding",
                 "" if r["submitted_at"] else "warn") for r in g["reports"]]))
        return out

    # ── actions ──
    def actions(self, g):
        who, status = self.who, g["status"]
        manages = rg.manages(who, g)
        holder = manages or who.username in rg._co_is(g)
        acts = []
        if status == "draft" and manages:
            acts += [("Edit", self.on_edit), ("Add cost line", self.on_add_line),
                     ("Remove cost line", self.on_remove_line),
                     ("Request approval", lambda: self.write(rg.request_approval, who,
                                                             g["application_id"],
                                                             done="Sent for approval."))]
        if status == "awaiting_approval" and (who.is_office or who.heads(g.get("department"))):
            acts += [("Approve", self.on_approve), ("Return for changes", self.on_return)]
        if status == "approved_to_submit" and manages:
            acts.append(("Mark submitted", self.on_submitted))
        if status == "submitted" and who.is_office:
            acts.append(("Record outcome", self.on_outcome))
        if status == "awarded" and who.is_office:
            acts.append(("Accept award", self.on_accept))
        if status == "active":
            if holder:
                acts += [("Record spend", self.on_spend), ("Submit report", self.on_submit_report)]
            if manages:
                acts.append(("Add report", self.on_add_report))
            if who.is_office:
                acts.append(("Close grant", lambda: common.confirm(self, "Close this grant?")
                             and self.write(rg.close, who, g["application_id"])))
        if status in ("draft", "awaiting_approval", "approved_to_submit", "submitted") and manages:
            acts.append(("Withdraw", self.on_withdraw))
        return acts

    def _form(self, values=None):
        projects = common.call(self, rp.choices, self.who, quiet=True) or []
        fields = [Field("grant_name", "Grant name", required=True),
                  Field("funding_agency", "Funder", required=True),
                  Field("scheme", "Scheme"),
                  Field("application_deadline", "Funder deadline", "date", required=True),
                  Field("department", "Department"),
                  Field("funder_rate", "Funder rate %", "number", hint="80 for UKRI"),
                  Field("co_investigators", "Co-investigators", hint="usernames, comma separated"),
                  Field("project_id", "Project", "combo", [("", "(none)"), *projects]),
                  Field("ethics_required", "Needs ethics approval", "check"),
                  Field("dmp_required", "Needs a data management plan", "check")]
        if self.who.is_office and values is None:
            fields.insert(0, Field("principal_investigator_id", "Principal investigator",
                                   "staff", common.staff_choices(self)))
        return fields

    def on_new(self):
        data = common.ask(self, "New grant application", self._form(),
                          {"funder_rate": 80, "dmp_required": True,
                           "principal_investigator_id": self.who.username})
        if data:
            gid = common.call(self, rg.create, self.who, _blank(data), write=True)
            if gid is not None:
                self.open_record(gid)
                self.portal.changed()

    def on_edit(self):
        g = self.record
        data = common.ask(self, "Edit application", self._form(g), g)
        if data:
            self.write(rg.update, self.who, g["application_id"], _blank(data))

    def on_add_line(self):
        data = common.ask(self, "Add cost line", [
            Field("category", "Category", "combo", list(rg.COST_CATEGORIES.items()),
                  required=True),
            Field("item", "Item", required=True), Field("amount", "Amount (£)", "number",
                                                        required=True)])
        if data:
            self.write(rg.add_cost_line, self.who, self.record["application_id"],
                       data["category"], data["item"], data["amount"])

    def on_remove_line(self):
        lines = self.record["costing"]["lines"]
        if not lines:
            common.info(self, "There are no cost lines.")
            return
        data = common.ask(self, "Remove cost line", [Field("line", "Line", "combo", [
            (ln["line_id"], f"{ln['item']} — {money(ln['amount'])}") for ln in lines],
            required=True)])
        if data:
            self.write(rg.remove_cost_line, self.who, int(data["line"]))

    def on_approve(self):
        note = common.ask_text(self, "Approve", "Note (optional)", required=False)
        if note is not None:
            self.write(rg.approve, self.who, self.record["application_id"], note)

    def on_return(self):
        note = common.ask_text(self, "Return for changes", "What needs changing")
        if note:
            self.write(rg.return_for_changes, self.who, self.record["application_id"], note)

    def on_submitted(self):
        data = common.ask(self, "Submitted to the funder", [
            Field("on", "Submitted on", "date")], {"on": common_today()})
        if data:
            self.write(rg.mark_submitted, self.who, self.record["application_id"],
                       data["on"] or None)

    def on_outcome(self):
        data = common.ask(self, "Funder decision", [
            Field("outcome", "Outcome", "combo", ["awarded", "rejected"], required=True),
            Field("amount", "Amount awarded (£)", "number"),
            Field("start", "Grant starts", "date"), Field("end", "Grant ends", "date"),
            Field("reference", "Award reference"), Field("note", "Note", "multiline")])
        if data:
            self.write(rg.record_outcome, self.who, self.record["application_id"],
                       data["outcome"], amount=data["amount"] or None, start=data["start"],
                       end=data["end"], award_reference=data["reference"], note=data["note"])

    def on_accept(self):
        g = self.record
        if g["blockers"]:
            common.info(self, "This award cannot be accepted yet:\n\n• " +
                        "\n• ".join(g["blockers"]))
            return
        if common.confirm(self, "Accept the award? Budget lines are created from the costing, "
                                "final reports are scheduled and Finance is told."):
            self.write(rg.accept_award, self.who, g["application_id"], done="Award accepted.")

    def on_spend(self):
        lines = self.record["budget"]["lines"]
        fields = [Field("line", "Budget line", "combo", [
            (ln["budget_id"], f"{nice(ln['category'])} — "
                              f"{money(float(ln['approved_amount'] or 0) - float(ln['spent_amount'] or 0))}"
                              f" left") for ln in lines], required=True),
            Field("amount", "Amount (£)", "number", required=True),
            Field("on", "Date spent", "date", required=True),
            Field("description", "Description", required=True)]
        if self.who.is_office:
            fields.append(Field("over", "Allow overspend", "check"))
        data = common.ask(self, "Record spend", fields, {"on": common_today()})
        if data:
            self.write(rg.record_spend, self.who, int(data["line"]), data["amount"], data["on"],
                       data["description"], allow_overspend=bool(data.get("over")))

    def on_add_report(self):
        data = common.ask(self, "Schedule a report", [
            Field("kind", "Kind", "combo", list(rg.REPORT_KINDS), required=True),
            Field("due", "Due date", "date", required=True), Field("note", "Note")])
        if data:
            self.write(rg.add_report, self.who, self.record["application_id"], data["kind"],
                       data["due"], data["note"])

    def on_submit_report(self):
        open_reports = [r for r in self.record["reports"] if not r["submitted_at"]]
        if not open_reports:
            common.info(self, "No reports are outstanding.")
            return
        data = common.ask(self, "Submit a report", [
            Field("report", "Report", "combo", [
                (r["report_id"], f"{nice(r['kind'])} due {r['due_date']}")
                for r in open_reports], required=True), Field("note", "Note")])
        if data:
            self.write(rg.submit_report, self.who, int(data["report"]), data["note"])

    def on_withdraw(self):
        reason = common.ask_text(self, "Withdraw application", "Reason")
        if reason:
            self.write(rg.withdraw, self.who, self.record["application_id"], reason)


def _signed(g, who):
    by, at = g.get(f"{who}_approved_by"), g.get(f"{who}_approved_at")
    return f"{by} on {at}" if at else "waiting"


def _blank(data):
    """Drop empty optional values so the rules keep their defaults."""
    out = dict(data)
    if out.get("project_id") in ("", None):
        out["project_id"] = None
    for key in ("funder_rate", "department", "principal_investigator_id"):
        if out.get(key) in ("", None):
            out.pop(key, None)
    return out


def common_today():
    from datetime import date
    return date.today().isoformat()
