"""Style setup mixin for LayoutManager."""

from tkinter import ttk


class StylesMixin:
    """GUI styles and fonts."""

    def setup_styles(self):
        """Set up GUI styles and fonts"""
        self.style = ttk.Style()

        # Define finance-specific custom styles (namespaced to avoid
        # overriding the main GUI's global styles such as Large.TButton)
        self.style.configure('Finance.Title.TLabel', font=('Arial', 16, 'bold'))
        self.style.configure('Finance.Heading.TLabel', font=('Arial', 12, 'bold'))
        self.style.configure('Finance.Large.TButton', font=('Arial', 10, 'bold'), padding=10)

        # Color schemes
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8'  # ADD this line
        }
