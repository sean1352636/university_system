"""
Facilities & Space Management — interactive CLI.

Wired to the managers in ``facilities.services.facilities_management_core``,
which read/write the shared ``student_records.db`` — the same database the
Facilities GUI (``building_management_app.py``) uses. Anything created here is
visible in the GUI and vice-versa.

Covers the seven areas the old stub menu only advertised:
Building Management, Room Bookings, Maintenance Requests, Work Orders,
Asset Inventory, Energy Usage Tracking, and Space Utilization Reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.core.i18n import get_text
from education_system.post_18.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
from education_system.post_18.university_system.modules.domain.campus.facilities.services.facilities_management_core import (
    BuildingManager,
    RoomManager,
    RoomBookingManager,
    MaintenanceRequestManager,
    WorkOrderManager,
    AssetManager,
    EnergyUsageManager,
    AccessCardManager,
    InspectionManager,
    OccupancyManager,
    CleaningScheduleManager,
)


# --------------------------------------------------------------------------- #
# Small input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    """Prompt for a string. Returns the trimmed input (or *default* if blank)."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    """Prompt for an integer. Blank returns None when *allow_blank*."""
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _prompt_float(text: str, *, allow_blank: bool = True) -> Optional[float]:
    """Prompt for a float. Blank returns None when *allow_blank*."""
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _current_username(auth) -> str:
    """Best-effort current username for 'reported_by' / 'booked_by' fields."""
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# --------------------------------------------------------------------------- #
# 1. Building Management
# --------------------------------------------------------------------------- #
def _list_buildings() -> None:
    buildings = BuildingManager.list_buildings(active_only=False)
    if not buildings:
        print("\nNo buildings registered yet.")
        return
    print(f"\n{'ID':<5}{'Code':<10}{'Name':<28}{'Type':<14}Floors")
    print("-" * 65)
    for b in buildings:
        print(f"{b['building_id']:<5}{(b.get('building_code') or ''):<10}"
              f"{(b.get('building_name') or '')[:27]:<28}"
              f"{(b.get('building_type') or '')[:13]:<14}"
              f"{b.get('total_floors') if b.get('total_floors') is not None else '-'}")


def _register_building() -> None:
    name = _prompt("Building name")
    code = _prompt("Building code")
    if not name or not code:
        print("Name and code are required.")
        return
    address = _prompt("Address (optional)")
    floors = _prompt_int("Total floors (optional)") or 0
    btype = _prompt("Building type (optional)")
    try:
        bid = BuildingManager.register_building(name, code, address, floors, btype)
        print(f"\n✓ Registered building '{name}' (id={bid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_rooms() -> None:
    bid = _prompt_int("Filter by building id (blank = all)")
    rooms = RoomManager.list_rooms(building_id=bid)
    if not rooms:
        print("\nNo rooms found.")
        return
    print(f"\n{'ID':<5}{'Room':<10}{'Building':<16}{'Type':<14}{'Cap':<6}Status")
    print("-" * 62)
    for r in rooms:
        print(f"{r.get('id'):<5}{(r.get('room_number') or ''):<10}"
              f"{(r.get('building') or '')[:15]:<16}"
              f"{(r.get('room_type') or '')[:13]:<14}"
              f"{r.get('capacity') if r.get('capacity') is not None else '-':<6}"
              f"{r.get('status') or 'available'}")


def _register_room() -> None:
    bid = _prompt_int("Building id", allow_blank=False)
    number = _prompt("Room number")
    if not number:
        print("Room number is required.")
        return
    rtype = _prompt("Room type", default="Lecture")
    capacity = _prompt_int("Capacity (optional)") or 0
    floor = _prompt_int("Floor number (optional)") or 1
    try:
        rid = RoomManager.register_room(bid, number, rtype, capacity, floor)
        print(f"\n✓ Registered room '{number}' (id={rid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _building_menu(auth) -> None:
    while True:
        _header("Building Management")
        print("[1] List buildings")
        print("[2] Register building")
        print("[3] List rooms")
        print("[4] Register room")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_buildings()
        elif choice == "2":
            _register_building()
        elif choice == "3":
            _list_rooms()
        elif choice == "4":
            _register_room()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Room Bookings
# --------------------------------------------------------------------------- #
def _list_available_rooms() -> None:
    rtype = _prompt("Room type filter (optional)")
    min_cap = _prompt_int("Minimum capacity (optional)") or 0
    rooms = RoomManager.get_available_rooms(rtype, min_cap)
    if not rooms:
        print("\nNo available rooms match.")
        return
    print(f"\n{'ID':<5}{'Room':<10}{'Building':<16}{'Type':<14}Cap")
    print("-" * 55)
    for r in rooms:
        print(f"{r.get('id'):<5}{(r.get('room_number') or ''):<10}"
              f"{(r.get('building') or '')[:15]:<16}"
              f"{(r.get('room_type') or '')[:13]:<14}"
              f"{r.get('capacity') if r.get('capacity') is not None else '-'}")


def _book_room(auth) -> None:
    room_id = _prompt_int("Room id (see 'List available rooms')", allow_blank=False)
    booking_type = _prompt("Booking type", default="event")
    start = _prompt("Start (YYYY-MM-DD HH:MM)")
    end = _prompt("End (YYYY-MM-DD HH:MM)")
    if not start or not end:
        print("Start and end are required.")
        return
    purpose = _prompt("Purpose (optional)")
    attendees = _prompt_int("Expected attendees (optional)") or 0
    booked_by = _current_username(auth)
    try:
        bid = RoomBookingManager.book_room(
            room_id, booked_by, booking_type, start, end, purpose, attendees)
        print(f"\n✓ Booked room {room_id} (booking id={bid}, by {booked_by}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_bookings() -> None:
    status = _prompt("Status filter (confirmed/cancelled, blank = all)")
    bookings = RoomBookingManager.list_bookings(status=status or None)
    if not bookings:
        print("\nNo bookings found.")
        return
    print(f"\n{'ID':<5}{'Room':<10}{'By':<14}{'Start':<18}{'Status'}")
    print("-" * 60)
    for bk in bookings:
        print(f"{bk['booking_id']:<5}{(bk.get('room_number') or bk.get('room_id')):<10}"
              f"{(bk.get('booked_by') or '')[:13]:<14}"
              f"{(bk.get('start_datetime') or '')[:17]:<18}"
              f"{bk.get('booking_status') or ''}")


def _cancel_booking() -> None:
    bid = _prompt_int("Booking id to cancel", allow_blank=False)
    try:
        if RoomBookingManager.cancel_booking(bid):
            print(f"\n✓ Cancelled booking {bid}.")
        else:
            print(f"\nNo booking with id {bid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _bookings_menu(auth) -> None:
    while True:
        _header("Room Bookings")
        print("[1] List available rooms")
        print("[2] Book a room")
        print("[3] List bookings")
        print("[4] Cancel a booking")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_available_rooms()
        elif choice == "2":
            _book_room(auth)
        elif choice == "3":
            _list_bookings()
        elif choice == "4":
            _cancel_booking()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Maintenance Requests
# --------------------------------------------------------------------------- #
def _list_requests() -> None:
    status = _prompt("Status filter (open/in_progress/completed, blank = all)")
    requests = MaintenanceRequestManager.list_requests(status=status or None)
    if not requests:
        print("\nNo maintenance requests found.")
        return
    print(f"\n{'ID':<5}{'Type':<14}{'Priority':<10}{'Status':<13}Description")
    print("-" * 70)
    for r in requests:
        print(f"{r['request_id']:<5}{(r.get('request_type') or '')[:13]:<14}"
              f"{(r.get('priority') or '')[:9]:<10}"
              f"{(r.get('status') or '')[:12]:<13}"
              f"{(r.get('description') or '')[:30]}")


def _submit_request(auth) -> None:
    rtype = _prompt("Request type (e.g. plumbing, electrical)")
    priority = _prompt("Priority (low/medium/high/urgent)", default="medium")
    description = _prompt("Description")
    if not rtype or not description:
        print("Type and description are required.")
        return
    building_id = _prompt_int("Building id (optional)")
    room_id = _prompt_int("Room id (optional)")
    reported_by = _current_username(auth)
    try:
        rid = MaintenanceRequestManager.submit_request(
            rtype, priority, description, reported_by,
            building_id=building_id, room_id=room_id)
        print(f"\n✓ Submitted maintenance request {rid} (by {reported_by}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_request(auth) -> None:
    rid = _prompt_int("Request id", allow_blank=False)
    status = _prompt("New status (open/in_progress/completed/cancelled)")
    if not status:
        print("Status is required.")
        return
    assign = _prompt("Assign to (blank to leave unchanged)")
    try:
        if MaintenanceRequestManager.update_status(
                rid, status, assigned_to=assign or None):
            print(f"\n✓ Updated request {rid} → {status}.")
        else:
            print(f"\nNo request with id {rid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _maintenance_menu(auth) -> None:
    while True:
        _header("Maintenance Requests")
        print("[1] List requests")
        print("[2] Submit request")
        print("[3] Update request status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_requests()
        elif choice == "2":
            _submit_request(auth)
        elif choice == "3":
            _update_request(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Work Orders
# --------------------------------------------------------------------------- #
def _list_work_orders() -> None:
    status = _prompt("Status filter (pending/in_progress/completed, blank = all)")
    orders = WorkOrderManager.list_work_orders(status=status or None)
    if not orders:
        print("\nNo work orders found.")
        return
    print(f"\n{'ID':<5}{'Req':<6}{'Type':<16}{'Technician':<16}Status")
    print("-" * 60)
    for o in orders:
        print(f"{o['work_order_id']:<5}{o.get('request_id') or '-':<6}"
              f"{(o.get('work_order_type') or '')[:15]:<16}"
              f"{(o.get('assigned_technician') or '-')[:15]:<16}"
              f"{o.get('status') or ''}")


def _create_work_order() -> None:
    req_id = _prompt_int("Maintenance request id", allow_blank=False)
    wtype = _prompt("Work order type", default="repair")
    description = _prompt("Description")
    if not description:
        print("Description is required.")
        return
    technician = _prompt("Assigned technician (optional)")
    try:
        wid = WorkOrderManager.create_work_order(
            req_id, wtype, description, technician)
        print(f"\n✓ Created work order {wid} for request {req_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_work_order() -> None:
    wid = _prompt_int("Work order id", allow_blank=False)
    status = _prompt("New status (pending/in_progress/completed/cancelled)")
    if not status:
        print("Status is required.")
        return
    try:
        if WorkOrderManager.update_status(wid, status):
            print(f"\n✓ Updated work order {wid} → {status}.")
        else:
            print(f"\nNo work order with id {wid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _work_orders_menu(auth) -> None:
    while True:
        _header("Work Orders")
        print("[1] List work orders")
        print("[2] Create work order (from a request)")
        print("[3] Update work order status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_work_orders()
        elif choice == "2":
            _create_work_order()
        elif choice == "3":
            _update_work_order()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 5. Asset Inventory
# --------------------------------------------------------------------------- #
def _list_assets() -> None:
    bid = _prompt_int("Building id filter (optional)")
    status = _prompt("Status filter (active/retired, blank = all)")
    assets = AssetManager.list_assets(building_id=bid, status=status or None)
    if not assets:
        print("\nNo assets found.")
        return
    print(f"\n{'ID':<5}{'Tag':<12}{'Name':<22}{'Type':<14}{'Cond':<8}Status")
    print("-" * 70)
    for a in assets:
        print(f"{a['asset_id']:<5}{(a.get('asset_tag') or '-')[:11]:<12}"
              f"{(a.get('asset_name') or '')[:21]:<22}"
              f"{(a.get('asset_type') or '')[:13]:<14}"
              f"{(a.get('condition') or '')[:7]:<8}"
              f"{a.get('status') or ''}")


def _register_asset() -> None:
    name = _prompt("Asset name")
    atype = _prompt("Asset type")
    tag = _prompt("Asset tag (unique)")
    if not name or not atype or not tag:
        print("Name, type and tag are required.")
        return
    building_id = _prompt_int("Building id (optional)")
    room_id = _prompt_int("Room id (optional)")
    cost = _prompt_float("Purchase cost (optional)") or 0
    try:
        aid = AssetManager.register_asset(
            name, atype, tag, building_id=building_id,
            room_id=room_id, purchase_cost=cost)
        print(f"\n✓ Registered asset '{name}' (id={aid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_asset() -> None:
    aid = _prompt_int("Asset id", allow_blank=False)
    status = _prompt("New status (blank to leave unchanged)")
    condition = _prompt("New condition (blank to leave unchanged)")
    if not status and not condition:
        print("Nothing to update.")
        return
    try:
        if AssetManager.update_asset(
                aid, status=status or None, condition=condition or None):
            print(f"\n✓ Updated asset {aid}.")
        else:
            print(f"\nNo asset with id {aid} (or nothing changed).")
    except Exception as e:
        print(f"\n✗ {e}")


def _assets_menu(auth) -> None:
    while True:
        _header("Asset Inventory")
        print("[1] List assets")
        print("[2] Register asset")
        print("[3] Update asset status/condition")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_assets()
        elif choice == "2":
            _register_asset()
        elif choice == "3":
            _update_asset()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 6. Energy Usage Tracking
# --------------------------------------------------------------------------- #
def _list_energy() -> None:
    readings = EnergyUsageManager.list_recent(limit=20)
    if not readings:
        print("\nNo energy readings recorded.")
        return
    print(f"\n{'Building':<10}{'Type':<12}{'Date':<12}{'Consumption':<14}Cost")
    print("-" * 55)
    for r in readings:
        cost = r.get('cost')
        cons = r.get('consumption')
        cons_str = f"{cons:.2f}" if cons is not None else "-"
        cost_str = f"£{cost:.2f}" if cost is not None else "-"
        print(f"{(r.get('building_code') or '?'):<10}"
              f"{(r.get('usage_type') or '')[:11]:<12}"
              f"{(r.get('reading_date') or '')[:10]:<12}"
              f"{cons_str:<14}{cost_str}")


def _record_energy() -> None:
    building_id = _prompt_int("Building id", allow_blank=False)
    usage_type = _prompt("Usage type (electricity/gas/water)", default="electricity")
    reading_date = _prompt("Reading date (YYYY-MM-DD)",
                           default=datetime.now().strftime("%Y-%m-%d"))
    meter = _prompt_float("Meter reading", allow_blank=False)
    consumption = _prompt_float("Consumption (optional)")
    cost = _prompt_float("Cost (optional)")
    try:
        uid = EnergyUsageManager.record_reading(
            building_id, usage_type, reading_date, meter, consumption, cost)
        print(f"\n✓ Recorded energy reading {uid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _energy_summary() -> None:
    rows = EnergyUsageManager.summary_by_building()
    if not rows:
        print("\nNo energy data to summarise.")
        return
    print(f"\n{'Building':<10}{'Name':<26}{'Consumption':<14}{'Cost':<12}Readings")
    print("-" * 72)
    for r in rows:
        cons = r.get('total_consumption') or 0
        cost = r.get('total_cost') or 0
        print(f"{(r.get('building_code') or '?'):<10}"
              f"{(r.get('building_name') or '')[:25]:<26}"
              f"{cons:<14.2f}£{cost:<11.2f}{r.get('readings')}")


def _energy_menu(auth) -> None:
    while True:
        _header("Energy Usage Tracking")
        print("[1] Recent readings")
        print("[2] Record a reading")
        print("[3] Summary by building")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_energy()
        elif choice == "2":
            _record_energy()
        elif choice == "3":
            _energy_summary()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 7. Space Utilization Reports
# --------------------------------------------------------------------------- #
def _occupancy_summary() -> None:
    rows = OccupancyManager.utilisation_summary()
    if not rows:
        print("\nNo occupancy records yet.")
        return
    print(f"\n{'Building':<10}{'Name':<26}{'Avg %':<9}{'Peak %':<9}Samples")
    print("-" * 65)
    for r in rows:
        print(f"{(r.get('building_code') or '?'):<10}"
              f"{(r.get('building_name') or '')[:25]:<26}"
              f"{(r.get('avg_pct') or 0):<9.1f}"
              f"{(r.get('peak_pct') or 0):<9.1f}"
              f"{r.get('sample_count')}")


def _record_occupancy() -> None:
    building_id = _prompt_int("Building id", allow_blank=False)
    occupants = _prompt_int("Occupant count", allow_blank=False)
    capacity = _prompt_int("Capacity", allow_blank=False)
    room_id = _prompt_int("Room id (optional)")
    try:
        rid = OccupancyManager.record(
            building_id, occupants, capacity, room_id=room_id)
        print(f"\n✓ Recorded occupancy sample {rid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _cleaning_due() -> None:
    rows = CleaningScheduleManager.list_due()
    if not rows:
        print("\nNo cleaning schedules due.")
        return
    print(f"\n{'ID':<5}{'Building':<10}{'Room':<8}{'Freq':<12}{'Next Due':<12}Assigned")
    print("-" * 62)
    for r in rows:
        print(f"{r['id']:<5}{r.get('building_id'):<10}"
              f"{r.get('room_id') or '-':<8}"
              f"{(r.get('frequency') or '')[:11]:<12}"
              f"{(r.get('next_due') or '')[:11]:<12}"
              f"{r.get('assigned_to') or '-'}")


def _schedule_cleaning() -> None:
    building_id = _prompt_int("Building id", allow_blank=False)
    frequency = _prompt("Frequency (daily/weekly/monthly)", default="weekly")
    room_id = _prompt_int("Room id (optional)")
    next_due = _prompt("Next due (YYYY-MM-DD, optional)")
    assigned = _prompt("Assigned to (optional)")
    try:
        sid = CleaningScheduleManager.schedule(
            building_id, frequency, room_id=room_id,
            next_due=next_due or None, assigned_to=assigned)
        print(f"\n✓ Scheduled cleaning {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _space_reports_menu(auth) -> None:
    while True:
        _header("Space Utilization Reports")
        print("[1] Occupancy summary (avg / peak per building)")
        print("[2] Record occupancy sample")
        print("[3] Cleaning schedules due")
        print("[4] Schedule cleaning")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _occupancy_summary()
        elif choice == "2":
            _record_occupancy()
        elif choice == "3":
            _cleaning_due()
        elif choice == "4":
            _schedule_cleaning()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 8. Access Cards
# --------------------------------------------------------------------------- #
def _list_access_cards() -> None:
    status = _prompt("Status filter (active/suspended/lost/expired/revoked, blank = all)")
    cards = AccessCardManager.list_cards(status=status or None)
    if not cards:
        print("\nNo access cards found.")
        return
    print(f"\n{'ID':<5}{'Card #':<14}{'Holder':<18}{'Type':<11}{'Status':<11}Expires")
    print("-" * 72)
    for c in cards:
        print(f"{c['card_id']:<5}{(c.get('card_number') or '')[:13]:<14}"
              f"{(c.get('user_name') or '')[:17]:<18}"
              f"{(c.get('card_type') or '')[:10]:<11}"
              f"{(c.get('status') or '')[:10]:<11}"
              f"{c.get('expiry_date') or '-'}")


def _issue_access_card(auth) -> None:
    card_number = _prompt("Card number")
    if not card_number:
        print("Card number is required.")
        return
    user_id = _prompt("User id (optional)")
    user_name = _prompt("Holder name (optional)")
    card_type = _prompt("Card type (staff/student/contractor/visitor/service)",
                        default="staff")
    access_level = _prompt("Access level (standard/elevated/restricted/high_security)",
                          default="standard")
    buildings = _prompt("Buildings (comma-separated codes, optional)")
    expiry = _prompt("Expiry date (YYYY-MM-DD, optional)")
    notes = _prompt("Notes (optional)")
    try:
        cid = AccessCardManager.issue_card(
            card_number, user_id=user_id, user_name=user_name,
            card_type=card_type, access_level=access_level,
            buildings_access=buildings, expiry_date=expiry or None,
            issued_by=_current_username(auth), notes=notes)
        print(f"\n✓ Issued access card '{card_number}' (id={cid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_access_card() -> None:
    cid = _prompt_int("Card id", allow_blank=False)
    status = _prompt("New status (active/suspended/lost/expired/revoked)")
    if not status:
        print("Status is required.")
        return
    try:
        if AccessCardManager.update_status(cid, status):
            print(f"\n✓ Updated card {cid} → {status}.")
        else:
            print(f"\nNo access card with id {cid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _access_cards_menu(auth) -> None:
    while True:
        _header("Access Cards")
        print("[1] List access cards")
        print("[2] Issue access card")
        print("[3] Update card status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_access_cards()
        elif choice == "2":
            _issue_access_card(auth)
        elif choice == "3":
            _update_access_card()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 9. Inspections
# --------------------------------------------------------------------------- #
def _list_inspections() -> None:
    status = _prompt("Status filter (scheduled/in_progress/passed/failed/"
                     "remedial_required, blank = all)")
    inspections = InspectionManager.list_inspections(status=status or None)
    if not inspections:
        print("\nNo inspections found.")
        return
    print(f"\n{'ID':<22}{'Room':<12}{'Type':<14}{'Date':<12}Status")
    print("-" * 74)
    for i in inspections:
        print(f"{(i.get('inspection_id') or '')[:21]:<22}"
              f"{(i.get('room_label') or i.get('room_id') or '')[:11]:<12}"
              f"{(i.get('inspection_type') or '')[:13]:<14}"
              f"{(i.get('inspection_date') or '')[:10]:<12}"
              f"{i.get('status') or ''}")


def _list_inspectable_rooms() -> None:
    rooms = InspectionManager.list_inspectable_rooms()
    if not rooms:
        print("\nNo inspectable rooms found.")
        return
    print(f"\n{'Room ID':<24}{'Building':<12}{'Room':<10}{'Floor':<7}Type")
    print("-" * 62)
    for r in rooms:
        print(f"{(r.get('room_id') or '')[:23]:<24}"
              f"{(str(r.get('building_id') or ''))[:11]:<12}"
              f"{(r.get('room_number') or '')[:9]:<10}"
              f"{r.get('floor_number') if r.get('floor_number') is not None else '-':<7}"
              f"{r.get('room_type') or ''}")


def _schedule_inspection() -> None:
    room_id = _prompt("Room id (see 'List inspectable rooms')")
    if not room_id:
        print("Room id is required.")
        return
    itype = _prompt("Type (lift/fire_safety/electrical/gas/asbestos/"
                    "legionella/structural/general/housing)", default="general")
    inspector = _prompt("Inspector")
    date = _prompt("Inspection date (YYYY-MM-DD)",
                   default=datetime.now().strftime("%Y-%m-%d"))
    status = _prompt("Status (scheduled/in_progress/passed/failed/"
                     "remedial_required)", default="scheduled")
    findings = _prompt("Findings (optional)")
    action = _prompt("Action required (optional)")
    follow_up = _prompt("Follow-up date (YYYY-MM-DD, optional)")
    try:
        iid = InspectionManager.schedule_inspection(
            room_id, inspector, itype, inspection_date=date, status=status,
            findings=findings, action_required=action,
            follow_up_date=follow_up or None)
        print(f"\n✓ Recorded inspection {iid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _update_inspection() -> None:
    iid = _prompt("Inspection id (INS-...)")
    if not iid:
        print("Inspection id is required.")
        return
    status = _prompt("New status (scheduled/in_progress/passed/failed/"
                     "remedial_required)")
    if not status:
        print("Status is required.")
        return
    findings = _prompt("Findings (blank to leave unchanged)")
    follow_up = _prompt("Follow-up date (blank to leave unchanged)")
    try:
        if InspectionManager.update_status(
                iid, status, findings=findings or None,
                follow_up_date=follow_up or None):
            print(f"\n✓ Updated inspection {iid} → {status}.")
        else:
            print(f"\nNo inspection with id {iid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _inspections_menu(auth) -> None:
    while True:
        _header("Inspections")
        print("[1] List inspections")
        print("[2] List inspectable rooms")
        print("[3] Record / schedule inspection")
        print("[4] Update inspection status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_inspections()
        elif choice == "2":
            _list_inspectable_rooms()
        elif choice == "3":
            _schedule_inspection()
        elif choice == "4":
            _update_inspection()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_facilities_menu(auth) -> None:
    """Run the Facilities & Space Management CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print(f"   {get_text('facilities.title', default='FACILITIES & SPACE MANAGEMENT')}")
        print("=" * 50)
        print(f"1. {get_text('facilities.menu.building', default='Building Management')}")
        print(f"2. {get_text('facilities.menu.room_bookings', default='Room Bookings')}")
        print(f"3. {get_text('facilities.menu.maintenance', default='Maintenance Requests')}")
        print(f"4. {get_text('facilities.menu.work_orders', default='Work Orders')}")
        print(f"5. {get_text('facilities.menu.assets', default='Asset Inventory')}")
        print(f"6. {get_text('facilities.menu.energy', default='Energy Usage Tracking')}")
        print(f"7. {get_text('facilities.menu.space_reports', default='Space Utilization Reports')}")
        print(f"8. {get_text('facilities.menu.access_cards', default='Access Cards')}")
        print(f"9. {get_text('facilities.menu.inspections', default='Inspections')}")
        print(f"10. {get_text('facilities.menu.language', default='Language')}")
        print(f"11. {get_text('facilities.menu.return_main', default='Return to Main Menu')}")
        print("=" * 50)

        try:
            choice = input(
                f"\n{get_text('facilities.prompt.choice', default='Enter your choice (1-11)')}: "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _building_menu(auth)
            elif choice == "2":
                _bookings_menu(auth)
            elif choice == "3":
                _maintenance_menu(auth)
            elif choice == "4":
                _work_orders_menu(auth)
            elif choice == "5":
                _assets_menu(auth)
            elif choice == "6":
                _energy_menu(auth)
            elif choice == "7":
                _space_reports_menu(auth)
            elif choice == "8":
                _access_cards_menu(auth)
            elif choice == "9":
                _inspections_menu(auth)
            elif choice == "10":
                display_language_menu_option()
            elif choice == "11":
                print(get_text('facilities.returning', default='Returning to main menu...'))
                return
            else:
                print(get_text('facilities.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(get_text('facilities.error', default='Error: {error}').format(error=e))
