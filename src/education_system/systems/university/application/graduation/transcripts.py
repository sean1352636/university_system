"""Sharing a graduate's transcript with an employer, and the HEAR.

* **Shares.** A graduate shares their frozen transcript with an employer
  themselves; the graduation office may do it for them only with a recorded
  consent reference. The link carries a random token; only its SHA-256 is
  stored. Links expire, can be revoked, stop working when the award is
  suspended, revoked or reissued, and every opening is counted.
* **HEAR** (Higher Education Achievement Report, which also serves as the
  diploma supplement): the eight standard sections built from the ratified
  award, the conferral, the module results and verified achievements.
  Students propose achievements; the office verifies them.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import hashlib
import html
import os
import secrets
from datetime import date, timedelta

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.application.graduation import conferral as gc

SHARE_DAYS = 30
ACHIEVEMENT_CATEGORIES = ("Prize", "Volunteering", "Representation", "Placement",
                          "Additional course", "Leadership", "Other")


def _hash(token) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def share_url(token) -> str:
    base = os.environ.get("UNIVERSITY_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    return f"{base}/api/v1/university/graduation/transcript/{token}"


def share(conn, who, conferral_id, employer_name, employer_email, purpose="", *,
          days=SHARE_DAYS, consent_reference=None) -> dict:
    """Create a share link. Returns ``{"token", "url", "expires_at", "emails"}``
    — the token is shown once and never stored."""
    row = gc.conferral(conn, conferral_id)
    ga.require_self_or_office(who, row["student_id"])
    if not who.is_student:
        consent_reference = ga.text(consent_reference, "The graduate's consent reference", True)
    if row["status"] != "conferred":
        raise ValueError("Only a conferred award's transcript can be shared")
    if not row.get("freeze_id"):
        raise ValueError("There is no transcript snapshot for this award")
    email = ga.text(employer_email, "Employer e-mail", True)
    if "@" not in email:
        raise ValueError("That is not an e-mail address")
    days = int(days)
    if not 1 <= days <= 90:
        raise ValueError("A link lasts 1 to 90 days")
    token = secrets.token_urlsafe(24)
    expires = (date.today() + timedelta(days=days)).isoformat()
    tid = conn.execute(
        "INSERT INTO transcript_access_tokens (freeze_id, token, requested_by, employer_name, "
        "employer_email, purpose, expires_at, consent_reference, created_by) VALUES (?, ?, ?, ?, "
        "?, ?, ?, ?, ?)",
        (row["freeze_id"], _hash(token), row["student_id"],
         ga.text(employer_name, "Employer", True), email, purpose or "", expires,
         consent_reference or "graduate", who.username)).lastrowid
    ga.audit(conn, who, "transcript_share", tid, "created",
             {"employer": employer_name, "expires": expires, "consent": consent_reference})
    url = share_url(token)
    body = (f"{row['certificate_name']} has shared their transcript for {row['award_name']} with "
            f"you. Open it here before {expires}:\n{url}")
    return {"token_id": int(tid), "token": token, "url": url, "expires_at": expires,
            "emails": [(email, "A transcript has been shared with you", body)]}


def shares(conn, who, student_id) -> list[dict]:
    ga.ensure(conn)
    ga.require_self_or_office(who, student_id)
    return ga.dicts(conn.execute(
        "SELECT token_id, employer_name, employer_email, purpose, issued_at, expires_at, "
        "accessed_at, access_count, revoked, consent_reference FROM transcript_access_tokens t "
        "JOIN transcript_freezes f ON f.freeze_id = t.freeze_id WHERE f.student_id = ? ORDER BY "
        "token_id DESC", (student_id,)))


def revoke_share(conn, who, token_id) -> None:
    row = ga.one(conn, "SELECT t.*, f.student_id FROM transcript_access_tokens t JOIN "
                       "transcript_freezes f ON f.freeze_id = t.freeze_id WHERE t.token_id = ?",
                 (token_id,))
    if not row:
        raise ValueError("No such share")
    ga.require_self_or_office(who, row["student_id"])
    conn.execute("UPDATE transcript_access_tokens SET revoked = 1 WHERE token_id = ?",
                 (token_id,))
    ga.audit(conn, who, "transcript_share", token_id, "revoked")


def open_share(conn, token) -> dict:
    """What the employer's link shows. ``{"ok": False, "message"}`` when it
    cannot be opened; otherwise the snapshot and the award."""
    ga.ensure(conn)
    row = ga.one(conn, "SELECT t.*, f.snapshot_html, f.snapshot_hash, f.revoked_at AS "
                       "freeze_revoked, f.superseded_at, f.conferral_id FROM "
                       "transcript_access_tokens t JOIN transcript_freezes f ON f.freeze_id = "
                       "t.freeze_id WHERE t.token = ?", (_hash(token),))
    if not row:
        return {"ok": False, "message": "This link is not valid."}
    if row["revoked"]:
        return {"ok": False, "message": "This link has been withdrawn."}
    if row["expires_at"] and row["expires_at"] < ga.today():
        return {"ok": False, "message": "This link has expired."}
    if row["freeze_revoked"] or row["superseded_at"]:
        return {"ok": False, "message": "This transcript is no longer current."}
    award = ga.one(conn, "SELECT * FROM graduation_conferrals WHERE conferral_id = ?",
                   (row["conferral_id"],)) if row["conferral_id"] else None
    if award and award["status"] != "conferred":
        return {"ok": False, "message": "This award is under review or no longer valid."}
    conn.execute("UPDATE transcript_access_tokens SET accessed_at = ?, access_count = "
                 "COALESCE(access_count, 0) + 1 WHERE token_id = ?", (ga.now(), row["token_id"]))
    return {"ok": True, "html": row["snapshot_html"], "sha256": row["snapshot_hash"],
            "employer": row["employer_name"], "expires_at": row["expires_at"],
            "award": award["award_name"] if award else None,
            "classification": award["classification"] if award else None}


# ── HEAR achievements ───────────────────────────────────────────────────


def achievements(conn, who, student_id, verified_only=False) -> list[dict]:
    ga.ensure(conn)
    ga.require_self_or_office(who, student_id)
    return ga.dicts(conn.execute("SELECT * FROM hear_achievements WHERE student_id = ?" +
                                 (" AND verified_at IS NOT NULL" if verified_only else "") +
                                 " ORDER BY created_at", (student_id,)))


def add_achievement(conn, who, student_id, category, description) -> int:
    ga.ensure(conn)
    ga.require_self_or_office(who, student_id)
    if category not in ACHIEVEMENT_CATEGORIES:
        raise ValueError("Category must be one of " + ", ".join(ACHIEVEMENT_CATEGORIES))
    aid = conn.execute("INSERT INTO hear_achievements (student_id, category, description, "
                       "created_by, verified_by, verified_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (student_id, category, ga.text(description, "Description", True),
                        who.username, who.username if who.is_office else None,
                        ga.now() if who.is_office else None)).lastrowid
    ga.audit(conn, who, "hear", student_id, "achievement_added", {"id": aid})
    return int(aid)


def verify_achievement(conn, who, achievement_id) -> None:
    ga.require_office(who)
    if not conn.execute("UPDATE hear_achievements SET verified_by = ?, verified_at = ? WHERE "
                        "achievement_id = ? AND verified_at IS NULL",
                        (who.username, ga.now(), achievement_id)).rowcount:
        raise ValueError("No such unverified achievement")


def remove_achievement(conn, who, achievement_id) -> None:
    row = ga.one(conn, "SELECT * FROM hear_achievements WHERE achievement_id = ?",
                 (achievement_id,))
    if not row:
        raise ValueError("No such achievement")
    ga.require_self_or_office(who, row["student_id"])
    ga.require(who.is_office or not row["verified_at"],
               "A verified achievement can only be removed by the office")
    conn.execute("DELETE FROM hear_achievements WHERE achievement_id = ?", (achievement_id,))


# ── the HEAR ────────────────────────────────────────────────────────────


def _results(conn, student_id) -> list[dict]:
    if not ga.has_table(conn, "module_grades"):
        return []
    return ga.dicts(conn.execute(
        "SELECT g.module_code, COALESCE(m.module_name, g.module_code) AS module_name, "
        "COALESCE(g.credits_awarded, m.credits) AS credits, m.level, g.final_score, "
        "g.final_grade, g.outcome FROM module_grades g LEFT JOIN modules m ON m.module_code = "
        "g.module_code WHERE g.student_id = ? ORDER BY m.level, g.module_code", (student_id,)))


def hear(conn, who, student_id) -> dict:
    """The HEAR's sections as data (for screens and the CLI)."""
    ga.ensure(conn)
    ga.require_self_or_office(who, student_id)
    st = ga.student(conn, student_id)
    conf = ga.one(conn, "SELECT * FROM graduation_conferrals WHERE student_id = ? AND status = "
                        "'conferred' ORDER BY conferral_id DESC LIMIT 1", (student_id,))
    if not conf:
        raise ValueError("The HEAR is issued once the award has been conferred")
    return {
        "1 Holder": [("Name", conf["certificate_name"]), ("Student number", student_id),
                     ("Date of birth", st.get("date_of_birth") or st.get("dob"))],
        "2 Qualification": [("Award", conf["award_name"]),
                            ("Classification", conf["classification"]),
                            ("Programme", conf["programme_code"]),
                            ("Awarding body", "The University")],
        "3 Level": [("Framework", "FHEQ (England, Wales and Northern Ireland)")],
        "4 Contents and results": _results(conn, student_id),
        "5 Function": [("Access to further study", "Gives access to postgraduate study")],
        "6 Additional information": achievements(conn, who, student_id, verified_only=True),
        "7 Certification": [("Conferred", conf["conferral_date"]),
                            ("Certificate", conf["certificate_number"]),
                            ("Verification code", conf["verification_code"])],
        "8 Higher education in the UK": [("Note", "Standard description of the UK higher "
                                                  "education system")],
    }


def hear_html(conn, who, student_id) -> str:
    data = hear(conn, who, student_id)
    out = ["<html><head><meta charset='utf-8'><title>HEAR</title></head><body>",
           "<h1>Higher Education Achievement Report</h1>"]
    for section, body in data.items():
        out.append(f"<h2>{html.escape(section)}</h2>")
        if body and isinstance(body[0], dict):
            keys = list(body[0])
            out.append("<table border='1' cellpadding='4'><tr>" +
                       "".join(f"<th>{html.escape(k)}</th>" for k in keys) + "</tr>")
            for row in body:
                out.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(k) or ''))}</td>"
                                            for k in keys) + "</tr>")
            out.append("</table>")
        else:
            out.append("<dl>" + "".join(f"<dt>{html.escape(str(k))}</dt><dd>"
                                        f"{html.escape(str(v or '—'))}</dd>"
                                        for k, v in body) + "</dl>" if body else "<p>—</p>")
    out.append("</body></html>")
    return "\n".join(out)
