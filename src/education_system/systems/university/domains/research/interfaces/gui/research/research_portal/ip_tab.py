"""IP & Commercialisation tab: disclosures, technology-transfer assessment,
filings and their deadlines, licences and licence income.

Inventors are entered one per line as ``username percent``; the shares add
up to 100. Inventors see their own payments; technology transfer sees the
whole split.
"""

from __future__ import annotations

from tkinter import messagebox

from education_system.systems.university.application.research import ip as rules
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
)


def parse_inventors(text):
    """``"jsmith 60\\nakhan 40"`` → ``[("jsmith", 60.0), ("akhan", 40.0)]``."""
    people = []
    for line in str(text or "").replace(",", "\n").splitlines():
        parts = line.replace("%", " ").split()
        if not parts:
            continue
        if len(parts) != 2:
            raise ValueError(f"Write each inventor as 'username percent': {line.strip()!r}")
        try:
            people.append((parts[0], float(parts[1])))
        except ValueError:
            raise ValueError(f"{parts[1]!r} is not a percentage") from None
    return people


class IPTab(common.RecordTab):
    columns = [("reference", "Reference", 100), ("title", "Title", 240),
               ("type", "Type", 90), ("status", "Status", 90)]
    statuses = rules.STATUSES

    def new_actions(self):
        return [("New disclosure", self.new_disclosure)]

    def load(self, conn, search, status):
        return rules.listing(conn, self.who, status, search)

    def row_id(self, row):
        return row["disclosure_id"]

    def values(self, row):
        return (row.get("reference"), row.get("title"), row.get("ip_type"),
                common.nice(row.get("status")))

    def fetch(self, conn, record_id):
        return rules.record(conn, self.who, int(record_id))

    def render(self, r):
        tto = self.who.is_tto
        inventors = [f"{i['username']}: {i['contribution_percentage']:g}%"
                     + (" (lead)" if i["is_primary"] else "") for i in r["inventors"]]
        licences = [f"#{lic['license_id']} {lic['licensee_name']} – "
                    f"{common.nice(lic['license_type'])}, {lic['territory']}, "
                    f"{lic['start_date']} to {lic.get('end_date') or 'open'}, royalty "
                    f"{lic.get('royalty_rate') or 0:g}%, fee {common.money(lic.get('annual_fee'))}"
                    f" – {lic['status']}" for lic in r["licences"]]
        revenue = []
        for rev in r["revenue"]:
            line = f"{rev['period']}: {common.money(rev['total_revenue'])}"
            if tto:
                line += (f" → inventors {common.money(rev['inventor_share'])}, department "
                         f"{common.money(rev['department_share'])}, university "
                         f"{common.money(rev['university_share'])}")
            else:
                line += f" → your share {common.money(rev.get('mine'))}"
            revenue.append(line)
        deadlines = [("✓ " if d["done_at"] else "• ") + f"{d['due_date']}  {d['kind']}"
                     + (f"  ({d['note']})" if d.get("note") else "") for d in r["deadlines"]]
        history = [f"{h['at']}  {h['actor'] or ''}  {common.nice(h['action'])}"
                   for h in r["history"]]
        self.detail.show(f"{r.get('reference')} – {r.get('title')}", [
            ("Disclosure", [("Status", common.nice(r.get("status"))),
                            ("Type", r.get("ip_type")),
                            ("Stage", r.get("development_stage")),
                            ("Department", r.get("department")),
                            ("Funding", r.get("funding_source")),
                            ("Project", r.get("project_id")),
                            ("Commercial route", r.get("commercial_route")),
                            ("Submitted", r.get("submitted_date")),
                            ("Assessed by", r.get("reviewed_by")),
                            ("Assessed", r.get("review_date")),
                            ("Filed", r.get("filing_date")),
                            ("Application number", r.get("application_number")),
                            ("Jurisdiction", r.get("jurisdiction"))]),
            ("Description", r.get("description") or "—"),
            ("Assessment", r.get("review_comments") or "—"),
            ("Inventors", inventors),
            ("Deadlines", deadlines),
            ("Licences", licences),
            ("Income", revenue),
            ("History", history),
        ])

    def actions(self, r):
        status, w = r.get("status"), self.who
        inventor = w.username in {i["username"] for i in r["inventors"]}
        acts = []
        if (inventor and status in ("draft", "submitted")) or w.is_tto:
            acts.append(("Edit", self.edit))
        if inventor and status == "draft":
            acts.append(("Submit", self.submit))
        if not w.is_tto:
            return acts
        if status in ("submitted", "evaluating"):
            acts.append(("Assess", self.assess))
        if status in ("protect", "filed"):
            acts.append(("Record filing", self.record_filing))
        acts.append(("Add deadline", self.add_deadline))
        if any(not d["done_at"] for d in r["deadlines"]):
            acts.append(("Mark deadline done", self.deadline_done))
        if status not in ("draft", "submitted", "abandoned"):
            acts.append(("Add licence", self.add_licence))
        if any(lic["status"] == "active" for lic in r["licences"]):
            acts += [("End licence", self.end_licence), ("Record income", self.record_income)]
        return acts

    # ── forms ──
    def _fields(self):
        from education_system.systems.university.application.research import (
            projects as research_projects,
        )
        projects = [("", "(none)")] + (common.call(self, research_projects.choices, self.who,
                                                   quiet=True) or [])
        return [Field("title", "Title", required=True),
                Field("ip_type", "Type", "combo", list(rules.TYPES), required=True),
                Field("development_stage", "Development stage"),
                Field("funding_source", "Funding source"),
                Field("department", "Department"),
                Field("project_id", "Project", "combo", projects),
                Field("commercial_route", "Commercial route"),
                Field("description", "Description", "multiline"),
                Field("inventors", "Inventors (one per line: username percent)", "multiline",
                      required=True)]

    def new_disclosure(self):
        data = common.ask(self, "New IP disclosure", self._fields(),
                          {"ip_type": "Patent", "inventors": f"{self.who.username} 100"})
        if data is None:
            return
        try:
            people = parse_inventors(data.pop("inventors"))
        except ValueError as exc:
            messagebox.showerror(common.TITLE, str(exc), parent=self)
            return
        new_id = common.call(self, rules.create, self.who, data, people, write=True)
        if new_id:
            self.open_record(new_id)
            self.portal.changed()

    def edit(self):
        r = self.record
        values = {k: r.get(k) for k in ("title", "ip_type", "development_stage",
                                        "funding_source", "department", "project_id",
                                        "commercial_route", "description")}
        values["inventors"] = "\n".join(f"{i['username']} {i['contribution_percentage']:g}"
                                        for i in r["inventors"])
        data = common.ask(self, f"Edit {r['reference']}", self._fields(), values)
        if data is None:
            return
        try:
            people = parse_inventors(data.pop("inventors"))
        except ValueError as exc:
            messagebox.showerror(common.TITLE, str(exc), parent=self)
            return
        self.write(rules.update, self.who, r["disclosure_id"], data, people)

    def submit(self):
        self.write(rules.submit, self.who, self.record["disclosure_id"],
                   done="Submitted to technology transfer.")

    def assess(self):
        data = common.ask(self, "Assess disclosure", [
            Field("decision", "Decision", "combo", list(rules.DECISIONS), required=True),
            Field("comments", "Comments", "multiline", required=True)])
        if data:
            self.write(rules.assess, self.who, self.record["disclosure_id"], data["decision"],
                       data["comments"])

    def record_filing(self):
        data = common.ask(self, "Record filing", [
            Field("date", "Filing date", "date", required=True),
            Field("number", "Application number", required=True),
            Field("jurisdiction", "Jurisdiction")], {"jurisdiction": "GB"})
        if data:
            self.write(rules.record_filing, self.who, self.record["disclosure_id"], data["date"],
                       data["number"], data["jurisdiction"] or "GB",
                       done="Filing recorded; patent deadlines added.")

    def add_deadline(self):
        data = common.ask(self, "Add deadline", [
            Field("kind", "What is due", required=True),
            Field("due", "Due date", "date", required=True),
            Field("note", "Note")])
        if data:
            self.write(rules.add_deadline, self.who, self.record["disclosure_id"], data["kind"],
                       data["due"], data["note"])

    def deadline_done(self):
        open_ = [(d["deadline_id"], f"{d['due_date']} {d['kind']}")
                 for d in self.record["deadlines"] if not d["done_at"]]
        data = common.ask(self, "Deadline done", [
            Field("deadline", "Deadline", "combo", open_, required=True),
            Field("note", "Note")])
        if data:
            self.write(rules.complete_deadline, self.who, int(data["deadline"]), data["note"])

    def add_licence(self):
        data = common.ask(self, "Add licence", [
            Field("licensee", "Licensee", required=True),
            Field("type", "Licence type", "combo", list(rules.LICENCE_TYPES), required=True),
            Field("start", "Start date", "date", required=True),
            Field("end", "End date", "date"),
            Field("royalty", "Royalty rate (%)", "number"),
            Field("fee", "Annual fee (£)", "number"),
            Field("territory", "Territory"),
            Field("notes", "Notes", "multiline")], {"territory": "worldwide"})
        if data:
            self.write(rules.add_licence, self.who, self.record["disclosure_id"],
                       data["licensee"], data["type"], data["start"], end_date=data["end"],
                       royalty_rate=data["royalty"] or 0, annual_fee=data["fee"] or 0,
                       territory=data["territory"] or "worldwide", notes=data["notes"])

    def _active_licences(self):
        return [(lic["license_id"], f"#{lic['license_id']} {lic['licensee_name']}")
                for lic in self.record["licences"] if lic["status"] == "active"]

    def end_licence(self):
        data = common.ask(self, "End licence", [
            Field("licence", "Licence", "combo", self._active_licences(), required=True),
            Field("reason", "Reason", "multiline", required=True)])
        if data:
            self.write(rules.end_licence, self.who, int(data["licence"]), data["reason"])

    def record_income(self):
        data = common.ask(self, "Record licence income", [
            Field("licence", "Licence", "combo", self._active_licences(), required=True),
            Field("period", "Period", required=True, hint="e.g. 2026 or 2026 Q1"),
            Field("amount", "Income (£)", "number", required=True),
            Field("paid", "Payment date", "date")])
        if not data:
            return
        earlier = sum(float(rev["total_revenue"] or 0) for rev in self.record["revenue"])
        shares = rules.split(earlier, float(data["amount"]))
        if not common.confirm(self, f"Split {common.money(data['amount'])}:\n"
                                    f"  inventors {common.money(shares['inventors'])}\n"
                                    f"  department {common.money(shares['department'])}\n"
                                    f"  university {common.money(shares['university'])}\n\n"
                                    "Record it?"):
            return
        self.write(rules.record_revenue, self.who, int(data["licence"]), data["period"],
                   data["amount"], data["paid"] or None)
