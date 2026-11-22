"""The research project register: projects, their teams, and the one view
that links a project to its ethics applications, grants, outputs, IP,
data management plans and declared interests. Also researcher profiles.

Projects live on ``research_projects``; teams on ``research_team_members``
(``staff_id`` holds the username). The principal investigator and the
research office manage a project; team members can see it.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.research import access as ra

STATUSES = ("proposed", "active", "suspended", "completed", "closed")
TYPES = ("Funded", "Unfunded", "Consultancy", "Collaborative", "Student-led", "Internal")
TEAM_ROLES = ("Co-investigator", "Researcher", "Research assistant", "Technician",
              "Student", "Collaborator")
_FIELDS = ("project_title", "project_description", "department", "project_type", "start_date",
           "end_date", "funding_source", "needs_ethics")


def project(conn, project_id) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM research_projects WHERE project_id = ?", (project_id,))
    if not row:
        raise ValueError("No such research project")
    return row


def _team(conn, project_id) -> set:
    return {r[0] for r in conn.execute("SELECT staff_id FROM research_team_members WHERE "
                                       "project_id = ? AND is_active = 1", (project_id,))}


def manages(who, row) -> bool:
    return who.is_office or who.username == row.get("principal_investigator_id")


def can_see(conn, who, row) -> bool:
    return manages(who, row) or who.heads(row.get("department")) or \
        who.username in _team(conn, row["project_id"])


def _clean(data, creating) -> dict:
    out = {}
    for key in _FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key in ("start_date", "end_date"):
            value = ra.iso_date(value, key.replace("_", " ").capitalize(),
                                creating and key == "start_date")
        elif key == "needs_ethics":
            value = int(bool(value))
        elif key == "project_type" and value not in TYPES:
            raise ValueError("Project type must be one of " + ", ".join(TYPES))
        else:
            value = ra.text(value, key.replace("_", " "),
                            creating and key in ("project_title", "department"))
        out[key] = value
    if out.get("start_date") and out.get("end_date") and out["end_date"] < out["start_date"]:
        raise ValueError("The project must end after it starts")
    return out


def _reference(conn) -> str:
    year = date.today().year
    n = conn.execute("SELECT COUNT(*) FROM research_projects WHERE reference LIKE ?",
                     (f"RP-{year}-%",)).fetchone()[0]
    while True:
        n += 1
        ref = f"RP-{year}-{n:03d}"
        if not conn.execute("SELECT 1 FROM research_projects WHERE reference = ?",
                            (ref,)).fetchone():
            return ref


def create(conn, who, data) -> int:
    ra.ensure(conn)
    ra.require_staff(who)
    fields = _clean({"project_type": "Unfunded", "start_date": ra.today(), **data}, True)
    pi = ra.staff_ref(conn, data.get("principal_investigator_id") or who.username,
                      "Principal investigator")
    ra.require(pi == who.username or who.is_office,
               "Only the research office can register a project for someone else")
    fields.setdefault("department", ra.department_of(conn, pi))
    if not fields.get("department"):
        raise ValueError("Department is required")
    cols = ["reference", "principal_investigator_id", "status", "created_by", *fields]
    pid = conn.execute(
        f"INSERT INTO research_projects ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [_reference(conn), pi, "active", who.username, *fields.values()]).lastrowid
    ra.audit(conn, who, "project", pid, "created")
    return int(pid)


def update(conn, who, project_id, data) -> None:
    row = project(conn, project_id)
    ra.require(manages(who, row), "Only the principal investigator can edit this project")
    fields = _clean(data, False)
    if not fields:
        return
    conn.execute(f"UPDATE research_projects SET {', '.join(f'{k} = ?' for k in fields)} WHERE "
                 "project_id = ?", (*fields.values(), project_id))
    ra.audit(conn, who, "project", project_id, "edited", {"fields": sorted(fields)})


def set_status(conn, who, project_id, status, reason="") -> None:
    row = project(conn, project_id)
    ra.require(manages(who, row), "Only the principal investigator can change the status")
    if status not in STATUSES:
        raise ValueError("Status must be one of " + ", ".join(STATUSES))
    if status == "active" and row.get("needs_ethics"):
        from education_system.systems.university.application.research import (
            ethics as research_ethics,
        )
        if not research_ethics.has_approval(conn, project_id):
            raise ValueError("This project needs an approved ethics application before it "
                             "can be active")
    conn.execute("UPDATE research_projects SET status = ?, closed_at = ? WHERE project_id = ?",
                 (status, ra.now() if status == "closed" else None, project_id))
    ra.audit(conn, who, "project", project_id, "status", {"status": status, "reason": reason})


def transfer_pi(conn, who, project_id, new_pi, reason) -> None:
    row = project(conn, project_id)
    ra.require(who.is_office, "Only the research office can change the principal investigator")
    new_pi = ra.staff_ref(conn, new_pi, "New principal investigator")
    conn.execute("UPDATE research_projects SET principal_investigator_id = ? WHERE "
                 "project_id = ?", (new_pi, project_id))
    ra.audit(conn, who, "project", project_id, "pi_changed",
             {"from": row["principal_investigator_id"], "to": new_pi,
              "reason": ra.text(reason, "Reason", True)})


def add_member(conn, who, project_id, username, role, contribution=None) -> None:
    row = project(conn, project_id)
    ra.require(manages(who, row), "Only the principal investigator can change the team")
    username = ra.staff_ref(conn, username, "Team member")
    if role not in TEAM_ROLES:
        raise ValueError("Role must be one of " + ", ".join(TEAM_ROLES))
    if username == row["principal_investigator_id"]:
        raise ValueError("The principal investigator is already on the project")
    if username in _team(conn, project_id):
        raise ValueError(f"{username} is already on the team")
    pct = None if contribution in (None, "") else float(contribution)
    if pct is not None and not 0 <= pct <= 100:
        raise ValueError("Contribution must be 0 to 100%")
    conn.execute("INSERT INTO research_team_members (project_id, staff_id, role, join_date, "
                 "contribution_percentage, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                 (project_id, username, role, ra.today(), pct))
    ra.audit(conn, who, "project", project_id, "member_added", {"who": username, "role": role})


def remove_member(conn, who, project_id, username) -> None:
    row = project(conn, project_id)
    ra.require(manages(who, row), "Only the principal investigator can change the team")
    if not conn.execute("UPDATE research_team_members SET is_active = 0, leave_date = ? WHERE "
                        "project_id = ? AND staff_id = ? AND is_active = 1",
                        (ra.today(), project_id, username)).rowcount:
        raise ValueError(f"{username} is not on the team")
    ra.audit(conn, who, "project", project_id, "member_removed", {"who": username})


def listing(conn, who, status=None, search=None) -> list[dict]:
    ra.ensure(conn)
    where, params = [], []
    if not who.is_office:
        heads = [s for r, s in who.roles if r == "head_of_department" and s]
        clause = ("(p.principal_investigator_id = ? OR EXISTS (SELECT 1 FROM "
                  "research_team_members t WHERE t.project_id = p.project_id AND t.staff_id = ? "
                  "AND t.is_active = 1)")
        params += [who.username, who.username]
        if heads:
            clause += f" OR p.department IN ({', '.join('?' * len(heads))})"
            params += heads
        where.append(clause + ")")
    if status:
        where.append("p.status = ?")
        params.append(status)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(p.project_title) LIKE ? OR LOWER(COALESCE(p.reference, '')) LIKE ? "
                     "OR LOWER(COALESCE(p.department, '')) LIKE ?)")
        params += [like, like, like]
    return ra.dicts(conn.execute(
        "SELECT p.* FROM research_projects p" + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY p.project_id DESC", params))


def choices(conn, who) -> list[tuple[int, str]]:
    """``[(project_id, "RP-… title")]`` for pickers."""
    return [(p["project_id"], f"{p.get('reference') or p['project_id']} {p['project_title']}")
            for p in listing(conn, who) if p.get("status") not in ("closed",)]


def record(conn, who, project_id) -> dict:
    row = project(conn, project_id)
    ra.require(can_see(conn, who, row), "You cannot see this project")
    row["team"] = ra.dicts(conn.execute(
        "SELECT staff_id AS username, role, join_date, leave_date, contribution_percentage, "
        "is_active FROM research_team_members WHERE project_id = ? ORDER BY is_active DESC, "
        "member_id", (project_id,)))
    linked = {
        "ethics": "SELECT review_id, reference, title, kind, decision AS status, "
                  "approval_expiry_date FROM ethics_reviews WHERE project_id = ?",
        "grants": "SELECT application_id, grant_name, funding_agency, status, requested_amount, "
                  "awarded_amount FROM grant_applications WHERE project_id = ?",
        "outputs": "SELECT publication_id, title, publication_type, publication_date, doi "
                   "FROM research_publications WHERE project_id = ?",
        "ip": "SELECT disclosure_id, reference, title, status FROM ip_disclosures WHERE "
              "project_id = ?",
        "data_plans": "SELECT plan_id, version, status, reviewed_at FROM research_data_plans "
                      "WHERE project_id = ? ORDER BY version",
        "interests": "SELECT declaration_id, username, kind, counterpart, status FROM "
                     "research_interest_declarations WHERE project_id = ?",
    }
    for key, sql in linked.items():
        row[key] = ra.dicts(conn.execute(sql, (project_id,)))
    row["history"] = ra.history(conn, "project", project_id)
    return row


def link(conn, who, kind, record_id, project_id) -> None:
    """Attach an existing grant / output / IP disclosure / ethics application."""
    tables = {"grant": ("grant_applications", "application_id"),
              "output": ("research_publications", "publication_id"),
              "ip": ("ip_disclosures", "disclosure_id"),
              "ethics": ("ethics_reviews", "review_id")}
    if kind not in tables:
        raise ValueError("Can link a grant, output, ip or ethics record")
    row = project(conn, project_id)
    ra.require(manages(who, row), "Only the principal investigator can link records")
    table, pk = tables[kind]
    # db-audit: ignore[DBW001] - table/pk come from the literal map above
    if not conn.execute(f"UPDATE {table} SET project_id = ? WHERE {pk} = ?",
                        (project_id, record_id)).rowcount:
        raise ValueError(f"No such {kind} record")
    ra.audit(conn, who, "project", project_id, "linked", {"kind": kind, "id": record_id})


# ── researcher profiles ─────────────────────────────────────────────────

PROFILE_FIELDS = ("research_interests", "orcid_id", "google_scholar_id", "scopus_id",
                  "researchgate_url")


def _orcid_ok(value) -> bool:
    digits = value.replace("-", "")
    if len(digits) != 16 or not digits[:15].isdigit():
        return False
    total = 0
    for ch in digits[:15]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return digits[15] == ("X" if check == 10 else str(check))


def profile(conn, username) -> dict:
    ra.ensure(conn)
    row = ra.one(conn, "SELECT * FROM research_profiles WHERE user_id = ?", (username,)) or {
        "user_id": username}
    row["name"] = ra.person_name(conn, username)
    row["department"] = ra.department_of(conn, username)
    row["outputs"] = conn.execute(
        "SELECT COUNT(DISTINCT publication_id) FROM research_output_authors WHERE username = ?",
        (username,)).fetchone()[0]
    row["projects"] = conn.execute(
        "SELECT COUNT(*) FROM research_projects WHERE principal_investigator_id = ? OR "
        "project_id IN (SELECT project_id FROM research_team_members WHERE staff_id = ? AND "
        "is_active = 1)", (username, username)).fetchone()[0]
    uoa = conn.execute("SELECT uoa, fte FROM ref_staff_uoa WHERE username = ?",
                       (username,)).fetchone()
    row["uoa"], row["ref_fte"] = (uoa[0], uoa[1]) if uoa else (None, None)
    return row


def save_profile(conn, who, username, data) -> None:
    ra.ensure(conn)
    ra.require(who.username == username or who.is_office,
               "You can only edit your own research profile")
    ra.staff_ref(conn, username, "Researcher")
    fields = {k: ra.text(data.get(k), k) for k in PROFILE_FIELDS if k in data}
    if fields.get("orcid_id") and not _orcid_ok(fields["orcid_id"]):
        raise ValueError("That is not a valid ORCID iD (0000-0000-0000-0000)")
    conn.execute("INSERT OR IGNORE INTO research_profiles (user_id) VALUES (?)", (username,))
    if fields:
        conn.execute(f"UPDATE research_profiles SET {', '.join(f'{k} = ?' for k in fields)}, "
                     "last_updated = ? WHERE user_id = ?", (*fields.values(), ra.now(), username))
    count = conn.execute("SELECT COUNT(DISTINCT publication_id) FROM research_output_authors "
                         "WHERE username = ?", (username,)).fetchone()[0]
    conn.execute("UPDATE research_profiles SET total_publications = ? WHERE user_id = ?",
                 (count, username))
    ra.audit(conn, who, "profile", username, "edited", {"fields": sorted(fields)})


def directory(conn, search=None) -> list[dict]:
    """Every active member of staff with their research profile summary."""
    ra.ensure(conn)
    rows = ra.staff_list(conn)
    profiles = {r["user_id"]: r for r in ra.dicts(conn.execute(
        "SELECT user_id, research_interests, orcid_id FROM research_profiles"))}
    uoas = dict(conn.execute("SELECT username, uoa FROM ref_staff_uoa").fetchall())
    out = []
    needle = (search or "").lower()
    for r in rows:
        p = profiles.get(r["username"], {})
        item = {**r, "research_interests": p.get("research_interests"),
                "orcid_id": p.get("orcid_id"), "uoa": uoas.get(r["username"])}
        hay = " ".join(str(v or "") for v in item.values()).lower()
        if not needle or needle in hay:
            out.append(item)
    return out
