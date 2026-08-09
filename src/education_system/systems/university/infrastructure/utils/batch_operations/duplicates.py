import datetime
from typing import Dict, List, Tuple

from fuzzywuzzy import fuzz

from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.utils.batch_operations.models import ImportResult

logger = configure_logging(name=__name__)


class DuplicatesMixin:
    """Mixin providing duplicate detection and conflict resolution methods."""

    def interactive_error_resolution(self, error_records: List[Dict]) -> List[Dict]:
        """Interactive mode for fixing import errors"""
        print("\n" + _t("shared.utils.batch_operations.title_error_resolution"))
        fixed_records = []

        for i, error_record in enumerate(error_records, 1):
            print(f"\n--- {_t('shared.utils.batch_operations.error_number', current=i, total=len(error_records))} ---")
            print(f"{_t('shared.utils.batch_operations.row')} {error_record['row']}: {error_record['data'].get('first_name', 'N/A')} {error_record['data'].get('last_name', 'N/A')}")
            print(f"{_t('shared.utils.batch_operations.errors')}: {'; '.join(error_record['errors'])}")

            print("\n" + _t("shared.utils.batch_operations.options"))
            print(_t("shared.utils.batch_operations.option_fix_record"))
            print(_t("shared.utils.batch_operations.option_skip_record"))
            print(_t("shared.utils.batch_operations.option_skip_remaining"))

            choice = input(_t("shared.utils.batch_operations.prompt_choose_1_3"))

            if choice == '1':
                fixed_record = self.fix_record_interactive(error_record['data'])
                if fixed_record:
                    fixed_records.append(fixed_record)
            elif choice == '3':
                break
            # Choice 2 (skip) does nothing, continues to next record

        return fixed_records

    def fix_record_interactive(self, record: Dict) -> Dict:
        """Interactive fixing of a single record"""
        print("\n" + _t("shared.utils.batch_operations.title_fix_record"))
        fixed_record = record.copy()

        editable_fields = ['first_name', 'last_name', 'gender', 'dob', 'course', 'email_address']

        for field in editable_fields:
            current_value = fixed_record.get(field, '')
            print(f"\n{field.replace('_', ' ').title()}: {current_value}")

            if field == 'gender':
                print(_t("shared.utils.batch_operations.valid_gender_options"))
            elif field == 'dob':
                print(_t("shared.utils.batch_operations.dob_format"))
            elif field == 'course':
                print(_t("shared.utils.batch_operations.valid_course_options"))

            new_value = input(_t("shared.utils.batch_operations.prompt_new_value")).strip()
            if new_value:
                fixed_record[field] = new_value

        # Validate fixed record
        errors = self.validate_student_data(fixed_record)
        if errors:
            print("\n" + _t("shared.utils.batch_operations.still_has_errors", errors='; '.join(errors)))
            retry = input(_t("shared.utils.batch_operations.prompt_try_fixing"))
            if retry.lower() == 'y':
                return self.fix_record_interactive(fixed_record)
            else:
                return None
        else:
            print(_t("shared.utils.batch_operations.record_fixed"))
            return fixed_record

    def find_duplicates_in_import(self, records: List[Dict]) -> List[Dict]:
        """Find potential duplicates between import records and existing database"""
        from education_system.systems.university.infrastructure.database.db import sqlite3
        duplicates = []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all existing students
            cursor.execute("SELECT * FROM students")
            existing_students = cursor.fetchall()

            for record in records:
                for existing in existing_students:
                    confidence = self.calculate_duplicate_confidence(record, existing)

                    if confidence > 0.7:  # 70% confidence threshold
                        duplicates.append({
                            'import_record': record,
                            'existing_record': existing,
                            'confidence': confidence
                        })

        except sqlite3.Error as e:
            logger.error(f"Error checking duplicates: {e}")
        finally:
            conn.close()

        return duplicates

    def calculate_duplicate_confidence(self, import_record: Dict, existing_record: Tuple) -> float:
        """Calculate confidence that two records are duplicates"""
        # existing_record format: (student_id, email, title, first_name, middle_name, last_name, gender, dob, age, course, registration_datetime)

        confidence_factors = []

        # Name matching
        import_first = str(import_record.get('first_name', '')).lower()
        import_last = str(import_record.get('last_name', '')).lower()
        existing_first = str(existing_record[3]).lower()
        existing_last = str(existing_record[5]).lower()

        name_ratio = (fuzz.ratio(import_first, existing_first) + fuzz.ratio(import_last, existing_last)) / 200
        confidence_factors.append(('name', name_ratio, 0.4))  # 40% weight

        # Email matching
        import_email = str(import_record.get('email_address', '')).lower()
        existing_email = str(existing_record[1]).lower()

        if import_email and existing_email:
            email_ratio = fuzz.ratio(import_email, existing_email) / 100
            confidence_factors.append(('email', email_ratio, 0.3))  # 30% weight

        # DOB matching
        import_dob = str(import_record.get('dob', ''))
        existing_dob = str(existing_record[7])

        if import_dob and existing_dob:
            dob_match = 1.0 if import_dob == existing_dob else 0.0
            confidence_factors.append(('dob', dob_match, 0.3))  # 30% weight

        # Calculate weighted confidence
        total_confidence = sum(factor[1] * factor[2] for factor in confidence_factors)
        total_weight = sum(factor[2] for factor in confidence_factors)

        return total_confidence / total_weight if total_weight > 0 else 0.0

    def handle_duplicates(self, records: List[Dict], duplicates: List[Dict], choice: str) -> ImportResult:
        """Handle duplicates based on user choice"""
        result = ImportResult()
        result.start_time = datetime.datetime.now()

        duplicate_import_records = {id(dup['import_record']): dup for dup in duplicates}

        if choice == '1':  # Skip all duplicates
            non_duplicate_records = [r for r in records if id(r) not in duplicate_import_records]
            result = self.import_valid_records(non_duplicate_records)
            result.duplicates_skipped = len(duplicates)

        elif choice == '2':  # Update existing records
            non_duplicate_records = [r for r in records if id(r) not in duplicate_import_records]

            # Import non-duplicates
            result = self.import_valid_records(non_duplicate_records)

            # Update duplicates
            for dup in duplicates:
                self.update_existing_record(dup['existing_record'][0], dup['import_record'])
                result.duplicates_updated += 1

        elif choice == '3':  # Handle individually
            non_duplicate_records = [r for r in records if id(r) not in duplicate_import_records]

            # Import non-duplicates first
            result = self.import_valid_records(non_duplicate_records)

            # Handle each duplicate
            for i, dup in enumerate(duplicates, 1):
                print(f"\n{_t('batch_ops.duplicates.header', current=i, total=len(duplicates))}")
                print(_t("batch_ops.duplicates.import_record", first_name=dup['import_record']['first_name'], last_name=dup['import_record']['last_name']))
                print(_t("batch_ops.duplicates.existing_record", first_name=dup['existing_record'][3], last_name=dup['existing_record'][5], id=dup['existing_record'][0]))
                print(_t("batch_ops.duplicates.confidence", confidence=f"{dup['confidence']:.0%}"))

                action = input(_t("batch_ops.duplicates.prompt_action")).lower()

                if action == 'u':
                    self.update_existing_record(dup['existing_record'][0], dup['import_record'])
                    result.duplicates_updated += 1
                elif action == 'i':
                    self.import_valid_records([dup['import_record']])
                    result.successful_imports += 1
                else:
                    result.duplicates_skipped += 1

        else:  # Import all as new
            result = self.import_valid_records(records)

        result.end_time = datetime.datetime.now()
        return result

    def find_duplicate_students(self):
        """Find potential duplicate students in database"""
        from education_system.systems.university.infrastructure.database.db import sqlite3
        import json
        print("\n" + _t("shared.utils.batch_operations.title_find_duplicates"))

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM students ORDER BY last_name, first_name")
            students = cursor.fetchall()

            print(_t("shared.utils.batch_operations.analyzing_for_duplicates", count=len(students)))

            duplicates = []

            # Compare each student with others
            for i, student1 in enumerate(students):
                progress = (i + 1) / len(students) * 100
                print(f"\rProgress: {progress:.1f}%", end='', flush=True)

                for j, student2 in enumerate(students[i+1:], i+1):
                    # Create fake import record for comparison
                    fake_record = {
                        'first_name': student2[3],
                        'last_name': student2[5],
                        'email_address': student2[1],
                        'dob': student2[7]
                    }

                    confidence = self.calculate_duplicate_confidence(fake_record, student1)

                    if confidence > 0.7:  # 70% confidence threshold
                        duplicates.append({
                            'student1': {
                                'id': student1[0],
                                'name': f"{student1[3]} {student1[5]}",
                                'email': student1[1],
                                'dob': student1[7]
                            },
                            'student2': {
                                'id': student2[0],
                                'name': f"{student2[3]} {student2[5]}",
                                'email': student2[1],
                                'dob': student2[7]
                            },
                            'confidence': confidence
                        })

            print("\n" + _t("shared.utils.batch_operations.found_duplicate_pairs", count=len(duplicates)))

            if duplicates:
                print("\n" + _t("shared.utils.batch_operations.potential_duplicates"))
                for i, dup in enumerate(duplicates[:10], 1):
                    print(f"{i}. {dup['student1']['name']} (ID: {dup['student1']['id']}) "
                          f"<-> {dup['student2']['name']} (ID: {dup['student2']['id']}) "
                          f"- {_t('shared.utils.batch_operations.confidence')}: {dup['confidence']:.0%}")

                if len(duplicates) > 10:
                    print(_t("shared.utils.batch_operations.and_more_duplicates", count=len(duplicates) - 10))

                # Export duplicates report
                filename = f"duplicate_students_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(duplicates, f, indent=2, default=str)
                print(_t("shared.utils.batch_operations.duplicates_report_saved", filename=filename))

                # Offer to merge duplicates
                merge_choice = input("\n" + _t("shared.utils.batch_operations.prompt_merge_duplicates"))
                if merge_choice.lower() == 'y':
                    self.interactive_duplicate_merger(duplicates)
            else:
                print(_t("shared.utils.batch_operations.no_duplicates"))

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def interactive_duplicate_merger(self, duplicates: List[Dict]):
        """Interactive tool for merging duplicate records"""
        print("\n" + _t("shared.utils.batch_operations.title_duplicate_merger"))

        for i, dup in enumerate(duplicates, 1):
            print(f"\n--- {_t('shared.utils.batch_operations.duplicate_pair', current=i, total=len(duplicates))} ---")
            print(f"{_t('shared.utils.batch_operations.student')} 1: {dup['student1']['name']} (ID: {dup['student1']['id']})")
            print(f"           Email: {dup['student1']['email']}, DOB: {dup['student1']['dob']}")
            print(f"{_t('shared.utils.batch_operations.student')} 2: {dup['student2']['name']} (ID: {dup['student2']['id']})")
            print(f"           Email: {dup['student2']['email']}, DOB: {dup['student2']['dob']}")
            print(f"{_t('shared.utils.batch_operations.confidence')}: {dup['confidence']:.0%}")

            print("\n" + _t("shared.utils.batch_operations.options"))
            print(_t("shared.utils.batch_operations.option_keep_student_1"))
            print(_t("shared.utils.batch_operations.option_keep_student_2"))
            print(_t("shared.utils.batch_operations.option_merge_manual"))
            print(_t("shared.utils.batch_operations.option_skip_pair"))
            print(_t("shared.utils.batch_operations.option_skip_all"))

            choice = input(_t("shared.utils.batch_operations.prompt_choose_1_5"))

            if choice == '1':
                self.merge_students(dup['student1']['id'], dup['student2']['id'], keep_first=True)
            elif choice == '2':
                self.merge_students(dup['student2']['id'], dup['student1']['id'], keep_first=True)
            elif choice == '3':
                self.manual_merge_students(dup['student1']['id'], dup['student2']['id'])
            elif choice == '5':
                break
            # Choice 4 (skip) does nothing

    def merge_students(self, keep_id: str, delete_id: str, keep_first: bool = True):
        """Merge student records - DISABLED: Use main GUI for student management"""
        print("\n" + _t("shared.utils.batch_operations.merge_disabled"))
        print(_t("shared.utils.batch_operations.deletion_centralized"))
        print("\n" + _t("shared.utils.batch_operations.use_main_gui"))
        print(_t("shared.utils.batch_operations.bullet_delete_duplicates"))
        print(_t("shared.utils.batch_operations.bullet_manage_records"))
        print("\n" + _t("shared.utils.batch_operations.ensures_consistency"))
