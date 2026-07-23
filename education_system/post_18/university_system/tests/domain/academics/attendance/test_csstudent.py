"""
Test suite for CSStudent Class

Tests the Computer Science student model class including:
- Initialization and attributes
- Full name formatting
- Module enrollment tracking
- GPA calculation
- String representations
"""

import pytest
from datetime import datetime
from education_system.post_18.university_system.modules.domain.academics.services.attendance.CSstudent import CSStudent


class TestCSStudentInitialization:
    """Test CSStudent class initialization"""

    def test_basic_initialization(self):
        """Test basic student initialization with all parameters"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2="CS202",
            module3="CS203",
            module4="CS204",
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.student_id == "CS001"
        assert student.email_address == "john.doe@university.edu"
        assert student.first_name == "John"
        assert student.last_name == "Doe"
        assert student.course == "Computer Science"

    def test_initialization_without_middle_name(self):
        """Test student initialization without middle name"""
        student = CSStudent(
            student_id="CS002",
            email_address="jane.smith@university.edu",
            title="Ms",
            first_name="Jane",
            middle_name=None,
            last_name="Smith",
            gender="Female",
            dob="2001-05-20",
            age=23,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.middle_name is None
        assert student.student_id == "CS002"

    def test_initialization_with_optional_modules_none(self):
        """Test student with no optional modules"""
        student = CSStudent(
            student_id="CS003",
            email_address="bob.jones@university.edu",
            title="Mr",
            first_name="Bob",
            middle_name="",
            last_name="Jones",
            gender="Male",
            dob="1999-12-10",
            age=25,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.module1 is None
        assert student.module2 is None


class TestCSStudentMethods:
    """Test CSStudent class methods"""

    def test_get_full_name_with_middle_name(self):
        """Test full name generation with middle name"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert full_name == "Mr John Michael Doe"

    def test_get_full_name_without_middle_name(self):
        """Test full name generation without middle name"""
        student = CSStudent(
            student_id="CS002",
            email_address="jane.smith@university.edu",
            title="Ms",
            first_name="Jane",
            middle_name=None,
            last_name="Smith",
            gender="Female",
            dob="2001-05-20",
            age=23,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert full_name == "Ms Jane Smith"

    def test_get_full_name_with_empty_middle_name(self):
        """Test full name generation with empty string middle name"""
        student = CSStudent(
            student_id="CS003",
            email_address="bob.jones@university.edu",
            title="Dr",
            first_name="Bob",
            middle_name="",
            last_name="Jones",
            gender="Male",
            dob="1999-12-10",
            age=25,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert full_name == "Dr Bob Jones"

    def test_get_enrolled_modules_all_modules(self):
        """Test getting all enrolled modules when all are present"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2="CS202",
            module3="CS203",
            module4="CS204",
            registration_datetime="2023-09-01 10:00:00"
        )

        modules = student.get_enrolled_modules()
        assert len(modules) == 6
        assert "CS101" in modules
        assert "CS102" in modules
        assert "CS201" in modules
        assert "CS202" in modules
        assert "CS203" in modules
        assert "CS204" in modules

    def test_get_enrolled_modules_compulsory_only(self):
        """Test getting modules when only compulsory modules are present"""
        student = CSStudent(
            student_id="CS002",
            email_address="jane.smith@university.edu",
            title="Ms",
            first_name="Jane",
            middle_name=None,
            last_name="Smith",
            gender="Female",
            dob="2001-05-20",
            age=23,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        modules = student.get_enrolled_modules()
        assert len(modules) == 2
        assert "CS101" in modules
        assert "CS102" in modules

    def test_get_enrolled_modules_partial_optional(self):
        """Test getting modules with some optional modules"""
        student = CSStudent(
            student_id="CS003",
            email_address="bob.jones@university.edu",
            title="Mr",
            first_name="Bob",
            middle_name="",
            last_name="Jones",
            gender="Male",
            dob="1999-12-10",
            age=25,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2="CS202",
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        modules = student.get_enrolled_modules()
        assert len(modules) == 4
        assert "CS101" in modules
        assert "CS102" in modules
        assert "CS201" in modules
        assert "CS202" in modules

    def test_calculate_gpa_placeholder(self):
        """Test GPA calculation (placeholder implementation)"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        gpa = student.calculate_gpa()
        # Placeholder returns 0.0
        assert gpa == 0.0
        assert isinstance(gpa, float)


class TestCSStudentStringRepresentation:
    """Test CSStudent string representations"""

    def test_str_representation(self):
        """Test __str__ method"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        str_repr = str(student)
        assert "CS Student" in str_repr
        assert "John" in str_repr
        assert "Doe" in str_repr
        assert "CS001" in str_repr

    def test_repr_representation(self):
        """Test __repr__ method"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        repr_str = repr(student)
        assert "CSStudent" in repr_str
        assert "CS001" in repr_str
        assert "Computer Science" in repr_str


class TestCSStudentAttributes:
    """Test CSStudent attribute access"""

    def test_all_attributes_accessible(self):
        """Test that all attributes are accessible"""
        student = CSStudent(
            student_id="CS001",
            email_address="john.doe@university.edu",
            title="Mr",
            first_name="John",
            middle_name="Michael",
            last_name="Doe",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1="CS201",
            module2="CS202",
            module3="CS203",
            module4="CS204",
            registration_datetime="2023-09-01 10:00:00"
        )

        # Test all attributes
        assert student.student_id == "CS001"
        assert student.email_address == "john.doe@university.edu"
        assert student.title == "Mr"
        assert student.first_name == "John"
        assert student.middle_name == "Michael"
        assert student.last_name == "Doe"
        assert student.gender == "Male"
        assert student.dob == "2000-01-15"
        assert student.age == 24
        assert student.course == "Computer Science"
        assert student.compulsory_module_1 == "CS101"
        assert student.compulsory_module_2 == "CS102"
        assert student.module1 == "CS201"
        assert student.module2 == "CS202"
        assert student.module3 == "CS203"
        assert student.module4 == "CS204"
        assert student.registration_datetime == "2023-09-01 10:00:00"


class TestCSStudentEdgeCases:
    """Test edge cases and special scenarios"""

    def test_special_characters_in_name(self):
        """Test names with special characters"""
        student = CSStudent(
            student_id="CS001",
            email_address="maria.garcia@university.edu",
            title="Ms",
            first_name="María",
            middle_name="José",
            last_name="García-López",
            gender="Female",
            dob="2000-03-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert "María" in full_name
        assert "José" in full_name
        assert "García-López" in full_name

    def test_very_long_names(self):
        """Test very long names"""
        student = CSStudent(
            student_id="CS001",
            email_address="test@university.edu",
            title="Dr",
            first_name="Verylongfirstname",
            middle_name="Verylongmiddlename",
            last_name="Verylonglastname",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert len(full_name) > 30

    def test_numeric_student_id(self):
        """Test numeric student ID"""
        student = CSStudent(
            student_id="12345",
            email_address="test@university.edu",
            title="Mr",
            first_name="Test",
            middle_name="",
            last_name="Student",
            gender="Male",
            dob="2000-01-15",
            age=24,
            course="Computer Science",
            compulsory_module_1="CS101",
            compulsory_module_2="CS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.student_id == "12345"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
