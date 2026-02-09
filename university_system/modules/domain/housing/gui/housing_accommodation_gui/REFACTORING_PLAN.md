# Housing Accommodation GUI Refactoring Plan

## Original File
- **Path**: `university_system/modules/domain/housing/gui/housing_accommodation_gui.py`
- **Size**: 8,110 lines
- **Main Class**: `HousingGUI` with 100+ methods
- **Inner Classes**: `HousingFinanceManager` (lines 7300-8062)

## Target Structure (18 Files)

### 1. ✅ `__init__.py` - Backward compatibility exports
### 2. ✅ `email_notifications.py` (Lines 116-356)
- `send_housing_email()`
- `send_maintenance_email()`

### 3. ✅ `utils.py` - Shared utility functions
- Date/currency formatting
- Validation helpers
- Safe type conversions

### 4. `main_gui.py` (Lines 358-430, orchestration)
- `HousingGUI` class __init__
- `create_main_interface()`
- `create_menu_buttons()`
- `clear_content()`
- Delegates to all manager modules

### 5. `dashboard_manager.py` (Lines 522-598)
- `show_dashboard()`
- Dashboard statistics and overview

### 6. `building_manager.py` (Lines 599-1500)
- `show_building_management()`
- `create_buildings_list()`
- `refresh_buildings_list()`
- `create_add_building_form()`
- `add_building()`
- `edit_selected_building()`
- `show_edit_building_dialog()`
- `delete_selected_building()`
- `manage_selected_building_rooms()`
- `show_building_rooms_management()`

### 7. `room_manager.py` (Lines 961-1236)
- `show_room_management()`
- `create_rooms_interface()`
- `add_single_room()`
- `create_rooms_list_view()`
- `refresh_rooms_list()`
- `show_batch_room_creation()`

### 8. `application_manager.py` (Lines 2980-3534)
- `show_applications()`
- `create_applications_list()`
- `refresh_applications_list()`
- `view_application_details()`
- `show_application_details_dialog()`
- `process_selected_application()`
- `show_process_application_dialog()`
- `create_new_application_form()`
- `load_buildings_combo()`
- `search_student()`
- `submit_application()`

### 9. `assignment_manager.py` (Lines 3535-3844)
- `show_assignments()`
- `refresh_assignments_list()`
- `view_assignment_details()`
- `show_assignment_details_dialog()`
- `update_assignment_status()`
- `load_active_assignments()`

### 10. `maintenance_manager.py` (Lines 1697-2266)
- `show_maintenance()`
- `create_maintenance_list()`
- `refresh_maintenance_list()`
- `view_maintenance_details()`
- `show_maintenance_details_dialog()`
- `update_maintenance_request()`
- `show_update_maintenance_dialog()`
- `create_maintenance_form()`
- `load_buildings_for_maintenance()`
- `load_rooms_for_maintenance()`
- `submit_maintenance_request()`

### 11. `payment_manager.py` (Lines 2267-2934)
- `show_payments()`
- `create_payments_refunds_tab()`
- `_refresh_refund_payments_list()`
- `view_housing_payment_details()`
- `export_housing_payments_csv()`
- `create_payment_history()`
- `refresh_payment_history()`
- `show_all_payments()`
- `create_payment_form()`
- `record_payment()`

### 12. `refund_manager.py` (Lines 2465-2754)
- `process_housing_refund()`
- `_show_housing_refund_method_dialog()`
- `_get_student_account_balance()`
- `_add_to_student_account()`
- `_notify_finance_for_housing_refund()`
- `_send_housing_refund_receipt()`

### 13. `inventory_manager.py` (Lines 4089-4284)
- `show_inventory()`
- Room inventory viewing and management
- Status change functions

### 14. `inspection_manager.py` (Lines 4286-5076)
- `show_inspections()`
- `schedule_inspection_dialog()`
- `send_inspection_emails()`
- `send_post_inspection_email()`
- `record_inspection_dialog()`
- `view_inspection_details()`
- `load_inspections()`
- `edit_inspection()`
- `delete_inspection()`

### 15. `report_manager.py` (Lines 5077-5660)
- `show_reports()`
- `open_report_window()`
- `export_report_as_txt()`
- `export_report_as_csv()`
- `export_report_as_pdf()`
- `send_report_to_admin()`
- `show_occupancy_report()`
- `show_financial_summary()`
- `show_maintenance_summary_gui()`
- `show_room_availability()`
- `show_export_options()`
- `export_data_gui()`

### 16. `scheduled_reports.py` (Lines 5798-6500)
- `show_scheduled_reports_manager()`
- `load_scheduled_reports()`
- `add_scheduled_report()`
- `edit_scheduled_report()`
- `delete_scheduled_report()`
- `run_scheduled_report_now()`
- Report generation content methods
- `show_report_template_settings()`

### 17. `student_portal.py` (Student-facing methods)
- `show_student_dashboard()`
- `show_student_application()`
- `show_student_assignment()`
- `show_student_maintenance()`
- Student view methods

### 18. `finance_integration.py` (Lines 7300-8062)
- `HousingFinanceManager` class (complete inner class)
- `open_finance_gui()`
- Finance integration methods

### 19. `export_manager.py` (Export-related functions)
- Data export utilities
- CSV/PDF/TXT export functions

## Implementation Strategy

1. ✅ Create directory structure
2. ✅ Extract independent modules first (email, utils)
3. ✅ Create __init__.py for imports
4. Create all manager modules (extracting methods from HousingGUI)
5. Create main_gui.py that:
   - Imports all managers
   - HousingGUI class delegates to manager functions
   - Maintains GUI state
6. Backup original file
7. Replace with redirect import
8. Test all functionality

## Key Dependencies

- All managers need:
  - `tkinter` imports
  - Database connections (`get_connection`, `transaction`)
  - Authentication (`get_auth`)
  - Activity logging
  - Email service (conditional)

- Main GUI needs:
  - All manager imports
  - State management (self.root, self.auth, self.content_frame, etc.)
  - Widget references for callbacks

## Notes

- Maintain backward compatibility through __init__.py
- Each manager should be self-contained with its imports
- Functions should accept necessary state as parameters
- GUI state (widgets, variables) managed in main_gui.py
