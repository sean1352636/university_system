"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def setup_keyboard_shortcuts(root, app):
    """Setup keyboard shortcuts"""
    # General shortcuts
    root.bind('<Control-n>', lambda e: app.show_add_book())
    root.bind('<Control-f>', lambda e: app.show_search_books())
    root.bind('<F5>', lambda e: app.refresh_books_table() if hasattr(app, 'books_tree') else None)
    root.bind('<Control-s>', lambda e: None)  # Save shortcut (context dependent)
    root.bind('<Escape>', lambda e: None)  # Cancel shortcut (context dependent)

    # Navigation shortcuts
    root.bind('<Control-Key-1>', lambda e: app.show_dashboard())
    root.bind('<Control-Key-2>', lambda e: app.show_all_books())
    root.bind('<Control-Key-3>', lambda e: app.show_search_books())
    root.bind('<Control-Key-4>', lambda e: app.show_reports())
    root.bind('<Control-Key-5>', lambda e: app.show_settings())

    # System shortcuts
    root.bind('<Control-b>', lambda e: app.backup_system_gui())
    root.bind('<Control-r>', lambda e: app.show_reports())
