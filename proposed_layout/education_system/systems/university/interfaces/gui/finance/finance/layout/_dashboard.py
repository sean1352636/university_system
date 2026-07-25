"""Dashboard tab mixin for LayoutManager."""


class DashboardMixin:
    """Dashboard tab."""

    def create_dashboard_tab(self):
        """Create dashboard tab"""
        try:
            # Try to delegate to dashboard manager if it has the method
            if hasattr(self.gui, 'dashboard') and hasattr(self.gui.dashboard, 'create_dashboard_tab'):
                self.gui.dashboard.create_dashboard_tab()
            else:
                self._create_placeholder_tab('dashboard', '\U0001f4ca Dashboard')
        except Exception as e:
            print(f"Error creating dashboard tab: {e}")
            self._create_placeholder_tab('dashboard', '\U0001f4ca Dashboard')
