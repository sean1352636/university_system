"""Settings tab mixin for LayoutManager."""


class SettingsMixin:
    """Settings tab (delegates to settings manager)."""

    def create_settings_tab(self):
        """Create settings tab"""
        try:
            if hasattr(self.gui, 'settings') and hasattr(self.gui.settings, 'create_settings_tab'):
                self.gui.settings.create_settings_tab()
            else:
                self._create_placeholder_tab('settings', '\u2699\ufe0f Settings')
        except Exception as e:
            print(f"Error creating settings tab: {e}")
            self._create_placeholder_tab('settings', '\u2699\ufe0f Settings')
