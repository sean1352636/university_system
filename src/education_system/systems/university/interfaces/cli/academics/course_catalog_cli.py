"""Course Catalog CLI menu.

Provides a command-line interface for managing the course catalog,
including courses, prerequisites, and course offerings. Menu options
are dynamically rendered based on the authenticated user's role.
"""

import logging
import uuid

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Database initialisation
# ------------------------------------------------------------------ #

_VALID_COURSE_COLUMNS = frozenset({
    "name", "description", "credits", "department", "level",
})

_VALID_OFFERING_COLUMNS = frozenset({
    "instructor", "schedule", "location", "room",
    "max_enrollment", "status",
})


def _init_tables():
    """Create the course catalog tables if they do not already exist."""
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS courses (
                    course_code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    credits INTEGER,
                    department TEXT,
                    level TEXT,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_modified TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_prerequisites (
                    course_code TEXT,
                    prerequisite_code TEXT,
                    PRIMARY KEY (course_code, prerequisite_code),
                    FOREIGN KEY (course_code)
                        REFERENCES courses(course_code) ON DELETE CASCADE,
                    FOREIGN KEY (prerequisite_code)
                        REFERENCES courses(course_code) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_offerings (
                    offering_id TEXT PRIMARY KEY,
                    course_code TEXT,
                    academic_year TEXT,
                    semester TEXT,
                    instructor TEXT,
                    schedule TEXT,
                    location TEXT,
                    room TEXT,
                    max_enrollment INTEGER DEFAULT 0,
                    current_enrollment INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'Open',
                    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_modified TIMESTAMP,
                    FOREIGN KEY (course_code)
                        REFERENCES courses(course_code) ON DELETE CASCADE
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error("Error initialising course catalog tables: %s", e)


# ------------------------------------------------------------------ #
#  Entry point
# ------------------------------------------------------------------ #


def display_course_catalog_menu(auth=None):
    """Display the course catalog management CLI menu."""
    if not auth or not auth.current_user:
        print("\n--- Please log in to access the course catalog.")
        input("Press Enter to continue...")
        return

    _init_tables()

    role = auth.current_user.get("role", "").lower()
    is_admin = role == "admin"

    while True:
        print("\n" + "=" * 60)
        print("      COURSE CATALOG MANAGEMENT")
        print("=" * 60)

        option_num = 1
        options = {}

        # Options available to all authenticated users
        print(f"{option_num}. List All Courses")
        options[str(option_num)] = "list_all"
        option_num += 1

        print(f"{option_num}. Search Courses")
        options[str(option_num)] = "search"
        option_num += 1

        print(f"{option_num}. View Course Details")
        options[str(option_num)] = "details"
        option_num += 1

        print(f"{option_num}. View Course Offerings")
        options[str(option_num)] = "view_offerings"
        option_num += 1

        # Admin-only options
        if is_admin:
            print(f"{option_num}. Add New Course")
            options[str(option_num)] = "add_course"
            option_num += 1

            print(f"{option_num}. Update Course")
            options[str(option_num)] = "update_course"
            option_num += 1

            print(f"{option_num}. Delete Course")
            options[str(option_num)] = "delete_course"
            option_num += 1

            print(f"{option_num}. Add Prerequisite")
            options[str(option_num)] = "add_prereq"
            option_num += 1

            print(f"{option_num}. Remove Prerequisite")
            options[str(option_num)] = "remove_prereq"
            option_num += 1

            print(f"{option_num}. Add Course Offering")
            options[str(option_num)] = "add_offering"
            option_num += 1

            print(f"{option_num}. Update Course Offering")
            options[str(option_num)] = "update_offering"
            option_num += 1

            print(f"{option_num}. Delete Course Offering")
            options[str(option_num)] = "delete_offering"
            option_num += 1

        print(f"{option_num}. Return to Main Menu")
        options[str(option_num)] = "return"

        print("=" * 60)
        choice = input("\nEnter your choice: ").strip()

        if choice not in options:
            print("Invalid choice. Please try again.")
            continue

        action = options[choice]

        if action == "return":
            break
        elif action == "list_all":
            _list_all_courses()
        elif action == "search":
            _search_courses()
        elif action == "details":
            _get_course_details()
        elif action == "view_offerings":
            _view_course_offerings()
        elif action == "add_course":
            _add_course()
        elif action == "update_course":
            _update_course()
        elif action == "delete_course":
            _delete_course()
        elif action == "add_prereq":
            _add_prerequisite()
        elif action == "remove_prereq":
            _remove_prerequisite()
        elif action == "add_offering":
            _add_course_offering()
        elif action == "update_offering":
            _update_course_offering()
        elif action == "delete_offering":
            _delete_course_offering()


# ------------------------------------------------------------------ #
#  Course helpers
# ------------------------------------------------------------------ #


def _list_all_courses():
    """List every course in the catalog."""
    print("\n--- All Courses ---")
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT course_code, name, credits, department, level "
                "FROM courses ORDER BY course_code"
            ).fetchall()

        if not rows:
            print("\nThe course catalog is empty.")
            input("Press Enter to continue...")
            return

        print(
            f"\n{'Code':<12}{'Name':<35}{'Credits':<10}"
            f"{'Department':<20}{'Level':<8}"
        )
        print("-" * 85)
        for r in rows:
            print(
                f"{r[0]:<12}{(r[1] or ''):<35}{r[2] or '':<10}"
                f"{(r[3] or ''):<20}{(r[4] or ''):<8}"
            )
    except Exception as e:
        logger.error("Error listing courses: %s", e)
        print(f"\nError retrieving courses: {e}")

    input("\nPress Enter to continue...")


def _search_courses():
    """Search courses by name, code, or department."""
    print("\n--- Search Courses ---")
    print("Search by:")
    print("1. Name")
    print("2. Course Code")
    print("3. Department")

    search_choice = input("Enter your choice (1-3): ").strip()
    field_map = {"1": "name", "2": "course_code", "3": "department"}

    if search_choice not in field_map:
        print("Invalid search option.")
        input("Press Enter to continue...")
        return

    term = input("Enter search term: ").strip()
    if not term:
        print("Search term cannot be empty.")
        input("Press Enter to continue...")
        return

    field = field_map[search_choice]

    try:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT course_code, name, credits, department "
                f"FROM courses WHERE {field} LIKE ? ORDER BY course_code",
                (f"%{term}%",),
            ).fetchall()

        if not rows:
            print("\nNo courses found matching your search.")
        else:
            print(f"\n{'Code':<12}{'Name':<35}{'Credits':<10}{'Department':<20}")
            print("-" * 77)
            for r in rows:
                print(
                    f"{r[0]:<12}{(r[1] or ''):<35}{r[2] or '':<10}"
                    f"{(r[3] or ''):<20}"
                )
    except Exception as e:
        logger.error("Error searching courses: %s", e)
        print(f"\nError searching courses: {e}")

    input("\nPress Enter to continue...")


def _get_course_details():
    """Display detailed information for a single course."""
    print("\n--- Course Details ---")
    course_code = input("Enter course code: ").strip()
    if not course_code:
        print("Course code is required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT course_code, name, description, credits, department, "
                "level, date_added, last_modified "
                "FROM courses WHERE course_code = ?",
                (course_code,),
            ).fetchone()

            if not row:
                print(f"\nCourse {course_code} not found.")
                input("Press Enter to continue...")
                return

            print(f"\n  Code:         {row[0]}")
            print(f"  Name:         {row[1]}")
            print(f"  Description:  {row[2] or 'N/A'}")
            print(f"  Credits:      {row[3]}")
            print(f"  Department:   {row[4] or 'N/A'}")
            print(f"  Level:        {row[5] or 'N/A'}")
            print(f"  Date Added:   {row[6] or 'N/A'}")
            print(f"  Last Modified:{row[7] or 'N/A'}")

            # Prerequisites
            prereqs = conn.execute(
                "SELECT p.prerequisite_code, c.name "
                "FROM course_prerequisites p "
                "LEFT JOIN courses c ON p.prerequisite_code = c.course_code "
                "WHERE p.course_code = ?",
                (course_code,),
            ).fetchall()

            if prereqs:
                print("  Prerequisites:")
                for p in prereqs:
                    print(f"    - {p[0]}: {p[1] or 'Unknown'}")
            else:
                print("  Prerequisites: None")

    except Exception as e:
        logger.error("Error getting course details: %s", e)
        print(f"\nError retrieving course details: {e}")

    input("\nPress Enter to continue...")


def _add_course():
    """Add a new course to the catalog."""
    print("\n--- Add New Course ---")

    course_code = input("Course code (e.g. CIS1001): ").strip()
    if not course_code:
        print("Course code is required.")
        input("Press Enter to continue...")
        return

    name = input("Course name: ").strip()
    if not name:
        print("Course name is required.")
        input("Press Enter to continue...")
        return

    description = input("Description: ").strip()

    credits_str = input("Credits: ").strip()
    try:
        credits = int(credits_str) if credits_str else 0
    except ValueError:
        print("Invalid credits value. Using 0.")
        credits = 0

    department = input("Department: ").strip()
    level = input("Level (e.g. 100, 200): ").strip()

    try:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM courses WHERE course_code = ?",
                (course_code,),
            ).fetchone()[0]
            if existing:
                print(f"\nCourse {course_code} already exists.")
                input("Press Enter to continue...")
                return

            conn.execute(
                "INSERT INTO courses "
                "(course_code, name, description, credits, department, level) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (course_code, name, description, credits, department, level),
            )
            conn.commit()
            print(f"\nCourse {course_code}: {name} added successfully.")
    except Exception as e:
        logger.error("Error adding course: %s", e)
        print(f"\nError adding course: {e}")

    input("Press Enter to continue...")


def _update_course():
    """Update an existing course's information."""
    print("\n--- Update Course ---")

    course_code = input("Enter course code to update: ").strip()
    if not course_code:
        print("Course code is required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT name, description, credits, department, level "
                "FROM courses WHERE course_code = ?",
                (course_code,),
            ).fetchone()

            if not existing:
                print(f"\nCourse {course_code} not found.")
                input("Press Enter to continue...")
                return

            print(f"\nCurrent values for {course_code}:")
            print(f"  Name:        {existing[0]}")
            print(f"  Description: {existing[1]}")
            print(f"  Credits:     {existing[2]}")
            print(f"  Department:  {existing[3]}")
            print(f"  Level:       {existing[4]}")
            print("\nLeave fields blank to keep current values.")

            updates = {}

            name = input("New name: ").strip()
            if name:
                updates["name"] = name

            description = input("New description: ").strip()
            if description:
                updates["description"] = description

            credits_str = input("New credits: ").strip()
            if credits_str:
                try:
                    updates["credits"] = int(credits_str)
                except ValueError:
                    print("Invalid credits value. Skipping.")

            department = input("New department: ").strip()
            if department:
                updates["department"] = department

            level = input("New level: ").strip()
            if level:
                updates["level"] = level

            if not updates:
                print("No changes specified.")
                input("Press Enter to continue...")
                return

            # Build safe UPDATE using only validated column names
            set_parts = []
            values = []
            for col, val in updates.items():
                if col not in _VALID_COURSE_COLUMNS:
                    continue
                set_parts.append(f"{col} = ?")
                values.append(val)

            if not set_parts:
                print("No valid changes specified.")
                input("Press Enter to continue...")
                return

            set_parts.append("last_modified = CURRENT_TIMESTAMP")
            values.append(course_code)

            conn.execute(
                f"UPDATE courses SET {', '.join(set_parts)} "
                f"WHERE course_code = ?",
                values,
            )
            conn.commit()
            print(f"\nCourse {course_code} updated successfully.")
    except Exception as e:
        logger.error("Error updating course: %s", e)
        print(f"\nError updating course: {e}")

    input("Press Enter to continue...")


def _delete_course():
    """Delete a course from the catalog."""
    print("\n--- Delete Course ---")

    course_code = input("Enter course code to delete: ").strip()
    if not course_code:
        print("Course code is required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM courses WHERE course_code = ?",
                (course_code,),
            ).fetchone()

            if not row:
                print(f"\nCourse {course_code} not found.")
                input("Press Enter to continue...")
                return

            confirm = input(
                f"Are you sure you want to delete {course_code}: {row[0]}? (yes/no): "
            ).strip()
            if confirm.lower() != "yes":
                print("Deletion cancelled.")
                input("Press Enter to continue...")
                return

            conn.execute(
                "DELETE FROM course_prerequisites WHERE course_code = ? "
                "OR prerequisite_code = ?",
                (course_code, course_code),
            )
            conn.execute(
                "DELETE FROM course_offerings WHERE course_code = ?",
                (course_code,),
            )
            conn.execute(
                "DELETE FROM courses WHERE course_code = ?",
                (course_code,),
            )
            conn.commit()
            print(f"\nCourse {course_code}: {row[0]} deleted successfully.")
    except Exception as e:
        logger.error("Error deleting course: %s", e)
        print(f"\nError deleting course: {e}")

    input("Press Enter to continue...")


# ------------------------------------------------------------------ #
#  Prerequisite helpers
# ------------------------------------------------------------------ #


def _check_circular_dependency(conn, course_code, prerequisite_code):
    """Return True if adding the prerequisite would create a cycle."""
    if course_code == prerequisite_code:
        return True

    visited = set()
    stack = [prerequisite_code]

    while stack:
        current = stack.pop()
        if current == course_code:
            return True
        if current in visited:
            continue
        visited.add(current)

        rows = conn.execute(
            "SELECT prerequisite_code FROM course_prerequisites "
            "WHERE course_code = ?",
            (current,),
        ).fetchall()
        for r in rows:
            stack.append(r[0])

    return False


def _add_prerequisite():
    """Add a prerequisite to a course."""
    print("\n--- Add Prerequisite ---")

    course_code = input("Course code: ").strip()
    prerequisite_code = input("Prerequisite course code: ").strip()

    if not course_code or not prerequisite_code:
        print("Both course code and prerequisite code are required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            # Verify both courses exist
            for code, label in [
                (course_code, "Course"),
                (prerequisite_code, "Prerequisite course"),
            ]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM courses WHERE course_code = ?",
                    (code,),
                ).fetchone()[0]
                if not count:
                    print(f"\n{label} {code} not found.")
                    input("Press Enter to continue...")
                    return

            # Check for duplicate
            dup = conn.execute(
                "SELECT COUNT(*) FROM course_prerequisites "
                "WHERE course_code = ? AND prerequisite_code = ?",
                (course_code, prerequisite_code),
            ).fetchone()[0]
            if dup:
                print(
                    f"\n{prerequisite_code} is already a prerequisite "
                    f"for {course_code}."
                )
                input("Press Enter to continue...")
                return

            # Circular dependency check
            if _check_circular_dependency(conn, course_code, prerequisite_code):
                print(
                    f"\nAdding {prerequisite_code} as a prerequisite for "
                    f"{course_code} would create a circular dependency."
                )
                input("Press Enter to continue...")
                return

            conn.execute(
                "INSERT INTO course_prerequisites "
                "(course_code, prerequisite_code) VALUES (?, ?)",
                (course_code, prerequisite_code),
            )
            conn.execute(
                "UPDATE courses SET last_modified = CURRENT_TIMESTAMP "
                "WHERE course_code = ?",
                (course_code,),
            )
            conn.commit()
            print(
                f"\nAdded {prerequisite_code} as a prerequisite "
                f"for {course_code}."
            )
    except Exception as e:
        logger.error("Error adding prerequisite: %s", e)
        print(f"\nError adding prerequisite: {e}")

    input("Press Enter to continue...")


def _remove_prerequisite():
    """Remove a prerequisite from a course."""
    print("\n--- Remove Prerequisite ---")

    course_code = input("Course code: ").strip()
    prerequisite_code = input("Prerequisite course code to remove: ").strip()

    if not course_code or not prerequisite_code:
        print("Both course code and prerequisite code are required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM course_prerequisites "
                "WHERE course_code = ? AND prerequisite_code = ?",
                (course_code, prerequisite_code),
            ).fetchone()[0]

            if not count:
                print(
                    f"\n{prerequisite_code} is not a prerequisite "
                    f"for {course_code}."
                )
                input("Press Enter to continue...")
                return

            conn.execute(
                "DELETE FROM course_prerequisites "
                "WHERE course_code = ? AND prerequisite_code = ?",
                (course_code, prerequisite_code),
            )
            conn.execute(
                "UPDATE courses SET last_modified = CURRENT_TIMESTAMP "
                "WHERE course_code = ?",
                (course_code,),
            )
            conn.commit()
            print(
                f"\nRemoved {prerequisite_code} as a prerequisite "
                f"for {course_code}."
            )
    except Exception as e:
        logger.error("Error removing prerequisite: %s", e)
        print(f"\nError removing prerequisite: {e}")

    input("Press Enter to continue...")


# ------------------------------------------------------------------ #
#  Course offering helpers
# ------------------------------------------------------------------ #


def _view_course_offerings():
    """View course offerings for a given academic year and semester."""
    print("\n--- View Course Offerings ---")

    academic_year = input("Academic year (e.g. 2026): ").strip()
    semester = input("Semester (e.g. Fall, Spring): ").strip()

    if not academic_year or not semester:
        print("Academic year and semester are required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT o.offering_id, o.course_code, c.name, o.instructor, "
                "o.schedule, o.room, o.max_enrollment, o.current_enrollment, "
                "o.status "
                "FROM course_offerings o "
                "JOIN courses c ON o.course_code = c.course_code "
                "WHERE o.academic_year = ? AND LOWER(o.semester) = LOWER(?) "
                "ORDER BY o.course_code",
                (academic_year, semester),
            ).fetchall()

        if not rows:
            print(
                f"\nNo offerings found for {semester} {academic_year}."
            )
            input("Press Enter to continue...")
            return

        print(
            f"\nOfferings for {semester} {academic_year}:\n"
        )
        print(
            f"{'ID':<38}{'Code':<12}{'Course':<25}{'Instructor':<16}"
            f"{'Schedule':<18}{'Room':<10}{'Enroll':<12}{'Status':<8}"
        )
        print("-" * 139)
        for r in rows:
            enroll = f"{r[7] or 0}/{r[6] or 0}"
            print(
                f"{(r[0] or ''):<38}{r[1]:<12}{(r[2] or ''):<25}"
                f"{(r[3] or ''):<16}{(r[4] or ''):<18}{(r[5] or ''):<10}"
                f"{enroll:<12}{(r[8] or ''):<8}"
            )
    except Exception as e:
        logger.error("Error viewing offerings: %s", e)
        print(f"\nError retrieving course offerings: {e}")

    input("\nPress Enter to continue...")


def _add_course_offering():
    """Add a new course offering."""
    print("\n--- Add Course Offering ---")

    course_code = input("Course code: ").strip()
    if not course_code:
        print("Course code is required.")
        input("Press Enter to continue...")
        return

    academic_year = input("Academic year: ").strip()
    semester = input("Semester (e.g. Fall, Spring): ").strip()
    instructor = input("Instructor: ").strip()
    room = input("Room: ").strip()
    schedule = input("Schedule (e.g. MWF 10:00-11:00): ").strip()

    capacity_str = input("Max enrollment (default 30): ").strip()
    try:
        max_enrollment = int(capacity_str) if capacity_str else 30
    except ValueError:
        print("Invalid capacity. Using default of 30.")
        max_enrollment = 30

    try:
        with get_connection() as conn:
            exists = conn.execute(
                "SELECT COUNT(*) FROM courses WHERE course_code = ?",
                (course_code,),
            ).fetchone()[0]
            if not exists:
                print(f"\nCourse {course_code} not found.")
                input("Press Enter to continue...")
                return

            offering_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO course_offerings "
                "(offering_id, course_code, academic_year, semester, "
                "instructor, schedule, room, max_enrollment) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    offering_id, course_code, academic_year, semester,
                    instructor, schedule, room, max_enrollment,
                ),
            )
            conn.commit()
            print(
                f"\nCourse offering added successfully "
                f"(ID: {offering_id})."
            )
    except Exception as e:
        logger.error("Error adding course offering: %s", e)
        print(f"\nError adding course offering: {e}")

    input("Press Enter to continue...")


def _update_course_offering():
    """Update an existing course offering."""
    print("\n--- Update Course Offering ---")

    offering_id = input("Offering ID: ").strip()
    if not offering_id:
        print("Offering ID is required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT course_code, instructor, schedule, room, "
                "max_enrollment, status "
                "FROM course_offerings WHERE offering_id = ?",
                (offering_id,),
            ).fetchone()

            if not row:
                print(f"\nOffering {offering_id} not found.")
                input("Press Enter to continue...")
                return

            print("\nCurrent values:")
            print(f"  Course:        {row[0]}")
            print(f"  Instructor:    {row[1]}")
            print(f"  Schedule:      {row[2]}")
            print(f"  Room:          {row[3]}")
            print(f"  Max Enrollment:{row[4]}")
            print(f"  Status:        {row[5]}")
            print("\nLeave fields blank to keep current values.")

            updates = {}

            instructor = input("New instructor: ").strip()
            if instructor:
                updates["instructor"] = instructor

            schedule = input("New schedule: ").strip()
            if schedule:
                updates["schedule"] = schedule

            room = input("New room: ").strip()
            if room:
                updates["room"] = room

            capacity_str = input("New max enrollment: ").strip()
            if capacity_str:
                try:
                    updates["max_enrollment"] = int(capacity_str)
                except ValueError:
                    print("Invalid capacity value. Skipping.")

            status = input("New status (Open/Closed/Cancelled): ").strip()
            if status:
                updates["status"] = status

            if not updates:
                print("No changes specified.")
                input("Press Enter to continue...")
                return

            set_parts = []
            values = []
            for col, val in updates.items():
                if col not in _VALID_OFFERING_COLUMNS:
                    continue
                set_parts.append(f"{col} = ?")
                values.append(val)

            if not set_parts:
                print("No valid changes specified.")
                input("Press Enter to continue...")
                return

            set_parts.append("last_modified = CURRENT_TIMESTAMP")
            values.append(offering_id)

            conn.execute(
                f"UPDATE course_offerings SET {', '.join(set_parts)} "
                f"WHERE offering_id = ?",
                values,
            )
            conn.commit()
            print(f"\nOffering {offering_id} updated successfully.")
    except Exception as e:
        logger.error("Error updating course offering: %s", e)
        print(f"\nError updating course offering: {e}")

    input("Press Enter to continue...")


def _delete_course_offering():
    """Delete a course offering."""
    print("\n--- Delete Course Offering ---")

    offering_id = input("Offering ID to delete: ").strip()
    if not offering_id:
        print("Offering ID is required.")
        input("Press Enter to continue...")
        return

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT course_code, semester, academic_year "
                "FROM course_offerings WHERE offering_id = ?",
                (offering_id,),
            ).fetchone()

            if not row:
                print(f"\nOffering {offering_id} not found.")
                input("Press Enter to continue...")
                return

            confirm = input(
                f"Are you sure you want to delete the offering for "
                f"{row[0]} ({row[1]} {row[2]})? (yes/no): "
            ).strip()
            if confirm.lower() != "yes":
                print("Deletion cancelled.")
                input("Press Enter to continue...")
                return

            conn.execute(
                "DELETE FROM course_offerings WHERE offering_id = ?",
                (offering_id,),
            )
            conn.commit()
            print(
                f"\nOffering for {row[0]} in {row[1]} {row[2]} "
                f"deleted successfully."
            )
    except Exception as e:
        logger.error("Error deleting course offering: %s", e)
        print(f"\nError deleting course offering: {e}")

    input("Press Enter to continue...")
