"""
Test suite for Course Evaluation Core Service

Tests the course evaluation system including:
- Evaluation template management
- Course evaluation creation
- Response collection
- Results analytics
- Instructor performance tracking
"""

import pytest
from education_system.post_18.university_system.modules.domain.academics.services.evaluation.db_schema import (
    initialize_evaluation_database
)
from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import (
    EvaluationTemplateManager,
    CourseEvaluationManager,
    ResponseManager,
    ResultsAnalyticsManager
)
from education_system.post_18.university_system.infrastructure.database.db import get_connection


class TestEvaluationTemplateManager:
    """Test EvaluationTemplateManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_evaluation_database()

    def test_create_template(self):
        """Test creating an evaluation template"""
        self.setUp()

        template_id = EvaluationTemplateManager.create_template(
            template_name='Standard Course Evaluation',
            template_type='Course',
            description='Standard evaluation for all courses',
            created_by='admin'
        )

        assert template_id is not None
        assert isinstance(template_id, int)
        assert template_id > 0

    def test_create_template_minimal(self):
        """Test creating template with minimal parameters"""
        self.setUp()

        template_id = EvaluationTemplateManager.create_template(
            template_name='Minimal Template',
            template_type='Course'
        )

        assert template_id is not None

    def test_add_question(self):
        """Test adding a question to a template"""
        self.setUp()

        # Create template first
        template_id = EvaluationTemplateManager.create_template(
            template_name='Test Template',
            template_type='Course'
        )

        # Add question
        question_id = EvaluationTemplateManager.add_question(
            template_id=template_id,
            question_text='How would you rate the course content?',
            question_type='scale',
            question_category='Content',
            scale_min=1,
            scale_max=5,
            display_order=1
        )

        assert question_id is not None
        assert isinstance(question_id, int)

    def test_add_multiple_questions(self):
        """Test adding multiple questions to a template"""
        self.setUp()

        template_id = EvaluationTemplateManager.create_template(
            template_name='Multi-Question Template',
            template_type='Course'
        )

        questions = [
            ('How would you rate the course content?', 'Content'),
            ('How effective was the instructor?', 'Instructor'),
            ('How useful were the assignments?', 'Assignments'),
        ]

        question_ids = []
        for i, (text, category) in enumerate(questions):
            qid = EvaluationTemplateManager.add_question(
                template_id=template_id,
                question_text=text,
                question_type='scale',
                question_category=category,
                display_order=i
            )
            question_ids.append(qid)

        assert len(question_ids) == 3
        assert all(qid > 0 for qid in question_ids)


class TestCourseEvaluationManager:
    """Test CourseEvaluationManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_evaluation_database()

        # Create a template for testing
        self.template_id = EvaluationTemplateManager.create_template(
            template_name='Test Evaluation Template',
            template_type='Course'
        )

    def test_create_evaluation(self):
        """Test creating a course evaluation"""
        self.setUp()

        evaluation_id = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Fall',
            instructor_id='INST001',
            template_id=self.template_id,
            start_date='2024-11-01',
            end_date='2024-11-30'
        )

        assert evaluation_id is not None
        assert isinstance(evaluation_id, int)

    def test_create_evaluation_different_semesters(self):
        """Test creating evaluations for different semesters"""
        self.setUp()

        fall_id = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Fall',
            instructor_id='INST001',
            template_id=self.template_id,
            start_date='2024-09-01',
            end_date='2024-09-30'
        )

        spring_id = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Spring',
            instructor_id='INST001',
            template_id=self.template_id,
            start_date='2025-01-01',
            end_date='2025-01-31'
        )

        assert fall_id != spring_id
        assert fall_id > 0
        assert spring_id > 0


class TestResponseManager:
    """Test ResponseManager functionality"""

    def setUp(self):
        """Set up test environment"""
        initialize_evaluation_database()

        # Create template
        self.template_id = EvaluationTemplateManager.create_template(
            template_name='Response Test Template',
            template_type='Course'
        )

        # Add a question
        self.question_id = EvaluationTemplateManager.add_question(
            template_id=self.template_id,
            question_text='Test Question',
            question_type='scale',
            question_category='Test'
        )

        # Create evaluation
        self.evaluation_id = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Fall',
            instructor_id='INST001',
            template_id=self.template_id,
            start_date='2024-11-01',
            end_date='2024-11-30'
        )

    def test_start_response(self):
        """Test starting an evaluation response"""
        self.setUp()

        response_id = ResponseManager.start_response(
            evaluation_id=self.evaluation_id,
            student_id='STU001'
        )

        assert response_id is not None
        assert isinstance(response_id, int)

    def test_start_anonymous_response(self):
        """Test starting an anonymous response"""
        self.setUp()

        response_id = ResponseManager.start_response(
            evaluation_id=self.evaluation_id,
            student_id=None
        )

        assert response_id is not None

    def test_record_answer(self):
        """Test recording an answer"""
        self.setUp()

        response_id = ResponseManager.start_response(
            evaluation_id=self.evaluation_id,
            student_id='STU002'
        )

        answer_id = ResponseManager.record_answer(
            response_id=response_id,
            question_id=self.question_id,
            answer_value='5',
            numeric_value=5.0
        )

        assert answer_id is not None
        assert isinstance(answer_id, int)

    def test_complete_response(self):
        """Test completing an evaluation response"""
        self.setUp()

        response_id = ResponseManager.start_response(
            evaluation_id=self.evaluation_id,
            student_id='STU003'
        )

        ResponseManager.record_answer(
            response_id=response_id,
            question_id=self.question_id,
            answer_value='4',
            numeric_value=4.0
        )

        result = ResponseManager.complete_response(
            response_id=response_id,
            time_taken_minutes=10
        )

        assert result is True

    def test_complete_response_updates_count(self):
        """Test that completing response updates evaluation count"""
        self.setUp()

        # Get initial count
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT response_count FROM course_evaluations
            WHERE evaluation_id = ?
        """, (self.evaluation_id,))
        initial_count = cursor.fetchone()[0]
        conn.close()

        # Complete a response
        response_id = ResponseManager.start_response(
            evaluation_id=self.evaluation_id,
            student_id='STU004'
        )

        ResponseManager.complete_response(
            response_id=response_id,
            time_taken_minutes=5
        )

        # Check updated count
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT response_count FROM course_evaluations
            WHERE evaluation_id = ?
        """, (self.evaluation_id,))
        new_count = cursor.fetchone()[0]
        conn.close()

        assert new_count == initial_count + 1


class TestResultsAnalyticsManager:
    """Test ResultsAnalyticsManager functionality"""

    def setUp(self):
        """Set up test environment with sample data"""
        initialize_evaluation_database()

        # Create template with questions
        self.template_id = EvaluationTemplateManager.create_template(
            template_name='Analytics Test Template',
            template_type='Course'
        )

        self.question_id = EvaluationTemplateManager.add_question(
            template_id=self.template_id,
            question_text='Rate the course',
            question_type='scale',
            question_category='Overall'
        )

        # Create evaluation
        self.evaluation_id = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Fall',
            instructor_id='INST001',
            template_id=self.template_id,
            start_date='2024-11-01',
            end_date='2024-11-30'
        )

        # Add sample responses
        for i in range(5):
            response_id = ResponseManager.start_response(
                evaluation_id=self.evaluation_id,
                student_id=f'STU{i:03d}'
            )

            ResponseManager.record_answer(
                response_id=response_id,
                question_id=self.question_id,
                answer_value=str(4),
                numeric_value=4.0
            )

            ResponseManager.complete_response(
                response_id=response_id,
                time_taken_minutes=10
            )

    def test_calculate_results(self):
        """Test calculating evaluation results"""
        self.setUp()

        results = ResultsAnalyticsManager.calculate_results(
            evaluation_id=self.evaluation_id
        )

        assert isinstance(results, list)
        assert len(results) > 0

    def test_calculate_results_accuracy(self):
        """Test that calculated results are accurate"""
        self.setUp()

        results = ResultsAnalyticsManager.calculate_results(
            evaluation_id=self.evaluation_id
        )

        # All responses were 4.0, so average should be 4.0
        for result in results:
            if result['question_id'] == self.question_id:
                assert result['average_score'] == 4.0
                assert result['response_count'] == 5


class TestDatabaseSchema:
    """Test database schema for evaluation system"""

    def test_all_tables_created(self):
        """Test that all evaluation tables are created"""
        initialize_evaluation_database()

        conn = get_connection()
        cursor = conn.cursor()

        required_tables = [
            'evaluation_templates',
            'evaluation_questions',
            'course_evaluations',
            'evaluation_responses',
            'evaluation_answers',
            'evaluation_results'
        ]

        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        for table in required_tables:
            assert table in existing_tables, f"Table {table} not created"

    def test_indexes_created(self):
        """Test that indexes are created"""
        initialize_evaluation_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='index'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_indexes = [
            'idx_eval_module',
            'idx_eval_instructor',
            'idx_response_evaluation'
        ]

        for idx in expected_indexes:
            assert idx in indexes, f"Index {idx} not created"


class TestIntegration:
    """Integration tests for complete evaluation workflow"""

    def test_complete_evaluation_workflow(self):
        """Test complete workflow from template creation to results"""
        initialize_evaluation_database()

        # 1. Create template
        template_id = EvaluationTemplateManager.create_template(
            template_name='Complete Workflow Template',
            template_type='Course',
            created_by='admin'
        )

        # 2. Add questions
        q1_id = EvaluationTemplateManager.add_question(
            template_id=template_id,
            question_text='Course content quality?',
            question_type='scale',
            question_category='Content',
            display_order=1
        )

        q2_id = EvaluationTemplateManager.add_question(
            template_id=template_id,
            question_text='Instructor effectiveness?',
            question_type='scale',
            question_category='Instructor',
            display_order=2
        )

        # 3. Create evaluation
        evaluation_id = CourseEvaluationManager.create_evaluation(
            module_code='CS201',
            academic_year='2024-2025',
            semester='Fall',
            instructor_id='INST002',
            template_id=template_id,
            start_date='2024-11-01',
            end_date='2024-11-30'
        )

        # 4. Submit responses
        for i in range(10):
            response_id = ResponseManager.start_response(
                evaluation_id=evaluation_id,
                student_id=f'STUDENT{i:03d}'
            )

            # Answer both questions
            ResponseManager.record_answer(
                response_id=response_id,
                question_id=q1_id,
                answer_value='4',
                numeric_value=4.0
            )

            ResponseManager.record_answer(
                response_id=response_id,
                question_id=q2_id,
                answer_value='5',
                numeric_value=5.0
            )

            ResponseManager.complete_response(
                response_id=response_id,
                time_taken_minutes=15
            )

        # 5. Calculate results
        results = ResultsAnalyticsManager.calculate_results(
            evaluation_id=evaluation_id
        )

        # Verify complete workflow
        assert template_id is not None
        assert evaluation_id is not None
        assert len(results) == 2
        assert all(r['response_count'] == 10 for r in results)

    def test_multiple_evaluations_same_course(self):
        """Test creating multiple evaluations for the same course"""
        initialize_evaluation_database()

        template_id = EvaluationTemplateManager.create_template(
            template_name='Multi-Eval Template',
            template_type='Course'
        )

        # Create evaluations for different semesters
        fall_eval = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Fall',
            instructor_id='INST001',
            template_id=template_id,
            start_date='2024-09-01',
            end_date='2024-09-30'
        )

        spring_eval = CourseEvaluationManager.create_evaluation(
            module_code='CS101',
            academic_year='2024-2025',
            semester='Spring',
            instructor_id='INST001',
            template_id=template_id,
            start_date='2025-01-01',
            end_date='2025-01-31'
        )

        assert fall_eval != spring_eval
        assert fall_eval > 0
        assert spring_eval > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
