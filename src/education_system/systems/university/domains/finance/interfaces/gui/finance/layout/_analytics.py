"""Analytics tab mixin for LayoutManager."""


class AnalyticsMixin:
    """Analytics tab (delegates to analytics manager)."""

    def create_analytics_tab(self):
        """Create analytics tab"""
        try:
            if hasattr(self.gui, 'analytics') and hasattr(self.gui.analytics, 'create_analytics_tab'):
                self.gui.analytics.create_analytics_tab()
            else:
                self._create_placeholder_tab('analytics', '\U0001f4ca Analytics')
        except Exception as e:
            print(f"Error creating analytics tab: {e}")
            self._create_placeholder_tab('analytics', '\U0001f4ca Analytics')
