"""Compatibility façade for the split implementation."""

from . import menus_shared as _shared
from .menus_shared import *  # noqa: F401,F403

from .menus_parts import display_enhanced_scheduling_menu as _part_1
display_enhanced_scheduling_menu = _part_1.display_enhanced_scheduling_menu
_shared.display_enhanced_scheduling_menu = display_enhanced_scheduling_menu
_shared.__all__.append("display_enhanced_scheduling_menu") if "display_enhanced_scheduling_menu" not in _shared.__all__ else None

from .menus_parts import display_analytics_menu as _part_2
display_analytics_menu = _part_2.display_analytics_menu
_shared.display_analytics_menu = display_analytics_menu
_shared.__all__.append("display_analytics_menu") if "display_analytics_menu" not in _shared.__all__ else None

from .menus_parts import display_workload_menu as _part_3
display_workload_menu = _part_3.display_workload_menu
_shared.display_workload_menu = display_workload_menu
_shared.__all__.append("display_workload_menu") if "display_workload_menu" not in _shared.__all__ else None

from .menus_parts import display_visual_timetable_menu as _part_4
display_visual_timetable_menu = _part_4.display_visual_timetable_menu
_shared.display_visual_timetable_menu = display_visual_timetable_menu
_shared.__all__.append("display_visual_timetable_menu") if "display_visual_timetable_menu" not in _shared.__all__ else None

from .menus_parts import display_smart_scheduling_menu as _part_5
display_smart_scheduling_menu = _part_5.display_smart_scheduling_menu
_shared.display_smart_scheduling_menu = display_smart_scheduling_menu
_shared.__all__.append("display_smart_scheduling_menu") if "display_smart_scheduling_menu" not in _shared.__all__ else None

from .menus_parts import display_batch_import_menu as _part_6
display_batch_import_menu = _part_6.display_batch_import_menu
_shared.display_batch_import_menu = display_batch_import_menu
_shared.__all__.append("display_batch_import_menu") if "display_batch_import_menu" not in _shared.__all__ else None

from .menus_parts import display_template_menu as _part_7
display_template_menu = _part_7.display_template_menu
_shared.display_template_menu = display_template_menu
_shared.__all__.append("display_template_menu") if "display_template_menu" not in _shared.__all__ else None

from .menus_parts import display_advanced_search_menu as _part_8
display_advanced_search_menu = _part_8.display_advanced_search_menu
_shared.display_advanced_search_menu = display_advanced_search_menu
_shared.__all__.append("display_advanced_search_menu") if "display_advanced_search_menu" not in _shared.__all__ else None

from .menus_parts import display_free_rooms_menu as _part_9
display_free_rooms_menu = _part_9.display_free_rooms_menu
_shared.display_free_rooms_menu = display_free_rooms_menu
_shared.__all__.append("display_free_rooms_menu") if "display_free_rooms_menu" not in _shared.__all__ else None

from .menus_parts import display_schedule_gaps_menu as _part_10
display_schedule_gaps_menu = _part_10.display_schedule_gaps_menu
_shared.display_schedule_gaps_menu = display_schedule_gaps_menu
_shared.__all__.append("display_schedule_gaps_menu") if "display_schedule_gaps_menu" not in _shared.__all__ else None

from .menus_parts import display_conflict_management_menu as _part_11
display_conflict_management_menu = _part_11.display_conflict_management_menu
_shared.display_conflict_management_menu = display_conflict_management_menu
_shared.__all__.append("display_conflict_management_menu") if "display_conflict_management_menu" not in _shared.__all__ else None

from .menus_parts import display_ical_export_menu as _part_12
display_ical_export_menu = _part_12.display_ical_export_menu
_shared.display_ical_export_menu = display_ical_export_menu
_shared.__all__.append("display_ical_export_menu") if "display_ical_export_menu" not in _shared.__all__ else None

from .menus_parts import display_pdf_reports_menu as _part_13
display_pdf_reports_menu = _part_13.display_pdf_reports_menu
_shared.display_pdf_reports_menu = display_pdf_reports_menu
_shared.__all__.append("display_pdf_reports_menu") if "display_pdf_reports_menu" not in _shared.__all__ else None

from .menus_parts import display_backup_menu as _part_14
display_backup_menu = _part_14.display_backup_menu
_shared.display_backup_menu = display_backup_menu
_shared.__all__.append("display_backup_menu") if "display_backup_menu" not in _shared.__all__ else None

from .menus_parts import display_restore_menu as _part_15
display_restore_menu = _part_15.display_restore_menu
_shared.display_restore_menu = display_restore_menu
_shared.__all__.append("display_restore_menu") if "display_restore_menu" not in _shared.__all__ else None

from .menus_parts import display_data_validation_menu as _part_16
display_data_validation_menu = _part_16.display_data_validation_menu
_shared.display_data_validation_menu = display_data_validation_menu
_shared.__all__.append("display_data_validation_menu") if "display_data_validation_menu" not in _shared.__all__ else None

from .menus_parts import display_system_settings_menu as _part_17
display_system_settings_menu = _part_17.display_system_settings_menu
_shared.display_system_settings_menu = display_system_settings_menu
_shared.__all__.append("display_system_settings_menu") if "display_system_settings_menu" not in _shared.__all__ else None

from .menus_parts import display_notifications_menu as _part_18
display_notifications_menu = _part_18.display_notifications_menu
_shared.display_notifications_menu = display_notifications_menu
_shared.__all__.append("display_notifications_menu") if "display_notifications_menu" not in _shared.__all__ else None

from .menus_parts import display_holiday_management_menu as _part_19
display_holiday_management_menu = _part_19.display_holiday_management_menu
_shared.display_holiday_management_menu = display_holiday_management_menu
_shared.__all__.append("display_holiday_management_menu") if "display_holiday_management_menu" not in _shared.__all__ else None

from .menus_parts import display_room_menu as _part_20
display_room_menu = _part_20.display_room_menu
_shared.display_room_menu = display_room_menu
_shared.__all__.append("display_room_menu") if "display_room_menu" not in _shared.__all__ else None

from .menus_parts import display_instructor_menu as _part_21
display_instructor_menu = _part_21.display_instructor_menu
_shared.display_instructor_menu = display_instructor_menu
_shared.__all__.append("display_instructor_menu") if "display_instructor_menu" not in _shared.__all__ else None

from .menus_parts import display_schedule_menu as _part_22
display_schedule_menu = _part_22.display_schedule_menu
_shared.display_schedule_menu = display_schedule_menu
_shared.__all__.append("display_schedule_menu") if "display_schedule_menu" not in _shared.__all__ else None

from .menus_parts import display_student_timetable_menu as _part_23
display_student_timetable_menu = _part_23.display_student_timetable_menu
_shared.display_student_timetable_menu = display_student_timetable_menu
_shared.__all__.append("display_student_timetable_menu") if "display_student_timetable_menu" not in _shared.__all__ else None

from .menus_parts import display_instructor_timetable_menu as _part_24
display_instructor_timetable_menu = _part_24.display_instructor_timetable_menu
_shared.display_instructor_timetable_menu = display_instructor_timetable_menu
_shared.__all__.append("display_instructor_timetable_menu") if "display_instructor_timetable_menu" not in _shared.__all__ else None

from .menus_parts import open_file_prompt as _part_25
open_file_prompt = _part_25.open_file_prompt
_shared.open_file_prompt = open_file_prompt
_shared.__all__.append("open_file_prompt") if "open_file_prompt" not in _shared.__all__ else None

from .menus_parts import display_module_scheduling_menu as _part_26
display_module_scheduling_menu = _part_26.display_module_scheduling_menu
_shared.display_module_scheduling_menu = display_module_scheduling_menu
_shared.__all__.append("display_module_scheduling_menu") if "display_module_scheduling_menu" not in _shared.__all__ else None

from .menus_parts import display_view_schedules_menu as _part_27
display_view_schedules_menu = _part_27.display_view_schedules_menu
_shared.display_view_schedules_menu = display_view_schedules_menu
_shared.__all__.append("display_view_schedules_menu") if "display_view_schedules_menu" not in _shared.__all__ else None

from .menus_parts import display_timetable_generation_menu as _part_28
display_timetable_generation_menu = _part_28.display_timetable_generation_menu
_shared.display_timetable_generation_menu = display_timetable_generation_menu
_shared.__all__.append("display_timetable_generation_menu") if "display_timetable_generation_menu" not in _shared.__all__ else None

from .menus_parts import display_department_schedule as _part_29
display_department_schedule = _part_29.display_department_schedule
_shared.display_department_schedule = display_department_schedule
_shared.__all__.append("display_department_schedule") if "display_department_schedule" not in _shared.__all__ else None

from .menus_parts import display_export_menu as _part_30
display_export_menu = _part_30.display_export_menu
_shared.display_export_menu = display_export_menu
_shared.__all__.append("display_export_menu") if "display_export_menu" not in _shared.__all__ else None

from .menus_parts import display_main_menu_info as _part_31
display_main_menu_info = _part_31.display_main_menu_info
_shared.display_main_menu_info = display_main_menu_info
_shared.__all__.append("display_main_menu_info") if "display_main_menu_info" not in _shared.__all__ else None

from .menus_parts import handle_graceful_exit as _part_32
handle_graceful_exit = _part_32.handle_graceful_exit
_shared.handle_graceful_exit = handle_graceful_exit
_shared.__all__.append("handle_graceful_exit") if "handle_graceful_exit" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['display_advanced_search_menu', 'display_analytics_menu', 'display_backup_menu', 'display_batch_import_menu', 'display_conflict_management_menu', 'display_data_validation_menu', 'display_department_schedule', 'display_enhanced_scheduling_menu', 'display_export_menu', 'display_free_rooms_menu', 'display_holiday_management_menu', 'display_ical_export_menu', 'display_instructor_menu', 'display_instructor_timetable_menu', 'display_main_menu_info', 'display_module_scheduling_menu', 'display_notifications_menu', 'display_pdf_reports_menu', 'display_restore_menu', 'display_room_menu', 'display_schedule_gaps_menu', 'display_schedule_menu', 'display_smart_scheduling_menu', 'display_student_timetable_menu', 'display_system_settings_menu', 'display_template_menu', 'display_timetable_generation_menu', 'display_view_schedules_menu', 'display_visual_timetable_menu', 'display_workload_menu', 'handle_graceful_exit', 'open_file_prompt']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32]:
    _module.__dict__.update(_exports)

display_timetable_optimizer_menu = display_enhanced_scheduling_menu


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['display_advanced_search_menu', 'display_analytics_menu', 'display_backup_menu', 'display_batch_import_menu', 'display_conflict_management_menu', 'display_data_validation_menu', 'display_department_schedule', 'display_enhanced_scheduling_menu', 'display_export_menu', 'display_free_rooms_menu', 'display_holiday_management_menu', 'display_ical_export_menu', 'display_instructor_menu', 'display_instructor_timetable_menu', 'display_main_menu_info', 'display_module_scheduling_menu', 'display_notifications_menu', 'display_pdf_reports_menu', 'display_restore_menu', 'display_room_menu', 'display_schedule_gaps_menu', 'display_schedule_menu', 'display_smart_scheduling_menu', 'display_student_timetable_menu', 'display_system_settings_menu', 'display_template_menu', 'display_timetable_generation_menu', 'display_view_schedules_menu', 'display_visual_timetable_menu', 'display_workload_menu', 'handle_graceful_exit', 'open_file_prompt']
