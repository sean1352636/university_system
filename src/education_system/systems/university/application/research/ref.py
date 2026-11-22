"""REF preparation: staff in each unit of assessment (UoA), internal
review of outputs, the output selection, impact case studies, environment
statements and the per-UoA picture.

* Staff are attributed to one UoA with an FTE (``ref_staff_uoa``). A UoA
  needs :data:`OUTPUTS_PER_FTE` outputs per FTE.
* Outputs are scored 0–4* by internal reviewers (REF leads or the research
  office, never an author). Two scores more than one star apart need
  moderation; the REF lead then sets the agreed rating.
* An output can be selected only if it is in the REF period, open-access
  compliant, has an agreed rating and an author attributed to its UoA.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import csv

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import outputs as ro

REF_PERIOD = ("2021-01-01", "2027-12-31")
OUTPUTS_PER_FTE = 2.5
UOAS = tuple(f"UoA {n}" for n in range(1, 35))
CASE_STATUSES = ("draft", "in_review", "final", "withdrawn")


def canonical_uoa(value) -> str:
    """``"UOA11"`` / ``"uoa 11"`` / ``"UoA 11"`` → ``"UoA 11"``."""
    value = (value or "").strip()
    if value.upper().startswith("UOA") and value[3:].strip().isdigit():
        value = f"UoA {int(value[3:].strip())}"
    if value not in UOAS:
        raise ValueError("Unit of assessment must be UoA 1 to UoA 34")
    return value


_uoa = canonical_uoa


# ── staff ───────────────────────────────────────────────────────────────


def staff(conn, uoa=None) -> list[dict]:
    ra.ensure(conn)
    sql = "SELECT r.*, s.name FROM ref_staff_uoa r LEFT JOIN staff s ON s.username = r.username"
    rows = ra.dicts(conn.execute(sql + (" WHERE r.uoa = ?" if uoa else "") + " ORDER BY r.uoa, "
                                 "s.name", (uoa,) if uoa else ()))
    return rows


def attribute(conn, who, username, uoa, fte=1.0) -> None:
    uoa = _uoa(uoa)
    ra.require(who.leads_ref(uoa), "Only the REF lead can attribute staff")
    username = ra.staff_ref(conn, username, "Member of staff")
    fte = float(fte)
    if not 0 < fte <= 1:
        raise ValueError("FTE must be more than 0 and at most 1")
    conn.execute("INSERT INTO ref_staff_uoa (username, uoa, fte, updated_by) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT (username) DO UPDATE SET uoa = excluded.uoa, fte = excluded.fte, "
                 "updated_by = excluded.updated_by, updated_at = datetime('now')",
                 (username, uoa, fte, who.username))
    ra.audit(conn, who, "ref_staff", username, "attributed", {"uoa": uoa, "fte": fte})


def unattribute(conn, who, username) -> None:
    row = conn.execute("SELECT uoa FROM ref_staff_uoa WHERE username = ?", (username,)).fetchone()
    if not row:
        raise ValueError(f"{username} is not attributed to a UoA")
    ra.require(who.leads_ref(row[0]), "Only the REF lead can change attribution")
    conn.execute("DELETE FROM ref_staff_uoa WHERE username = ?", (username,))
    ra.audit(conn, who, "ref_staff", username, "unattributed", {"uoa": row[0]})


# ── internal review ─────────────────────────────────────────────────────


def reviews(conn, publication_id) -> list[dict]:
    return ra.dicts(conn.execute("SELECT * FROM research_output_reviews WHERE publication_id = ? "
                                 "ORDER BY review_id", (publication_id,)))


def add_review(conn, who, publication_id, score, comment="") -> None:
    row = ro.output(conn, publication_id)
    ra.require(who.leads_ref(row.get("uoa")), "Only REF reviewers can score outputs")
    if who.username in {a["username"] for a in ro.authors(conn, publication_id)}:
        raise PermissionError("You cannot review your own output")
    score = int(score)
    if not 0 <= score <= 4:
        raise ValueError("Score must be 0 to 4")
    conn.execute("INSERT INTO research_output_reviews (publication_id, reviewer, score, comment) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT (publication_id, reviewer) DO UPDATE SET "
                 "score = excluded.score, comment = excluded.comment, reviewed_at = "
                 "datetime('now')", (publication_id, who.username, score, comment or None))
    ra.audit(conn, who, "output", publication_id, "reviewed", {"score": score})


def review_summary(conn, publication_id) -> dict:
    scores = [r["score"] for r in reviews(conn, publication_id)]
    if not scores:
        return {"count": 0, "mean": None, "needs_moderation": False}
    return {"count": len(scores), "mean": round(sum(scores) / len(scores), 2),
            "needs_moderation": max(scores) - min(scores) > 1}


def set_rating(conn, who, publication_id, stars) -> None:
    row = ro.output(conn, publication_id)
    ra.require(who.leads_ref(row.get("uoa")), "Only the REF lead can set the agreed rating")
    stars = int(str(stars).rstrip("*"))
    if not 0 <= stars <= 4:
        raise ValueError("Rating must be 0* to 4*")
    if not reviews(conn, publication_id):
        raise ValueError("The output needs at least one internal review first")
    conn.execute("UPDATE research_publications SET quality_rating = ? WHERE publication_id = ?",
                 (f"{stars}*", publication_id))
    ra.audit(conn, who, "output", publication_id, "rated", {"rating": f"{stars}*"})


# ── selection ───────────────────────────────────────────────────────────


def eligibility(conn, row) -> list[str]:
    """Why an output cannot be selected (empty when it can)."""
    problems = []
    if not row.get("uoa"):
        problems.append("no unit of assessment")
    when = row.get("publication_date") or row.get("acceptance_date")
    if not when or not REF_PERIOD[0] <= when <= REF_PERIOD[1]:
        problems.append(f"not published in the REF period {REF_PERIOD[0]} – {REF_PERIOD[1]}")
    if not ro.oa_ok(row):
        problems.append(f"open access: {ro.oa_status(row)}")
    if not row.get("quality_rating"):
        problems.append("no agreed rating")
    attributed = {r[0] for r in conn.execute(
        "SELECT a.username FROM research_output_authors a JOIN ref_staff_uoa s ON s.username = "
        "a.username WHERE a.publication_id = ? AND s.uoa = ?",
        (row["publication_id"], row.get("uoa") or ""))}
    if not attributed:
        problems.append("no author attributed to this UoA")
    return problems


def select(conn, who, publication_id, selected=True) -> None:
    row = ro.output(conn, publication_id)
    ra.require(who.leads_ref(row.get("uoa")), "Only the REF lead can change the selection")
    if selected:
        problems = eligibility(conn, row)
        if problems:
            raise ValueError("Cannot select: " + "; ".join(problems))
    conn.execute("UPDATE research_publications SET ref_submitted = ? WHERE publication_id = ?",
                 (int(bool(selected)), publication_id))
    ra.audit(conn, who, "output", publication_id, "selected" if selected else "deselected")


def candidates(conn, uoa) -> list[dict]:
    uoa = _uoa(uoa)
    out = []
    for row in ro.listing(conn, uoa=uoa):
        row["problems"] = eligibility(conn, row)
        row["review"] = review_summary(conn, row["publication_id"])
        out.append(row)
    return out


# ── impact cases and environment statements ─────────────────────────────

_CASE_FIELDS = ("title", "summary", "status", "reach_significance", "beneficiaries",
                "evidence_links", "quality_rating", "lead_username")


def impact_cases(conn, uoa=None) -> list[dict]:
    ra.ensure(conn)
    return ra.dicts(conn.execute("SELECT * FROM ref_impact_cases" + (" WHERE uoa = ?" if uoa
                                                                     else "")
                                 + " ORDER BY uoa, id", (uoa,) if uoa else ()))


def _case_fields(conn, data) -> dict:
    out = {}
    for key in _CASE_FIELDS:
        if key not in data:
            continue
        value = ra.text(data[key], key)
        if key == "status" and value not in CASE_STATUSES:
            raise ValueError("Status must be one of " + ", ".join(CASE_STATUSES))
        if key == "lead_username" and value:
            ra.staff_ref(conn, value, "Lead")
        out[key] = value
    return out


def save_impact_case(conn, who, data, case_id=None) -> int:
    ra.ensure(conn)
    if case_id:
        case = ra.one(conn, "SELECT * FROM ref_impact_cases WHERE id = ?", (case_id,))
        if not case:
            raise ValueError("No such impact case")
        ra.require(who.leads_ref(case["uoa"]) or who.username == case.get("lead_username"),
                   "Only the REF lead or the case lead can edit this case")
        fields = _case_fields(conn, data)
        if fields:
            conn.execute(f"UPDATE ref_impact_cases SET {', '.join(f'{k} = ?' for k in fields)}, "
                         "updated_at = datetime('now') WHERE id = ?", (*fields.values(), case_id))
        ra.audit(conn, who, "impact_case", case_id, "edited", {"fields": sorted(fields)})
        return int(case_id)
    uoa = _uoa(data.get("uoa"))
    ra.require(who.leads_ref(uoa), "Only the REF lead can start an impact case")
    fields = _case_fields(conn, {"status": "draft", **data})
    if not fields.get("title"):
        raise ValueError("Title is required")
    cols = ["uoa", *fields]
    cid = conn.execute(f"INSERT INTO ref_impact_cases ({', '.join(cols)}) VALUES "
                       f"({', '.join('?' * len(cols))})", [uoa, *fields.values()]).lastrowid
    ra.audit(conn, who, "impact_case", cid, "created")
    return int(cid)


def environment_statements(conn, uoa=None) -> list[dict]:
    ra.ensure(conn)
    return ra.dicts(conn.execute("SELECT * FROM ref_environment_statements" +
                                 (" WHERE uoa = ?" if uoa else "") + " ORDER BY uoa, version DESC",
                                 (uoa,) if uoa else ()))


def add_environment_statement(conn, who, uoa, narrative) -> int:
    uoa = _uoa(uoa)
    ra.require(who.leads_ref(uoa), "Only the REF lead can write the environment statement")
    version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM ref_environment_statements "
                           "WHERE uoa = ?", (uoa,)).fetchone()[0]
    sid = conn.execute("INSERT INTO ref_environment_statements (uoa, narrative_text, version, "
                       "drafted_by_username) VALUES (?, ?, ?, ?)",
                       (uoa, ra.text(narrative, "Statement", True), version,
                        who.username)).lastrowid
    ra.audit(conn, who, "environment", uoa, "new_version", {"version": version})
    return int(sid)


# ── the UoA picture ─────────────────────────────────────────────────────


def uoa_summary(conn, uoa) -> dict:
    uoa = _uoa(uoa)
    people = staff(conn, uoa)
    fte = round(sum(float(p["fte"]) for p in people), 2)
    outputs = candidates(conn, uoa)
    selected = [o for o in outputs if o.get("ref_submitted")]
    ratings = [int(o["quality_rating"].rstrip("*")) for o in selected
               if (o.get("quality_rating") or "").rstrip("*").isdigit()]
    required = round(fte * OUTPUTS_PER_FTE)
    cases = [c for c in impact_cases(conn, uoa) if c["status"] != "withdrawn"]
    env = environment_statements(conn, uoa)
    gaps = []
    if len(selected) < required:
        gaps.append(f"{required - len(selected)} more output(s) needed")
    if not cases:
        gaps.append("no impact case studies")
    if not env:
        gaps.append("no environment statement")
    moderation = [o["publication_id"] for o in outputs if o["review"]["needs_moderation"]]
    if moderation:
        gaps.append(f"{len(moderation)} output(s) need moderation")
    return {"uoa": uoa, "staff": len(people), "fte": fte, "required_outputs": required,
            "outputs": len(outputs), "selected": len(selected),
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "four_star": ratings.count(4), "three_star": ratings.count(3),
            "impact_cases": len(cases), "environment_version": env[0]["version"] if env else None,
            "gaps": gaps}


def active_uoas(conn) -> list[str]:
    ra.ensure(conn)
    found = {r[0] for r in conn.execute("SELECT uoa FROM ref_staff_uoa UNION SELECT uoa FROM "
                                        "research_publications WHERE uoa IS NOT NULL UNION "
                                        "SELECT uoa FROM ref_impact_cases")}
    return [u for u in UOAS if u in found]


def export(conn, uoa, path) -> int:
    """CSV of the UoA's selected outputs, impact cases and latest
    environment statement. Returns the number of rows written."""
    uoa = _uoa(uoa)
    rows = []
    for o in candidates(conn, uoa):
        if o.get("ref_submitted"):
            rows.append(["output", o["publication_id"], o["title"], o.get("authors"),
                         o.get("doi"), o.get("quality_rating"), o["oa_status"]])
    for c in impact_cases(conn, uoa):
        if c["status"] != "withdrawn":
            rows.append(["impact_case", c["id"], c["title"], c.get("lead_username"), "",
                         c.get("quality_rating"), c["status"]])
    env = environment_statements(conn, uoa)
    if env:
        rows.append(["environment", env[0]["id"], f"Version {env[0]['version']}", "", "", "",
                     env[0]["narrative_text"][:200]])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["kind", "id", "title", "people", "doi", "rating", "status"])
        writer.writerows(rows)
    return len(rows)
