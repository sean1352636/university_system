"""
Tests for course_catalog_cli — the CLI menu for course catalog management.

Tests cover table initialization, CRUD for courses / prerequisites / offerings,
menu navigation, role-based access, and circular dependency detection.
"""

import sqlite3
import pytest
from unittest.mock import Mock, patch, MagicMock

MODULE = (
    "education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_auth_admin():
    """Create a mock authentication object with an admin user."""
    auth = Mock()
    auth.current_user = {
        "id": 1,
        "user_id": 1,
        "username": "admin_user",
        "role": "admin",
        "display_name": "Admin User",
    }
    return auth


@pytest.fixture
def mock_auth_student():
    """Create a mock authentication object with a student user."""
    auth = Mock()
    auth.current_user = {
        "id": 42,
        "user_id": 42,
        "username": "jdoe",
        "role": "student",
        "student_id": "STU0042",
        "display_name": "Jane Doe",
    }
    return auth


@pytest.fixture
def mem_conn():
    """Create an in-memory SQLite connection with catalog tables."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""
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
    cur.execute("""
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
    cur.execute("""
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
    return conn


def _seed_courses(conn):
    """Insert sample courses for testing."""
    conn.execute(
        "INSERT INTO courses (course_code, name, credits, department, level) "
        "VALUES (?, ?, ?, ?, ?)",
        ("CIS1001", "Intro to CS", 3, "Computer Science", "100"),
    )
    conn.execute(
        "INSERT INTO courses (course_code, name, credits, department, level) "
        "VALUES (?, ?, ?, ?, ?)",
        ("CIS2001", "Data Structures", 4, "Computer Science", "200"),
    )
    conn.execute(
        "INSERT INTO courses (course_code, name, credits, department, level) "
        "VALUES (?, ?, ?, ?, ?)",
        ("MAT1001", "Calculus I", 3, "Mathematics", "100"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests -- Table Initialization
# ---------------------------------------------------------------------------

class TestInitTables:
    """Tests for _init_tables."""

    @patch(f"{MODULE}.get_connection")
    def test_init_tables_creates_tables(self, mock_get_conn):
        """_init_tables should create the three catalog tables."""
        conn = sqlite3.connect(":memory:")
        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _init_tables,
        )

        _init_tables()

        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "courses" in tables
        assert "course_prerequisites" in tables
        assert "course_offerings" in tables
        conn.close()


# ---------------------------------------------------------------------------
# Tests -- List All Courses
# ---------------------------------------------------------------------------

class TestListAllCourses:
    """Tests for _list_all_courses."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_list_courses_displays_rows(self, _inp, mock_get_conn, mem_conn, capsys):
        """Listing courses should print each course row."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _list_all_courses,
        )

        _list_all_courses()

        out = capsys.readouterr().out
        assert "CIS1001" in out
        assert "Intro to CS" in out
        assert "MAT1001" in out

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input", return_value="")
    def test_list_courses_empty_catalog(self, _inp, mock_get_conn, mem_conn, capsys):
        """An empty catalog should print an appropriate message."""
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _list_all_courses,
        )

        _list_all_courses()

        out = capsys.readouterr().out
        assert "empty" in out.lower()


# ---------------------------------------------------------------------------
# Tests -- Search Courses
# ---------------------------------------------------------------------------

class TestSearchCourses:
    """Tests for _search_courses."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_search_by_name(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Searching by name should find matching courses."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        # choice=1 (name), term="Intro", press enter to continue
        mock_input.side_effect = ["1", "Intro", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _search_courses,
        )

        _search_courses()

        out = capsys.readouterr().out
        assert "CIS1001" in out
        assert "Intro to CS" in out

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_search_by_department(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Searching by department should find matching courses."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["3", "Math", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _search_courses,
        )

        _search_courses()

        out = capsys.readouterr().out
        assert "MAT1001" in out

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_search_by_code(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Searching by course code should find matching courses."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["2", "CIS2001", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _search_courses,
        )

        _search_courses()

        out = capsys.readouterr().out
        assert "CIS2001" in out
        assert "Data Structures" in out

    @patch("builtins.input")
    def test_search_invalid_option(self, mock_input, capsys):
        """An invalid search option should print an error."""
        mock_input.side_effect = ["9", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _search_courses,
        )

        _search_courses()

        out = capsys.readouterr().out
        assert "invalid" in out.lower()


# ---------------------------------------------------------------------------
# Tests -- View Course Details
# ---------------------------------------------------------------------------

class TestGetCourseDetails:
    """Tests for _get_course_details."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_view_details_with_prerequisites(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Viewing details should display course info and prerequisites."""
        _seed_courses(mem_conn)
        mem_conn.execute(
            "INSERT INTO course_prerequisites (course_code, prerequisite_code) "
            "VALUES (?, ?)",
            ("CIS2001", "CIS1001"),
        )
        mem_conn.commit()
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["CIS2001", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _get_course_details,
        )

        _get_course_details()

        out = capsys.readouterr().out
        assert "CIS2001" in out
        assert "Data Structures" in out
        assert "CIS1001" in out  # prerequisite shown

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_view_details_not_found(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Viewing a non-existent course should show 'not found'."""
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["FAKE999", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _get_course_details,
        )

        _get_course_details()

        out = capsys.readouterr().out
        assert "not found" in out.lower()


# ---------------------------------------------------------------------------
# Tests -- View Course Offerings
# ---------------------------------------------------------------------------

class TestViewCourseOfferings:
    """Tests for _view_course_offerings."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_view_offerings_displays_rows(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Viewing offerings should list matching rows."""
        _seed_courses(mem_conn)
        mem_conn.execute(
            "INSERT INTO course_offerings "
            "(offering_id, course_code, academic_year, semester, instructor, "
            "schedule, room, max_enrollment, current_enrollment, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("off-1", "CIS1001", "2026", "Fall", "Dr Smith",
             "MWF 10-11", "101", 30, 5, "Open"),
        )
        mem_conn.commit()
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["2026", "Fall", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _view_course_offerings,
        )

        _view_course_offerings()

        out = capsys.readouterr().out
        assert "CIS1001" in out
        assert "Dr Smith" in out

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_view_offerings_no_results(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Viewing offerings with no matches should show a message."""
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["2099", "Fall", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _view_course_offerings,
        )

        _view_course_offerings()

        out = capsys.readouterr().out
        assert "no offerings" in out.lower()


# ---------------------------------------------------------------------------
# Tests -- Add Course
# ---------------------------------------------------------------------------

class TestAddCourse:
    """Tests for _add_course."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_course_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Adding a new course should insert it into the database."""
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = [
            "PHY1001",   # course_code
            "Physics I", # name
            "Intro physics", # description
            "4",         # credits
            "Physics",   # department
            "100",       # level
            "",          # press enter to continue
        ]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _add_course,
        )

        _add_course()

        out = capsys.readouterr().out
        assert "added successfully" in out.lower()

        row = mem_conn.execute(
            "SELECT name FROM courses WHERE course_code = ?", ("PHY1001",)
        ).fetchone()
        assert row is not None
        assert row[0] == "Physics I"

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_duplicate_course(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Adding a course that already exists should print a warning."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = [
            "CIS1001", "Duplicate", "", "3", "CS", "100", "",
        ]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _add_course,
        )

        _add_course()

        out = capsys.readouterr().out
        assert "already exists" in out.lower()


# ---------------------------------------------------------------------------
# Tests -- Update Course
# ---------------------------------------------------------------------------

class TestUpdateCourse:
    """Tests for _update_course."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_update_course_name(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Updating a course name should persist the change."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = [
            "CIS1001",              # course code
            "Introduction to CS",   # new name
            "",                     # description (keep)
            "",                     # credits (keep)
            "",                     # department (keep)
            "",                     # level (keep)
            "",                     # press enter
        ]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _update_course,
        )

        _update_course()

        out = capsys.readouterr().out
        assert "updated successfully" in out.lower()

        row = mem_conn.execute(
            "SELECT name FROM courses WHERE course_code = ?", ("CIS1001",)
        ).fetchone()
        assert row[0] == "Introduction to CS"


# ---------------------------------------------------------------------------
# Tests -- Delete Course
# ---------------------------------------------------------------------------

class TestDeleteCourse:
    """Tests for _delete_course."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_delete_course_confirmed(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Deleting a course with 'yes' confirmation should remove it."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["CIS1001", "yes", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _delete_course,
        )

        _delete_course()

        out = capsys.readouterr().out
        assert "deleted successfully" in out.lower()

        row = mem_conn.execute(
            "SELECT COUNT(*) FROM courses WHERE course_code = ?", ("CIS1001",)
        ).fetchone()
        assert row[0] == 0

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_delete_course_cancelled(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Declining deletion should keep the course."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["CIS1001", "no", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _delete_course,
        )

        _delete_course()

        out = capsys.readouterr().out
        assert "cancelled" in out.lower()

        row = mem_conn.execute(
            "SELECT COUNT(*) FROM courses WHERE course_code = ?", ("CIS1001",)
        ).fetchone()
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Tests -- Prerequisites
# ---------------------------------------------------------------------------

class TestPrerequisites:
    """Tests for _add_prerequisite and _remove_prerequisite."""

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_prerequisite_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Adding a valid prerequisite should insert the relationship."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["CIS2001", "CIS1001", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _add_prerequisite,
        )

        _add_prerequisite()

        out = capsys.readouterr().out
        assert "added" in out.lower() and "prerequisite" in out.lower()

        count = mem_conn.execute(
            "SELECT COUNT(*) FROM course_prerequisites "
            "WHERE course_code = ? AND prerequisite_code = ?",
            ("CIS2001", "CIS1001"),
        ).fetchone()[0]
        assert count == 1

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_prerequisite_circular_dependency(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Adding a prerequisite that creates a cycle should be rejected."""
        _seed_courses(mem_conn)
        # CIS2001 requires CIS1001
        mem_conn.execute(
            "INSERT INTO course_prerequisites (course_code, prerequisite_code) "
            "VALUES (?, ?)",
            ("CIS2001", "CIS1001"),
        )
        mem_conn.commit()
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        # Now try to make CIS1001 require CIS2001 -> cycle
        mock_input.side_effect = ["CIS1001", "CIS2001", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _add_prerequisite,
        )

        _add_prerequisite()

        out = capsys.readouterr().out
        assert "circular" in out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_remove_prerequisite_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Removing an existing prerequisite should delete the relationship."""
        _seed_courses(mem_conn)
        mem_conn.execute(
            "INSERT INTO course_prerequisites (course_code, prerequisite_code) "
            "VALUES (?, ?)",
            ("CIS2001", "CIS1001"),
        )
        mem_conn.commit()
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["CIS2001", "CIS1001", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _remove_prerequisite,
        )

        _remove_prerequisite()

        out = capsys.readouterr().out
        assert "removed" in out.lower()

        count = mem_conn.execute(
            "SELECT COUNT(*) FROM course_prerequisites "
            "WHERE course_code = ? AND prerequisite_code = ?",
            ("CIS2001", "CIS1001"),
        ).fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Tests -- Course Offerings CRUD
# ---------------------------------------------------------------------------

class TestCourseOfferings:
    """Tests for add/update/delete course offerings."""

    @patch(f"{MODULE}.uuid")
    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_add_offering_success(self, mock_input, mock_get_conn, mock_uuid, mem_conn, capsys):
        """Adding a course offering should insert a new row."""
        _seed_courses(mem_conn)
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_uuid.uuid4.return_value = "test-uuid-1234"
        mock_input.side_effect = [
            "CIS1001",        # course code
            "2026",           # academic year
            "Fall",           # semester
            "Dr Smith",       # instructor
            "101",            # room
            "MWF 10-11",     # schedule
            "30",             # max enrollment
            "",               # press enter
        ]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _add_course_offering,
        )

        _add_course_offering()

        out = capsys.readouterr().out
        assert "added successfully" in out.lower()

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_update_offering_success(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Updating an offering should persist the changes."""
        _seed_courses(mem_conn)
        mem_conn.execute(
            "INSERT INTO course_offerings "
            "(offering_id, course_code, academic_year, semester, instructor, "
            "schedule, room, max_enrollment, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("off-1", "CIS1001", "2026", "Fall", "Dr Smith",
             "MWF 10-11", "101", 30, "Open"),
        )
        mem_conn.commit()
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = [
            "off-1",          # offering id
            "Dr Jones",       # new instructor
            "",               # schedule (keep)
            "202",            # new room
            "",               # max enrollment (keep)
            "",               # status (keep)
            "",               # press enter
        ]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _update_course_offering,
        )

        _update_course_offering()

        out = capsys.readouterr().out
        assert "updated successfully" in out.lower()

        row = mem_conn.execute(
            "SELECT instructor, room FROM course_offerings WHERE offering_id = ?",
            ("off-1",),
        ).fetchone()
        assert row[0] == "Dr Jones"
        assert row[1] == "202"

    @patch(f"{MODULE}.get_connection")
    @patch("builtins.input")
    def test_delete_offering_confirmed(self, mock_input, mock_get_conn, mem_conn, capsys):
        """Deleting an offering with confirmation should remove it."""
        _seed_courses(mem_conn)
        mem_conn.execute(
            "INSERT INTO course_offerings "
            "(offering_id, course_code, academic_year, semester) "
            "VALUES (?, ?, ?, ?)",
            ("off-2", "CIS1001", "2026", "Spring"),
        )
        mem_conn.commit()
        mock_get_conn.return_value.__enter__ = Mock(return_value=mem_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        mock_input.side_effect = ["off-2", "yes", ""]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _delete_course_offering,
        )

        _delete_course_offering()

        out = capsys.readouterr().out
        assert "deleted successfully" in out.lower()

        count = mem_conn.execute(
            "SELECT COUNT(*) FROM course_offerings WHERE offering_id = ?",
            ("off-2",),
        ).fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Tests -- Menu Navigation & Role-Based Access
# ---------------------------------------------------------------------------

class TestMenuNavigation:
    """Tests for display_course_catalog_menu."""

    @patch(f"{MODULE}._init_tables")
    @patch("builtins.input")
    def test_menu_returns_on_exit_option_admin(self, mock_input, mock_init, mock_auth_admin, capsys):
        """Admin menu should show all options; selecting last exits."""
        # Admin has 13 options (12 + return). Option 13 = return.
        mock_input.side_effect = ["13"]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            display_course_catalog_menu,
        )

        display_course_catalog_menu(auth=mock_auth_admin)

        out = capsys.readouterr().out
        assert "COURSE CATALOG MANAGEMENT" in out

    @patch(f"{MODULE}._init_tables")
    @patch("builtins.input")
    def test_menu_returns_on_exit_option_student(self, mock_input, mock_init, mock_auth_student, capsys):
        """Student menu should show only read options; selecting 5 exits."""
        # Student has 5 options (4 read + return). Option 5 = return.
        mock_input.side_effect = ["5"]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            display_course_catalog_menu,
        )

        display_course_catalog_menu(auth=mock_auth_student)

        out = capsys.readouterr().out
        assert "COURSE CATALOG MANAGEMENT" in out

    @patch(f"{MODULE}._init_tables")
    @patch("builtins.input")
    def test_admin_sees_write_options(self, mock_input, mock_init, mock_auth_admin, capsys):
        """Admin menu should include options like Add New Course."""
        mock_input.side_effect = ["13"]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            display_course_catalog_menu,
        )

        display_course_catalog_menu(auth=mock_auth_admin)

        out = capsys.readouterr().out
        assert "Add New Course" in out
        assert "Delete Course" in out
        assert "Add Prerequisite" in out

    @patch(f"{MODULE}._init_tables")
    @patch("builtins.input")
    def test_student_does_not_see_write_options(self, mock_input, mock_init, mock_auth_student, capsys):
        """Student menu should NOT include admin-only options."""
        mock_input.side_effect = ["5"]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            display_course_catalog_menu,
        )

        display_course_catalog_menu(auth=mock_auth_student)

        out = capsys.readouterr().out
        assert "Add New Course" not in out
        assert "Delete Course" not in out

    @patch("builtins.input")
    def test_menu_requires_auth(self, mock_input, capsys):
        """Calling the menu without auth should prompt login."""
        mock_input.return_value = ""

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            display_course_catalog_menu,
        )

        display_course_catalog_menu(auth=None)

        out = capsys.readouterr().out
        assert "log in" in out.lower()

    @patch(f"{MODULE}._init_tables")
    @patch("builtins.input")
    def test_invalid_choice_shows_error(self, mock_input, mock_init, mock_auth_student, capsys):
        """An invalid menu choice should print an error then re-prompt."""
        mock_input.side_effect = ["999", "5"]

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            display_course_catalog_menu,
        )

        display_course_catalog_menu(auth=mock_auth_student)

        out = capsys.readouterr().out
        assert "invalid" in out.lower()


# ---------------------------------------------------------------------------
# Tests -- Circular Dependency Helper
# ---------------------------------------------------------------------------

class TestCircularDependencyCheck:
    """Tests for _check_circular_dependency."""

    def test_self_reference_detected(self, mem_conn):
        """A course requiring itself should be detected as circular."""
        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _check_circular_dependency,
        )

        assert _check_circular_dependency(mem_conn, "CIS1001", "CIS1001") is True

    def test_indirect_cycle_detected(self, mem_conn):
        """An indirect cycle (A->B->C->A) should be detected."""
        _seed_courses(mem_conn)
        mem_conn.execute(
            "INSERT INTO course_prerequisites VALUES (?, ?)", ("CIS2001", "CIS1001")
        )
        mem_conn.execute(
            "INSERT INTO course_prerequisites VALUES (?, ?)", ("MAT1001", "CIS2001")
        )
        mem_conn.commit()

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _check_circular_dependency,
        )

        # Adding CIS1001 as prereq of MAT1001 is fine (MAT->CIS2->CIS1)
        # But adding MAT1001 as prereq of CIS1001 would create CIS1->MAT->CIS2->CIS1
        assert _check_circular_dependency(mem_conn, "CIS1001", "MAT1001") is True

    def test_no_cycle(self, mem_conn):
        """A valid prerequisite chain should not be flagged as circular."""
        _seed_courses(mem_conn)

        from education_system.post_18.university_system.modules.domain.academics.cli.course_catalog_cli import (
            _check_circular_dependency,
        )

        assert _check_circular_dependency(mem_conn, "CIS2001", "CIS1001") is False
