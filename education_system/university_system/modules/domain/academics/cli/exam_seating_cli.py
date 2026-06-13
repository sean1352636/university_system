"""CLI for exam seating plans.

Hooks into exam_management_cli.display_exam_portal_menu via display_seating_menu.
Staff/admin only.
"""

from education_system.university_system.modules.domain.academics.services.exam_management.seating import (
    POLICIES,
    define_room_layout,
    delete_room_layout,
    list_layouts,
    get_layout,
    auto_allocate,
    clear_allocation,
    list_allocations,
    seating_chart,
    export_chart_csv,
    assign_invigilator_zone,
    list_zones,
    clear_zones,
)
from education_system.university_system.infrastructure.database.db import get_connection


def _prompt_int(msg, *, allow_zero=False):
    while True:
        raw = input(msg).strip()
        try:
            n = int(raw)
            if n < 0 or (n == 0 and not allow_zero):
                print("Enter a positive number.")
                continue
            return n
        except ValueError:
            print("Enter a valid number.")


def _prompt_label_set(prompt_text):
    raw = input(prompt_text).strip()
    if not raw:
        return set()
    return {tok.strip().upper() for tok in raw.split(',') if tok.strip()}


def _pick_room():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id, COALESCE(room_name, room_number), building, capacity
            FROM rooms
            WHERE is_active = 1 OR status = 'available'
            ORDER BY building, room_name
        ''')
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        print("No rooms found.")
        return None
    print("\nRooms:")
    for i, (rid, name, bld, cap) in enumerate(rows, 1):
        print(f"  {i}. {name or '?'} ({bld or '—'}) — capacity {cap or '?'}")
    while True:
        sel = input("Pick a room (number, 0 to cancel): ").strip()
        if sel == '0':
            return None
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(rows):
                return rows[idx][0], rows[idx][1]
        except ValueError:
            pass
        print(f"Enter 1–{len(rows)} or 0.")


def _pick_exam():
    """List exams; return id or None."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id, module_code, COALESCE(module_name, ''), date, room
            FROM exams ORDER BY date DESC, start_time DESC
            LIMIT 50
        ''')
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        print("No exams found.")
        return None
    print("\nRecent exams:")
    for i, (eid, code, name, date, room) in enumerate(rows, 1):
        print(f"  {i}. [{eid}] {code} {name[:30]} — {date} ({room or '—'})")
    while True:
        sel = input("Pick an exam (number, 0 to cancel): ").strip()
        if sel == '0':
            return None
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(rows):
                return rows[idx][0]
        except ValueError:
            pass
        print(f"Enter 1–{len(rows)} or 0.")


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------

def _define_layout():
    room = _pick_room()
    if not room:
        return
    room_id, room_name = room
    print(f"\nDefining layout for {room_name}.")
    rows_n = _prompt_int("Number of rows: ")
    cols_n = _prompt_int("Number of columns: ")
    print(f"Seats will be labelled A1..{chr(ord('A')+rows_n-1) if rows_n<=26 else 'rows>26'}{cols_n}.")
    accessible = _prompt_label_set(
        "Accessible (wheelchair) seat labels (comma-separated, blank for none): ")
    left_handed = _prompt_label_set(
        "Left-handed desk labels (blank for none): ")
    disabled = _prompt_label_set(
        "Out-of-service seat labels (blank for none): ")
    try:
        layout_id = define_room_layout(
            room_id, rows_n, cols_n,
            accessible_seats=accessible,
            left_handed_seats=left_handed,
            disabled_seats=disabled,
        )
        usable = rows_n * cols_n - len(disabled)
        print(f"\nLayout {layout_id} saved. Usable seats: {usable}.")
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}")
    input("Press Enter...")


def _list_layouts():
    rows = list_layouts()
    if not rows:
        print("\nNo layouts defined.")
        input("Press Enter...")
        return
    print("\nDefined layouts:")
    for r in rows:
        print(f"  Room: {r['room_name'] or '?'} ({r['building'] or '—'}) "
              f"— {r['rows_n']}×{r['cols_n']}, "
              f"usable seats {r['seats_total']}")
    input("Press Enter...")


def _delete_layout():
    room = _pick_room()
    if not room:
        return
    room_id, room_name = room
    try:
        ok = delete_room_layout(room_id)
        print(f"Deleted layout for {room_name}." if ok
              else "No layout to delete.")
    except RuntimeError as e:
        print(f"Cannot delete: {e}")
    input("Press Enter...")


def _allocate_seats():
    exam_id = _pick_exam()
    if not exam_id:
        return
    print(f"\nAllocation policies: {', '.join(POLICIES)}")
    policy = input("Policy [alphabetical]: ").strip() or 'alphabetical'
    if policy not in POLICIES:
        print(f"Unknown policy. Must be one of {POLICIES}.")
        return
    try:
        result = auto_allocate(exam_id, policy=policy)
    except ValueError as e:
        print(f"Error: {e}")
        return
    print(f"\nAllocated:   {result['allocated']}")
    if result['unallocated']:
        print(f"Unallocated: {len(result['unallocated'])}")
        for sid, reason in result['unallocated']:
            print(f"  - {sid}: {reason}")
    for w in result['warnings']:
        print(f"⚠  {w}")
    print(f"\nRun View Seating Chart to inspect, or Export CSV.")
    input("Press Enter...")


def _clear_allocation():
    exam_id = _pick_exam()
    if not exam_id:
        return
    if input("Clear allocations for this exam? (y/n): ").strip().lower() != 'y':
        return
    n = clear_allocation(exam_id)
    print(f"Cleared {n} allocation(s).")
    input("Press Enter...")


def _view_chart():
    exam_id = _pick_exam()
    if not exam_id:
        return
    print("\n" + seating_chart(exam_id))
    rows = list_allocations(exam_id)
    if rows:
        print(f"\n{len(rows)} allocation(s):")
        for r in rows:
            extra = f"  [{r['accommodation_notes']}]" if r['accommodation_notes'] else ""
            print(f"  {r['seat_label']:>5}  {r['student_id']}{extra}")
    input("Press Enter...")


def _export_chart():
    exam_id = _pick_exam()
    if not exam_id:
        return
    path = input("Output CSV path "
                 f"[exam_{exam_id}_seating.csv]: ").strip() or f"exam_{exam_id}_seating.csv"
    try:
        n = export_chart_csv(exam_id, path)
        print(f"Wrote {n} row(s) to {path}.")
    except RuntimeError as e:
        print(f"Error: {e}")
    input("Press Enter...")


def _assign_invigilator():
    exam_id = _pick_exam()
    if not exam_id:
        return
    invigilator = input("Invigilator name: ").strip()
    if not invigilator:
        return
    zone_label = input("Zone label (e.g. 'Front', 'Rows A-C'): ").strip()
    if not zone_label:
        return
    print("Bounds (optional — blank to skip):")
    def _opt_int(prompt):
        v = input(prompt).strip()
        if not v:
            return None
        try:
            return int(v)
        except ValueError:
            return None
    rs = _opt_int("  Row start (1-based): ")
    re = _opt_int("  Row end: ")
    cs = _opt_int("  Col start (1-based): ")
    ce = _opt_int("  Col end: ")
    zid = assign_invigilator_zone(
        exam_id, invigilator, zone_label,
        row_start=rs, row_end=re, col_start=cs, col_end=ce,
    )
    print(f"Zone {zid} created.")
    input("Press Enter...")


def _list_invigilators():
    exam_id = _pick_exam()
    if not exam_id:
        return
    zones = list_zones(exam_id)
    if not zones:
        print("No invigilator zones for this exam.")
    else:
        print(f"\nZones for exam {exam_id}:")
        for z in zones:
            bounds = []
            if z['row_start'] or z['row_end']:
                bounds.append(f"rows {z['row_start']}–{z['row_end']}")
            if z['col_start'] or z['col_end']:
                bounds.append(f"cols {z['col_start']}–{z['col_end']}")
            bounds_text = f"  ({', '.join(bounds)})" if bounds else ""
            print(f"  [{z['zone_id']}] {z['invigilator']} — {z['zone_label']}{bounds_text}")
    if zones and input("\nClear all zones for this exam? (y/n): ").strip().lower() == 'y':
        n = clear_zones(exam_id)
        print(f"Cleared {n} zone(s).")
    input("Press Enter...")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def display_seating_menu(auth):
    """Staff/admin menu for exam seating."""
    user = auth.current_user if auth and auth.current_user else {}
    role = user.get('role', '')
    if role not in ('admin', 'staff', 'instructor'):
        print("You don't have permission to manage exam seating.")
        return

    while True:
        print("\nExam Seating Plans")
        print("=" * 40)
        print("1. Define Room Layout")
        print("2. List Layouts")
        print("3. Delete Room Layout")
        print("4. Allocate Seats (auto)")
        print("5. Clear Allocation")
        print("6. View Seating Chart")
        print("7. Export Chart (CSV)")
        print("8. Assign Invigilator Zone")
        print("9. List / Clear Invigilator Zones")
        print("0. Back")

        choice = input("\nChoice: ").strip()
        if choice == '1':
            _define_layout()
        elif choice == '2':
            _list_layouts()
        elif choice == '3':
            _delete_layout()
        elif choice == '4':
            _allocate_seats()
        elif choice == '5':
            _clear_allocation()
        elif choice == '6':
            _view_chart()
        elif choice == '7':
            _export_chart()
        elif choice == '8':
            _assign_invigilator()
        elif choice == '9':
            _list_invigilators()
        elif choice == '0':
            return
        else:
            print("Invalid choice.")
