"""Alumni community: chapters, mentoring current students (with vetting,
the student's consent and a way to raise concerns), and moderation of the
forum, stories and photos.

* **Chapters** use ``regional_chapters`` + ``chapter_memberships`` only.
* **Mentoring**: an alumnus offers to mentor; the mentoring coordinator
  vets them (training done, approval expires after three years); only a
  vetted mentor can be proposed to a student, and the match starts only
  when the student accepts. Either side or the coordinator can end it, and
  anyone in it can raise a concern, which pauses the match until the
  coordinator closes or escalates it. :func:`suggest_matches` ranks vetted
  mentors with room for another mentee against a student (subject,
  focus/skills, experience, location) and explains each score; the
  coordinator still proposes the match.
* **Moderation**: anyone signed in can report a post, reply, story or
  photo; a moderator upholds (hides) or dismisses it. Stories are published
  only with the author's consent and a moderator's approval; photos are
  featured only once consent is confirmed. A moderator can also delete a
  photo permanently (:func:`delete_photo`): the record and the stored file
  go, the audit keeps who, when and why.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from education_system.systems.university.application.alumni import access as aa

VETTING_YEARS = 3
MAX_MENTEES = 3
_OPEN_MATCH = ("proposed", "active", "paused")
_COMMON = frozenset("""and the for with from into that this your their have about other
studies study university college school degree bachelor master honours hons bsc ba msc
ma phd year years student students work working""".split())
REPORT_KINDS = {"forum_post": ("alumni_forum", "post_id"),
                "forum_reply": ("forum_replies", "reply_id"),
                "story": ("alumni_stories", "story_id"),
                "photo": ("photo_gallery", "photo_id")}


def _office(who):
    return who is not None and who.is_office


def _alumnus(who):
    aa.require(who is not None and who.alumni_id is not None, "Only alumni can do this")


# ── chapters ────────────────────────────────────────────────────────────


def chapters(conn) -> list[dict]:
    aa.ensure(conn)
    return aa.dicts(conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM chapter_memberships m WHERE m.chapter_id = "
        "c.chapter_id) AS members FROM regional_chapters c WHERE COALESCE(c.status, 'active') = "
        "'active' ORDER BY c.chapter_name"))


def save_chapter(conn, who, data, chapter_id=None) -> int:
    aa.ensure(conn)
    aa.require(_office(who), "Only the alumni office can manage chapters")
    fields = {k: aa.text(data.get(k), k.replace("_", " "), k == "chapter_name" and
                         chapter_id is None)
              for k in ("chapter_name", "location", "description", "contact_email") if k in data}
    if chapter_id:
        if fields:
            conn.execute(f"UPDATE regional_chapters SET {', '.join(f'{k} = ?' for k in fields)} "
                         "WHERE chapter_id = ?", (*fields.values(), chapter_id))
        aa.audit(conn, who, "chapter", chapter_id, "edited")
        return int(chapter_id)
    cid = conn.execute(f"INSERT INTO regional_chapters ({', '.join(fields)}, created_by, "
                       f"created_date, status) VALUES ({', '.join('?' * len(fields))}, ?, ?, "
                       "'active')", (*fields.values(), who.username, aa.now())).lastrowid
    aa.audit(conn, who, "chapter", cid, "created")
    return int(cid)


def close_chapter(conn, who, chapter_id) -> None:
    aa.require(_office(who), "Only the alumni office can manage chapters")
    if not conn.execute("UPDATE regional_chapters SET status = 'inactive' WHERE chapter_id = ?",
                        (chapter_id,)).rowcount:
        raise ValueError("No such chapter")
    aa.audit(conn, who, "chapter", chapter_id, "closed")


def join(conn, who, chapter_id) -> None:
    _alumnus(who)
    if not conn.execute("SELECT 1 FROM regional_chapters WHERE chapter_id = ? AND COALESCE("
                        "status, 'active') = 'active'", (chapter_id,)).fetchone():
        raise ValueError("No such chapter")
    if conn.execute("SELECT 1 FROM chapter_memberships WHERE chapter_id = ? AND alumni_id = ?",
                    (chapter_id, who.alumni_id)).fetchone():
        raise ValueError("You are already a member")
    conn.execute("INSERT INTO chapter_memberships (chapter_id, alumni_id, join_date, role) "
                 "VALUES (?, ?, ?, 'member')", (chapter_id, who.alumni_id, aa.today()))
    _sync_count(conn, chapter_id)


def leave(conn, who, chapter_id, alumni_id=None) -> None:
    alumni_id = alumni_id or (who.alumni_id if who else None)
    aa.require_self_or(who, alumni_id, _office)
    if not conn.execute("DELETE FROM chapter_memberships WHERE chapter_id = ? AND alumni_id = ?",
                        (chapter_id, alumni_id)).rowcount:
        raise ValueError("Not a member of that chapter")
    _sync_count(conn, chapter_id)


def _sync_count(conn, chapter_id) -> None:
    conn.execute("UPDATE regional_chapters SET member_count = (SELECT COUNT(*) FROM "
                 "chapter_memberships WHERE chapter_id = ?) WHERE chapter_id = ?",
                 (chapter_id, chapter_id))


def set_leader(conn, who, chapter_id, alumni_id) -> None:
    aa.require(_office(who), "Only the alumni office can appoint chapter leaders")
    if not conn.execute("UPDATE chapter_memberships SET role = 'leader' WHERE chapter_id = ? AND "
                        "alumni_id = ?", (chapter_id, alumni_id)).rowcount:
        raise ValueError("The leader must be a member of the chapter")
    conn.execute("UPDATE regional_chapters SET coordinator_id = ? WHERE chapter_id = ?",
                 (alumni_id, chapter_id))
    aa.audit(conn, who, "chapter", chapter_id, "leader", {"alumni": alumni_id})


def members(conn, who, chapter_id) -> list[dict]:
    """Members' names for the office or the chapter's leader."""
    leads = who is not None and who.alumni_id and conn.execute(
        "SELECT 1 FROM chapter_memberships WHERE chapter_id = ? AND alumni_id = ? AND role = "
        "'leader'", (chapter_id, who.alumni_id)).fetchone()
    aa.require(_office(who) or leads, "Only the chapter leader can see the members")
    return aa.dicts(conn.execute(
        "SELECT m.alumni_id, m.role, m.join_date, a.first_name, a.last_name, CASE WHEN "
        "COALESCE(d.show_contact_info, 0) = 1 THEN a.email_address END AS email FROM "
        "chapter_memberships m JOIN alumni a ON a.alumni_id = m.alumni_id LEFT JOIN "
        "alumni_directory_settings d ON d.alumni_id = m.alumni_id WHERE m.chapter_id = ? ORDER "
        "BY CASE m.role WHEN 'leader' THEN 0 ELSE 1 END, a.last_name", (chapter_id,)))


def my_chapters(conn, who) -> list[dict]:
    _alumnus(who)
    return aa.dicts(conn.execute("SELECT c.*, m.role FROM chapter_memberships m JOIN "
                                 "regional_chapters c ON c.chapter_id = m.chapter_id WHERE "
                                 "m.alumni_id = ?", (who.alumni_id,)))


# ── mentoring ───────────────────────────────────────────────────────────


def _coord(who):
    return who is not None and who.is_coordinator


def offer_to_mentor(conn, who, focus_areas) -> None:
    _alumnus(who)
    if not aa.contactable(aa.alumnus(conn, who.alumni_id)):
        raise ValueError("This alumni record cannot take on mentoring")
    conn.execute("INSERT INTO mentor_vetting (alumni_id, focus_areas) VALUES (?, ?) ON CONFLICT "
                 "(alumni_id) DO UPDATE SET focus_areas = excluded.focus_areas",
                 (who.alumni_id, aa.text(focus_areas, "What you can help with", True)))
    aa.audit(conn, who, "mentoring", who.alumni_id, "offered")
    aa.notify(conn, aa.holders(conn, "mentoring_coordinator"), "New mentor offer",
              f"{who.alumni_id} offered to mentor students. Please vet them.")


def vet(conn, who, alumni_id, approve, *, training_completed=False, expires_on=None,
        notes="") -> None:
    aa.require(_coord(who), "Only the mentoring coordinator can vet mentors")
    if not conn.execute("SELECT 1 FROM mentor_vetting WHERE alumni_id = ?",
                        (alumni_id,)).fetchone():
        raise ValueError("That alumnus has not offered to mentor")
    if approve and not training_completed:
        raise ValueError("Mentors must complete safeguarding training before approval")
    if approve and not aa.contactable(aa.alumnus(conn, alumni_id)):
        raise ValueError("This alumni record cannot take on mentoring")
    expires = aa.iso_date(expires_on, "Expires on") or (
        date.today() + timedelta(days=365 * VETTING_YEARS)).isoformat()
    conn.execute("UPDATE mentor_vetting SET status = ?, training_completed = ?, checked_by = ?, "
                 "checked_at = ?, expires_on = ?, notes = ? WHERE alumni_id = ?",
                 ("approved" if approve else "rejected", int(bool(training_completed)),
                  who.username, aa.now(), expires if approve else None, notes or None,
                  alumni_id))
    conn.execute("UPDATE alumni SET is_mentor = ? WHERE alumni_id = ?", (int(bool(approve)),
                                                                          alumni_id))
    aa.audit(conn, who, "mentoring", alumni_id, "vetted", {"approved": bool(approve)})


def vetted(conn, alumni_id, on=None) -> bool:
    day = aa.iso_date(on, "Date") or aa.today()
    return conn.execute("SELECT 1 FROM mentor_vetting v JOIN alumni a ON a.alumni_id = "
                        "v.alumni_id WHERE v.alumni_id = ? AND v.status = 'approved' AND "
                        "v.training_completed = 1 AND v.expires_on >= ? AND a.deceased_at IS NULL "
                        "AND a.anonymised_at IS NULL", (alumni_id, day)).fetchone() is not None


def vetting_queue(conn, who) -> list[dict]:
    aa.require(_coord(who), "Only the mentoring coordinator can see this")
    aa.ensure(conn)
    return aa.dicts(conn.execute(
        "SELECT v.*, a.first_name, a.last_name, a.degree_earned, a.current_employer FROM "
        "mentor_vetting v JOIN alumni a ON a.alumni_id = v.alumni_id ORDER BY v.status, "
        "v.offered_at"))


def propose_match(conn, who, mentor_id, student_id, focus_area="", match_score=None) -> int:
    aa.require(_coord(who), "Only the mentoring coordinator can match mentors")
    if not vetted(conn, mentor_id):
        raise ValueError("That mentor is not vetted (or their approval has expired)")
    if not conn.execute("SELECT 1 FROM students WHERE student_id = ? AND COALESCE(status, "
                        "'Active') = 'Active'", (student_id,)).fetchone():
        raise ValueError("Mentees must be current students")
    if conn.execute("SELECT 1 FROM mentorships WHERE mentor_id = ? AND mentee_id = ? AND status "
                    "IN ('proposed', 'active', 'paused')", (mentor_id, student_id)).fetchone():
        raise ValueError("That pair is already matched")
    if conn.execute("SELECT COUNT(*) FROM mentorships WHERE mentor_id = ? AND status IN "
                    "('proposed', 'active', 'paused')", (mentor_id,)).fetchone()[0] >= MAX_MENTEES:
        raise ValueError(f"That mentor already has {MAX_MENTEES} mentees")
    mid = conn.execute("INSERT INTO mentorships (mentor_id, mentee_id, status, focus_area, "
                       "matched_by, match_score) VALUES (?, ?, 'proposed', ?, ?, ?)",
                       (mentor_id, student_id, focus_area or None, who.username,
                        match_score)).lastrowid
    aa.audit(conn, who, "mentorship", mid, "proposed", {"mentor": mentor_id,
                                                         "student": student_id})
    aa.notify(conn, [student_id], "A mentor has been suggested for you",
              "An alumni mentor has been suggested. Accept or decline in the alumni portal; "
              "nothing is shared with them until you accept.")
    return int(mid)


def _words(*values) -> set[str]:
    """Meaningful lower-case words (and comma-separated phrases) of ``values``."""
    found: set[str] = set()
    for value in values:
        text = str(value or "").lower()
        found |= {p.strip() for p in text.split(",") if " " in p.strip()}
        found |= {w for w in re.findall(r"[a-z][a-z+#]{2,}", text) if w not in _COMMON}
    return found


def _student_profile(conn, student_id) -> dict:
    row = aa.one(conn, "SELECT * FROM students WHERE student_id = ? AND COALESCE(status, 'Active') "
                    "= 'Active'", (student_id,))
    if not row:
        raise ValueError("Mentees must be current students")
    course = aa.one(conn, "SELECT COALESCE(course_name, name) AS name, department FROM courses "
                       "WHERE course_code = ? OR code = ? LIMIT 1",
                 (row.get("course"), row.get("course"))) if aa.has_table(conn, "courses") else None
    row["course_name"] = (course or {}).get("name") or row.get("course")
    row["course_department"] = (course or {}).get("department")
    return row


def _mentor_pool(conn, student_id) -> list[dict]:
    """Vetted, contactable mentors with room for another mentee who have not
    already been matched with (or declined by) this student."""
    rows = aa.dicts(conn.execute(
        "SELECT a.*, v.focus_areas, (SELECT COUNT(*) FROM mentorships m WHERE m.mentor_id = "
        "a.alumni_id AND m.status IN ('proposed', 'active', 'paused')) AS load FROM alumni a "
        "JOIN mentor_vetting v ON v.alumni_id = a.alumni_id WHERE v.status = 'approved' AND "
        "v.training_completed = 1 AND v.expires_on >= ? AND a.deceased_at IS NULL AND "
        "a.anonymised_at IS NULL AND NOT EXISTS (SELECT 1 FROM mentorships m WHERE "
        "m.mentor_id = a.alumni_id AND m.mentee_id = ? AND m.status IN ('proposed', 'active', "
        "'paused', 'declined'))", (aa.today(), student_id)))
    return [r for r in rows if aa.contactable(r) and r["load"] < MAX_MENTEES]


def _score(student, mentor, focus) -> tuple[int, list[str]]:
    score, why = 0, []
    subject = _words(student.get("course_name"), student.get("major"), student.get("program"),
                     student.get("department"), student.get("course_department"))
    field = _words(mentor.get("degree_earned"), mentor.get("industry"), mentor.get("job_title"))
    dept = str(student.get("department") or student.get("course_department") or "").lower()
    if dept and dept == str(mentor.get("industry") or "").lower():
        score += 30
        why.append(f"works in {mentor['industry']}, the student's field")
    else:
        shared = sorted(subject & field)
        if shared:
            score += min(30, 10 * len(shared))
            why.append("subject in common: " + ", ".join(shared[:4]))
    wanted = _words(focus) or _words(student.get("major"), student.get("course_name"))
    offered = _words(mentor.get("focus_areas"), mentor.get("skills"))
    shared = sorted(wanted & offered)
    if shared:
        score += min(30, 10 * len(shared))
        why.append("can help with " + ", ".join(shared[:4]))
    year = mentor.get("graduation_year")
    try:
        gap = date.today().year - int(year)
    except (TypeError, ValueError):
        gap = None
    if gap is not None and 3 <= gap <= 15:
        score += 20
        why.append(f"graduated {gap} years ago")
    elif gap is not None and gap > 15:
        score += 10
        why.append(f"{gap} years' experience since graduating")
    city = str(mentor.get("city") or "").strip().lower()
    if city and city in str(student.get("address") or "").lower():
        score += 10
        why.append(f"also in {mentor['city']}")
    if not mentor["load"]:
        score += 5
        why.append("has no mentees at the moment")
    return score, why


def suggest_matches(conn, who, student_id, focus="", limit=5) -> list[dict]:
    """The best vetted mentors for ``student_id``, highest score first, each
    with the reasons behind its score. Nothing is proposed or stored."""
    aa.require(_coord(who), "Only the mentoring coordinator can suggest matches")
    aa.ensure(conn)
    student = _student_profile(conn, str(student_id).strip())
    found = []
    for mentor in _mentor_pool(conn, student["student_id"]):
        score, why = _score(student, mentor, focus)
        if score <= 5:          # free capacity alone is not a match
            continue
        found.append({"mentor_id": mentor["alumni_id"],
                      "name": " ".join(p for p in (mentor.get("first_name"),
                                                   mentor.get("last_name")) if p),
                      "industry": mentor.get("industry"), "job_title": mentor.get("job_title"),
                      "focus_areas": mentor.get("focus_areas"), "mentees": mentor["load"],
                      "score": score, "quality": ("Excellent" if score >= 50 else
                                                  "Good" if score >= 30 else "Fair"),
                      "reasons": why})
    found.sort(key=lambda m: (-m["score"], m["mentees"], m["name"]))
    return found[:max(1, int(limit))]


def mentorship(conn, mentorship_id) -> dict:
    aa.ensure(conn)
    row = aa.one(conn, "SELECT * FROM mentorships WHERE mentorship_id = ?", (mentorship_id,))
    if not row:
        raise ValueError("No such mentorship")
    return row


def _party(who, row) -> bool:
    return who is not None and (who.alumni_id == row["mentor_id"] or
                                (who.student_id and who.student_id == row["mentee_id"] and
                                 who.is_student))


def respond(conn, who, mentorship_id, accept) -> None:
    row = mentorship(conn, mentorship_id)
    aa.require(who is not None and who.is_student and who.student_id == row["mentee_id"],
               "Only the student can accept or decline")
    if row["status"] != "proposed":
        raise ValueError("This match is not waiting for an answer")
    if accept:
        conn.execute("UPDATE mentorships SET status = 'active', student_consent_at = ?, "
                     "start_date = ? WHERE mentorship_id = ?", (aa.now(), aa.today(),
                                                                mentorship_id))
        aa.notify(conn, [row["mentor_id"]], "Your mentoring match started",
                  f"Student {row['mentee_id']} accepted you as their mentor.")
    else:
        conn.execute("UPDATE mentorships SET status = 'declined' WHERE mentorship_id = ?",
                     (mentorship_id,))
    aa.audit(conn, who, "mentorship", mentorship_id, "accepted" if accept else "declined")


def end_match(conn, who, mentorship_id, reason) -> None:
    row = mentorship(conn, mentorship_id)
    aa.require(_party(who, row) or _coord(who), "Only the mentor, student or coordinator can "
                                                "end this")
    if row["status"] not in ("proposed", "active", "paused"):
        raise ValueError("This match has already ended")
    conn.execute("UPDATE mentorships SET status = 'ended', end_date = ?, ended_by = ?, "
                 "ended_reason = ? WHERE mentorship_id = ?",
                 (aa.today(), who.username, aa.text(reason, "Reason", True), mentorship_id))
    aa.audit(conn, who, "mentorship", mentorship_id, "ended", {"reason": reason})


def raise_concern(conn, who, mentorship_id, description) -> int:
    row = mentorship(conn, mentorship_id)
    aa.require(_party(who, row) or _coord(who), "Only someone in this match can raise a concern")
    cid = conn.execute("INSERT INTO mentoring_concerns (mentorship_id, raised_by, description) "
                       "VALUES (?, ?, ?)", (mentorship_id, who.username,
                                            aa.text(description, "What happened", True))
                       ).lastrowid
    if row["status"] == "active":
        conn.execute("UPDATE mentorships SET status = 'paused' WHERE mentorship_id = ?",
                     (mentorship_id,))
    aa.audit(conn, who, "mentorship", mentorship_id, "concern_raised", {"concern": cid})
    aa.notify(conn, aa.holders(conn, "mentoring_coordinator"), "Mentoring concern raised",
              f"A concern was raised about mentoring match {mentorship_id}. The match is paused.")
    return int(cid)


def handle_concern(conn, who, concern_id, action, outcome) -> None:
    aa.require(_coord(who), "Only the mentoring coordinator can handle concerns")
    concern = aa.one(conn, "SELECT * FROM mentoring_concerns WHERE concern_id = ?",
                     (concern_id,))
    if not concern or concern["status"] != "open":
        raise ValueError("No such open concern")
    if action not in ("close", "escalate"):
        raise ValueError("Close or escalate the concern")
    outcome = aa.text(outcome, "Outcome", True)
    conn.execute("UPDATE mentoring_concerns SET status = ?, handled_by = ?, handled_at = ?, "
                 "outcome = ? WHERE concern_id = ?",
                 ("closed" if action == "close" else "escalated", who.username, aa.now(),
                  outcome, concern_id))
    mid = concern["mentorship_id"]
    if action == "escalate":
        row = mentorship(conn, mid)
        conn.execute("UPDATE mentorships SET status = 'ended', end_date = ?, ended_by = ?, "
                     "ended_reason = 'concern escalated' WHERE mentorship_id = ?",
                     (aa.today(), who.username, mid))
        conn.execute("UPDATE mentor_vetting SET status = 'rejected', notes = TRIM(COALESCE(notes, "
                     "'') || ' Suspended after concern ' || ?) WHERE alumni_id = ?",
                     (concern_id, row["mentor_id"]))
        aa.notify(conn, aa.holders(conn, "alumni_office"), "Mentoring concern escalated",
                  f"Concern {concern_id} on match {mid} was escalated to safeguarding: "
                  f"{outcome}")
    elif not conn.execute("SELECT 1 FROM mentoring_concerns WHERE mentorship_id = ? AND status "
                          "= 'open'", (mid,)).fetchone():
        conn.execute("UPDATE mentorships SET status = 'active' WHERE mentorship_id = ? AND "
                     "status = 'paused'", (mid,))
    aa.audit(conn, who, "mentorship", mid, f"concern_{action}", {"concern": concern_id})


def mentorships(conn, who, status=None) -> list[dict]:
    aa.ensure(conn)
    where, params = [], []
    if not _coord(who):
        aa.require(who is not None, "Sign in first")
        # A mentor sees a match only once the student has accepted it.
        where.append("((m.mentor_id = ? AND m.student_consent_at IS NOT NULL) OR m.mentee_id = ?)")
        params += [who.alumni_id or "", who.student_id if who.is_student else ""]
    if status:
        where.append("m.status = ?")
        params.append(status)
    return aa.dicts(conn.execute(
        "SELECT m.*, a.first_name || ' ' || a.last_name AS mentor_name, (SELECT COUNT(*) FROM "
        "mentoring_concerns c WHERE c.mentorship_id = m.mentorship_id AND c.status = 'open') AS "
        "open_concerns FROM mentorships m LEFT JOIN alumni a ON a.alumni_id = m.mentor_id" +
        (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY m.mentorship_id DESC",
        params))


def concerns(conn, who, status="open") -> list[dict]:
    aa.require(_coord(who), "Only the mentoring coordinator can see concerns")
    return aa.dicts(conn.execute("SELECT * FROM mentoring_concerns" +
                                 (" WHERE status = ?" if status else "") +
                                 " ORDER BY raised_at", (status,) if status else ()))


# ── moderation ──────────────────────────────────────────────────────────


def _mod(who):
    return who is not None and who.is_moderator


def report(conn, who, kind, item_id, reason) -> int:
    aa.ensure(conn)
    aa.require(who is not None, "Sign in first")
    if kind not in REPORT_KINDS:
        raise ValueError("Unknown kind of content")
    table, pk = REPORT_KINDS[kind]
    # db-audit: ignore[DBW001] - table/pk come from the literal map above
    if not conn.execute(f"SELECT 1 FROM {table} WHERE {pk} = ?", (item_id,)).fetchone():
        raise ValueError("No such item")
    rid = conn.execute("INSERT INTO alumni_content_reports (kind, item_id, reported_by, reason) "
                       "VALUES (?, ?, ?, ?)", (kind, item_id, who.username,
                                               aa.text(reason, "Reason", True))).lastrowid
    aa.notify(conn, aa.holders(conn, "moderator"), "Alumni content reported",
              f"A {kind.replace('_', ' ')} was reported: {reason}")
    return int(rid)


def reports(conn, who, status="open") -> list[dict]:
    aa.require(_mod(who), "Only moderators can see reports")
    aa.ensure(conn)
    return aa.dicts(conn.execute("SELECT * FROM alumni_content_reports" +
                                 (" WHERE status = ?" if status else "") +
                                 " ORDER BY reported_at", (status,) if status else ()))


def hide(conn, who, kind, item_id, reason) -> None:
    aa.require(_mod(who), "Only moderators can hide content")
    table, pk = REPORT_KINDS[kind]
    reason = aa.text(reason, "Reason", True)
    if kind == "story":
        sql, params = f"UPDATE {table} SET status = 'withdrawn' WHERE {pk} = ?", (item_id,)
    elif kind == "photo":
        sql, params = f"UPDATE {table} SET hidden_at = ?, is_featured = 0 WHERE {pk} = ?", (
            aa.now(), item_id)
    else:
        sql, params = f"UPDATE {table} SET hidden_at = ?, hidden_reason = ? WHERE {pk} = ?", (
            aa.now(), reason, item_id)
    # db-audit: ignore[DBW001] - table/pk come from the literal map above
    if not conn.execute(sql, params).rowcount:
        raise ValueError("No such item")
    aa.audit(conn, who, kind, item_id, "hidden", {"reason": reason})


def resolve(conn, who, report_id, uphold, note="") -> None:
    aa.require(_mod(who), "Only moderators can resolve reports")
    row = aa.one(conn, "SELECT * FROM alumni_content_reports WHERE report_id = ?", (report_id,))
    if not row or row["status"] != "open":
        raise ValueError("No such open report")
    if uphold:
        hide(conn, who, row["kind"], row["item_id"], note or row["reason"])
    conn.execute("UPDATE alumni_content_reports SET status = ?, handled_by = ?, handled_at = ? "
                 "WHERE report_id = ?", ("upheld" if uphold else "dismissed", who.username,
                                         aa.now(), report_id))


def submit_story(conn, who, title, content, category="", consent=False) -> int:
    _alumnus(who)
    if not consent:
        raise ValueError("Confirm that we may publish your story and name")
    sid = conn.execute("INSERT INTO alumni_stories (alumni_id, title, content, category, "
                       "story_type, status, consent_at) VALUES (?, ?, ?, ?, 'alumni', "
                       "'pending', ?)", (who.alumni_id, aa.text(title, "Title", True),
                                         aa.text(content, "Story", True), category or None,
                                         aa.now())).lastrowid
    aa.notify(conn, aa.holders(conn, "moderator"), "Alumni story to review",
              f"{who.alumni_id} submitted a story: {title}")
    return int(sid)


def review_story(conn, who, story_id, approve) -> None:
    aa.require(_mod(who), "Only moderators can publish stories")
    row = aa.one(conn, "SELECT * FROM alumni_stories WHERE story_id = ?", (story_id,))
    if not row or (row.get("status") or "published") != "pending":
        raise ValueError("No such story waiting for review")
    if approve and not row.get("consent_at"):
        raise ValueError("The author has not consented to publication")
    conn.execute("UPDATE alumni_stories SET status = ?, approved_by = ?, publish_date = ? WHERE "
                 "story_id = ?", ("published" if approve else "withdrawn", who.username,
                                  aa.today() if approve else None, story_id))
    aa.audit(conn, who, "story", story_id, "published" if approve else "rejected")


def withdraw_story(conn, who, story_id) -> None:
    row = aa.one(conn, "SELECT * FROM alumni_stories WHERE story_id = ?", (story_id,))
    if not row:
        raise ValueError("No such story")
    aa.require_self_or(who, row["alumni_id"], _mod)
    conn.execute("UPDATE alumni_stories SET status = 'withdrawn', is_featured = 0 WHERE story_id "
                 "= ?", (story_id,))


def stories(conn, who=None, status="published") -> list[dict]:
    aa.ensure(conn)
    if status != "published":
        aa.require(_mod(who), "Only moderators can see unpublished stories")
    return aa.dicts(conn.execute("SELECT s.*, a.first_name || ' ' || a.last_name AS author FROM "
                                 "alumni_stories s LEFT JOIN alumni a ON a.alumni_id = "
                                 "s.alumni_id WHERE COALESCE(s.status, 'published') = ? ORDER BY "
                                 "s.story_id DESC", (status,)))


def confirm_photo_consent(conn, who, photo_id) -> None:
    aa.require(_mod(who), "Only moderators can confirm photo consent")
    if not conn.execute("UPDATE photo_gallery SET consent_confirmed = 1 WHERE photo_id = ?",
                        (photo_id,)).rowcount:
        raise ValueError("No such photo")
    aa.audit(conn, who, "photo", photo_id, "consent_confirmed")


def feature_photo(conn, who, photo_id, featured=True) -> None:
    aa.require(_mod(who), "Only moderators can feature photos")
    row = aa.one(conn, "SELECT * FROM photo_gallery WHERE photo_id = ?", (photo_id,))
    if not row:
        raise ValueError("No such photo")
    if featured and not row.get("consent_confirmed"):
        raise ValueError("Confirm the people in the photo consented before featuring it")
    if featured and row.get("hidden_at"):
        raise ValueError("That photo is hidden")
    conn.execute("UPDATE photo_gallery SET is_featured = ? WHERE photo_id = ?",
                 (int(bool(featured)), photo_id))


def photo_dir():
    from education_system import paths
    return paths.UNIVERSITY_DATA_DIR / "alumni_photos"


def delete_photo(conn, who, photo_id, reason) -> str | None:
    """Delete a photo permanently: its record, any reports about it, and
    the stored file (only ever a file inside the alumni photo folder). The
    audit keeps who, when, why and the caption, not the image. Returns the
    file removed, if any. The file goes last, once the record is gone."""
    aa.require(_mod(who), "Only moderators can delete photos")
    reason = aa.text(reason, "Reason", True)
    row = aa.one(conn, "SELECT * FROM photo_gallery WHERE photo_id = ?", (photo_id,))
    if not row:
        raise ValueError("No such photo")
    conn.execute("UPDATE alumni_content_reports SET status = 'upheld', handled_by = ?, "
                 "handled_at = ? WHERE kind = 'photo' AND item_id = ? AND status = 'open'",
                 (who.username, aa.now(), photo_id))
    conn.execute("DELETE FROM photo_gallery WHERE photo_id = ?", (photo_id,))
    aa.audit(conn, who, "photo", photo_id, "deleted",
             {"reason": reason, "caption": row.get("caption"),
              "uploaded_by": row.get("uploaded_by"), "uploaded": row.get("upload_date")})
    return remove_photo_file(row.get("photo_path"))


def remove_photo_file(stored) -> str | None:
    """Delete a stored photo file, only ever one inside the alumni photo
    folder. Returns the file removed, if any."""
    from pathlib import Path
    stored = str(stored or "")
    if not stored:
        return None
    folder = photo_dir().resolve()
    path = Path(stored)
    path = (path if path.is_absolute() else folder / path).resolve()
    if folder not in path.parents or not path.is_file():
        return None
    path.unlink()
    return str(path)


# ── forum ───────────────────────────────────────────────────────────────

FORUM_CATEGORIES = ("General Discussion", "Career Advice", "Networking", "Industry News",
                    "Class Updates", "Events", "Mentorship")


def _forum_member(who):
    aa.require(who is not None and (who.alumni_id is not None or who.is_staff_role),
               "Only alumni can use the forum")


def forum_posts(conn, who, search=None, category=None, mine=False) -> list[dict]:
    """Visible posts (moderators also see hidden ones, marked)."""
    aa.ensure(conn)
    _forum_member(who)
    where, params = [], []
    if not _mod(who):
        where.append("p.hidden_at IS NULL")
    if category and category != "All":
        where.append("p.category = ?")
        params.append(category)
    if mine:
        where.append("p.author_id = ?")
        params.append(who.alumni_id or who.username)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(COALESCE(p.title, '')) LIKE ? OR LOWER(COALESCE(p.content, '')) "
                     "LIKE ?)")
        params += [like, like]
    return aa.dicts(conn.execute(
        "SELECT p.*, COALESCE(TRIM(a.first_name || ' ' || a.last_name), p.author_id) AS "
        "author_name, (SELECT COUNT(*) FROM forum_replies r WHERE r.post_id = p.post_id AND "
        "r.hidden_at IS NULL) AS replies FROM alumni_forum p LEFT JOIN alumni a ON a.alumni_id "
        "= p.author_id" + (" WHERE " + " AND ".join(where) if where else "") +
        " ORDER BY p.is_pinned DESC, COALESCE(p.last_updated, p.post_date) DESC", params))


def forum_post(conn, who, post_id) -> dict:
    _forum_member(who)
    row = aa.one(conn, "SELECT p.*, COALESCE(TRIM(a.first_name || ' ' || a.last_name), "
                       "p.author_id) AS author_name FROM alumni_forum p LEFT JOIN alumni a ON "
                       "a.alumni_id = p.author_id WHERE p.post_id = ?", (post_id,))
    if not row or (row.get("hidden_at") and not _mod(who)):
        raise ValueError("No such post")
    conn.execute("UPDATE alumni_forum SET view_count = COALESCE(view_count, 0) + 1 WHERE post_id "
                 "= ?", (post_id,))
    row["replies"] = aa.dicts(conn.execute(
        "SELECT r.*, COALESCE(TRIM(a.first_name || ' ' || a.last_name), r.author_name, "
        "r.author_id) AS author FROM forum_replies r LEFT JOIN alumni a ON a.alumni_id = "
        "r.author_id WHERE r.post_id = ?" + ("" if _mod(who) else " AND r.hidden_at IS NULL") +
        " ORDER BY r.reply_id", (post_id,)))
    return row


def post(conn, who, title, content, category="General Discussion") -> int:
    aa.ensure(conn)
    _forum_member(who)
    if category not in FORUM_CATEGORIES:
        raise ValueError("Pick a category")
    pid = conn.execute("INSERT INTO alumni_forum (author_id, title, content, category, post_date, "
                       "last_updated, reply_count, view_count) VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
                       (who.alumni_id or who.username, aa.text(title, "Title", True),
                        aa.text(content, "Post", True), category, aa.now(), aa.now())).lastrowid
    return int(pid)


def reply(conn, who, post_id, content) -> int:
    row = forum_post(conn, who, post_id)
    if row.get("hidden_at"):
        raise ValueError("That post is hidden")
    rid = conn.execute("INSERT INTO forum_replies (post_id, author_id, author_name, content, "
                       "reply_date, created_date) VALUES (?, ?, ?, ?, ?, ?)",
                       (post_id, who.alumni_id or who.username, who.username,
                        aa.text(content, "Reply", True), aa.now(), aa.now())).lastrowid
    conn.execute("UPDATE alumni_forum SET reply_count = (SELECT COUNT(*) FROM forum_replies WHERE "
                 "post_id = ? AND hidden_at IS NULL), last_updated = ? WHERE post_id = ?",
                 (post_id, aa.now(), post_id))
    return int(rid)


def photos(conn, who, include_hidden=False) -> list[dict]:
    aa.ensure(conn)
    if include_hidden:
        aa.require(_mod(who), "Only moderators can see hidden photos")
    return aa.dicts(conn.execute("SELECT * FROM photo_gallery" +
                                 ("" if include_hidden else " WHERE hidden_at IS NULL") +
                                 " ORDER BY upload_date DESC"))
