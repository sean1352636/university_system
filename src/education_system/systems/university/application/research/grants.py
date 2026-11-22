"""Research grants from costing to closure.

draft → awaiting_approval → approved_to_submit → submitted → awarded /
rejected → active → closed (or withdrawn before an outcome).

* **Costing** is full economic cost (fEC): directly incurred, directly
  allocated and indirect costs are paid by the funder at the funder's rate
  (80% for UKRI); exceptions are paid in full. The price to the funder
  becomes the amount requested; the rest is the university's contribution.
* **Internal approval**: the head of the PI's department and the research
  office both sign off before submission. Where no head of department is
  set up for that department, the office's approval stands for both.
* **Accepting an award** needs an approved ethics application when the grant
  needs one and an approved data management plan when the funder requires
  one; it turns the costing into budget lines, schedules the final reports
  and tells Finance (``publish_grant_decision``).
* **Spend** is recorded against budget lines and may not overspend a line
  unless the research office allows it. A grant closes once every report is in.

Grants live on ``grant_applications`` / ``grant_budgets``.
Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.research import access as ra

STATUSES = ("draft", "awaiting_approval", "approved_to_submit", "submitted", "awarded",
            "rejected", "active", "closed", "withdrawn")
COST_CATEGORIES = {"directly_incurred": "Directly incurred", "directly_allocated":
                   "Directly allocated", "indirect": "Indirect (estates and overheads)",
                   "exception": "Exceptions (paid at 100%)"}
REPORT_KINDS = ("interim", "final", "financial", "other")
_FIELDS = ("grant_name", "title", "funding_agency", "scheme", "application_deadline",
           "department", "funder_rate", "ethics_required", "dmp_required", "project_id")


def grant(conn, application_id) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM grant_applications WHERE application_id = ?",
                 (application_id,))
    if not row:
        raise ValueError("No such grant application")
    row["status"] = row.get("status") or "draft"
    return row


def _co_is(row) -> list[str]:
    return [c.strip() for c in (row.get("co_investigators") or "").split(",") if c.strip()]


def manages(who, row) -> bool:
    return who.is_office or who.username == row.get("principal_investigator_id")


def can_see(who, row) -> bool:
    return manages(who, row) or who.username in _co_is(row) or who.heads(row.get("department"))


def _clean(conn, data) -> dict:
    out = {}
    for key in _FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key == "application_deadline":
            value = ra.iso_date(value, "Funder deadline", True)
        elif key == "funder_rate":
            value = float(value if value not in (None, "") else 80)
            if not 0 < value <= 100:
                raise ValueError("The funder rate must be 1 to 100%")
        elif key in ("ethics_required", "dmp_required"):
            value = int(bool(value))
        elif key == "project_id":
            value = int(value) if value not in (None, "") else None
            if value and not conn.execute("SELECT 1 FROM research_projects WHERE project_id = ?",
                                          (value,)).fetchone():
                raise ValueError("No such research project")
        else:
            value = ra.text(value, key.replace("_", " "), key in ("grant_name", "funding_agency"))
        out[key] = value
    return out


def _co_investigators(conn, value) -> str | None:
    names = [v.strip() for v in str(value or "").replace(";", ",").split(",") if v.strip()]
    for name in names:
        ra.staff_ref(conn, name, "Co-investigator")
    return ", ".join(dict.fromkeys(names)) or None


def create(conn, who, data) -> int:
    ra.ensure(conn)
    ra.require_staff(who)
    fields = _clean(conn, {"funder_rate": 80, **data})
    for key, label in (("grant_name", "Grant name"), ("funding_agency", "Funder"),
                       ("application_deadline", "Funder deadline")):
        if not fields.get(key):
            raise ValueError(f"{label} is required")
    pi = ra.staff_ref(conn, data.get("principal_investigator_id") or who.username,
                      "Principal investigator")
    ra.require(pi == who.username or who.is_office,
               "Only the research office can start an application for someone else")
    fields.setdefault("department", ra.department_of(conn, pi) or None)
    fields["co_investigators"] = _co_investigators(conn, data.get("co_investigators"))
    cols = ["principal_investigator_id", "requested_amount", "status", "decision_status",
            "created_by", *fields]
    gid = conn.execute(
        f"INSERT INTO grant_applications ({', '.join(cols)}) VALUES "
        f"({', '.join('?' * len(cols))})",
        [pi, 0, "draft", "pending", who.username, *fields.values()]).lastrowid
    ra.audit(conn, who, "grant", gid, "created")
    return int(gid)


def _draft(conn, who, application_id) -> dict:
    row = grant(conn, application_id)
    ra.require(manages(who, row), "Only the principal investigator can change this application")
    if row["status"] != "draft":
        raise ValueError("Only a draft application can be changed")
    return row


def update(conn, who, application_id, data) -> None:
    _draft(conn, who, application_id)
    fields = _clean(conn, data)
    if "co_investigators" in data:
        fields["co_investigators"] = _co_investigators(conn, data["co_investigators"])
    if fields:
        conn.execute(f"UPDATE grant_applications SET {', '.join(f'{k} = ?' for k in fields)} "
                     "WHERE application_id = ?", (*fields.values(), application_id))
        _reprice(conn, application_id)
        ra.audit(conn, who, "grant", application_id, "edited", {"fields": sorted(fields)})


# ── costing ─────────────────────────────────────────────────────────────


def add_cost_line(conn, who, application_id, category, item, amount) -> int:
    _draft(conn, who, application_id)
    if category not in COST_CATEGORIES:
        raise ValueError("Category must be one of " + ", ".join(COST_CATEGORIES))
    line = conn.execute("INSERT INTO grant_cost_lines (application_id, category, item, amount) "
                        "VALUES (?, ?, ?, ?)",
                        (application_id, category, ra.text(item, "Item", True),
                         ra.money(amount, "Amount"))).lastrowid
    _reprice(conn, application_id)
    return int(line)


def remove_cost_line(conn, who, line_id) -> None:
    row = conn.execute("SELECT application_id FROM grant_cost_lines WHERE line_id = ?",
                       (line_id,)).fetchone()
    if not row:
        raise ValueError("No such cost line")
    _draft(conn, who, row[0])
    conn.execute("DELETE FROM grant_cost_lines WHERE line_id = ?", (line_id,))
    _reprice(conn, row[0])


def costing(conn, application_id) -> dict:
    row = grant(conn, application_id)
    rate = float(row.get("funder_rate") or 80) / 100
    lines = ra.dicts(conn.execute("SELECT * FROM grant_cost_lines WHERE application_id = ? "
                                  "ORDER BY category, line_id", (application_id,)))
    totals = {c: 0.0 for c in COST_CATEGORIES}
    for line in lines:
        totals[line["category"]] += float(line["amount"])
    fec = round(sum(totals.values()), 2)
    price = round((fec - totals["exception"]) * rate + totals["exception"], 2)
    return {"lines": lines, "totals": totals, "fec": fec, "price": price,
            "university_contribution": round(fec - price, 2), "rate": rate * 100}


def _reprice(conn, application_id) -> None:
    conn.execute("UPDATE grant_applications SET requested_amount = ? WHERE application_id = ?",
                 (costing(conn, application_id)["price"], application_id))


# ── internal approval and submission ────────────────────────────────────


def _approvers(conn, row) -> list[str]:
    heads = ra.holders(conn, "head_of_department", row.get("department") or "")
    return heads + ra.holders(conn, "research_office")


def request_approval(conn, who, application_id) -> list:
    row = _draft(conn, who, application_id)
    if not costing(conn, application_id)["lines"]:
        raise ValueError("Cost the application before asking for approval")
    if row["application_deadline"] < ra.today():
        raise ValueError("The funder deadline has passed")
    conn.execute("UPDATE grant_applications SET status = 'awaiting_approval', hod_approved_by = "
                 "NULL, hod_approved_at = NULL, office_approved_by = NULL, office_approved_at = "
                 "NULL WHERE application_id = ?", (application_id,))
    ra.audit(conn, who, "grant", application_id, "approval_requested")
    return ra.notify(conn, _approvers(conn, row), f"Grant application to approve: "
                     f"{row['grant_name']}", f"{row['grant_name']} to {row['funding_agency']} "
                     f"(deadline {row['application_deadline']}) needs sign-off.")


def approve(conn, who, application_id, note="") -> list:
    """Head-of-department and/or research-office sign-off, as ``who`` may give."""
    row = grant(conn, application_id)
    if row["status"] != "awaiting_approval":
        raise ValueError("This application is not waiting for approval")
    ra.require(who.username != row["principal_investigator_id"] or who.is_admin,
               "You cannot approve your own application")
    as_head = who.heads(row.get("department")) and not row.get("hod_approved_at")
    as_office = who.is_office and not row.get("office_approved_at")
    ra.require(as_head or as_office, "You cannot approve this application (or already have)")
    sets = {}
    if as_head:
        sets.update(hod_approved_by=who.username, hod_approved_at=ra.now())
    if as_office:
        sets.update(office_approved_by=who.username, office_approved_at=ra.now())
        if not ra.holders(conn, "head_of_department", row.get("department") or "") and \
                not row.get("hod_approved_at") and "hod_approved_at" not in sets:
            sets.update(hod_approved_by=f"{who.username} (no head of department set)",
                        hod_approved_at=ra.now())
    done = (sets.get("hod_approved_at") or row.get("hod_approved_at")) and \
        (sets.get("office_approved_at") or row.get("office_approved_at"))
    if done:
        sets["status"] = "approved_to_submit"
    conn.execute(f"UPDATE grant_applications SET {', '.join(f'{k} = ?' for k in sets)} WHERE "
                 "application_id = ?", (*sets.values(), application_id))
    ra.audit(conn, who, "grant", application_id, "approved",
             {"as": [k for k, v in (("head", as_head), ("office", as_office)) if v],
              "note": note})
    if done:
        return ra.notify(conn, [row["principal_investigator_id"]],
                         f"Approved to submit: {row['grant_name']}",
                         "Your application has internal approval and can be submitted.")
    return []


def return_for_changes(conn, who, application_id, note) -> list:
    row = grant(conn, application_id)
    ra.require(who.is_office or who.heads(row.get("department")),
               "Only an approver can return an application")
    if row["status"] != "awaiting_approval":
        raise ValueError("This application is not waiting for approval")
    note = ra.text(note, "What needs changing", True)
    conn.execute("UPDATE grant_applications SET status = 'draft', decision_note = ? WHERE "
                 "application_id = ?", (note, application_id))
    ra.audit(conn, who, "grant", application_id, "returned", {"note": note})
    return ra.notify(conn, [row["principal_investigator_id"]],
                     f"Grant application returned: {row['grant_name']}", note)


def mark_submitted(conn, who, application_id, submitted_on=None) -> None:
    row = grant(conn, application_id)
    ra.require(manages(who, row), "Only the principal investigator can do this")
    if row["status"] != "approved_to_submit":
        raise ValueError("The application needs internal approval before it is submitted")
    conn.execute("UPDATE grant_applications SET status = 'submitted', submission_date = ? WHERE "
                 "application_id = ?",
                 (ra.iso_date(submitted_on, "Submitted on") or ra.today(), application_id))
    ra.audit(conn, who, "grant", application_id, "submitted")


def record_outcome(conn, who, application_id, outcome, *, amount=None, start=None, end=None,
                   award_reference=None, note="") -> list:
    row = grant(conn, application_id)
    ra.require(who.is_office, "Only the research office records funder decisions")
    if row["status"] != "submitted":
        raise ValueError("Only a submitted application gets an outcome")
    if outcome not in ("awarded", "rejected"):
        raise ValueError("Outcome must be awarded or rejected")
    sets = {"status": outcome, "decision_status": outcome, "decision_date": ra.today(),
            "decision_note": note or None}
    if outcome == "awarded":
        start = ra.iso_date(start, "Start date", True)
        end = ra.iso_date(end, "End date", True)
        if end <= start:
            raise ValueError("The grant must end after it starts")
        sets.update(awarded_amount=ra.money(amount, "Amount awarded"), grant_period_start=start,
                    grant_period_end=end, award_reference=ra.text(award_reference, "Reference"))
        if not sets["awarded_amount"]:
            raise ValueError("Amount awarded is required")
    conn.execute(f"UPDATE grant_applications SET {', '.join(f'{k} = ?' for k in sets)} WHERE "
                 "application_id = ?", (*sets.values(), application_id))
    ra.audit(conn, who, "grant", application_id, outcome, {"amount": sets.get("awarded_amount")})
    return ra.notify(conn, [row["principal_investigator_id"], *_co_is(row)],
                     f"Funder decision: {row['grant_name']}",
                     f"{row['grant_name']} was {outcome}." + (f"\n{note}" if note else ""))


def acceptance_blockers(conn, row) -> list[str]:
    from education_system.systems.university.application.research import ethics as research_ethics
    problems = []
    project = row.get("project_id")
    if (row.get("ethics_required") or row.get("dmp_required")) and not project:
        problems.append("Link the grant to a research project first")
        return problems
    if row.get("ethics_required") and not research_ethics.has_approval(conn, project):
        problems.append("The project has no current ethics approval")
    if row.get("dmp_required") and not conn.execute(
            "SELECT 1 FROM research_data_plans WHERE project_id = ? AND status = 'approved'",
            (project,)).fetchone():
        problems.append("The project has no approved data management plan")
    return problems


def accept_award(conn, who, application_id) -> None:
    """Start the grant: budget lines from the costing, final reports due
    90 days after the end, and Finance told about the award."""
    row = grant(conn, application_id)
    ra.require(who.is_office, "Only the research office can accept an award")
    if row["status"] != "awarded":
        raise ValueError("Only an awarded grant can be accepted")
    problems = acceptance_blockers(conn, row)
    if problems:
        raise ValueError("; ".join(problems))
    cost = costing(conn, application_id)
    scale = float(row["awarded_amount"]) / cost["price"] if cost["price"] else 0
    rate = cost["rate"] / 100
    parts = [(c, t if c == "exception" else t * rate) for c, t in cost["totals"].items() if t]
    allotted = 0.0
    for n, (category, paid) in enumerate(parts):
        approved = round(paid * scale, 2) if n < len(parts) - 1 else \
            round(float(row["awarded_amount"]) - allotted, 2)
        allotted += approved
        conn.execute("INSERT INTO grant_budgets (application_id, category, description, "
                     "requested_amount, approved_amount, spent_amount, remaining_amount) VALUES "
                     "(?, ?, ?, ?, ?, 0, ?)",
                     (application_id, category, COST_CATEGORIES[category], round(paid, 2),
                      approved, approved))
    due = (date.fromisoformat(row["grant_period_end"]) + timedelta(days=90)).isoformat()
    for kind in ("final", "financial"):
        conn.execute("INSERT INTO grant_reports (application_id, kind, due_date) VALUES (?, ?, ?)",
                     (application_id, kind, due))
    conn.execute("UPDATE grant_applications SET status = 'active', accepted_by = ?, accepted_at "
                 "= ? WHERE application_id = ?", (who.username, ra.now(), application_id))
    ra.audit(conn, who, "grant", application_id, "accepted")
    _tell_finance(row)


def _tell_finance(row) -> None:
    try:
        from education_system.systems.university.services.bus.integration.finance.subscribers import (  # noqa: E501
            publish_grant_decision,
        )
    except ImportError:
        return
    publish_grant_decision(row["application_id"], status="awarded", grant_name=row["grant_name"],
                           awarded_amount=float(row["awarded_amount"] or 0),
                           pi_id=row["principal_investigator_id"],
                           grant_period_start=row["grant_period_start"],
                           grant_period_end=row["grant_period_end"])


# ── spend and reports ───────────────────────────────────────────────────


def budget(conn, application_id) -> dict:
    row = grant(conn, application_id)
    lines = ra.dicts(conn.execute("SELECT * FROM grant_budgets WHERE application_id = ? ORDER BY "
                                  "budget_id", (application_id,)))
    total = sum(float(b["approved_amount"] or 0) for b in lines)
    spent = sum(float(b["spent_amount"] or 0) for b in lines)
    elapsed = None
    if row.get("grant_period_start") and row.get("grant_period_end"):
        start = date.fromisoformat(row["grant_period_start"])
        end = date.fromisoformat(row["grant_period_end"])
        span = max((end - start).days, 1)
        elapsed = round(100 * min(max((date.today() - start).days, 0), span) / span, 1)
    return {"lines": lines, "total": round(total, 2), "spent": round(spent, 2),
            "remaining": round(total - spent, 2),
            "spent_pct": round(100 * spent / total, 1) if total else 0.0,
            "time_pct": elapsed}


def record_spend(conn, who, budget_id, amount, spent_on, description,
                 allow_overspend=False) -> int:
    line = ra.one(conn, "SELECT * FROM grant_budgets WHERE budget_id = ?", (budget_id,))
    if not line:
        raise ValueError("No such budget line")
    row = grant(conn, line["application_id"])
    ra.require(manages(who, row) or who.username in _co_is(row),
               "Only the grant holders can record spend")
    if row["status"] != "active":
        raise ValueError("Spend can only be recorded on an active grant")
    amount = ra.money(amount, "Amount")
    if not amount:
        raise ValueError("Amount must be more than zero")
    day = ra.iso_date(spent_on, "Date spent", True)
    if not (row["grant_period_start"] <= day <= row["grant_period_end"]):
        raise ValueError("The spend falls outside the grant period")
    remaining = float(line["approved_amount"] or 0) - float(line["spent_amount"] or 0)
    if amount > remaining + 0.005 and not (allow_overspend and who.is_office):
        raise ValueError(f"That would overspend the line (£{remaining:,.2f} left)")
    sid = conn.execute("INSERT INTO grant_spend (budget_id, amount, spent_on, description, "
                       "recorded_by) VALUES (?, ?, ?, ?, ?)",
                       (budget_id, amount, day, ra.text(description, "Description", True),
                        who.username)).lastrowid
    conn.execute("UPDATE grant_budgets SET spent_amount = COALESCE(spent_amount, 0) + ?, "
                 "remaining_amount = COALESCE(approved_amount, 0) - COALESCE(spent_amount, 0) - ? "
                 "WHERE budget_id = ?", (amount, amount, budget_id))
    ra.audit(conn, who, "grant", line["application_id"], "spend",
             {"line": line["category"], "amount": amount})
    return int(sid)


def spend(conn, application_id) -> list[dict]:
    return ra.dicts(conn.execute(
        "SELECT s.*, b.category FROM grant_spend s JOIN grant_budgets b ON b.budget_id = "
        "s.budget_id WHERE b.application_id = ? ORDER BY s.spent_on DESC, s.spend_id DESC",
        (application_id,)))


def add_report(conn, who, application_id, kind, due_date, note="") -> int:
    row = grant(conn, application_id)
    ra.require(manages(who, row), "Only the grant holders can schedule reports")
    if kind not in REPORT_KINDS:
        raise ValueError("Kind must be one of " + ", ".join(REPORT_KINDS))
    rid = conn.execute("INSERT INTO grant_reports (application_id, kind, due_date, note) VALUES "
                       "(?, ?, ?, ?)", (application_id, kind,
                                        ra.iso_date(due_date, "Due date", True),
                                        note or None)).lastrowid
    return int(rid)


def submit_report(conn, who, report_id, note="") -> None:
    rep = ra.one(conn, "SELECT * FROM grant_reports WHERE report_id = ?", (report_id,))
    if not rep:
        raise ValueError("No such report")
    row = grant(conn, rep["application_id"])
    ra.require(manages(who, row) or who.username in _co_is(row),
               "Only the grant holders can submit reports")
    if rep["submitted_at"]:
        raise ValueError("That report is already submitted")
    conn.execute("UPDATE grant_reports SET submitted_at = ?, submitted_by = ?, note = COALESCE(?, "
                 "note) WHERE report_id = ?", (ra.now(), who.username, note or None, report_id))
    ra.audit(conn, who, "grant", rep["application_id"], "report_submitted", {"kind": rep["kind"]})


def reports(conn, application_id) -> list[dict]:
    return ra.dicts(conn.execute("SELECT * FROM grant_reports WHERE application_id = ? ORDER BY "
                                 "due_date", (application_id,)))


def close(conn, who, application_id) -> None:
    row = grant(conn, application_id)
    ra.require(who.is_office, "Only the research office can close a grant")
    if row["status"] != "active":
        raise ValueError("Only an active grant can be closed")
    if conn.execute("SELECT 1 FROM grant_reports WHERE application_id = ? AND submitted_at IS "
                    "NULL", (application_id,)).fetchone():
        raise ValueError("Every report must be submitted before the grant closes")
    conn.execute("UPDATE grant_applications SET status = 'closed', closed_at = ? WHERE "
                 "application_id = ?", (ra.now(), application_id))
    ra.audit(conn, who, "grant", application_id, "closed")


def withdraw(conn, who, application_id, reason) -> None:
    row = grant(conn, application_id)
    ra.require(manages(who, row), "Only the principal investigator can withdraw this")
    if row["status"] not in ("draft", "awaiting_approval", "approved_to_submit", "submitted"):
        raise ValueError("This application can no longer be withdrawn")
    conn.execute("UPDATE grant_applications SET status = 'withdrawn', decision_status = "
                 "'withdrawn' WHERE application_id = ?", (application_id,))
    ra.audit(conn, who, "grant", application_id, "withdrawn",
             {"reason": ra.text(reason, "Reason", True)})


# ── lists and summaries ─────────────────────────────────────────────────


def listing(conn, who, status=None, search=None) -> list[dict]:
    ra.ensure(conn)
    rows = ra.dicts(conn.execute("SELECT * FROM grant_applications ORDER BY application_id "
                                 "DESC"))
    needle = (search or "").lower()
    out = []
    for row in rows:
        row["status"] = row.get("status") or "draft"
        if not can_see(who, row) or (status and row["status"] != status):
            continue
        hay = " ".join(str(row.get(k) or "") for k in ("grant_name", "funding_agency",
                                                         "department", "award_reference"))
        if not needle or needle in hay.lower():
            out.append(row)
    return out


def approvals_for(conn, who) -> list[dict]:
    """Applications waiting for ``who``'s sign-off."""
    out = []
    for row in listing(conn, who, "awaiting_approval"):
        if row["principal_investigator_id"] == who.username and not who.is_admin:
            continue
        if (who.heads(row.get("department")) and not row.get("hod_approved_at")) or \
                (who.is_office and not row.get("office_approved_at")):
            out.append(row)
    return out


def record(conn, who, application_id) -> dict:
    row = grant(conn, application_id)
    ra.require(can_see(who, row), "You cannot see this grant")
    row["costing"] = costing(conn, application_id)
    row["budget"] = budget(conn, application_id)
    row["spend"] = spend(conn, application_id)
    row["reports"] = reports(conn, application_id)
    row["blockers"] = acceptance_blockers(conn, row) if row["status"] == "awarded" else []
    row["history"] = ra.history(conn, "grant", application_id)
    return row


def pipeline(conn, who) -> dict:
    rows = listing(conn, who)
    by_status = {s: 0 for s in STATUSES}
    by_dept: dict[str, dict] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        dept = by_dept.setdefault(row.get("department") or "—",
                                  {"applications": 0, "requested": 0.0, "awarded": 0.0})
        dept["applications"] += 1
        dept["requested"] += float(row.get("requested_amount") or 0)
        if row["status"] in ("awarded", "active", "closed"):
            dept["awarded"] += float(row.get("awarded_amount") or 0)
    won = sum(by_status[s] for s in ("awarded", "active", "closed"))
    decided = won + by_status["rejected"]
    return {"by_status": by_status, "by_department": by_dept,
            "success_rate": round(100 * won / decided, 1) if decided else None}


def due(conn, days=30, as_of=None) -> dict:
    """Funder deadlines coming up on unsubmitted applications, and reports
    due or overdue on active grants."""
    ra.ensure(conn)
    day = date.fromisoformat(ra.iso_date(as_of, "Date") or ra.today())
    until = (day + timedelta(days=int(days))).isoformat()
    deadlines = ra.dicts(conn.execute(
        "SELECT application_id, grant_name, principal_investigator_id, application_deadline, "
        "status FROM grant_applications WHERE COALESCE(status, 'draft') IN ('draft', "
        "'awaiting_approval', 'approved_to_submit') AND application_deadline BETWEEN ? AND ? "
        "ORDER BY application_deadline", (day.isoformat(), until)))
    reports_due = ra.dicts(conn.execute(
        "SELECT r.report_id, r.kind, r.due_date, g.application_id, g.grant_name, "
        "g.principal_investigator_id FROM grant_reports r JOIN grant_applications g ON "
        "g.application_id = r.application_id WHERE r.submitted_at IS NULL AND r.due_date <= ? "
        "ORDER BY r.due_date", (until,)))
    return {"deadlines": deadlines, "reports": reports_due}
