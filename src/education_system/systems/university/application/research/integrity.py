"""Research integrity: declarations of interest and data management plans.

* **Declarations.** Researchers declare interests (financial, shareholding,
  consultancy, directorships, gifts, personal) — or that they have none —
  at least once every :data:`DECLARATION_MONTHS` months, and whenever
  something changes. The research office or the person's head of department
  reviews each one: no action, managed (with a management plan) or closed.
* **Data management plans.** One per project, versioned. The PI writes and
  submits it; the research office approves it or asks for changes. A new
  version supersedes the approved one only when it is itself approved.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.research import access as ra

KINDS = ("none", "financial", "shareholding", "consultancy", "directorship", "gift",
         "personal", "other")
REVIEW_OUTCOMES = ("no_action", "managed", "closed")
DECLARATION_MONTHS = 12
_PLAN_FIELDS = ("data_types", "storage", "sharing", "repository", "retention_years",
                "personal_data", "dpia_reference")


# ── declarations of interest ────────────────────────────────────────────


def declare(conn, who, kind, *, counterpart=None, description=None, value=None,
            project_id=None) -> int:
    ra.ensure(conn)
    ra.require_staff(who)
    if kind not in KINDS:
        raise ValueError("Kind must be one of " + ", ".join(KINDS))
    if kind != "none":
        counterpart = ra.text(counterpart, "Who the interest is with", True)
        description = ra.text(description, "Description", True)
    if project_id not in (None, "") and not conn.execute(
            "SELECT 1 FROM research_projects WHERE project_id = ?", (project_id,)).fetchone():
        raise ValueError("No such research project")
    did = conn.execute("INSERT INTO research_interest_declarations (username, kind, counterpart, "
                       "description, value, project_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (who.username, kind, counterpart, description,
                        None if value in (None, "") else ra.money(value, "Value"),
                        project_id or None,
                        "no_action" if kind == "none" else "declared")).lastrowid
    ra.audit(conn, who, "declaration", did, "declared", {"kind": kind})
    if kind == "none":
        return int(did)
    reviewers = ra.holders(conn, "head_of_department", ra.department_of(conn, who.username)) \
        or ra.holders(conn, "research_office")
    ra.notify(conn, reviewers, "Declaration of interest to review",
              f"{ra.person_name(conn, who.username)} declared a {kind} interest "
              f"({counterpart}).")
    return int(did)


def can_review(conn, who, row) -> bool:
    if row["username"] == who.username:
        return False
    return who.is_office or who.heads(ra.department_of(conn, row["username"]))


def review(conn, who, declaration_id, outcome, management_plan="") -> None:
    row = ra.one(conn, "SELECT * FROM research_interest_declarations WHERE declaration_id = ?",
                 (declaration_id,))
    if not row:
        raise ValueError("No such declaration")
    ra.require(can_review(conn, who, row), "You cannot review this declaration")
    if outcome not in REVIEW_OUTCOMES:
        raise ValueError("Outcome must be one of " + ", ".join(REVIEW_OUTCOMES))
    if outcome == "managed":
        management_plan = ra.text(management_plan, "Management plan", True)
    conn.execute("UPDATE research_interest_declarations SET status = ?, management_plan = ?, "
                 "reviewed_by = ?, reviewed_at = ? WHERE declaration_id = ?",
                 (outcome, management_plan or None, who.username, ra.now(), declaration_id))
    ra.audit(conn, who, "declaration", declaration_id, "reviewed", {"outcome": outcome})
    ra.notify(conn, [row["username"]], "Your declaration of interest was reviewed",
              f"Outcome: {outcome.replace('_', ' ')}."
              + (f"\nManagement plan: {management_plan}" if management_plan else ""))


def declarations(conn, who, mine=False) -> list[dict]:
    """Own declarations; reviewers also see the ones they may review."""
    ra.ensure(conn)
    rows = ra.dicts(conn.execute("SELECT * FROM research_interest_declarations ORDER BY "
                                 "declared_at DESC, declaration_id DESC"))
    return [r for r in rows if r["username"] == who.username or
            (not mine and can_review(conn, who, r))]


def to_review(conn, who) -> list[dict]:
    return [r for r in declarations(conn, who) if r["status"] == "declared" and
            r["username"] != who.username]


def overdue(conn, as_of=None) -> list[dict]:
    """Staff who are on a project, grant or IP record and have not declared
    (even a nil return) in the last :data:`DECLARATION_MONTHS` months."""
    ra.ensure(conn)
    day = date.fromisoformat(ra.iso_date(as_of, "Date") or ra.today())
    since = (day - timedelta(days=round(DECLARATION_MONTHS * 30.44))).isoformat()
    researchers = {r[0] for r in conn.execute(
        "SELECT principal_investigator_id FROM research_projects WHERE COALESCE(status, "
        "'active') NOT IN ('closed', 'completed') UNION SELECT staff_id FROM "
        "research_team_members WHERE is_active = 1 UNION SELECT principal_investigator_id FROM "
        "grant_applications WHERE COALESCE(status, 'draft') NOT IN ('closed', 'rejected', "
        "'withdrawn') UNION SELECT user_id FROM ip_inventors") if r[0]}
    latest = dict(conn.execute("SELECT username, MAX(declared_at) FROM "
                               "research_interest_declarations GROUP BY username").fetchall())
    return [{"username": u, "name": ra.person_name(conn, u), "last_declared": latest.get(u)}
            for u in sorted(researchers)
            if ra.is_staff_username(conn, u) and (latest.get(u) or "") < since]


# ── data management plans ───────────────────────────────────────────────


def _project(conn, project_id) -> dict:
    row = ra.one(conn, "SELECT * FROM research_projects WHERE project_id = ?", (project_id,))
    if not row:
        raise ValueError("No such research project")
    return row


def plan(conn, plan_id) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM research_data_plans WHERE plan_id = ?", (plan_id,))
    if not row:
        raise ValueError("No such data management plan")
    return row


def plans(conn, project_id) -> list[dict]:
    ra.ensure(conn)
    return ra.dicts(conn.execute("SELECT * FROM research_data_plans WHERE project_id = ? ORDER "
                                 "BY version DESC", (project_id,)))


def _clean_plan(data) -> dict:
    out = {}
    for key in _PLAN_FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key == "retention_years":
            value = None if value in (None, "") else int(value)
            if value is not None and not 0 < value <= 100:
                raise ValueError("Retention must be 1 to 100 years")
        elif key == "personal_data":
            value = int(bool(value))
        else:
            value = ra.text(value, key)
        out[key] = value
    return out


def _pi_or_office(who, project) -> bool:
    return who.is_office or who.username == project.get("principal_investigator_id")


def draft_plan(conn, who, project_id, data) -> int:
    """Start a new version (copying the latest) or edit the open draft."""
    ra.ensure(conn)
    project = _project(conn, project_id)
    ra.require(_pi_or_office(who, project), "Only the principal investigator writes the plan")
    fields = _clean_plan(data)
    existing = plans(conn, project_id)
    open_plan = next((p for p in existing if p["status"] in ("draft", "changes_requested")),
                     None)
    if open_plan:
        if fields:
            conn.execute(f"UPDATE research_data_plans SET "
                         f"{', '.join(f'{k} = ?' for k in fields)}, status = 'draft' WHERE "
                         "plan_id = ?", (*fields.values(), open_plan["plan_id"]))
        ra.audit(conn, who, "data_plan", open_plan["plan_id"], "edited")
        return int(open_plan["plan_id"])
    if any(p["status"] == "submitted" for p in existing):
        raise ValueError("A version is already waiting for review")
    base = {k: existing[0].get(k) for k in _PLAN_FIELDS} if existing else {}
    base.update(fields)
    version = (existing[0]["version"] + 1) if existing else 1
    cols = ["project_id", "version", "status", "author", *base]
    pid = conn.execute(
        f"INSERT INTO research_data_plans ({', '.join(cols)}) VALUES "
        f"({', '.join('?' * len(cols))})",
        [project_id, version, "draft", who.username, *base.values()]).lastrowid
    ra.audit(conn, who, "data_plan", pid, "drafted", {"version": version})
    return int(pid)


def submit_plan(conn, who, plan_id) -> list:
    row = plan(conn, plan_id)
    project = _project(conn, row["project_id"])
    ra.require(_pi_or_office(who, project), "Only the principal investigator submits the plan")
    if row["status"] not in ("draft", "changes_requested"):
        raise ValueError("Only a draft can be submitted")
    missing = [k.replace("_", " ") for k in ("data_types", "storage", "sharing",
                                             "retention_years") if not row.get(k)]
    if row.get("personal_data") and not row.get("dpia_reference"):
        missing.append("DPIA reference (the plan involves personal data)")
    if missing:
        raise ValueError("Fill in before submitting: " + ", ".join(missing))
    conn.execute("UPDATE research_data_plans SET status = 'submitted', submitted_at = ? WHERE "
                 "plan_id = ?", (ra.now(), plan_id))
    ra.audit(conn, who, "data_plan", plan_id, "submitted")
    return ra.notify(conn, ra.holders(conn, "research_office"),
                     "Data management plan to review",
                     f"Version {row['version']} for project {project['project_title']}.")


def review_plan(conn, who, plan_id, approve, note="") -> list:
    row = plan(conn, plan_id)
    ra.require(who.is_office, "Only the research office reviews data management plans")
    if row["status"] != "submitted":
        raise ValueError("This plan is not waiting for review")
    if not approve:
        note = ra.text(note, "What needs changing", True)
    status = "approved" if approve else "changes_requested"
    if approve:
        conn.execute("UPDATE research_data_plans SET status = 'superseded' WHERE project_id = ? "
                     "AND status = 'approved'", (row["project_id"],))
    conn.execute("UPDATE research_data_plans SET status = ?, reviewed_by = ?, reviewed_at = ?, "
                 "review_note = ? WHERE plan_id = ?",
                 (status, who.username, ra.now(), note or None, plan_id))
    ra.audit(conn, who, "data_plan", plan_id, status)
    project = _project(conn, row["project_id"])
    return ra.notify(conn, [project["principal_investigator_id"]],
                     f"Data management plan {status.replace('_', ' ')}",
                     f"Version {row['version']} for {project['project_title']}: "
                     f"{status.replace('_', ' ')}." + (f"\n{note}" if note else ""))


def plans_to_review(conn, who) -> list[dict]:
    if not who.is_office:
        return []
    return ra.dicts(conn.execute(
        "SELECT d.*, p.project_title, p.principal_investigator_id FROM research_data_plans d "
        "JOIN research_projects p ON p.project_id = d.project_id WHERE d.status = 'submitted' "
        "ORDER BY d.submitted_at"))


def projects_missing_plan(conn) -> list[dict]:
    """Active projects with a live grant that requires a plan, and none approved."""
    ra.ensure(conn)
    return ra.dicts(conn.execute(
        "SELECT DISTINCT p.project_id, p.reference, p.project_title, "
        "p.principal_investigator_id FROM research_projects p JOIN grant_applications g ON "
        "g.project_id = p.project_id WHERE COALESCE(g.dmp_required, 1) = 1 AND "
        "COALESCE(g.status, 'draft') IN ('submitted', 'awarded', 'active') AND NOT EXISTS "
        "(SELECT 1 FROM research_data_plans d WHERE d.project_id = p.project_id AND d.status = "
        "'approved')"))
