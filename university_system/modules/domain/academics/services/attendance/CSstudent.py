class CSStudent:
    def __init__(self, student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, compulsory_module_1, compulsory_module_2, module1, module2, module3, module4, registration_datetime):
        self.student_id = student_id
        self.email_address = email_address
        self.title = title
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.gender = gender
        self.age = age
        self.dob = dob
        self.course = course
        self.compulsory_module_1 = compulsory_module_1
        self.compulsory_module_2 = compulsory_module_2
        self.module1 = module1
        self.module2 = module2
        self.module3 = module3
        self.module4 = module4
        self.registration_datetime = registration_datetime

    def get_full_name(self):
        """Return formatted full name."""
        name_parts = [self.title, self.first_name]
        if self.middle_name:
            name_parts.append(self.middle_name)
        name_parts.append(self.last_name)
        return " ".join(part for part in name_parts if part)

    def get_enrolled_modules(self):
        """Return list of enrolled modules."""
        modules = [self.compulsory_module_1, self.compulsory_module_2]
        optional_modules = [self.module1, self.module2, self.module3, self.module4]
        modules.extend([mod for mod in optional_modules if mod])
        return modules

    def calculate_gpa(self):
        """Calculate student's GPA - placeholder implementation."""
        # This would typically query grades from database
        return 0.0

    def __str__(self):
        """String representation of student."""
        return f"CS Student: {self.get_full_name()} (ID: {self.student_id})"

    def __repr__(self):
        """Object representation for debugging."""
        return f"CSStudent(student_id={self.student_id}, name='{self.get_full_name()}', course='{self.course}')"

