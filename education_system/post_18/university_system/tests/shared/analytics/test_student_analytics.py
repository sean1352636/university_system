"""
Tests for Student Analytics Module

Tests all functionality in university_system/modules/shared/services/analytics/student_analytics/
"""

import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

from education_system.post_18.university_system.modules.shared.services.analytics.student_analytics import (
    StudentAnalytics,
    configure_matplotlib,
    CONFIG
)


@pytest.fixture
def analytics():
    """Create StudentAnalytics instance for testing"""
    with patch('education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.base.get_connection'):
        return StudentAnalytics(gui_mode=True)


@pytest.fixture
def sample_students_df():
    """Create sample students DataFrame"""
    return pd.DataFrame({
        'student_id': ['S001', 'S002', 'S003', 'S004', 'S005'],
        'first_name': ['John', 'Jane', 'Bob', 'Alice', 'Charlie'],
        'last_name': ['Doe', 'Smith', 'Johnson', 'Williams', 'Brown'],
        'age': [20, 22, 21, 23, 20],
        'gender': ['Male', 'Female', 'Male', 'Female', 'Male'],
        'course': ['CS', 'ENG', 'CS', 'MATH', 'ENG'],
        'email_address': ['john@test.com', 'jane@test.com', 'bob@test.com', 'alice@test.com', 'charlie@test.com'],
        'registration_datetime': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
    })


@pytest.fixture
def sample_modules_df():
    """Create sample modules DataFrame"""
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'student_id': ['S001', 'S001', 'S002', 'S003', 'S004'],
        'module_code': ['CS101', 'CS102', 'ENG101', 'CS101', 'MATH101'],
        'module_name': ['Intro CS', 'Data Structures', 'English Lit', 'Intro CS', 'Calculus'],
        'grade': ['A', 'B', 'B', 'C', 'A'],
        'status': ['Completed', 'Completed', 'In Progress', 'Completed', 'Completed'],
        'course': ['CS', 'CS', 'ENG', 'CS', 'MATH'],
        'age': [20, 20, 22, 21, 23],
        'gender': ['Male', 'Male', 'Female', 'Male', 'Female']
    })


class TestConfigureMatplotlib:
    """Test matplotlib configuration"""

    def test_configure_matplotlib(self):
        """Test matplotlib backend configuration"""
        result = configure_matplotlib()
        assert isinstance(result, bool)


class TestStudentAnalyticsInit:
    """Test StudentAnalytics initialization"""

    def test_init_default(self):
        """Test default initialization"""
        with patch('education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.base.get_connection'):
            analytics = StudentAnalytics()

            assert hasattr(analytics, 'db_path')
            assert hasattr(analytics, 'plots_dir')
            assert hasattr(analytics, 'reports_dir')
            assert analytics.gui_mode is False

    def test_init_gui_mode(self):
        """Test initialization with GUI mode"""
        with patch('education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.base.get_connection'):
            analytics = StudentAnalytics(gui_mode=True)
            assert analytics.gui_mode is True

    def test_create_directories(self):
        """Test directory creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.base.get_connection'):
                analytics = StudentAnalytics()
                analytics.plots_dir = os.path.join(tmpdir, 'plots')
                analytics.reports_dir = os.path.join(tmpdir, 'reports')

                analytics.create_directories()

                assert os.path.exists(analytics.plots_dir)
                assert os.path.exists(analytics.reports_dir)


class TestDataRetrieval:
    """Test data retrieval methods"""

    def test_get_all_students_no_filters(self, analytics, sample_students_df):
        """Test getting all students without filters"""
        with patch('pandas.read_sql_query', return_value=sample_students_df):
            with patch.object(analytics, 'get_connection'):
                students = analytics.get_all_students()

                assert not students.empty
                assert len(students) >= len(sample_students_df)

    def test_get_all_students_with_course_filter(self, analytics, sample_students_df):
        """Test getting students with course filter"""
        with patch('pandas.read_sql_query', return_value=sample_students_df[sample_students_df['course'] == 'CS']):
            with patch.object(analytics, 'get_connection'):
                students = analytics.get_all_students(filters={'course': 'CS'})

                assert not students.empty

    def test_get_all_students_with_age_range(self, analytics, sample_students_df):
        """Test getting students with age range filter"""
        with patch('pandas.read_sql_query', return_value=sample_students_df):
            with patch.object(analytics, 'get_connection'):
                students = analytics.get_all_students(filters={'age_range': [20, 22]})

    def test_get_all_students_empty(self, analytics):
        """Test getting students when database is empty"""
        with patch('pandas.read_sql_query', return_value=pd.DataFrame()):
            with patch.object(analytics, 'get_connection'):
                students = analytics.get_all_students()
                assert students.empty

    def test_get_all_modules_no_filters(self, analytics, sample_modules_df):
        """Test getting all modules without filters"""
        with patch('pandas.read_sql_query', return_value=sample_modules_df):
            with patch.object(analytics, 'get_connection'):
                modules = analytics.get_all_modules()

                assert not modules.empty

    def test_get_all_modules_with_filters(self, analytics, sample_modules_df):
        """Test getting modules with filters"""
        with patch('pandas.read_sql_query', return_value=sample_modules_df[sample_modules_df['module_code'] == 'CS101']):
            with patch.object(analytics, 'get_connection'):
                modules = analytics.get_all_modules(filters={'module_code': 'CS101'})


class TestDataSimulation:
    """Test data simulation methods"""

    def test_simulate_additional_data(self, analytics, sample_students_df):
        """Test simulating additional student data"""
        enriched_df = analytics.simulate_additional_data(sample_students_df.copy())

        assert 'overall_grade' in enriched_df.columns
        assert 'gpa' in enriched_df.columns
        assert 'completion_status' in enriched_df.columns
        assert 'engagement_score' in enriched_df.columns
        assert 'location' in enriched_df.columns
        assert 'previous_education' in enriched_df.columns

        assert len(enriched_df) == len(sample_students_df)

    def test_simulate_module_data(self, analytics, sample_modules_df):
        """Test simulating additional module data"""
        enriched_df = analytics.simulate_module_data(sample_modules_df.copy())

        # Check for expected columns
        assert 'module_completion' in enriched_df.columns
        assert 'module_type' in enriched_df.columns


class TestPlottingUtilities:
    """Test plotting utility methods"""

    def test_safe_plot_data(self, analytics):
        """Test safe plotting data filtering"""
        x = np.array([1, 2, np.nan, 4, np.inf])
        y = np.array([1, 2, 3, 4, 5])

        x_safe, y_safe = analytics.safe_plot_data(x, y)

        assert len(x_safe) < len(x)
        assert len(x_safe) == len(y_safe)
        assert all(np.isfinite(x_safe))

    def test_save_or_display_plot_gui_mode(self, analytics):
        """Test saving/displaying plot in GUI mode"""
        import matplotlib.pyplot as plt

        fig = plt.figure()

        analytics.gui_mode = True
        result = analytics.save_or_display_plot(fig, 'test_plot')

        # In GUI mode, should return the figure
        assert result is not None
        plt.close(fig)


class TestStudentDemographics:
    """Test student demographics analysis"""

    def test_analyze_student_demographics(self, analytics, sample_students_df):
        """Test student demographics analysis"""
        with patch.object(analytics, 'get_all_students', return_value=sample_students_df):
            with patch.object(analytics, 'simulate_additional_data', side_effect=lambda df: df):
                with patch('matplotlib.pyplot.figure'):
                    with patch.object(analytics, 'save_or_display_plot'):
                        analytics.analyze_student_demographics()
                        # Should complete without error

    def test_analyze_student_demographics_empty(self, analytics):
        """Test demographics analysis with no data"""
        with patch.object(analytics, 'get_all_students', return_value=pd.DataFrame()):
            with patch('builtins.print') as mock_print:
                analytics.analyze_student_demographics()
                # Should print message about no data


class TestGradeDistribution:
    """Test grade distribution analysis"""

    def test_analyze_grade_distribution(self, analytics, sample_modules_df):
        """Test grade distribution analysis"""
        with patch.object(analytics, 'get_all_modules', return_value=sample_modules_df):
            with patch('matplotlib.pyplot.figure'):
                with patch.object(analytics, 'save_or_display_plot'):
                    analytics.analyze_grade_distribution()

    def test_analyze_grade_distribution_empty(self, analytics):
        """Test grade distribution with no data"""
        with patch.object(analytics, 'get_all_modules', return_value=pd.DataFrame()):
            with patch('builtins.print') as mock_print:
                analytics.analyze_grade_distribution()


class TestCourseEnrollments:
    """Test course enrollment analysis"""

    def test_analyze_course_enrollments(self, analytics, sample_students_df):
        """Test course enrollment analysis"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())
        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch('matplotlib.pyplot.figure'):
                with patch('matplotlib.pyplot.colorbar'):
                    with patch('pandas.core.frame.DataFrame.plot'):
                        with patch.object(analytics, 'save_or_display_plot'):
                            analytics.analyze_course_enrollments()


class TestRegistrationTimeline:
    """Test registration timeline analysis"""

    def test_analyze_registration_timeline(self, analytics, sample_students_df):
        """Test registration timeline analysis"""
        with patch.object(analytics, 'get_all_students', return_value=sample_students_df):
            with patch('matplotlib.pyplot.figure'):
                with patch.object(analytics, 'save_or_display_plot'):
                    analytics.analyze_registration_timeline()


class TestAcademicRisk:
    """Test academic risk assessment"""

    def test_analyze_academic_risk(self, analytics, sample_students_df, sample_modules_df):
        """Test academic risk analysis"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())

        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch.object(analytics, 'get_all_modules', return_value=sample_modules_df):
                with patch('matplotlib.pyplot.figure'):
                    with patch.object(analytics, 'save_or_display_plot'):
                        analytics.analyze_academic_risk()


class TestModuleDifficulty:
    """Test module difficulty analysis"""

    def test_analyze_module_difficulty(self, analytics, sample_modules_df):
        """Test module difficulty analysis"""
        enriched_modules = analytics.simulate_module_data(sample_modules_df.copy())

        with patch.object(analytics, 'get_all_modules', return_value=enriched_modules):
            with patch('matplotlib.pyplot.figure'):
                with patch.object(analytics, 'save_or_display_plot'):
                    analytics.analyze_module_difficulty()


class TestCorrelationAnalysis:
    """Test correlation analysis"""

    def test_analyze_correlations(self, analytics, sample_students_df):
        """Test correlation analysis"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())

        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch('matplotlib.pyplot.figure'):
                with patch.object(analytics, 'save_or_display_plot'):
                    analytics.analyze_correlations()


class TestEngagementAnalysis:
    """Test engagement analysis"""

    def test_analyze_engagement(self, analytics, sample_students_df, sample_modules_df):
        """Test engagement analysis"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())
        enriched_modules = analytics.simulate_module_data(sample_modules_df.copy())

        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch.object(analytics, 'get_all_modules', return_value=enriched_modules):
                with patch('matplotlib.pyplot.figure'):
                    with patch.object(analytics, 'save_or_display_plot'):
                        analytics.analyze_engagement()


class TestPredictiveAnalytics:
    """Test predictive analytics"""

    def test_predictive_analytics(self, analytics, sample_students_df, sample_modules_df):
        """Test predictive analytics"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())

        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch.object(analytics, 'get_all_modules', return_value=sample_modules_df):
                with patch('matplotlib.pyplot.figure'):
                    with patch.object(analytics, 'save_or_display_plot'):
                        analytics.predictive_analytics()


class TestCohortAnalysis:
    """Test cohort analysis"""

    def test_analyze_cohorts(self, analytics, sample_students_df):
        """Test cohort analysis"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())
        enriched_students['registration_datetime'] = pd.to_datetime(enriched_students['registration_datetime'])

        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch('matplotlib.pyplot.figure'):
                with patch.object(analytics, 'save_or_display_plot'):
                    analytics.analyze_cohorts()


class TestPerformanceTrends:
    """Test performance trends analysis"""

    def test_analyze_performance_trends(self, analytics, sample_modules_df):
        """Test performance trends analysis"""
        enriched_modules = analytics.simulate_module_data(sample_modules_df.copy())

        with patch.object(analytics, 'get_all_modules', return_value=enriched_modules):
            with patch('matplotlib.pyplot.figure'):
                with patch.object(analytics, 'save_or_display_plot'):
                    analytics.analyze_performance_trends()


class TestModulePopularity:
    """Test module popularity analysis"""

    def test_analyze_module_popularity(self, analytics, sample_modules_df):
        """Test module popularity analysis"""
        enriched_modules = analytics.simulate_module_data(sample_modules_df.copy())
        with patch.object(analytics, 'get_all_modules', return_value=enriched_modules):
            with patch('matplotlib.pyplot.figure'):
                with patch('matplotlib.pyplot.colorbar'):
                    with patch('pandas.core.frame.DataFrame.plot'):
                        with patch.object(analytics, 'save_or_display_plot'):
                            analytics.analyze_module_popularity()


class TestDataExport:
    """Test data export functionality"""

    def test_export_data(self, analytics, sample_students_df):
        """Test exporting data"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())
        with patch('builtins.input', side_effect=['2']):
            with patch.object(analytics, 'get_all_students', return_value=enriched_students):
                with patch.object(analytics, 'get_all_modules', return_value=pd.DataFrame()):
                    with patch('pandas.DataFrame.to_csv'):
                        with patch('builtins.print'):
                            analytics.export_data()


class TestDataQualityCheck:
    """Test data quality checking"""

    def test_data_quality_check(self, analytics, sample_students_df, sample_modules_df):
        """Test data quality check"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())
        enriched_modules = analytics.simulate_module_data(sample_modules_df.copy())
        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch.object(analytics, 'get_all_modules', return_value=enriched_modules):
                with patch('builtins.print'):
                    analytics.data_quality_check()


class TestAdvancedFiltering:
    """Test advanced filtering"""

    def test_advanced_filtering_add_filter(self, analytics, sample_students_df):
        """Test adding filters"""
        with patch.object(analytics, 'get_all_students', return_value=sample_students_df):
            with patch('builtins.input', side_effect=['4', 'CS', '9']):
                with patch('builtins.print'):
                    analytics.advanced_filtering()

                    assert 'course' in analytics.custom_filters
                    assert analytics.custom_filters['course'] == ['CS']

    def test_advanced_filtering_clear_filters(self, analytics, sample_students_df):
        """Test clearing filters"""
        analytics.custom_filters = {'course': 'CS'}

        with patch.object(analytics, 'get_all_students', return_value=sample_students_df):
            with patch('builtins.input', side_effect=['8', '9']):
                with patch('builtins.print'):
                    analytics.advanced_filtering()

                    assert len(analytics.custom_filters) == 0


class TestConfigurationSettings:
    """Test configuration settings"""

    def test_configuration_settings(self, analytics):
        """Test updating configuration settings"""
        with patch('builtins.input', side_effect=['1', 'png,pdf', '5']):
            with patch('builtins.print'):
                analytics.configuration_settings()

                assert 'png' in CONFIG['export_formats']


class TestReportGeneration:
    """Test report generation"""

    def test_generate_complete_report(self, analytics, sample_students_df, sample_modules_df):
        """Test generating complete report"""
        enriched_students = analytics.simulate_additional_data(sample_students_df.copy())
        enriched_modules = analytics.simulate_module_data(sample_modules_df.copy())

        with patch.object(analytics, 'get_all_students', return_value=enriched_students):
            with patch.object(analytics, 'get_all_modules', return_value=enriched_modules):
                with patch('education_system.post_18.university_system.modules.shared.services.analytics.student_analytics.reporting.PdfPages') as mock_pdf:
                    mock_pdf_instance = MagicMock()
                    mock_pdf.return_value.__enter__ = Mock(return_value=mock_pdf_instance)
                    mock_pdf.return_value.__exit__ = Mock(return_value=False)
                    with patch('matplotlib.pyplot.figure'):
                        with patch('matplotlib.pyplot.close'):
                            with patch('matplotlib.pyplot.axis'):
                                with patch('matplotlib.pyplot.text'):
                                    with patch('os.path.getsize', return_value=1024):
                                        with patch('builtins.print'):
                                            analytics.generate_complete_report()


class TestEmailReports:
    """Test email reporting functionality"""

    def test_email_reports(self, analytics):
        """Test email reports menu"""
        with patch('builtins.input', side_effect=['3']):
            with patch('builtins.print'):
                analytics.email_reports()

    def test_send_email_with_attachment(self, analytics):
        """Test sending email with attachment"""
        with patch('smtplib.SMTP'):
            with patch('builtins.print'):
                # This will fail due to missing config, but tests the flow
                try:
                    analytics.send_email_with_attachment(
                        'test@example.com',
                        'Test Subject',
                        'demographics'
                    )
                except (OSError, IOError):
                    pass  # Expected to fail without proper email config


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
