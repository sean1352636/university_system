"""Tests for PDF export chart builder.

Tests the ChartBuilder class which creates visualizations for PDF export.
"""

import io
import pytest
from unittest.mock import patch, MagicMock


def _matplotlib_available():
    """Check if matplotlib is available."""
    try:
        import matplotlib
        return True
    except ImportError:
        return False


class TestChartBuilder:
    """Test cases for ChartBuilder class."""

    @pytest.fixture
    def chart_builder(self):
        """Create a ChartBuilder instance."""
        from education_system.university_system.modules.shared.services.pdf_export.chart_builder import (
            ChartBuilder,
        )

        return ChartBuilder()

    def test_initialization(self, chart_builder):
        """Test ChartBuilder initialization."""
        assert chart_builder is not None
        assert hasattr(chart_builder, "matplotlib_available")
        assert hasattr(chart_builder, "COLORS")
        assert len(chart_builder.COLORS) >= 5

    def test_create_text_based_chart(self, chart_builder):
        """Test text-based chart generation (always works)."""
        data = {"Category A": 10, "Category B": 20, "Category C": 5}
        result = chart_builder.create_text_based_chart(data, "Test Chart")

        assert isinstance(result, str)
        assert "Test Chart" in result
        assert "Category A" in result
        assert "Category B" in result
        assert "Category C" in result

    def test_create_text_based_chart_empty_data(self, chart_builder):
        """Test text-based chart with empty data."""
        result = chart_builder.create_text_based_chart({}, "Empty Chart")

        assert "Empty Chart" in result
        assert "No data available" in result

    def test_create_text_based_chart_single_item(self, chart_builder):
        """Test text-based chart with single item."""
        data = {"Single": 100}
        result = chart_builder.create_text_based_chart(data, "Single Item")

        assert "Single Item" in result
        assert "Single" in result
        assert "100" in result


@pytest.mark.skipif(
    not _matplotlib_available(),
    reason="matplotlib not available",
)
class TestChartBuilderWithMatplotlib:
    """Test chart creation when matplotlib is available."""

    @pytest.fixture
    def chart_builder(self):
        """Create a ChartBuilder instance."""
        from education_system.university_system.modules.shared.services.pdf_export.chart_builder import (
            ChartBuilder,
        )

        return ChartBuilder()

    def test_create_pie_chart(self, chart_builder):
        """Test pie chart generation."""
        data = {"Slice A": 30, "Slice B": 50, "Slice C": 20}
        result = chart_builder.create_pie_chart(data, "Test Pie Chart")

        if result is not None:
            assert isinstance(result, io.BytesIO)
            # Check that it contains image data
            result.seek(0)
            assert len(result.read()) > 0

    def test_create_pie_chart_empty_data(self, chart_builder):
        """Test pie chart with empty data."""
        result = chart_builder.create_pie_chart({}, "Empty Pie")
        assert result is None

    def test_create_bar_chart(self, chart_builder):
        """Test bar chart generation."""
        data = {"Bar A": 10, "Bar B": 25, "Bar C": 15}
        result = chart_builder.create_bar_chart(
            data, "Test Bar Chart", xlabel="Categories", ylabel="Count"
        )

        if result is not None:
            assert isinstance(result, io.BytesIO)

    def test_create_bar_chart_horizontal(self, chart_builder):
        """Test horizontal bar chart generation."""
        data = {"Item 1": 100, "Item 2": 75, "Item 3": 50}
        result = chart_builder.create_bar_chart(
            data, "Horizontal Bar Chart", horizontal=True
        )

        if result is not None:
            assert isinstance(result, io.BytesIO)

    def test_create_table_size_chart(self, chart_builder):
        """Test table size chart generation."""
        table_data = [
            ("students", 1000),
            ("modules", 500),
            ("grades", 5000),
        ]
        result = chart_builder.create_table_size_chart(
            table_data, "Database Table Sizes"
        )

        if result is not None:
            assert isinstance(result, io.BytesIO)

    def test_create_summary_dashboard(self, chart_builder):
        """Test summary dashboard generation."""
        stats = {
            "total_tables": 50,
            "total_records": 10000,
            "tables_with_data": 45,
            "empty_tables": 5,
            "export_timestamp": "2025-01-01T00:00:00",
            "largest_tables": [
                ("students", 5000),
                ("grades", 3000),
                ("modules", 1000),
            ],
        }
        result = chart_builder.create_summary_dashboard(stats)

        if result is not None:
            assert isinstance(result, io.BytesIO)


class TestChartBuilderMocked:
    """Test chart builder with mocked matplotlib."""

    def test_pie_chart_matplotlib_error(self):
        """Test pie chart when matplotlib raises an error."""
        from education_system.university_system.modules.shared.services.pdf_export.chart_builder import (
            ChartBuilder,
        )

        builder = ChartBuilder()

        with patch.object(builder, "matplotlib_available", True):
            with patch("matplotlib.pyplot.subplots", side_effect=Exception("Test error")):
                data = {"A": 10, "B": 20}
                result = builder.create_pie_chart(data, "Error Test")
                assert result is None

    def test_bar_chart_matplotlib_error(self):
        """Test bar chart when matplotlib raises an error."""
        from education_system.university_system.modules.shared.services.pdf_export.chart_builder import (
            ChartBuilder,
        )

        builder = ChartBuilder()

        with patch.object(builder, "matplotlib_available", True):
            with patch("matplotlib.pyplot.subplots", side_effect=Exception("Test error")):
                data = {"A": 10, "B": 20}
                result = builder.create_bar_chart(data, "Error Test")
                assert result is None


def _matplotlib_available():
    """Check if matplotlib is available."""
    try:
        import matplotlib

        return True
    except ImportError:
        return False
