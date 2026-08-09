"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def open_library_finance(self):
    """Open the Library Finance management window directly in Library GUI"""
    if not self.check_permission('manage_loans'):
        return

    try:
        # Create new window for Library Finance
        finance_window = tk.Toplevel(self.master)
        finance_window.title(_t('gui.academics.library.finance_parts.open_library_finance.windows.library_finance_management', default="Library Finance Management"))
        finance_window.geometry("1400x900")
        finance_window.transient(self.master)

        # Create and initialize the LibraryFinanceManager
        library_finance_manager = LibraryFinanceManager(finance_window, self.auth)

        # Add close button at the bottom
        close_frame = tk.Frame(finance_window, bg='white')
        close_frame.pack(fill='x', side='bottom', pady=10)
        tk.Button(
            close_frame,
            text=_("common.close"),
            command=finance_window.destroy,
            bg='#3498db',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=30,
            pady=8
        ).pack()

    except Exception as e:
        messagebox.showerror(
            _t('gui.academics.library.finance_parts.open_library_finance.dialogs.error', default="Error"),
            f"Failed to open Library Finance:\n{str(e)}\n\nFalling back to basic fine management."
        )
        import traceback
        traceback.print_exc()
        # Fall back to basic fine management
        self.show_fine_management()
