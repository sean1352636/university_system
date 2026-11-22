"""The alumnus's own menus, and a current student's mentoring."""

from __future__ import annotations

import json

from education_system.systems.university.application.alumni import community as acm
from education_system.systems.university.application.alumni import records as ar
from education_system.systems.university.domains.learners.interfaces.cli.alumni import (
    _io,
    giving,
    office,
)


def privacy(ctx) -> None:
    me = ctx.who.alumni_id
    current = _io.read(ar.directory_settings, me) or {}
    print("  Nothing is shown in the directory unless you choose it. Your date of birth and")
    print("  home address are never shown.")
    settings = {}
    labels = {"searchable": "List me in the alumni directory",
              "show_contact_info": "Show my e-mail, phone and LinkedIn",
              "show_employment": "Show my employer and job",
              "show_education": "Show my degree",
              "networking_available": "Open to networking requests",
              "mentor_available": "Open to mentoring"}
    for key, label in labels.items():
        now = "yes" if current.get(key) else "no"
        settings[key] = _io.ask_choice(label, ["yes", "no"], now) == "yes"
    if _io.run(ar.save_directory_settings, ctx.who, me, settings):
        print("\n✅ Saved.")


def my_consent(ctx) -> None:
    row = _io.read(ar.profile, ctx.who, ctx.who.alumni_id) or {}
    state = {None: "not asked yet", 0: "no", 1: "yes"}.get(row.get("marketing_consent"), "no")
    print(f"  Newsletters and appeals: currently {state}.")
    agree = _io.ask_choice("May we send you newsletters and appeals", ["yes", "no"])
    if agree and _io.run(ar.set_consent, ctx.who, ctx.who.alumni_id, agree == "yes"):
        print("\n✅ Saved. You can change this at any time.")


def my_data(ctx) -> None:
    me = ctx.who.alumni_id
    choice = _io.ask_choice("Download everything we hold, or ask us to erase your record",
                            ["download", "erase"])
    if choice == "download":
        data = _io.run(ar.export, ctx.who, me)
        path = _io.ask("Save to file", f"my_alumni_data_{me}.json")
        if data and _io.write_file(path, json.dumps(data, indent=2, default=str)):
            print(f"\n✅ Saved to {path}.")
    elif choice == "erase" and _io.confirm("Ask the alumni office to erase your record?"):
        if _io.run(ar.request_erasure, ctx.who, me, _io.ask("Anything we should know")):
            print("\n✅ Request sent to the alumni office.")


def my_chapters(ctx) -> str:
    def mine():
        rows = _io.read(acm.my_chapters, ctx.who)
        if rows is not None:
            _io.table(rows, [("chapter_id", "Id", 5), ("chapter_name", "Chapter", 24),
                             ("location", "Location", 18), ("role", "Role", 8)])

    def join():
        if _io.run(acm.join, ctx.who, _io.ask_int("Chapter id")):
            print("\n✅ Joined.")

    def leave():
        if _io.run(acm.leave, ctx.who, _io.ask_int("Chapter id")):
            print("\n✅ Left.")

    return _io.menu("My chapters", [("All chapters", lambda: office_chapters(ctx)),
                                    ("My chapters", mine), ("Join a chapter", join),
                                    ("Leave a chapter", leave),
                                    ("Members (chapter leaders)",
                                     lambda: _members(ctx))])


def office_chapters(ctx) -> None:
    from education_system.systems.university.domains.learners.interfaces.cli.alumni import (
        community,
    )
    community.list_chapters(ctx)


def _members(ctx) -> None:
    from education_system.systems.university.domains.learners.interfaces.cli.alumni import (
        community,
    )
    community.chapter_members(ctx)


def mentoring_as_mentor(ctx) -> str:
    def offer():
        if _io.run(acm.offer_to_mentor, ctx.who, _io.ask("What can you help students with")):
            print("\n✅ Thank you. The mentoring coordinator will vet you (safeguarding "
                  "training is required) before any match.")

    def matches():
        rows = _io.read(acm.mentorships, ctx.who)
        if rows is not None:
            _io.table(rows, [("mentorship_id", "Id", 5), ("mentee_id", "Student", 12),
                             ("status", "Status", 10), ("focus_area", "Focus", 20),
                             ("start_date", "Started", 12)])

    return _io.menu("Mentoring", [("Offer to mentor students", offer), ("My matches", matches),
                                  ("End a match", lambda: _end(ctx)),
                                  ("Raise a concern", lambda: _concern(ctx))])


def _end(ctx) -> None:
    if _io.run(acm.end_match, ctx.who, _io.ask_int("Match id"), _io.ask("Reason")):
        print("\n✅ Ended.")


def _concern(ctx) -> None:
    if _io.run(acm.raise_concern, ctx.who, _io.ask_int("Match id"),
               _io.ask("What happened")):
        print("\n✅ Raised. The match is paused while the coordinator looks into it.")


def submit_story(ctx) -> None:
    title = _io.ask("Title")
    content = _io.ask("Your story")
    consent = _io.confirm("May we publish your story with your name?")
    if _io.run(acm.submit_story, ctx.who, title, content, _io.ask("Category"), consent):
        print("\n✅ Submitted; a moderator will review it before it is published.")


def report_content(ctx) -> None:
    kind = _io.ask_choice("What are you reporting", list(acm.REPORT_KINDS))
    if kind and _io.run(acm.report, ctx.who, kind, _io.ask_int("Its id"), _io.ask("Why")):
        print("\n✅ Reported to the moderators.")


def alumnus_menu(ctx) -> str:
    me = ctx.who.alumni_id
    return _io.menu("My alumni account", [
        ("My profile", lambda: office.view(ctx, me)),
        ("Edit my profile", lambda: office.edit_profile(ctx, me)),
        ("Directory privacy", lambda: privacy(ctx)),
        ("Newsletter consent", lambda: my_consent(ctx)),
        ("My data (download / erase)", lambda: my_data(ctx)),
        ("My giving", lambda: giving.my_giving(ctx)),
        ("My chapters", lambda: my_chapters(ctx)),
        ("Mentoring", lambda: mentoring_as_mentor(ctx)),
        ("Submit a story", lambda: submit_story(ctx)),
        ("Report a post, story or photo", lambda: report_content(ctx)),
    ])


def student_menu(ctx) -> str:
    def matches():
        rows = _io.read(acm.mentorships, ctx.who)
        if rows is not None:
            _io.table(rows, [("mentorship_id", "Id", 5), ("mentor_name", "Mentor", 22),
                             ("status", "Status", 10), ("focus_area", "Focus", 20)])

    def respond():
        mid = _io.ask_int("Match id")
        answer = _io.ask_choice("Accept this mentor", ["yes", "no"])
        if answer and _io.run(acm.respond, ctx.who, mid, answer == "yes"):
            print("\n✅ " + ("Accepted. Your mentor has been told." if answer == "yes"
                            else "Declined."))

    return _io.menu("My mentoring", [("My mentor matches", matches),
                                     ("Accept / decline a match", respond),
                                     ("End a match", lambda: _end(ctx)),
                                     ("Raise a concern", lambda: _concern(ctx))])
