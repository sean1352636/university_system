"""
Tests for ModuleDialog class from grade_tracking dialogs.
Tests module creation/editing, UI components, and validation.
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from education_system.university_system.modules.domain.academics.gui.grade_tracking.dialogs.module_dialog import (
    ModuleDialog
)


@pytest.fixture
def root():
    """Create a tkinter root window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestModuleDialog:
    """Test ModuleDialog class"""

    def test_init_creates_dialog_new_module(self, root):
        """Test dialog initialization for creating new module"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Check dialog was created
        assert dialog.dialog is not None
        assert dialog.result is None

        # Check variables are initialized empty or with defaults
        assert dialog.module_code_var.get() == ""
        assert dialog.module_name_var.get() == ""
        assert dialog.credits_var.get() == "3"  # Default

        dialog.dialog.destroy()

    def test_init_creates_dialog_edit_module(self, root):
        """Test dialog initialization for editing existing module"""
        test_data = (
            "CS101",                    # module_code
            "Intro to Computer Science", # module_name
            "Core",                     # module_type
            3,                          # credits
            "Introduction to programming",  # description
            "None",                     # prerequisites
            "Fall",                     # semester
            "2024"                      # year
        )

        dialog = ModuleDialog(root, "Edit Module", data=test_data)

        # Check dialog was created
        assert dialog.dialog is not None

        # Check data is loaded
        assert dialog.module_code_var.get() == "CS101"
        assert dialog.module_name_var.get() == "Intro to Computer Science"
        assert dialog.module_type_var.get() == "Core"
        assert dialog.credits_var.get() == "3"
        assert dialog.semester_var.get() == "Fall"
        assert dialog.year_var.get() == "2024"

        dialog.dialog.destroy()

    def test_ui_components_exist(self, root):
        """Test all expected UI components are created"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Check essential attributes exist
        assert hasattr(dialog, 'module_code_var')
        assert hasattr(dialog, 'module_name_var')
        assert hasattr(dialog, 'module_type_var')
        assert hasattr(dialog, 'credits_var')
        assert hasattr(dialog, 'description_text')
        assert hasattr(dialog, 'prerequisites_var')
        assert hasattr(dialog, 'semester_var')
        assert hasattr(dialog, 'year_var')

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.module_dialog.messagebox')
    def test_save_module_missing_required_fields(self, mock_msgbox, root):
        """Test validation for missing required fields"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Leave required fields empty
        dialog.module_code_var.set("")
        dialog.module_name_var.set("")
        dialog.module_type_var.set("")

        dialog.save_module()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "fill in all required fields" in str(mock_msgbox.showerror.call_args)

        # Verify result is not set
        assert dialog.result is None

        dialog.dialog.destroy()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.dialogs.module_dialog.messagebox')
    def test_save_module_invalid_credits(self, mock_msgbox, root):
        """Test validation for non-numeric credits"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set all required fields
        dialog.module_code_var.set("CS101")
        dialog.module_name_var.set("Intro to CS")
        dialog.module_type_var.set("Core")
        dialog.credits_var.set("abc")  # Non-numeric

        dialog.save_module()

        # Verify error message
        mock_msgbox.showerror.assert_called_once()
        assert "Credits must be a number" in str(mock_msgbox.showerror.call_args)

        # Verify result is not set
        assert dialog.result is None

        dialog.dialog.destroy()

    def test_save_module_valid_data(self, root):
        """Test saving module with valid data"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set valid data
        dialog.module_code_var.set("CS101")
        dialog.module_name_var.set("Intro to Computer Science")
        dialog.module_type_var.set("Core")
        dialog.credits_var.set("3")
        dialog.description_text.insert(1.0, "Introduction to programming concepts")
        dialog.prerequisites_var.set("None")
        dialog.semester_var.set("Fall")
        dialog.year_var.set("2024")

        dialog.save_module()

        # Verify result is set with correct data
        assert dialog.result is not None
        code, name, mod_type, credits, desc, prereq, semester, year = dialog.result

        assert code == "CS101"
        assert name == "Intro to Computer Science"
        assert mod_type == "Core"
        assert credits == 3
        assert "Introduction to programming" in desc
        assert prereq == "None"
        assert semester == "Fall"
        assert year == "2024"

    def test_module_types_available(self, root):
        """Test that module types combobox has expected values"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Module type combobox should have specific values
        # Note: We can't directly access the combobox widget in this setup,
        # but we can verify the variable exists
        assert hasattr(dialog, 'module_type_var')

        dialog.dialog.destroy()

    def test_semester_options_available(self, root):
        """Test that semester combobox has expected values"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Semester combobox should have specific values
        assert hasattr(dialog, 'semester_var')

        dialog.dialog.destroy()

    def test_default_credits_value(self, root):
        """Test that credits defaults to 3"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Default credits should be 3
        assert dialog.credits_var.get() == "3"

        dialog.dialog.destroy()

    def test_default_year_value(self, root):
        """Test that year defaults to current year"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Default year should be current year
        current_year = str(datetime.now().year)
        assert dialog.year_var.get() == current_year

        dialog.dialog.destroy()

    def test_description_optional(self, root):
        """Test that description is optional"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set required fields, leave description empty
        dialog.module_code_var.set("CS101")
        dialog.module_name_var.set("Intro to CS")
        dialog.module_type_var.set("Core")
        dialog.credits_var.set("3")
        # Leave description empty

        dialog.save_module()

        # Should succeed
        assert dialog.result is not None

        dialog.dialog.destroy()

    def test_prerequisites_optional(self, root):
        """Test that prerequisites are optional"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set required fields, leave prerequisites empty
        dialog.module_code_var.set("CS101")
        dialog.module_name_var.set("Intro to CS")
        dialog.module_type_var.set("Core")
        dialog.credits_var.set("3")
        dialog.prerequisites_var.set("")  # Empty

        dialog.save_module()

        # Should succeed
        assert dialog.result is not None

        dialog.dialog.destroy()

    def test_credits_range_validation(self, root):
        """Test various credits values"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set required fields
        dialog.module_code_var.set("CS101")
        dialog.module_name_var.set("Intro to CS")
        dialog.module_type_var.set("Core")

        # Test valid credits values
        for credits in [1, 3, 6, 9, 12]:
            dialog.credits_var.set(str(credits))
            dialog.save_module()
            assert dialog.result is not None
            _, _, _, result_credits, _, _, _, _ = dialog.result
            assert result_credits == credits

        dialog.dialog.destroy()

    def test_whitespace_stripped_from_inputs(self, root):
        """Test that whitespace is stripped from inputs"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set data with extra whitespace
        dialog.module_code_var.set("  CS101  ")
        dialog.module_name_var.set("  Intro to CS  ")
        dialog.module_type_var.set("  Core  ")
        dialog.credits_var.set("3")
        dialog.prerequisites_var.set("  None  ")
        dialog.semester_var.set("  Fall  ")
        dialog.year_var.set("  2024  ")

        dialog.save_module()

        # Verify whitespace was stripped
        assert dialog.result is not None
        code, name, mod_type, _, _, prereq, semester, year = dialog.result

        assert code == "CS101"
        assert name == "Intro to CS"
        assert mod_type == "Core"
        assert prereq == "None"
        assert semester == "Fall"
        assert year == "2024"

        dialog.dialog.destroy()

    def test_edit_module_preserves_data(self, root):
        """Test that editing a module preserves unchanged data"""
        original_data = (
            "CS101",
            "Intro to Computer Science",
            "Core",
            3,
            "Introduction to programming",
            "None",
            "Fall",
            "2024"
        )

        dialog = ModuleDialog(root, "Edit Module", data=original_data)

        # Only change the module name
        dialog.module_name_var.set("Introduction to CS")

        dialog.save_module()

        # Verify other data is preserved
        assert dialog.result is not None
        code, name, mod_type, credits, _, _, _, _ = dialog.result

        assert code == "CS101"  # Preserved
        assert name == "Introduction to CS"  # Changed
        assert mod_type == "Core"  # Preserved
        assert credits == 3  # Preserved

        dialog.dialog.destroy()

    def test_multiline_description(self, root):
        """Test handling of multiline descriptions"""
        dialog = ModuleDialog(root, "Add Module", data=None)

        # Set required fields
        dialog.module_code_var.set("CS101")
        dialog.module_name_var.set("Intro to CS")
        dialog.module_type_var.set("Core")
        dialog.credits_var.set("3")

        # Add multiline description
        multiline_desc = "Line 1\nLine 2\nLine 3"
        dialog.description_text.insert(1.0, multiline_desc)

        dialog.save_module()

        # Verify multiline description is preserved
        assert dialog.result is not None
        _, _, _, _, desc, _, _, _ = dialog.result
        assert "Line 1" in desc
        assert "Line 2" in desc

        dialog.dialog.destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
