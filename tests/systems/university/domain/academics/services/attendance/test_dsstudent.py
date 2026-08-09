"""
Test suite for DSStudent Class

Tests the Data Science student model class including:
- Initialization and attributes
- Full name formatting
- Module enrollment tracking
- GPA calculation
- String representations
"""

import pytest
from datetime import datetime
from education_system.systems.university.domain.academics.services.attendance.DSstudent import DSStudent


class TestDSStudentInitialization:
    """Test DSStudent class initialization"""

    def test_basic_initialization(self):
        """Test basic student initialization with all parameters"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2="DS202",
            module3="DS203",
            module4="DS204",
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.student_id == "DS001"
        assert student.email_address == "alice.johnson@university.edu"
        assert student.first_name == "Alice"
        assert student.last_name == "Johnson"
        assert student.course == "Data Science"

    def test_initialization_without_middle_name(self):
        """Test student initialization without middle name"""
        student = DSStudent(
            student_id="DS002",
            email_address="bob.wilson@university.edu",
            title="Mr",
            first_name="Bob",
            middle_name=None,
            last_name="Wilson",
            gender="Male",
            dob="2000-07-10",
            age=24,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.middle_name is None
        assert student.student_id == "DS002"

    def test_initialization_with_optional_modules_none(self):
        """Test student with no optional modules"""
        student = DSStudent(
            student_id="DS003",
            email_address="charlie.brown@university.edu",
            title="Mr",
            first_name="Charlie",
            middle_name="",
            last_name="Brown",
            gender="Male",
            dob="1999-11-05",
            age=25,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.module1 is None
        assert student.module2 is None


class TestDSStudentMethods:
    """Test DSStudent class methods"""

    def test_get_full_name_with_middle_name(self):
        """Test full name generation with middle name"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert full_name == "Ms Alice Marie Johnson"

    def test_get_full_name_without_middle_name(self):
        """Test full name generation without middle name"""
        student = DSStudent(
            student_id="DS002",
            email_address="bob.wilson@university.edu",
            title="Mr",
            first_name="Bob",
            middle_name=None,
            last_name="Wilson",
            gender="Male",
            dob="2000-07-10",
            age=24,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert full_name == "Mr Bob Wilson"

    def test_get_full_name_with_empty_middle_name(self):
        """Test full name generation with empty string middle name"""
        student = DSStudent(
            student_id="DS003",
            email_address="charlie.brown@university.edu",
            title="Dr",
            first_name="Charlie",
            middle_name="",
            last_name="Brown",
            gender="Male",
            dob="1999-11-05",
            age=25,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert full_name == "Dr Charlie Brown"

    def test_get_enrolled_modules_all_modules(self):
        """Test getting all enrolled modules when all are present"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2="DS202",
            module3="DS203",
            module4="DS204",
            registration_datetime="2023-09-01 10:00:00"
        )

        modules = student.get_enrolled_modules()
        assert len(modules) == 6
        assert "DS101" in modules
        assert "DS102" in modules
        assert "DS201" in modules
        assert "DS202" in modules
        assert "DS203" in modules
        assert "DS204" in modules

    def test_get_enrolled_modules_compulsory_only(self):
        """Test getting modules when only compulsory modules are present"""
        student = DSStudent(
            student_id="DS002",
            email_address="bob.wilson@university.edu",
            title="Mr",
            first_name="Bob",
            middle_name=None,
            last_name="Wilson",
            gender="Male",
            dob="2000-07-10",
            age=24,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        modules = student.get_enrolled_modules()
        assert len(modules) == 2
        assert "DS101" in modules
        assert "DS102" in modules

    def test_get_enrolled_modules_partial_optional(self):
        """Test getting modules with some optional modules"""
        student = DSStudent(
            student_id="DS003",
            email_address="charlie.brown@university.edu",
            title="Mr",
            first_name="Charlie",
            middle_name="",
            last_name="Brown",
            gender="Male",
            dob="1999-11-05",
            age=25,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2="DS202",
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        modules = student.get_enrolled_modules()
        assert len(modules) == 4
        assert "DS101" in modules
        assert "DS102" in modules
        assert "DS201" in modules
        assert "DS202" in modules

    def test_calculate_gpa_placeholder(self):
        """Test GPA calculation (placeholder implementation)"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        gpa = student.calculate_gpa()
        # Placeholder returns 0.0
        assert gpa == 0.0
        assert isinstance(gpa, float)


class TestDSStudentStringRepresentation:
    """Test DSStudent string representations"""

    def test_str_representation(self):
        """Test __str__ method"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        str_repr = str(student)
        assert "DS Student" in str_repr
        assert "Alice" in str_repr
        assert "Johnson" in str_repr
        assert "DS001" in str_repr

    def test_repr_representation(self):
        """Test __repr__ method"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        repr_str = repr(student)
        assert "DSStudent" in repr_str
        assert "DS001" in repr_str
        assert "Data Science" in repr_str


class TestDSStudentAttributes:
    """Test DSStudent attribute access"""

    def test_all_attributes_accessible(self):
        """Test that all attributes are accessible"""
        student = DSStudent(
            student_id="DS001",
            email_address="alice.johnson@university.edu",
            title="Ms",
            first_name="Alice",
            middle_name="Marie",
            last_name="Johnson",
            gender="Female",
            dob="2001-03-20",
            age=23,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1="DS201",
            module2="DS202",
            module3="DS203",
            module4="DS204",
            registration_datetime="2023-09-01 10:00:00"
        )

        # Test all attributes
        assert student.student_id == "DS001"
        assert student.email_address == "alice.johnson@university.edu"
        assert student.title == "Ms"
        assert student.first_name == "Alice"
        assert student.middle_name == "Marie"
        assert student.last_name == "Johnson"
        assert student.gender == "Female"
        assert student.dob == "2001-03-20"
        assert student.age == 23
        assert student.course == "Data Science"
        assert student.compulsory_module_1 == "DS101"
        assert student.compulsory_module_2 == "DS102"
        assert student.module1 == "DS201"
        assert student.module2 == "DS202"
        assert student.module3 == "DS203"
        assert student.module4 == "DS204"
        assert student.registration_datetime == "2023-09-01 10:00:00"


class TestDSStudentEdgeCases:
    """Test edge cases and special scenarios"""

    def test_special_characters_in_name(self):
        """Test names with special characters"""
        student = DSStudent(
            student_id="DS001",
            email_address="francois@university.edu",
            title="Mr",
            first_name="François",
            middle_name="André",
            last_name="Dupont-Martin",
            gender="Male",
            dob="2000-04-15",
            age=24,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        full_name = student.get_full_name()
        assert "François" in full_name
        assert "André" in full_name
        assert "Dupont-Martin" in full_name

    def test_very_long_names(self):
        """Test very long names"""
        student = DSStudent(
            student_id="DS001",
            email_address="test@university.edu",
            title="Prof",
            first_name="Superlongfirstname",
            middle_name="Superlongmiddlename",
            last_name="Superlonglastname",
            gender="Female",
            dob="2000-01-15",
            age=24,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
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
        student = DSStudent(
            student_id="67890",
            email_address="test@university.edu",
            title="Ms",
            first_name="Test",
            middle_name="",
            last_name="Student",
            gender="Female",
            dob="2000-01-15",
            age=24,
            course="Data Science",
            compulsory_module_1="DS101",
            compulsory_module_2="DS102",
            module1=None,
            module2=None,
            module3=None,
            module4=None,
            registration_datetime="2023-09-01 10:00:00"
        )

        assert student.student_id == "67890"

    def test_different_title_formats(self):
        """Test different title formats"""
        titles = ["Mr", "Ms", "Mrs", "Dr", "Prof", "Sir", "Dame"]

        for title in titles:
            student = DSStudent(
                student_id=f"DS{title}",
                email_address=f"{title.lower()}@university.edu",
                title=title,
                first_name="Test",
                middle_name="Middle",
                last_name="Student",
                gender="Other",
                dob="2000-01-15",
                age=24,
                course="Data Science",
                compulsory_module_1="DS101",
                compulsory_module_2="DS102",
                module1=None,
                module2=None,
                module3=None,
                module4=None,
                registration_datetime="2023-09-01 10:00:00"
            )

            full_name = student.get_full_name()
            assert title in full_name


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
