"""Research grants tab mixin for LayoutManager."""

import tkinter as tk
from tkinter.scrolledtext import ScrolledText

from education_system.university_system.modules.shared.utils.i18n import get_text as _

try:
    from education_system.university_system.modules.domain.research.gui.research_grants_gui import launch_research_grants_gui
    RESEARCH_GRANTS_AVAILABLE = True
except ImportError:
    RESEARCH_GRANTS_AVAILABLE = False
    launch_research_grants_gui = None


class ResearchGrantsMixin:
    """Research grants tab."""

    def create_research_grants_tab(self):
        """Create research & grants management tab"""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['research_grants'] = frame

        # Add title
        title_label = tk.Label(
            frame,
            text=_("finance_gui.research_grants_tab.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            frame,
            text=_("finance_gui.tabs.research_grants.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        if RESEARCH_GRANTS_AVAILABLE and launch_research_grants_gui:
            launch_btn = tk.Button(
                frame,
                text=_("finance_gui.research_grants_tab.open_management"),
                command=lambda: launch_research_grants_gui(self.root, self.gui.auth),
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
                text=_("finance_gui.research_grants_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger']
            )
            error_label.pack(pady=10)

        # Info text
        info_text = ScrolledText(frame, height=15, width=80, font=('Arial', 10), wrap='word')
        info_text.pack(pady=20, padx=20, fill='both', expand=True)

        info_content = _("finance_gui.research_grants_tab.info_content")

        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')
