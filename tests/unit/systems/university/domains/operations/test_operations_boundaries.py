"""Import-boundary tests for the Operations vertical slice.

The last of the eleven university domains. The rules live in
``tests/unit/systems/university/domains/conftest.py``; this module supplies only
what Operations currently violates. The allow-list is a ratchet, so it can only
shrink.

159 entries across 802 modules — 19.8 per cent. One cluster is almost the whole
story: 118 modules import Finance's integration module, because every commercial
outlet (barber, betting, butcher, cafe, car rental, cinema, gym, marketplace,
music shop, nail bar, phone shop, restaurant, textbooks) takes payment by calling
Finance directly.

Together with Pastoral's 56 and the Academics cluster, "post to Finance by
import" is the single largest structural debt this migration surfaced, and one
published charge-raised event would retire the lot.
"""

from __future__ import annotations

SLICE = "operations"

_UNI = "education_system.systems.university"
_FIN = f"{_UNI}.domains.finance"
_ACAD = f"{_UNI}.domains.academics"

#: Every commercial outlet posts payments through Finance's integration module.
_FINANCE_INTEGRATION = f"{_FIN}.infrastructure.finance_integration"

_FINANCE_INTEGRATION_CALLERS = {
    "domain/campus/housing/services/housing_accommodation/common.py",
    "domain/commerce/bakery_shop/domain/loyalty.py",
    "domain/commerce/bakery_shop/services/checkout.py",
    "domain/commerce/bakery_shop/tabs_main/tab_refunds.py",
    "domain/commerce/cafe/__init__.py",
    "domain/commerce/cafe/integrations/finance.py",
    "domain/commerce/services/grocery/grocery_service.py",
    "domain/commerce/services/restaurant/operations/order_processing.py",
    "domain/commerce/services/shop_management/shopping.py",
    "domain/commerce/services/takeaway/takeaway_service.py",
    "interfaces/gui/campus/community/church_management/services/payments.py",
    "interfaces/gui/campus/equipment/equipment_gui.py",
    "interfaces/gui/campus/mobility/parking_management/dialogs/payment_dialog.py",
    "interfaces/gui/campus/mobility/parking_management/dialogs/refund_dialog.py",
    "interfaces/gui/campus/mobility/taxi_booking_gui_parts/taxibookingapp_process_taxi_refund.py",
    "interfaces/gui/campus/mobility/taxi_booking_gui_shared.py",
    "interfaces/gui/campus/mobility/train_station_gui_parts/trainstationapp_add_train_refund_to_student_acco.py",
    "interfaces/gui/campus/mobility/train_station_gui_shared.py",
    "interfaces/gui/campus/printing/printing_gui.py",
    "interfaces/gui/commerce/bar_gui.py",
    "interfaces/gui/commerce/barber/common.py",
    "interfaces/gui/commerce/betting/services/payments.py",
    "interfaces/gui/commerce/cafe_common.py",
    "interfaces/gui/commerce/cafe_pos.py",
    "interfaces/gui/commerce/cafe_system_gui.py",
    "interfaces/gui/commerce/carrental/carrental_gui_parts/carrentalgui_complete_carrental_refund.py",
    "interfaces/gui/commerce/carrental/carrental_gui_shared.py",
    "interfaces/gui/commerce/cinema/cinema_gui/booking/payment.py",
    "interfaces/gui/commerce/cinema/cinema_gui/core/main_gui.py",
    "interfaces/gui/commerce/cinema/cinema_gui/reports/refunds.py",
    "interfaces/gui/commerce/grocery_gui.py",
    "interfaces/gui/commerce/musicshop/musicshop_gui_parts/musicshopgui_create_refunds_tab.py",
    "interfaces/gui/commerce/musicshop/musicshop_gui_shared.py",
    "interfaces/gui/commerce/nailbar/nailbar_gui_parts/nailbargui_process_nailbar_refund.py",
    "interfaces/gui/commerce/nailbar/nailbar_gui_shared.py",
    "interfaces/gui/commerce/phoneshop/phoneshop_gui.py",
    "interfaces/gui/commerce/restaurant_management_gui/core/main_gui.py",
    "interfaces/gui/commerce/restaurant_management_gui/core/tabs.py",
    "interfaces/gui/commerce/restaurant_management_gui/customers/customer_management.py",
    "interfaces/gui/commerce/restaurant_management_gui/customers/feedback.py",
    "interfaces/gui/commerce/restaurant_management_gui/customers/loyalty.py",
    "interfaces/gui/commerce/restaurant_management_gui/inventory/inventory_management.py",
    "interfaces/gui/commerce/restaurant_management_gui/inventory/inventory_reports.py",
    "interfaces/gui/commerce/restaurant_management_gui/inventory/purchase_orders.py",
    "interfaces/gui/commerce/restaurant_management_gui/menu/menu_management.py",
    "interfaces/gui/commerce/restaurant_management_gui/misc.py",
    "interfaces/gui/commerce/restaurant_management_gui/orders/order_management.py",
    "interfaces/gui/commerce/restaurant_management_gui/orders/payments.py",
    "interfaces/gui/commerce/restaurant_management_gui/orders/place_order.py",
    "interfaces/gui/commerce/restaurant_management_gui/reports/financial_reports.py",
    "interfaces/gui/commerce/restaurant_management_gui/reports/sales_reports.py",
    "interfaces/gui/commerce/restaurant_management_gui/reports/waste_reports.py",
    "interfaces/gui/commerce/restaurant_management_gui/settings/backup_settings.py",
    "interfaces/gui/commerce/restaurant_management_gui/staff/performance.py",
    "interfaces/gui/commerce/restaurant_management_gui/staff/staff_management.py",
    "interfaces/gui/commerce/restaurant_management_gui/tables/qr_codes.py",
    "interfaces/gui/commerce/restaurant_management_gui/tables/table_management.py",
    "interfaces/gui/commerce/shop_management_gui/auth_manager.py",
    "interfaces/gui/commerce/shop_management_gui/bulk_operations.py",
    "interfaces/gui/commerce/shop_management_gui/cart_manager.py",
    "interfaces/gui/commerce/shop_management_gui/checkout_manager.py",
    "interfaces/gui/commerce/shop_management_gui/dashboard_manager.py",
    "interfaces/gui/commerce/shop_management_gui/discount_manager.py",
    "interfaces/gui/commerce/shop_management_gui/email_notifications.py",
    "interfaces/gui/commerce/shop_management_gui/finance_integration.py",
    "interfaces/gui/commerce/shop_management_gui/inventory_manager.py",
    "interfaces/gui/commerce/shop_management_gui/main_gui.py",
    "interfaces/gui/commerce/shop_management_gui/order_manager.py",
    "interfaces/gui/commerce/shop_management_gui/product_browser.py",
    "interfaces/gui/commerce/shop_management_gui/product_manager.py",
    "interfaces/gui/commerce/shop_management_gui/refund_manager.py",
    "interfaces/gui/commerce/shop_management_gui/report_manager.py",
    "interfaces/gui/commerce/shop_management_gui/ui_components.py",
    "interfaces/gui/commerce/shop_management_gui/utils.py",
    "interfaces/gui/commerce/takeaway_gui.py",
}

#: Tk applications sitting in the domain layer.
_TKINTER_IN_DOMAIN = {
    "domain/campus/mobility/services/parking_launcher.py",
    "domain/campus/services/campus_events_gui.py",
    "domain/commerce/bakery_shop/_common.py",
    "domain/commerce/bakery_shop/tabs_advanced/tab_production.py",
    "domain/commerce/barber/barber_portals.py",
    "domain/commerce/cinema/cinema_portals.py",
    "domain/commerce/services/commerce_portals.py",
    "domain/communications/feedback/complaints_portal.py",
    "domain/reporting/institutional_analytics/institutional_analytics_app.py",
    "domain/reporting/kpi_dashboard/kpi_dashboard_app.py",
}

#: Direct SQL driver use in the domain layer.
_SQLITE_IN_DOMAIN = {
    "domain/campus/housing/services/housing_accommodation/extended_cli.py",
    "domain/campus/housing/services/housing_accommodation/extras.py",
    "domain/campus/housing/services/housing_accommodation/waitlist.py",
    "domain/campus/room_booking/services/room_booking_service.py",
    "domain/commerce/bakery_shop/_common.py",
    "domain/communications/feedback/complaints_portal.py",
    "domain/reporting/institutional_analytics/services/institutional_analytics_service.py",
    "domain/reporting/kpi_dashboard/services/kpi_dashboard_service.py",
}

KNOWN_VIOLATIONS: set[tuple[str, str]] = (
    {(p, _FINANCE_INTEGRATION) for p in _FINANCE_INTEGRATION_CALLERS}
    | {(p, "tkinter") for p in _TKINTER_IN_DOMAIN}
    | {(p, "sqlite3") for p in _SQLITE_IN_DOMAIN}
    | {
        # Everything else: other Finance reaches, Academics, this slice's own
        # adapters, tkinter submodules, and two singletons.
        #
        # The bakery entry is a *dangling* import, not merely a boundary
        # crossing: `university.domain.helpdesk` has never existed — the helpdesk
        # service has always lived under pastoral/services/helpdesk (now
        # domains/pastoral/domain/services/helpdesk), and it is substantial. The
        # import sits in a try/except, so the bakery's "raise a helpdesk ticket"
        # path silently does nothing. Repointing the path is not sufficient
        # either: that package exposes create_ticket_enhanced(auth) and
        # create_ticket_from_template(auth, template_id), not the create_ticket()
        # this calls. Wiring it up needs a decision about what the bakery passes
        # for `auth`, so it is recorded here rather than guessed at.
        ("domain/campus/accessibility/__init__.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.accessibility.accessibility_cli"),
        ("domain/campus/campus_navigation/__init__.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.campus_navigation.navigation_cli"),
        ("domain/campus/equipment/services/equipment_core.py",
         f"{_FIN}.domain.ledger"),
        ("domain/campus/facilities/services/facilities_management_core.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.facilities.facilities_cli"),
        ("domain/campus/facilities/services/facilities_management_core.py",
         f"{_UNI}.domains.operations.interfaces.gui.campus.facilities.building_management_app"),
        ("domain/campus/housing/services/housing_accommodation/deposits.py",
         f"{_FIN}.domain.ledger"),
        ("domain/campus/housing/services/housing_accommodation/deposits.py",
         f"{_FIN}.domain.ledger.hooks"),
        ("domain/campus/housing/services/housing_accommodation/payments.py",
         f"{_FIN}.domain.ledger"),
        ("domain/campus/lost_found/__init__.py",
         f"{_UNI}.domains.operations.interfaces.cli.campus.lost_found.lost_found_cli"),
        ("domain/campus/mobility/services/parking_launcher.py",
         f"{_UNI}.domains.operations.interfaces.gui.campus.mobility.parking_management_gui"),
        ("domain/campus/mobility/services/parking_launcher.py",
         "tkinter.ttk"),
        ("domain/campus/mobility/services/trip_management/_common.py",
         f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
        ("domain/campus/mobility/services/trip_management/_common.py",
         f"{_ACAD}.domain.services.academic_calendar.config"),
        ("domain/commerce/bakery_shop/services/feedback_kitchen.py",
         f"{_UNI}.domain.helpdesk"),
        ("domain/commerce/bakery_shop/tabs_advanced/tab_pos.py",
         f"{_UNI}.domains.operations.interfaces.gui.commerce.bakery_shop.pos"),
        ("domain/commerce/barber/services/barber_core.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("domain/commerce/barber/services/barber_core.py",
         f"{_FIN}.domain.ledger"),
        ("domain/commerce/barber/services/barber_core.py",
         f"{_UNI}.domains.operations.interfaces.gui.commerce.barber.barber_gui"),
        ("domain/commerce/butcher/services/butcher_core.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("domain/commerce/butcher/services/butcher_core.py",
         f"{_UNI}.domains.operations.interfaces.gui.commerce.butcher.butcher_gui"),
        ("domain/commerce/carrental/services/carrental_core.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("domain/commerce/cinema/__init__.py",
         f"{_UNI}.domains.operations.interfaces.cli.commerce.cinema"),
        ("domain/commerce/cinema/cinema_portals.py",
         "tkinter.simpledialog"),
        ("domain/commerce/cinema/services/cinema_service.py",
         f"{_UNI}.domains.operations.interfaces.gui.commerce.cinema.cinema_gui.constants"),
        ("domain/commerce/cinema/services/cinema_service.py",
         f"{_UNI}.domains.operations.interfaces.gui.commerce.cinema.cinema_gui.database"),
        ("domain/commerce/nailbar/services/nailbar_core.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("domain/commerce/nailbar/services/nailbar_core.py",
         f"{_UNI}.domains.operations.interfaces.gui.commerce.nailbar.nailbar_gui"),
        ("domain/commerce/services/commerce_portals.py",
         "tkinter.simpledialog"),
        ("domain/commerce/services/shop_management/menus.py",
         f"{_UNI}.interfaces.cli.shell.database_manager"),
        ("domain/reporting/external_qa_kpis.py",
         f"{_ACAD}.domain.research.external_quality_assurance.services"),
        ("interfaces/cli/commerce/nailbar/nailbar_cli.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/finance_integration.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/finance_integration.py",
         f"{_FIN}.interfaces.gui.finance.finance_gui"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/payment_manager.py",
         f"{_FIN}.domain.core.account_management"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/payment_manager.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/payment_manager.py",
         f"{_FIN}.interfaces.gui.finance.finance_gui"),
        ("interfaces/gui/campus/housing/housing_accommodation_gui/refund_manager.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/mobility/parking_management/tabs/payments.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/mobility/taxi_booking_gui_parts/taxibookingapp_process_taxi_refund.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/mobility/train_station_gui_parts/trainstationapp_add_train_refund_to_student_acco.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/mobility/train_station_gui_parts/trainstationapp_show_refunds.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/campus/mobility/trip_management_gui/_imports.py",
         f"{_ACAD}.domain.services.academic_calendar.calendar_core"),
        ("interfaces/gui/campus/mobility/trip_management_gui/_imports.py",
         f"{_ACAD}.domain.services.academic_calendar.config"),
        ("interfaces/gui/commerce/bar_gui.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("interfaces/gui/commerce/betting/services/payments.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("interfaces/gui/commerce/betting/shared.py",
         f"{_FIN}.domain.core.finance_db_operations"),
        ("interfaces/gui/commerce/butcher/butcher_gui_parts/butchergui_init.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("interfaces/gui/commerce/butcher/butcher_gui_parts/butchergui_process_butcher_refund.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/cafe_refunds.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/carrental/carrental_gui_parts/carrentalgui_complete_carrental_refund.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/cinema/cinema_gui/reports/refunds.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/grocery_gui.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/gym/gym_gui.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("interfaces/gui/commerce/gym/gym_gui.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/musicshop/musicshop_gui_parts/musicshopgui_create_refunds_tab.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/nailbar/nailbar_gui_parts/nailbargui_process_nailbar_refund.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/phoneshop/phoneshop_gui.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/restaurant_management_gui/orders/payments.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("interfaces/gui/commerce/restaurant_management_gui/orders/payments.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/restaurant_management_gui/orders/payments.py",
         f"{_FIN}.interfaces.gui.finance"),
        ("interfaces/gui/commerce/restaurant_management_gui/orders/refunds.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/shop_management_gui/checkout_manager.py",
         f"{_FIN}.domain.core.unified_payments"),
        ("interfaces/gui/commerce/shop_management_gui/checkout_manager.py",
         f"{_FIN}.interfaces.gui.finance"),
        ("interfaces/gui/commerce/shop_management_gui/refund_manager.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/commerce/takeaway_gui.py",
         f"{_FIN}.domain.ledger"),
        ("interfaces/gui/communications/mail/mail_post_gui.py",
         f"{_FIN}.domain.core.finance_db_operations"),
    }
)


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)


def test_legacy_domain_tree_is_empty() -> None:
    """All eleven domains have migrated: domain/ holds no modules."""
    from pathlib import Path

    legacy = (
        Path(__file__).resolve().parents[6]
        / "src/education_system/systems/university/domain"
    )
    leftover = sorted(p.name for p in legacy.rglob("*.py") if p.name != "__init__.py")
    assert not leftover, f"modules still in the legacy domain/ tree: {leftover}"
