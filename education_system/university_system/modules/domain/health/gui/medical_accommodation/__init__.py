# medical_accommodation/__init__.py
# Package re-exports for backward compatibility.

from education_system.university_system.modules.domain.health.gui.medical_accommodation.main_gui import AccommodationGUI
from education_system.university_system.modules.domain.health.gui.medical_accommodation.cli_integration import main, integrate_with_original_cli, export_gui_data_to_cli_format
from education_system.university_system.modules.domain.health.gui.medical_accommodation.utils import (
    resolve_user_identifier,
    check_conflict,
    validate_gui_input,
    create_tooltip,
    format_date_display,
    get_status_color,
    gui_error_handler,
    GUI_CONFIG,
    GUI_VERSION,
)

__all__ = [
    'AccommodationGUI',
    'main',
    'integrate_with_original_cli',
    'export_gui_data_to_cli_format',
    'resolve_user_identifier',
    'check_conflict',
    'validate_gui_input',
    'create_tooltip',
    'format_date_display',
    'get_status_color',
    'gui_error_handler',
    'GUI_CONFIG',
    'GUI_VERSION',
]
