"""Career Services CLI screens.

The menu used to print "Feature available via Career Services managers"
for all seven options and hand the user an import statement. These are
the screens that were missing: each one drives the managers in
``career_services_core`` — the same code the GUI and the API use — so
what a student does here is visible everywhere else.

Owner ids follow the Student Union convention (``identity.current_student_id``):
the real ``users.student_id`` when the account has one, otherwise a stable
``user:<username>`` stand-in, so an account without a student record can
still use the screens without writing rows nobody can read back.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    sqlite3, get_connection,
)
from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError, ValidationError,
)
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.identity import (
    current_student_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small shared prompts
# ---------------------------------------------------------------------------

def _ask(prompt: str, *, required: bool = False, default: str = "") -> str | None:
    """Ask for a value. Returns None when the user cancels with a blank."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        if default:
            return default
        if not required:
            return None
        print("  This one is required — enter a value or press Ctrl-C to go back.")


def _ask_date(prompt: str, *, required: bool = True) -> str | None:
    """Ask for a YYYY-MM-DD date, re-prompting until it parses."""
    while True:
        value = input(prompt).strip()
        if not value:
            return None if not required else None
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            print("  Invalid date format. Please use YYYY-MM-DD.")


def _ask_int(prompt: str, *, default: int | None = None,
             minimum: int = 1) -> int | None:
    while True:
        value = input(prompt).strip()
        if not value:
            return default
        if value.isdigit() and int(value) >= minimum:
            return int(value)
        print(f"  Please enter a whole number of {minimum} or more.")


def _pick(rows, prompt: str, render):
    """Print a numbered list and return the row the user picks."""
    if not rows:
        return None
    for index, row in enumerate(rows, 1):
        print(f"  {index}. {render(row)}")
    raw = input(f"\n{prompt} (1-{len(rows)}, blank to cancel): ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(rows)):
        print("  Cancelled.")
        return None
    return rows[int(raw) - 1]


def _resolve_student_id(auth):
    """The id career records are owned by, or None if nobody is signed in."""
    try:
        with get_connection() as conn:
            return current_student_id(conn.cursor(), auth)
    except sqlite3.Error as exc:
        logger.warning("could not resolve the current student id: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 1. Browse job postings
# ---------------------------------------------------------------------------

def browse_job_postings(student_id):
    """List open vacancies, show one in full, and apply."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        JobManager, ResumeManager,
    )

    filters = {}
    job_type = input("Filter by job type (blank for all): ").strip()
    if job_type:
        filters["job_type"] = job_type
    location = input("Filter by location (blank for all): ").strip()
    if location:
        filters["location"] = location

    jobs = JobManager.get_active_jobs(filters or None)
    if not jobs:
        print("\nNo job postings match that search.")
        return

    print(f"\n{len(jobs)} vacancy(ies):\n")
    chosen = _pick(
        jobs, "Select a job to view",
        lambda j: (f"{j.get('job_title', 'Untitled')} — {j.get('company_name', 'Unknown')} "
                   f"({j.get('job_type') or 'unspecified'}, {j.get('location') or 'location TBC'})"),
    )
    if not chosen:
        return

    print("\n" + "=" * 50)
    print(f"  {chosen.get('job_title', 'Untitled')}")
    print("=" * 50)
    print(f"Company:   {chosen.get('company_name') or 'Unknown'}")
    print(f"Type:      {chosen.get('job_type') or 'unspecified'}")
    print(f"Location:  {chosen.get('location') or 'TBC'}")
    print(f"Salary:    {chosen.get('salary_range') or 'not stated'}")
    deadline = chosen.get('expiry_date') or chosen.get('application_deadline')
    print(f"Deadline:  {deadline or 'none given'}")
    if chosen.get('job_description') or chosen.get('description'):
        print(f"\n{chosen.get('job_description') or chosen.get('description')}")
    if chosen.get('requirements'):
        print(f"\nRequirements:\n{chosen['requirements']}")

    job_id = chosen['job_id']
    if JobManager.has_applied(job_id, student_id):
        print("\nYou have already applied for this job — see Job Application Tracking.")
        return

    if input("\nApply for this job? (y/n): ").strip().lower() != 'y':
        return

    resume_id = None
    resumes = ResumeManager.get_student_resumes(student_id)
    if resumes:
        print("\nAttach a resume:")
        picked = _pick(resumes, "Select a resume",
                       lambda r: (f"{r.get('resume_name')}"
                                  f"{' (primary)' if r.get('is_primary') else ''}"))
        if picked:
            resume_id = picked['resume_id']
    else:
        print("\nYou have no resume on file — you can add one from 'Submit Resume'.")

    cover_letter = input("Cover letter (optional): ").strip()

    try:
        application_id = JobManager.apply_for_job(job_id, student_id, resume_id,
                                                  cover_letter)
    except (DatabaseError, ValidationError) as exc:
        print(f"\nCould not submit the application: {exc}")
        return

    print(f"\n✓ Applied for '{chosen.get('job_title')}' "
          f"(application {application_id}).")
    print("Track its progress under Job Application Tracking.")


# ---------------------------------------------------------------------------
# 2. Submit resume
# ---------------------------------------------------------------------------

def submit_resume(student_id):
    """Add a resume and list the ones already on file."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        ResumeManager,
    )

    resumes = ResumeManager.get_student_resumes(student_id)
    if resumes:
        print("\nResumes on file:")
        for r in resumes:
            marker = " (primary)" if r.get('is_primary') else ""
            print(f"  [{r['resume_id']}] {r.get('resume_name')}{marker} — "
                  f"{r.get('file_url') or 'no file'}")
    else:
        print("\nYou have no resumes on file yet.")

    if input("\nAdd a resume now? (y/n): ").strip().lower() != 'y':
        return

    resume_name = _ask("Resume name (blank to cancel): ")
    if not resume_name:
        print("Cancelled.")
        return

    file_url = _ask("File path or URL (blank to cancel): ")
    if not file_url:
        print("Cancelled.")
        return

    template_used = input("Template used (optional): ").strip()
    is_primary = input("Make this your primary resume? (y/n): ").strip().lower() == 'y'

    try:
        resume_id = ResumeManager.upload_resume(student_id, resume_name, file_url,
                                                template_used, is_primary)
    except (DatabaseError, ValidationError) as exc:
        print(f"\nCould not save the resume: {exc}")
        return

    print(f"\n✓ Resume '{resume_name}' saved (ID {resume_id})"
          f"{' and set as your primary' if is_primary else ''}.")


# ---------------------------------------------------------------------------
# 3. Schedule mock interview
# ---------------------------------------------------------------------------

def schedule_mock_interview(student_id):
    """Book a practice interview against one of your applications."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        InterviewManager, JobManager,
    )

    applications = JobManager.get_student_applications(student_id)
    if not applications:
        print("\nYou have no applications yet — a mock interview is booked "
              "against one, so apply for a job first.")
        return

    print("\nYour applications:")
    chosen = _pick(
        applications, "Select the application to practise for",
        lambda a: (f"[{a['application_id']}] {a.get('job_title')} at "
                   f"{a.get('company_name')} — {a.get('status')}"),
    )
    if not chosen:
        return

    interview_date = _ask_date("Date (YYYY-MM-DD, blank to cancel): ")
    if not interview_date:
        print("Cancelled.")
        return

    interview_time = _ask("Time (HH:MM, blank to cancel): ")
    if not interview_time:
        print("Cancelled.")
        return

    duration = _ask_int("Duration in minutes [60]: ", default=60, minimum=5)
    location = input("Location (blank if online): ").strip()
    meeting_link = input("Meeting link (blank if in person): ").strip()
    interviewer = input("Interviewer name (optional): ").strip()

    try:
        interview_id = InterviewManager.schedule_interview(
            chosen['application_id'], 'mock', interview_date, interview_time,
            duration, location, meeting_link, interviewer,
        )
    except (DatabaseError, ValidationError) as exc:
        print(f"\nCould not schedule the interview: {exc}")
        return

    print(f"\n✓ Mock interview booked for {interview_date} at {interview_time} "
          f"(ID {interview_id}).")
    print("A confirmation email has been sent if an address is on file.")


# ---------------------------------------------------------------------------
# 4. Career events
# ---------------------------------------------------------------------------

def view_career_events(student_id):
    """List career events and register for one."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        CareerEventManager,
    )

    mine = CareerEventManager.get_registrations_for(student_id)
    if mine:
        print("\nYou are registered for:")
        for r in mine:
            when = (r.get('start_datetime') or 'date TBC')[:16]
            print(f"  [{r['event_id']}] {r.get('title')} — {when} "
                  f"({r.get('location') or 'location TBC'})")

    events = CareerEventManager.get_upcoming_events()
    if not events:
        print("\nThere are no upcoming career events.")
        return

    print("\nUpcoming career events:")
    chosen = _pick(
        events, "Select an event to register for",
        lambda e: (f"{e.get('title')} — {(e.get('start_datetime') or 'date TBC')[:16]} "
                   f"({e.get('event_type') or 'event'}, "
                   f"{e.get('location') or 'location TBC'})"),
    )
    if not chosen:
        return

    if CareerEventManager.is_registered(chosen['event_id'], student_id):
        print(f"\nYou are already registered for '{chosen.get('title')}'.")
        return

    if chosen.get('description'):
        print(f"\n{chosen['description']}")

    guests = _ask_int("Number of guests [0]: ", default=0, minimum=0)
    if input(f"Register for '{chosen.get('title')}'? (y/n): ").strip().lower() != 'y':
        return

    try:
        registration_id = CareerEventManager.register_for_event(
            chosen['event_id'], student_id, guests or 0)
    except (DatabaseError, ValidationError) as exc:
        print(f"\nCould not register: {exc}")
        return

    print(f"\n✓ Registered for '{chosen.get('title')}' "
          f"(registration {registration_id}).")


# ---------------------------------------------------------------------------
# 5. Alumni mentorship
# ---------------------------------------------------------------------------

def alumni_mentorship_program(student_id):
    """Find a mentor, see your matches, or offer to mentor."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        MentorshipManager,
    )

    while True:
        print("\nAlumni Mentorship")
        print("1. Browse available mentors")
        print("2. Request a mentor")
        print("3. My mentorships")
        print("4. Register as a mentor")
        print("5. Return to career services")

        choice = input("Choose an option: ").strip()

        if choice == '1':
            industry = input("Filter by industry (blank for all): ").strip()
            mentors = MentorshipManager.get_available_mentors(industry or None)
            if not mentors:
                print("\nNo mentors are currently taking on mentees.")
                continue
            print(f"\n{len(mentors)} mentor(s) with capacity:")
            for m in mentors:
                places = (m.get('max_mentees') or 3) - (m.get('current_mentees') or 0)
                print(f"  [{m['mentor_id']}] {m.get('job_title')} at {m.get('company')} "
                      f"— {m.get('industry') or 'general'} ({places} place(s) left)")
                if m.get('expertise_areas'):
                    print(f"       Expertise: {m['expertise_areas']}")

        elif choice == '2':
            mentors = MentorshipManager.get_available_mentors()
            if not mentors:
                print("\nNo mentors are currently taking on mentees.")
                continue
            print("\nMentors with capacity:")
            chosen = _pick(
                mentors, "Select a mentor to request",
                lambda m: (f"{m.get('job_title')} at {m.get('company')} — "
                           f"{m.get('industry') or 'general'}"),
            )
            if not chosen:
                continue

            frequency = input("Preferred meeting frequency [monthly]: ").strip() or "monthly"
            notes = input("What would you like help with? (optional): ").strip()

            try:
                match_id = MentorshipManager.create_mentorship_match(
                    chosen['mentor_id'], student_id, frequency, notes)
            except (DatabaseError, ValidationError) as exc:
                print(f"\nCould not create the match: {exc}")
                continue

            print(f"\n✓ Mentorship requested with {chosen.get('job_title')} at "
                  f"{chosen.get('company')} (match {match_id}).")

        elif choice == '3':
            matches = MentorshipManager.get_matches_for(student_id)
            if not matches:
                print("\nYou have no mentorships yet.")
                continue
            print("\nYour mentorships:")
            for m in matches:
                print(f"  [{m['match_id']}] {m.get('job_title')} at {m.get('company')} "
                      f"— {m.get('status') or 'active'}, meeting "
                      f"{m.get('meeting_frequency') or 'as agreed'}")
                if m.get('notes'):
                    print(f"       {m['notes']}")

        elif choice == '4':
            job_title = _ask("Your job title (blank to cancel): ")
            if not job_title:
                print("Cancelled.")
                continue
            company = _ask("Company (blank to cancel): ")
            if not company:
                print("Cancelled.")
                continue
            industry = input("Industry: ").strip()
            expertise = input("Areas you can help with: ").strip()
            max_mentees = _ask_int("How many mentees can you take? [3]: ", default=3)
            bio = input("Short bio (optional): ").strip()

            try:
                mentor_id = MentorshipManager.register_mentor(
                    student_id, job_title, company, industry, expertise,
                    max_mentees or 3, bio)
            except (DatabaseError, ValidationError) as exc:
                print(f"\nCould not register you as a mentor: {exc}")
                continue

            print(f"\n✓ Registered as a mentor (ID {mentor_id}). "
                  f"Students can now request you.")

        elif choice == '5':
            break
        else:
            print("Invalid choice.")


# ---------------------------------------------------------------------------
# 6. Skills
# ---------------------------------------------------------------------------

def skills_assessment(student_id):
    """Record and review the skills on your profile."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        SkillsManager,
    )

    while True:
        print("\nSkills Assessment")
        print("1. My skills")
        print("2. Add a skill")
        print("3. Return to career services")

        choice = input("Choose an option: ").strip()

        if choice == '1':
            skills = SkillsManager.get_student_skills(student_id)
            if not skills:
                print("\nYou have not recorded any skills yet.")
                continue
            print(f"\n{len(skills)} skill(s):")
            category = None
            for s in skills:
                if s.get('skill_category') != category:
                    category = s.get('skill_category')
                    print(f"\n  --- {(category or 'General').upper()} ---")
                verified = " ✓ verified" if s.get('verified') else ""
                print(f"  {s.get('skill_name')} — "
                      f"{s.get('proficiency_level') or 'unrated'}{verified}")

        elif choice == '2':
            skill_name = _ask("Skill (blank to cancel): ")
            if not skill_name:
                print("Cancelled.")
                continue
            category = input("Category (e.g. Technical, Language, Soft): ").strip() or "General"

            levels = ['beginner', 'intermediate', 'advanced', 'expert']
            print(f"Proficiency options: {', '.join(levels)}")
            level = input("Proficiency [intermediate]: ").strip().lower()
            if level not in levels:
                level = 'intermediate'

            try:
                skill_id = SkillsManager.add_skill(student_id, skill_name,
                                                   category, level)
            except (DatabaseError, ValidationError) as exc:
                print(f"\nCould not add the skill: {exc}")
                continue

            print(f"\n✓ '{skill_name}' added at {level} level (ID {skill_id}).")

        elif choice == '3':
            break
        else:
            print("Invalid choice.")


# ---------------------------------------------------------------------------
# 7. Application tracking
# ---------------------------------------------------------------------------

def job_application_tracking(student_id):
    """Show every application you have made and where it has got to."""
    from education_system.systems.university.domains.pastoral.domain.services.career_services.career_services_core import (
        JobManager,
    )

    applications = JobManager.get_student_applications(student_id)
    if not applications:
        print("\nYou have not applied for any jobs yet — "
              "start from 'Browse Job Postings'.")
        return

    print(f"\nYour applications ({len(applications)}):")
    print(f"{'ID':<6} {'Job':<28} {'Company':<22} {'Applied':<12} {'Status':<20}")
    print("-" * 92)
    for a in applications:
        print(f"{a['application_id']:<6} {(a.get('job_title') or '')[:28]:<28} "
              f"{(a.get('company_name') or '')[:22]:<22} "
              f"{(a.get('application_date') or '')[:10]:<12} "
              f"{(a.get('status') or 'pending')[:20]:<20}")

    interviews = [a for a in applications if a.get('interview_date')]
    if interviews:
        print("\nScheduled interviews:")
        for a in interviews:
            where = a.get('interview_location') or a.get('meeting_link') or 'TBC'
            print(f"  {a.get('job_title')} at {a.get('company_name')}: "
                  f"{a.get('interview_type') or 'interview'} on "
                  f"{a.get('interview_date')} {a.get('interview_time') or ''} — {where}")

    counts = {}
    for a in applications:
        status = a.get('status') or 'pending'
        counts[status] = counts.get(status, 0) + 1
    print("\nBy status: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))

    chosen = _pick(applications, "\nSelect an application to view in full",
                   lambda a: f"[{a['application_id']}] {a.get('job_title')} "
                             f"at {a.get('company_name')}")
    if not chosen:
        return

    print("\n" + "=" * 50)
    print(f"  Application {chosen['application_id']}")
    print("=" * 50)
    print(f"Job:      {chosen.get('job_title')} ({chosen.get('job_type') or 'unspecified'})")
    print(f"Company:  {chosen.get('company_name')}")
    print(f"Location: {chosen.get('location') or 'TBC'}")
    print(f"Applied:  {(chosen.get('application_date') or '')[:10]}")
    print(f"Status:   {chosen.get('status') or 'pending'}")
    if chosen.get('resume_id'):
        print(f"Resume:   #{chosen['resume_id']}")
    if chosen.get('cover_letter'):
        print(f"\nCover letter:\n{chosen['cover_letter']}")
    if chosen.get('interview_date'):
        print(f"\nInterview: {chosen.get('interview_type') or 'interview'} on "
              f"{chosen['interview_date']} {chosen.get('interview_time') or ''}")
        if chosen.get('interview_location'):
            print(f"Location:  {chosen['interview_location']}")
        if chosen.get('meeting_link'):
            print(f"Link:      {chosen['meeting_link']}")


__all__ = [
    "browse_job_postings", "submit_resume", "schedule_mock_interview",
    "view_career_events", "alumni_mentorship_program", "skills_assessment",
    "job_application_tracking", "_resolve_student_id",
]
