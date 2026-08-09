"""Extracted demographic-reporting behaviour."""
from . import *

class AdvancedReportBuilderMixin:
    def _generate_report_text(self):
        """Generate complete text report"""
        if not self.report_data or self.report_data['total'] == 0:
            return "No data available for report."

        total = self.report_data['total']

        report = "=" * 90 + "\n"
        report += "                    ADVANCED STUDENT DEMOGRAPHIC REPORT\n"
        report += "=" * 90 + "\n"
        report += f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Total Students Analyzed: {total:,}\n"
        report += "=" * 90 + "\n\n"

        # Section 1: Gender Distribution
        report += "SECTION 1: GENDER DISTRIBUTION\n"
        report += "-" * 50 + "\n"
        report += f"{'Gender':<25} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 50 + "\n"
        for gender, count in sorted(self.report_data['gender'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            report += f"{gender:<25} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 2: Age Distribution
        report += "SECTION 2: AGE DISTRIBUTION\n"
        report += "-" * 50 + "\n"
        report += f"{'Age Group':<25} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 50 + "\n"
        age_order = ['Under 20', '20-24', '25-29', '30-39', '40-49', '50+']
        for age_bucket in age_order:
            count = self.report_data['age'].get(age_bucket, 0)
            pct = (count / total * 100) if total > 0 else 0
            report += f"{age_bucket:<25} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 3: Status Distribution
        report += "SECTION 3: ENROLLMENT STATUS\n"
        report += "-" * 50 + "\n"
        report += f"{'Status':<25} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 50 + "\n"
        for status, count in sorted(self.report_data['status'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            report += f"{status:<25} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 4: Course Enrollment
        report += "SECTION 4: COURSE ENROLLMENT (ALL)\n"
        report += "-" * 70 + "\n"
        report += f"{'Course':<45} {'Count':>10} {'Percentage':>12}\n"
        report += "-" * 70 + "\n"
        for course, count in sorted(self.report_data['course'].items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            course_display = course[:44] if len(course) > 44 else course
            report += f"{course_display:<45} {count:>10,} {pct:>11.1f}%\n"
        report += "\n"

        # Section 5: Ethnicity (if available)
        if self.report_data['ethnicity'] and any(k != 'Unknown' for k in self.report_data['ethnicity']):
            report += "SECTION 5: ETHNICITY DISTRIBUTION\n"
            report += "-" * 50 + "\n"
            report += f"{'Ethnicity':<25} {'Count':>10} {'Percentage':>12}\n"
            report += "-" * 50 + "\n"
            for ethnicity, count in sorted(self.report_data['ethnicity'].items(), key=lambda x: -x[1]):
                pct = (count / total * 100) if total > 0 else 0
                report += f"{ethnicity:<25} {count:>10,} {pct:>11.1f}%\n"
            report += "\n"

        # Section 6: Academic Level (if available)
        if self.report_data['academic_level'] and any(k != 'Unknown' for k in self.report_data['academic_level']):
            report += "SECTION 6: ACADEMIC LEVEL DISTRIBUTION\n"
            report += "-" * 50 + "\n"
            report += f"{'Academic Level':<25} {'Count':>10} {'Percentage':>12}\n"
            report += "-" * 50 + "\n"
            for level, count in sorted(self.report_data['academic_level'].items(), key=lambda x: -x[1]):
                pct = (count / total * 100) if total > 0 else 0
                report += f"{level:<25} {count:>10,} {pct:>11.1f}%\n"
            report += "\n"

        report += "=" * 90 + "\n"
        report += "                              END OF REPORT\n"
        report += "=" * 90 + "\n"

        return report

class StudentReportBuilderMixin:
    def _generate_report_text(self):
        """Generate formatted text report"""
        if not self.report_data:
            return "No data available for report."

        # Header
        report = "=" * 80 + "\n"
        report += "STUDENT DEMOGRAPHIC REPORT\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 80 + "\n\n"

        # Applied filters
        report += "APPLIED FILTERS:\n"
        report += "-" * 40 + "\n"
        for name, var in self.filter_vars.items():
            if var.get() != 'All':
                report += f"  {name.replace('_', ' ').title()}: {var.get()}\n"
        if all(v.get() == 'All' for v in self.filter_vars.values()):
            report += "  No filters applied (showing all students)\n"
        report += "\n"

        # Summary
        report += "SUMMARY:\n"
        report += "-" * 40 + "\n"
        report += f"  Total Students: {len(self.report_data)}\n\n"

        # Detailed results
        report += "DETAILED RESULTS:\n"
        report += "-" * 80 + "\n"
        report += f"{'ID':<15} {'Name':<25} {'Gender':<10} {'Age':<5} {'Course':<25} {'Status':<10}\n"
        report += "-" * 80 + "\n"

        for row in self.report_data:
            student_id = str(row[0])[:14]
            name = str(row[1])[:24].strip()
            gender = str(row[2] or 'N/A')[:9]
            age = str(row[3] or 'N/A')[:4]
            course = str(row[4] or 'N/A')[:24]
            status = str(row[5] or 'N/A')[:9]
            report += f"{student_id:<15} {name:<25} {gender:<10} {age:<5} {course:<25} {status:<10}\n"

        report += "\n" + "=" * 80 + "\n"
        report += "END OF REPORT\n"

        return report
