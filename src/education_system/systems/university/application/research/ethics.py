"""Research ethics review: application → (supervisor endorsement for
students) → reviewers allocated → reviews → chair's decision with conditions
→ amendments, renewals and expiry.

Applications live on ``ethics_reviews``. Its old ``decision`` column holds
the workflow status (the portal always read it as the status).

Routing by risk: low-risk applications need one review, medium and high
two; high-risk and clinical studies go to the full committee. Reviewers may
not review an application they are named on or connected to through the
project team, and must declare any other conflict, which hands the
allocation back for someone else.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.research import access as ra

STATUSES = ("draft", "awaiting_supervisor", "submitted", "under_review",
            "revisions_required", "approved", "rejected", "withdrawn", "expired", "closed")
OPEN = ("draft", "awaiting_supervisor", "submitted", "under_review", "revisions_required")
CATEGORIES = ("Human participants", "Animal", "Data-only", "Clinical", "Environmental", "Other")
RISK_LEVELS = ("Low", "Medium", "High")
DECISIONS = ("approve", "approve_with_conditions", "revise", "reject")
RECOMMENDATIONS = DECISIONS
APPROVAL_YEARS = 3
_EDITABLE = ("title", "category", "risk_level", "summary", "participants", "data_handling",
             "start_date", "end_date", "department", "project_id", "notes")


def _status(row) -> str:
    value = (row.get("decision") or "").lower()
    return "submitted" if value in ("", "pending") else value


def required_reviews(risk) -> int:
    return 1 if (risk or "").lower() == "low" else 2


def route_for(risk, category) -> str:
    if (risk or "").lower() == "high" or (category or "").lower() == "clinical":
        return "full committee"
    return "proportionate" if (risk or "").lower() == "low" else "committee"


def application(conn, review_id) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM ethics_reviews WHERE review_id = ?", (review_id,))
    if not row:
        raise ValueError("No such ethics application")
    row["status"] = _status(row)
    return row


def _owns(who, row) -> bool:
    return who.me in (row.get("applicant_id"), row.get("principal_investigator_id"),
                      row.get("created_by")) or who.username == row.get("principal_investigator_id")


def _connected(conn, row) -> set:
    """Everyone named on the application or on its project's team."""
    people = {row.get(k) for k in ("applicant_id", "principal_investigator_id", "supervisor_id")}
    if row.get("project_id"):
        people |= {r[0] for r in conn.execute(
            "SELECT staff_id FROM research_team_members WHERE project_id = ? AND is_active = 1",
            (row["project_id"],))}
        p = conn.execute("SELECT principal_investigator_id FROM research_projects WHERE "
                         "project_id = ?", (row["project_id"],)).fetchone()
        if p:
            people.add(p[0])
    return {p for p in people if p}


def can_see(conn, who, row) -> bool:
    if who.chairs_ethics or _owns(who, row) or who.username == row.get("supervisor_id"):
        return True
    return conn.execute("SELECT 1 FROM ethics_reviewer_allocations WHERE review_id = ? AND "
                        "reviewer = ?", (row["review_id"], who.username)).fetchone() is not None


def _next_reference(conn) -> str:
    year = date.today().year
    n = conn.execute("SELECT COUNT(*) FROM ethics_reviews WHERE reference LIKE ?",
                     (f"ETH-{year}-%",)).fetchone()[0]
    while True:
        n += 1
        ref = f"ETH-{year}-{n:03d}"
        if not conn.execute("SELECT 1 FROM ethics_reviews WHERE reference = ?",
                            (ref,)).fetchone():
            return ref


def _clean(conn, data) -> dict:
    out = {}
    for key in _EDITABLE:
        if key not in data:
            continue
        value = data[key]
        if key in ("start_date", "end_date"):
            value = ra.iso_date(value, key.replace("_", " ").capitalize())
        elif key == "project_id":
            value = int(value) if value not in (None, "") else None
            if value and not conn.execute("SELECT 1 FROM research_projects WHERE project_id = ?",
                                          (value,)).fetchone():
                raise ValueError("No such research project")
        elif key == "category" and value and value not in CATEGORIES:
            raise ValueError("Unknown category")
        elif key == "risk_level" and value and value not in RISK_LEVELS:
            raise ValueError("Risk level must be Low, Medium or High")
        else:
            value = ra.text(value, key)
        out[key] = value
    if out.get("start_date") and out.get("end_date") and out["end_date"] < out["start_date"]:
        raise ValueError("The study must end after it starts")
    return out


def create(conn, who, data) -> int:
    """A draft application owned by ``who``. Students name their supervisor."""
    ra.ensure(conn)
    ra.require(who is not None, "Sign in first")
    fields = _clean(conn, data)
    if not fields.get("title"):
        raise ValueError("Study title is required")
    supervisor = None
    if who.is_student:
        supervisor = ra.staff_ref(conn, data.get("supervisor_id"), "Supervisor")
        pi = supervisor
    else:
        pi = ra.staff_ref(conn, data.get("principal_investigator_id") or who.username,
                          "Principal investigator")
    fields.setdefault("department", ra.department_of(conn, pi) or None)
    cols = ["reference", "review_type", "submission_date", "decision", "kind", "applicant_id",
            "principal_investigator_id", "supervisor_id", "created_by", "updated_at", *fields]
    vals = [_next_reference(conn), fields.get("category") or "Research ethics application",
            ra.today(), "draft", "application", who.me, pi, supervisor, who.me, ra.now(),
            *fields.values()]
    rid = conn.execute(f"INSERT INTO ethics_reviews ({', '.join(cols)}) VALUES "
                       f"({', '.join('?' * len(cols))})", vals).lastrowid
    ra.audit(conn, who, "ethics", rid, "created")
    return int(rid)


def update(conn, who, review_id, data) -> None:
    row = application(conn, review_id)
    ra.require(_owns(who, row) or who.is_office, "Only the applicant can edit this application")
    if row["status"] not in ("draft", "revisions_required"):
        raise ValueError("Only a draft, or one sent back for revisions, can be edited")
    fields = _clean(conn, data)
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE ethics_reviews SET {sets}, updated_at = ? WHERE review_id = ?",
                 (*fields.values(), ra.now(), review_id))
    ra.audit(conn, who, "ethics", review_id, "edited", {"fields": sorted(fields)})


def _missing(row) -> list[str]:
    need = ["title", "category", "risk_level", "summary", "start_date", "end_date"]
    if (row.get("category") or "") in ("Human participants", "Clinical"):
        need += ["participants", "data_handling"]
    return [k.replace("_", " ") for k in need if not row.get(k)]


def submit(conn, who, review_id) -> list:
    """Send a draft (or a revised application) for review. Returns e-mails."""
    row = application(conn, review_id)
    ra.require(_owns(who, row), "Only the applicant can submit this application")
    if row["status"] not in ("draft", "revisions_required"):
        raise ValueError(f"An application that is {row['status']} cannot be submitted")
    missing = _missing(row)
    if missing:
        raise ValueError("Fill in before submitting: " + ", ".join(missing))
    route = route_for(row["risk_level"], row["category"])
    endorsed = bool(row.get("supervisor_endorsed_at"))
    if row.get("supervisor_id") and not endorsed:
        status, to = "awaiting_supervisor", [row["supervisor_id"]]
    else:
        reopened = _reopen_reviews(conn, review_id)
        status = "under_review" if reopened else "submitted"
        to = (_active_reviewers(conn, review_id) if reopened
              else ra.holders(conn, "ethics_chair") or ra.holders(conn, "research_office"))
    conn.execute("UPDATE ethics_reviews SET decision = ?, route = ?, submission_date = ?, "
                 "updated_at = ? WHERE review_id = ?",
                 (status, route, ra.today(), ra.now(), review_id))
    ra.audit(conn, who, "ethics", review_id, "submitted", {"status": status, "route": route})
    return ra.notify(conn, to, f"Ethics application {row['reference']} needs attention",
                     f"{row['reference']} – {row['title']} is {status.replace('_', ' ')}.")


def _reopen_reviews(conn, review_id) -> int:
    return conn.execute("UPDATE ethics_reviewer_allocations SET status = 'allocated', "
                        "recommendation = NULL, completed_at = NULL WHERE review_id = ? AND "
                        "status = 'completed'", (review_id,)).rowcount


def _active_reviewers(conn, review_id) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT reviewer FROM ethics_reviewer_allocations WHERE review_id = ? AND status IN "
        "('allocated', 'completed')", (review_id,))]


def endorse(conn, who, review_id, approve, note="") -> list:
    """The student's supervisor signs the application off (or sends it back)."""
    row = application(conn, review_id)
    ra.require(who.username == row.get("supervisor_id") or who.is_office,
               "Only the named supervisor can endorse this application")
    if row["status"] != "awaiting_supervisor":
        raise ValueError("This application is not waiting for its supervisor")
    if approve:
        conn.execute("UPDATE ethics_reviews SET decision = 'submitted', supervisor_endorsed_by "
                     "= ?, supervisor_endorsed_at = ?, updated_at = ? WHERE review_id = ?",
                     (who.username, ra.now(), ra.now(), review_id))
        to = ra.holders(conn, "ethics_chair") or ra.holders(conn, "research_office")
    else:
        if not (note or "").strip():
            raise ValueError("Say what needs changing")
        conn.execute("UPDATE ethics_reviews SET decision = 'revisions_required', "
                     "reviewer_comments = ?, updated_at = ? WHERE review_id = ?",
                     (note, ra.now(), review_id))
        to = [row["applicant_id"]]
    ra.audit(conn, who, "ethics", review_id, "endorsed" if approve else "returned_by_supervisor",
             {"note": note} if note else None)
    return ra.notify(conn, to, f"Ethics application {row['reference']}",
                     f"{row['reference']} was {'endorsed' if approve else 'returned'} by the "
                     f"supervisor." + (f"\n{note}" if note else ""))


def allocate(conn, who, review_id, reviewer) -> list:
    row = application(conn, review_id)
    ra.require(who.chairs_ethics, "Only the ethics chair can allocate reviewers")
    if row["status"] not in ("submitted", "under_review"):
        raise ValueError("Only submitted applications can be given reviewers")
    reviewer = ra.staff_ref(conn, reviewer, "Reviewer")
    if not (reviewer in ra.holders(conn, "ethics_reviewer")
            or reviewer in ra.holders(conn, "ethics_chair")):
        raise ValueError(f"{reviewer} is not an ethics reviewer")
    if reviewer in _connected(conn, row):
        raise ValueError(f"{reviewer} is connected to this application and cannot review it")
    if conn.execute("SELECT 1 FROM ethics_reviewer_allocations WHERE review_id = ? AND "
                    "reviewer = ? AND status IN ('allocated', 'completed', 'conflicted')",
                    (review_id, reviewer)).fetchone():
        raise ValueError(f"{reviewer} is already allocated (or has declared a conflict)")
    conn.execute("INSERT INTO ethics_reviewer_allocations (review_id, reviewer, allocated_by) "
                 "VALUES (?, ?, ?)", (review_id, reviewer, who.username))
    conn.execute("UPDATE ethics_reviews SET decision = 'under_review', review_date = "
                 "COALESCE(review_date, ?), updated_at = ? WHERE review_id = ?",
                 (ra.today(), ra.now(), review_id))
    ra.audit(conn, who, "ethics", review_id, "reviewer_allocated", {"reviewer": reviewer})
    return ra.notify(conn, [reviewer], f"Ethics review requested: {row['reference']}",
                     f"Please review {row['reference']} – {row['title']}. If you have a "
                     "conflict of interest, declare it in the Research Portal.")


def _allocation(conn, allocation_id) -> dict:
    row = ra.one(conn, "SELECT * FROM ethics_reviewer_allocations WHERE allocation_id = ?",
                 (allocation_id,))
    if not row:
        raise ValueError("No such review allocation")
    return row


def declare_conflict(conn, who, allocation_id, detail) -> list:
    alloc = _allocation(conn, allocation_id)
    ra.require(who.username == alloc["reviewer"], "Only the reviewer can declare a conflict")
    if alloc["status"] != "allocated":
        raise ValueError("This review is no longer open")
    detail = ra.text(detail, "Conflict details", True)
    conn.execute("UPDATE ethics_reviewer_allocations SET status = 'conflicted', "
                 "conflict_detail = ?, completed_at = ? WHERE allocation_id = ?",
                 (detail, ra.now(), allocation_id))
    row = application(conn, alloc["review_id"])
    ra.audit(conn, who, "ethics", alloc["review_id"], "conflict_declared", {"detail": detail})
    return ra.notify(conn, ra.holders(conn, "ethics_chair"),
                     f"Reviewer conflict on {row['reference']}",
                     f"{who.username} declared a conflict and cannot review {row['reference']}. "
                     "Please allocate another reviewer.")


def submit_review(conn, who, allocation_id, recommendation, comments) -> list:
    alloc = _allocation(conn, allocation_id)
    ra.require(who.username == alloc["reviewer"], "Only the allocated reviewer can do this")
    if alloc["status"] != "allocated":
        raise ValueError("This review is no longer open")
    if recommendation not in RECOMMENDATIONS:
        raise ValueError("Recommendation must be one of " + ", ".join(RECOMMENDATIONS))
    comments = ra.text(comments, "Comments", True)
    conn.execute("UPDATE ethics_reviewer_allocations SET status = 'completed', recommendation = "
                 "?, comments = ?, completed_at = ? WHERE allocation_id = ?",
                 (recommendation, comments, ra.now(), allocation_id))
    row = application(conn, alloc["review_id"])
    ra.audit(conn, who, "ethics", alloc["review_id"], "reviewed",
             {"recommendation": recommendation})
    if _completed(conn, alloc["review_id"]) >= required_reviews(row["risk_level"]):
        return ra.notify(conn, ra.holders(conn, "ethics_chair"),
                         f"{row['reference']} is ready for a decision",
                         f"All reviews are in for {row['reference']} – {row['title']}.")
    return []


def _completed(conn, review_id) -> int:
    return conn.execute("SELECT COUNT(*) FROM ethics_reviewer_allocations WHERE review_id = ? "
                        "AND status = 'completed'", (review_id,)).fetchone()[0]


def _approval_expiry(row, expiry) -> str:
    if expiry:
        return ra.iso_date(expiry, "Approval expiry")
    if row.get("end_date"):
        return row["end_date"]
    return (date.today() + timedelta(days=365 * APPROVAL_YEARS)).isoformat()


def decide(conn, who, review_id, decision, comments, conditions=(), expiry=None) -> list:
    """The chair's decision. Approval needs the required number of reviews."""
    row = application(conn, review_id)
    ra.require(who.chairs_ethics, "Only the ethics chair can decide applications")
    ra.require(who.username not in _connected(conn, row),
               "You are connected to this application and cannot decide it")
    if row["status"] not in ("submitted", "under_review"):
        raise ValueError(f"An application that is {row['status']} cannot be decided")
    if decision not in DECISIONS:
        raise ValueError("Decision must be one of " + ", ".join(DECISIONS))
    comments = ra.text(comments, "Decision comments", True)
    conditions = [c.strip() for c in conditions if c and c.strip()]
    if decision == "approve_with_conditions" and not conditions:
        raise ValueError("List the conditions")
    if decision.startswith("approve"):
        need = required_reviews(row["risk_level"])
        if _completed(conn, review_id) < need:
            raise ValueError(f"This application needs {need} completed review(s) first")
    status = {"revise": "revisions_required", "reject": "rejected"}.get(decision, "approved")
    until = _approval_expiry(row, expiry) if status == "approved" else None
    conn.execute("UPDATE ethics_reviews SET decision = ?, decision_date = ?, decided_by = ?, "
                 "reviewer_comments = ?, conditions = ?, approval_expiry_date = COALESCE(?, "
                 "approval_expiry_date), updated_at = ? WHERE review_id = ?",
                 (status, ra.today(), who.username, comments, "\n".join(conditions) or None,
                  until, ra.now(), review_id))
    for text in conditions:
        conn.execute("INSERT INTO ethics_conditions (review_id, condition_text) VALUES (?, ?)",
                     (review_id, text))
    if status == "approved":
        _apply_to_parent(conn, row, until)
        _mark_project(conn, row)
    ra.audit(conn, who, "ethics", review_id, "decided",
             {"decision": decision, "expiry": until, "conditions": conditions})
    return ra.notify(conn, [row["applicant_id"], row["principal_investigator_id"]],
                     f"Ethics decision: {row['reference']}",
                     f"{row['reference']} – {row['title']}: {decision.replace('_', ' ')}.\n"
                     f"{comments}" + ("\nConditions:\n- " + "\n- ".join(conditions)
                                      if conditions else ""))


def _apply_to_parent(conn, row, until) -> None:
    if row.get("kind") == "renewal" and row.get("parent_review_id"):
        conn.execute("UPDATE ethics_reviews SET approval_expiry_date = ?, decision = 'approved', "
                     "updated_at = ? WHERE review_id = ?",
                     (until, ra.now(), row["parent_review_id"]))


def _mark_project(conn, row) -> None:
    if row.get("project_id"):
        conn.execute("UPDATE research_projects SET ethics_approval_status = 'approved', "
                     "ethics_approval_date = ? WHERE project_id = ?",
                     (ra.today(), row["project_id"]))


def meet_condition(conn, who, condition_id, evidence) -> None:
    cond = ra.one(conn, "SELECT * FROM ethics_conditions WHERE condition_id = ?",
                  (condition_id,))
    if not cond:
        raise ValueError("No such condition")
    row = application(conn, cond["review_id"])
    ra.require(_owns(who, row) or who.chairs_ethics, "Only the applicant can do this")
    if cond["met_at"]:
        raise ValueError("That condition is already met")
    conn.execute("UPDATE ethics_conditions SET met_at = ?, met_by = ?, evidence = ? WHERE "
                 "condition_id = ?",
                 (ra.now(), who.username, ra.text(evidence, "Evidence", True), condition_id))
    ra.audit(conn, who, "ethics", cond["review_id"], "condition_met",
             {"condition": cond["condition_text"]})


def _child(conn, who, parent_id, kind, changes) -> int:
    parent = application(conn, parent_id)
    ra.require(_owns(who, parent), "Only the applicant can amend or renew this approval")
    if parent["status"] not in ("approved", "expired") or (
            kind == "amendment" and parent["status"] != "approved"):
        raise ValueError("Only an approved application can be amended or renewed")
    if conn.execute("SELECT 1 FROM ethics_reviews WHERE parent_review_id = ? AND decision IN "
                    f"({', '.join('?' * len(OPEN))})", (parent_id, *OPEN)).fetchone():
        raise ValueError("There is already an amendment or renewal in progress")
    copy = {k: parent.get(k) for k in _EDITABLE}
    copy.update(changes)
    copy["title"] = parent["title"]
    rid = create(conn, who, {**copy, "supervisor_id": parent.get("supervisor_id"),
                             "principal_investigator_id": parent.get("principal_investigator_id")})
    conn.execute("UPDATE ethics_reviews SET kind = ?, parent_review_id = ?, reference = ? WHERE "
                 "review_id = ?",
                 (kind, parent_id, f"{parent['reference']}/{kind[0].upper()}{rid}", rid))
    ra.audit(conn, who, "ethics", parent_id, f"{kind}_started", {"child": rid})
    return rid


def amend(conn, who, parent_id, description) -> int:
    """Start an amendment to an approved study (goes through review again)."""
    return _child(conn, who, parent_id, "amendment",
                  {"notes": ra.text(description, "Description of the change", True)})


def renew(conn, who, parent_id, new_end_date) -> int:
    """Ask for the approval to be extended to ``new_end_date``."""
    end = ra.iso_date(new_end_date, "New end date", True)
    return _child(conn, who, parent_id, "renewal", {"end_date": end})


def withdraw(conn, who, review_id, reason) -> None:
    row = application(conn, review_id)
    ra.require(_owns(who, row) or who.is_office, "Only the applicant can withdraw this")
    if row["status"] not in OPEN:
        raise ValueError("Only an application still in progress can be withdrawn")
    conn.execute("UPDATE ethics_reviews SET decision = 'withdrawn', updated_at = ? WHERE "
                 "review_id = ?", (ra.now(), review_id))
    conn.execute("UPDATE ethics_reviewer_allocations SET status = 'withdrawn' WHERE review_id = ? "
                 "AND status = 'allocated'", (review_id,))
    ra.audit(conn, who, "ethics", review_id, "withdrawn",
             {"reason": ra.text(reason, "Reason", True)})


def close(conn, who, review_id) -> None:
    """The study has finished; its approval is no longer needed."""
    row = application(conn, review_id)
    ra.require(_owns(who, row) or who.is_office, "Only the applicant can close this")
    if row["status"] != "approved":
        raise ValueError("Only an approved study can be closed")
    conn.execute("UPDATE ethics_reviews SET decision = 'closed', updated_at = ? WHERE "
                 "review_id = ?", (ra.now(), review_id))
    ra.audit(conn, who, "ethics", review_id, "closed")


def expire_due(conn, as_of=None) -> list[dict]:
    """Approvals past their expiry become ``expired``. Returns them."""
    ra.ensure(conn)
    day = ra.iso_date(as_of, "Date") or ra.today()
    rows = ra.dicts(conn.execute(
        "SELECT review_id, reference, title, applicant_id, principal_investigator_id FROM "
        "ethics_reviews WHERE decision = 'approved' AND approval_expiry_date IS NOT NULL AND "
        "approval_expiry_date < ?", (day,)))
    for row in rows:
        conn.execute("UPDATE ethics_reviews SET decision = 'expired', updated_at = ? WHERE "
                     "review_id = ?", (ra.now(), row["review_id"]))
        ra.audit(conn, "system", "ethics", row["review_id"], "expired")
    return rows


def expiring(conn, days=60, as_of=None) -> list[dict]:
    ra.ensure(conn)
    day = date.fromisoformat(ra.iso_date(as_of, "Date") or ra.today())
    return ra.dicts(conn.execute(
        "SELECT review_id, reference, title, applicant_id, principal_investigator_id, "
        "approval_expiry_date FROM ethics_reviews WHERE decision = 'approved' AND "
        "approval_expiry_date BETWEEN ? AND ? ORDER BY approval_expiry_date",
        (day.isoformat(), (day + timedelta(days=int(days))).isoformat())))


def listing(conn, who, status=None, search=None) -> list[dict]:
    """Applications ``who`` may see, newest first."""
    ra.ensure(conn)
    where, params = [], []
    if not who.chairs_ethics:
        where.append("(e.applicant_id = ? OR e.principal_investigator_id = ? OR e.supervisor_id "
                     "= ? OR e.created_by = ? OR EXISTS (SELECT 1 FROM "
                     "ethics_reviewer_allocations a WHERE a.review_id = e.review_id AND "
                     "a.reviewer = ?))")
        params += [who.me, who.username, who.username, who.me, who.username]
    if status:
        where.append("COALESCE(NULLIF(LOWER(e.decision), 'pending'), 'submitted') = ?")
        params.append(status)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(COALESCE(e.reference, '')) LIKE ? OR LOWER(COALESCE(e.title, '')) "
                     "LIKE ? OR LOWER(COALESCE(e.department, '')) LIKE ?)")
        params += [like, like, like]
    rows = ra.dicts(conn.execute(
        "SELECT e.* FROM ethics_reviews e" + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY e.submission_date DESC, e.review_id DESC", params))
    for row in rows:
        row["status"] = _status(row)
    return rows


def record(conn, who, review_id) -> dict:
    row = application(conn, review_id)
    ra.require(can_see(conn, who, row), "You cannot see this application")
    row["allocations"] = ra.dicts(conn.execute(
        "SELECT * FROM ethics_reviewer_allocations WHERE review_id = ? ORDER BY allocation_id",
        (review_id,)))
    if not (who.chairs_ethics or _is_reviewer(row, who)):
        for alloc in row["allocations"]:      # applicants do not see who reviewed them
            alloc["reviewer"] = "reviewer"
            alloc["conflict_detail"] = None
    row["conditions"] = ra.dicts(conn.execute(
        "SELECT * FROM ethics_conditions WHERE review_id = ? ORDER BY condition_id",
        (review_id,)))
    row["children"] = ra.dicts(conn.execute(
        "SELECT review_id, reference, kind, decision AS status FROM ethics_reviews WHERE "
        "parent_review_id = ? ORDER BY review_id", (review_id,)))
    row["history"] = ra.history(conn, "ethics", review_id)
    row["route"] = row.get("route") or route_for(row.get("risk_level"), row.get("category"))
    row["reviews_needed"] = required_reviews(row.get("risk_level"))
    return row


def _is_reviewer(row, who) -> bool:
    return any(a["reviewer"] == who.username for a in row["allocations"])


def my_reviews(conn, who) -> list[dict]:
    ra.ensure(conn)
    return ra.dicts(conn.execute(
        "SELECT a.allocation_id, a.status AS review_status, a.allocated_at, e.review_id, "
        "e.reference, e.title, e.risk_level FROM ethics_reviewer_allocations a JOIN "
        "ethics_reviews e ON e.review_id = a.review_id WHERE a.reviewer = ? AND a.status = "
        "'allocated' ORDER BY a.allocated_at", (who.username,)))


def chair_queue(conn) -> dict:
    """What the chair needs to do: allocate, re-allocate, decide."""
    ra.ensure(conn)
    rows = listing(conn, ra.Researcher("system", "admin"))
    out = {"to_allocate": [], "to_decide": []}
    for row in rows:
        if row["status"] not in ("submitted", "under_review"):
            continue
        active = conn.execute("SELECT COUNT(*) FROM ethics_reviewer_allocations WHERE "
                              "review_id = ? AND status IN ('allocated', 'completed')",
                              (row["review_id"],)).fetchone()[0]
        need = required_reviews(row.get("risk_level"))
        if active < need:
            out["to_allocate"].append({**row, "allocated": active, "needed": need})
        elif _completed(conn, row["review_id"]) >= need:
            out["to_decide"].append(row)
    return out


def has_approval(conn, project_id, on=None) -> bool:
    """An approved, unexpired application covers the project."""
    ra.ensure(conn)
    day = ra.iso_date(on, "Date") or ra.today()
    return conn.execute("SELECT 1 FROM ethics_reviews WHERE project_id = ? AND decision = "
                        "'approved' AND (approval_expiry_date IS NULL OR approval_expiry_date "
                        ">= ?)", (project_id, day)).fetchone() is not None
