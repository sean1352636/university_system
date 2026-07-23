import re


class ValidationMixin:
    def validate_course_code(self, code):
        """Validate the course code format (e.g., CS101, MATH200)"""
        pattern = r'^[A-Z]{2,4}\d{2,3}$'
        return bool(re.match(pattern, code))

    def validate_email(self, email):
        """Validate email format - delegates to centralized validator"""
        from education_system.post_18.university_system.modules.shared.utils.input_validation import is_valid_email
        return is_valid_email(email)

    def validate_time_format(self, time_str):
        """Validate time format (HH:MM)"""
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, time_str))

    def validate_days_of_week(self, days_str):
        """Validate days of week format"""
        valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
        days = [day.strip() for day in days_str.split(',')]
        return all(day in valid_days for day in days)
