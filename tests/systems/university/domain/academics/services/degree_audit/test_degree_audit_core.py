"""
Test suite for Degree Audit Core Service

Tests the degree audit core functionality including:
- Degree program management
- Degree progress tracking
- What-if scenario analysis
- Advising appointments
- Graduation audits
"""

import pytest
from datetime import datetime
from education_system.systems.university.domain.academics.services.degree_audit.db_schema import (
    initialize_degree_audit_database
)
from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import (
    DegreeProgramManager,
    DegreeProgressManager,
    WhatIfScenarioManager,
    AdvisingAppointmentManager,
    GraduationAuditManager
)
from education_system.systems.university.infrastructure.database.db import get_connection


class TestDegreeProgramManager:
    """Test DegreeProgramManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_degree_audit_database()

    def test_create_program(self):
        """Test creating a degree program"""
        self.setUp()

        program_id = DegreeProgramManager.create_program(
            program_code='CS-BS-2024',
            program_name='Computer Science BS',
            degree_type='Bachelor of Science',
            total_credits_required=120,
            department='Computer Science',
            min_gpa_required=2.0,
            max_years_allowed=4,
            description='Bachelor of Science in Computer Science'
        )

        assert program_id is not None
        assert isinstance(program_id, int)
        assert program_id > 0

    def test_create_program_duplicate_code(self):
        """Test creating program with duplicate code fails"""
        self.setUp()

        # Create first program
        DegreeProgramManager.create_program(
            program_code='DUP-TEST',
            program_name='Test Program',
            degree_type='Bachelor',
            total_credits_required=120
        )

        # Try to create duplicate
        with pytest.raises(Exception):
            DegreeProgramManager.create_program(
                program_code='DUP-TEST',
                program_name='Duplicate Program',
                degree_type='Bachelor',
                total_credits_required=120
            )

    def test_add_requirement(self):
        """Test adding a requirement to a program"""
        self.setUp()

        # Create program first
        program_id = DegreeProgramManager.create_program(
            program_code='REQ-TEST',
            program_name='Requirement Test',
            degree_type='Bachelor',
            total_credits_required=120
        )

        # Add requirement
        requirement_id = DegreeProgramManager.add_requirement(
            program_id=program_id,
            requirement_type='Core',
            requirement_name='Core Computer Science',
            credits_required=30,
            description='Core CS courses',
            min_grade='C',
            is_mandatory=True
        )

        assert requirement_id is not None
        assert isinstance(requirement_id, int)
        assert requirement_id > 0

    def test_add_required_course(self):
        """Test adding a required course to a requirement"""
        self.setUp()

        # Create program and requirement
        program_id = DegreeProgramManager.create_program(
            program_code='COURSE-TEST',
            program_name='Course Test',
            degree_type='Bachelor',
            total_credits_required=120
        )

        requirement_id = DegreeProgramManager.add_requirement(
            program_id=program_id,
            requirement_type='Core',
            requirement_name='Core Courses',
            credits_required=30
        )

        # Add required course
        req_course_id = DegreeProgramManager.add_required_course(
            requirement_id=requirement_id,
            module_code='CS101',
            is_alternative=False
        )

        assert req_course_id is not None
        assert isinstance(req_course_id, int)

    def test_add_prerequisite(self):
        """Test adding a course prerequisite"""
        self.setUp()

        prerequisite_id = DegreeProgramManager.add_prerequisite(
            module_code='CS201',
            prerequisite_module_code='CS101',
            min_grade='C',
            is_corequisite=False
        )

        assert prerequisite_id is not None
        assert isinstance(prerequisite_id, int)

    def test_get_program_requirements(self):
        """Test retrieving program requirements"""
        self.setUp()

        # Create program with requirements
        program_id = DegreeProgramManager.create_program(
            program_code='GET-REQ-TEST',
            program_name='Get Requirements Test',
            degree_type='Bachelor',
            total_credits_required=120
        )

        DegreeProgramManager.add_requirement(
            program_id=program_id,
            requirement_type='Core',
            requirement_name='Core Requirements',
            credits_required=30
        )

        DegreeProgramManager.add_requirement(
            program_id=program_id,
            requirement_type='Elective',
            requirement_name='Elective Requirements',
            credits_required=20
        )

        # Get requirements
        requirements = DegreeProgramManager.get_program_requirements(program_id)

        assert isinstance(requirements, list)
        assert len(requirements) == 2


class TestDegreeProgressManager:
    """Test DegreeProgressManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_degree_audit_database()

        # Create a test program
        self.program_id = DegreeProgramManager.create_program(
            program_code='PROG-TEST',
            program_name='Progress Test Program',
            degree_type='Bachelor',
            total_credits_required=120
        )

    def test_initialize_student_progress(self):
        """Test initializing student progress tracking"""
        self.setUp()

        progress_id = DegreeProgressManager.initialize_student_progress(
            student_id='STU001',
            program_id=self.program_id,
            enrollment_year=2024
        )

        assert progress_id is not None
        assert isinstance(progress_id, int)

    def test_initialize_student_progress_duplicate(self):
        """Test that duplicate progress initialization fails"""
        self.setUp()

        # First initialization
        DegreeProgressManager.initialize_student_progress(
            student_id='STU002',
            program_id=self.program_id,
            enrollment_year=2024
        )

        # Duplicate should fail
        with pytest.raises(Exception):
            DegreeProgressManager.initialize_student_progress(
                student_id='STU002',
                program_id=self.program_id,
                enrollment_year=2024
            )

    def test_get_student_progress(self):
        """Test retrieving student progress"""
        self.setUp()

        # Initialize progress
        DegreeProgressManager.initialize_student_progress(
            student_id='STU003',
            program_id=self.program_id,
            enrollment_year=2024
        )

        # Get progress
        progress = DegreeProgressManager.get_student_progress('STU003')

        assert progress is not None
        assert isinstance(progress, dict)
        assert progress['student_id'] == 'STU003'

    def test_get_student_progress_nonexistent(self):
        """Test getting progress for non-existent student"""
        self.setUp()

        progress = DegreeProgressManager.get_student_progress('NONEXISTENT')

        assert progress is None

    def test_check_prerequisite_completion(self):
        """Test checking prerequisite completion"""
        self.setUp()

        # Add prerequisite
        DegreeProgramManager.add_prerequisite(
            module_code='CS201',
            prerequisite_module_code='CS101',
            min_grade='C'
        )

        # Check prerequisites for student who hasn't completed them
        completed, missing = DegreeProgressManager.check_prerequisite_completion(
            student_id='STU004',
            module_code='CS201'
        )

        assert isinstance(completed, bool)
        assert isinstance(missing, list)


class TestWhatIfScenarioManager:
    """Test WhatIfScenarioManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_degree_audit_database()

        # Create test programs
        self.program_id = DegreeProgramManager.create_program(
            program_code='WHATIF-TEST',
            program_name='What-If Test Program',
            degree_type='Bachelor',
            total_credits_required=120
        )

    def test_create_scenario(self):
        """Test creating a what-if scenario"""
        self.setUp()

        scenario_id = WhatIfScenarioManager.create_scenario(
            student_id='STU005',
            scenario_name='Switch to Computer Science',
            target_program_id=self.program_id,
            notes='Exploring CS program'
        )

        assert scenario_id is not None
        assert isinstance(scenario_id, int)

    def test_analyze_scenario(self):
        """Test analyzing a what-if scenario"""
        self.setUp()

        # Analyze scenario
        analysis = WhatIfScenarioManager.analyze_scenario(
            student_id='STU006',
            target_program_id=self.program_id
        )

        assert isinstance(analysis, dict)
        assert 'target_program_id' in analysis
        assert 'total_requirements' in analysis
        assert 'requirements_met' in analysis
        assert 'completion_percentage' in analysis


class TestAdvisingAppointmentManager:
    """Test AdvisingAppointmentManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_degree_audit_database()

    def test_schedule_appointment(self):
        """Test scheduling an advising appointment"""
        self.setUp()

        appointment_id = AdvisingAppointmentManager.schedule_appointment(
            student_id='STU007',
            advisor_id='ADV001',
            appointment_date='2024-12-15',
            appointment_time='14:00',
            appointment_type='Academic Planning',
            duration_minutes=30,
            topic='Degree requirements review',
            notes='First meeting'
        )

        assert appointment_id is not None
        assert isinstance(appointment_id, int)

    def test_get_student_appointments(self):
        """Test retrieving student appointments"""
        self.setUp()

        # Schedule appointment
        AdvisingAppointmentManager.schedule_appointment(
            student_id='STU008',
            advisor_id='ADV001',
            appointment_date='2024-12-15',
            appointment_time='10:00',
            appointment_type='Academic Planning'
        )

        # Get appointments
        appointments = AdvisingAppointmentManager.get_student_appointments('STU008')

        assert isinstance(appointments, list)
        assert len(appointments) > 0

    def test_get_student_appointments_empty(self):
        """Test getting appointments for student with none"""
        self.setUp()

        appointments = AdvisingAppointmentManager.get_student_appointments('NOAPPOINTMENTS')

        assert isinstance(appointments, list)
        assert len(appointments) == 0


class TestGraduationAuditManager:
    """Test GraduationAuditManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_degree_audit_database()

        # Create test program
        self.program_id = DegreeProgramManager.create_program(
            program_code='GRAD-AUDIT',
            program_name='Graduation Audit Test',
            degree_type='Bachelor',
            total_credits_required=120,
            min_gpa_required=2.0
        )

        # Initialize student progress
        DegreeProgressManager.initialize_student_progress(
            student_id='GRAD-STU001',
            program_id=self.program_id,
            enrollment_year=2020
        )

    def test_run_graduation_audit(self):
        """Test running a graduation audit"""
        self.setUp()

        audit_result = GraduationAuditManager.run_graduation_audit(
            student_id='GRAD-STU001',
            program_id=self.program_id
        )

        assert isinstance(audit_result, dict)
        assert 'all_requirements_met' in audit_result
        assert 'gpa_requirement_met' in audit_result
        assert 'credit_requirement_met' in audit_result
        assert 'can_graduate' in audit_result

    def test_approve_graduation(self):
        """Test approving a student for graduation"""
        self.setUp()

        # Run audit first
        GraduationAuditManager.run_graduation_audit(
            student_id='GRAD-STU002',
            program_id=self.program_id
        )

        # Approve graduation
        result = GraduationAuditManager.approve_graduation(
            student_id='GRAD-STU002',
            program_id=self.program_id,
            graduation_date='2025-05-15'
        )

        assert result is True


class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_degree_audit_workflow(self):
        """Test complete degree audit workflow from setup to graduation"""
        initialize_degree_audit_database()

        # 1. Create degree program
        program_id = DegreeProgramManager.create_program(
            program_code='CS-INT-TEST',
            program_name='Computer Science Integration Test',
            degree_type='Bachelor',
            total_credits_required=120,
            min_gpa_required=2.5
        )

        # 2. Add requirements
        req_id = DegreeProgramManager.add_requirement(
            program_id=program_id,
            requirement_type='Core',
            requirement_name='Core CS Courses',
            credits_required=60,
            is_mandatory=True
        )

        # 3. Add required course
        DegreeProgramManager.add_required_course(
            requirement_id=req_id,
            module_code='CS101'
        )

        # 4. Initialize student progress
        student_id = 'INT-STU001'
        DegreeProgressManager.initialize_student_progress(
            student_id=student_id,
            program_id=program_id,
            enrollment_year=2024
        )

        # 5. Schedule advising appointment
        AdvisingAppointmentManager.schedule_appointment(
            student_id=student_id,
            advisor_id='ADV-INT',
            appointment_date='2024-12-20',
            appointment_time='10:00',
            appointment_type='Degree Planning'
        )

        # 6. Create what-if scenario
        WhatIfScenarioManager.create_scenario(
            student_id=student_id,
            scenario_name='Test Scenario',
            target_program_id=program_id
        )

        # 7. Run graduation audit
        audit_result = GraduationAuditManager.run_graduation_audit(
            student_id=student_id,
            program_id=program_id
        )

        # Verify workflow completed
        assert program_id is not None
        assert req_id is not None
        assert audit_result is not None
        assert 'can_graduate' in audit_result

    def test_prerequisite_workflow(self):
        """Test prerequisite checking workflow"""
        initialize_degree_audit_database()

        # Add prerequisites
        DegreeProgramManager.add_prerequisite(
            module_code='CS301',
            prerequisite_module_code='CS201',
            min_grade='B'
        )

        DegreeProgramManager.add_prerequisite(
            module_code='CS201',
            prerequisite_module_code='CS101',
            min_grade='C'
        )

        # Check prerequisites
        completed, missing = DegreeProgressManager.check_prerequisite_completion(
            student_id='PREREQ-TEST',
            module_code='CS301'
        )

        # Should have missing prerequisites
        assert isinstance(completed, bool)
        assert isinstance(missing, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
