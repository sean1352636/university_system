"""Projects: the register, teams, linked records and data management plans."""

from __future__ import annotations

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import integrity
from education_system.systems.university.application.research import projects as rp
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Field,
)

LINK_KINDS = ("grant", "output", "ip", "ethics")


def _record(conn, who, project_id):
    record = rp.record(conn, who, int(project_id))
    record["plans"] = integrity.plans(conn, int(project_id))
    record["pi_name"] = ra.person_name(conn, record["principal_investigator_id"])
    for member in record["team"]:
        member["name"] = ra.person_name(conn, member["username"])
    return record


class ProjectsTab(common.RecordTab):
    columns = [("reference", "Reference", 90), ("title", "Title", 230),
               ("pi", "PI", 110), ("department", "Department", 110), ("status", "Status", 80)]
    statuses = rp.STATUSES

    def new_actions(self):
        return [("New project", self._new)]

    def load(self, conn, search, status):
        return rp.listing(conn, self.who, status, search)

    def row_id(self, row):
        return row["project_id"]

    def values(self, row):
        return (row.get("reference"), row["project_title"], row["principal_investigator_id"],
                row.get("department"), row.get("status"))

    def fetch(self, conn, record_id):
        return _record(conn, self.who, record_id)

    # ── detail ──
    def render(self, r):
        sections = [
            ("", [("Reference", r.get("reference")), ("Principal investigator", r["pi_name"]),
                  ("Department", r.get("department")), ("Type", r.get("project_type")),
                  ("Status", r.get("status")), ("Dates", f"{r.get('start_date') or '—'} to "
                                                         f"{r.get('end_date') or 'open'}"),
                  ("Funding", r.get("funding_source")),
                  ("Needs ethics approval", "yes" if r.get("needs_ethics") else "no"),
                  ("Ethics status", r.get("ethics_approval_status"))]),
            ("Description", r.get("project_description") or "—"),
            ("Team", [f"{m['name']} ({m['username']}) – {m['role']}"
                      + ("" if m["is_active"] else f" (left {m.get('leave_date') or ''})")
                      for m in r["team"]]),
            ("Ethics", [f"{e['reference']} {e['title']} – {common.nice(e['status'])}"
                        + (f", expires {e['approval_expiry_date']}"
                           if e.get("approval_expiry_date") else "") for e in r["ethics"]]),
            ("Grants", [f"#{g['application_id']} {g['grant_name']} ({g['funding_agency']}) – "
                        f"{common.nice(g['status'])}" for g in r["grants"]]),
            ("Outputs", [f"#{o['publication_id']} {o['title']} ({o['publication_type']})"
                         for o in r["outputs"]]),
            ("IP", [f"{i.get('reference') or i['disclosure_id']} {i['title']} – "
                    f"{common.nice(i['status'])}" for i in r["ip"]]),
            ("Data management plan", [self._plan_line(p) for p in r["plans"]]),
            ("Declared interests", [f"{d['username']}: {d['kind']} {d.get('counterpart') or ''}"
                                    f" – {common.nice(d['status'])}" for d in r["interests"]]),
            ("History", [f"{h['at']}  {h['actor'] or ''}  {common.nice(h['action'])}"
                         for h in r["history"]]),
        ]
        self.detail.show(r["project_title"], sections)

    @staticmethod
    def _plan_line(p):
        line = f"v{p['version']} – {common.nice(p['status'])}"
        bits = [p.get("data_types"), p.get("storage"), p.get("repository")]
        if any(bits):
            line += "; " + "; ".join(b for b in bits if b)
        if p.get("retention_years"):
            line += f"; keep {p['retention_years']} years"
        if p.get("personal_data"):
            line += f"; personal data (DPIA {p.get('dpia_reference') or 'missing'})"
        if p.get("review_note"):
            line += f"\n   Review note: {p['review_note']}"
        return line

    def actions(self, r):
        manages = rp.manages(self.who, r)
        out = []
        if manages:
            out += [("Edit", self._edit), ("Change status", self._status),
                    ("Add team member", self._add_member)]
            if any(m["is_active"] for m in r["team"]):
                out.append(("Remove team member", self._remove_member))
            out += [("Link a record", self._link), ("Write data plan", self._draft_plan)]
            if any(p["status"] in ("draft", "changes_requested") for p in r["plans"]):
                out.append(("Submit data plan", self._submit_plan))
        if self.who.is_office:
            out.append(("Change PI", self._change_pi))
            if any(p["status"] == "submitted" for p in r["plans"]):
                out += [("Approve data plan", lambda: self._review_plan(True)),
                        ("Ask for plan changes", lambda: self._review_plan(False))]
        return out

    # ── forms ──
    def _fields(self, creating):
        fields = [Field("project_title", "Title", required=True),
                  Field("department", "Department", required=creating),
                  Field("project_type", "Type", "combo", list(rp.TYPES), required=True),
                  Field("start_date", "Start date", "date", required=creating),
                  Field("end_date", "End date", "date"),
                  Field("funding_source", "Funding source"),
                  Field("needs_ethics", "Needs ethics approval", "check"),
                  Field("project_description", "Description", "multiline")]
        if creating and self.who.is_office:
            fields.insert(1, Field("principal_investigator_id", "Principal investigator",
                                   "staff", common.staff_choices(self)))
        return fields

    def _new(self):
        values = {"project_type": "Unfunded",
                  "department": common.call(self, lambda c: ra.department_of(c, self.who.username),
                                            quiet=True) or ""}
        data = common.ask(self, "New research project", self._fields(True), values)
        if data is None:
            return
        data = {k: v for k, v in data.items() if v not in ("", None) or k == "needs_ethics"}
        pid = common.call(self, rp.create, self.who, data, write=True)
        if pid is not None:
            self.current_id = pid
            self.reload()

    def _edit(self):
        r = self.record
        data = common.ask(self, "Edit project", self._fields(False), r)
        if data is not None:
            self.write(rp.update, self.who, r["project_id"], data)

    def _status(self):
        data = common.ask(self, "Change status", [
            Field("status", "Status", "combo", list(rp.STATUSES), required=True),
            Field("reason", "Reason", "multiline")], {"status": self.record.get("status")})
        if data is not None:
            self.write(rp.set_status, self.who, self.record["project_id"], data["status"],
                       data["reason"])

    def _add_member(self):
        data = common.ask(self, "Add team member", [
            Field("username", "Member of staff", "staff", common.staff_choices(self),
                  required=True),
            Field("role", "Role", "combo", list(rp.TEAM_ROLES), required=True),
            Field("contribution", "Contribution %", "number")])
        if data is not None:
            self.write(rp.add_member, self.who, self.record["project_id"], data["username"],
                       data["role"], data["contribution"])

    def _remove_member(self):
        active = [(m["username"], f"{m['name']} ({m['username']})")
                  for m in self.record["team"] if m["is_active"]]
        data = common.ask(self, "Remove team member", [
            Field("username", "Member", "combo", active, required=True)])
        if data is not None and common.confirm(self, f"Take {data['username']} off the team?"):
            self.write(rp.remove_member, self.who, self.record["project_id"], data["username"])

    def _link(self):
        data = common.ask(self, "Link a record to this project", [
            Field("kind", "Record type", "combo", list(LINK_KINDS), required=True),
            Field("record_id", "Record number", required=True,
                  hint="grant / output / IP / ethics id")])
        if data is None:
            return
        try:
            record_id = int(data["record_id"])
        except ValueError:
            common.info(self, "The record number must be a whole number.")
            return
        self.write(rp.link, self.who, data["kind"], record_id, self.record["project_id"])

    def _change_pi(self):
        data = common.ask(self, "Change principal investigator", [
            Field("new_pi", "New PI", "staff", common.staff_choices(self), required=True),
            Field("reason", "Reason", "multiline", required=True)])
        if data is not None:
            self.write(rp.transfer_pi, self.who, self.record["project_id"], data["new_pi"],
                       data["reason"])

    # ── data management plan ──
    def _draft_plan(self):
        plans = self.record["plans"]
        current = next((p for p in plans if p["status"] in ("draft", "changes_requested")),
                       plans[0] if plans else {})
        data = common.ask(self, "Data management plan", [
            Field("data_types", "Data to be collected", "multiline", required=True),
            Field("storage", "Storage and security", "multiline", required=True),
            Field("sharing", "Sharing and access", "multiline", required=True),
            Field("repository", "Repository"),
            Field("retention_years", "Keep for (years)", required=True),
            Field("personal_data", "Involves personal data", "check"),
            Field("dpia_reference", "DPIA reference")], current)
        if data is not None:
            self.write(integrity.draft_plan, self.who, self.record["project_id"], data,
                       done="Saved as a draft. Submit it when it is ready.")

    def _open_plan(self, status):
        return next((p for p in self.record["plans"] if p["status"] in status), None)

    def _submit_plan(self):
        plan = self._open_plan(("draft", "changes_requested"))
        if plan:
            self.write(integrity.submit_plan, self.who, plan["plan_id"],
                       done="Sent to the research office for review.")

    def _review_plan(self, approve):
        plan = self._open_plan(("submitted",))
        if not plan:
            return
        note = "" if approve else common.ask_text(self, "Ask for changes", "What needs changing")
        if note is None:
            return
        self.write(integrity.review_plan, self.who, plan["plan_id"], approve, note)
