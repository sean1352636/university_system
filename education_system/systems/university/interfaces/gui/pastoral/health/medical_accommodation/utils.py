# utils.py
# Utility functions, helpers, and constants for the medical accommodation GUI.

from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation._common import (
    tk, messagebox, datetime, timedelta, json, logging, os, sqlite3,
    CLI_AVAILABLE, get_connection, get_current_user, logger,
)

# Configuration and constants for GUI
GUI_CONFIG = {
    'window_title': 'Student Accommodation Management System',
    'window_size': '1200x800',
    'min_window_size': '800x600',
    'theme': 'default',
    'auto_refresh_interval': 30000,  # milliseconds
    'max_recent_files': 10,
    'default_export_format': 'csv',
    'date_format': '%Y-%m-%d',
    'datetime_format': '%Y-%m-%d %H:%M:%S'
}

# Version and compatibility information
GUI_VERSION = "1.0.0"
REQUIRED_CLI_VERSION = "1.0.0"
COMPATIBLE_PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9", "3.10", "3.11"]


def resolve_user_identifier(default: str = 'gui_user', auth_instance=None) -> str:
    """Return a string-safe identifier for the current user.

    Args:
        default: Default value if no user is found
        auth_instance: Optional auth instance to get user from

    Returns:
        String identifier for the current user
    """
    # Try to get user from auth instance first
    if auth_instance and hasattr(auth_instance, 'current_user'):
        user = auth_instance.current_user
        if user and isinstance(user, dict):
            for key in ('username', 'email', 'name', 'id'):
                value = user.get(key)
                if value:
                    return str(value)

    # Fall back to get_current_user() from auth module
    if CLI_AVAILABLE:
        try:
            user = get_current_user()
            if user is None:
                return 'system'

            if isinstance(user, dict):
                for key in ('username', 'email', 'name', 'id'):
                    value = user.get(key)
                    if value:
                        return str(value)
                return json.dumps(user, default=str)

            return str(user)
        except Exception as e:
            logger.debug(f"Failed to resolve user identifier: {e}")

    return default


def check_conflict(student_id, accommodation_type, start_date, end_date, excluded_id=None):
    """Check for conflicting accommodations"""
    if not CLI_AVAILABLE:
        return False

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            query = '''
                SELECT COUNT(*) FROM accommodations
                WHERE student_id = ? AND accommodation_type = ?
                AND status = 'active'
            '''
            params = [student_id, accommodation_type]

            if start_date and end_date:
                query += '''
                    AND ((start_date <= ? AND end_date >= ?)
                         OR (start_date <= ? AND end_date >= ?)
                         OR (start_date >= ? AND end_date <= ?))
                '''
                params.extend([start_date, start_date, end_date, end_date, start_date, end_date])

            if excluded_id:
                query += ' AND id != ?'
                params.append(excluded_id)

            cursor.execute(query, params)
            return cursor.fetchone()[0] > 0

    except Exception as e:
        print(f"Conflict check error: {e}")
        return False


def validate_gui_input(value, input_type):
    """Validate GUI input based on type"""
    if input_type == 'student_id':
        if CLI_AVAILABLE:
            from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation._common import validate_student_id
            return value.strip() != '' and validate_student_id(value.strip())
        return value.strip() != ''
    elif input_type == 'date':
        if not value.strip():
            return True  # Empty dates are allowed
        try:
            datetime.fromisoformat(value.strip())
            return True
        except ValueError:
            return False
    elif input_type == 'integer':
        try:
            int(value)
            return True
        except ValueError:
            return False
    return True


def create_tooltip(widget, text):
    """Create a tooltip for a widget"""
    def on_enter(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

        label = tk.Label(tooltip, text=text, background="lightyellow",
                        relief="solid", borderwidth=1, font=("Arial", 8))
        label.pack()

        widget.tooltip = tooltip

    def on_leave(event):
        if hasattr(widget, 'tooltip'):
            widget.tooltip.destroy()
            del widget.tooltip

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def format_date_display(date_str):
    """Format date for display"""
    if not date_str:
        return 'N/A'
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return date_str


def get_status_color(status):
    """Get color for status display"""
    colors = {
        'active': 'green',
        'pending': 'orange',
        'suspended': 'red',
        'expired': 'gray',
        'rejected': 'darkred'
    }
    return colors.get(status, 'black')


def gui_error_handler(func):
    """Decorator for GUI error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"GUI Error in {func.__name__}: {e}")
            if CLI_AVAILABLE:
                logging.error(f"GUI Error in {func.__name__}: {e}")
            # Show error dialog if tkinter is available
            try:
                messagebox.showerror("Error", f"An error occurred: {str(e)}")
            except Exception:
                print(f"Error: {e}")
    return wrapper
