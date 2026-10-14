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
        # 1400x900 does not fit a 1366x768 display; center() clamps it to
        # the screen and positions it, instead of leaving the window
        # oversized and pinned to a corner.
        try:
            from education_system.platform.delivery.gui.window_sizing import center
            center(finance_window, 1400, 900, minsize=(1100, 650))
        except Exception:
            finance_window.geometry("1400x900")
        finance_window.transient(self.master)

        # The close bar is packed BEFORE the manager fills the window.
        # LibraryFinanceManager.__init__ packs its content frame with
        # fill='both', expand=True, so a bar added afterwards was given
        # whatever height was left — nothing, once the window was clamped
        # to the screen — and the Close button was invisible.
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

        # Create and initialize the LibraryFinanceManager
        library_finance_manager = LibraryFinanceManager(finance_window, self.auth)

    except Exception as e:
        messagebox.showerror(
            _t('gui.academics.library.finance_parts.open_library_finance.dialogs.error', default="Error"),
            f"Failed to open Library Finance:\n{str(e)}\n\nFalling back to basic fine management."
        )
        import traceback
        traceback.print_exc()
        # Fall back to basic fine management
        self.show_fine_management()
