"""Alumni screens for mentoring, moderation, the forum and stories, on the
rules in ``university/application/alumni/community``.

Mentoring: the coordinator vets mentors, gets suggested mentors for a
student (scored, with reasons), proposes matches and handles concerns; an alumnus offers to mentor and sees matches only once the
student accepts; a student accepts or declines and can raise a concern.
Moderation: reports, stories waiting for publication, forum posts and
photos (consent before featuring; permanent deletion with a reason).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.ui import record_screens as common
from education_system.systems.university.domains.learners.interfaces.gui.alumni import (
    alumni_office_community as base,
)

Field = common.Field


def _acm():
    return base._rules("alumni_community")


def _report(app, who, kind, item_id, after=None):
    reason = common.ask_text(app.root, "Report content", "What is wrong with it?")
    if reason and base.write(app, _acm().report, who, kind, int(item_id), reason):
        common.info(app.root, "Thank you. A moderator will look at it.")
        if after:
            after()


def _text_window(app, title, sections, buttons=()):
    win = tk.Toplevel(app.root)
    win.title(title)
    win.geometry("760x560")
    b = base.bar(win)
    detail = common.Detail(win)
    detail.pack(fill="both", expand=True)
    detail.show(title, sections)
    for text, cmd in buttons:
        base.button(b, text, lambda c=cmd: c(win))
    base.button(b, "Close", win.destroy)
    return win


# ── mentoring (coordinator) ─────────────────────────────────────────────


def _match_columns():
    return [("mentor", "Mentor", 160), ("student", "Student", 100), ("status", "Status", 90),
            ("focus", "Focus", 180), ("start", "Started", 90), ("concerns", "Open concerns",
                                                                 100)]


def _match_values(r):
    return (r.get("mentor_name") or r["mentor_id"], r["mentee_id"], r["status"],
            r.get("focus_area"), r.get("start_date") or "", r.get("open_concerns") or 0)


def _vetting_tab(app, nb, who):
    acm = _acm()
    t = base.tab(nb, "Vetting")
    b = base.bar(t)
    tree = common.make_tree(t, [("id", "Alumnus", 90), ("name", "Name", 170),
                                ("focus", "Can help with", 220), ("status", "Status", 80),
                                ("training", "Training", 70), ("expires", "Expires", 90)])

    def refresh():
        rows = common.call(app.root, acm.vetting_queue, who) or []
        common.fill(tree, rows, lambda r: r["alumni_id"],
                    lambda r: (r["alumni_id"], f"{r.get('first_name') or ''} "
                                               f"{r.get('last_name') or ''}".strip(),
                               r.get("focus_areas"), r["status"],
                               "done" if r["training_completed"] else "no",
                               r.get("expires_on") or ""))

    def approve():
        aid = base.need(app, tree, "an alumnus")
        if aid is None:
            return
        ans = common.ask(app.root, f"Approve mentor {aid}", [
            Field("training", "Safeguarding training completed", "check"),
            Field("expires_on", "Approval expires", "date", hint="blank = three years"),
            Field("notes", "Notes", "multiline")])
        if ans:
            base.write(app, acm.vet, who, aid, True, training_completed=ans["training"],
                       expires_on=ans["expires_on"] or None, notes=ans["notes"], then=refresh)

    def reject():
        aid = base.need(app, tree, "an alumnus")
        if aid:
            notes = common.ask_text(app.root, "Reject mentor", "Reason")
            if notes:
                base.write(app, acm.vet, who, aid, False, notes=notes, then=refresh)

    for text, cmd in (("Approve…", approve), ("Reject…", reject), ("Refresh", refresh)):
        base.button(b, text, cmd)
    refresh()
    return refresh


def _matches_tab(app, nb, who):
    acm = _acm()
    t = base.tab(nb, "Matches")
    top = ttk.Frame(t)
    top.pack(side="top", fill="x")
    ttk.Label(top, text="Status").pack(side="left")
    status = tk.StringVar(value="")
    box = ttk.Combobox(top, textvariable=status, width=14, state="readonly",
                       values=("", "proposed", "active", "paused", "ended", "declined"))
    box.pack(side="left", padx=4)
    b = base.bar(t)
    tree = common.make_tree(t, _match_columns())

    def refresh():
        rows = common.call(app.root, acm.mentorships, who, status.get() or None) or []
        common.fill(tree, rows, lambda r: r["mentorship_id"], _match_values)

    def propose():
        mentors = [(r["alumni_id"], f"{r.get('first_name') or ''} {r.get('last_name') or ''} "
                                    f"({r['alumni_id']})")
                   for r in common.call(app.root, acm.vetting_queue, who) or []
                   if r["status"] == "approved"]
        if not mentors:
            common.info(app.root, "There are no approved mentors yet.")
            return
        ans = common.ask(app.root, "Propose a match", [
            Field("mentor", "Mentor", "combo", mentors, required=True),
            Field("student", "Student id", required=True), Field("focus", "Focus")])
        if ans:
            base.write(app, acm.propose_match, who, ans["mentor"], ans["student"].strip(),
                       ans["focus"], then=refresh)

    def suggest():
        ans = common.ask(app.root, "Suggest mentors", [
            Field("student", "Student id", required=True),
            Field("focus", "Wants help with", hint="blank = their subject")])
        if not ans:
            return
        student, focus = ans["student"].strip(), ans["focus"].strip()
        found = common.call(app.root, acm.suggest_matches, who, student, focus, 8)
        if found is None:
            return
        if not found:
            common.info(app.root, "No vetted mentor with room for another mentee fits this "
                                  "student.")
            return
        _suggestions_window(app, who, student, focus, found, refresh)

    def end():
        mid = base.need(app, tree, "a match")
        if mid:
            reason = common.ask_text(app.root, "End match", "Reason")
            if reason:
                base.write(app, acm.end_match, who, int(mid), reason, then=refresh)

    def concern():
        mid = base.need(app, tree, "a match")
        if mid:
            text = common.ask_text(app.root, "Raise a concern", "What happened")
            if text:
                base.write(app, acm.raise_concern, who, int(mid), text, then=refresh)

    box.bind("<<ComboboxSelected>>", lambda _e: refresh())
    for text, cmd in (("Suggest mentors…", suggest), ("Propose match…", propose),
                      ("End match…", end),
                      ("Raise concern…", concern), ("Refresh", refresh)):
        base.button(b, text, cmd)
    refresh()
    return refresh


def _suggestions_window(app, who, student, focus, found, after):
    """Ranked mentors for one student, the reasons for the selected one, and
    a button to propose the match."""
    acm = _acm()
    win = tk.Toplevel(app.root)
    win.title(f"Suggested mentors for {student}")
    win.geometry("820x480")
    b = base.bar(win)
    reasons = tk.Text(win, height=6, wrap="word", font=("Segoe UI", 10))
    reasons.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
    tree = common.make_tree(win, [("name", "Mentor", 170), ("score", "Score", 60),
                                  ("quality", "Match", 80), ("industry", "Industry", 140),
                                  ("job", "Job", 140), ("load", "Mentees now", 90)])
    by_id = {str(m["mentor_id"]): m for m in found}
    common.fill(tree, found, lambda m: m["mentor_id"],
                lambda m: (m["name"], m["score"], m["quality"], m.get("industry") or "",
                           m.get("job_title") or "", m["mentees"]))

    def show(_e=None):
        sel = tree.selection()
        reasons.configure(state="normal")
        reasons.delete("1.0", "end")
        if sel:
            m = by_id[str(sel[0])]
            reasons.insert("1.0", "Why: " + "; ".join(m["reasons"]) +
                           (f"\nCan help with: {m['focus_areas']}" if m.get("focus_areas")
                            else ""))
        reasons.configure(state="disabled")

    def propose():
        sel = tree.selection()
        if not sel:
            common.info(win, "Choose a mentor first.")
            return
        m = by_id[str(sel[0])]
        if base.write(app, acm.propose_match, who, m["mentor_id"], student, focus or None,
                      m["score"]) is not None:
            common.info(win, "Proposed. The student decides whether to accept.")
            win.destroy()
            after()

    tree.bind("<<TreeviewSelect>>", show)
    base.button(b, "Propose this match", propose)
    base.button(b, "Close", win.destroy)


def _concerns_tab(app, nb, who, after):
    acm = _acm()
    t = base.tab(nb, "Concerns")
    top = ttk.Frame(t)
    top.pack(side="top", fill="x")
    show_all = tk.BooleanVar()
    b = base.bar(t)
    tree = common.make_tree(t, [("match", "Match", 70), ("by", "Raised by", 110),
                                ("at", "Raised", 140), ("what", "What happened", 320),
                                ("status", "Status", 80), ("outcome", "Outcome", 200)])

    def refresh():
        rows = common.call(app.root, acm.concerns, who, None if show_all.get() else "open") or []
        common.fill(tree, rows, lambda r: r["concern_id"],
                    lambda r: (r["mentorship_id"], r["raised_by"], r["raised_at"],
                               r["description"], r["status"], r.get("outcome") or ""))

    def handle(action):
        cid = base.need(app, tree, "a concern")
        if cid is None:
            return
        outcome = common.ask_text(app.root, f"{action.capitalize()} concern", "Outcome")
        if outcome:
            base.write(app, acm.handle_concern, who, int(cid), action, outcome, then=refresh)
            after()

    ttk.Checkbutton(top, text="Show closed too", variable=show_all,
                    command=refresh).pack(side="left")
    base.button(b, "Close…", lambda: handle("close"))
    base.button(b, "Escalate to safeguarding…", lambda: handle("escalate"))
    base.button(b, "Refresh", refresh)
    refresh()


def show_mentoring(app):
    who = base.who_of(app)
    frame = base.page(app, "Mentoring", "Vet mentors, match them with students and handle "
                                         "concerns.")
    if who is None or not who.is_coordinator:
        base.refuse(frame, "Mentoring is run by the mentoring coordinator. Alumni and students "
                           "use My mentoring.")
        return
    nb = base.notebook(frame)
    _vetting_tab(app, nb, who)
    matches_refresh = _matches_tab(app, nb, who)
    _concerns_tab(app, nb, who, matches_refresh)


def show_my_mentoring(app):
    acm = _acm()
    who = base.who_of(app)
    frame = base.page(app, "My mentoring")
    if who is None or not (who.alumni_id or who.is_student):
        base.refuse(frame, "Mentoring is for alumni mentors and current students.")
        return
    student = who.is_student
    ttk.Label(frame, text="A mentor suggested for you sees nothing about you until you accept."
              if student else "Mentors are vetted and trained before they are matched. You see "
                              "a match once the student accepts it.",
              wraplength=1000).pack(anchor="w")
    b = base.bar(frame)
    tree = common.make_tree(frame, _match_columns())

    def refresh():
        rows = common.call(app.root, acm.mentorships, who) or []
        common.fill(tree, rows, lambda r: r["mentorship_id"], _match_values)

    def respond(accept):
        mid = base.need(app, tree, "a match")
        if mid:
            base.write(app, acm.respond, who, int(mid), accept, then=refresh)

    def end():
        mid = base.need(app, tree, "a match")
        if mid:
            reason = common.ask_text(app.root, "End mentoring", "Reason")
            if reason:
                base.write(app, acm.end_match, who, int(mid), reason, then=refresh)

    def concern():
        mid = base.need(app, tree, "a match")
        if mid:
            text = common.ask_text(app.root, "Raise a concern",
                                   "What happened (the match pauses while it is looked at)")
            if text:
                base.write(app, acm.raise_concern, who, int(mid), text, then=refresh)
                common.info(app.root, "The mentoring coordinator has been told.")

    def offer():
        areas = common.ask_text(app.root, "Offer to mentor", "What could you help students "
                                                             "with?")
        if areas and base.write(app, acm.offer_to_mentor, who, areas):
            common.info(app.root, "Thank you. The mentoring coordinator will contact you about "
                                  "vetting and safeguarding training.")

    if student:
        base.button(b, "Accept", lambda: respond(True))
        base.button(b, "Decline", lambda: respond(False))
    else:
        base.button(b, "Offer to mentor…", offer)
    base.button(b, "End…", end)
    base.button(b, "Raise concern…", concern)
    base.button(b, "Refresh", refresh)
    refresh()


# ── moderation ──────────────────────────────────────────────────────────


def _reports_tab(app, nb, who):
    acm = _acm()
    t = base.tab(nb, "Reports")
    b = base.bar(t)
    tree = common.make_tree(t, [("kind", "Kind", 100), ("item", "Item", 60),
                                ("by", "Reported by", 120), ("at", "When", 140),
                                ("reason", "Reason", 360)])
    rows_by_id = {}

    def refresh():
        rows = common.call(app.root, acm.reports, who) or []
        rows_by_id.clear()
        rows_by_id.update({str(r["report_id"]): r for r in rows})
        common.fill(tree, rows, lambda r: r["report_id"],
                    lambda r: (r["kind"].replace("_", " "), r["item_id"], r["reported_by"],
                               r["reported_at"], r["reason"]))

    def view():
        rid = base.need(app, tree, "a report")
        if rid is None:
            return
        row = rows_by_id[rid]
        if row["kind"] == "forum_post":
            post = common.call(app.root, acm.forum_post, who, row["item_id"], write=True)
            if post:
                _text_window(app, post["title"], [("By", [("Author", post["author_name"])]),
                                                  ("Post", post["content"] or "")])
        else:
            common.info(app.root, f"{row['kind'].replace('_', ' ').capitalize()} "
                                  f"#{row['item_id']}: {row['reason']}")

    def resolve(uphold):
        rid = base.need(app, tree, "a report")
        if rid is None:
            return
        note = common.ask_text(app.root, "Uphold report" if uphold else "Dismiss report",
                               "Note", required=uphold)
        if note is not None:
            base.write(app, acm.resolve, who, int(rid), uphold, note, then=refresh)

    for text, cmd in (("View", view), ("Uphold (hide it)…", lambda: resolve(True)),
                      ("Dismiss…", lambda: resolve(False)), ("Refresh", refresh)):
        base.button(b, text, cmd)
    refresh()


def _stories_tab(app, nb, who):
    acm = _acm()
    t = base.tab(nb, "Stories waiting")
    b = base.bar(t)
    tree = common.make_tree(t, [("title", "Title", 260), ("author", "Author", 160),
                                ("category", "Category", 140), ("consent", "Consent", 140)])
    rows_by_id = {}

    def refresh():
        rows = common.call(app.root, acm.stories, who, "pending") or []
        rows_by_id.clear()
        rows_by_id.update({str(r["story_id"]): r for r in rows})
        common.fill(tree, rows, lambda r: r["story_id"],
                    lambda r: (r["title"], r.get("author"), r.get("category"),
                               r.get("consent_at") or "none"))

    def read():
        sid = base.need(app, tree, "a story")
        if sid:
            r = rows_by_id[sid]
            _text_window(app, r["title"], [("By", [("Author", r.get("author"))]),
                                           ("Story", r.get("content") or "")])

    def review(approve):
        sid = base.need(app, tree, "a story")
        if sid:
            base.write(app, acm.review_story, who, int(sid), approve, then=refresh)

    for text, cmd in (("Read", read), ("Publish", lambda: review(True)),
                      ("Reject", lambda: review(False)), ("Refresh", refresh)):
        base.button(b, text, cmd)
    refresh()


def _forum_mod_tab(app, nb, who):
    acm = _acm()
    t = base.tab(nb, "Forum")
    b = base.bar(t)
    tree = common.make_tree(t, [("title", "Title", 280), ("author", "Author", 150),
                                ("category", "Category", 130), ("hidden", "Hidden", 140)])

    def refresh():
        rows = common.call(app.root, acm.forum_posts, who) or []
        common.fill(tree, rows, lambda r: r["post_id"],
                    lambda r: (r["title"], r["author_name"], r.get("category"),
                               r.get("hidden_at") or ""))

    def hide():
        pid = base.need(app, tree, "a post")
        if pid:
            reason = common.ask_text(app.root, "Hide post", "Reason")
            if reason:
                base.write(app, acm.hide, who, "forum_post", int(pid), reason, then=refresh)

    base.button(b, "Hide…", hide)
    base.button(b, "Refresh", refresh)
    refresh()


def _photos_tab(app, nb, who):
    acm = _acm()
    t = base.tab(nb, "Photos")
    b = base.bar(t)
    tree = common.make_tree(t, [("caption", "Caption", 260), ("by", "Uploaded by", 120),
                                ("date", "Uploaded", 140), ("consent", "Consent", 80),
                                ("featured", "Featured", 80), ("hidden", "Hidden", 130)])

    def refresh():
        rows = common.call(app.root, acm.photos, who, True) or []
        common.fill(tree, rows, lambda r: r["photo_id"],
                    lambda r: (r.get("caption"), r.get("uploaded_by"), r.get("upload_date"),
                               "yes" if r.get("consent_confirmed") else "no",
                               "yes" if r.get("is_featured") else "no", r.get("hidden_at") or ""))

    def act(fn, *args):
        pid = base.need(app, tree, "a photo")
        if pid:
            base.write(app, fn, who, int(pid), *args, then=refresh)

    def hide():
        pid = base.need(app, tree, "a photo")
        if pid:
            reason = common.ask_text(app.root, "Hide photo", "Reason")
            if reason:
                base.write(app, acm.hide, who, "photo", int(pid), reason, then=refresh)

    def delete():
        pid = base.need(app, tree, "a photo")
        if not pid:
            return
        reason = common.ask_text(app.root, "Delete photo permanently",
                                 "Reason (kept in the audit; the photo and its file are "
                                 "removed)")
        if reason and common.confirm(app.root, "Delete this photo and its file permanently? "
                                               "This cannot be undone."):
            base.write(app, acm.delete_photo, who, int(pid), reason, then=refresh)

    for text, cmd in (("Consent confirmed", lambda: act(acm.confirm_photo_consent)),
                      ("Feature", lambda: act(acm.feature_photo, True)),
                      ("Unfeature", lambda: act(acm.feature_photo, False)),
                      ("Hide…", hide), ("Delete permanently…", delete), ("Refresh", refresh)):
        base.button(b, text, cmd)
    refresh()


def show_moderation(app):
    who = base.who_of(app)
    frame = base.page(app, "Moderation", "Reported content, stories waiting for publication, "
                                         "the forum and photos.")
    if who is None or not who.is_moderator:
        base.refuse(frame, "Moderation is for alumni moderators and the alumni office.")
        return
    nb = base.notebook(frame)
    _reports_tab(app, nb, who)
    _stories_tab(app, nb, who)
    _forum_mod_tab(app, nb, who)
    _photos_tab(app, nb, who)


# ── the forum and stories (alumni) ──────────────────────────────────────


def _open_post(app, who, post_id, after):
    acm = _acm()
    post = common.call(app.root, acm.forum_post, who, int(post_id), write=True)
    if not post:
        return
    replies = [f"{r['author']} ({r.get('reply_date') or r.get('created_date') or ''}): "
               f"{r['content']}" for r in post["replies"]]

    def do_reply(win):
        text = common.ask_text(app.root, "Reply", "Your reply")
        if text and base.write(app, acm.reply, who, int(post_id), text):
            win.destroy()
            after()
            _open_post(app, who, post_id, after)

    def do_report(win):
        _report(app, who, "forum_post", post_id)

    def report_reply(win):
        if not post["replies"]:
            return
        ans = common.ask(app.root, "Report a reply", [Field("reply", "Reply", "combo", [
            (r["reply_id"], f"{r['author']}: {r['content'][:60]}") for r in post["replies"]],
                                                           required=True)])
        if ans:
            _report(app, who, "forum_reply", ans["reply"])

    _text_window(app, post["title"],
                 [("", [("Author", post["author_name"]), ("Category", post.get("category")),
                        ("Posted", post.get("post_date"))]),
                  ("Post", post.get("content") or ""),
                  (f"Replies ({len(replies)})", replies or ["No replies yet."])],
                 buttons=(("Reply…", do_reply), ("Report post…", do_report),
                          ("Report a reply…", report_reply)))


def show_forum(app, mine=False):
    acm = _acm()
    who = base.who_of(app)
    frame = base.page(app, "Alumni forum")
    if who is None or not (who.alumni_id or who.is_staff_role):
        base.refuse(frame, "The forum is for alumni.")
        return
    top = ttk.Frame(frame)
    top.pack(side="top", fill="x", pady=4)
    ttk.Label(top, text="Search").pack(side="left")
    search = tk.StringVar()
    ttk.Entry(top, textvariable=search, width=24).pack(side="left", padx=4)
    category = tk.StringVar(value="All")
    ttk.Combobox(top, textvariable=category, values=("All", *acm.FORUM_CATEGORIES),
                 state="readonly", width=20).pack(side="left", padx=4)
    mine = tk.BooleanVar(value=mine)
    ttk.Checkbutton(top, text="My posts", variable=mine).pack(side="left", padx=4)
    b = base.bar(frame)
    tree = common.make_tree(frame, [("title", "Title", 320), ("author", "Author", 160),
                                    ("category", "Category", 140), ("replies", "Replies", 70),
                                    ("views", "Views", 60), ("updated", "Last activity", 140)])

    def refresh():
        rows = common.call(app.root, acm.forum_posts, who, search=search.get().strip() or None,
                           category=category.get(), mine=mine.get()) or []
        common.fill(tree, rows, lambda r: r["post_id"],
                    lambda r: (r["title"], r["author_name"], r.get("category"), r["replies"],
                               r.get("view_count") or 0, r.get("last_updated") or ""))

    def read():
        pid = base.need(app, tree, "a post")
        if pid:
            _open_post(app, who, pid, refresh)

    def new():
        ans = common.ask(app.root, "New forum post", [
            Field("category", "Category", "combo", list(acm.FORUM_CATEGORIES)),
            Field("title", "Title", required=True), Field("content", "Post", "multiline",
                                                           required=True)],
                         {"category": "General Discussion"})
        if ans:
            base.write(app, acm.post, who, ans["title"], ans["content"],
                       ans["category"] or "General Discussion", then=refresh)

    def report():
        pid = base.need(app, tree, "a post")
        if pid:
            _report(app, who, "forum_post", pid)

    ttk.Button(top, text="Search", command=refresh).pack(side="left", padx=4)
    tree.bind("<Double-1>", lambda _e: read())
    for text, cmd in (("Read", read), ("New post…", new), ("Report…", report),
                      ("Refresh", refresh)):
        base.button(b, text, cmd)
    refresh()


def show_stories(app, submit_first=False):
    acm = _acm()
    who = base.who_of(app)
    frame = base.page(app, "Alumni stories")
    if who is None:
        base.refuse(frame, "Sign in to read alumni stories.")
        return
    b = base.bar(frame)
    tree = common.make_tree(frame, [("title", "Title", 320), ("author", "Author", 180),
                                    ("category", "Category", 160), ("published", "Published",
                                                                    100)])
    rows_by_id = {}

    def refresh():
        rows = common.call(app.root, acm.stories, who) or []
        rows_by_id.clear()
        rows_by_id.update({str(r["story_id"]): r for r in rows})
        common.fill(tree, rows, lambda r: r["story_id"],
                    lambda r: (r["title"], r.get("author"), r.get("category"),
                               r.get("publish_date") or ""))

    def read():
        sid = base.need(app, tree, "a story")
        if sid:
            r = rows_by_id[sid]
            _text_window(app, r["title"], [("By", [("Author", r.get("author"))]),
                                           ("Story", r.get("content") or "")],
                         buttons=(("Report…", lambda w: _report(app, who, "story", sid)),))

    def submit():
        ans = common.ask(app.root, "Share your story", [
            Field("title", "Title", required=True),
            Field("category", "Category", "combo", ["Career Achievement", "Community Service",
                                                    "Entrepreneurship", "Research & Innovation",
                                                    "Personal Journey"]),
            Field("content", "Your story", "multiline", required=True),
            Field("consent", "I agree to the university publishing this story with my name",
                  "check")])
        if ans and base.write(app, acm.submit_story, who, ans["title"], ans["content"],
                              ans["category"], ans["consent"]):
            common.info(app.root, "Thank you. A moderator will review your story before it is "
                                  "published.")

    def withdraw():
        sid = base.need(app, tree, "a story")
        if sid and common.confirm(app.root, "Withdraw this story?"):
            base.write(app, acm.withdraw_story, who, int(sid), then=refresh)

    for text, cmd in (("Read", read), ("Share your story…", submit), ("Withdraw mine", withdraw),
                      ("Report…", lambda: base.need(app, tree, "a story") and
                       _report(app, who, "story", base.sel(tree))), ("Refresh", refresh)):
        base.button(b, text, cmd)
    tree.bind("<Double-1>", lambda _e: read())
    refresh()
    if submit_first and who.alumni_id:
        submit()



def photo_browser(app, parent):
    """Visible photos with a Report button, built into ``parent``."""
    acm = _acm()
    who = base.who_of(app)
    b = base.bar(parent)
    tree = common.make_tree(parent, [("caption", "Caption", 300), ("by", "Uploaded by", 140),
                                     ("date", "Uploaded", 150), ("featured", "Featured", 80)])

    def refresh():
        rows = common.call(app.root, acm.photos, who) or []
        common.fill(tree, rows, lambda r: r["photo_id"],
                    lambda r: (r.get("caption"), r.get("uploaded_by"), r.get("upload_date"),
                               "yes" if r.get("is_featured") else ""))

    def report():
        pid = base.need(app, tree, "a photo")
        if pid:
            _report(app, who, "photo", pid)

    base.button(b, "Report…", report)
    base.button(b, "Refresh", refresh)
    refresh()
    return refresh


__all__ = ["show_mentoring", "show_my_mentoring", "show_moderation", "show_forum",
           "photo_browser", "show_stories"]
