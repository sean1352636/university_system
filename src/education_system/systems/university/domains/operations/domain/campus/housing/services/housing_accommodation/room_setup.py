"""Residence set-up rules shared by the housing CLI and GUI.

Three things live here so both interfaces behave identically:

* **Occupancy is derived, never typed in.** ``housing_rooms.current_occupants``
  is kept equal to the number of occupying assignments (``Active`` or
  ``Pending`` — a pending assignment already holds the bed) by triggers on
  ``housing_assignments`` and a guard trigger on ``housing_rooms``. Any code
  path that still does ``current_occupants = current_occupants + 1`` is
  corrected by the guard, so the column can no longer drift or hold made-up
  numbers.
* **Building counters are recounted** from the rooms that actually exist.
* **CSV room import** with row-by-row validation; nothing is written unless
  every row is valid.
"""

from __future__ import annotations

import csv
import datetime
import io

#: Assignment statuses that hold a bed.
OCCUPYING_ASSIGNMENT_STATUSES = ('Active', 'Pending')

#: Canonical room vocabularies (the CLI's spelling, which the reports and
#: filters match on).
ROOM_TYPES = ('Single', 'Double', 'Triple', 'Suite', 'Studio', 'Apartment')
ROOM_STATUSES = ('Available', 'Occupied', 'Maintenance', 'Reserved')

#: Columns accepted by :func:`parse_rooms_csv`. ``building`` may be a
#: building id or an exact building name.
CSV_REQUIRED_COLUMNS = ('building', 'room_number', 'floor_number', 'room_type',
                        'max_occupants', 'monthly_rent')
CSV_OPTIONAL_COLUMNS = ('is_accessible', 'status')

_DERIVED = (
    "(SELECT COUNT(*) FROM housing_assignments ha "
    " WHERE ha.room_id = housing_rooms.room_id "
    "   AND ha.status IN ('Active', 'Pending'))"
)


def normalise_room_type(value):
    """Return the canonical spelling of *value*, or ``None`` if unknown."""
    text = (value or '').strip().lower()
    for room_type in ROOM_TYPES:
        if room_type.lower() == text:
            return room_type
    return None


def normalise_room_status(value):
    """Return the canonical spelling of *value*, or ``None`` if unknown."""
    text = (value or '').strip().lower()
    for status in ROOM_STATUSES:
        if status.lower() == text:
            return status
    return None


def install_occupancy_triggers(cursor):
    """Create the triggers that keep ``current_occupants`` derived.

    Idempotent (``IF NOT EXISTS``), so it is safe to call from
    ``init_housing_db`` on every launch, alongside the building mirror
    triggers created there.
    """
    recount_new = (
        "UPDATE housing_rooms SET current_occupants = "
        "(SELECT COUNT(*) FROM housing_assignments ha WHERE ha.room_id = NEW.room_id "
        " AND ha.status IN ('Active', 'Pending')) WHERE room_id = NEW.room_id;"
    )
    recount_old = (
        "UPDATE housing_rooms SET current_occupants = "
        "(SELECT COUNT(*) FROM housing_assignments ha WHERE ha.room_id = OLD.room_id "
        " AND ha.status IN ('Active', 'Pending')) WHERE room_id = OLD.room_id;"
    )
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS housing_assignments_occupancy_insert "
        "AFTER INSERT ON housing_assignments BEGIN " + recount_new + " END;")
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS housing_assignments_occupancy_update "
        "AFTER UPDATE OF status, room_id ON housing_assignments BEGIN "
        + recount_old + " " + recount_new + " END;")
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS housing_assignments_occupancy_delete "
        "AFTER DELETE ON housing_assignments BEGIN " + recount_old + " END;")
    # Guard: whatever a writer puts in current_occupants (an old "+ 1", an
    # INSERT with a literal), it is replaced by the derived count. The WHEN
    # clause stops the guard's own UPDATE from looping if recursive triggers
    # are ever switched on.
    guard_when = (
        "WHEN NEW.current_occupants IS NOT "
        "(SELECT COUNT(*) FROM housing_assignments ha WHERE ha.room_id = NEW.room_id "
        " AND ha.status IN ('Active', 'Pending')) "
    )
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS housing_rooms_occupancy_guard_update "
        "AFTER UPDATE OF current_occupants ON housing_rooms " + guard_when
        + "BEGIN " + recount_new + " END;")
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS housing_rooms_occupancy_guard_insert "
        "AFTER INSERT ON housing_rooms " + guard_when
        + "BEGIN " + recount_new + " END;")


def resync_room_occupancy(cursor):
    """Set every room's ``current_occupants`` to its derived count.

    Returns the number of rooms whose stored value was wrong.
    """
    cursor.execute(
        "UPDATE housing_rooms SET current_occupants = " + _DERIVED
        + " WHERE current_occupants IS NOT " + _DERIVED)
    return cursor.rowcount or 0


def recount_building(cursor, building_id, timestamp=None):
    """Recompute a building's ``total_rooms`` / ``available_rooms`` from its rooms."""
    timestamp = timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    UPDATE housing_buildings
    SET total_rooms = (SELECT COUNT(*) FROM housing_rooms WHERE building_id = ?),
        available_rooms = (SELECT COUNT(*) FROM housing_rooms
                           WHERE building_id = ? AND status = 'Available'),
        updated_at = ?
    WHERE building_id = ?
    ''', (building_id, building_id, timestamp, building_id))


def building_count(cursor):
    """How many residences are set up (0 means the set-up screens are needed)."""
    try:
        cursor.execute('SELECT COUNT(*) FROM housing_buildings')
        return cursor.fetchone()[0]
    except Exception:
        return 0


def rooms_csv_template():
    """Header plus one illustrative row, for staff to fill in."""
    return (",".join(CSV_REQUIRED_COLUMNS + CSV_OPTIONAL_COLUMNS) + "\n"
            "<building id or name>,101,1,Single,1,650.00,no,Available\n")


def _parse_bool(text):
    value = (text or '').strip().lower()
    if value in ('', '0', 'n', 'no', 'false'):
        return 0
    if value in ('1', 'y', 'yes', 'true'):
        return 1
    return None


def parse_rooms_csv(cursor, source):
    """Validate a rooms CSV.

    *source* is a file path or a text stream. Returns ``(rows, errors)`` where
    *rows* are dicts ready for :func:`import_rooms` and *errors* are
    ``"line N: message"`` strings. Any error means nothing should be imported.
    """
    errors = []
    rows = []

    if hasattr(source, 'read'):
        text = source.read()
    else:
        with open(source, newline='', encoding='utf-8-sig') as handle:
            text = handle.read()

    reader = csv.DictReader(io.StringIO(text))
    header = [(h or '').strip().lower() for h in (reader.fieldnames or [])]
    missing = [col for col in CSV_REQUIRED_COLUMNS if col not in header]
    if missing:
        return [], [f"header: missing column(s) {', '.join(missing)} "
                    f"(expected {', '.join(CSV_REQUIRED_COLUMNS + CSV_OPTIONAL_COLUMNS)})"]

    cursor.execute('SELECT building_id, building_name FROM housing_buildings')
    by_id = {}
    by_name = {}
    for bid, bname in cursor.fetchall():
        by_id[str(bid).strip().lower()] = bid
        by_name.setdefault(str(bname).strip().lower(), []).append(bid)

    cursor.execute('SELECT building_id, room_number, room_id FROM housing_rooms')
    existing_numbers = set()
    existing_ids = set()
    for bid, number, rid in cursor.fetchall():
        existing_numbers.add((bid, str(number).strip().lower()))
        existing_ids.add(rid)

    seen = set()
    for line_no, raw in enumerate(reader, start=2):
        record = {(k or '').strip().lower(): (v or '').strip() for k, v in raw.items()}
        if not any(record.values()):
            continue
        problems = []

        ref = record.get('building', '')
        building_id = by_id.get(ref.lower())
        if building_id is None:
            matches = by_name.get(ref.lower(), [])
            if len(matches) == 1:
                building_id = matches[0]
            elif len(matches) > 1:
                problems.append(f"building '{ref}' matches {len(matches)} buildings - use the building id")
            else:
                problems.append(f"unknown building '{ref}'")

        room_number = record.get('room_number', '')
        if not room_number:
            problems.append("room_number is empty")

        try:
            floor = int(record.get('floor_number', ''))
            if floor < 0:
                problems.append("floor_number must be 0 or more")
        except ValueError:
            floor = None
            problems.append(f"floor_number '{record.get('floor_number', '')}' is not a whole number")

        room_type = normalise_room_type(record.get('room_type'))
        if room_type is None:
            problems.append(f"room_type '{record.get('room_type', '')}' is not one of {', '.join(ROOM_TYPES)}")

        try:
            max_occ = int(record.get('max_occupants', ''))
            if max_occ <= 0:
                problems.append("max_occupants must be at least 1")
        except ValueError:
            max_occ = None
            problems.append(f"max_occupants '{record.get('max_occupants', '')}' is not a whole number")

        try:
            rent = float(record.get('monthly_rent', '').replace('£', '').replace(',', ''))
            if rent <= 0:
                problems.append("monthly_rent must be greater than 0")
        except ValueError:
            rent = None
            problems.append(f"monthly_rent '{record.get('monthly_rent', '')}' is not a number")

        accessible = _parse_bool(record.get('is_accessible'))
        if accessible is None:
            problems.append(f"is_accessible '{record.get('is_accessible')}' must be yes/no")

        status_text = record.get('status', '')
        status = normalise_room_status(status_text) if status_text else 'Available'
        if status is None:
            problems.append(f"status '{status_text}' is not one of {', '.join(ROOM_STATUSES)}")
        elif status == 'Occupied':
            problems.append("status 'Occupied' cannot be imported - occupancy comes "
                            "from assignments; import as Available and assign residents")

        if building_id is not None and room_number:
            key = (building_id, room_number.lower())
            room_id = f"{building_id}-{room_number}"
            if key in existing_numbers or room_id in existing_ids:
                problems.append(f"room {room_number} already exists in that building")
            elif key in seen:
                problems.append(f"room {room_number} appears more than once in the file")
            seen.add(key)

        if problems:
            errors.extend(f"line {line_no}: {p}" for p in problems)
            continue

        rows.append({
            'room_id': f"{building_id}-{room_number}",
            'building_id': building_id,
            'room_number': room_number,
            'floor_number': floor,
            'room_type': room_type,
            'max_occupants': max_occ,
            'is_accessible': accessible,
            'status': status,
            'monthly_rent': rent,
        })

    if not rows and not errors:
        errors.append("the file has no room rows")
    return rows, errors


def import_rooms(cursor, rows):
    """Insert validated *rows* and recount the affected buildings.

    The caller owns the transaction (commit / rollback). Returns
    ``{building_id: rooms_added}``.
    """
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    added = {}
    for row in rows:
        cursor.execute('''
        INSERT INTO housing_rooms (
            room_id, building_id, room_number, floor_number, room_type, max_occupants,
            current_occupants, is_accessible, status, monthly_rent, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
        ''', (row['room_id'], row['building_id'], row['room_number'], row['floor_number'],
              row['room_type'], row['max_occupants'], row['is_accessible'], row['status'],
              row['monthly_rent'], timestamp, timestamp))
        added[row['building_id']] = added.get(row['building_id'], 0) + 1
    for building_id in added:
        recount_building(cursor, building_id, timestamp)
    return added
