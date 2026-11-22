"""What is offered: the course catalogue, classes (each run of a course),
venues and tutors.

Rules: course codes are unique (upper-cased); English/maths, ESOL and digital
courses can't be above the level they're funded at; a class's end follows
its start, times are HH:MM, and its capacity can't drop below the learners
already enrolled; tutors' DBS checks are flagged for renewal after 3 years.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.adult_education.core import dates
from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError
from education_system.systems.adult_education.infrastructure import database as db
from education_system.systems.adult_education.modules.funding import COURSE_TYPES, MAX_LEVEL
from education_system.systems.adult_education.modules.learners import (
    LEVEL_RANK, LEVELS, check_email, check_phone, check_postcode,
)

SUBJECTS = ("English", "Maths", "ESOL", "Digital skills", "Arts & crafts", "Languages",
            "Health & wellbeing", "Employability", "Business & finance", "Care",
            "Construction & trades", "Cookery", "Humanities", "Science", "Other")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DBS_RENEWAL_YEARS = 3


def _check_course(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if values.get("code"):
        values["code"] = values["code"].upper().replace(" ", "")
        with db.connect() as conn:
            if conn.execute("SELECT 1 FROM courses WHERE code = ? AND id IS NOT ?",
                            (values["code"], (old or {}).get("id"))).fetchone():
                raise ValidationError(f"Course code {values['code']} is already used.")
    cap = MAX_LEVEL.get(merged.get("course_type") or "")
    if cap and LEVEL_RANK.get(merged.get("level") or "", -1) > LEVEL_RANK[cap]:
        raise ValidationError(f"{merged['course_type']} courses run up to {cap}.")
    if merged.get("accredited") and not merged.get("awarding_body"):
        raise ValidationError("An accredited course needs its awarding body.")


COURSES = RecordType(
    key="courses", title="Course Catalogue", singular="course", order_by="subject, title",
    check=_check_course, filters=("subject", "level", "mode", "status"),
    describe=lambda row: f"{row.get('code')} - {row.get('title')}",
    fields=(
        Field("code", "Code", required=True),
        Field("title", "Title", required=True),
        Field("subject", "Subject", "choice", SUBJECTS, required=True),
        Field("level", "Level", "choice", LEVELS, required=True),
        Field("course_type", "Funding type", "choice", COURSE_TYPES, required=True,
              default="General course", listed=False),
        Field("accredited", "Accredited", "bool",
              help="Leads to a qualification (otherwise RARPA / non-accredited)"),
        Field("awarding_body", "Awarding body", listed=False),
        Field("qualification_ref", "Qualification no.", listed=False),
        Field("mode", "Mode", "choice", ("Classroom", "Online", "Blended"), required=True,
              default="Classroom"),
        Field("guided_hours", "Guided hours", "int"),
        Field("fee", "Full fee", "money"),
        Field("description", "Description", "long", listed=False),
        Field("status", "Status", "choice", ("Active", "Withdrawn"), required=True,
              default="Active"),
    ),
)


def _check_venue(values: dict, _old: dict | None) -> None:
    check_postcode(values)


VENUES = RecordType(
    key="venues", title="Venues", singular="venue", order_by="name", check=_check_venue,
    filters=("kind",), describe=lambda row: str(row.get("name")),
    fields=(
        Field("name", "Name", required=True),
        Field("kind", "Type", "choice", ("Main centre", "Community centre", "Library", "School",
                                         "Employer site", "Online"), required=True),
        Field("address", "Address", listed=False),
        Field("postcode", "Postcode"),
        Field("rooms", "Rooms", "int"),
        Field("step_free", "Step-free access", "bool"),
        Field("hearing_loop", "Hearing loop", "bool"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _dbs_due(row: dict) -> str:
    checked = r.to_date(row.get("dbs_date"))
    if row.get("status") != "Active":
        return ""
    if not checked:
        return "No DBS - overdue"
    due = dates.add_months(checked, 12 * DBS_RENEWAL_YEARS)
    days = (due - date.today()).days
    return f"Renewal overdue {-days}d" if days < 0 else (f"Renew by {dates.uk(due)}"
                                                        if days <= 60 else "")


def _check_tutor(values: dict, old: dict | None) -> None:
    check_email(values)
    check_phone(values)
    merged = {**(old or {}), **values}
    d = r.to_date(r.parse_date(merged.get("dbs_date")))
    if d and d > date.today():
        raise ValidationError("The DBS check date can't be in the future.")


TUTORS = RecordType(
    key="tutors", title="Tutors", singular="tutor", order_by="name", check=_check_tutor,
    filters=("contract", "status"), computed=(("DBS", _dbs_due),),
    describe=lambda row: str(row.get("name")),
    fields=(
        Field("name", "Name", required=True),
        Field("email", "E-mail"),
        Field("phone", "Phone", listed=False),
        Field("subjects", "Teaches"),
        Field("teaching_qualification", "Teaching qualification", "choice",
              ("QTLS", "PGCE / Cert Ed", "Level 5 DET", "Level 3 AET", "In training", "None")),
        Field("contract", "Contract", "choice", ("Sessional", "Part-time", "Full-time",
                                                 "Volunteer"), required=True),
        Field("dbs_date", "DBS checked", "date", listed=False),
        Field("dbs_ref", "DBS certificate no.", listed=False),
        Field("status", "Status", "choice", ("Active", "Left"), required=True,
              default="Active"),
    ),
)


def enrolled_count(conn, class_id: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM enrolments WHERE class_id = ? AND status IN "
                        "('Enrolled', 'Completed')", (class_id,)).fetchone()[0]


def _check_class(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start = r.to_date(r.parse_date(merged.get("start_date")))
    end = r.to_date(r.parse_date(merged.get("end_date")))
    if start and end and end < start:
        raise ValidationError("The class can't end before it starts.")
    for key in ("start_time", "end_time"):
        if values.get(key) and not _TIME.match(values[key]):
            raise ValidationError(f"Times are 24-hour HH:MM (e.g. 18:30), not '{values[key]}'.")
    if merged.get("start_time") and merged.get("end_time") and \
            merged["end_time"] <= merged["start_time"]:
        raise ValidationError("The class must finish after it starts.")
    cap = merged.get("capacity")
    if cap is not None and int(cap) < 1:
        raise ValidationError("Capacity must be at least 1.")
    if old is not None and cap is not None:
        with db.connect() as conn:
            n = enrolled_count(conn, old["id"])
        if int(cap) < n:
            raise ValidationError(f"{n} learners are already enrolled; capacity can't be "
                                  "lower than that.")
    course = r.get(COURSES, int(merged["course_id"])) if merged.get("course_id") else None
    if course and course["status"] != "Active" and old is None:
        raise ValidationError("That course is withdrawn; reactivate it to run a class.")


def delivery(row: dict) -> str:
    """Daytime / Evening / Weekend, from the day and start time."""
    if row.get("day") in ("Saturday", "Sunday"):
        return "Weekend"
    if (row.get("start_time") or "") >= "17:00":
        return "Evening"
    return "Daytime" if row.get("start_time") else ""


def _fill(row: dict) -> str:
    with db.connect() as conn:
        n = enrolled_count(conn, row["id"])
    return f"{n}/{row.get('capacity') or '?'}"


def class_label(row: dict) -> str:
    course = r.get(COURSES, row["course_id"]) if row.get("course_id") else None
    name = f"{course['code']} {course['title']}" if course else "Class"
    return f"{name} - {row.get('day') or ''} {row.get('start_time') or ''} from " \
           f"{dates.uk(r.to_date(row.get('start_date')))}".replace("  ", " ")


CLASSES = RecordType(
    key="classes", title="Classes & Timetable", singular="class",
    order_by="start_date DESC, day, start_time", check=_check_class,
    filters=("term", "day", "status"), describe=class_label,
    computed=(("When", delivery), ("Enrolled", _fill)),
    fields=(
        Field("course_id", "Course", "ref", ref="courses", required=True),
        Field("term", "Term", "choice", ("Autumn", "Spring", "Summer", "Year-round")),
        Field("start_date", "Starts", "date", required=True),
        Field("end_date", "Ends", "date", required=True),
        Field("day", "Day", "choice", DAYS),
        Field("start_time", "From", help="24-hour HH:MM"),
        Field("end_time", "To", listed=False),
        Field("venue_id", "Venue", "ref", ref="venues"),
        Field("tutor_id", "Tutor", "ref", ref="tutors"),
        Field("capacity", "Places", "int", required=True, default=15),
        Field("sessions", "Sessions", "int", listed=False),
        Field("status", "Status", "choice", ("Planned", "Open for enrolment", "Running",
                                             "Completed", "Cancelled"), required=True,
              default="Planned"),
    ),
)
