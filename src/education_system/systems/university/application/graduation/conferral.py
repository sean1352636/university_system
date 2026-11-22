"""Conferring an award, and what happens to it afterwards.

:func:`confer` is the one way an award is given, at a ceremony or in
absentia. In one transaction it checks eligibility (ratified + released
award, no holds, certificate name confirmed) and creates:

* the certificate (dated the conferral date, in the confirmed name, the
  award and classification taken from the ratified award — never typed in),
* a digital credential with a random verification code,
* an immutable transcript snapshot,
* the certificate print job,
* the alumni record, and the student's lifecycle move to Completed.

After the commit, :func:`after_commit` publishes the lifecycle change, gives
the login the alumni role and sends the e-mails.

If an assessment board reopens, :func:`suspend_for_board` suspends its
conferrals (certificates stop verifying); :func:`review_suspended` then
reinstates them or, when the award changed, reissues them.
:func:`revoke` withdraws an award; :func:`replace_certificate` issues a
replacement and cancels the original.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
import secrets

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.application.graduation import eligibility as ge

MODES = ("ceremony", "in_absentia")
DELIVERY = ("ceremony", "post", "collect")
JOB_STATUSES = ("queued", "printing", "printed", "dispatched", "collected", "cancelled", "failed")
_JOB_NEXT = {"queued": {"printing", "cancelled"}, "printing": {"printed", "failed", "cancelled"},
             "printed": {"dispatched", "collected", "cancelled"}, "failed": {"queued",
                                                                             "cancelled"},
             "dispatched": set(), "collected": set(), "cancelled": set()}
REPLACEMENT_FEE = 40.0


def conferral(conn, conferral_id) -> dict:
    ga.ensure(conn)
    row = ga.one(conn, "SELECT * FROM graduation_conferrals WHERE conferral_id = ?",
                 (conferral_id,))
    if not row:
        raise ValueError("No such conferral")
    return row


def _render_transcript(student_id, academic_year):
    from education_system.platform.features.certificates.transcript_service import (
        TranscriptService,
    )
    return TranscriptService().export_transcript_html(student_id, academic_year=academic_year)


def _certificate(conn, student_id, award, name, day, mode, who) -> tuple[int, str]:
    number = f"CERT-{secrets.token_hex(6).upper()}"
    cid = conn.execute(
        "INSERT INTO certificates (student_id, certificate_number, certificate_type, course_name, "
        "award_date, grade, additional_info, status, issued_by) VALUES (?, ?, 'completion', ?, ?, "
        "?, ?, 'active', ?)",
        (student_id, number, award["award_name"], day, award.get("classification"),
         f"Awarded to {name}" + (" in absentia" if mode == "in_absentia" else ""),
         getattr(who, "username", "system"))).lastrowid
    return int(cid), number


def _credential(conn, student_id, award, number, day) -> tuple[int | None, str]:
    code = secrets.token_urlsafe(12)
    if not ga.has_table(conn, "blockchain_credentials"):
        return None, code
    meta = {"certificate_number": number, "award": award["award_name"],
            "classification": award.get("classification"), "conferred": day}
    cid = conn.execute(
        "INSERT INTO blockchain_credentials (student_id, credential_type, credential_name, "
        "issue_date, blockchain_hash, metadata) VALUES (?, 'degree', ?, ?, ?, ?)",
        (student_id, award["award_name"], day, code, json.dumps(meta))).lastrowid
    return int(cid), code


def _freeze(conn, student_id, award, html, who, conferral_id) -> int | None:
    import hashlib
    if not html or not ga.has_table(conn, "transcript_freezes"):
        return None
    year = award.get("academic_year") or ""
    old = conn.execute("SELECT freeze_id FROM transcript_freezes WHERE student_id = ? AND "
                       "academic_year = ?", (student_id, year)).fetchone()
    if old:     # keep the old snapshot as it was; only its key moves aside
        conn.execute("UPDATE transcript_freezes SET academic_year = ?, superseded_at = ? WHERE "
                     "freeze_id = ?", (f"{year} (superseded #{old[0]})", ga.now(), old[0]))
    fid = conn.execute(
        "INSERT INTO transcript_freezes (student_id, program_id, academic_year, snapshot_html, "
        "snapshot_hash, frozen_by, gpa, classification, conferral_id) VALUES (?, NULL, ?, ?, ?, "
        "?, '', ?, ?)",
        (student_id, year, html, hashlib.sha256(html.encode("utf-8")).hexdigest(),
         getattr(who, "username", "system"), award.get("classification"), conferral_id)
    ).lastrowid
    return int(fid)


def _alumni(conn, st, award, day) -> None:
    if not ga.has_table(conn, "alumni"):
        return
    conn.execute(
        "INSERT INTO alumni (alumni_id, student_id, email_address, first_name, last_name, "
        "graduation_year, degree_earned, date_registered) VALUES (?, ?, ?, ?, ?, ?, ?, "
        "datetime('now')) ON CONFLICT (alumni_id) DO UPDATE SET graduation_year = "
        "excluded.graduation_year, degree_earned = excluded.degree_earned",
        (st["student_id"], st["student_id"], st.get("email_address"), st.get("first_name"),
         st.get("last_name"), int(day[:4]), award["award_name"]))


def _complete_student(conn, st, who) -> int | None:
    """Lifecycle 'complete' (Active → Completed). Returns the history id to
    publish after commit; legacy 'Graduated' is normalised to Completed."""
    status = st.get("status") or ""
    if status == "Graduated":
        conn.execute("UPDATE students SET status = 'Completed', is_active = 0 WHERE student_id "
                     "= ?", (st["student_id"],))
        return None
    if status != "Active":
        return None
    if ga.has_table(conn, "student_lifecycle_history") and \
            ga.has_table(conn, "student_lifecycle_actions"):
        from education_system.systems.university.domains.learners.domain import student_lifecycle
        from education_system.systems.university.infrastructure.database.db import (
            sqlite3 as _sqlite,
        )
        from education_system.systems.university.services.boundary_errors import (
            EnrolmentBoundaryError,
        )
        before = conn.row_factory
        conn.row_factory = _sqlite.Row          # the lifecycle reads rows by name
        try:
            history_id, _ = student_lifecycle.apply_status_change(
                conn, st["student_id"], "complete", actor_id=getattr(who, "username", "system"),
                reason="Award conferred")
        except EnrolmentBoundaryError as exc:
            raise ValueError(str(exc)) from None
        finally:
            conn.row_factory = before
        return int(history_id)
    conn.execute("UPDATE students SET status = 'Completed', is_active = 0 WHERE student_id = ?",
                 (st["student_id"],))
    return None


def confer(conn, who, student_id, *, mode="in_absentia", ceremony_id=None, conferral_date=None,
           delivery=None, address=None, render=_render_transcript) -> dict:
    """Confer the student's ratified award. Returns the conferral summary
    (pass it to :func:`after_commit` once committed)."""
    ga.ensure(conn)
    ga.require_office(who)
    if mode not in MODES:
        raise ValueError("Mode must be ceremony or in_absentia")
    report = ge.check(conn, student_id)
    if report["conferral"]:
        raise ValueError(f"{student_id} already has this award conferred")
    if report["blockers"]:
        raise ValueError("Cannot confer: " + "; ".join(report["blockers"]))
    if not report["name_confirmed"]:
        raise ValueError("The name on the certificate has not been confirmed")
    award = report["award"]
    day = ga.iso_date(conferral_date, "Conferral date") or ga.today()
    if mode == "ceremony":
        if not ceremony_id:
            raise ValueError("Say which ceremony")
        attended = conn.execute("SELECT attended_at FROM ceremony_rsvps WHERE ceremony_id = ? AND "
                                "student_id = ?", (ceremony_id, student_id)).fetchone()
        if not attended or not attended[0]:
            raise ValueError("The graduand was not checked in at that ceremony")
    delivery = delivery or ("ceremony" if mode == "ceremony" else "post")
    if delivery not in DELIVERY:
        raise ValueError("Delivery must be ceremony, post or collect")
    if delivery == "post" and not (address or "").strip():
        st_addr = ga.one(conn, "SELECT * FROM students WHERE student_id = ?", (student_id,))
        address = (st_addr or {}).get("address") or ""
    st = ga.student(conn, student_id)
    html = render(student_id, award.get("academic_year")) if render else None
    name = report["certificate_name"]
    cert_id, number = _certificate(conn, student_id, award, name, day, mode, who)
    cred_id, code = _credential(conn, student_id, award, number, day)
    cid = conn.execute(
        "INSERT INTO graduation_conferrals (student_id, award_id, programme_code, award_name, "
        "classification, academic_year, conferral_date, mode, ceremony_id, certificate_name, "
        "certificate_id, certificate_number, credential_id, verification_code, conferred_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, award["award_id"], award.get("programme_code"), award["award_name"],
         award.get("classification"), award.get("academic_year"), day, mode, ceremony_id, name,
         cert_id, number, cred_id, code, who.username)).lastrowid
    freeze_id = _freeze(conn, student_id, award, html, who, cid)
    conn.execute("UPDATE graduation_conferrals SET freeze_id = ? WHERE conferral_id = ?",
                 (freeze_id, cid))
    conn.execute("INSERT INTO certificate_print_jobs (conferral_id, student_id, certificate_id, "
                 "certificate_number, kind, delivery, ceremony_id, address) VALUES (?, ?, ?, ?, "
                 "'original', ?, ?, ?)",
                 (cid, student_id, cert_id, number, delivery, ceremony_id, address or None))
    _alumni(conn, st, award, day)
    if ga.has_table(conn, "alumni"):
        from education_system.systems.university.application.alumni import (
            records as alumni_records,
        )
        alumni_records.on_conferral(conn, student_id, day)
    history_id = _complete_student(conn, st, who)
    if ga.has_table(conn, "graduation_checklist"):
        conn.execute("UPDATE graduation_checklist SET conferral_status = 'conferred', "
                     "graduation_date = ? WHERE student_id = ?", (day, student_id))
    ga.audit(conn, who, "conferral", cid, "conferred",
             {"student": student_id, "award": award["award_name"], "mode": mode,
              "ceremony": ceremony_id, "certificate": number})
    emails = ga.notify(conn, [student_id], f"Congratulations: {award['award_name']}",
                       f"Your award {award['award_name']}"
                       + (f" ({award['classification']})" if award.get("classification") else "")
                       + f" was conferred on {day}. Certificate {number}. Anyone can check it "
                         f"with verification code {code}.")
    return {"conferral_id": int(cid), "student_id": student_id, "certificate_number": number,
            "verification_code": code, "history_id": history_id, "emails": emails}


def after_commit(result) -> None:
    """Post-commit work for :func:`confer`: lifecycle event, alumni role."""
    if not isinstance(result, dict) or "conferral_id" not in result:
        return
    sid = result["student_id"]
    if result.get("history_id"):
        try:
            from education_system.systems.university.domains.learners.domain import (
                student_lifecycle,
            )
            student_lifecycle.publish_change(sid, "complete", result["history_id"])
        except Exception:
            pass
    promote_to_alumni(sid)


def promote_to_alumni(student_id) -> bool:
    """Give the graduate's shared login the university 'alumni' role, so the
    next sign-in opens the alumni portal. Best effort."""
    try:
        from education_system.platform.identity.auth.db import connect as auth_connect
        from education_system.platform.identity.auth.role_manager import RoleManager
        conn = auth_connect()
        try:
            row = conn.execute("SELECT id FROM users WHERE username = ?",
                               (student_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            return False
        RoleManager().grant_system_access(row[0], "university", "alumni")
        return True
    except Exception:
        return False


# ── suspension, review, revocation ──────────────────────────────────────


def _set_status(conn, who, conferral_id, status, reason) -> None:
    conn.execute("UPDATE graduation_conferrals SET status = ?, status_changed_at = ?, "
                 "status_changed_by = ?, status_reason = ? WHERE conferral_id = ?",
                 (status, ga.now(), getattr(who, "username", who), reason, conferral_id))


def _artefacts(conn, row, certificate_status, revoked, end_shares=False) -> None:
    if row.get("certificate_id"):
        conn.execute("UPDATE certificates SET status = ? WHERE id = ?",
                     (certificate_status, row["certificate_id"]))
    if row.get("credential_id") and ga.has_table(conn, "blockchain_credentials"):
        conn.execute("UPDATE blockchain_credentials SET is_revoked = ?, revoked_at = ? WHERE "
                     "credential_id = ?",
                     (int(revoked), ga.now() if revoked else None, row["credential_id"]))
    if end_shares and row.get("freeze_id") and ga.has_table(conn, "transcript_access_tokens"):
        conn.execute("UPDATE transcript_access_tokens SET revoked = 1 WHERE freeze_id = ?",
                     (row["freeze_id"],))


def suspend_for_board(conn, board_id, actor="assessment board") -> list[int]:
    """The board reopened: suspend conferrals of its awards. Returns ids."""
    ga.ensure(conn)
    rows = ga.dicts(conn.execute(
        "SELECT c.* FROM graduation_conferrals c JOIN ratified_student_awards a ON a.award_id = "
        "c.award_id WHERE a.board_id = ? AND c.status = 'conferred'", (board_id,)))
    for row in rows:
        _set_status(conn, actor, row["conferral_id"], "suspended",
                    f"Assessment board {board_id} reopened")
        _artefacts(conn, row, "suspended", True)
        ga.audit(conn, actor, "conferral", row["conferral_id"], "suspended", {"board": board_id})
        ga.notify(conn, ga.office_usernames(conn) + [row["student_id"]],
                  "Award under review",
                  f"The award {row['award_name']} is back with the assessment board. Its "
                  "certificate will not verify until the review is finished.")
    return [r["conferral_id"] for r in rows]


def review_suspended(conn, who, conferral_id, render=_render_transcript) -> dict:
    """After the board: reinstate the conferral when the award stands
    unchanged, otherwise reissue it against the new award."""
    ga.require_office(who)
    row = conferral(conn, conferral_id)
    if row["status"] != "suspended":
        raise ValueError("Only a suspended conferral can be reviewed")
    current = ge.award(conn, row["student_id"])
    if current is None:
        raise ValueError("The board has not released the award again yet")
    unchanged = current["award_id"] == row["award_id"] and \
        (current.get("classification") or "") == (row.get("classification") or "")
    if unchanged:
        _set_status(conn, who, conferral_id, "conferred", "Award confirmed after board review")
        _artefacts(conn, row, "active", False)
        ga.audit(conn, who, "conferral", conferral_id, "reinstated")
        return {"conferral_id": conferral_id, "reinstated": True, "emails": []}
    _set_status(conn, who, conferral_id, "superseded", "Award changed by the assessment board")
    _artefacts(conn, row, "revoked", True, end_shares=True)
    conn.execute("UPDATE certificate_print_jobs SET status = 'cancelled' WHERE conferral_id = ? "
                 "AND status IN ('queued', 'printing', 'printed', 'failed')", (conferral_id,))
    result = confer(conn, who, row["student_id"], mode="in_absentia",
                    conferral_date=row["conferral_date"], render=render)
    conn.execute("UPDATE graduation_conferrals SET replaces_conferral_id = ?, mode = ?, "
                 "ceremony_id = ? WHERE conferral_id = ?",
                 (conferral_id, row["mode"], row["ceremony_id"], result["conferral_id"]))
    ga.audit(conn, who, "conferral", conferral_id, "reissued", {"new": result["conferral_id"]})
    return {**result, "reinstated": False, "replaces": conferral_id}


def revoke(conn, who, conferral_id, reason) -> list:
    """Withdraw a conferred award (e.g. after a misconduct finding)."""
    ga.require_office(who)
    row = conferral(conn, conferral_id)
    if row["status"] not in ("conferred", "suspended"):
        raise ValueError("This award is not currently conferred")
    reason = ga.text(reason, "Reason", True)
    _set_status(conn, who, conferral_id, "revoked", reason)
    _artefacts(conn, row, "revoked", True, end_shares=True)
    if row.get("freeze_id"):
        conn.execute("UPDATE transcript_freezes SET revoked_at = ? WHERE freeze_id = ?",
                     (ga.now(), row["freeze_id"]))
    conn.execute("UPDATE certificate_print_jobs SET status = 'cancelled' WHERE conferral_id = ? "
                 "AND status IN ('queued', 'printing', 'printed', 'failed')", (conferral_id,))
    ga.audit(conn, who, "conferral", conferral_id, "revoked", {"reason": reason})
    return ga.notify(conn, [row["student_id"]], f"Award revoked: {row['award_name']}", reason)


# ── certificates and printing ───────────────────────────────────────────


def replace_certificate(conn, who, conferral_id, reason, *, delivery="post", address=None,
                        waive_fee=False) -> dict:
    """A replacement certificate; the original stops verifying. The student
    may ask for their own; only the office can waive the fee."""
    row = conferral(conn, conferral_id)
    ga.require_self_or_office(who, row["student_id"])
    if row["status"] != "conferred":
        raise ValueError("Only a conferred award gets a replacement certificate")
    if delivery not in ("post", "collect"):
        raise ValueError("Replacements are posted or collected")
    if delivery == "post" and not (address or "").strip():
        raise ValueError("Give the postal address")
    ga.require(not waive_fee or who.is_office, "Only the graduation office can waive the fee")
    reason = ga.text(reason, "Reason", True)
    award = {"award_name": row["award_name"], "classification": row["classification"]}
    conn.execute("UPDATE certificates SET status = 'replaced' WHERE id = ?",
                 (row["certificate_id"],))
    cert_id, number = _certificate(conn, row["student_id"], award, row["certificate_name"],
                                   row["conferral_date"], row["mode"], who)
    conn.execute("UPDATE graduation_conferrals SET certificate_id = ?, certificate_number = ? "
                 "WHERE conferral_id = ?", (cert_id, number, conferral_id))
    fee = 0.0 if waive_fee else REPLACEMENT_FEE
    conn.execute("INSERT INTO certificate_print_jobs (conferral_id, student_id, certificate_id, "
                 "certificate_number, kind, delivery, address, fee, notes) VALUES (?, ?, ?, ?, "
                 "'replacement', ?, ?, ?, ?)",
                 (conferral_id, row["student_id"], cert_id, number, delivery, address or None, fee,
                  reason))
    ga.audit(conn, who, "conferral", conferral_id, "certificate_replaced",
             {"old": row["certificate_number"], "new": number, "fee": fee, "reason": reason})
    return {"certificate_number": number, "fee": fee, "student_id": row["student_id"]}


def charge_replacement_fee(result, actor) -> None:
    """After commit: put the replacement fee on the student's account."""
    if not result or not result.get("fee"):
        return
    try:
        from education_system.systems.university.services.bus.finance_bus import raise_charge
        raise_charge(result["student_id"], result["fee"], source="graduation",
                     description=f"Replacement certificate {result['certificate_number']}",
                     reference_id=result["certificate_number"], processed_by=actor)
    except Exception:
        pass


def print_jobs(conn, status=None, ceremony_id=None) -> list[dict]:
    ga.ensure(conn)
    where, params = [], []
    if status:
        where.append("j.status = ?")
        params.append(status)
    if ceremony_id:
        where.append("j.ceremony_id = ?")
        params.append(ceremony_id)
    return ga.dicts(conn.execute(
        "SELECT j.*, c.certificate_name, c.award_name FROM certificate_print_jobs j LEFT JOIN "
        "graduation_conferrals c ON c.conferral_id = j.conferral_id" +
        (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY j.job_id DESC", params))


def set_job_status(conn, who, job_id, status, note="") -> None:
    ga.require_office(who)
    job = ga.one(conn, "SELECT * FROM certificate_print_jobs WHERE job_id = ?", (job_id,))
    if not job:
        raise ValueError("No such print job")
    if status not in _JOB_NEXT.get(job["status"], set()):
        raise ValueError(f"A {job['status']} job cannot become {status}")
    stamp = {"printed": "printed_at", "dispatched": "dispatched_at",
             "collected": "dispatched_at"}.get(status)
    sets = "status = ?, notes = TRIM(COALESCE(notes, '') || ' ' || ?)"
    if stamp:
        sets += f", {stamp} = datetime('now')"
    conn.execute(f"UPDATE certificate_print_jobs SET {sets} WHERE job_id = ?",
                 (status, note or "", job_id))
    ga.audit(conn, who, "print_job", job_id, status, {"note": note} if note else None)


# ── verification and lists ──────────────────────────────────────────────


def verify(conn, reference) -> dict:
    """Public check of a certificate number or verification code. Says only
    what the certificate itself says."""
    ga.ensure(conn)
    ref = str(reference or "").strip()
    if not ref:
        return {"valid": False, "message": "Enter a certificate number or verification code."}
    row = ga.one(conn, "SELECT * FROM graduation_conferrals WHERE verification_code = ? OR "
                       "certificate_number = ? ORDER BY conferral_id DESC LIMIT 1", (ref, ref))
    if row is None:
        cert = ga.one(conn, "SELECT * FROM certificates WHERE certificate_number = ?", (ref,))
        if cert is None:
            return {"valid": False, "message": "No award matches that reference."}
        row = ga.one(conn, "SELECT * FROM graduation_conferrals WHERE certificate_id = ?",
                     (cert["id"],))
        if row is None or cert["status"] == "replaced":
            return {"valid": False, "message": "That certificate has been replaced or is not a "
                                               "conferred award."}
    messages = {"conferred": "This award is valid.",
                "suspended": "This award is under review by the university.",
                "revoked": "This award has been revoked.",
                "superseded": "This award was reissued; this certificate is no longer valid."}
    return {"valid": row["status"] == "conferred", "status": row["status"],
            "message": messages[row["status"]], "name": row["certificate_name"],
            "award": row["award_name"], "classification": row["classification"],
            "conferral_date": row["conferral_date"],
            "in_absentia": row["mode"] == "in_absentia"}


def listing(conn, who, student_id=None, status=None, search=None) -> list[dict]:
    ga.ensure(conn)
    if who.is_student:
        student_id = who.student_id
    else:
        ga.require_office(who)
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if status:
        where.append("status = ?")
        params.append(status)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(student_id) LIKE ? OR LOWER(certificate_name) LIKE ? OR "
                     "LOWER(award_name) LIKE ? OR LOWER(COALESCE(certificate_number, '')) LIKE ?)")
        params += [like] * 4
    return ga.dicts(conn.execute("SELECT * FROM graduation_conferrals" +
                                 (" WHERE " + " AND ".join(where) if where else "") +
                                 " ORDER BY conferral_id DESC", params))


def record(conn, who, conferral_id) -> dict:
    row = conferral(conn, conferral_id)
    ga.require_self_or_office(who, row["student_id"])
    row["print_jobs"] = ga.dicts(conn.execute("SELECT * FROM certificate_print_jobs WHERE "
                                              "conferral_id = ? ORDER BY job_id",
                                              (conferral_id,)))
    row["history"] = ga.history(conn, "conferral", conferral_id)
    return row
