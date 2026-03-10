"""
Common imports and utilities for Financial Aid & Scholarships GUI

This module provides shared dependencies and utility functions used across
all financial aid GUI components.
"""

# Standard library imports
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import csv
import logging
from typing import Optional, Dict, List, Any, Tuple

# Backend managers
from education_system.university_system.modules.domain.finance.services.financial_aid import (
    FinancialAidManager,
    ScholarshipManager
)

# Database
from education_system.university_system.infrastructure.database.db import get_connection, transaction

# Authentication
from education_system.university_system.infrastructure.shared_context import get_auth

# Activity logging
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Email service
from education_system.university_system.infrastructure.email.email_service import send_email

# i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t, init_i18n
init_i18n()

# Logger
logger = logging.getLogger(__name__)


# Color scheme
COLORS = {
    'primary': '#2c3e50',
    'secondary': '#3498db',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'info': '#16a085',
    'light': '#ecf0f1',
    'dark': '#34495e',
    'white': '#ffffff'
}


# Common widget styles
def configure_styles():
    """Configure ttk styles for consistent appearance"""
    style = ttk.Style()

    # Button styles
    style.configure('Primary.TButton',
                   background=COLORS['primary'],
                   foreground=COLORS['white'],
                   font=('Arial', 10, 'bold'))

    style.configure('Success.TButton',
                   background=COLORS['success'],
                   foreground=COLORS['white'])

    style.configure('Danger.TButton',
                   background=COLORS['danger'],
                   foreground=COLORS['white'])

    # Label styles
    style.configure('Title.TLabel',
                   font=('Arial', 16, 'bold'),
                   foreground=COLORS['primary'])

    style.configure('Heading.TLabel',
                   font=('Arial', 12, 'bold'),
                   foreground=COLORS['dark'])

    style.configure('Info.TLabel',
                   font=('Arial', 10),
                   foreground=COLORS['info'])

    # Frame styles
    style.configure('Card.TFrame',
                   background=COLORS['light'],
                   relief='raised')


def create_scrollable_frame(parent) -> Tuple[ttk.Frame, tk.Canvas, ttk.Scrollbar]:
    """
    Create a scrollable frame with canvas and scrollbar

    Args:
        parent: Parent widget

    Returns:
        Tuple of (scrollable_frame, canvas, scrollbar)
    """
    canvas = tk.Canvas(parent, bg=COLORS['white'])
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    return scrollable_frame, canvas, scrollbar


def create_data_table(parent, columns: List[str], column_widths: Optional[Dict[str, int]] = None) -> ttk.Treeview:
    """
    Create a data table with sorting capability

    Args:
        parent: Parent widget
        columns: List of column names
        column_widths: Optional dict mapping column names to widths

    Returns:
        Treeview widget
    """
    # Create frame for table
    table_frame = ttk.Frame(parent)
    table_frame.pack(fill='both', expand=True, padx=5, pady=5)

    # Create treeview
    tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    # Configure columns
    for col in columns:
        tree.heading(col, text=col)
        width = column_widths.get(col, 100) if column_widths else 100
        tree.column(col, width=width, anchor='w')

    # Add scrollbars
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    # Grid layout
    tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    hsb.grid(row=1, column=0, sticky='ew')

    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)

    return tree


def create_search_filter_bar(parent, on_search_callback, filters: Optional[List[str]] = None) -> Tuple[tk.Entry, ttk.Combobox]:
    """
    Create a search and filter bar

    Args:
        parent: Parent widget
        on_search_callback: Callback function when search is triggered
        filters: Optional list of filter options

    Returns:
        Tuple of (search_entry, filter_combobox)
    """
    filter_frame = ttk.Frame(parent)
    filter_frame.pack(fill='x', padx=5, pady=5)

    # Search box
    ttk.Label(filter_frame, text=_t("financial_aid.common.search")).pack(side='left', padx=(0, 5))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=30)
    search_entry.pack(side='left', padx=(0, 10))

    # Search button
    ttk.Button(filter_frame, text=_t("financial_aid.common.search_btn"), command=on_search_callback).pack(side='left', padx=(0, 20))

    # Filter dropdown
    filter_combo = None
    if filters:
        ttk.Label(filter_frame, text=_t("financial_aid.common.filter")).pack(side='left', padx=(0, 5))
        filter_combo = ttk.Combobox(filter_frame, values=filters, state='readonly', width=20)
        filter_combo.pack(side='left')
        if filters:
            filter_combo.current(0)

    return search_entry, filter_combo


def format_currency(amount: float) -> str:
    """Format amount as currency"""
    return f"${amount:,.2f}"


def format_date(date_obj: Any) -> str:
    """Format date for display"""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, '%Y-%m-%d')
        except (ValueError, TypeError):
            return date_obj

    if isinstance(date_obj, (datetime, date)):
        return date_obj.strftime('%m/%d/%Y')

    return str(date_obj)


def validate_decimal(value: str) -> bool:
    """Validate decimal input"""
    try:
        Decimal(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_date(date_str: str) -> bool:
    """Validate date string - delegates to centralized validator"""
    from education_system.university_system.modules.shared.utils.input_validation import is_valid_date
    return is_valid_date(date_str, formats=['%Y-%m-%d', '%m/%d/%Y'])


def show_error(title: str, message: str):
    """Show error message box"""
    messagebox.showerror(title, message)


def show_success(title: str, message: str):
    """Show success message box"""
    messagebox.showinfo(title, message)


def show_warning(title: str, message: str):
    """Show warning message box"""
    messagebox.showwarning(title, message)


def confirm_action(message: str) -> bool:
    """Show confirmation dialog"""
    return messagebox.askyesno(_t("financial_aid.common.confirm"), message)


def create_stat_card(parent, title: str, value: str, color: str = 'primary') -> ttk.Frame:
    """
    Create a statistics card widget

    Args:
        parent: Parent widget
        title: Card title
        value: Value to display
        color: Color theme

    Returns:
        Frame containing the card
    """
    card = ttk.Frame(parent, style='Card.TFrame', relief='raised', borderwidth=2)

    # Title
    title_label = ttk.Label(card, text=title, font=('Arial', 10))
    title_label.pack(pady=(10, 5))

    # Value
    value_label = ttk.Label(card, text=value, font=('Arial', 18, 'bold'), foreground=COLORS.get(color, COLORS['primary']))
    value_label.pack(pady=(0, 10))

    return card


def export_to_csv(data: List[Dict], filename: str):
    """
    Export data to CSV file

    Args:
        data: List of dictionaries containing data
        filename: Output filename
    """
    if not data:
        show_warning(_t("financial_aid.common.export"), _t("financial_aid.common.no_data_to_export"))
        return

    try:
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=filename
        )

        if filepath:
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

            show_success(_t("financial_aid.common.export"), _t("financial_aid.common.data_exported", filepath=filepath))
            log_activity('export', 'csv', filepath, {'record_count': len(data)})
    except Exception as e:
        logger.error(f"Export error: {e}")
        show_error(_t("financial_aid.common.export_error"), str(e))


def get_current_user():
    """Get currently authenticated user"""
    auth = get_auth()
    if auth and auth.current_user:
        return auth.current_user
    return None


def check_permission(permission: str) -> bool:
    """Check if current user has permission"""
    auth = get_auth()
    if auth and auth.current_user:
        return auth.check_permission(permission)
    return False


def get_student_id() -> Optional[str]:
    """Get student ID of current user"""
    user = get_current_user()
    if user:
        # Try to get dict representation
        if hasattr(user, 'to_dict'):
            user_dict = user.to_dict()
        elif hasattr(user, '__dict__'):
            user_dict = user.__dict__
        elif isinstance(user, dict):
            user_dict = user
        else:
            user_dict = {}

        # Try multiple field names that might contain student ID
        student_id = (user_dict.get('student_id') or
                     user_dict.get('user_id') or
                     user_dict.get('id') or
                     getattr(user, 'student_id', None) or
                     getattr(user, 'user_id', None) or
                     getattr(user, 'id', None))

        return str(student_id) if student_id else None
    return None


def clear_frame(frame):
    """Clear all widgets from frame"""
    try:
        # Check if frame exists and is valid
        if frame and hasattr(frame, 'winfo_exists') and frame.winfo_exists():
            for widget in frame.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass  # Widget already destroyed
    except Exception:
        pass  # Frame already destroyed or invalid


# Academic year utilities
def get_current_academic_year() -> str:
    """Get current academic year string"""
    today = date.today()
    year = today.year
    month = today.month

    # Academic year starts in August
    if month >= 8:
        return f"{year}-{year + 1}"
    else:
        return f"{year - 1}-{year}"


def get_academic_year_list(count: int = 5) -> List[str]:
    """Get list of academic years"""
    current_year = get_current_academic_year()
    start_year = int(current_year.split('-')[0])

    return [f"{start_year + i}-{start_year + i + 1}" for i in range(-2, count)]


# Status color mapping
STATUS_COLORS = {
    'pending': COLORS['warning'],
    'approved': COLORS['success'],
    'denied': COLORS['danger'],
    'awarded': COLORS['success'],
    'disbursed': COLORS['info'],
    'active': COLORS['success'],
    'inactive': COLORS['dark'],
    'completed': COLORS['info'],
    'in_review': COLORS['warning'],
    'cancelled': COLORS['danger']
}


def get_status_color(status: str) -> str:
    """Get color for status"""
    return STATUS_COLORS.get(status.lower(), COLORS['dark'])


# Explicit exports to avoid namespace pollution from wildcard imports
__all__ = [
    # Standard library re-exports
    'tk', 'ttk', 'messagebox', 'filedialog', 'scrolledtext',
    'datetime', 'date', 'timedelta',
    'Decimal',
    'json', 'csv', 'logging',
    'Optional', 'Dict', 'List', 'Any', 'Tuple',
    # Backend managers
    'FinancialAidManager', 'ScholarshipManager',
    # Database
    'get_connection', 'transaction',
    # Authentication
    'get_auth',
    # Logging
    'log_activity', 'logger',
    # Email
    'send_email',
    # i18n
    '_t',
    # Colors and styles
    'COLORS', 'STATUS_COLORS', 'configure_styles',
    # Widget utilities
    'create_scrollable_frame', 'create_data_table', 'create_search_filter_bar',
    'create_stat_card', 'clear_frame',
    # Formatting
    'format_currency', 'format_date',
    # Validation
    'validate_decimal', 'validate_date',
    # Dialogs
    'show_error', 'show_success', 'show_warning', 'confirm_action',
    # Export
    'export_to_csv',
    # User utilities
    'get_current_user', 'check_permission', 'get_student_id',
    # Academic year utilities
    'get_current_academic_year', 'get_academic_year_list',
    # Status utilities
    'get_status_color',
]
