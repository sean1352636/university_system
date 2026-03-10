"""Payments tab mixin for LayoutManager."""


class PaymentsMixin:
    """Payments tab (delegates to transaction manager)."""

    def create_payments_tab(self):
        """Create payments tab"""
        try:
            if hasattr(self.gui, 'transactions') and hasattr(self.gui.transactions, 'create_payments_tab'):
                self.gui.transactions.create_payments_tab()
            else:
                self._create_placeholder_tab('payments', '\U0001f4b3 Payments')
        except Exception as e:
            print(f"Error creating payments tab: {e}")
            self._create_placeholder_tab('payments', '\U0001f4b3 Payments')
