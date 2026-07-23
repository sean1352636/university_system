"""Research grants tab mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk

from education_system.post_18.university_system.core.i18n import get_text as _

try:
    from education_system.post_18.university_system.modules.domain.academics.research.gui.research_grants_gui import ResearchGrantsGUI
    RESEARCH_GRANTS_AVAILABLE = True
except ImportError:
    RESEARCH_GRANTS_AVAILABLE = False
    ResearchGrantsGUI = None


class ResearchGrantsMixin:
    """Research & Grants tab — embeds the Research & Grants GUI inline."""

    def create_research_grants_tab(self):
        """Create research & grants tab; embed lazily on first show."""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['research_grants'] = frame
        self._research_grants_instance = None

        if not (RESEARCH_GRANTS_AVAILABLE and ResearchGrantsGUI):
            tk.Label(
                frame,
                text=_("finance_gui.research_grants_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger'],
            ).pack(pady=10)
            return

        frame.bind('<Map>', self._on_research_grants_tab_shown, add='+')

    def _on_research_grants_tab_shown(self, _event):
        if getattr(self, '_research_grants_instance', None) is not None:
            return
        frame = self.tab_frames.get('research_grants')
        if frame is None:
            return
        try:
            host = ttk.Frame(frame)
            host.pack(fill='both', expand=True)
            auth = getattr(self.gui, 'auth', None) or getattr(self, 'auth', None)
            self._research_grants_instance = ResearchGrantsGUI(
                self.root, auth, parent_container=host,
            )
        except Exception as e:
            tk.Label(
                frame,
                text=str(e),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger'],
                justify='left',
            ).pack(padx=20, pady=20, anchor='nw')
