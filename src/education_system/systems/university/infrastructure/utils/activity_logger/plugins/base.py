from typing import Dict, List, Any

from education_system.systems.university.infrastructure.utils.activity_logger.models import LogEntry


class LoggerPlugin:
    """Base class for logger plugins"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)

    def before_log(self, log_entry: LogEntry) -> LogEntry:
        """Called before logging - can modify log entry"""
        if not self.enabled:
            return log_entry
        return log_entry

    def after_log(self, log_entry: LogEntry, success: bool):
        """Called after logging attempt"""
        if not self.enabled:
            return

    def on_shutdown(self):
        """
        Called during logger shutdown

        Override this method in subclasses to perform cleanup operations such as:
        - Flushing pending messages
        - Closing database connections
        - Releasing file handles
        - Cleaning up temporary resources
        - Sending final notifications
        """
        # Base implementation does nothing - subclasses should override
        # to implement their specific cleanup logic
        if self.enabled:
            # Subclasses can add their cleanup logic here
            pass

    def get_status(self) -> Dict[str, Any]:
        """Get plugin status information"""
        return {
            'name': self.__class__.__name__,
            'enabled': self.enabled,
            'config': self.config
        }


class PluginManager:
    """Manage logger plugins"""

    def __init__(self):
        self.plugins: List[LoggerPlugin] = []

    def register_plugin(self, plugin: LoggerPlugin):
        """Register a new plugin"""
        self.plugins.append(plugin)
        print(f"Registered plugin: {plugin.__class__.__name__}")

    def unregister_plugin(self, plugin_class: str):
        """Unregister a plugin by class name"""
        self.plugins = [p for p in self.plugins if p.__class__.__name__ != plugin_class]

    def before_log(self, log_entry: LogEntry) -> LogEntry:
        """Apply all plugins' before_log methods"""
        for plugin in self.plugins:
            try:
                log_entry = plugin.before_log(log_entry)
            except Exception as e:
                print(f"Plugin {plugin.__class__.__name__} before_log error: {e}")
        return log_entry

    def after_log(self, log_entry: LogEntry, success: bool):
        """Apply all plugins' after_log methods"""
        for plugin in self.plugins:
            try:
                plugin.after_log(log_entry, success)
            except Exception as e:
                print(f"Plugin {plugin.__class__.__name__} after_log error: {e}")

    def shutdown_plugins(self):
        """Shutdown all plugins"""
        for plugin in self.plugins:
            try:
                plugin.on_shutdown()
            except Exception as e:
                print(f"Plugin {plugin.__class__.__name__} shutdown error: {e}")

    def get_plugin_status(self) -> List[Dict[str, Any]]:
        """Get status of all plugins"""
        return [plugin.get_status() for plugin in self.plugins]
