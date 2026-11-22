"""Fee-status assessment: whether a student pays Home, Islands or
International tuition.

A short questionnaire is recorded first (nationality, where the student
lived over the three years before the course starts, immigration status,
the evidence seen), then an assessor with the ``finance.fee_status``
capability decides a category with a reason. Every step is audited; a new
assessment for the same year supersedes the earlier one, so the history is
kept. A decision writes the charging basis to ``students.fee_status``.

The categories follow the English fee regulations in outline (the Higher
Education (Fee Limits and Student Support) (England) rules and UKCISA's
guidance); the assessor still makes the decision on the evidence - the
questionnaire only suggests a category.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json

from education_system.systems.university.domains.finance.domain.tuition import access

#: category -> (label, charging basis)
CATEGORIES = {
    "home": ("Home - UK national, ordinarily resident in the UK", "home"),
    "home_settled": ("Home - settled status in the UK (ILR)", "home"),
    "home_eu_settled": ("Home - EU/EEA/Swiss with EUSS settled status", "home"),
    "home_eu_pre_settled": ("Home - EU/EEA/Swiss with EUSS pre-settled status "
                            "(3 years' residence)", "home"),
    "home_irish": ("Home - Irish national (Common Travel Area)", "home"),
    "home_protection": ("Home - refugee / humanitarian protection or other protected "
                        "category", "home"),
    "islands": ("Islands - Channel Islands or Isle of Man", "islands"),
    "international": ("International - overseas", "international"),
    "international_eu": ("International - EU/EEA/Swiss without EUSS status", "international"),
}
BASES = ("home", "islands", "international")
IMMIGRATION_STATUSES = (
    "british_citizen", "irish_citizen", "indefinite_leave", "euss_settled", "euss_pre_settled",
    "refugee", "humanitarian_protection", "student_visa", "other_visa", "none_required",
)
UK = {"uk", "united kingdom", "england", "scotland", "wales", "northern ireland", "gb",
      "great britain", "british"}
ISLANDS = {"jersey", "guernsey", "isle of man", "channel islands", "alderney", "sark"}
EU_EEA_CH = {
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic", "czechia",
    "denmark", "estonia", "finland", "france", "germany", "greece", "hungary", "italy",
    "latvia", "lithuania", "luxembourg", "malta", "netherlands", "poland", "portugal",
    "romania", "slovakia", "slovenia", "spain", "sweden", "iceland", "liechtenstein", "norway",
    "switzerland",
}


def _clean_residence(residence) -> list[dict]:
    """Residence periods: ``[{"from", "to", "country", "purpose"}]``."""
    out = []
    for period in residence or []:
        country = access.text(period.get("country"), "Country")
        if not country:
            continue
        out.append({"from": access.text(period.get("from"), "From") or "",
                    "to": access.text(period.get("to"), "To") or "",
                    "country": country,
                    "purpose": access.text(period.get("purpose"), "Purpose") or ""})
    return out


def _clean_evidence(evidence) -> list[str]:
    return [str(e).strip() for e in (evidence or []) if str(e).strip()]


def submit(conn, who, student_id, academic_year, *, nationality, residence, immigration_status,
           evidence=(), notes=None) -> int:
    """Record the questionnaire. Students may submit their own; staff need
    the fee-status capability. Returns the assessment id."""
    access.ensure(conn)
    access.require_self_or(conn, who, student_id, access.FEE_STATUS)
    access.student_row(conn, student_id)
    nationality = access.text(nationality, "Nationality", True)
    status = access.text(immigration_status, "Immigration status", True)
    if status not in IMMIGRATION_STATUSES:
        raise ValueError("Immigration status must be one of: " + ", ".join(IMMIGRATION_STATUSES))
    periods = _clean_residence(residence)
    if not periods:
        raise ValueError("Give where the student lived over the last three years")
    year = access.year_label(academic_year)
    conn.execute("UPDATE fee_status_assessments SET status = 'superseded' WHERE student_id = ? "
                 "AND academic_year = ? AND status = 'submitted'", (str(student_id), year))
    new_id = conn.execute(
        "INSERT INTO fee_status_assessments (student_id, academic_year, nationality, "
        "residence_json, immigration_status, evidence_json, notes, submitted_by) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?)",
        (str(student_id), year, nationality, json.dumps(periods), status,
         json.dumps(_clean_evidence(evidence)), access.text(notes, "Notes"),
         who.username)).lastrowid
    access.audit(conn, who.username, "fee_status.submitted", "fee_status_assessment", new_id,
                 student_id=student_id, detail={"academic_year": year,
                                                "nationality": nationality,
                                                "immigration_status": status,
                                                "residence": periods})
    return int(new_id)


def _lived_in(periods, places) -> bool:
    return bool(periods) and all(p["country"].strip().lower() in places for p in periods)


def suggest(assessment: dict) -> tuple[str, str]:
    """A suggested ``(category, why)`` from the questionnaire. Only a
    suggestion - the assessor decides."""
    nationality = str(assessment.get("nationality") or "").strip().lower()
    status = assessment.get("immigration_status") or ""
    periods = assessment.get("residence") or json.loads(assessment.get("residence_json") or "[]")
    local = UK | ISLANDS
    if _lived_in(periods, ISLANDS) and status in ("british_citizen", "indefinite_leave"):
        return "islands", "Lived in the Islands for the whole three years"
    if status == "irish_citizen" or nationality in ("ireland", "irish"):
        return "home_irish", "Irish national (Common Travel Area)"
    if status in ("refugee", "humanitarian_protection"):
        return "home_protection", "Protected immigration status"
    if status == "euss_settled":
        return "home_eu_settled", "EU Settlement Scheme settled status"
    if status == "euss_pre_settled":
        if _lived_in(periods, local | EU_EEA_CH):
            return "home_eu_pre_settled", "Pre-settled status with three years' residence"
        return "international_eu", "Pre-settled status without three years' residence"
    if status in ("british_citizen", "indefinite_leave"):
        if _lived_in(periods, local):
            return ("home" if status == "british_citizen" else "home_settled",
                    "Settled and ordinarily resident in the UK for three years")
        return "international", "Not ordinarily resident in the UK for the three years"
    if nationality in EU_EEA_CH:
        return "international_eu", "EU/EEA/Swiss national without EUSS status"
    return "international", "No settled or protected status"


def _load(conn, assessment_id) -> dict:
    row = access.one(conn.execute("SELECT * FROM fee_status_assessments WHERE assessment_id = ?",
                                  (int(assessment_id),)))
    if not row:
        raise ValueError(f"No fee-status assessment {assessment_id}")
    row["residence"] = json.loads(row.get("residence_json") or "[]")
    row["evidence"] = json.loads(row.get("evidence_json") or "[]")
    row["suggested"], row["suggested_why"] = suggest(row)
    return row


def get(conn, who, assessment_id) -> dict:
    access.ensure(conn)
    row = _load(conn, assessment_id)
    access.require_self_or(conn, who, row["student_id"], access.FEE_STATUS)
    return row


def decide(conn, who, assessment_id, category, reason) -> dict:
    """The assessor's decision. Writes the basis to the student record."""
    access.ensure(conn)
    access.require(conn, who, access.FEE_STATUS)
    if category not in CATEGORIES:
        raise ValueError("Category must be one of: " + ", ".join(CATEGORIES))
    reason = access.text(reason, "Reason", True)
    row = _load(conn, assessment_id)
    if row["status"] != "submitted":
        raise ValueError(f"Assessment {assessment_id} is {row['status']}, not awaiting a "
                         "decision")
    basis = CATEGORIES[category][1]
    conn.execute("UPDATE fee_status_assessments SET status = 'superseded' WHERE student_id = ? "
                 "AND academic_year = ? AND status = 'decided'",
                 (row["student_id"], row["academic_year"]))
    conn.execute("UPDATE fee_status_assessments SET status = 'decided', category = ?, "
                 "fee_basis = ?, decision_reason = ?, decided_by = ?, decided_at = ? WHERE "
                 "assessment_id = ?", (category, basis, reason, who.username, access.now(),
                                       int(assessment_id)))
    previous = access.student_row(conn, row["student_id"]).get("fee_status")
    conn.execute("UPDATE students SET fee_status = ? WHERE student_id = ?",
                 (basis, row["student_id"]))
    access.audit(conn, who.username, "fee_status.decided", "fee_status_assessment",
                 assessment_id, student_id=row["student_id"],
                 detail={"category": category, "basis": basis, "reason": reason,
                         "suggested": row["suggested"], "previous_record_value": previous,
                         "academic_year": row["academic_year"]})
    return {"category": category, "basis": basis, "label": CATEGORIES[category][0]}


def listing(conn, who, *, status="submitted", student_id=None) -> list[dict]:
    access.ensure(conn)
    if student_id is not None:
        access.require_self_or(conn, who, student_id, access.FEE_STATUS)
    else:
        access.require(conn, who, access.FEE_STATUS)
    sql = ("SELECT a.*, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
           "AS name FROM fee_status_assessments a LEFT JOIN students s ON s.student_id = "
           "a.student_id WHERE 1 = 1")
    params: list = []
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    if student_id is not None:
        sql += " AND a.student_id = ?"
        params.append(str(student_id))
    rows = access.dicts(conn.execute(sql + " ORDER BY a.assessment_id DESC", params))
    for r in rows:
        r["suggested"], r["suggested_why"] = suggest(r)
    return rows


def current(conn, student_id, academic_year=None) -> dict:
    """The fee basis used for charging: the decided assessment for the year
    (or the latest decided one), else the student record's value marked as
    not assessed. ``{"basis", "category", "label", "source", "assessment_id"}``."""
    access.ensure(conn)
    params: list = [str(student_id)]
    order = "assessment_id DESC"
    if academic_year:
        order = "(substr(academic_year, 1, 4) = ?) DESC, " + order
        params.append(str(access.year_start(academic_year)))
    row = access.one(conn.execute(
        "SELECT assessment_id, category, fee_basis, academic_year, decided_at FROM "
        f"fee_status_assessments WHERE student_id = ? AND status = 'decided' ORDER BY {order} "  # nosec B608
        "LIMIT 1", params))
    if row:
        return {"basis": row["fee_basis"], "category": row["category"],
                "label": CATEGORIES.get(row["category"], (row["category"],))[0],
                "source": f"assessed {str(row['decided_at'] or '')[:10]} for "
                          f"{row['academic_year']}", "assessment_id": row["assessment_id"]}
    recorded = str(access.student_row(conn, student_id).get("fee_status") or "").lower()
    if recorded in BASES:
        return {"basis": recorded, "category": None, "label": recorded.title(),
                "source": "student record (not assessed)", "assessment_id": None}
    return {"basis": None, "category": None, "label": "Not assessed",
            "source": "no assessment and nothing on the student record", "assessment_id": None}
