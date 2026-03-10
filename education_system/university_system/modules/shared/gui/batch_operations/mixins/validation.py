"""Data validation and cleaning mixin."""

import re

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    datetime, json, logging,
    Callable, Dict, List, Optional,
    tk, ttk, messagebox,
    DEFAULT_DB_PATH,
    sqlite3,
    _t,
    logger,
)


class ValidationMixin:
    """Mixin providing data validation, cleaning, and standardization methods."""

    def clean_and_fix_data(self, progress_callback=None) -> int:
        """Clean and fix common data issues. Returns the number of issues fixed."""
        issues = self.validate_and_clean_data(progress_callback)
        return len(issues)

    def validate_and_clean_data(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> List[Dict]:
        """Validate and clean data in the database with comprehensive validation and reporting.

        Performs comprehensive data validation and cleaning operations including:
        - Data type validation
        - Missing data detection and handling
        - Duplicate record identification and resolution
        - Data consistency checks
        - Format standardization
        - Relationship validation

        Parameters
        ----------
        progress_callback : Callable[[int, str], None], optional
            A callback that accepts an integer progress percentage and a message.

        Returns
        -------
        List[Dict]
            A list of dictionaries describing any issues found and actions taken.
        """
        self.progress_callback = progress_callback

        try:
            # Initialize validation results
            validation_results = []
            start_time = datetime.datetime.now()

            if self.progress_callback:
                self.progress_callback(5, "Starting data validation and cleaning...")

            # Connect to database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Step 1: Validate student records
            if self.progress_callback:
                self.progress_callback(10, "Validating student records...")

            student_issues = self._validate_student_data(cursor)
            validation_results.extend(student_issues)

            # Step 2: Check for duplicates
            if self.progress_callback:
                self.progress_callback(25, "Identifying duplicate records...")

            duplicate_issues = self._identify_and_handle_duplicates(cursor)
            validation_results.extend(duplicate_issues)

            # Step 3: Validate data integrity
            if self.progress_callback:
                self.progress_callback(40, "Checking data integrity...")

            integrity_issues = self._validate_data_integrity(cursor)
            validation_results.extend(integrity_issues)

            # Step 4: Standardize data formats
            if self.progress_callback:
                self.progress_callback(55, "Standardizing data formats...")

            format_fixes = self._standardize_data_formats(cursor)
            validation_results.extend(format_fixes)

            # Step 5: Validate relationships
            if self.progress_callback:
                self.progress_callback(70, "Validating data relationships...")

            relationship_issues = self._validate_relationships(cursor)
            validation_results.extend(relationship_issues)

            # Step 6: Clean orphaned records
            if self.progress_callback:
                self.progress_callback(85, "Cleaning orphaned records...")

            orphan_cleanup = self._clean_orphaned_records(cursor)
            validation_results.extend(orphan_cleanup)

            # Commit changes
            conn.commit()

            if self.progress_callback:
                self.progress_callback(95, "Generating validation report...")

            # Generate comprehensive report
            report_data = self._generate_validation_report(validation_results, start_time)

            # Save report to file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"data_validation_report_{timestamp}.json"
            with open(report_filename, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            if self.progress_callback:
                self.progress_callback(100, "Validation and cleaning complete!")

            # Show completion dialog with results
            try:
                self._show_validation_results_dialog(report_data, report_filename)
            except Exception:
                print(f"Validation completed. Report saved to {report_filename}")

            return validation_results

        except Exception as e:
            try:
                messagebox.showerror(_t("batch_ops.msg_titles.validation_error"), f"An error occurred during data validation: {str(e)}")
            except Exception:
                print(f"Error during data validation: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()

    def _validate_student_data(self, cursor) -> List[Dict]:
        """Validate student data fields"""
        issues = []

        try:
            # Check for missing required fields
            cursor.execute("""
                SELECT student_id, first_name, last_name, email_address, phone_number
                FROM students
                WHERE first_name IS NULL OR first_name = ''
                   OR last_name IS NULL OR last_name = ''
                   OR email_address IS NULL OR email_address = ''
            """)

            missing_data = cursor.fetchall()
            for record in missing_data:
                student_id, first_name, last_name, email, phone = record
                missing_fields = []
                if not first_name: missing_fields.append('first_name')
                if not last_name: missing_fields.append('last_name')
                if not email: missing_fields.append('email_address')

                issues.append({
                    'type': 'missing_data',
                    'severity': 'high',
                    'student_id': student_id,
                    'description': f'Missing required fields: {", ".join(missing_fields)}',
                    'action': 'flagged_for_review',
                    'timestamp': datetime.datetime.now().isoformat()
                })

            # Validate email formats
            cursor.execute("SELECT student_id, email_address FROM students WHERE email_address IS NOT NULL")
            email_records = cursor.fetchall()

            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

            for student_id, email in email_records:
                if email and not re.match(email_pattern, email):
                    issues.append({
                        'type': 'invalid_format',
                        'severity': 'medium',
                        'student_id': student_id,
                        'field': 'email_address',
                        'current_value': email,
                        'description': 'Invalid email format',
                        'action': 'requires_correction',
                        'timestamp': datetime.datetime.now().isoformat()
                    })

                    # Attempt basic email correction
                    corrected_email = self._attempt_email_correction(email)
                    if corrected_email and corrected_email != email:
                        cursor.execute(
                            "UPDATE students SET email_address = ? WHERE student_id = ?",
                            (corrected_email, student_id)
                        )
                        issues.append({
                            'type': 'data_corrected',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'email_address',
                            'old_value': email,
                            'new_value': corrected_email,
                            'description': 'Email format automatically corrected',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

            # Validate phone numbers
            cursor.execute("SELECT student_id, phone_number FROM students WHERE phone_number IS NOT NULL")
            phone_records = cursor.fetchall()

            for student_id, phone in phone_records:
                if phone:
                    # Clean phone number for validation
                    clean_phone = re.sub(r'[^\d]', '', phone)
                    if len(clean_phone) < 10:
                        issues.append({
                            'type': 'invalid_format',
                            'severity': 'medium',
                            'student_id': student_id,
                            'field': 'phone_number',
                            'current_value': phone,
                            'description': 'Phone number too short',
                            'action': 'requires_correction',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

        except Exception as e:
            issues.append({
                'type': 'validation_error',
                'severity': 'critical',
                'description': f'Error during student data validation: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _identify_and_handle_duplicates(self, cursor) -> List[Dict]:
        """Identify and handle duplicate records"""
        issues = []

        try:
            # Find potential duplicates by email
            cursor.execute("""
                SELECT email_address, COUNT(*) as count,
                       GROUP_CONCAT(student_id) as student_ids
                FROM students
                WHERE email_address IS NOT NULL AND email_address != ''
                GROUP BY LOWER(email_address)
                HAVING COUNT(*) > 1
            """)

            email_duplicates = cursor.fetchall()
            for email, count, student_ids in email_duplicates:
                ids = student_ids.split(',')
                issues.append({
                    'type': 'duplicate_email',
                    'severity': 'high',
                    'email': email,
                    'count': count,
                    'student_ids': ids,
                    'description': f'Email address {email} used by {count} students',
                    'action': 'requires_manual_review',
                    'timestamp': datetime.datetime.now().isoformat()
                })

            # Find duplicates by name and potential typos
            cursor.execute("""
                SELECT first_name, last_name, COUNT(*) as count,
                       GROUP_CONCAT(student_id) as student_ids
                FROM students
                WHERE first_name IS NOT NULL AND last_name IS NOT NULL
                GROUP BY LOWER(first_name), LOWER(last_name)
                HAVING COUNT(*) > 1
            """)

            name_duplicates = cursor.fetchall()
            for first_name, last_name, count, student_ids in name_duplicates:
                if count > 3:  # Only flag if more than 3 (could be common names)
                    ids = student_ids.split(',')
                    issues.append({
                        'type': 'duplicate_name',
                        'severity': 'medium',
                        'first_name': first_name,
                        'last_name': last_name,
                        'count': count,
                        'student_ids': ids,
                        'description': f'Name "{first_name} {last_name}" appears {count} times',
                        'action': 'review_for_duplicates',
                        'timestamp': datetime.datetime.now().isoformat()
                    })

        except Exception as e:
            issues.append({
                'type': 'duplicate_check_error',
                'severity': 'critical',
                'description': f'Error during duplicate detection: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _validate_data_integrity(self, cursor) -> List[Dict]:
        """Validate data integrity and consistency"""
        issues = []

        try:
            # Check for students with grades but no enrollment records
            cursor.execute("""
                SELECT DISTINCT g.student_id
                FROM grades g
                LEFT JOIN enrollments e ON g.student_id = e.student_id
                WHERE e.student_id IS NULL
            """)

            orphan_grades = cursor.fetchall()
            for (student_id,) in orphan_grades:
                issues.append({
                    'type': 'integrity_violation',
                    'severity': 'high',
                    'student_id': student_id,
                    'description': 'Student has grades but no enrollment records',
                    'action': 'requires_investigation',
                    'timestamp': datetime.datetime.now().isoformat()
                })

            # Check for invalid grade values
            cursor.execute("""
                SELECT student_id, subject, grade
                FROM grades
                WHERE grade NOT IN ('A', 'B', 'C', 'D', 'F', 'A+', 'A-', 'B+', 'B-', 'C+', 'C-', 'D+', 'D-')
                  AND grade NOT BETWEEN 0 AND 100
            """)

            invalid_grades = cursor.fetchall()
            for student_id, subject, grade in invalid_grades:
                issues.append({
                    'type': 'invalid_data',
                    'severity': 'medium',
                    'student_id': student_id,
                    'field': 'grade',
                    'subject': subject,
                    'current_value': grade,
                    'description': 'Invalid grade value',
                    'action': 'requires_correction',
                    'timestamp': datetime.datetime.now().isoformat()
                })

        except Exception as e:
            issues.append({
                'type': 'integrity_check_error',
                'severity': 'critical',
                'description': f'Error during integrity validation: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _standardize_data_formats(self, cursor) -> List[Dict]:
        """Standardize data formats across the database"""
        issues = []

        try:
            # Standardize name capitalization
            cursor.execute("SELECT student_id, first_name, last_name FROM students")
            name_records = cursor.fetchall()

            for student_id, first_name, last_name in name_records:
                if first_name:
                    standardized_first = first_name.strip().title()
                    if standardized_first != first_name:
                        cursor.execute(
                            "UPDATE students SET first_name = ? WHERE student_id = ?",
                            (standardized_first, student_id)
                        )
                        issues.append({
                            'type': 'format_standardized',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'first_name',
                            'old_value': first_name,
                            'new_value': standardized_first,
                            'description': 'Name capitalization standardized',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

                if last_name:
                    standardized_last = last_name.strip().title()
                    if standardized_last != last_name:
                        cursor.execute(
                            "UPDATE students SET last_name = ? WHERE student_id = ?",
                            (standardized_last, student_id)
                        )
                        issues.append({
                            'type': 'format_standardized',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'last_name',
                            'old_value': last_name,
                            'new_value': standardized_last,
                            'description': 'Name capitalization standardized',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

            # Standardize email addresses (lowercase)
            cursor.execute("SELECT student_id, email_address FROM students WHERE email_address IS NOT NULL")
            email_records = cursor.fetchall()

            for student_id, email in email_records:
                if email:
                    standardized_email = email.strip().lower()
                    if standardized_email != email:
                        cursor.execute(
                            "UPDATE students SET email_address = ? WHERE student_id = ?",
                            (standardized_email, student_id)
                        )
                        issues.append({
                            'type': 'format_standardized',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'email_address',
                            'old_value': email,
                            'new_value': standardized_email,
                            'description': 'Email address standardized to lowercase',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

        except Exception as e:
            issues.append({
                'type': 'standardization_error',
                'severity': 'critical',
                'description': f'Error during format standardization: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _validate_relationships(self, cursor) -> List[Dict]:
        """Validate relationships between tables"""
        issues = []

        try:
            # Check for enrollments without valid students
            cursor.execute("""
                SELECT e.student_id, e.course_id, e.semester
                FROM enrollments e
                LEFT JOIN students s ON e.student_id = s.student_id
                WHERE s.student_id IS NULL
            """)

            invalid_enrollments = cursor.fetchall()
            for student_id, course_id, semester in invalid_enrollments:
                issues.append({
                    'type': 'relationship_violation',
                    'severity': 'high',
                    'table': 'enrollments',
                    'student_id': student_id,
                    'course_id': course_id,
                    'semester': semester,
                    'description': 'Enrollment record references non-existent student',
                    'action': 'requires_cleanup',
                    'timestamp': datetime.datetime.now().isoformat()
                })

        except Exception as e:
            issues.append({
                'type': 'relationship_check_error',
                'severity': 'critical',
                'description': f'Error during relationship validation: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _clean_orphaned_records(self, cursor) -> List[Dict]:
        """Clean up orphaned records"""
        issues = []

        try:
            # Clean up orphaned grade records
            cursor.execute("""
                DELETE FROM grades
                WHERE student_id NOT IN (SELECT student_id FROM students)
            """)

            orphaned_grades_cleaned = cursor.rowcount
            if orphaned_grades_cleaned > 0:
                issues.append({
                    'type': 'cleanup_completed',
                    'severity': 'info',
                    'table': 'grades',
                    'records_cleaned': orphaned_grades_cleaned,
                    'description': f'Cleaned {orphaned_grades_cleaned} orphaned grade records',
                    'action': 'auto_cleaned',
                    'timestamp': datetime.datetime.now().isoformat()
                })

        except Exception as e:
            issues.append({
                'type': 'cleanup_error',
                'severity': 'critical',
                'description': f'Error during orphaned record cleanup: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _attempt_email_correction(self, email: str) -> str:
        """Attempt basic email format corrections"""
        if not email:
            return email

        # Common corrections
        corrections = {
            'gmail.com': ['gmai.com', 'gmial.com', 'gmail.co'],
            'yahoo.com': ['yaho.com', 'yahoo.co'],
            'hotmail.com': ['hotmai.com', 'hotmail.co'],
            'outlook.com': ['outlok.com', 'outlook.co']
        }

        email = email.strip().lower()

        # Fix common domain typos
        for correct_domain, typos in corrections.items():
            for typo in typos:
                if email.endswith(f'@{typo}'):
                    return email.replace(f'@{typo}', f'@{correct_domain}')

        # Fix missing @ symbol
        if ' ' in email and '@' not in email:
            parts = email.split(' ')
            if len(parts) == 2 and '.' in parts[1]:
                return f"{parts[0]}@{parts[1]}"

        return email

    def _generate_validation_report(self, validation_results: List[Dict], start_time) -> Dict:
        """Generate comprehensive validation report"""
        end_time = datetime.datetime.now()

        # Categorize issues
        categories = {}
        severities = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        actions = {}

        for issue in validation_results:
            # Count by type
            issue_type = issue.get('type', 'unknown')
            categories[issue_type] = categories.get(issue_type, 0) + 1

            # Count by severity
            severity = issue.get('severity', 'unknown')
            if severity in severities:
                severities[severity] += 1

            # Count by action
            action = issue.get('action', 'unknown')
            actions[action] = actions.get(action, 0) + 1

        report = {
            'summary': {
                'total_issues_found': len(validation_results),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': (end_time - start_time).total_seconds(),
                'validation_status': 'completed'
            },
            'issue_breakdown': {
                'by_category': categories,
                'by_severity': severities,
                'by_action': actions
            },
            'detailed_issues': validation_results,
            'recommendations': self._generate_recommendations(validation_results),
            'report_metadata': {
                'generated_by': 'University Management System - Batch Operations',
                'version': '1.0',
                'report_type': 'Data Validation and Cleaning'
            }
        }

        return report

    def _generate_recommendations(self, validation_results: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []

        # Count critical issues
        critical_count = len([r for r in validation_results if r.get('severity') == 'critical'])
        if critical_count > 0:
            recommendations.append(f"Address {critical_count} critical issues immediately to prevent data corruption")

        # Count missing data issues
        missing_data_count = len([r for r in validation_results if r.get('type') == 'missing_data'])
        if missing_data_count > 0:
            recommendations.append(f"Review {missing_data_count} records with missing required fields")

        # Count duplicate issues
        duplicate_count = len([r for r in validation_results if 'duplicate' in r.get('type', '')])
        if duplicate_count > 0:
            recommendations.append(f"Investigate {duplicate_count} potential duplicate records")

        # Count format issues
        format_count = len([r for r in validation_results if r.get('type') == 'invalid_format'])
        if format_count > 0:
            recommendations.append(f"Correct {format_count} invalid data formats")

        # General recommendations
        recommendations.extend([
            "Implement data validation at input stage to prevent future issues",
            "Schedule regular data validation runs (weekly or monthly)",
            "Consider implementing automated data quality monitoring",
            "Train data entry staff on proper formatting standards"
        ])

        return recommendations

    def _show_validation_results_dialog(self, report_data: Dict, report_filename: str):
        """Show validation results in a dialog"""
        try:
            result_dialog = tk.Toplevel(self.root)
            result_dialog.title(_t("batch_ops.windows.validation_results"))
            result_dialog.geometry("800x600")
            result_dialog.transient(self.root)
            result_dialog.grab_set()

            # Center the dialog
            result_dialog.update_idletasks()
            x = (result_dialog.winfo_screenwidth() // 2) - (result_dialog.winfo_width() // 2)
            y = (result_dialog.winfo_screenheight() // 2) - (result_dialog.winfo_height() // 2)
            result_dialog.geometry(f"+{x}+{y}")

            # Header
            header_frame = tk.Frame(result_dialog, bg='#4CAF50')
            header_frame.pack(fill=tk.X, pady=(0, 10))

            tk.Label(header_frame, text="Data Validation and Cleaning Results",
                    font=('Arial', 14, 'bold'), bg='#4CAF50', fg='white').pack(pady=15)

            # Create notebook for different views
            notebook = ttk.Notebook(result_dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Summary tab
            summary_frame = ttk.Frame(notebook)
            notebook.add(summary_frame, text="Summary")

            summary_text = tk.Text(summary_frame, wrap=tk.WORD, font=('Courier', 9))
            summary_scroll = ttk.Scrollbar(summary_frame, orient=tk.VERTICAL, command=summary_text.yview)
            summary_text.configure(yscrollcommand=summary_scroll.set)

            summary = report_data['summary']
            breakdown = report_data['issue_breakdown']

            NL = '\n'
            category_lines = NL.join([f"\u2022 {cat.replace('_', ' ').title()}: {count}" for cat, count in breakdown['by_category'].items()])
            action_lines = NL.join([f"\u2022 {action.replace('_', ' ').title()}: {count}" for action, count in breakdown['by_action'].items()])
            recommendation_lines = NL.join([f"\u2022 {rec}" for rec in report_data['recommendations']])

            summary_content = f"""DATA VALIDATION SUMMARY
=======================

Duration: {summary['duration_seconds']:.2f} seconds
Total Issues Found: {summary['total_issues_found']}
Status: {summary['validation_status'].title()}

ISSUE BREAKDOWN BY SEVERITY:
\u2022 Critical: {breakdown['by_severity'].get('critical', 0)}
\u2022 High: {breakdown['by_severity'].get('high', 0)}
\u2022 Medium: {breakdown['by_severity'].get('medium', 0)}
\u2022 Low: {breakdown['by_severity'].get('low', 0)}
\u2022 Info: {breakdown['by_severity'].get('info', 0)}

ISSUE BREAKDOWN BY CATEGORY:
{category_lines}

ACTIONS TAKEN:
{action_lines}

RECOMMENDATIONS:
{recommendation_lines}

Report saved to: {report_filename}
"""

            summary_text.insert(tk.END, summary_content)
            summary_text.config(state=tk.DISABLED)
            summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            summary_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            # Detailed issues tab
            issues_frame = ttk.Frame(notebook)
            notebook.add(issues_frame, text="Detailed Issues")

            issues_tree = ttk.Treeview(issues_frame, columns=("Type", "Severity", "Description", "Action"), show="tree headings")
            issues_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            issues_tree.heading("#0", text=_t("batch_ops.columns.id"))
            issues_tree.heading("Type", text=_t("batch_ops.columns.type"))
            issues_tree.heading("Severity", text=_t("batch_ops.columns.severity"))
            issues_tree.heading("Description", text=_t("batch_ops.columns.description"))
            issues_tree.heading("Action", text=_t("batch_ops.columns.action"))

            issues_tree.column("#0", width=50)
            issues_tree.column("Type", width=120)
            issues_tree.column("Severity", width=80)
            issues_tree.column("Description", width=300)
            issues_tree.column("Action", width=120)

            # Populate issues
            for i, issue in enumerate(report_data['detailed_issues'][:100]):  # Limit to first 100
                issues_tree.insert("", "end", text=str(i+1),
                                  values=(issue.get('type', ''), issue.get('severity', ''),
                                         issue.get('description', ''), issue.get('action', '')))

            # Close button
            tk.Button(result_dialog, text=_t("batch_ops.buttons.close"), command=result_dialog.destroy,
                     bg='#f0f0f0', padx=20, pady=5).pack(pady=15)

        except Exception as e:
            print(f"Error showing results dialog: {e}")
            messagebox.showinfo("Validation Complete",
                              f"Data validation completed successfully!\n"
                              f"Report saved to: {report_filename}\n"
                              f"Total issues found: {report_data['summary']['total_issues_found']}")
