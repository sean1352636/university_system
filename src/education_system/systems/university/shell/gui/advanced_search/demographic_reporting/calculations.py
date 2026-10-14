"""Extracted demographic-reporting behaviour."""
from . import *

class AdvancedCalculationsMixin:
    def _process_demographics(self):
        """Process raw data into demographic statistics"""
        self.report_data = {
            'total': len(self.raw_data),
            'gender': {},
            'age': {},
            'age_group': {},
            'course': {},
            'status': {},
            'ethnicity': {},
            'academic_level': {}
        }

        for row in self.raw_data:
            # row: student_id, full_name, gender, age, course, status, ethnicity, academic_level, age_group, enrollment_date
            gender = row[2] or 'Unknown'
            age = row[3] or 0
            course = row[4] or 'Unknown'
            status = row[5] or 'Unknown'
            ethnicity = row[6] or 'Unknown'
            academic_level = row[7] or 'Unknown'
            age_group = row[8] or 'Unknown'

            # Count by category
            self.report_data['gender'][gender] = self.report_data['gender'].get(gender, 0) + 1
            self.report_data['course'][course] = self.report_data['course'].get(course, 0) + 1
            self.report_data['status'][status] = self.report_data['status'].get(status, 0) + 1
            self.report_data['ethnicity'][ethnicity] = self.report_data['ethnicity'].get(ethnicity, 0) + 1
            self.report_data['academic_level'][academic_level] = self.report_data['academic_level'].get(academic_level, 0) + 1
            self.report_data['age_group'][age_group] = self.report_data['age_group'].get(age_group, 0) + 1

            # Age buckets
            if age > 0:
                if age < 20:
                    bucket = 'Under 20'
                elif age < 25:
                    bucket = '20-24'
                elif age < 30:
                    bucket = '25-29'
                elif age < 40:
                    bucket = '30-39'
                elif age < 50:
                    bucket = '40-49'
                else:
                    bucket = '50+'
                self.report_data['age'][bucket] = self.report_data['age'].get(bucket, 0) + 1

    def _create_visual_bar(self, percentage, width=30):
        """Create ASCII visual bar for percentage"""
        filled = int(percentage / 100 * width)
        return '[' + '#' * filled + '-' * (width - filled) + ']'
