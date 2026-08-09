"""Optional university runtime plugins (disabled by default)."""

from .registry import discover_plugins, register_enabled_plugin_routes

__all__ = ["discover_plugins", "register_enabled_plugin_routes"]
