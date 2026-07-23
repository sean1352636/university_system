"""
Enhanced Library Management System - GUI Version
Help module with user guide, shortcuts, and about dialogs
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
init_i18n()

from education_system.post_18.university_system.modules.domain.academics.gui.library.base import LibraryGUI


def show_help(self):
    """Show user guide dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.user_guide"))
    dialog.geometry("800x600")
    dialog.transient(self.master)

    # Create notebook for different help sections
    notebook = ttk.Notebook(dialog)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Getting Started tab
    getting_started = ScrolledText(notebook, wrap=tk.WORD, width=80, height=30)
    getting_started.pack(fill=tk.BOTH, expand=True)
    getting_started.insert('1.0', _("library.help.getting_started_content"))
    getting_started.config(state='disabled')
    notebook.add(getting_started, text=_("library.help.getting_started_tab"))

    # Features tab
    features = ScrolledText(notebook, wrap=tk.WORD, width=80, height=30)
    features.pack(fill=tk.BOTH, expand=True)
    features.insert('1.0', _("library.help.features_content"))
    features.config(state='disabled')
    notebook.add(features, text=_("library.help.features_tab"))

    # FAQ tab
    faq = ScrolledText(notebook, wrap=tk.WORD, width=80, height=30)
    faq.pack(fill=tk.BOTH, expand=True)
    faq.insert('1.0', _("library.help.faq_content"))
    faq.config(state='disabled')
    notebook.add(faq, text=_("library.help.faq_tab"))

    # Close button
    ttk.Button(dialog, text=_("common.close"), command=dialog.destroy).pack(pady=10)


def show_shortcuts(self):
    """Show keyboard shortcuts dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.keyboard_shortcuts"))
    dialog.geometry("600x500")
    dialog.transient(self.master)

    ttk.Label(dialog, text=_("library.help.keyboard_shortcuts_title"), font=('Arial', 14, 'bold')).pack(pady=10)

    # Create scrolled text for shortcuts
    shortcuts_text = ScrolledText(dialog, wrap=tk.WORD, width=70, height=25)
    shortcuts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    shortcuts_text.insert('1.0', _("library.help.shortcuts_content"))
    shortcuts_text.config(state='disabled')

    # Close button
    ttk.Button(dialog, text=_("common.close"), command=dialog.destroy).pack(pady=10)


def show_about(self):
    """Show about dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.about"))
    dialog.geometry("500x600")
    dialog.transient(self.master)

    # Logo/Title
    title_frame = ttk.Frame(dialog)
    title_frame.pack(fill=tk.X, pady=20)

    ttk.Label(title_frame, text="📚", font=('Arial', 48)).pack()
    ttk.Label(title_frame, text=_("library.help.about_title"),
             font=('Arial', 14, 'bold')).pack(pady=5)
    ttk.Label(title_frame, text=_("library.help.about_version"), font=('Arial', 10)).pack()

    # Information frame
    info_frame = ttk.Frame(dialog)
    info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    info_text = ScrolledText(info_frame, wrap=tk.WORD, height=20)
    info_text.pack(fill=tk.BOTH, expand=True)

    info_text.insert('1.0', _("library.help.about_content"))
    info_text.config(state='disabled')

    # Buttons
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Button(button_frame, text=_("library.help.view_license"),
              command=lambda: messagebox.showinfo(_("library.help.license_title"), _("library.help.license_text"))).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
