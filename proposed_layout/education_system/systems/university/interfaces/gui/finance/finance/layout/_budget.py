"""Budget tab mixin for LayoutManager."""


class BudgetMixin:
    """Budget tab (delegates to budget manager)."""

    def create_budget_tab(self):
        """Create budget tab"""
        try:
            if hasattr(self.gui, 'budgets') and hasattr(self.gui.budgets, 'create_budget_tab'):
                self.gui.budgets.create_budget_tab()
            else:
                self._create_placeholder_tab('budget', '\U0001f4bc Budget')
        except Exception as e:
            print(f"Error creating budget tab: {e}")
            self._create_placeholder_tab('budget', '\U0001f4bc Budget')
