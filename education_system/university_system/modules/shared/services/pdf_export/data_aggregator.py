"""Data aggregator for collecting database information for PDF export.

This module queries the database and aggregates data from all tables
into structured formats suitable for PDF generation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.i18n import get_text, _
from education_system.university_system.core.sql_safety import validate_table_name

logger = logging.getLogger(__name__)


class DataAggregator:
    """Collects and aggregates data from the database for PDF export."""

    # Core tables to export with their display names and descriptions
    TABLE_CATEGORIES = {
        "Academic": {
            "students": ("Students", "Student enrollment records"),
            "modules": ("Modules/Courses", "Academic modules and courses"),
            "student_modules": ("Enrollments", "Student course enrollments"),
            "lms_courses": ("LMS Courses", "Learning management system courses"),
            "lms_gradebook": ("Gradebook", "Student grades and scores"),
            "degree_programs": ("Degree Programs", "Available degree programs"),
            "attendance_sessions": ("Attendance Sessions", "Class attendance records"),
            "attendance_records": ("Attendance Records", "Individual attendance entries"),
        },
        "Student Services": {
            "student_clubs": ("Student Clubs", "Campus clubs and organizations"),
            "club_members": ("Club Members", "Club membership records"),
            "health_records": ("Health Records", "Student health information"),
            "vaccination_records": ("Vaccinations", "Vaccination records"),
            "mental_health_appointments": ("Counseling Appointments", "Mental health appointments"),
            "room_bookings": ("Room Bookings", "Facility room bookings"),
        },
        "Finance": {
            "fee_types": ("Fee Types", "Types of fees charged"),
            "program_fees": ("Program Fees", "Fees by academic program"),
            "scholarships": ("Scholarships", "Available scholarships"),
            "student_scholarships": ("Student Scholarships", "Scholarship awards"),
            "payment_plan_templates": ("Payment Plans", "Payment plan options"),
        },
        "Housing": {
            "buildings": ("Buildings", "Campus buildings"),
            "rooms": ("Rooms", "Accommodation rooms"),
            "facility_bookings": ("Facility Bookings", "Facility reservations"),
        },
        "Career Services": {
            "job_postings": ("Job Postings", "Employment opportunities"),
            "job_applications": ("Job Applications", "Student job applications"),
            "employers": ("Employers", "Registered employers"),
            "student_resumes": ("Resumes", "Student resume records"),
        },
        "Research": {
            "research_projects": ("Research Projects", "Academic research projects"),
            "research_publications": ("Publications", "Research publications"),
            "grant_applications": ("Grant Applications", "Research grant applications"),
        },
        "Events": {
            "campus_events": ("Campus Events", "University events"),
            "event_registrations": ("Event Registrations", "Event attendance"),
            "union_events": ("Union Events", "Student union events"),
        },
        "Alumni": {
            "alumni_profiles": ("Alumni Profiles", "Graduate profiles"),
            "alumni_donations": ("Donations", "Alumni contributions"),
            "alumni_events": ("Alumni Events", "Alumni networking events"),
        },
        "System": {
            "email_log": ("Email Log", "System email records"),
            "email_templates": ("Email Templates", "Email template library"),
        },
    }

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the data aggregator.

        Args:
            db_path: Optional path to database file. Uses default if not provided.
        """
        self.db_path = db_path or str(paths.DEFAULT_DB_PATH)

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database.

        Returns:
            List of table names.
        """
        try:
            with get_connection(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting table list: {e}")
            return []

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get metadata about a table.

        Args:
            table_name: Name of the table.

        Returns:
            Dictionary with table info including columns, row count, etc.
        """
        try:
            with get_connection(self.db_path) as conn:
                # Get column info
                safe_table = validate_table_name(table_name, conn=conn)
                cursor = conn.execute("PRAGMA table_info([" + safe_table + "])")
                columns = [
                    {
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "pk": bool(row[5]),
                    }
                    for row in cursor.fetchall()
                ]

                # Get row count
                count_cursor = conn.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                row_count = count_cursor.fetchone()[0]

                return {
                    "name": table_name,
                    "columns": columns,
                    "column_names": [c["name"] for c in columns],
                    "row_count": row_count,
                }
        except Exception as e:
            logger.error(f"Error getting table info for {table_name}: {e}")
            return {"name": table_name, "columns": [], "column_names": [], "row_count": 0}

    def get_table_data(
        self, table_name: str, limit: Optional[int] = None
    ) -> Tuple[List[str], List[Tuple]]:
        """Get data from a table.

        Args:
            table_name: Name of the table.
            limit: Optional limit on number of rows to retrieve.

        Returns:
            Tuple of (column_names, rows).
        """
        try:
            with get_connection(self.db_path) as conn:
                # Get column names
                safe_table = validate_table_name(table_name, conn=conn)
                cursor = conn.execute("PRAGMA table_info([" + safe_table + "])")
                columns = [row[1] for row in cursor.fetchall()]

                # Get data
                query = "SELECT * FROM [" + safe_table + "]"
                if limit:
                    query += " LIMIT " + str(int(limit))

                data_cursor = conn.execute(query)
                rows = data_cursor.fetchall()

                return columns, [tuple(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting data from {table_name}: {e}")
            return [], []

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics about the database.

        Returns:
            Dictionary with summary statistics.
        """
        stats = {
            "total_tables": 0,
            "total_records": 0,
            "tables_with_data": 0,
            "empty_tables": 0,
            "largest_tables": [],
            "export_timestamp": datetime.now().isoformat(),
        }

        try:
            tables = self.get_all_tables()
            stats["total_tables"] = len(tables)

            table_sizes = []
            for table in tables:
                info = self.get_table_info(table)
                row_count = info["row_count"]
                stats["total_records"] += row_count

                if row_count > 0:
                    stats["tables_with_data"] += 1
                    table_sizes.append((table, row_count))
                else:
                    stats["empty_tables"] += 1

            # Get top 10 largest tables
            table_sizes.sort(key=lambda x: x[1], reverse=True)
            stats["largest_tables"] = table_sizes[:10]

        except Exception as e:
            logger.error(f"Error calculating summary statistics: {e}")

        return stats

    def get_student_statistics(self) -> Dict[str, Any]:
        """Get student enrollment statistics.

        Returns:
            Dictionary with student statistics for charts.
        """
        stats = {
            "total_students": 0,
            "by_status": {},
            "by_program": {},
            "enrollment_trends": [],
        }

        try:
            with get_connection(self.db_path) as conn:
                # Total students
                cursor = conn.execute("SELECT COUNT(*) FROM students")
                result = cursor.fetchone()
                stats["total_students"] = result[0] if result else 0

                # By status (if status column exists)
                try:
                    cursor = conn.execute(
                        "SELECT status, COUNT(*) FROM students GROUP BY status"
                    )
                    stats["by_status"] = {
                        row[0] or "Unknown": row[1] for row in cursor.fetchall()
                    }
                except Exception:
                    pass

                # By program (if program column exists)
                try:
                    cursor = conn.execute(
                        "SELECT program, COUNT(*) FROM students "
                        "WHERE program IS NOT NULL GROUP BY program"
                    )
                    stats["by_program"] = {row[0]: row[1] for row in cursor.fetchall()}
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error getting student statistics: {e}")

        return stats

    def get_financial_statistics(self) -> Dict[str, Any]:
        """Get financial statistics for reporting.

        Returns:
            Dictionary with financial statistics.
        """
        stats = {
            "scholarship_count": 0,
            "scholarship_total": 0,
            "fee_types_count": 0,
            "scholarships_by_type": {},
        }

        try:
            with get_connection(self.db_path) as conn:
                # Scholarships
                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM scholarships")
                    result = cursor.fetchone()
                    stats["scholarship_count"] = result[0] if result else 0

                    cursor = conn.execute(
                        "SELECT SUM(amount) FROM scholarships WHERE amount IS NOT NULL"
                    )
                    result = cursor.fetchone()
                    stats["scholarship_total"] = result[0] if result and result[0] else 0
                except Exception:
                    pass

                # Fee types
                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM fee_types")
                    result = cursor.fetchone()
                    stats["fee_types_count"] = result[0] if result else 0
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error getting financial statistics: {e}")

        return stats

    def get_attendance_statistics(self) -> Dict[str, Any]:
        """Get attendance statistics for reporting.

        Returns:
            Dictionary with attendance statistics.
        """
        stats = {
            "total_sessions": 0,
            "total_records": 0,
            "by_status": {},
        }

        try:
            with get_connection(self.db_path) as conn:
                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM attendance_sessions")
                    result = cursor.fetchone()
                    stats["total_sessions"] = result[0] if result else 0
                except Exception:
                    pass

                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM attendance_records")
                    result = cursor.fetchone()
                    stats["total_records"] = result[0] if result else 0

                    cursor = conn.execute(
                        "SELECT status, COUNT(*) FROM attendance_records "
                        "WHERE status IS NOT NULL GROUP BY status"
                    )
                    stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error getting attendance statistics: {e}")

        return stats

    def get_event_statistics(self) -> Dict[str, Any]:
        """Get event statistics for reporting.

        Returns:
            Dictionary with event statistics.
        """
        stats = {
            "total_events": 0,
            "total_registrations": 0,
            "by_type": {},
        }

        try:
            with get_connection(self.db_path) as conn:
                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM campus_events")
                    result = cursor.fetchone()
                    stats["total_events"] = result[0] if result else 0
                except Exception:
                    pass

                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM event_registrations")
                    result = cursor.fetchone()
                    stats["total_registrations"] = result[0] if result else 0
                except Exception:
                    pass

                try:
                    cursor = conn.execute(
                        "SELECT event_type, COUNT(*) FROM campus_events "
                        "WHERE event_type IS NOT NULL GROUP BY event_type"
                    )
                    stats["by_type"] = {row[0]: row[1] for row in cursor.fetchall()}
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error getting event statistics: {e}")

        return stats

    def get_categorized_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all tables organized by category with their data.

        Returns:
            Dictionary mapping category names to lists of table info.
        """
        all_tables = set(self.get_all_tables())
        categorized = {}

        # Process known categories
        for category, tables in self.TABLE_CATEGORIES.items():
            category_tables = []
            for table_name, (display_name, description) in tables.items():
                if table_name in all_tables:
                    info = self.get_table_info(table_name)
                    info["display_name"] = display_name
                    info["description"] = description
                    category_tables.append(info)
                    all_tables.discard(table_name)

            if category_tables:
                categorized[category] = category_tables

        # Add remaining tables to "Other" category
        if all_tables:
            other_tables = []
            for table_name in sorted(all_tables):
                info = self.get_table_info(table_name)
                info["display_name"] = table_name.replace("_", " ").title()
                info["description"] = f"Data from {table_name} table"
                other_tables.append(info)
            categorized["Other"] = other_tables

        return categorized
