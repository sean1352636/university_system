from .. import *  # shared compatibility dependencies

class DataTableMixin:
        def _clear_treatment_filters(self):
            """Clear all treatment filters."""
            self.treatment_filter_var.set("All")
            self.payment_filter_var.set("All")
            self._refresh_treatments_list()
