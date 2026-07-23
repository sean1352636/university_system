"""Bank app tab mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk

from education_system.post_18.university_system.core.i18n import get_text as _

try:
    from education_system.post_18.university_system.modules.domain.finance.gui.bank_app import BankApp
    BANK_APP_AVAILABLE = True
except ImportError:
    BANK_APP_AVAILABLE = False
    BankApp = None


class BankAppMixin:
    """Bank application tab — embeds the Bank App inline."""

    def create_bank_app_tab(self):
        """Create bank application tab; embed lazily on first show."""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['bank_app'] = frame
        self._bank_app_instance = None

        if not (BANK_APP_AVAILABLE and BankApp):
            tk.Label(
                frame,
                text=_("finance_gui.bank_app_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger'],
            ).pack(pady=20)
            return

        frame.bind('<Map>', self._on_bank_app_tab_shown, add='+')

    def _on_bank_app_tab_shown(self, _event):
        if getattr(self, '_bank_app_instance', None) is not None:
            return
        frame = self.tab_frames.get('bank_app')
        if frame is None:
            return
        try:
            host = ttk.Frame(frame)
            host.pack(fill='both', expand=True)
            auth = getattr(self.gui, 'auth', None) or getattr(self, 'auth', None)
            self._bank_app_instance = BankApp(parent=host, auth=auth)
        except Exception as e:
            tk.Label(
                frame,
                text=_("finance_gui.bank_app_tab.failed_to_open", error=str(e)),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger'],
                justify='left',
            ).pack(padx=20, pady=20, anchor='nw')
