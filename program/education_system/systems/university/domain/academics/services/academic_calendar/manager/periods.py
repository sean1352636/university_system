"""Extracted AcademicCalendarManager periods methods."""

from ._shared import *  # noqa: F401,F403


class PeriodsMixin:
    def add_academic_year(self, year: str, start_date: str, end_date: str) -> Tuple[bool, str]:
        """Add a new academic year to the calendar"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add academic years")

        try:
            year = ValidationUtils.sanitize_string(year, 20)
            if not isinstance(year, str) or len(year.split('-')) != 2:
                raise ValidationError("Year should be in format 'YYYY-YYYY' (e.g., '2023-2024')")

            if not ValidationUtils.validate_date(start_date) or not ValidationUtils.validate_date(end_date):
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

            if start_date >= end_date:
                raise ValidationError("End date must be after start date")

            # Check if academic year already exists
            existing = self.db_manager.execute_query("SELECT id FROM academic_years WHERE id = ?", (year,))
            if existing:
                return False, f"Academic year {year} already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO academic_years (id, start_date, end_date, date_added)
                       VALUES (?, ?, ?, ?)""",
                    (year, start_date, end_date, datetime.now().isoformat())
                )

                # Log the action
                user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                self.audit_manager.log_change(
                    table_name='academic_years',
                    record_id=year,
                    action='CREATE',
                    new_values={'year': year, 'start_date': start_date, 'end_date': end_date},
                    user_id=user_id
                )

                # Mirror onto the calendar so the academic year shows up
                # alongside exams, holidays and ad-hoc events.
                self._sync_academic_year_to_calendar(
                    year, start_date, end_date)

            logger.info(f"Academic year {year} added successfully")
            return True, f"Academic year {year} added successfully"

        except Exception as e:
            logger.error(f"Failed to add academic year: {e}")
            raise DatabaseError(f"Database error: {str(e)}")

    def add_semester(self, academic_year: str, semester_name: str, start_date: str, end_date: str) -> Tuple[bool, str]:
        """Add a semester to an academic year"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add semesters")

        try:
            academic_year = ValidationUtils.sanitize_string(academic_year, 20)
            semester_name = ValidationUtils.sanitize_string(semester_name, 50)

            if not ValidationUtils.validate_date(start_date) or not ValidationUtils.validate_date(end_date):
                raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

            if start_date >= end_date:
                raise ValidationError("End date must be after start date")

            # Check if academic year exists
            year_data = self.db_manager.execute_query(
                "SELECT id, start_date, end_date FROM academic_years WHERE id = ?", (academic_year,)
            )
            if not year_data:
                return False, f"Academic year {academic_year} not found"

            year_info = dict(year_data[0])
            if start_date < year_info['start_date'] or end_date > year_info['end_date']:
                return False, "Semester dates must fall within the academic year"

            # Check if semester already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM semesters WHERE academic_year_id = ? AND name = ?",
                (academic_year, semester_name)
            )
            if existing:
                return False, f"Semester {semester_name} already exists for academic year {academic_year}"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO semesters (academic_year_id, name, start_date, end_date, date_added)
                       VALUES (?, ?, ?, ?, ?)""",
                    (academic_year, semester_name, start_date, end_date, datetime.now().isoformat())
                )

                # Look up the new semester's id and mirror it onto the
                # calendar (period plus registration/exam sub-windows
                # if those dates have been set).
                new_row = self.db_manager.execute_query(
                    "SELECT id, registration_start, registration_end, "
                    "       final_exams_start, final_exams_end "
                    "FROM semesters WHERE academic_year_id = ? AND name = ?",
                    (academic_year, semester_name),
                )
                if new_row:
                    sem = dict(new_row[0])
                    self._sync_semester_to_calendar(
                        semester_id=sem["id"],
                        name=semester_name,
                        start_date=start_date,
                        end_date=end_date,
                        registration_start=sem.get("registration_start"),
                        registration_end=sem.get("registration_end"),
                        exams_start=sem.get("final_exams_start"),
                        exams_end=sem.get("final_exams_end"),
                    )

            logger.info(f"Semester {semester_name} added to academic year {academic_year}")
            return True, f"Semester {semester_name} added successfully to academic year {academic_year}"

        except Exception as e:
            logger.error(f"Failed to add semester: {e}")
            raise DatabaseError(f"Database error: {str(e)}")

    def get_current_academic_year(self) -> Optional[Dict]:
        """Get the current academic year"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            # First try to find current academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE start_date <= ? AND end_date >= ?",
                (current_date, current_date)
            )
            if rows:
                return dict(rows[0])

            # If not found, look for upcoming academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE start_date > ? ORDER BY start_date ASC LIMIT 1",
                (current_date,)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'upcoming'
                return result

            # If still not found, look for most recent past academic year
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_years WHERE end_date < ? ORDER BY end_date DESC LIMIT 1",
                (current_date,)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'past'
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to get current academic year: {e}")
            return None

    def get_current_semester(self) -> Optional[Dict]:
        """Get the current semester"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            current_year = self.get_current_academic_year()
            if not current_year:
                return None

            current_year_id = current_year['id']
            year_status = current_year.get('status')

            if year_status == 'upcoming':
                rows = self.db_manager.execute_query(
                    "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date ASC LIMIT 1",
                    (current_year_id,)
                )
                if rows:
                    result = dict(rows[0])
                    result['status'] = 'upcoming'
                    return result
            elif year_status == 'past':
                rows = self.db_manager.execute_query(
                    "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY end_date DESC LIMIT 1",
                    (current_year_id,)
                )
                if rows:
                    result = dict(rows[0])
                    result['status'] = 'past'
                    return result

            # Look for current semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND start_date <= ? AND end_date >= ?",
                (current_year_id, current_date, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'current'
                return result

            # Look for upcoming semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND start_date > ? ORDER BY start_date ASC LIMIT 1",
                (current_year_id, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'upcoming'
                return result

            # Look for most recent past semester
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? AND end_date < ? ORDER BY end_date DESC LIMIT 1",
                (current_year_id, current_date)
            )
            if rows:
                result = dict(rows[0])
                result['status'] = 'past'
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to get current semester: {e}")
            return None

    def get_semesters_for_academic_year(self, academic_year_id: str) -> List[Dict]:
        """Get all semesters for a specific academic year"""
        try:
            academic_year_id = ValidationUtils.sanitize_string(academic_year_id, 20)
            rows = self.db_manager.execute_query(
                "SELECT * FROM semesters WHERE academic_year_id = ? ORDER BY start_date",
                (academic_year_id,)
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get semesters: {e}")
            return []
