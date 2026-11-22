"""Finance dashboard (CLI): headline figures over bursaries and their
attendance holds, free meals, trips and refunds, fees and tuition
invoices, receipts and expenses, and department budgets.

Reached from the Fees menu, and as a top-level entry via
``dispatch("Finance Dashboard")``.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domains.finance.domain.finance_hub import (
    finance_hub,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)

logger = logging.getLogger(__name__)

LABEL = "Finance Dashboard"


@ui.handler
def show_dashboard() -> None:
    year = ui.ask("Academic year (blank = current)") or None
    print()
    print(finance_hub.dashboard(year).as_text())


def dispatch(label: str) -> bool:
    if label != LABEL:
        return False
    try:
        show_dashboard()
    except Exception as exc:  # noqa: BLE001 - never crash the main menu
        logger.exception("Finance dashboard crashed")
        print(f"\n  ✗ Unexpected error: {exc}")
    return True
