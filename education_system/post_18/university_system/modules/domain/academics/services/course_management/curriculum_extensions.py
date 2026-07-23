"""CLI counterparts of the course-management *curriculum extensions*.

These mirror the ten GUI tabs added under ``course_management_gui`` and share
the exact same tables (keyed by ``course_code``), so data entered in the CLI
shows up in the GUI and vice versa:

  1. Academic terms & course sections
  2. Co-requisites & enrolment restrictions
  3. Syllabus & course materials
  4. Learning outcomes & curriculum mapping
  5. Course approval workflow
  6. Weekly timetable (text view)
  7. Term rollover / clone
  8. Cross-listing & equivalency
  9. Grading scheme & assessment weighting
 10. Waitlist auto-promotion rules

The schema is (re)declared here rather than imported from the GUI package so
the CLI never has to import tkinter. Statements are idempotent and use the
same table names as the GUI, keeping a single source of data.

Error handling and logging are centralised in the small helpers near the top
(``_run``, ``_connect``) and reused by every command.
"""

import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)
from education_system.post_18.university_system.core.i18n import get_text
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_menu_navigation, log_create, log_update, log_delete,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema (mirrors course_management_gui.core.ext_common)
# ---------------------------------------------------------------------------

_EXTENSION_DDL = (
    """CREATE TABLE IF NOT EXISTS academic_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        term_type TEXT NOT NULL DEFAULT 'Semester',
        academic_year TEXT NOT NULL DEFAULT '',
        start_date TEXT DEFAULT '', end_date TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Planned',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, term_id INTEGER NOT NULL,
        section_number TEXT NOT NULL DEFAULT '001', instructor TEXT DEFAULT '',
        capacity INTEGER NOT NULL DEFAULT 30, enrolled INTEGER NOT NULL DEFAULT 0,
        delivery_mode TEXT NOT NULL DEFAULT 'In Person', location TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Open', notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(course_code, term_id, section_number))""",
    """CREATE TABLE IF NOT EXISTS course_corequisites_ext (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, corequisite_code TEXT NOT NULL,
        notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(course_code, corequisite_code))""",
    """CREATE TABLE IF NOT EXISTS course_restrictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, restriction_type TEXT NOT NULL DEFAULT 'Major',
        restriction_value TEXT NOT NULL DEFAULT '', reserved_seats INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, material_type TEXT NOT NULL DEFAULT 'Textbook',
        title TEXT NOT NULL, author TEXT DEFAULT '', isbn TEXT DEFAULT '',
        edition TEXT DEFAULT '', url TEXT DEFAULT '', cost REAL NOT NULL DEFAULT 0.0,
        required INTEGER NOT NULL DEFAULT 1, notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_learning_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, outcome_code TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS outcome_program_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outcome_id INTEGER NOT NULL, standard_type TEXT NOT NULL DEFAULT 'Program Outcome',
        standard_code TEXT NOT NULL DEFAULT '', standard_description TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL UNIQUE, stage TEXT NOT NULL DEFAULT 'Draft',
        submitted_by TEXT DEFAULT '', reviewer TEXT DEFAULT '', comments TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_approval_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, from_stage TEXT DEFAULT '', to_stage TEXT NOT NULL,
        actor TEXT DEFAULT '', comments TEXT DEFAULT '',
        changed_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS section_meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER NOT NULL, day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL DEFAULT '09:00', end_time TEXT NOT NULL DEFAULT '10:00',
        location TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_crosslistings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, related_code TEXT NOT NULL,
        relation_type TEXT NOT NULL DEFAULT 'Cross-listed', notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(course_code, related_code, relation_type))""",
    """CREATE TABLE IF NOT EXISTS course_grading_schemes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL UNIQUE, scheme_type TEXT NOT NULL DEFAULT 'Letter',
        pass_mark REAL NOT NULL DEFAULT 50.0, notes TEXT DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS course_assessment_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, name TEXT NOT NULL, weight REAL NOT NULL DEFAULT 0.0,
        notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS waitlist_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL UNIQUE, auto_promote INTEGER NOT NULL DEFAULT 0,
        promotion_order TEXT NOT NULL DEFAULT 'FIFO', notify INTEGER NOT NULL DEFAULT 1,
        max_auto INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')))""",
)

_DONE_WAITLIST_STATUSES = {"promoted", "enrolled", "removed", "cancelled", "withdrawn"}
APPROVAL_TRANSITIONS = {
    "Draft": ["Submitted"],
    "Submitted": ["Under Review", "Draft"],
    "Under Review": ["Approved", "Rejected"],
    "Approved": ["Draft"],
    "Rejected": ["Draft"],
}


def ensure_extension_schema():
    """Create the curriculum-extension tables if missing. Resilient: a single
    failing statement is logged and skipped rather than aborting the rest."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for ddl in _EXTENSION_DDL:
            try:
                cur.execute(ddl)
                conn.commit()
            except Exception:
                logger.exception("Extension DDL failed (continuing): %s",
                                 " ".join(ddl.split())[:70])
        return True
    except Exception:
        logger.exception("Could not ensure curriculum-extension schema")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("close failed", exc_info=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _username(auth):
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or "system"
        if user is not None:
            return getattr(user, "username", None) or "system"
    except Exception:
        logger.debug("username resolve failed", exc_info=True)
    return "system"


def _can_edit(auth):
    try:
        return bool(auth and auth.current_user and auth.check_permission("manage_courses"))
    except Exception:
        return False


def _require_login(auth):
    if not auth or not auth.current_user:
        print(get_text("course_mgmt.login_required",
                       default="You must be logged in to access course management."))
        return False
    return True


def _prompt(message):
    try:
        return input(message).strip()
    except EOFError:
        return ""


def _pause():
    _prompt("\nPress Enter to continue...")


def _run(action_label, fn, *args, **kwargs):
    """Execute ``fn`` guarding against DB and unexpected errors, logging both.

    Keeps every command's error handling identical and out of the happy path.
    """
    try:
        return fn(*args, **kwargs)
    except sqlite3.Error as exc:
        logger.exception("Database error during %s", action_label)
        print(f"\n❌ Database error while trying to {action_label}: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error during %s", action_label)
        print(f"\n❌ Error while trying to {action_label}: {exc}")
    return None


def _fetch_courses(cur):
    cur.execute(
        "SELECT COALESCE(course_code, code) AS cc, COALESCE(course_name, name) AS cn "
        "FROM courses WHERE COALESCE(course_code, code) IS NOT NULL ORDER BY cc")
    return [(r[0], r[1]) for r in cur.fetchall()]


def _pick_course(cur, prompt="Enter course code"):
    """Prompt for a course code, accepting only codes that exist in the DB."""
    courses = _fetch_courses(cur)
    if not courses:
        print("No courses exist in the database.")
        return None
    valid = {str(code).upper(): code for code, _ in courses}
    print("\nAvailable courses:")
    for code, name in courses:
        print(f"  {code:<12} {name or ''}")
    while True:
        raw = _prompt(f"\n{prompt} (blank to cancel): ")
        if not raw:
            return None
        key = raw.upper()
        if key in valid:
            return valid[key]
        print("That course code is not in the database. Choose one listed above.")


def _pick_term(cur, prompt="Enter term ID"):
    cur.execute("SELECT id, name FROM academic_terms ORDER BY academic_year DESC, name")
    terms = cur.fetchall()
    if not terms:
        print("No academic terms exist yet. Create one first.")
        return None
    valid = {str(t[0]): t[0] for t in terms}
    print("\nAvailable terms:")
    for tid, name in terms:
        print(f"  [{tid}] {name}")
    while True:
        raw = _prompt(f"\n{prompt} (blank to cancel): ")
        if not raw:
            return None
        if raw in valid:
            return valid[raw]
        print("Invalid term ID. Choose one listed above.")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_minutes(hhmm):
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


# ===========================================================================
# 1. Academic terms & course sections
# ===========================================================================

@log_menu_navigation(description="Managing terms and sections")
def manage_terms_and_sections(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    while True:
        print("\n--- TERMS & SECTIONS ---")
        print("1. List academic terms")
        print("2. List course sections")
        if editable:
            print("3. Add term      4. Delete term")
            print("5. Add section   6. Delete section")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("list terms", _list_terms)
        elif choice == "2":
            _run("list sections", _list_sections)
        elif choice == "3" and editable:
            _run("add term", _add_term, auth)
        elif choice == "4" and editable:
            _run("delete term", _delete_term, auth)
        elif choice == "5" and editable:
            _run("add section", _add_section, auth)
        elif choice == "6" and editable:
            _run("delete section", _delete_section, auth)
        else:
            print("Invalid choice.")
        _pause()


def _list_terms():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, term_type, academic_year, status "
                    "FROM academic_terms ORDER BY academic_year DESC, name")
        rows = cur.fetchall()
        if not rows:
            print("\nNo academic terms defined.")
            return
        print(f"\n{'ID':<5}{'Name':<24}{'Type':<14}{'Year':<12}{'Status':<12}")
        print("-" * 67)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<24}{(r[2] or ''):<14}{(r[3] or ''):<12}{(r[4] or ''):<12}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding academic term")
def _add_term(auth):
    name = _prompt("Term name (e.g. Fall 2026): ")
    if not name:
        print("Cancelled — name is required.")
        return
    term_type = _prompt("Type [Semester]: ") or "Semester"
    year = _prompt("Academic year (e.g. 2026-27): ")
    start = _prompt("Start date (YYYY-MM-DD, optional): ")
    end = _prompt("End date (YYYY-MM-DD, optional): ")
    status = _prompt("Status [Planned]: ") or "Planned"
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO academic_terms (name, term_type, academic_year, start_date, "
            "end_date, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, term_type, year, start, end, status, _now(), _now()))
        conn.commit()
        print(f"✅ Term '{name}' created.")
    except sqlite3.IntegrityError:
        print(f"❌ A term named '{name}' already exists.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Deleting academic term")
def _delete_term(auth):
    conn = get_connection()
    try:
        cur = conn.cursor()
        term_id = _pick_term(cur, "Enter term ID to delete")
        if term_id is None:
            return
        cur.execute("SELECT COUNT(*) FROM course_sections WHERE term_id=?", (term_id,))
        n = cur.fetchone()[0]
        if _prompt(f"Delete term and its {n} section(s)? (y/n): ").lower() != "y":
            print("Cancelled.")
            return
        cur.execute("DELETE FROM course_sections WHERE term_id=?", (term_id,))
        cur.execute("DELETE FROM academic_terms WHERE id=?", (term_id,))
        conn.commit()
        print("✅ Term deleted.")
    finally:
        conn.close()


def _list_sections():
    conn = get_connection()
    try:
        cur = conn.cursor()
        term_id = _pick_term(cur, "List sections for term ID")
        if term_id is None:
            return
        cur.execute(
            "SELECT id, course_code, section_number, instructor, capacity, enrolled, "
            "delivery_mode, status FROM course_sections WHERE term_id=? "
            "ORDER BY course_code, section_number", (term_id,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo sections in this term.")
            return
        print(f"\n{'ID':<5}{'Course':<10}{'Sec':<6}{'Instructor':<18}{'Cap':<5}{'Enr':<5}{'Mode':<12}{'Status':<10}")
        print("-" * 71)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<10}{(r[2] or ''):<6}{(r[3] or ''):<18}"
                  f"{r[4]:<5}{r[5]:<5}{(r[6] or ''):<12}{(r[7] or ''):<10}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding course section")
def _add_section(auth):
    conn = get_connection()
    try:
        cur = conn.cursor()
        code = _pick_course(cur, "Course for the section")
        if not code:
            return
        term_id = _pick_term(cur, "Term for the section")
        if term_id is None:
            return
        section = _prompt("Section number [001]: ") or "001"
        instructor = _prompt("Instructor: ")
        mode = _prompt("Delivery mode [In Person]: ") or "In Person"
        location = _prompt("Location: ")
        cap = _read_int("Capacity [30]: ", default=30, minimum=0)
        enrolled = _read_int("Enrolled [0]: ", default=0, minimum=0)
        status = _prompt("Status [Open]: ") or "Open"
        try:
            cur.execute(
                "INSERT INTO course_sections (course_code, term_id, section_number, "
                "instructor, capacity, enrolled, delivery_mode, location, status, "
                "notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, term_id, section, instructor, cap, enrolled, mode, location,
                 status, "", _now(), _now()))
            conn.commit()
            print(f"✅ Section {code}-{section} created.")
        except sqlite3.IntegrityError:
            print(f"❌ Section '{section}' already exists for {code} in that term.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Deleting course section")
def _delete_section(auth):
    conn = get_connection()
    try:
        cur = conn.cursor()
        term_id = _pick_term(cur, "Term of the section to delete")
        if term_id is None:
            return
        cur.execute("SELECT id, course_code, section_number FROM course_sections "
                    "WHERE term_id=? ORDER BY course_code, section_number", (term_id,))
        rows = cur.fetchall()
        if not rows:
            print("No sections in that term.")
            return
        valid = {str(r[0]): r for r in rows}
        for r in rows:
            print(f"  [{r[0]}] {r[1]} section {r[2]}")
        sid = _prompt("Section ID to delete (blank to cancel): ")
        if sid not in valid:
            print("Cancelled / invalid.")
            return
        cur.execute("DELETE FROM section_meetings WHERE section_id=?", (sid,))
        cur.execute("DELETE FROM course_sections WHERE id=?", (sid,))
        conn.commit()
        print("✅ Section deleted.")
    finally:
        conn.close()


def _read_int(prompt, default=0, minimum=None, maximum=None):
    while True:
        raw = _prompt(prompt)
        if not raw:
            return default
        try:
            val = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minimum is not None and val < minimum:
            print(f"Must be ≥ {minimum}.")
            continue
        if maximum is not None and val > maximum:
            print(f"Must be ≤ {maximum}.")
            continue
        return val


def _read_float(prompt, default=0.0, minimum=None, maximum=None):
    while True:
        raw = _prompt(prompt)
        if not raw:
            return default
        try:
            val = float(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if minimum is not None and val < minimum:
            print(f"Must be ≥ {minimum}.")
            continue
        if maximum is not None and val > maximum:
            print(f"Must be ≤ {maximum}.")
            continue
        return val


# ===========================================================================
# 2. Co-requisites & enrolment restrictions
# ===========================================================================

@log_menu_navigation(description="Managing co-requisites and restrictions")
def manage_corequisites_and_restrictions(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        code = _pick_course(conn.cursor(), "Course to manage")
    finally:
        conn.close()
    if not code:
        return
    while True:
        print(f"\n--- CO-REQS & RESTRICTIONS for {code} ---")
        print("1. View co-requisites   2. View restrictions")
        if editable:
            print("3. Add co-requisite     4. Remove co-requisite")
            print("5. Add restriction      6. Remove restriction")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("view co-requisites", _list_coreqs, code)
        elif choice == "2":
            _run("view restrictions", _list_restrictions, code)
        elif choice == "3" and editable:
            _run("add co-requisite", _add_coreq, auth, code)
        elif choice == "4" and editable:
            _run("remove co-requisite", _remove_coreq, auth, code)
        elif choice == "5" and editable:
            _run("add restriction", _add_restriction, auth, code)
        elif choice == "6" and editable:
            _run("remove restriction", _remove_restriction, auth, code)
        else:
            print("Invalid choice.")
        _pause()


def _list_coreqs(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, corequisite_code, notes FROM course_corequisites_ext "
                    "WHERE course_code=? ORDER BY corequisite_code", (code,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo co-requisites.")
            return
        print(f"\n{'ID':<5}{'Co-requisite':<16}{'Notes'}")
        print("-" * 50)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<16}{r[2] or ''}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding co-requisite")
def _add_coreq(auth, code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        coreq = _pick_course(cur, "Co-requisite course")
        if not coreq:
            return
        if coreq == code:
            print("A course cannot be its own co-requisite.")
            return
        notes = _prompt("Notes: ")
        try:
            cur.execute("INSERT INTO course_corequisites_ext (course_code, "
                        "corequisite_code, notes, created_at) VALUES (?, ?, ?, ?)",
                        (code, coreq, notes, _now()))
            conn.commit()
            print(f"✅ Co-requisite {coreq} added to {code}.")
        except sqlite3.IntegrityError:
            print("❌ That co-requisite is already linked.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing co-requisite")
def _remove_coreq(auth, code):
    _list_coreqs(code)
    rid = _prompt("Co-requisite ID to remove (blank to cancel): ")
    if not rid:
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM course_corequisites_ext WHERE id=? AND course_code=?",
                     (rid, code))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


def _list_restrictions(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, restriction_type, restriction_value, reserved_seats, "
                    "active FROM course_restrictions WHERE course_code=? "
                    "ORDER BY restriction_type", (code,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo restrictions.")
            return
        print(f"\n{'ID':<5}{'Type':<18}{'Applies to':<24}{'Seats':<7}{'Active'}")
        print("-" * 62)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<18}{(r[2] or ''):<24}{r[3]:<7}"
                  f"{'Yes' if r[4] else 'No'}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding restriction")
def _add_restriction(auth, code):
    rtype = _prompt("Restriction type [Major]: ") or "Major"
    value = _prompt("Applies to (value): ")
    seats = _read_int("Reserved seats [0]: ", default=0, minimum=0)
    active = (_prompt("Active? (Y/n): ") or "y").lower() != "n"
    conn = get_connection()
    try:
        conn.execute("INSERT INTO course_restrictions (course_code, restriction_type, "
                     "restriction_value, reserved_seats, active, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (code, rtype, value, seats, 1 if active else 0, _now()))
        conn.commit()
        print("✅ Restriction added.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing restriction")
def _remove_restriction(auth, code):
    _list_restrictions(code)
    rid = _prompt("Restriction ID to remove (blank to cancel): ")
    if not rid:
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM course_restrictions WHERE id=? AND course_code=?",
                     (rid, code))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


# ===========================================================================
# 3. Syllabus & course materials
# ===========================================================================

@log_menu_navigation(description="Managing course materials")
def manage_course_materials(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        code = _pick_course(conn.cursor(), "Course to manage materials for")
    finally:
        conn.close()
    if not code:
        return
    while True:
        print(f"\n--- MATERIALS for {code} ---")
        print("1. List materials")
        if editable:
            print("2. Add material   3. Remove material")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("list materials", _list_materials, code)
        elif choice == "2" and editable:
            _run("add material", _add_material, auth, code)
        elif choice == "3" and editable:
            _run("remove material", _remove_material, auth, code)
        else:
            print("Invalid choice.")
        _pause()


def _list_materials(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, material_type, title, author, isbn, cost, required "
                    "FROM course_materials WHERE course_code=? "
                    "ORDER BY material_type, title", (code,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo materials.")
            return
        required_total = 0.0
        print(f"\n{'ID':<5}{'Type':<12}{'Title':<28}{'Author':<16}{'Cost':<8}{'Req'}")
        print("-" * 73)
        for r in rows:
            cost = r[5] or 0.0
            if r[6]:
                required_total += cost
            print(f"{r[0]:<5}{(r[1] or ''):<12}{(r[2] or '')[:27]:<28}{(r[3] or '')[:15]:<16}"
                  f"{cost:<8.2f}{'Yes' if r[6] else 'No'}")
        print(f"\nRequired-materials cost total: {required_total:.2f}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding course material")
def _add_material(auth, code):
    mtype = _prompt("Type [Textbook]: ") or "Textbook"
    title = _prompt("Title: ")
    if not title:
        print("Cancelled — title is required.")
        return
    author = _prompt("Author: ")
    isbn = _prompt("ISBN: ")
    edition = _prompt("Edition: ")
    url = _prompt("URL / file path: ")
    cost = _read_float("Cost [0]: ", default=0.0, minimum=0)
    required = (_prompt("Required? (Y/n): ") or "y").lower() != "n"
    conn = get_connection()
    try:
        conn.execute("INSERT INTO course_materials (course_code, material_type, title, "
                     "author, isbn, edition, url, cost, required, notes, created_at, "
                     "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (code, mtype, title, author, isbn, edition, url, cost,
                      1 if required else 0, "", _now(), _now()))
        conn.commit()
        print(f"✅ Material '{title}' added.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing course material")
def _remove_material(auth, code):
    _list_materials(code)
    mid = _prompt("Material ID to remove (blank to cancel): ")
    if not mid:
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM course_materials WHERE id=? AND course_code=?",
                     (mid, code))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


# ===========================================================================
# 4. Learning outcomes & curriculum mapping
# ===========================================================================

@log_menu_navigation(description="Managing learning outcomes")
def manage_learning_outcomes(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        code = _pick_course(conn.cursor(), "Course to manage outcomes for")
    finally:
        conn.close()
    if not code:
        return
    while True:
        print(f"\n--- LEARNING OUTCOMES for {code} ---")
        print("1. List outcomes   2. View mappings for an outcome")
        if editable:
            print("3. Add outcome     4. Remove outcome")
            print("5. Add mapping     6. Remove mapping")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("list outcomes", _list_outcomes, code)
        elif choice == "2":
            _run("view mappings", _view_mappings, code)
        elif choice == "3" and editable:
            _run("add outcome", _add_outcome, auth, code)
        elif choice == "4" and editable:
            _run("remove outcome", _remove_outcome, auth, code)
        elif choice == "5" and editable:
            _run("add mapping", _add_mapping, auth, code)
        elif choice == "6" and editable:
            _run("remove mapping", _remove_mapping, auth, code)
        else:
            print("Invalid choice.")
        _pause()


def _list_outcomes(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, outcome_code, description FROM course_learning_outcomes "
                    "WHERE course_code=? ORDER BY outcome_code, id", (code,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo learning outcomes.")
            return rows
        print(f"\n{'ID':<5}{'Code':<10}{'Description'}")
        print("-" * 60)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<10}{r[2] or ''}")
        return rows
    finally:
        conn.close()


@log_create(module="course_management", description="Adding learning outcome")
def _add_outcome(auth, code):
    oc = _prompt("Outcome code (e.g. CLO1): ")
    desc = _prompt("Description: ")
    if not desc:
        print("Cancelled — description is required.")
        return
    conn = get_connection()
    try:
        conn.execute("INSERT INTO course_learning_outcomes (course_code, outcome_code, "
                     "description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                     (code, oc, desc, _now(), _now()))
        conn.commit()
        print("✅ Outcome added.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing learning outcome")
def _remove_outcome(auth, code):
    _list_outcomes(code)
    oid = _prompt("Outcome ID to remove (blank to cancel): ")
    if not oid:
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM outcome_program_mappings WHERE outcome_id=?", (oid,))
        conn.execute("DELETE FROM course_learning_outcomes WHERE id=? AND course_code=?",
                     (oid, code))
        conn.commit()
        print("✅ Outcome and its mappings removed.")
    finally:
        conn.close()


def _resolve_outcome_id(cur, code):
    rows = _list_outcomes(code)
    if not rows:
        return None
    oid = _prompt("Outcome ID (blank to cancel): ")
    if not oid:
        return None
    cur.execute("SELECT 1 FROM course_learning_outcomes WHERE id=? AND course_code=?",
                (oid, code))
    if not cur.fetchone():
        print("Invalid outcome ID.")
        return None
    return oid


def _view_mappings(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        oid = _resolve_outcome_id(cur, code)
        if oid is None:
            return
        cur.execute("SELECT id, standard_type, standard_code, standard_description "
                    "FROM outcome_program_mappings WHERE outcome_id=? "
                    "ORDER BY standard_type", (oid,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo mappings for that outcome.")
            return
        print(f"\n{'ID':<5}{'Type':<22}{'Code':<10}{'Description'}")
        print("-" * 66)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<22}{(r[2] or ''):<10}{r[3] or ''}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding outcome mapping")
def _add_mapping(auth, code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        oid = _resolve_outcome_id(cur, code)
        if oid is None:
            return
        stype = _prompt("Standard type [Program Outcome]: ") or "Program Outcome"
        scode = _prompt("Standard code: ")
        sdesc = _prompt("Standard description: ")
        if not scode and not sdesc:
            print("Cancelled — provide a code or description.")
            return
        cur.execute("INSERT INTO outcome_program_mappings (outcome_id, standard_type, "
                    "standard_code, standard_description, created_at) "
                    "VALUES (?, ?, ?, ?, ?)", (oid, stype, scode, sdesc, _now()))
        conn.commit()
        print("✅ Mapping added.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing outcome mapping")
def _remove_mapping(auth, code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        oid = _resolve_outcome_id(cur, code)
        if oid is None:
            return
        cur.execute("SELECT id, standard_type, standard_code FROM outcome_program_mappings "
                    "WHERE outcome_id=?", (oid,))
        for r in cur.fetchall():
            print(f"  [{r[0]}] {r[1]} {r[2]}")
        mid = _prompt("Mapping ID to remove (blank to cancel): ")
        if not mid:
            return
        cur.execute("DELETE FROM outcome_program_mappings WHERE id=? AND outcome_id=?",
                    (mid, oid))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


# ===========================================================================
# 5. Course approval workflow
# ===========================================================================

@log_menu_navigation(description="Managing course approvals")
def manage_course_approvals(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    while True:
        print("\n--- COURSE APPROVALS ---")
        print("1. View approval status (all courses)")
        print("2. View approval history for a course")
        if editable:
            print("3. Transition a course")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("view approvals", _list_approvals)
        elif choice == "2":
            _run("view approval history", _approval_history)
        elif choice == "3" and editable:
            _run("transition approval", _transition_approval, auth)
        else:
            print("Invalid choice.")
        _pause()


def _list_approvals():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(c.course_code, c.code), COALESCE(a.stage, 'Draft'), "
            "COALESCE(a.submitted_by, ''), COALESCE(a.reviewer, ''), "
            "COALESCE(a.updated_at, '') FROM courses c "
            "LEFT JOIN course_approvals a ON a.course_code = COALESCE(c.course_code, c.code) "
            "WHERE COALESCE(c.course_code, c.code) IS NOT NULL "
            "ORDER BY 1")
        rows = cur.fetchall()
        print(f"\n{'Course':<12}{'Stage':<14}{'Submitted by':<16}{'Reviewer':<16}{'Updated'}")
        print("-" * 70)
        for r in rows:
            print(f"{(r[0] or ''):<12}{(r[1] or ''):<14}{(r[2] or ''):<16}"
                  f"{(r[3] or ''):<16}{r[4] or ''}")
    finally:
        conn.close()


def _approval_history():
    conn = get_connection()
    try:
        cur = conn.cursor()
        code = _pick_course(cur, "Course")
        if not code:
            return
        cur.execute("SELECT changed_at, from_stage, to_stage, actor, comments "
                    "FROM course_approval_history WHERE course_code=? "
                    "ORDER BY id DESC", (code,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo transitions recorded.")
            return
        print(f"\n{'When':<20}{'From':<14}{'To':<14}{'Actor':<14}{'Comment'}")
        print("-" * 78)
        for r in rows:
            print(f"{(r[0] or ''):<20}{(r[1] or ''):<14}{(r[2] or ''):<14}"
                  f"{(r[3] or ''):<14}{r[4] or ''}")
    finally:
        conn.close()


@log_update(module="course_management", description="Transitioning course approval")
def _transition_approval(auth):
    conn = get_connection()
    try:
        cur = conn.cursor()
        code = _pick_course(cur, "Course to transition")
        if not code:
            return
        cur.execute("SELECT stage FROM course_approvals WHERE course_code=?", (code,))
        row = cur.fetchone()
        current = row[0] if row else "Draft"
        targets = APPROVAL_TRANSITIONS.get(current, [])
        if not targets:
            print(f"No transitions available from '{current}'.")
            return
        print(f"\nCurrent stage: {current}")
        for i, t in enumerate(targets, 1):
            print(f"  {i}. {t}")
        sel = _prompt("Move to (number, blank to cancel): ")
        if not sel:
            return
        try:
            target = targets[int(sel) - 1]
        except (ValueError, IndexError):
            print("Invalid selection.")
            return
        comment = _prompt("Comment: ")
        if target == "Rejected" and not comment:
            print("A comment is required when rejecting.")
            return
        actor = _username(auth)
        if row:
            cur.execute(
                "UPDATE course_approvals SET stage=?, "
                "submitted_by=CASE WHEN ?='Submitted' THEN ? ELSE submitted_by END, "
                "reviewer=CASE WHEN ? IN ('Approved','Rejected','Under Review') "
                "             THEN ? ELSE reviewer END, "
                "comments=?, updated_at=? WHERE course_code=?",
                (target, target, actor, target, actor, comment, _now(), code))
        else:
            cur.execute(
                "INSERT INTO course_approvals (course_code, stage, submitted_by, "
                "reviewer, comments, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (code, target, actor if target == "Submitted" else "",
                 actor if target in ("Approved", "Rejected", "Under Review") else "",
                 comment, _now(), _now()))
        cur.execute(
            "INSERT INTO course_approval_history (course_code, from_stage, to_stage, "
            "actor, comments, changed_at) VALUES (?,?,?,?,?,?)",
            (code, current, target, actor, comment, _now()))
        conn.commit()
        print(f"✅ {code}: {current} → {target}")
    finally:
        conn.close()


# ===========================================================================
# 6. Weekly timetable (text view)
# ===========================================================================

@log_menu_navigation(description="Viewing timetable")
def view_timetable(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        term_id = _pick_term(conn.cursor(), "Term to view timetable for")
    finally:
        conn.close()
    if term_id is None:
        return
    while True:
        _run("show timetable", _print_timetable, term_id)
        if not editable:
            return
        print("\n1. Add meeting time   2. Remove meeting time   0. Back")
        choice = _prompt("Choice: ")
        if choice == "1":
            _run("add meeting time", _add_meeting, auth, term_id)
        elif choice == "2":
            _run("remove meeting time", _remove_meeting, auth, term_id)
        else:
            return


def _print_timetable(term_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT s.course_code, s.section_number, m.day_of_week, m.start_time, "
            "m.end_time, m.location FROM section_meetings m "
            "JOIN course_sections s ON m.section_id = s.id "
            "WHERE s.term_id=? ORDER BY m.day_of_week, m.start_time", (term_id,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo meeting times scheduled for this term.")
            return
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                "Saturday", "Sunday"]
        by_day = {}
        for code, sec, day, start, end, loc in rows:
            by_day.setdefault(day, []).append((start, end, code, sec, loc))
        print(f"\nWeekly timetable (term {term_id}):")
        ordered = sorted(by_day, key=lambda d: days.index(d) if d in days else 99)
        for day in ordered:
            print(f"\n  {day}")
            for start, end, code, sec, loc in sorted(
                    by_day[day], key=lambda t: _to_minutes(t[0]) or 0):
                loc_str = f"  @ {loc}" if loc else ""
                print(f"    {start}-{end}  {code} ({sec}){loc_str}")
    finally:
        conn.close()


def _pick_section_in_term(cur, term_id):
    cur.execute("SELECT id, course_code, section_number FROM course_sections "
                "WHERE term_id=? ORDER BY course_code, section_number", (term_id,))
    rows = cur.fetchall()
    if not rows:
        print("No sections in this term — add sections first.")
        return None
    valid = {str(r[0]): r for r in rows}
    for r in rows:
        print(f"  [{r[0]}] {r[1]} section {r[2]}")
    sid = _prompt("Section ID (blank to cancel): ")
    if sid not in valid:
        print("Cancelled / invalid.")
        return None
    return sid


@log_create(module="course_management", description="Adding meeting time")
def _add_meeting(auth, term_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sid = _pick_section_in_term(cur, term_id)
        if sid is None:
            return
        day = _prompt("Day of week (e.g. Monday): ")
        start = _prompt("Start (HH:MM) [09:00]: ") or "09:00"
        end = _prompt("End (HH:MM) [10:00]: ") or "10:00"
        sm, em = _to_minutes(start), _to_minutes(end)
        if sm is None or em is None:
            print("Times must be HH:MM.")
            return
        if em <= sm:
            print("End time must be after start time.")
            return
        location = _prompt("Location: ")
        cur.execute("INSERT INTO section_meetings (section_id, day_of_week, start_time, "
                    "end_time, location, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (sid, day, start, end, location, _now()))
        conn.commit()
        print("✅ Meeting time added.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing meeting time")
def _remove_meeting(auth, term_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sid = _pick_section_in_term(cur, term_id)
        if sid is None:
            return
        cur.execute("SELECT id, day_of_week, start_time, end_time FROM section_meetings "
                    "WHERE section_id=? ORDER BY day_of_week, start_time", (sid,))
        rows = cur.fetchall()
        if not rows:
            print("No meeting times for that section.")
            return
        for r in rows:
            print(f"  [{r[0]}] {r[1]} {r[2]}-{r[3]}")
        mid = _prompt("Meeting ID to remove (blank to cancel): ")
        if not mid:
            return
        cur.execute("DELETE FROM section_meetings WHERE id=? AND section_id=?", (mid, sid))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


# ===========================================================================
# 7. Term rollover / clone
# ===========================================================================

@log_update(module="course_management", description="Running term rollover")
def term_rollover(auth):
    if not _require_login(auth):
        return
    if not _can_edit(auth):
        print("You don't have permission to run term rollover.")
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        print("Source term:")
        src = _pick_term(cur, "Copy FROM term ID")
        if src is None:
            return
        print("Target term:")
        dst = _pick_term(cur, "Copy TO term ID")
        if dst is None:
            return
        if src == dst:
            print("Source and target must differ.")
            return
        reset = (_prompt("Reset enrolment to 0 in copies? (Y/n): ") or "y").lower() != "n"
        copy_meetings = (_prompt("Copy meeting times too? (Y/n): ") or "y").lower() != "n"
        skip_existing = (_prompt("Skip sections already in target? (Y/n): ") or "y").lower() != "n"

        cur.execute("SELECT id, course_code, section_number, instructor, capacity, "
                    "enrolled, delivery_mode, location, status, notes "
                    "FROM course_sections WHERE term_id=?", (src,))
        source_rows = cur.fetchall()
        if not source_rows:
            print("Source term has no sections.")
            return
        copied = skipped = meetings_copied = 0
        for row in source_rows:
            (old_id, code, sec, instructor, cap, enrolled, mode, location,
             status, notes) = row
            if skip_existing:
                cur.execute("SELECT 1 FROM course_sections WHERE course_code=? "
                            "AND term_id=? AND section_number=?", (code, dst, sec))
                if cur.fetchone():
                    skipped += 1
                    continue
            try:
                cur.execute(
                    "INSERT INTO course_sections (course_code, term_id, section_number, "
                    "instructor, capacity, enrolled, delivery_mode, location, status, "
                    "notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (code, dst, sec, instructor, cap, 0 if reset else enrolled, mode,
                     location, status, notes, _now(), _now()))
            except sqlite3.IntegrityError:
                skipped += 1
                continue
            new_id = cur.lastrowid
            copied += 1
            if copy_meetings:
                cur.execute("SELECT day_of_week, start_time, end_time, location "
                            "FROM section_meetings WHERE section_id=?", (old_id,))
                for m in cur.fetchall():
                    cur.execute("INSERT INTO section_meetings (section_id, day_of_week, "
                                "start_time, end_time, location, created_at) "
                                "VALUES (?, ?, ?, ?, ?, ?)", (new_id,) + tuple(m) + (_now(),))
                    meetings_copied += 1
        conn.commit()
        print(f"\n✅ Rollover complete. Sections copied: {copied}, "
              f"skipped: {skipped}, meeting times copied: {meetings_copied}.")
    finally:
        conn.close()


# ===========================================================================
# 8. Cross-listing & equivalency
# ===========================================================================

_SYMMETRIC_RELATIONS = {"Cross-listed", "Equivalent"}


@log_menu_navigation(description="Managing cross-listings")
def manage_crosslistings(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        code = _pick_course(conn.cursor(), "Course to manage cross-listings for")
    finally:
        conn.close()
    if not code:
        return
    while True:
        print(f"\n--- CROSS-LISTING for {code} ---")
        print("1. List links")
        if editable:
            print("2. Add link   3. Remove link")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("list cross-listings", _list_crosslistings, code)
        elif choice == "2" and editable:
            _run("add cross-listing", _add_crosslisting, auth, code)
        elif choice == "3" and editable:
            _run("remove cross-listing", _remove_crosslisting, auth, code)
        else:
            print("Invalid choice.")
        _pause()


def _list_crosslistings(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, related_code, relation_type, notes "
                    "FROM course_crosslistings WHERE course_code=? "
                    "ORDER BY relation_type, related_code", (code,))
        rows = cur.fetchall()
        if not rows:
            print("\nNo cross-listings.")
            return
        print(f"\n{'ID':<5}{'Related':<12}{'Relation':<20}{'Notes'}")
        print("-" * 55)
        for r in rows:
            print(f"{r[0]:<5}{(r[1] or ''):<12}{(r[2] or ''):<20}{r[3] or ''}")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding cross-listing")
def _add_crosslisting(auth, code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        related = _pick_course(cur, "Related course")
        if not related:
            return
        if related == code:
            print("A course cannot be linked to itself.")
            return
        print("Relations: Cross-listed, Equivalent, Transfer Equivalent")
        rtype = _prompt("Relation [Cross-listed]: ") or "Cross-listed"
        notes = _prompt("Notes: ")
        cur.execute("INSERT OR IGNORE INTO course_crosslistings (course_code, "
                    "related_code, relation_type, notes, created_at) VALUES (?,?,?,?,?)",
                    (code, related, rtype, notes, _now()))
        if rtype in _SYMMETRIC_RELATIONS:
            cur.execute("INSERT OR IGNORE INTO course_crosslistings (course_code, "
                        "related_code, relation_type, notes, created_at) VALUES (?,?,?,?,?)",
                        (related, code, rtype, notes, _now()))
        conn.commit()
        print(f"✅ {rtype} link added between {code} and {related}.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing cross-listing")
def _remove_crosslisting(auth, code):
    _list_crosslistings(code)
    conn = get_connection()
    try:
        cur = conn.cursor()
        lid = _prompt("Link ID to remove (blank to cancel): ")
        if not lid:
            return
        cur.execute("SELECT related_code, relation_type FROM course_crosslistings "
                    "WHERE id=? AND course_code=?", (lid, code))
        row = cur.fetchone()
        if not row:
            print("Invalid link ID.")
            return
        related, rtype = row[0], row[1]
        cur.execute("DELETE FROM course_crosslistings WHERE id=?", (lid,))
        if rtype in _SYMMETRIC_RELATIONS:
            cur.execute("DELETE FROM course_crosslistings WHERE course_code=? "
                        "AND related_code=? AND relation_type=?", (related, code, rtype))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


# ===========================================================================
# 9. Grading scheme & assessment weighting
# ===========================================================================

@log_menu_navigation(description="Managing grading schemes")
def manage_grading_schemes(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        code = _pick_course(conn.cursor(), "Course to manage grading for")
    finally:
        conn.close()
    if not code:
        return
    while True:
        print(f"\n--- GRADING for {code} ---")
        print("1. View scheme & components")
        if editable:
            print("2. Set scheme       3. Add component")
            print("4. Remove component")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("view grading scheme", _view_grading, code)
        elif choice == "2" and editable:
            _run("set grading scheme", _set_scheme, auth, code)
        elif choice == "3" and editable:
            _run("add component", _add_component, auth, code)
        elif choice == "4" and editable:
            _run("remove component", _remove_component, auth, code)
        else:
            print("Invalid choice.")
        _pause()


def _view_grading(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT scheme_type, pass_mark FROM course_grading_schemes "
                    "WHERE course_code=?", (code,))
        row = cur.fetchone()
        if row:
            print(f"\nScheme: {row[0]}   Pass mark: {row[1]:g}%")
        else:
            print("\nNo grading scheme set (defaults to Letter).")
        cur.execute("SELECT id, name, weight, notes FROM course_assessment_components "
                    "WHERE course_code=? ORDER BY id", (code,))
        rows = cur.fetchall()
        if not rows:
            print("No assessment components.")
            return
        total = 0.0
        print(f"\n{'ID':<5}{'Component':<24}{'Weight %':<10}{'Notes'}")
        print("-" * 55)
        for r in rows:
            total += r[2] or 0.0
            print(f"{r[0]:<5}{(r[1] or ''):<24}{(r[2] or 0):<10g}{r[3] or ''}")
        warn = "" if abs(total - 100.0) < 0.01 else "  ⚠ should total 100%"
        print(f"\nTotal weight: {total:g}%{warn}")
    finally:
        conn.close()


@log_update(module="course_management", description="Setting grading scheme")
def _set_scheme(auth, code):
    print("Types: Letter, Pass/Fail, Percentage, Competency, Credit/No Credit")
    stype = _prompt("Scheme type [Letter]: ") or "Letter"
    pass_mark = _read_float("Pass mark % [50]: ", default=50.0, minimum=0, maximum=100)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO course_grading_schemes (course_code, scheme_type, pass_mark, "
            "updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(course_code) DO UPDATE SET scheme_type=excluded.scheme_type, "
            "pass_mark=excluded.pass_mark, updated_at=excluded.updated_at",
            (code, stype, pass_mark, _now()))
        conn.commit()
        print(f"✅ Grading scheme saved for {code}.")
    finally:
        conn.close()


@log_create(module="course_management", description="Adding assessment component")
def _add_component(auth, code):
    name = _prompt("Component name: ")
    if not name:
        print("Cancelled — name is required.")
        return
    weight = _read_float("Weight % [0]: ", default=0.0, minimum=0, maximum=100)
    notes = _prompt("Notes: ")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO course_assessment_components (course_code, name, "
                     "weight, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                     (code, name, weight, notes, _now()))
        conn.commit()
        print("✅ Component added.")
    finally:
        conn.close()


@log_delete(module="course_management", description="Removing assessment component")
def _remove_component(auth, code):
    _view_grading(code)
    cid = _prompt("Component ID to remove (blank to cancel): ")
    if not cid:
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM course_assessment_components WHERE id=? "
                     "AND course_code=?", (cid, code))
        conn.commit()
        print("✅ Removed.")
    finally:
        conn.close()


# ===========================================================================
# 10. Waitlist auto-promotion rules
# ===========================================================================

@log_menu_navigation(description="Managing waitlist automation")
def manage_waitlist_rules(auth):
    if not _require_login(auth):
        return
    editable = _can_edit(auth)
    conn = get_connection()
    try:
        code = _pick_course(conn.cursor(), "Course to manage waitlist rules for")
    finally:
        conn.close()
    if not code:
        return
    while True:
        print(f"\n--- WAITLIST AUTOMATION for {code} ---")
        print("1. View rule & waitlist   2. Preview promotions")
        if editable:
            print("3. Set rule               4. Run promotion now")
        print("0. Back")
        choice = _prompt("Choice: ")
        if choice == "0":
            return
        if choice == "1":
            _run("view waitlist", _view_waitlist_rule, code)
        elif choice == "2":
            _run("preview promotions", _promotion_action, code, commit=False)
        elif choice == "3" and editable:
            _run("set waitlist rule", _set_waitlist_rule, auth, code)
        elif choice == "4" and editable:
            _run("run promotion", _promotion_action, code, commit=True, auth=auth)
        else:
            print("Invalid choice.")
        _pause()


def _free_seats(cur, code):
    cur.execute("SELECT COALESCE(max_enrollment,0), COALESCE(current_enrollment,0) "
                "FROM courses WHERE COALESCE(course_code, code)=?", (code,))
    row = cur.fetchone()
    if not row:
        return 0
    return max(0, int(row[0]) - int(row[1]))


def _waitlist_candidates(cur, code):
    try:
        cur.execute("SELECT id, student_id, position, added_at, COALESCE(status,'') "
                    "FROM course_waitlist WHERE course_id=? "
                    "ORDER BY position ASC, added_at ASC", (code,))
        rows = cur.fetchall()
    except sqlite3.Error:
        logger.exception("Could not read course_waitlist")
        print("Waitlist table is not available in this database.")
        return []
    return [r for r in rows if str(r[4]).strip().lower() not in _DONE_WAITLIST_STATUSES]


def _view_waitlist_rule(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT auto_promote, promotion_order, notify, max_auto, active "
                    "FROM waitlist_rules WHERE course_code=?", (code,))
        row = cur.fetchone()
        if row:
            print(f"\nAuto-promote: {'Yes' if row[0] else 'No'}   Order: {row[1]}   "
                  f"Notify: {'Yes' if row[2] else 'No'}   Max/run: {row[3]}   "
                  f"Active: {'Yes' if row[4] else 'No'}")
        else:
            print("\nNo rule configured (defaults: manual, FIFO).")
        free = _free_seats(cur, code)
        cands = _waitlist_candidates(cur, code)
        print(f"Free seats: {free}   Waiting: {len(cands)}")
        for i, c in enumerate(cands, 1):
            print(f"  {i}. {c[1]} (position {c[2]}, added {c[3]})")
    finally:
        conn.close()


@log_update(module="course_management", description="Setting waitlist rule")
def _set_waitlist_rule(auth, code):
    auto = (_prompt("Auto-promote when a seat frees? (y/N): ") or "n").lower() == "y"
    order = _prompt("Promotion order [FIFO]: ") or "FIFO"
    notify = (_prompt("Notify promoted students? (Y/n): ") or "y").lower() != "n"
    max_auto = _read_int("Max auto-promotions per run (0 = no limit) [0]: ",
                         default=0, minimum=0)
    active = (_prompt("Rule active? (Y/n): ") or "y").lower() != "n"
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO waitlist_rules (course_code, auto_promote, promotion_order, "
            "notify, max_auto, active, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(course_code) DO UPDATE SET auto_promote=excluded.auto_promote, "
            "promotion_order=excluded.promotion_order, notify=excluded.notify, "
            "max_auto=excluded.max_auto, active=excluded.active, "
            "updated_at=excluded.updated_at",
            (code, 1 if auto else 0, order, 1 if notify else 0, max_auto,
             1 if active else 0, _now()))
        conn.commit()
        print(f"✅ Waitlist rule saved for {code}.")
    finally:
        conn.close()


def _promotion_action(code, *, commit, auth=None):
    """Compute (and optionally apply) the promotion plan for a course."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        free = _free_seats(cur, code)
        cands = _waitlist_candidates(cur, code)
        cur.execute("SELECT max_auto FROM waitlist_rules WHERE course_code=?", (code,))
        row = cur.fetchone()
        max_auto = int(row[0]) if row and row[0] is not None else 0
        if free <= 0 or not cands:
            print(f"\nNo promotions possible (free seats: {free}, waiting: {len(cands)}).")
            return
        limit = free if max_auto <= 0 else min(free, max_auto)
        plan = cands[:limit]
        print(f"\n{len(plan)} student(s) would be promoted for {code} "
              f"(free seats: {free}):")
        for c in plan:
            print(f"  • {c[1]} (position {c[2]})")
        if not commit:
            return
        if _prompt(f"Promote these {len(plan)} student(s)? (y/n): ").lower() != "y":
            print("Cancelled.")
            return
        ids = [c[0] for c in plan]
        placeholders = ",".join("?" for _ in ids)
        cur.execute(f"UPDATE course_waitlist SET status='Promoted' "
                    f"WHERE id IN ({placeholders})", ids)
        cur.execute("UPDATE courses SET current_enrollment = "
                    "COALESCE(current_enrollment,0) + ? "
                    "WHERE COALESCE(course_code, code)=?", (len(ids), code))
        conn.commit()
        for c in plan:
            logger.info("Waitlist promotion: course=%s student=%s", code, c[1])
        print(f"✅ Promoted {len(ids)} student(s) for {code}.")
    finally:
        conn.close()


# ===========================================================================
# Submenu
# ===========================================================================

@log_menu_navigation(description="Displaying curriculum extensions menu")
def display_curriculum_extensions_menu(auth):
    """Submenu exposing the ten curriculum-extension features in the CLI."""
    if not _require_login(auth):
        return

    ensure_extension_schema()

    can_view = bool(auth.check_permission("view_courses")
                    or auth.check_permission("manage_courses"))
    if not can_view:
        print(get_text("course_mgmt.no_permission",
                       default="You don't have permission to view courses."))
        return

    options = {
        "1": ("Academic terms & course sections", manage_terms_and_sections),
        "2": ("Co-requisites & enrolment restrictions", manage_corequisites_and_restrictions),
        "3": ("Syllabus & course materials", manage_course_materials),
        "4": ("Learning outcomes & curriculum mapping", manage_learning_outcomes),
        "5": ("Course approval workflow", manage_course_approvals),
        "6": ("Weekly timetable", view_timetable),
        "7": ("Term rollover / clone", term_rollover),
        "8": ("Cross-listing & equivalency", manage_crosslistings),
        "9": ("Grading scheme & weighting", manage_grading_schemes),
        "10": ("Waitlist automation rules", manage_waitlist_rules),
    }

    while True:
        print("\n" + "=" * 70)
        print("CURRICULUM EXTENSIONS".center(70))
        print("=" * 70)
        for key in sorted(options, key=int):
            print(f"  {key:>2}. {options[key][0]}")
        print("   0. Back")

        choice = _prompt("\nEnter your choice (0-10): ")
        if choice == "0":
            return
        entry = options.get(choice)
        if not entry:
            print("Invalid choice.")
            continue
        label, handler = entry
        _run(f"open {label}", handler, auth)
