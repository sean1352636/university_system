"""
Tests for university_system.modules.domain.academics.grade_misc.forecasting module.

This module tests forecasting and prediction functions including:
- Course performance forecasting
- Module difficulty forecasting
- Success rate forecasting
- Dashboard visualization and reporting
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest import mock

import numpy as np
import pytest

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.academics.grading.forecasting import (
    create_dashboard_visualizations,
    export_batch_predictions,
    extract_comprehensive_student_features,
    extract_student_features,
    forecast_course_success_rate,
    forecast_module_difficulty,
    forecast_module_difficulty_single,
    forecast_single_course,
    forecast_success_rates,
    generate_dashboard_alerts,
    generate_dashboard_recommendations,
    generate_dashboard_report,
)


@pytest.fixture(autouse=True)
def _init_i18n_for_tests():
    """Ensure i18n is loaded so get_text returns English strings, not keys."""
    try:
        from education_system.shared.i18n import init_i18n
        init_i18n("en")
    except Exception:
        pass


@pytest.fixture
def setup_forecast_data():
    """Set up test data for forecasting tests"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create test students
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, email, course)
            VALUES
            ('FCST001', 'Alice', 'Smith', 'alice@test.com', 'CS'),
            ('FCST002', 'Bob', 'Jones', 'bob@test.com', 'CS'),
            ('FCST003', 'Carol', 'White', 'carol@test.com', 'ENG')
        """)

        # Create modules
        cursor.execute("""
            INSERT INTO modules (module_code, module_name, credits)
            VALUES
            ('FCST101', 'Test Module 1', 10),
            ('FCST102', 'Test Module 2', 10)
        """)

        # Enroll students
        for student_id in ['FCST001', 'FCST002', 'FCST003']:
            cursor.execute("""
                INSERT INTO student_modules (student_id, module_code, enrollment_date)
                VALUES (?, 'FCST101', '2023-09-01')
            """, (student_id,))

        # Create module grades
        cursor.execute("""
            INSERT INTO module_grades (student_id, module_code, final_score, final_grade)
            VALUES
            ('FCST001', 'FCST101', 85.0, 'A'),
            ('FCST002', 'FCST101', 75.0, 'B'),
            ('FCST003', 'FCST101', 65.0, 'C')
        """)

        # Create assessments over time
        base_date = datetime.now() - timedelta(days=180)

        for i in range(8):  # Create 8 months of data
            month_date = (base_date + timedelta(days=30 * i)).strftime('%Y-%m-%d')

            cursor.execute("""
                INSERT INTO assessments (module_code, assessment_name, assessment_type, max_points, due_date)
                VALUES ('FCST101', ?, 'Quiz', 100, ?)
            """, (f'Quiz {i+1}', month_date))

            assessment_id = cursor.lastrowid

            # Create grades for this assessment
            for student_id, base_score in [('FCST001', 85), ('FCST002', 75), ('FCST003', 65)]:
                score = base_score + (i * 2)  # Trending up
                cursor.execute("""
                    INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, assessment_id, min(score, 100), 'A' if score >= 90 else 'B', month_date))

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM grades WHERE student_id LIKE 'FCST%'")
        cursor.execute("DELETE FROM assessments WHERE module_code LIKE 'FCST%'")
        cursor.execute("DELETE FROM module_grades WHERE student_id LIKE 'FCST%'")
        cursor.execute("DELETE FROM student_modules WHERE student_id LIKE 'FCST%'")
        cursor.execute("DELETE FROM modules WHERE module_code LIKE 'FCST%'")
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'FCST%'")


class TestExportFunctions:
    """Test export functions"""

    def test_export_batch_predictions(self, tmp_path, monkeypatch):
        """Test exporting batch predictions"""
        monkeypatch.chdir(tmp_path)

        predictions = [
            {
                'student_id': 'S001',
                'name': 'Test Student',
                'course': 'CS',
                'predicted_score': 85.5,
                'predicted_grade': 'A',
                'confidence': 'High'
            },
            {
                'student_id': 'S002',
                'name': 'Test Student 2',
                'course': 'ENG',
                'predicted_score': 72.0,
                'predicted_grade': 'B',
                'confidence': 'Medium'
            }
        ]

        export_batch_predictions(predictions, "next_assessment_predictions")

        # Check that file was created
        export_dir = tmp_path / "prediction_exports"
        assert export_dir.exists()
        files = list(export_dir.glob("*.csv"))
        assert len(files) > 0


class TestForecastSingleCourse:
    """Test single course forecasting"""

    def test_forecast_single_course_with_data(self, setup_forecast_data, capsys):
        """Test forecasting with sufficient data"""
        with get_connection() as conn:
            cursor = conn.cursor()
            forecast_single_course(cursor, 'CS')

            captured = capsys.readouterr()
            assert "Forecast" in captured.out or "forecast" in captured.out.lower()

    def test_forecast_single_course_insufficient_data(self, capsys):
        """Test forecasting with insufficient historical data"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create minimal data (less than 6 months)
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, course)
                VALUES ('FCST999', 'Test', 'User', 'test@test.com', 'TEST')
            """)

            try:
                forecast_single_course(cursor, 'TEST')

                captured = capsys.readouterr()
                assert "insufficient" in captured.out.lower() or "forecasting" in captured.out.lower()
            finally:
                cursor.execute("DELETE FROM students WHERE student_id = 'FCST999'")
                conn.rollback()


class TestForecastModuleDifficulty:
    """Test module difficulty forecasting"""

    def test_forecast_module_difficulty_with_data(self, setup_forecast_data, capsys):
        """Test module difficulty forecasting"""
        with get_connection() as conn:
            cursor = conn.cursor()
            forecast_module_difficulty(cursor)

            captured = capsys.readouterr()
            assert "difficulty" in captured.out.lower()

    def test_forecast_module_difficulty_no_data(self, capsys):
        """Test with no modules"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM grades")

            try:
                forecast_module_difficulty(cursor)

                captured = capsys.readouterr()
                assert "no_modules" in captured.out.lower() or "No modules" in captured.out or "sufficient" in captured.out.lower()
            finally:
                conn.rollback()

    def test_forecast_module_difficulty_single(self, setup_forecast_data):
        """Test forecasting difficulty for a single module"""
        with get_connection() as conn:
            cursor = conn.cursor()

            result = forecast_module_difficulty_single(cursor, 'FCST101', 'Test Module 1')

            if result:
                assert 'code' in result
                assert 'name' in result
                assert 'current_avg' in result
                assert 'trend' in result
                assert 'projected_difficulty' in result


class TestForecastSuccessRates:
    """Test success rate forecasting"""

    def test_forecast_success_rates_with_data(self, setup_forecast_data, capsys):
        """Test success rate forecasting"""
        with get_connection() as conn:
            cursor = conn.cursor()
            forecast_success_rates(cursor)

            captured = capsys.readouterr()
            assert "success_rate" in captured.out.lower() or "success rate" in captured.out.lower()

    def test_forecast_success_rates_insufficient_data(self, capsys):
        """Test with insufficient data"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM grades")

            try:
                forecast_success_rates(cursor)

                captured = capsys.readouterr()
                assert "insufficient" in captured.out.lower() or "forecasting" in captured.out.lower()
            finally:
                conn.rollback()

    def test_forecast_course_success_rate(self, setup_forecast_data):
        """Test forecasting success rate for specific course"""
        with get_connection() as conn:
            cursor = conn.cursor()

            result = forecast_course_success_rate(cursor, 'CS')

            if result:
                assert 'current' in result
                assert 'trend' in result
                assert 'projected' in result
                assert 0 <= result['current'] <= 100
                assert 0 <= result['projected'] <= 100


class TestFeatureExtraction:
    """Test feature extraction functions"""

    def test_extract_student_features(self, setup_forecast_data):
        """Test extracting features for a student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            features = extract_student_features(cursor, 'FCST001')

            assert features is not None
            assert 'avg_score' in features
            assert 'assessment_count' in features
            assert 'failed_count' in features
            assert 'submission_rate' in features

    def test_extract_student_features_no_data(self):
        """Test extracting features for student with no data"""
        with get_connection() as conn:
            cursor = conn.cursor()

            features = extract_student_features(cursor, 'NONEXISTENT')

            assert features is None

    def test_extract_comprehensive_student_features(self, setup_forecast_data):
        """Test extracting comprehensive features"""
        with get_connection() as conn:
            cursor = conn.cursor()

            features = extract_comprehensive_student_features(cursor, 'FCST001')

            assert features is not None
            assert 'avg_score' in features
            assert 'assessment_count' in features
            assert 'consistency_score' in features
            assert 'score_trend' in features
            assert 'failed_count' in features
            assert 'submission_rate' in features

    def test_extract_comprehensive_features_no_data(self):
        """Test extracting comprehensive features with no data"""
        with get_connection() as conn:
            cursor = conn.cursor()

            features = extract_comprehensive_student_features(cursor, 'NONEXISTENT')

            assert features is None


class TestDashboardVisualization:
    """Test dashboard visualization functions"""

    def test_create_dashboard_visualizations(self, setup_forecast_data, tmp_path, monkeypatch):
        """Test creating dashboard visualizations"""
        monkeypatch.chdir(tmp_path)

        from education_system.university_system.modules.domain.academics.grading.progress import collect_dashboard_data

        with get_connection() as conn:
            cursor = conn.cursor()
            dashboard_data = collect_dashboard_data(cursor)

        create_dashboard_visualizations(dashboard_data)

        # Check that visualization directory was created
        viz_dir = tmp_path / "dashboard_visualizations"
        assert viz_dir.exists()

    def test_generate_dashboard_report(self, setup_forecast_data, tmp_path, monkeypatch):
        """Test generating dashboard PDF report"""
        monkeypatch.chdir(tmp_path)

        # A previous test may have corrupted reportlab modules in sys.modules
        # (e.g. GUI tests that mock sys.modules wholesale replace reportlab
        # submodules with MagicMock).  The forecasting module imports
        # reportlab.lib.colors at module level, so we must purge the bad
        # entries, reimport reportlab cleanly, then reload forecasting so its
        # module-level `colors`, `TableStyle` etc. point to real objects.
        import sys, importlib
        import reportlab.lib.colors as _rl_check
        if not hasattr(_rl_check, '__file__'):
            # reportlab.lib.colors is a MagicMock — purge and reimport
            for k in [k for k in sys.modules if k.startswith('reportlab')]:
                del sys.modules[k]
            import reportlab.lib.colors  # noqa: F401, F811  # deliberate reimport after MagicMock purge
            # Reload the forecasting module so its module-level imports pick
            # up the real reportlab objects
            forecasting_key = 'education_system.university_system.modules.domain.academics.grading.forecasting'
            if forecasting_key in sys.modules:
                importlib.reload(sys.modules[forecasting_key])

        from education_system.university_system.modules.domain.academics.grading.progress import collect_dashboard_data

        # Re-import generate_dashboard_report after potential reload
        from education_system.university_system.modules.domain.academics.grading.forecasting import generate_dashboard_report as _gen_report

        with get_connection() as conn:
            cursor = conn.cursor()
            dashboard_data = collect_dashboard_data(cursor)

        _gen_report(dashboard_data)

        # Check that report directory was created
        reports_dir = tmp_path / "dashboard_reports"
        assert reports_dir.exists()

    def test_generate_dashboard_recommendations(self, setup_forecast_data):
        """Test generating recommendations"""
        from education_system.university_system.modules.domain.academics.grading.progress import collect_dashboard_data

        with get_connection() as conn:
            cursor = conn.cursor()
            dashboard_data = collect_dashboard_data(cursor)

        recommendations = generate_dashboard_recommendations(dashboard_data)

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_generate_dashboard_alerts(self, setup_forecast_data, capsys):
        """Test generating dashboard alerts"""
        from education_system.university_system.modules.domain.academics.grading.progress import collect_dashboard_data

        with get_connection() as conn:
            cursor = conn.cursor()
            dashboard_data = collect_dashboard_data(cursor)

        generate_dashboard_alerts(dashboard_data)

        captured = capsys.readouterr()
        # Should output some alerts or confirmation
        assert len(captured.out) > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_forecast_with_negative_trend(self, setup_forecast_data):
        """Test forecasting with declining performance"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create declining grades
            base_date = datetime.now() - timedelta(days=180)

            for i in range(8):
                month_date = (base_date + timedelta(days=30 * i)).strftime('%Y-%m-%d')

                cursor.execute("""
                    INSERT INTO assessments (module_code, assessment_name, assessment_type, max_points, due_date)
                    VALUES ('FCST101', ?, 'Test', 100, ?)
                """, (f'Test Decline {i+1}', month_date))

                assessment_id = cursor.lastrowid

                # Declining scores
                score = 90 - (i * 5)  # Trending down
                cursor.execute("""
                    INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                    VALUES ('FCST001', ?, ?, 'B', ?)
                """, (assessment_id, max(score, 0), month_date))

            try:
                forecast_single_course(cursor, 'CS')
            finally:
                conn.rollback()

    def test_forecast_with_all_same_scores(self):
        """Test forecasting with no variation in scores"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create student and module
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, course)
                VALUES ('FCST888', 'Test', 'User', 'test@test.com', 'FLAT')
            """)

            cursor.execute("""
                INSERT INTO modules (module_code, module_name, credits)
                VALUES ('FLAT101', 'Flat Module', 10)
            """)

            # Create assessments with identical scores
            base_date = datetime.now() - timedelta(days=180)

            for i in range(8):
                month_date = (base_date + timedelta(days=30 * i)).strftime('%Y-%m-%d')

                cursor.execute("""
                    INSERT INTO assessments (module_code, assessment_name, assessment_type, max_points, due_date)
                    VALUES ('FLAT101', ?, 'Quiz', 100, ?)
                """, (f'Quiz {i+1}', month_date))

                assessment_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                    VALUES ('FCST888', ?, 80.0, 'B', ?)
                """, (assessment_id, month_date))

            try:
                forecast_single_course(cursor, 'FLAT')
            finally:
                cursor.execute("DELETE FROM grades WHERE student_id = 'FCST888'")
                cursor.execute("DELETE FROM assessments WHERE module_code = 'FLAT101'")
                cursor.execute("DELETE FROM modules WHERE module_code = 'FLAT101'")
                cursor.execute("DELETE FROM students WHERE student_id = 'FCST888'")
                conn.rollback()

    def test_empty_dashboard_data(self):
        """Test dashboard functions with minimal data"""
        dashboard_data = {
            'overview': {
                'total_students': 0,
                'total_modules': 0,
                'total_assessments': 0,
                'total_grades': 0
            },
            'grade_distribution': {
                'distribution': {},
                'total_grades': 0,
                'passing_rate': 0
            },
            'course_performance': [],
            'risk_stats': {
                'at_risk_students': 0,
                'high_risk_students': 0,
                'at_risk_percentage': 0
            },
            'recent_trends': []
        }

        recommendations = generate_dashboard_recommendations(dashboard_data)
        assert isinstance(recommendations, list)

    def test_forecast_boundary_values(self):
        """Test forecasting with boundary score values"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create test data with extreme values
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, course)
                VALUES ('FCST777', 'Boundary', 'Test', 'bound@test.com', 'BOUND')
            """)

            cursor.execute("""
                INSERT INTO modules (module_code, module_name, credits)
                VALUES ('BOUND101', 'Boundary Module', 10)
            """)

            base_date = datetime.now() - timedelta(days=180)

            for i in range(8):
                month_date = (base_date + timedelta(days=30 * i)).strftime('%Y-%m-%d')

                cursor.execute("""
                    INSERT INTO assessments (module_code, assessment_name, assessment_type, max_points, due_date)
                    VALUES ('BOUND101', ?, 'Test', 100, ?)
                """, (f'Test {i+1}', month_date))

                assessment_id = cursor.lastrowid

                # Alternating between 0 and 100
                score = 100 if i % 2 == 0 else 0
                cursor.execute("""
                    INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                    VALUES ('FCST777', ?, ?, ?, ?)
                """, (assessment_id, score, 'A' if score == 100 else 'F', month_date))

            try:
                features = extract_comprehensive_student_features(cursor, 'FCST777')
                assert features is not None
            finally:
                cursor.execute("DELETE FROM grades WHERE student_id = 'FCST777'")
                cursor.execute("DELETE FROM assessments WHERE module_code = 'BOUND101'")
                cursor.execute("DELETE FROM modules WHERE module_code = 'BOUND101'")
                cursor.execute("DELETE FROM students WHERE student_id = 'FCST777'")
                conn.rollback()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
