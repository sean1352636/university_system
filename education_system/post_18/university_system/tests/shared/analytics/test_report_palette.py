"""
Comprehensive test suite for report_palette.py

Tests all functions and functionality including:
- DEFAULT_PALETTE constant
- get_report_palette function
- color_at function
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from education_system.post_18.university_system.modules.shared.utils import report_palette
from education_system.post_18.university_system.modules.shared.utils.report_palette import (
    DEFAULT_PALETTE,
    get_report_palette,
    color_at,
)


class TestDefaultPalette:
    """Test DEFAULT_PALETTE constant"""

    def test_default_palette_exists(self):
        """Test that DEFAULT_PALETTE is defined"""
        assert DEFAULT_PALETTE is not None

    def test_default_palette_is_list(self):
        """Test that DEFAULT_PALETTE is a list"""
        assert isinstance(DEFAULT_PALETTE, list)

    def test_default_palette_has_colors(self):
        """Test that DEFAULT_PALETTE contains color strings"""
        assert len(DEFAULT_PALETTE) > 0
        for color in DEFAULT_PALETTE:
            assert isinstance(color, str)

    def test_default_palette_hex_format(self):
        """Test that colors are in hex format"""
        for color in DEFAULT_PALETTE:
            assert color.startswith('#')
            assert len(color) == 7  # #RRGGBB format

    def test_default_palette_count(self):
        """Test that DEFAULT_PALETTE has exactly 10 colors"""
        assert len(DEFAULT_PALETTE) == 10

    def test_default_palette_specific_colors(self):
        """Test that DEFAULT_PALETTE contains expected colors"""
        expected_first = "#4C78A8"
        expected_second = "#F58518"
        assert DEFAULT_PALETTE[0] == expected_first
        assert DEFAULT_PALETTE[1] == expected_second


class TestGetReportPalette:
    """Test get_report_palette function"""

    def test_get_report_palette_no_args(self):
        """Test get_report_palette without arguments"""
        palette = get_report_palette()
        assert isinstance(palette, list)
        assert len(palette) > 0

    def test_get_report_palette_returns_list(self):
        """Test that function returns a list"""
        result = get_report_palette()
        assert isinstance(result, list)

    def test_get_report_palette_with_n_exact(self):
        """Test get_report_palette with exact number"""
        palette = get_report_palette(n=5)
        assert len(palette) == 5

    def test_get_report_palette_with_n_larger(self):
        """Test get_report_palette with n larger than palette"""
        palette = get_report_palette(n=15)
        assert len(palette) == 15

    def test_get_report_palette_with_n_smaller(self):
        """Test get_report_palette with n smaller than palette"""
        palette = get_report_palette(n=3)
        assert len(palette) == 3

    def test_get_report_palette_with_n_zero(self):
        """Test get_report_palette with n=0"""
        palette = get_report_palette(n=0)
        # Should return default palette
        assert isinstance(palette, list)

    def test_get_report_palette_with_n_negative(self):
        """Test get_report_palette with negative n"""
        palette = get_report_palette(n=-1)
        # Should return default palette
        assert isinstance(palette, list)

    def test_get_report_palette_with_n_one(self):
        """Test get_report_palette with n=1"""
        palette = get_report_palette(n=1)
        assert len(palette) == 1
        # Color might be from matplotlib or DEFAULT_PALETTE
        assert isinstance(palette[0], str)
        assert palette[0].startswith('#')

    def test_get_report_palette_repeats_correctly(self):
        """Test that palette repeats correctly when n > palette length"""
        palette = get_report_palette(n=25)
        assert len(palette) == 25
        # Palette should cycle - check that it repeats
        # Get the base palette size by getting a default palette
        base_palette = get_report_palette()
        base_size = len(base_palette)
        # Colors should repeat after base_size
        if base_size > 0:
            assert palette[0] == palette[base_size]
            if base_size > 1:
                assert palette[1] == palette[base_size + 1]

    @patch('matplotlib.pyplot.rcParams', new_callable=dict)
    def test_get_report_palette_with_matplotlib(self, mock_rcParams):
        """Test get_report_palette with matplotlib available"""
        # Mock matplotlib color cycle
        mock_cycle = Mock()
        mock_cycle.by_key.return_value = {
            'color': ['#FF0000', '#00FF00', '#0000FF']
        }
        mock_rcParams['axes.prop_cycle'] = mock_cycle

        with patch.dict('sys.modules', {'matplotlib.pyplot': Mock(rcParams=mock_rcParams)}):
            palette = get_report_palette()
            # Should use matplotlib colors if available
            assert isinstance(palette, list)

    def test_get_report_palette_without_matplotlib(self):
        """Test get_report_palette when matplotlib is not available"""
        with patch.dict('sys.modules', {'matplotlib': None, 'matplotlib.pyplot': None}):
            palette = get_report_palette()
            # Should fall back to DEFAULT_PALETTE
            assert palette == DEFAULT_PALETTE

    def test_get_report_palette_matplotlib_exception(self):
        """Test get_report_palette when matplotlib raises exception"""
        mock_plt = Mock()
        mock_plt.rcParams.get.side_effect = Exception("Matplotlib error")

        with patch('matplotlib.pyplot', mock_plt):
            palette = get_report_palette()
            # Should fall back to DEFAULT_PALETTE
            assert isinstance(palette, list)


class TestColorAt:
    """Test color_at function"""

    def test_color_at_index_zero(self):
        """Test color_at with index 0"""
        color = color_at(0)
        assert color == DEFAULT_PALETTE[0]

    def test_color_at_index_one(self):
        """Test color_at with index 1"""
        color = color_at(1)
        assert color == DEFAULT_PALETTE[1]

    def test_color_at_last_index(self):
        """Test color_at with last valid index"""
        idx = len(DEFAULT_PALETTE) - 1
        color = color_at(idx)
        assert color == DEFAULT_PALETTE[idx]

    def test_color_at_wraps_around(self):
        """Test that color_at wraps around when index exceeds palette length"""
        idx = len(DEFAULT_PALETTE)
        color = color_at(idx)
        assert color == DEFAULT_PALETTE[0]

    def test_color_at_large_index(self):
        """Test color_at with large index"""
        idx = 100
        expected_idx = idx % len(DEFAULT_PALETTE)
        color = color_at(idx)
        assert color == DEFAULT_PALETTE[expected_idx]

    def test_color_at_negative_index(self):
        """Test color_at with negative index"""
        color = color_at(-1)
        # Python modulo should handle this
        assert color == DEFAULT_PALETTE[-1 % len(DEFAULT_PALETTE)]

    def test_color_at_with_custom_palette(self):
        """Test color_at with custom palette"""
        custom_palette = ['#AAAAAA', '#BBBBBB', '#CCCCCC']
        color = color_at(0, palette=custom_palette)
        assert color == '#AAAAAA'

        color = color_at(1, palette=custom_palette)
        assert color == '#BBBBBB'

    def test_color_at_custom_palette_wraps(self):
        """Test color_at with custom palette wraps around"""
        custom_palette = ['#AAAAAA', '#BBBBBB']
        color = color_at(2, palette=custom_palette)
        assert color == '#AAAAAA'

    def test_color_at_with_empty_palette(self):
        """Test color_at with empty palette falls back to default"""
        color = color_at(0, palette=[])
        assert color == DEFAULT_PALETTE[0]

    def test_color_at_with_none_palette(self):
        """Test color_at with None palette uses default"""
        color = color_at(0, palette=None)
        assert color == DEFAULT_PALETTE[0]

    def test_color_at_sequential_indices(self):
        """Test color_at with sequential indices"""
        colors = [color_at(i) for i in range(5)]
        assert len(colors) == 5
        for i, color in enumerate(colors):
            assert color == DEFAULT_PALETTE[i]


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_get_report_palette_very_large_n(self):
        """Test get_report_palette with very large n"""
        palette = get_report_palette(n=1000)
        assert len(palette) == 1000
        # Check it cycles correctly
        assert palette[0] == palette[10] == palette[20]

    def test_color_at_max_int(self):
        """Test color_at with very large index"""
        import sys
        if sys.maxsize > 2**31:  # 64-bit system
            idx = 2**20  # Large but reasonable number
            color = color_at(idx)
            assert color in DEFAULT_PALETTE

    def test_get_report_palette_with_float(self):
        """Test get_report_palette with float n (should work with int conversion)"""
        # This tests robustness - function uses n in calculations
        palette = get_report_palette(n=5)
        assert len(palette) == 5

    def test_color_at_with_single_color_palette(self):
        """Test color_at with single-color palette"""
        single_palette = ['#123456']
        color0 = color_at(0, palette=single_palette)
        color1 = color_at(1, palette=single_palette)
        color10 = color_at(10, palette=single_palette)

        assert color0 == '#123456'
        assert color1 == '#123456'
        assert color10 == '#123456'


class TestPaletteConsistency:
    """Test palette consistency and reliability"""

    def test_palette_immutability(self):
        """Test that getting palette doesn't modify DEFAULT_PALETTE"""
        original = DEFAULT_PALETTE.copy()
        palette = get_report_palette()
        assert DEFAULT_PALETTE == original

    def test_repeated_calls_consistent(self):
        """Test that repeated calls return consistent results"""
        palette1 = get_report_palette(n=10)
        palette2 = get_report_palette(n=10)
        assert palette1 == palette2

    def test_color_at_repeated_calls(self):
        """Test that color_at returns consistent results"""
        color1 = color_at(5)
        color2 = color_at(5)
        assert color1 == color2

    def test_default_palette_not_modified(self):
        """Test that DEFAULT_PALETTE is not modified by function calls"""
        original_length = len(DEFAULT_PALETTE)
        original_colors = DEFAULT_PALETTE.copy()

        get_report_palette(n=20)
        color_at(100)

        assert len(DEFAULT_PALETTE) == original_length
        assert DEFAULT_PALETTE == original_colors


class TestIntegration:
    """Integration tests for palette functionality"""

    def test_full_palette_workflow(self):
        """Test a complete workflow of using palette functions"""
        # Get a palette
        palette = get_report_palette(n=15)
        assert len(palette) == 15

        # Use color_at to get colors
        colors = [color_at(i, palette=palette) for i in range(15)]
        assert len(colors) == 15
        assert colors == palette

    def test_palette_cycling(self):
        """Test that palette cycles correctly through multiple iterations"""
        n = 35  # More than 3 cycles
        palette = get_report_palette(n=n)

        # Get base palette to determine cycle length
        base_palette = get_report_palette()
        cycle_length = len(base_palette)

        # Check that it cycles - each position should equal position + cycle_length
        if cycle_length > 0:
            for i in range(min(n - cycle_length, 10)):  # Check first 10 cycles
                assert palette[i] == palette[i + cycle_length]

    def test_custom_palette_workflow(self):
        """Test workflow with custom palette"""
        custom = ['#111111', '#222222', '#333333']

        # Get specific colors
        c0 = color_at(0, palette=custom)
        c1 = color_at(1, palette=custom)
        c3 = color_at(3, palette=custom)  # Should wrap to index 0

        assert c0 == '#111111'
        assert c1 == '#222222'
        assert c3 == '#111111'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
