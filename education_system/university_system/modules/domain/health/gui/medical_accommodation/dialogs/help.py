# dialogs/help.py
# Dialog for help / user guide.

from .._common import tk, ttk, ScrolledText


class HelpDialog:
    """Dialog for help information"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("User Guide")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        help_text = ScrolledText(main_frame, width=70, height=25)
        help_text.pack(fill=tk.BOTH, expand=True)

        help_content = """
STUDENT ACCOMMODATION MANAGEMENT SYSTEM - USER GUIDE
===================================================

OVERVIEW
--------
This application helps manage student accommodations with features for:
- Adding and updating accommodation records
- Template management for common accommodations
- Search and filtering capabilities
- Approval workflow for pending accommodations
- Import/export functionality
- Dashboard and reporting

MAIN FEATURES
-------------

1. ACCOMMODATIONS TAB
   - View all accommodation records
   - Add new accommodations
   - Update existing records
   - Remove accommodations
   - Approve/reject pending requests

2. SEARCH & FILTER TAB
   - Search by student ID, type, status
   - Filter by date ranges
   - Keyword search in descriptions

3. DASHBOARD TAB
   - Key metrics and statistics
   - Visual charts and breakdowns
   - Quick overview of system status

4. TEMPLATES TAB
   - Create reusable templates
   - Apply templates to students
   - Manage existing templates

MENU OPTIONS
------------

File Menu:
- Import from CSV/JSON files
- Export to various formats (CSV, Excel, PDF, JSON)

Accommodations Menu:
- Add new accommodations
- Update/remove selected records
- Approval management

Templates Menu:
- Save and apply templates
- Template management

Reports Menu:
- Dashboard metrics
- Statistics reports
- Expiry notifications

Tools Menu:
- CLI mode (command-line interface)
- Database information
- Application settings

KEYBOARD SHORTCUTS
------------------
- Double-click on record: View details
- F5: Refresh data
- Ctrl+N: New accommodation
- Ctrl+E: Edit selected
- Delete: Remove selected

TROUBLESHOOTING
---------------
- If data doesn't load, check database connection
- For import errors, verify file format
- CLI mode provides additional debugging options

For technical support, contact your system administrator.
"""

        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
