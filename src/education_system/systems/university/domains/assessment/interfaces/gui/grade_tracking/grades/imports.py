"""Extracted GradeManager behaviour."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *
from .scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter

class GradeImportMixin:
    def import_grades(self):
        """Import grades from CSV file"""
        file_path = filedialog.askopenfilename(
            title=_t('gui.academics.grade_tracking.grades.imports.dialogs.select_csv_file', default="Select CSV file"),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            original_filename = os.path.basename(file_path)

            if not original_filename.lower().endswith('.csv'):
                raise ValueError("Only CSV files are accepted")
            if os.path.getsize(file_path) > MAX_IMPORT_BYTES:
                raise ValueError("CSV file exceeds the permitted size")

            # Security: Validate file before processing
            if not SECURE_UPLOAD_AVAILABLE or not validate_upload:
                raise RuntimeError("Secure file validation is unavailable")
            with open(file_path, 'rb') as f:
                file_content = f.read(MAX_IMPORT_BYTES + 1)
            validation = validate_upload(original_filename, file_content, category='data')
            if not isinstance(validation, dict) or not validation.get('valid'):
                raise ValueError("File validation failed")

            imported = 0
            errors = []
            imported_ids = []
            overwrite = {'asked': False, 'reason': None}
            from .marking_rules import ABSENCE_CODES, ask_reason, log_change, after_exam_mark
            from education_system.systems.university.application.exams import (
                marking as exam_marking,
            )
            import_user = (getattr(self.auth, 'current_user', None) or {}).get('username')

            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                fieldnames = reader.fieldnames or []
                normalized = [str(name).strip().casefold() for name in fieldnames]
                if len(normalized) != len(set(normalized)):
                    raise ValueError("CSV contains duplicate column names")

                # Expected columns: student_id, assessment_id, score, submission_date, comments
                required_columns = ['student_id', 'assessment_id', 'score']

                # Check if required columns exist
                if not all(col in fieldnames for col in required_columns):
                    raise ValueError("CSV is missing required columns")

                cursor = self.get_safe_cursor()

                for row_num, row in enumerate(reader, start=2):
                    if row_num > MAX_IMPORT_ROWS + 1:
                        raise ValueError("CSV contains too many rows")
                    try:
                        student_id = row['student_id'].strip()
                        assessment_id = row['assessment_id'].strip()
                        if any(len(str(row.get(name, '') or '')) > MAX_FIELD_LENGTH
                               for name in fieldnames):
                            raise ValueError("Field exceeds maximum length")
                        raw_score = (row.get('score') or '').strip()
                        absence = raw_score.upper() if raw_score.upper() in ABSENCE_CODES else None
                        score = 0.0 if absence else float(raw_score)
                        submission_date = row.get('submission_date', datetime.now().strftime('%Y-%m-%d')).strip()
                        comments = row.get('comments', '').strip()
                        datetime.strptime(submission_date, '%Y-%m-%d')
                        if not math.isfinite(score):
                            raise ValueError("Score must be finite")

                        # Verify student exists
                        cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
                        if not cursor.fetchone():
                            errors.append(f"Row {row_num}: Student {student_id} not found")
                            continue

                        # Verify assessment exists and get max points
                        cursor.execute("SELECT max_points FROM assessments WHERE assessment_id = ?", (assessment_id,))
                        result = cursor.fetchone()
                        if not result:
                            errors.append(f"Row {row_num}: Assessment {assessment_id} not found")
                            continue

                        if not self.authorize_grade_mutation(
                                'import', assessment_id=assessment_id, cursor=cursor):
                            errors.append(f"Row {row_num}: Not authorised for this assessment")
                            continue

                        max_points = result[0]

                        if absence:
                            exam_marking.record_absence(cursor.connection, int(assessment_id), student_id,
                                                        absence, import_user, reason=comments or None)
                            imported += 1
                            continue

                        # Validate score
                        if not math.isfinite(float(max_points)) or score < 0 or score > float(max_points):
                            errors.append(f"Row {row_num}: Invalid score {score} (max: {max_points})")
                            continue

                        # Calculate letter grade
                        percentage = (score / max_points) * 100
                        letter_grade = self.percentage_to_letter(percentage)

                        # Check if grade already exists
                        cursor.execute("""
                            SELECT grade_id, COALESCE(version, 1) FROM grades
                            WHERE student_id = ? AND assessment_id = ?
                        """, (student_id, assessment_id))

                        existing = cursor.fetchone()
                        if existing:
                            # Overwriting a different recorded mark needs a reason,
                            # asked once for the whole import.
                            old = cursor.execute("SELECT score FROM grades WHERE grade_id = ?",
                                                 (existing[0],)).fetchone()[0]
                            if old is not None and abs(float(old) - score) > 1e-9:
                                if overwrite['reason'] is None and not overwrite['asked']:
                                    overwrite['asked'] = True
                                    overwrite['reason'] = ask_reason(self.root, "overwrite existing marks with this import")
                                if not overwrite['reason']:
                                    errors.append(f"Row {row_num}: kept the existing mark {old} (no reason given)")
                                    continue
                                log_change(cursor.connection, source='grades', record_id=existing[0],
                                           student_id=student_id, module_code=None, old_value=old,
                                           new_value=score, reason=overwrite['reason'],
                                           changed_by=import_user)
                            # Update existing grade
                            cursor.execute("""
                                UPDATE grades
                                SET score = ?, letter_grade = ?, submission_date = ?, comments = ?,
                                    version = COALESCE(version, 1) + 1, updated_at = datetime('now')
                                WHERE student_id = ? AND assessment_id = ?
                                  AND COALESCE(version, 1) = ?
                            """, (score, letter_grade, submission_date, comments, student_id, assessment_id, existing[1]))
                            if cursor.rowcount != 1:
                                raise sqlite3.Error("Grade was changed by another user")
                            imported_ids.append(existing[0])
                        else:
                            # Insert new grade
                            cursor.execute("""
                                INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date, comments)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (student_id, assessment_id, score, letter_grade, submission_date, comments))
                            imported_ids.append(cursor.lastrowid)

                        imported += 1

                    except ValueError as e:
                        errors.append(f"Row {row_num}: Invalid number format - {e}")
                    except sqlite3.Error as e:
                        errors.append(f"Row {row_num}: Database error - {e}")

                # Referral caps, moderation and module results for what was imported.
                for grade_id in imported_ids:
                    after_exam_mark(cursor.connection, grade_id)

                # Immutable audit log for bulk grade import (FERPA compliance)
                if imported > 0:
                    user_id, session_id = get_gui_context()
                    require_grade_audit(
                        conn=cursor.connection,
                        action=AuditAction.BULK_UPDATE,
                        user_id=user_id,
                        resource_type='grade',
                        session_id=session_id,
                        details={
                            'operation': 'import_grades',
                            'count': imported,
                            'filename': original_filename,
                            'errors': len(errors)
                        }
                    )
                self.safe_commit()

            # Show results
            result_msg = f"Successfully imported {imported} grade(s)"
            if errors:
                result_msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
                if len(errors) > 10:
                    result_msg += f"\n... and {len(errors) - 10} more errors"
                messagebox.showwarning(_t('gui.academics.grade_tracking.grades.imports.dialogs.import_completed_with_errors', default="Import Completed with Errors"), result_msg)
            else:
                messagebox.showinfo(_t('gui.academics.grade_tracking.grades.imports.dialogs.import_successful', default="Import Successful"), result_msg)

            self.refresh_grades()

        except Exception:
            try:
                if self.conn:
                    self.conn.rollback()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            logger.exception("Grade import failed")
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.imports.dialogs.import_error', default="Import Error"), "Import could not be completed. Check the file and try again.")
