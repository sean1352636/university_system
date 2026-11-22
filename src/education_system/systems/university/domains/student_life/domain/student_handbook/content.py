"""Student Handbook 2026/27 — the handbook text.

The institution's name is not written into the text: ``{institution}`` (the
full name, e.g. "Teesside University") and ``{short}`` (e.g. "Teesside") are
filled from admin Branding & Customization by :func:`handbook`.

Shared by the book-style GUI reader (interfaces/gui/student_handbook) and the
CLI reader (interfaces/cli/student_handbook). Kept free of tkinter so the
CLI and headless code can import it.
"""

from __future__ import annotations

import copy
import re

# --------------------------------------------------------------------------
# Handbook content
#   Each chapter has sections. Each section becomes one or more pages.
#   Inline links use the form [[label|section_id]].
# --------------------------------------------------------------------------
HANDBOOK = [
    {
        "id": "ch1", "title": "Welcome to {institution}",
        "sections": [
            {"id": "welcome", "title": "A Word from the Vice-Chancellor", "body": [
                "Welcome to {institution}. Whether you are joining us straight from school, "
                "returning to study after time in work, or arriving from the other side of the world, "
                "you are now part of a community of more than 18,000 students and 3,000 staff.",
                "This handbook is your companion for the year ahead. Keep it close: it explains how your "
                "course is organised, how you will be assessed, where to find help, and what we expect "
                "of one another. If you only read one chapter, read [[Getting Help|support]].",
                "We hope your time here is challenging, rewarding and, above all, your own.",
            ]},
            {"id": "history", "title": "Our History", "body": [
                "{institution} grew out of a mechanics' institute that offered evening classes in "
                "engineering and science to people working in the local industries.",
                "Over the following century it became a university college and then a university in its "
                "own right. Today it has several faculties and a research portfolio spanning energy, "
                "health, data science and the creative industries.",
                "The original Institute building, now the Old Library, still stands at the heart of the "
                "City Campus. See [[Campus Map|campus]] for directions.",
            ]},
            {"id": "dates", "title": "Key Dates 2026/27", "body": [
                "• Welcome Week ...................... 21 – 25 September 2026",
                "• Autumn Term ....................... 28 September – 11 December 2026",
                "• Winter Vacation ................... 14 December 2026 – 8 January 2027",
                "• January Assessment Period ......... 11 – 22 January 2027",
                "• Spring Term ....................... 25 January – 26 March 2027",
                "• Easter Vacation ................... 29 March – 23 April 2027",
                "• Summer Term ....................... 26 April – 11 June 2027",
                "• Main Examination Period ........... 10 May – 4 June 2027",
                "• Graduation Week ................... 12 – 16 July 2027",
                "Assessment rules for these periods are set out in [[Examinations|exams]].",
            ]},
        ],
    },
    {
        "id": "ch2", "title": "Your Studies",
        "sections": [
            {"id": "structure", "title": "Programme Structure", "body": [
                "Undergraduate degrees are made up of modules worth 20 credits each. A full-time year "
                "of study is 120 credits, and an honours degree requires 360 credits across three years "
                "(480 for integrated master's programmes).",
                "Most modules run for a single term; some year-long modules run across the autumn and "
                "spring terms. Your programme specification lists which modules are core (compulsory), "
                "which are optional, and any prerequisites.",
                "If you are thinking about changing programme, speak to your Personal Tutor before the "
                "end of week 3 of the autumn term. See [[Personal Tutors|tutors]].",
            ]},
            {"id": "timetable", "title": "Timetables & Attendance", "body": [
                "Your personal timetable is published on the Student Portal and syncs to most calendar apps. "
                "Check it daily during the first few weeks, as rooms can change.",
                "Attendance at timetabled teaching is expected. Attendance is recorded by scanning your "
                "student card at the door. If you miss more than three consecutive sessions without notice, "
                "your Personal Tutor will contact you to check you are all right.",
                "If illness or personal circumstances affect your attendance, read "
                "[[Extenuating Circumstances|ec]] as soon as possible.",
            ]},
            {"id": "tutors", "title": "Personal Tutors", "body": [
                "Every student is assigned a Personal Tutor: an academic in your department who will meet "
                "you at least twice each term to discuss your progress, choices and wellbeing.",
                "Your tutor is your first point of contact for academic questions that are not about a "
                "specific module. They can also write references for placements, jobs and further study.",
                "Your tutor's name and office hours are shown on the Student Portal under 'My Support'.",
            ]},
        ],
    },
    {
        "id": "ch3", "title": "Assessment",
        "sections": [
            {"id": "grading", "title": "How You Are Graded", "body": [
                "Work is marked on a 0–100 scale. The pass mark for undergraduate modules is 40; for "
                "postgraduate modules it is 50.",
                "Degree classification (undergraduate):",
                "• First Class Honours ................ 70 and above",
                "• Upper Second (2:1) ................. 60 – 69",
                "• Lower Second (2:2) ................. 50 – 59",
                "• Third Class Honours ................ 40 – 49",
                "Your final classification is weighted 40% on Year 2 and 60% on Year 3. First-year marks "
                "must be passed but do not count towards the classification.",
            ]},
            {"id": "deadlines", "title": "Deadlines & Late Work", "body": [
                "Coursework must be submitted through the Virtual Learning Environment by 12:00 noon on the "
                "deadline day unless your module handbook says otherwise.",
                "Work submitted up to 24 hours late receives a 10-mark penalty. Work submitted more than 24 "
                "hours late is capped at the pass mark. Work more than five working days late receives a "
                "mark of zero.",
                "If something outside your control stops you meeting a deadline, apply for an extension "
                "before the deadline using the [[Extenuating Circumstances|ec]] process.",
            ]},
            {"id": "exams", "title": "Examinations", "body": [
                "Exam timetables are published four weeks before each assessment period. You must bring your "
                "student card to every exam; you will not be admitted without it.",
                "Arrive at least 15 minutes early. You may not enter more than 30 minutes after the start, or "
                "leave in the first 30 minutes or the final 15 minutes.",
                "Mobile phones, smart watches and any unauthorised materials must be switched off and left in "
                "the area indicated by invigilators. Possession of them at your desk is treated as a breach of "
                "[[Academic Integrity|integrity]] regulations.",
                "Students with reasonable adjustments (extra time, a separate room, a reader) should register "
                "with [[Disability Support|disability]] at least six weeks before the exam period.",
            ]},
            {"id": "ec", "title": "Extenuating Circumstances", "body": [
                "Extenuating circumstances are serious, unforeseen events beyond your control that affect "
                "your ability to study or be assessed, such as illness, bereavement or a family crisis.",
                "You can request (a) an extension of up to 10 working days on coursework, or (b) to defer an "
                "assessment to the next opportunity without penalty.",
                "Apply through the Student Portal. Supporting evidence (for example a doctor's note) is usually "
                "required, but self-certification is allowed for short illnesses of up to seven days, twice a year.",
                "If you are unsure whether your situation qualifies, talk to the [[Student Hub|support]] — "
                "advisers can help you complete the form.",
            ]},
            {"id": "integrity", "title": "Academic Integrity", "body": [
                "Academic integrity means that the work you submit is your own, and that you acknowledge "
                "the ideas and words of others through proper referencing.",
                "Academic misconduct includes plagiarism, collusion, contract cheating (paying or asking "
                "someone else to complete work for you), fabricating data, and submitting AI-generated "
                "content where a module's assessment brief does not permit it.",
                "Penalties range from a formal warning to a mark of zero for the module and, in the most "
                "serious cases, expulsion.",
                "The Library runs free referencing workshops every week. See [[Library|library]].",
            ]},
        ],
    },
    {
        "id": "ch4", "title": "Support & Wellbeing",
        "sections": [
            {"id": "support", "title": "Getting Help: The Student Hub", "body": [
                "The Student Hub, on the ground floor of the Old Library, is your one-stop shop for "
                "questions about fees, enrolment, ID cards, letters, accommodation and wellbeing.",
                "Open Monday – Friday, 9:00 – 17:00. Phone 0191 000 1000 or email hub@northgate.ac.uk.",
                "Not sure who to ask? Start at the Hub. Staff will either answer your question or book you "
                "an appointment with the right specialist team:",
                "• [[Wellbeing & Counselling|wellbeing]]",
                "• [[Disability Support|disability]]",
                "• [[Money Advice|money]]",
                "• [[Careers Service|careers]]",
            ]},
            {"id": "wellbeing", "title": "Wellbeing & Counselling", "body": [
                "The Wellbeing Service offers free, confidential one-to-one sessions with trained counsellors "
                "and mental health advisers, plus group workshops on stress, sleep and exam anxiety.",
                "Book through the Student Hub or self-refer on the Student Portal. Same-day drop-in "
                "appointments are available every weekday from 13:00.",
                "If you are in crisis or worried about your immediate safety, call 999 or go to A&E. For "
                "out-of-hours emotional support you can call Samaritans free on 116 123 at any time.",
            ]},
            {"id": "disability", "title": "Disability Support", "body": [
                "We support students with physical disabilities, sensory impairments, long-term health "
                "conditions, mental health conditions and specific learning differences such as dyslexia.",
                "Register with the Disability Team as early as possible so that a Learning Support Plan can be "
                "put in place. This plan tells your lecturers what reasonable adjustments you need.",
                "You may also be eligible for Disabled Students' Allowance (DSA); the team can help you apply.",
            ]},
            {"id": "money", "title": "Money Advice", "body": [
                "Money Advisers can help with budgeting, student finance problems and applying for the "
                "{short} Hardship Fund, which provides non-repayable grants to students facing financial "
                "difficulty.",
                "{short} Bursaries of £1,000 a year are awarded automatically to eligible UK students with "
                "a household income below £30,000. You do not need to apply separately.",
            ]},
            {"id": "careers", "title": "Careers Service", "body": [
                "The Careers Service supports you from your first week to three years after graduation. "
                "Services include CV and application reviews, mock interviews, a jobs board and "
                "placement-year advice.",
                "The Autumn Careers Fair takes place in the Sports Hall in week 6 of the autumn term.",
            ]},
        ],
    },
    {
        "id": "ch5", "title": "Campus Life",
        "sections": [
            {"id": "campus", "title": "Campus Map & Buildings", "body": [
                "City Campus — Old Library (Student Hub), Armstrong Building (Engineering), Grey Building "
                "(Business & Law), Students' Union, Main Library.",
                "Riverside Campus — Health Sciences Centre, Clinical Skills Suite, Riverside Halls. "
                "Free shuttle bus to City Campus every 15 minutes.",
                "Moorland Campus — Sports Centre, playing fields, Agricultural Research Station.",
                "Most buildings are open 8:00 – 21:00 on weekdays. Card access is needed after 18:00.",
            ]},
            {"id": "library", "title": "Library", "body": [
                "The Main Library is open 24 hours a day, 7 days a week during term time, with silent, "
                "quiet and group study zones across five floors.",
                "You can borrow up to 30 items. Standard loans are for four weeks and renew automatically "
                "unless someone else requests the item.",
                "Subject librarians run sessions on literature searching and referencing — essential reading "
                "for [[Academic Integrity|integrity]].",
            ]},
            {"id": "union", "title": "Students' Union & Societies", "body": [
                "{short} Students' Union is run by students, for students. It represents your views to the "
                "University, supports more than 200 clubs and societies, and runs the Union bar, shop and venue.",
                "The SU Advice Centre gives independent advice on academic appeals, complaints and housing "
                "disputes, separate from the University.",
                "Join societies at the Freshers' Fair in Welcome Week, or online at any time of year.",
            ]},
        ],
    },
    {
        "id": "ch6", "title": "Rules & Regulations",
        "sections": [
            {"id": "conduct", "title": "Code of Conduct", "body": [
                "Members of the University community are expected to treat one another with respect and to "
                "behave in a way that does not harm the safety, wellbeing or reputation of others.",
                "Harassment, bullying, hate speech, sexual misconduct, and damage to property are serious "
                "disciplinary offences, whether they occur on campus, in halls or online.",
                "You can report concerns, anonymously if you wish, through the 'Report and Support' page on "
                "the Student Portal.",
            ]},
            {"id": "appeals", "title": "Appeals & Complaints", "body": [
                "An academic appeal asks the University to review a decision about your marks or progression. "
                "Appeals must be submitted within 10 working days of results being published. You cannot "
                "appeal against academic judgement.",
                "A complaint is about the quality of a service. Try to resolve it informally first; if that "
                "fails, submit a formal complaint through the Student Portal.",
                "If you remain dissatisfied after completing internal procedures, you may refer your case to "
                "the Office of the Independent Adjudicator (OIA).",
            ]},
            {"id": "contacts", "title": "Useful Contacts", "body": [
                "• Student Hub ............ 0191 000 1000 · hub@northgate.ac.uk",
                "• Campus Security (24h) .. 0191 000 2222",
                "• IT Service Desk ........ 0191 000 3000 · it@northgate.ac.uk",
                "• Library ................ library@northgate.ac.uk",
                "• Students' Union ........ su@northgate.ac.uk",
                "• Emergency .............. 999",
                "Return to the [[Contents|toc]] or the [[Welcome|welcome]] page.",
            ]},
        ],
    },
]

UNIVERSITY = "the University"   # only if no institution name is configured
SUBTITLE = "Student Handbook"
YEAR = "2026 – 2027"
MOTTO = "Scientia Lux Septentrionis"


# --------------------------------------------------------------------------
# Lookups used by the readers
# --------------------------------------------------------------------------
def institution_name() -> str:
    """The institution name set in admin Branding & Customization, worded as
    the dashboard's welcome banner words it ("… University" unless the name
    already says so). Falls back to the handbook's own name."""
    try:
        from education_system.systems.university.infrastructure.institution_settings import (
            get_institution_name,
        )
        name = (get_institution_name() or "").strip()
    except Exception:
        name = ""
    if not name:
        return UNIVERSITY
    return name if "university" in name.lower() else f"{name} University"


def short_name(name: str | None = None) -> str:
    """"Teesside" for "Teesside University", "Leeds" for "University of Leeds"."""
    name = (name or institution_name()).strip()
    for prefix in ("The University of ", "University of "):
        if name.startswith(prefix):
            return name[len(prefix):].strip() or name
    if name.lower().endswith(" university"):
        return name[: -len(" university")].strip() or name
    return name


def institution_address() -> str:
    """One line of the institution's address from institution settings."""
    try:
        from education_system.systems.university.infrastructure.institution_settings import (
            get_setting,
        )
        parts = [str(get_setting(k, "") or "").strip()
                 for k in ("address_line1", "address_line2", "postcode")]
    except Exception:
        parts = []
    return " · ".join(p for p in parts if p)


def _fill(text: str, name: str, short: str) -> str:
    return text.replace("{institution}", name).replace("{short}", short)


def handbook() -> list[dict]:
    """The chapters with branding placeholders filled in. Readers call this
    each time they open, so a renamed institution shows without a restart."""
    chapters = copy.deepcopy(HANDBOOK)
    name = institution_name()
    short = short_name(name)
    for ch in chapters:
        ch["title"] = _fill(ch["title"], name, short)
        for sec in ch["sections"]:
            sec["title"] = _fill(sec["title"], name, short)
            sec["body"] = [_fill(p, name, short) for p in sec["body"]]
    return chapters


LINK_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")


def links_in(text: str) -> list[tuple[str, str]]:
    """``[(label, target_id), ...]`` for each [[label|target]] link in ``text``."""
    return LINK_RE.findall(text)


def strip_links(text: str) -> str:
    """``text`` with each [[label|target]] link reduced to its label."""
    return LINK_RE.sub(lambda m: m.group(1), text)


def sections(chapters: list[dict] | None = None) -> list[dict]:
    """Every section in reading order, each as
    ``{"num": "2.3", "chapter": <chapter>, "section": <section>}``."""
    out = []
    for c_num, ch in enumerate(chapters if chapters is not None else handbook(), start=1):
        for s_num, sec in enumerate(ch["sections"], start=1):
            out.append({"num": f"{c_num}.{s_num}", "chapter": ch, "section": sec})
    return out


def search(query: str, chapters: list[dict] | None = None) -> list[dict]:
    """Sections whose title or text contains every word of ``query``."""
    words = [w for w in query.casefold().split() if w]
    if not words:
        return []
    hits = []
    for entry in sections(chapters):
        sec = entry["section"]
        haystack = " ".join([entry["chapter"]["title"], sec["title"],
                             *(strip_links(p) for p in sec["body"])]).casefold()
        if all(w in haystack for w in words):
            hits.append(entry)
    return hits
