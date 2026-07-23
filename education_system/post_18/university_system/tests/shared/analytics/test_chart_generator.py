"""
Comprehensive tests for chart_generator.py

Tests all chart generation functionality, database integration,
email features, and chart viewer components.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path


@pytest.fixture
def mock_matplotlib():
    """Mock matplotlib and related libraries"""
    with patch.dict('sys.modules', {
        'matplotlib': MagicMock(),
        'matplotlib.pyplot': MagicMock(),
        'matplotlib.backends': MagicMock(),
        'matplotlib.backends.backend_tkagg': MagicMock(),
        'matplotlib.figure': MagicMock(),
        'seaborn': MagicMock(),
        'numpy': MagicMock(),
    }):
        yield


@pytest.fixture
def chart_generator_module(mock_matplotlib):
    """Import chart_generator module with mocked dependencies"""
    import importlib
    import sys

    mod_key = 'education_system.post_18.university_system.modules.shared.utils.chart_generator'

    # Remove if already imported so a fresh import picks up the mocked
    # matplotlib/numpy/seaborn. We must use importlib.import_module on the
    # fully-qualified key rather than `from package import submodule`: the
    # latter would rebind the existing attribute still held on the parent
    # package without re-registering the submodule in sys.modules, which
    # would leave the module key absent for any later reload.
    sys.modules.pop(mod_key, None)

    # Mock database connection during module load so import has no side effects
    with patch('education_system.post_18.university_system.infrastructure.database.db.get_connection') as mock_conn:
        mock_conn.return_value = MagicMock()
        chart_generator = importlib.import_module(mod_key)

    return chart_generator


class TestChartGenerator:
    """Test ChartGenerator class"""

    def test_init_with_charts_available(self, chart_generator_module):
        """Test initialization when matplotlib is available"""
        chart_generator_module.CHARTS_AVAILABLE = True

        gen = chart_generator_module.ChartGenerator()
        assert gen.available is True

    def test_init_with_charts_unavailable(self, chart_generator_module):
        """Test initialization when matplotlib is not available"""
        chart_generator_module.CHARTS_AVAILABLE = False

        gen = chart_generator_module.ChartGenerator()
        assert gen.available is False

    def test_is_available(self, chart_generator_module):
        """Test is_available method"""
        gen = chart_generator_module.ChartGenerator()
        chart_generator_module.CHARTS_AVAILABLE = True
        gen.available = True

        assert gen.is_available() is True

        gen.available = False
        assert gen.is_available() is False

    def test_generate_bar_chart(self, chart_generator_module):
        """Test bar chart generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {
                'labels': ['A', 'B', 'C'],
                'values': [10, 20, 15],
                'xlabel': 'Category',
                'ylabel': 'Count'
            }

            fig = gen.generate_chart('bar', data, 'Test Bar Chart')

            assert fig is not None
            mock_ax.bar.assert_called_once()

    def test_generate_line_chart(self, chart_generator_module):
        """Test line chart generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {
                'x': [1, 2, 3, 4],
                'y': [10, 20, 15, 25],
                'xlabel': 'Time',
                'ylabel': 'Value'
            }

            fig = gen.generate_chart('line', data, 'Test Line Chart')

            assert fig is not None
            mock_ax.plot.assert_called_once()

    def test_generate_pie_chart(self, chart_generator_module):
        """Test pie chart generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax
            mock_ax.pie.return_value = ([], [], [])

            data = {
                'labels': ['A', 'B', 'C'],
                'sizes': [30, 40, 30]
            }

            fig = gen.generate_chart('pie', data, 'Test Pie Chart')

            assert fig is not None
            mock_ax.pie.assert_called_once()

    def test_generate_histogram(self, chart_generator_module):
        """Test histogram generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax
            mock_ax.hist.return_value = ([], [], [])

            data = {
                'values': [1, 2, 2, 3, 3, 3, 4, 4, 5],
                'bins': 5
            }

            fig = gen.generate_chart('histogram', data, 'Test Histogram')

            assert fig is not None
            mock_ax.hist.assert_called_once()

    def test_generate_scatter_plot(self, chart_generator_module):
        """Test scatter plot generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {
                'x': [1, 2, 3, 4, 5],
                'y': [2, 4, 6, 8, 10]
            }

            fig = gen.generate_chart('scatter', data, 'Test Scatter Plot')

            assert fig is not None
            mock_ax.scatter.assert_called_once()

    def test_generate_heatmap(self, chart_generator_module):
        """Test heatmap generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {
                'matrix': [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                'xlabels': ['X1', 'X2', 'X3'],
                'ylabels': ['Y1', 'Y2', 'Y3']
            }

            fig = gen.generate_chart('heatmap', data, 'Test Heatmap')

            assert fig is not None
            mock_ax.imshow.assert_called_once()

    def test_generate_box_plot(self, chart_generator_module):
        """Test box plot generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax
            mock_ax.boxplot.return_value = {'boxes': []}

            data = {
                'values': [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6]],
                'labels': ['Group 1', 'Group 2']
            }

            fig = gen.generate_chart('box', data, 'Test Box Plot')

            assert fig is not None
            mock_ax.boxplot.assert_called_once()

    def test_generate_grouped_bar_chart(self, chart_generator_module):
        """Test grouped bar chart generation"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure, \
             patch.object(chart_generator_module, 'np') as mock_np:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax
            import numpy as real_np
            mock_np.arange.return_value = real_np.arange(3)

            data = {
                'labels': ['A', 'B', 'C'],
                'groups': {
                    'Group 1': [10, 20, 15],
                    'Group 2': [15, 25, 20]
                }
            }

            fig = gen.generate_chart('grouped_bar', data, 'Test Grouped Bar')

            assert fig is not None
            assert mock_ax.bar.call_count == 2  # One for each group

    def test_generate_chart_unavailable(self, chart_generator_module):
        """Test chart generation when matplotlib is unavailable"""
        gen = chart_generator_module.ChartGenerator()
        gen.available = False

        data = {'labels': ['A'], 'values': [1]}
        fig = gen.generate_chart('bar', data)

        assert fig is None

    def test_generate_chart_with_error(self, chart_generator_module):
        """Test chart generation with error handling"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_figure.side_effect = Exception("Test error")

            data = {'labels': ['A'], 'values': [1]}
            fig = gen.generate_chart('bar', data)

            assert fig is None

    def test_default_to_bar_chart(self, chart_generator_module):
        """Test that unknown chart types default to bar chart"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {'labels': ['A'], 'values': [1]}
            fig = gen.generate_chart('unknown_type', data, 'Test')

            assert fig is not None
            mock_ax.bar.assert_called_once()

    @patch('tempfile.mkstemp')
    def test_save_chart_with_temp_file(self, mock_mkstemp, chart_generator_module):
        """Test saving chart to temporary file"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()

        # Mock tempfile
        mock_mkstemp.return_value = (1, '/tmp/chart_test.png')

        # Mock figure
        mock_fig = MagicMock()

        with patch('os.close'):
            filename = gen.save_chart(mock_fig)

        assert filename == '/tmp/chart_test.png'
        mock_fig.savefig.assert_called_once()

    def test_save_chart_with_filename(self, chart_generator_module):
        """Test saving chart to specific file"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()

        mock_fig = MagicMock()
        filename = '/tmp/my_chart.png'

        result = gen.save_chart(mock_fig, filename)

        assert result == filename
        mock_fig.savefig.assert_called_once_with(
            filename, dpi=150, bbox_inches='tight', facecolor='white'
        )

    def test_email_chart_success(self, chart_generator_module):
        """Test emailing chart successfully"""
        chart_generator_module.EMAIL_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()

        with patch.object(chart_generator_module, 'send_email_as_system') as mock_send, \
             patch.object(chart_generator_module, 'datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = '20250101_120000'
            mock_send.return_value = True

            mock_fig = MagicMock()

            result = gen.email_chart(mock_fig, 'test@example.com', 'Test Chart')

            assert result is True
            mock_send.assert_called_once()
            mock_fig.savefig.assert_called_once()

    def test_email_chart_failure(self, chart_generator_module):
        """Test emailing chart with failure"""
        chart_generator_module.EMAIL_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()

        with patch.object(chart_generator_module, 'send_email_as_system') as mock_send:
            mock_send.return_value = False

            mock_fig = MagicMock()

            result = gen.email_chart(mock_fig, 'test@example.com', 'Test Chart')

            assert result is False

    def test_email_chart_unavailable(self, chart_generator_module, capsys):
        """Test emailing chart when email is unavailable"""
        chart_generator_module.EMAIL_AVAILABLE = False
        gen = chart_generator_module.ChartGenerator()

        mock_fig = MagicMock()

        result = gen.email_chart(mock_fig, 'test@example.com', 'Test Chart')

        assert result is False
        captured = capsys.readouterr()
        assert "Email service not available" in captured.out

    def test_email_chart_with_custom_message(self, chart_generator_module):
        """Test emailing chart with custom message"""
        chart_generator_module.EMAIL_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()

        with patch.object(chart_generator_module, 'send_email_as_system') as mock_send:
            mock_send.return_value = True
            mock_fig = MagicMock()

            custom_msg = "This is a custom message for the chart."
            result = gen.email_chart(
                mock_fig, 'test@example.com', 'Test Chart', message=custom_msg
            )

            assert result is True
            # Check that custom message was used in body kwarg
            call_args = mock_send.call_args
            assert custom_msg == call_args.kwargs['body']


class TestDatabaseChartGenerator:
    """Test DatabaseChartGenerator class"""

    def test_generate_age_distribution(self, chart_generator_module):
        """Test age distribution chart generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [(20,), (21,), (22,), (23,), (24,)]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn), \
             patch.object(chart_generator_module.ChartGenerator, 'generate_chart') as mock_gen:
            mock_gen.return_value = MagicMock()

            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_age_distribution()

            assert fig is not None
            mock_cursor.execute.assert_called_once()
            mock_gen.assert_called_once_with('histogram', {
                'values': [20, 21, 22, 23, 24],
                'bins': 20,
                'xlabel': 'Age',
                'ylabel': 'Number of Students',
                'color': 'steelblue'
            }, 'Student Age Distribution')

    def test_generate_age_distribution_no_data(self, chart_generator_module):
        """Test age distribution with no data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn):
            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_age_distribution()

            assert fig is None

    def test_generate_course_distribution(self, chart_generator_module):
        """Test course distribution chart generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('Computer Science', 100),
            ('Engineering', 80),
            ('Mathematics', 60)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn), \
             patch.object(chart_generator_module.ChartGenerator, 'generate_chart') as mock_gen:
            mock_gen.return_value = MagicMock()

            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_course_distribution()

            assert fig is not None
            mock_gen.assert_called_once_with('pie', {
                'labels': ['Computer Science', 'Engineering', 'Mathematics'],
                'sizes': [100, 80, 60]
            }, 'Course Distribution')

    def test_generate_registration_timeline(self, chart_generator_module):
        """Test registration timeline chart generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('2024-01', 50),
            ('2024-02', 60),
            ('2024-03', 70)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn), \
             patch.object(chart_generator_module.ChartGenerator, 'generate_chart') as mock_gen:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_fig.axes = [mock_ax]
            mock_gen.return_value = mock_fig

            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_registration_timeline()

            assert fig is not None
            mock_ax.set_xticks.assert_called_once()
            mock_ax.set_xticklabels.assert_called_once()

    def test_generate_gender_course_distribution(self, chart_generator_module):
        """Test gender-course distribution chart generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('Computer Science', 'male', 60),
            ('Computer Science', 'female', 40),
            ('Engineering', 'male', 70),
            ('Engineering', 'female', 30)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn), \
             patch.object(chart_generator_module.ChartGenerator, 'generate_chart') as mock_gen:
            mock_gen.return_value = MagicMock()

            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_gender_course_distribution()

            assert fig is not None
            call_args = mock_gen.call_args
            assert call_args[0][0] == 'grouped_bar'
            assert 'Male' in call_args[0][1]['groups']
            assert 'Female' in call_args[0][1]['groups']

    def test_generate_module_popularity(self, chart_generator_module):
        """Test module popularity chart generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('CS101', 150),
            ('CS102', 120),
            ('CS201', 100)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn), \
             patch.object(chart_generator_module.ChartGenerator, 'generate_chart') as mock_gen:
            mock_gen.return_value = MagicMock()

            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_module_popularity()

            assert fig is not None
            mock_gen.assert_called_once_with('bar', {
                'labels': ['CS101', 'CS102', 'CS201'],
                'values': [150, 120, 100],
                'xlabel': 'Module Code',
                'ylabel': 'Enrollments',
                'color': 'coral'
            }, 'Top 15 Most Popular Modules')

    def test_generate_grade_distribution(self, chart_generator_module):
        """Test grade distribution chart generation"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('A', 30),
            ('B', 50),
            ('C', 40),
            ('D', 20),
            ('F', 10)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn), \
             patch.object(chart_generator_module.ChartGenerator, 'generate_chart') as mock_gen:
            mock_gen.return_value = MagicMock()

            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_grade_distribution()

            assert fig is not None
            mock_gen.assert_called_once_with('bar', {
                'labels': ['A', 'B', 'C', 'D', 'F'],
                'values': [30, 50, 40, 20, 10],
                'xlabel': 'Grade',
                'ylabel': 'Number of Students',
                'color': 'mediumseagreen'
            }, 'Overall Grade Distribution')

    def test_database_error_handling(self, chart_generator_module, capsys):
        """Test error handling for database errors"""
        with patch.object(chart_generator_module, 'get_connection',
                         side_effect=Exception("Database connection error")):
            db_gen = chart_generator_module.DatabaseChartGenerator()
            fig = db_gen.generate_age_distribution()

            assert fig is None
            captured = capsys.readouterr()
            assert "Error" in captured.out


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_get_admin_emails(self, chart_generator_module):
        """Test getting admin emails from database"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('admin1@university.edu',),
            ('admin2@university.edu',),
            ('admin3@university.edu',)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn):
            emails = chart_generator_module.get_admin_emails()

            assert len(emails) == 3
            assert 'admin1@university.edu' in emails
            assert 'admin2@university.edu' in emails

    def test_get_admin_emails_with_nulls(self, chart_generator_module):
        """Test getting admin emails filters out nulls"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ('admin1@university.edu',),
            (None,),
            ('admin2@university.edu',),
            ('',)
        ]

        with patch.object(chart_generator_module, 'get_connection', return_value=mock_conn):
            emails = chart_generator_module.get_admin_emails()

            assert len(emails) == 2
            assert None not in emails
            assert '' not in emails

    def test_get_admin_emails_error(self, chart_generator_module):
        """Test getting admin emails with error returns default"""
        with patch.object(chart_generator_module, 'get_connection',
                         side_effect=Exception("Database error")):
            emails = chart_generator_module.get_admin_emails()

            assert emails == ["admin@university.edu"]


class TestChartTypes:
    """Test all chart type generation methods"""

    @pytest.fixture
    def setup_chart_generator(self, chart_generator_module):
        """Setup chart generator with mocked Figure"""
        chart_generator_module.CHARTS_AVAILABLE = True
        gen = chart_generator_module.ChartGenerator()
        gen.available = True
        return gen

    def test_bar_chart_with_all_options(self, setup_chart_generator, chart_generator_module):
        """Test bar chart with all options"""
        gen = setup_chart_generator

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_bar = MagicMock()
            mock_bar.get_height.return_value = 10
            mock_bar.get_x.return_value = 0
            mock_bar.get_width.return_value = 1
            mock_ax.bar.return_value = [mock_bar]

            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {
                'labels': ['A', 'B', 'C'],
                'values': [10, 20, 15],
                'xlabel': 'Category',
                'ylabel': 'Count',
                'color': 'red'
            }

            fig = gen.generate_chart('bar', data, 'Test')

            assert fig is not None
            mock_ax.set_xlabel.assert_called_with('Category')
            mock_ax.set_ylabel.assert_called_with('Count')
            mock_ax.set_title.assert_called_with('Test', fontweight='bold', pad=20)

    def test_line_chart_with_string_x_values(self, setup_chart_generator, chart_generator_module):
        """Test line chart with string x values rotates labels"""
        gen = setup_chart_generator

        with patch.object(chart_generator_module, 'Figure') as mock_figure:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            data = {
                'x': ['Jan', 'Feb', 'Mar'],
                'y': [10, 20, 15]
            }

            fig = gen.generate_chart('line', data, 'Test')

            assert fig is not None
            mock_ax.set_xticklabels.assert_called_once()

    def test_pie_chart_with_custom_colors(self, setup_chart_generator, chart_generator_module):
        """Test pie chart with custom colors"""
        gen = setup_chart_generator

        with patch.object(chart_generator_module, 'Figure') as mock_figure, \
             patch.object(chart_generator_module, 'sns') as mock_sns:
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_figure.return_value = mock_fig
            mock_fig.add_subplot.return_value = mock_ax

            # Mock pie return values
            mock_wedges = []
            mock_texts = []
            mock_autotexts = [MagicMock(), MagicMock()]
            mock_ax.pie.return_value = (mock_wedges, mock_texts, mock_autotexts)

            data = {
                'labels': ['A', 'B'],
                'sizes': [40, 60],
                'colors': ['red', 'blue']
            }

            fig = gen.generate_chart('pie', data, 'Test')

            assert fig is not None
            # Verify autotexts were styled
            for autotext in mock_autotexts:
                autotext.set_color.assert_called_with('white')
                autotext.set_weight.assert_called_with('bold')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
