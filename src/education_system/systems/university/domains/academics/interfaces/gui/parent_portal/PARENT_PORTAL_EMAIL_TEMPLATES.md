# Parent Portal Email Templates Migration

## Summary

Migrated hardcoded email templates from Parent Portal GUI files to centralized JSON template files.

## Date
2026-01-29

## Files Modified

### New Template Files Created

All templates are located in: `university_system/templates/email/parent_portal/`

1. **parent_absence_notification.json**
   - **Purpose**: Notification sent to admin when parent/guardian reports student absence
   - **Used by**: `attendance.py`
   - **Variables**: student_name, student_id, absence_date, reason, sessions_text, reporter_name, reporter_email, report_datetime

2. **meal_account_topup.json**
   - **Purpose**: Notification sent to student when meal account is topped up
   - **Used by**: `meal.py`
   - **Variables**: student_name, amount, new_balance, topup_datetime

3. **parent_issue_report.json**
   - **Purpose**: Notification sent to admin when parent reports an issue
   - **Used by**: `meetings.py`
   - **Variables**: issue_id, parent_name, parent_id, category, priority, subject, description

4. **transportation_request.json**
   - **Purpose**: Notification sent to admin for new transportation requests
   - **Used by**: `transport.py`
   - **Variables**: student_name, student_id, service_type, route_preference, special_needs, start_date, sender_name, request_datetime

### Python Files Updated

1. **attendance.py**
   - Function: `_send_absence_notification_to_admin()`
   - Line ~247-314
   - Now uses template: `parent_portal/parent_absence_notification`

2. **meal.py**
   - Function: `check_meal_balance()` (nested send notification)
   - Line ~298-333
   - Now uses template: `parent_portal/meal_account_topup`

3. **meetings.py**
   - Function: `show_report_issue_interface()` (nested submit_issue)
   - Line ~284-313
   - Now uses template: `parent_portal/parent_issue_report`

4. **transport.py**
   - Function: `request_transportation()` (nested submit_request)
   - Line ~422-452
   - Now uses template: `parent_portal/transportation_request`

## Implementation Details

### Template Rendering Approach

All updated functions now follow this pattern:

```python
from university_system.infrastructure.email.template_utils import render_template

subject, body = render_template('parent_portal/template_name', {
    'variable1': value1,
    'variable2': value2,
    # ... more variables
})

# Fallback if template not found
if not subject or not body:
    subject = "Fallback Subject"
    body = "Fallback body content"

send_email(recipient, subject, body)
```

### Variable Syntax

Templates use Python `string.Template` syntax with `$variable` notation:
- `$variable` - Basic substitution
- `${variable}` - Braced form when needed

### Backward Compatibility

All functions include fallback email content if templates cannot be loaded, ensuring the system continues to function even if template files are missing.

## Benefits

1. **Centralized Management**: Email templates can be edited without modifying Python code
2. **Consistency**: All parent portal emails now use the same template infrastructure
3. **Maintainability**: Easier to update email content, especially for translations
4. **Flexibility**: Templates can be customized per deployment
5. **Auditability**: Template changes are tracked separately from code changes

## Testing Recommendations

1. Test absence reporting functionality
2. Test meal account top-up notifications
3. Test parent issue reporting
4. Test transportation request submissions
5. Verify emails are sent with correct variable substitution
6. Test fallback behavior when templates are missing

## Notes

- **messages.py** was reviewed but contains no standalone email templates (emails are built inline and dynamically)
- All templates follow the existing pattern used in other parts of the system
- Templates include proper documentation and variable lists
