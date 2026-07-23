"""
Integration Marketplace GUI Package

Comprehensive GUI for browsing, installing, and managing third-party integrations.
Includes integration catalog, installation management, credential management,
sync logs, data mappings, webhooks, and usage analytics. Full authentication,
error handling, and email notifications.
"""

from education_system.post_18.university_system.modules.services.gui.integration_marketplace_gui.main import IntegrationMarketplaceGUI
from education_system.post_18.university_system.modules.services.gui.integration_marketplace_gui.launcher import launch_integration_marketplace_gui

__all__ = ['IntegrationMarketplaceGUI', 'launch_integration_marketplace_gui']
