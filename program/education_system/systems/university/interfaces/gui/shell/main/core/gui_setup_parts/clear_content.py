"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def clear_content(self):
    """Clear the content area"""
    # Check if content_frame exists before trying to clear it
    if hasattr(self, 'content_frame') and self.content_frame:
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        # Clearing the content area always destroys the workspace
        # notebook (it lives inside content_frame). Drop the
        # references so ``open_in_workspace`` doesn't try to add tabs
        # to a destroyed widget.
        self.workspace_notebook = None
        if hasattr(self, 'workspace_tabs') and self.workspace_tabs is not None:
            self.workspace_tabs.clear()
    else:
        # If content_frame doesn't exist yet, just return
        return
