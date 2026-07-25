"""Revenue source tab mixin for LayoutManager."""


class RevenueMixin:
    """Revenue source tab (delegates to revenue source manager)."""

    def create_revenue_source_tab(self):
        """Create revenue by source tab"""
        try:
            # Delegate to revenue source manager if available
            if hasattr(self.gui, 'revenue_source') and hasattr(self.gui.revenue_source, 'create_revenue_source_tab'):
                self.gui.revenue_source.create_revenue_source_tab()
            else:
                self._create_placeholder_tab('revenue_source', '\U0001f4b5 Revenue by Source')
        except Exception as e:
            print(f"Error creating revenue source tab: {e}")
            self._create_placeholder_tab('revenue_source', '\U0001f4b5 Revenue by Source')
