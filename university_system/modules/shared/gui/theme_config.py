"""
Theme Configuration for University Management System GUI
Provides centralized dark/light mode theme management across all GUI modules
"""

import tkinter as tk
from tkinter import ttk


class ThemeManager:
    """Centralized theme manager for consistent styling across all GUI modules"""

    _instance = None
    _dark_mode = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._observers = []

        # Light mode colors
        self.light_theme = {
            'bg': '#f0f0f0',
            'fg': '#000000',
            'select_bg': '#0078d7',
            'select_fg': '#ffffff',
            'button_bg': '#e1e1e1',
            'button_fg': '#000000',
            'entry_bg': '#ffffff',
            'entry_fg': '#000000',
            'frame_bg': '#f0f0f0',
            'label_bg': '#f0f0f0',
            'label_fg': '#000000',
            'treeview_bg': '#ffffff',
            'treeview_fg': '#000000',
            'treeview_selected': '#0078d7',
            'scrollbar_bg': '#e0e0e0',
            'scrollbar_fg': '#606060'
        }

        # Dark mode colors
        self.dark_theme = {
            'bg': '#2b2b2b',
            'fg': '#e0e0e0',
            'select_bg': '#0d47a1',
            'select_fg': '#ffffff',
            'button_bg': '#404040',
            'button_fg': '#e0e0e0',
            'entry_bg': '#3c3c3c',
            'entry_fg': '#e0e0e0',
            'frame_bg': '#2b2b2b',
            'label_bg': '#2b2b2b',
            'label_fg': '#e0e0e0',
            'treeview_bg': '#333333',
            'treeview_fg': '#e0e0e0',
            'treeview_selected': '#0d47a1',
            'scrollbar_bg': '#404040',
            'scrollbar_fg': '#606060'
        }

    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_observer(self, callback):
        """Register a callback to be notified of theme changes"""
        if callback not in self._observers:
            self._observers.append(callback)

    def unregister_observer(self, callback):
        """Unregister a theme change observer"""
        if callback in self._observers:
            self._observers.remove(callback)

    def toggle_dark_mode(self):
        """Toggle between light and dark mode"""
        self._dark_mode = not self._dark_mode
        self._notify_observers()

    def set_dark_mode(self, enabled):
        """Set dark mode on or off"""
        if self._dark_mode != enabled:
            self._dark_mode = enabled
            self._notify_observers()

    def is_dark_mode(self):
        """Check if dark mode is enabled"""
        return self._dark_mode

    def get_current_theme(self):
        """Get the current theme colors"""
        return self.dark_theme if self._dark_mode else self.light_theme

    def _notify_observers(self):
        """Notify all observers of theme change"""
        for callback in self._observers:
            try:
                callback()
            except Exception as e:
                print(f"Error notifying observer: {e}")

    def apply_theme_to_style(self, style):
        """Apply current theme to a ttk.Style object"""
        theme = self.get_current_theme()

        # Configure ttk styles
        style.configure('TFrame', background=theme['frame_bg'])
        style.configure('TLabel', background=theme['label_bg'], foreground=theme['label_fg'])
        style.configure('TButton', background=theme['button_bg'], foreground=theme['button_fg'])
        style.configure('Accent.TButton', background=theme['select_bg'], foreground=theme['select_fg'])
        style.configure('TEntry', fieldbackground=theme['entry_bg'], foreground=theme['entry_fg'])
        style.configure('TLabelFrame', background=theme['frame_bg'], foreground=theme['label_fg'])
        style.configure('TLabelFrame.Label', background=theme['frame_bg'], foreground=theme['label_fg'])
        style.configure('TNotebook', background=theme['frame_bg'])
        style.configure('TNotebook.Tab', background=theme['button_bg'], foreground=theme['button_fg'])
        style.configure('TCombobox', fieldbackground=theme['entry_bg'], foreground=theme['entry_fg'])
        style.configure('TCheckbutton', background=theme['frame_bg'], foreground=theme['label_fg'])
        style.configure('TRadiobutton', background=theme['frame_bg'], foreground=theme['label_fg'])

        # Configure Treeview
        style.configure('Treeview',
                       background=theme['treeview_bg'],
                       foreground=theme['treeview_fg'],
                       fieldbackground=theme['treeview_bg'])
        style.map('Treeview',
                 background=[('selected', theme['treeview_selected'])],
                 foreground=[('selected', theme['select_fg'])])

        # Configure button hover effects
        style.map('TButton',
                 background=[('active', theme['select_bg'])],
                 foreground=[('active', theme['select_fg'])])

        # Configure Scrollbar
        style.configure('TScrollbar', background=theme['scrollbar_bg'])

    def apply_theme_to_window(self, window):
        """Apply current theme to a window and all its children"""
        theme = self.get_current_theme()

        try:
            window.configure(bg=theme['bg'])
        except:
            pass

        self._update_canvas_widgets(window, theme)
        self._update_text_widgets(window, theme)
        self._update_listbox_widgets(window, theme)

    def _update_canvas_widgets(self, widget, theme):
        """Recursively update all Canvas widgets"""
        try:
            for child in widget.winfo_children():
                if isinstance(child, tk.Canvas):
                    child.configure(bg=theme['bg'], highlightbackground=theme['bg'])
                self._update_canvas_widgets(child, theme)
        except:
            pass

    def _update_text_widgets(self, widget, theme):
        """Recursively update all Text widgets"""
        try:
            for child in widget.winfo_children():
                if isinstance(child, tk.Text):
                    child.configure(bg=theme['entry_bg'], fg=theme['entry_fg'],
                                  insertbackground=theme['entry_fg'])
                self._update_text_widgets(child, theme)
        except:
            pass

    def _update_listbox_widgets(self, widget, theme):
        """Recursively update all Listbox widgets"""
        try:
            for child in widget.winfo_children():
                if isinstance(child, tk.Listbox):
                    child.configure(bg=theme['treeview_bg'], fg=theme['treeview_fg'],
                                  selectbackground=theme['treeview_selected'],
                                  selectforeground=theme['select_fg'])
                self._update_listbox_widgets(child, theme)
        except:
            pass


def get_theme_manager():
    """Get the global ThemeManager instance"""
    return ThemeManager.get_instance()
