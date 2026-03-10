"""
Integration Marketplace GUI Package

Comprehensive GUI for browsing, installing, and managing third-party integrations.
Includes integration catalog, installation management, credential management,
sync logs, data mappings, webhooks, and usage analytics. Full authentication,
error handling, and email notifications.
"""

from .main import IntegrationMarketplaceGUI
from .launcher import launch_integration_marketplace_gui

__all__ = ['IntegrationMarketplaceGUI', 'launch_integration_marketplace_gui']
