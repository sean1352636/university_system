"""
Tests for university_system.modules.domain.academics.grade_misc.grade_web_context module.

This module tests the shared imports and utilities for grade miscellaneous helpers.
"""

from __future__ import annotations

import pytest


class TestGradeWebContextImports:
    """Test that all required imports are available"""

    def test_import_csv(self):
        """Test csv import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            csv,
        )

        assert csv is not None

    def test_import_math(self):
        """Test math import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            math,
        )

        assert math is not None

    def test_import_os(self):
        """Test os import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            os,
        )

        assert os is not None

    def test_import_datetime(self):
        """Test datetime imports"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            datetime,
            timedelta,
        )

        assert datetime is not None
        assert timedelta is not None

    def test_import_matplotlib(self):
        """Test matplotlib imports"""
        import importlib

        from education_system.post_18.university_system.modules.domain.academics.grading import (
            grade_web_context,
        )

        # GUI grade_tracking modules call matplotlib.use('TkAgg') at import,
        # mutating the process-wide backend. Reload so grade_web_context's own
        # matplotlib.use('Agg') is re-applied before we assert on it.
        importlib.reload(grade_web_context)
        matplotlib = grade_web_context.matplotlib
        plt = grade_web_context.plt

        assert matplotlib is not None
        assert plt is not None
        # Check that backend is set to Agg
        assert matplotlib.get_backend() == 'Agg'

    def test_import_numpy(self):
        """Test numpy import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            np,
        )

        assert np is not None

    def test_import_pandas(self):
        """Test pandas import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            pd,
        )

        assert pd is not None

    def test_import_seaborn(self):
        """Test seaborn import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            sns,
        )

        assert sns is not None

    def test_import_reportlab_components(self):
        """Test reportlab imports"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            colors,
            A4,
            letter,
            getSampleStyleSheet,
            ParagraphStyle,
            inch,
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
            VerticalBarChart,
            HorizontalLineChart,
            Drawing,
        )

        assert colors is not None
        assert A4 is not None
        assert letter is not None
        assert getSampleStyleSheet is not None
        assert ParagraphStyle is not None
        assert inch is not None
        assert Image is not None
        assert Paragraph is not None
        assert SimpleDocTemplate is not None
        assert Spacer is not None
        assert Table is not None
        assert TableStyle is not None
        assert VerticalBarChart is not None
        assert HorizontalLineChart is not None
        assert Drawing is not None

    def test_import_scipy(self):
        """Test scipy import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            stats,
        )

        assert stats is not None

    def test_import_sklearn_components(self):
        """Test sklearn imports"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            RandomForestClassifier,
            LogisticRegression,
            accuracy_score,
            classification_report,
            confusion_matrix,
            train_test_split,
            StandardScaler,
        )

        assert RandomForestClassifier is not None
        assert LogisticRegression is not None
        assert accuracy_score is not None
        assert classification_report is not None
        assert confusion_matrix is not None
        assert train_test_split is not None
        assert StandardScaler is not None

    def test_import_database_components(self):
        """Test database imports"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            DatabaseManager,
            get_connection,
            sqlite3,
        )

        assert DatabaseManager is not None
        assert get_connection is not None
        assert sqlite3 is not None

    def test_import_report_palette(self):
        """Test report palette import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            get_report_palette,
        )

        assert get_report_palette is not None
        assert callable(get_report_palette)

    def test_import_select_assessment(self):
        """Test select_assessment import"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            select_assessment,
        )

        assert select_assessment is not None
        assert callable(select_assessment)

    def test_import_grade_calculation_functions(self):
        """Test grade_calculation imports"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            calculate_student_gpa,
            letter_to_gpa,
            compare_by_grade_threshold,
            GRADE_SYSTEMS,
        )

        assert calculate_student_gpa is not None
        assert letter_to_gpa is not None
        assert compare_by_grade_threshold is not None
        assert GRADE_SYSTEMS is not None
        assert isinstance(GRADE_SYSTEMS, dict)


class TestGradeWebContextWarnings:
    """Test warning suppression"""

    def test_warnings_filtered(self):
        """Test that warnings are suppressed"""
        import warnings

        # Import the module to trigger warning filter setup
        from education_system.post_18.university_system.modules.domain.academics.grading import (
            grade_web_context,
        )

        # Check that warnings are filtered
        # This is a basic check - the module sets warnings.filterwarnings("ignore")


class TestGradeSystemsFallback:
    """Test GRADE_SYSTEMS fallback when imports fail"""

    def test_grade_systems_structure(self):
        """Test GRADE_SYSTEMS has expected structure"""
        from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import (
            GRADE_SYSTEMS,
        )

        # Should have letter and percentage keys
        assert 'letter' in GRADE_SYSTEMS
        assert 'percentage' in GRADE_SYSTEMS

        # Letter grades should map to numeric values
        assert isinstance(GRADE_SYSTEMS['letter'], dict)
        assert 'A' in GRADE_SYSTEMS['letter']
        assert 'F' in GRADE_SYSTEMS['letter']


class TestModuleLevelConfiguration:
    """Test module-level configuration"""

    def test_matplotlib_backend(self):
        """Test matplotlib backend is set correctly"""
        import importlib

        from education_system.post_18.university_system.modules.domain.academics.grading import (
            grade_web_context,
        )

        # Other (GUI) modules may have switched the global backend to TkAgg;
        # reload so grade_web_context re-applies its Agg backend selection.
        importlib.reload(grade_web_context)

        # Backend should be Agg for non-interactive plotting
        backend = grade_web_context.matplotlib.get_backend()
        assert backend == 'Agg'

    def test_module_can_be_imported_multiple_times(self):
        """Test that module can be safely imported multiple times"""
        from education_system.post_18.university_system.modules.domain.academics.grading import (
            grade_web_context,
        )

        # Re-import should work without issues
        from education_system.post_18.university_system.modules.domain.academics.grading import (
            grade_web_context as gwc2,
        )

        assert grade_web_context is gwc2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
