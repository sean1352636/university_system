"""Utility functions mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    logging,
    List,
    logger,
)


class UtilsMixin:
    """Mixin providing student query and navigation utility methods."""

    def get_students_by_course(self, course: str,
                               progress_callback=None) -> List[str]:
        """Get list of student IDs by course - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Fetching students in {course}...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id FROM students WHERE course = ? ORDER BY student_id",
                    (course,)
                )
                student_ids = [row[0] for row in cursor.fetchall()]

            if progress_callback:
                progress_callback(100, f"Found {len(student_ids)} students in {course}")

            logger.info(f"Retrieved {len(student_ids)} students for course {course}")
            return student_ids

        except Exception as e:
            logger.error(f"Error getting students by course: {e}")
            raise

    def get_all_student_ids(self, progress_callback=None) -> List[str]:
        """Get all student IDs from database - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Fetching all student IDs...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT student_id FROM students ORDER BY student_id")
                student_ids = [row[0] for row in cursor.fetchall()]

            if progress_callback:
                progress_callback(100, f"Found {len(student_ids)} total students")

            logger.info(f"Retrieved {len(student_ids)} total student IDs")
            return student_ids

        except Exception as e:
            logger.error(f"Error getting all student IDs: {e}")
            raise

    def read_student_ids_from_file(self, file_path: str,
                                   progress_callback=None) -> List[str]:
        """Read student IDs from text file - GUI version

        Expected format: One student ID per line
        """
        try:
            if progress_callback:
                progress_callback(0, f"Reading student IDs from {file_path}...")

            student_ids = []

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    student_id = line.strip()
                    if student_id and not student_id.startswith('#'):  # Skip empty lines and comments
                        student_ids.append(student_id)

            if progress_callback:
                progress_callback(100, f"Read {len(student_ids)} student IDs")

            logger.info(f"Read {len(student_ids)} student IDs from {file_path}")
            return student_ids

        except Exception as e:
            logger.error(f"Error reading student IDs from file: {e}")
            raise

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()
