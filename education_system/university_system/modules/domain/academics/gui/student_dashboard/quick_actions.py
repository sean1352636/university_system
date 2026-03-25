"""
Quick Actions Mixin for Student Dashboard

Provides a grid of shortcut buttons that navigate the student to
commonly used features such as grades, timetable, module registration,
exams, library, and financial aid.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.academics.gui.student_dashboard.common_imports import COLORS, _t


class QuickActionsMixin:
    """Mixin that adds quick-action buttons to the student dashboard."""

    def create_quick_actions(self, parent):
        """
        Build a grid of quick-action buttons for common student tasks.

        Args:
            parent: Parent frame to pack widgets into
        """
        actions_frame = ttk.LabelFrame(
            parent,
            text=_t('dashboard.quick_actions', 'Quick Actions'),
        )
        actions_frame.pack(fill='x', padx=20, pady=(10, 20))

        button_grid = ttk.Frame(actions_frame)
        button_grid.pack(fill='x', padx=15, pady=15)
        for col in range(3):
            button_grid.columnconfigure(col, weight=1)

        actions = [
            (_t('dashboard.view_grades', 'View Grades'), 'grades', COLORS['info']),
            (_t('dashboard.timetable', 'My Timetable'), 'timetable', COLORS['primary']),
            (_t('dashboard.register_modules', 'Register for Modules'), 'register', COLORS['success']),
            (_t('dashboard.view_exams', 'View Exams'), 'exams', COLORS['warning']),
            (_t('dashboard.library', 'Library'), 'library', COLORS['secondary']),
            (_t('dashboard.financial_aid', 'Financial Aid'), 'financial_aid', COLORS['danger']),
        ]

        for idx, (label, action_key, color) in enumerate(actions):
            row, col = divmod(idx, 3)
            btn = tk.Button(
                button_grid,
                text=label,
                font=('Arial', 11, 'bold'),
                fg=COLORS['white'],
                bg=color,
                activebackground=color,
                activeforeground=COLORS['white'],
                relief='flat',
                cursor='hand2',
                width=20,
                height=2,
                command=lambda k=action_key: self._handle_action(k),
            )
            btn.grid(row=row, column=col, padx=8, pady=8, sticky='nsew')

    def _handle_action(self, action_key: str):
        """
        Route a quick-action button press to the appropriate GUI feature.

        Args:
            action_key: Identifier for the action to perform
        """
        action_map = {
            'grades': ('show_grades', _t('dashboard.view_grades', 'View Grades')),
            'timetable': ('show_student_timetable_gui', _t('dashboard.timetable', 'My Timetable')),
            'register': ('show_student_registration_gui', _t('dashboard.register_modules', 'Register for Modules')),
            'exams': ('show_exam_scheduler_gui', _t('dashboard.view_exams', 'View Exams')),
            'library': ('show_library_management', _t('dashboard.library', 'Library')),
            'financial_aid': ('show_financial_aid', _t('dashboard.financial_aid', 'Financial Aid')),
        }

        method_name, display_name = action_map.get(action_key, (None, action_key))

        if self.main_gui and method_name and hasattr(self.main_gui, method_name):
            getattr(self.main_gui, method_name)()
        else:
            messagebox.showinfo(
                _t('dashboard.info', 'Information'),
                _t(
                    'dashboard.feature_unavailable',
                    f'{display_name} is not available in the current session.',
                ),
            )
