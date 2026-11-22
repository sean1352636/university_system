"""Community menus: chapters, mentoring (coordinator), moderation, and the
classic community features the new rules do not cover yet."""

from __future__ import annotations

from education_system.systems.university.application.alumni import community as acm
from education_system.systems.university.domains.learners.interfaces.cli.alumni import _io

_MATCH_COLS = [("mentorship_id", "Id", 5), ("mentor_id", "Mentor", 12),
               ("mentor_name", "Mentor name", 20), ("mentee_id", "Student", 12),
               ("status", "Status", 10), ("focus_area", "Focus", 18),
               ("open_concerns", "Concerns", 9)]


# ── chapters ────────────────────────────────────────────────────────────


def list_chapters(ctx) -> None:
    rows = _io.read(acm.chapters)
    if rows is not None:
        _io.table(rows, [("chapter_id", "Id", 5), ("chapter_name", "Chapter", 24),
                         ("location", "Location", 18), ("members", "Members", 8),
                         ("coordinator_id", "Leader", 12)])


def chapter_members(ctx) -> None:
    rows = _io.read(acm.members, ctx.who, _io.ask_int("Chapter id"))
    if rows is not None:
        _io.table(rows, [("alumni_id", "Alumni", 12), ("first_name", "First", 14),
                         ("last_name", "Last", 16), ("role", "Role", 8),
                         ("join_date", "Joined", 12), ("email", "E-mail (if shown)", 26)])


def chapters_menu(ctx) -> str:
    def save():
        cid = _io.ask_int("Chapter id to edit (blank = new)")
        data = {k: v for k, v in (("chapter_name", _io.ask("Name")),
                                  ("location", _io.ask("Location")),
                                  ("description", _io.ask("Description")),
                                  ("contact_email", _io.ask("Contact e-mail"))) if v}
        result = _io.run(acm.save_chapter, ctx.who, data, cid)
        if result:
            print(f"\n✅ Chapter {result} saved.")

    def close():
        if _io.run(acm.close_chapter, ctx.who, _io.ask_int("Chapter id")):
            print("\n✅ Closed.")

    def leader():
        if _io.run(acm.set_leader, ctx.who, _io.ask_int("Chapter id"),
                   _io.ask("Alumni id of the new leader")):
            print("\n✅ Leader set.")

    def remove_member():
        if _io.run(acm.leave, ctx.who, _io.ask_int("Chapter id"), _io.ask("Alumni id")):
            print("\n✅ Removed.")

    return _io.menu("Chapters", [("List chapters", lambda: list_chapters(ctx)),
                                 ("Members of a chapter", lambda: chapter_members(ctx)),
                                 ("New / edit chapter", save), ("Close a chapter", close),
                                 ("Appoint a leader", leader),
                                 ("Remove a member", remove_member)])


# ── mentoring (coordinator) ─────────────────────────────────────────────


def list_matches(ctx, status=None) -> None:
    rows = _io.read(acm.mentorships, ctx.who, status)
    if rows is not None:
        _io.table(rows, _MATCH_COLS)


def mentoring_menu(ctx) -> str:
    def queue():
        rows = _io.read(acm.vetting_queue, ctx.who)
        if rows is not None:
            _io.table(rows, [("alumni_id", "Alumni", 12), ("first_name", "First", 12),
                             ("last_name", "Last", 14), ("focus_areas", "Can help with", 22),
                             ("status", "Status", 9), ("training_completed", "Trained", 8),
                             ("expires_on", "Expires", 12)])

    def vet():
        alumni_id = _io.ask("Alumni id")
        approve = _io.ask_choice("Decision", ["approve", "reject"]) == "approve"
        result = _io.run(acm.vet, ctx.who, alumni_id, approve,
                         training_completed=approve and _io.confirm(
                             "Safeguarding training completed?"),
                         expires_on=(_io.ask("Approval expires (blank = 3 years)") or None)
                         if approve else None,
                         notes=_io.ask("Notes"))
        if result:
            print("\n✅ Saved.")

    def propose():
        result = _io.run(acm.propose_match, ctx.who, _io.ask("Mentor alumni id"),
                         _io.ask("Student id"), _io.ask("Focus area"))
        if result:
            print(f"\n✅ Match {result} proposed; the student decides whether to accept.")

    def suggest():
        student = _io.ask("Student id")
        if not student:
            return
        focus = _io.ask("What the student wants help with (blank = their subject)")
        found = _io.read(acm.suggest_matches, ctx.who, student, focus, 5)
        if not found:
            if found is not None:
                print("\n  No vetted mentor with room for another mentee fits this student.")
            return
        for n, m in enumerate(found, 1):
            print(f"\n  {n}. {m['name']} ({m['mentor_id']}) — score {m['score']} "
                  f"({m['quality']}), {m['mentees']} current mentee(s)")
            for reason in m["reasons"]:
                print(f"       • {reason}")
        pick = _io.ask_int("\nPropose which number (blank = none)")
        if pick and 1 <= pick <= len(found):
            m = found[pick - 1]
            result = _io.run(acm.propose_match, ctx.who, m["mentor_id"], student,
                             focus or None, m["score"])
            if result:
                print(f"\n✅ Match {result} proposed; the student decides whether to accept.")

    def show_concerns():
        rows = _io.read(acm.concerns, ctx.who, _io.ask_choice(
            "Status", ["open", "escalated", "closed"], "open") or "open")
        if rows is not None:
            _io.table(rows, [("concern_id", "Id", 5), ("mentorship_id", "Match", 6),
                             ("raised_by", "Raised by", 14), ("raised_at", "When", 20),
                             ("description", "What happened", 30), ("status", "Status", 10)])

    def handle():
        cid = _io.ask_int("Concern id")
        action = _io.ask_choice("Action", ["close", "escalate"])
        if action and _io.run(acm.handle_concern, ctx.who, cid, action, _io.ask("Outcome")):
            print("\n✅ Done." + (" The match is ended and the mentor suspended."
                                 if action == "escalate" else ""))

    def end():
        if _io.run(acm.end_match, ctx.who, _io.ask_int("Match id"), _io.ask("Reason")):
            print("\n✅ Ended.")

    return _io.menu("Mentoring", [("Mentor vetting queue", queue), ("Vet a mentor", vet),
                                  ("All matches", lambda: list_matches(ctx)),
                                  ("Suggest mentors for a student", suggest),
                                  ("Propose a match", propose), ("Concerns", show_concerns),
                                  ("Handle a concern", handle), ("End a match", end)])


# ── moderation ──────────────────────────────────────────────────────────


def moderation_menu(ctx) -> str:
    def show_reports():
        rows = _io.read(acm.reports, ctx.who, "open")
        if rows is not None:
            _io.table(rows, [("report_id", "Id", 5), ("kind", "Kind", 12), ("item_id", "Item", 6),
                             ("reported_by", "By", 14), ("reason", "Reason", 30),
                             ("reported_at", "When", 20)])

    def resolve():
        rid = _io.ask_int("Report id")
        uphold = _io.ask_choice("Decision", ["uphold", "dismiss"]) == "uphold"
        if _io.run(acm.resolve, ctx.who, rid, uphold, _io.ask("Note") if uphold else ""):
            print("\n✅ " + ("Upheld; the item is hidden." if uphold else "Dismissed."))

    def pending():
        rows = _io.read(acm.stories, ctx.who, "pending")
        if rows is not None:
            _io.table(rows, [("story_id", "Id", 5), ("author", "Author", 20),
                             ("title", "Title", 30), ("consent_at", "Consent", 20)])

    def review():
        sid = _io.ask_int("Story id")
        approve = _io.ask_choice("Decision", ["publish", "reject"]) == "publish"
        if _io.run(acm.review_story, ctx.who, sid, approve):
            print("\n✅ Done.")

    def hide():
        kind = _io.ask_choice("Kind", list(acm.REPORT_KINDS))
        if kind and _io.run(acm.hide, ctx.who, kind, _io.ask_int("Item id"), _io.ask("Reason")):
            print("\n✅ Hidden.")

    def photo():
        pid = _io.ask_int("Photo id")
        action = _io.ask_choice("Action", ["consent", "feature", "unfeature"])
        if action == "consent":
            ok = _io.run(acm.confirm_photo_consent, ctx.who, pid)
        elif action:
            ok = _io.run(acm.feature_photo, ctx.who, pid, action == "feature")
        else:
            return
        if ok:
            print("\n✅ Done.")

    def delete_photo():
        pid = _io.ask_int("Photo id")
        if not pid:
            return
        reason = _io.ask("Reason (kept in the audit)")
        if reason and _io.confirm(f"Delete photo {pid} and its file permanently? This cannot be "
                                  "undone"):
            if _io.run(acm.delete_photo, ctx.who, pid, reason):
                print("\n✅ Deleted.")

    return _io.menu("Moderation", [("Open reports", show_reports), ("Resolve a report", resolve),
                                   ("Stories waiting for review", pending),
                                   ("Publish / reject a story", review),
                                   ("Hide a post, reply, story or photo", hide),
                                   ("Photo consent / featuring", photo),
                                   ("Delete a photo permanently", delete_photo)])


# ── classic features (not yet on the new rules) ─────────────────────────


def classic_menu(ctx) -> str:
    """Events, reunions, jobs, careers, business directory, engagement,
    forum and photo gallery still run on the original interactive code."""
    from education_system.systems.university.domains.learners.domain import alumni as old
    old.set_auth(ctx.auth)
    items = [("Events", old.view_events), ("Register for an event", old.register_for_event),
             ("Class reunions", old.manage_class_reunions), ("Job board", old.view_job_board),
             ("Networking requests", old.view_connection_requests),
             ("Engagement leaderboard", old.view_engagement_leaderboard),
             ("My badges", old.view_my_badges),
             ("Recommendations", old.generate_engagement_recommendations),
             ("Forum", old.manage_alumni_forum), ("Photo gallery", old.manage_photo_gallery)]
    if ctx.who.is_staff_role or ctx.who.is_alumnus:
        items += [("Post a job", old.post_job_opportunity),
                  ("Book career counselling", old.schedule_career_counseling),
                  ("Business directory", old.manage_business_directory)]
    if ctx.who.is_office:
        items += [("Create an event", old.create_enhanced_event),
                  ("Event check-in", old.event_check_in_system),
                  ("Engagement report", old.generate_alumni_report)]
    return _io.menu("Community (classic)", items)
