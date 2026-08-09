"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def load_available_modules(self):
    """Load available modules into the listbox"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()
        # Join with modules table to get proper module names
        cursor.execute("""
            SELECT DISTINCT sm.module_code,
                   COALESCE(m.module_name, sm.module_name, sm.module_code) as module_name
            FROM student_modules sm
            LEFT JOIN modules m ON sm.module_code = m.module_code
            ORDER BY module_name
        """)
        self.available_modules = cursor.fetchall()
        conn.close()

        self.module_listbox.delete(0, tk.END)
        for code, name in self.available_modules:
            display_name = name or code
            self.module_listbox.insert(tk.END, f"{code} - {display_name}")

    except Exception as e:
        messagebox.showerror(_t('common.error'), _t('advanced_search.search_advanced.could_not_load_modules', error=str(e)))
