"""Bank app tab mixin for LayoutManager."""

import tkinter as tk
from tkinter import messagebox

from education_system.university_system.modules.shared.utils.i18n import get_text as _

try:
    from education_system.university_system.modules.domain.finance.gui.bank_app import BankApp
    BANK_APP_AVAILABLE = True
except ImportError:
    BANK_APP_AVAILABLE = False
    BankApp = None


class BankAppMixin:
    """Bank application launcher tab."""

    def create_bank_app_tab(self):
        """Create bank application tab with launch button"""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['bank_app'] = frame

        # Add title
        title_label = tk.Label(
            frame,
            text=_("finance_gui.bank_app_tab.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            frame,
            text=_("finance_gui.bank_app_tab.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        if BANK_APP_AVAILABLE and BankApp:
            launch_btn = tk.Button(
                frame,
                text=_("finance_gui.bank_app_tab.open_bank_app"),
                command=self._launch_bank_app,
                font=('Arial', 12, 'bold'),
                bg=self.colors['success'],
                fg='white',
                padx=30,
                pady=15
            )
            launch_btn.pack(pady=10)
        else:
            error_label = tk.Label(
                frame,
                text=_("finance_gui.bank_app_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger']
            )
            error_label.pack(pady=20)

    def _launch_bank_app(self):
        """Launch the Bank App GUI in a new window"""
        try:
            window = tk.Toplevel(self.root)
            window.title(_("finance_gui.bank_app_tab.window_title"))
            window.geometry("900x700")
            window.minsize(800, 600)
            try:
                window.transient(self.root)
            except Exception:
                pass
            BankApp(window, auth=self.gui.auth)
            print("Bank App opened successfully from Finance GUI")
        except Exception as e:
            messagebox.showerror(
                _("common.error"),
                _("finance_gui.bank_app_tab.failed_to_open", error=str(e))
            )
            print(f"Bank App error: {e}")
