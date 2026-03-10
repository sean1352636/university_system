"""Entry point for launching the Integration Marketplace GUI."""

from __future__ import annotations

import tkinter as tk
import logging
import traceback

logger = logging.getLogger(__name__)


def launch_integration_marketplace_gui(auth=None, parent=None):
    """Launch the Integration Marketplace GUI as a child window"""
    from .main import IntegrationMarketplaceGUI

    try:
        if parent:
            # Pass parent directly - IntegrationMarketplaceGUI creates its own Toplevel
            app = IntegrationMarketplaceGUI(parent, auth_system=auth)
        else:
            # Create as standalone root window if no parent (for testing)
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            app = IntegrationMarketplaceGUI(root, auth_system=auth)
            root.mainloop()
    except Exception as e:
        logger.error(f"Error launching Integration Marketplace GUI: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    launch_integration_marketplace_gui()
