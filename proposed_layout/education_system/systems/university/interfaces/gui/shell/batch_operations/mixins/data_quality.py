"""Data quality dashboard mixin."""

from education_system.systems.university.interfaces.gui.shell.batch_operations.constants import (
    datetime, logging,
    Dict,
    logger,
)


class DataQualityMixin:
    """Mixin providing data quality dashboard and metrics."""

    def data_quality_dashboard(self, progress_callback=None) -> Dict:
        """Comprehensive data quality dashboard - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, "Gathering data quality metrics...")

            dashboard = {
                'generated_at': datetime.datetime.now().isoformat(),
                'overall_score': 0,
                'metrics': {},
                'issues': [],
                'recommendations': []
            }

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Total student count
                cursor.execute("SELECT COUNT(*) FROM students")
                total_students = cursor.fetchone()[0]
                dashboard['metrics']['total_students'] = total_students

                if progress_callback:
                    progress_callback(20, "Checking data completeness...")

                # Missing data check
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN email IS NULL OR email = '' THEN 1 ELSE 0 END) as missing_email,
                        SUM(CASE WHEN phone_number IS NULL OR phone_number = '' THEN 1 ELSE 0 END) as missing_phone,
                        SUM(CASE WHEN address IS NULL OR address = '' THEN 1 ELSE 0 END) as missing_address,
                        SUM(CASE WHEN date_of_birth IS NULL OR date_of_birth = '' THEN 1 ELSE 0 END) as missing_dob
                    FROM students
                """)
                missing = cursor.fetchone()
                dashboard['metrics']['missing_data'] = {
                    'email': missing[0],
                    'phone': missing[1],
                    'address': missing[2],
                    'date_of_birth': missing[3]
                }

                if progress_callback:
                    progress_callback(40, "Checking for duplicates...")

                # Duplicate check
                duplicates = self.find_duplicate_students(None)
                dashboard['metrics']['duplicates_found'] = len(duplicates)

                if progress_callback:
                    progress_callback(60, "Validating data formats...")

                # Invalid email format check
                cursor.execute("""
                    SELECT COUNT(*) FROM students
                    WHERE email IS NOT NULL AND email != ''
                    AND email NOT LIKE '%@%.%'
                """)
                invalid_emails = cursor.fetchone()[0]
                dashboard['metrics']['invalid_emails'] = invalid_emails

                if progress_callback:
                    progress_callback(80, "Calculating quality score...")

                # Calculate overall quality score (0-100)
                completeness_score = (1 - sum(missing) / (total_students * 4)) * 100 if total_students > 0 else 0
                duplicate_penalty = min(len(duplicates) * 5, 30)  # Max 30 point penalty
                format_penalty = min(invalid_emails * 2, 20)  # Max 20 point penalty

                overall_score = max(0, completeness_score - duplicate_penalty - format_penalty)
                dashboard['overall_score'] = round(overall_score, 2)

                # Generate issues
                if sum(missing) > 0:
                    dashboard['issues'].append(f"{sum(missing)} records with missing data")
                if len(duplicates) > 0:
                    dashboard['issues'].append(f"{len(duplicates)} potential duplicate records")
                if invalid_emails > 0:
                    dashboard['issues'].append(f"{invalid_emails} records with invalid email format")

                # Generate recommendations
                if overall_score < 70:
                    dashboard['recommendations'].append("Data quality is below acceptable threshold - immediate action required")
                if sum(missing) > total_students * 0.1:
                    dashboard['recommendations'].append("Implement mandatory field validation for new entries")
                if len(duplicates) > 0:
                    dashboard['recommendations'].append("Review and merge duplicate records")
                if invalid_emails > 0:
                    dashboard['recommendations'].append("Validate and correct email formats")

                dashboard['recommendations'].append("Schedule regular data quality audits")

                if progress_callback:
                    progress_callback(100, "Dashboard generation complete")

                logger.info(f"Generated data quality dashboard - Score: {overall_score}")
                return dashboard

        except Exception as e:
            logger.error(f"Error generating data quality dashboard: {e}")
            raise
