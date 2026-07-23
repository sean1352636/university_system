"""CLI counterparts for the 13 housing GUI features added alongside
the moveout / waitlist / vacancy / bulk / broadcast / search / keys /
contracts / damages / checklists / guests / audit / roommate-finder
work.

Layout mirrors the existing housing CLI conventions:

- one ``display_<feature>_menu`` function per feature, each printing a
  numbered menu and looping until "Back"
- a top-level ``display_extended_housing_menu`` that the main housing
  menu dispatches into
- thin wrappers over the same service helpers the GUI uses, so the
  CLI and GUI share validation + logging end-to-end

Every action is wrapped in try/except so a bad row doesn't abort the
menu, and every successful write goes through ``log_activity`` for the
existing audit pipeline.
"""

from __future__ import annotations

import datetime
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    common as _common,
    extras,
    waitlist as waitlist_service,
)
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    get_connection, generate_id,
)
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity, log_update,
)

logger = logging.getLogger(__name__)


# ── Tiny CLI helpers ───────────────────────────────────────────────────

def _prompt(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or (default or "")


def _yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _print_table(rows: list[dict], columns: list[tuple[str, str, int]]) -> None:
    """Print rows in a fixed-width table. `columns` is a list of
    ``(key, header, width)`` tuples."""
    if not rows:
        print("  (no rows)")
        return
    header = "  ".join(h.ljust(w) for _k, h, w in columns)
    print(header)
    print("-" * len(header))
    for r in rows:
        line = "  ".join(str(r.get(k, "") or "")[:w].ljust(w)
                          for k, _h, w in columns)
        print(line)


def _section(title: str) -> None:
    print(f"\n— {title} —")


def _menu_loop(title: str, options: list[tuple[str, Callable[[], None]]]) -> None:
    """Generic numbered menu. The last entry is always "Back"."""
    while True:
        print(f"\n=== {title} ===")
        for i, (label, _) in enumerate(options, 1):
            print(f"{i}. {label}")
        print(f"{len(options) + 1}. Back")
        choice = input("Enter choice: ").strip()
        if not choice.isdigit():
            print("Invalid choice.")
            continue
        n = int(choice)
        if 1 <= n <= len(options):
            try:
                options[n - 1][1]()
            except KeyboardInterrupt:
                print("\nCancelled.")
            except Exception as e:
                logger.exception("Menu action %r failed", options[n - 1][0])
                print(f"Error: {e}")
        elif n == len(options) + 1:
            return
        else:
            print("Invalid choice.")


def _require_permission(perm: str) -> bool:
    auth = _common.auth
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return False
    if not auth.check_permission(perm):
        print("You don't have permission for this action.")
        return False
    return True


def _current_user() -> str:
    auth = _common.auth
    if auth and auth.current_user:
        return auth.current_user.get('username', 'housing')
    return 'housing'


# ── Top-level dispatcher ───────────────────────────────────────────────

def display_extended_housing_menu() -> None:
    """Sub-menu exposing the 13 new operations. Wired in from the main
    housing menu."""
    if not _require_permission('manage_accommodations'):
        return
    extras.init_extras_schemas()
    waitlist_service.init_waitlist_schema()

    _menu_loop("Advanced Housing Operations", [
        ("Move-out workflow",            display_moveout_menu),
        ("Waitlist",                     display_waitlist_menu),
        ("Vacancy board",                cli_vacancy_board),
        ("Bulk operations",              display_bulk_menu),
        ("Resident broadcasts",          display_broadcast_menu),
        ("Resident search",              cli_resident_search),
        ("Keys & access cards",          display_keys_menu),
        ("Lease / contract documents",   display_contracts_menu),
        ("Move-in / move-out checklists", display_checklists_menu),
        ("Guest passes",                 display_guests_menu),
        ("Damages ledger",               cli_damages_ledger),
        ("Activity / audit log",         cli_audit_log),
        ("Roommate finder (staff)",      cli_roommate_finder),
    ])


# ── 1. Move-out workflow ──────────────────────────────────────────────

def display_moveout_menu() -> None:
    asg = _pick_assignment(active_only=True)
    if not asg:
        return
    _menu_loop(f"Move-out — {asg['assignment_id']} ({asg['student_name']})", [
        ("Show tenancy summary",        lambda: _moveout_summary(asg)),
        ("Record / edit final inspection",
         lambda: _moveout_inspection(asg)),
        ("Add deduction",               lambda: _moveout_add_deduction(asg)),
        ("Show deductions",             lambda: _moveout_show_deductions(asg)),
        ("Finalise move-out",           lambda: _moveout_finalise(asg)),
    ])


def _moveout_summary(asg: dict) -> None:
    held = _moveout_held_deposit(asg['assignment_id'])
    deds = _moveout_list_deductions(asg['assignment_id'])
    total = sum(float(d['amount']) for d in deds if d['status'] != 'Withdrawn')
    print(f"\nAssignment : {asg['assignment_id']}")
    print(f"Student    : {asg['student_name']} ({asg['student_id']})")
    print(f"Room       : {asg['room_number']} · {asg['building_name']}")
    print(f"Move-in    : {asg['move_in_date']} -> planned "
          f"{asg['planned_move_out_date']}")
    print(f"Held deposit         : £{held:,.2f}")
    print(f"Proposed/applied ded.: £{total:,.2f}")
    print(f"Refundable           : £{max(0.0, held - total):,.2f}")


def _moveout_inspection(asg: dict) -> None:
    _section("Final inspection")
    existing = _latest_moveout_inspection(asg['room_id'])
    if existing:
        print(f"Existing inspection {existing['inspection_id']} "
              f"({existing['inspection_date']}) status={existing['status']}")
    inspector = _prompt("Inspector",
                         existing['inspector'] if existing
                         else _current_user())
    date = _prompt("Inspection date (YYYY-MM-DD)",
                    existing['inspection_date'] if existing
                    else datetime.date.today().isoformat())
    status = _prompt("Status (Passed/Issues found/Failed)",
                      existing['status'] if existing else "Passed")
    print("Findings (single line):")
    findings = input("> ").strip()
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            if existing:
                cur.execute('''
                    UPDATE housing_inspections
                       SET inspector=?, inspection_date=?, status=?,
                           findings=?, updated_at=?
                     WHERE inspection_id=?
                ''', (inspector, date, status, findings, now,
                      existing['inspection_id']))
                log_update('housing_inspections',
                           existing['inspection_id'],
                           "Move-out inspection updated (CLI)")
                print(f"Updated inspection {existing['inspection_id']}.")
            else:
                iid = generate_id('INS')
                cur.execute('''
                    INSERT INTO housing_inspections
                    (inspection_id, room_id, inspector, inspection_date,
                     inspection_type, status, findings, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'Move-out', ?, ?, ?, ?)
                ''', (iid, asg['room_id'], inspector, date, status,
                      findings, now, now))
                log_activity(f"Move-out inspection {iid} recorded for "
                             f"{asg['assignment_id']} (CLI)")
                print(f"Recorded inspection {iid}.")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Inspection write failed")
        print(f"Error: {e}")


def _moveout_add_deduction(asg: dict) -> None:
    _section("Add deduction")
    desc = _prompt("Description")
    if not desc:
        print("Cancelled.")
        return
    try:
        amount = float(_prompt("Amount (£)"))
        if amount <= 0:
            raise ValueError
    except ValueError:
        print("Amount must be a positive number.")
        return
    insp = _latest_moveout_inspection(asg['room_id'])
    iid = insp['inspection_id'] if insp else None
    try:
        did = generate_id('DED')
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            conn.execute('''
                INSERT INTO housing_deposit_deductions
                (deduction_id, assignment_id, deposit_payment_id,
                 inspection_id, description, amount, status,
                 created_by, created_at)
                VALUES (?, ?, NULL, ?, ?, ?, 'Proposed', ?, ?)
            ''', (did, asg['assignment_id'], iid, desc, amount,
                  _current_user(), now))
            conn.commit()
        finally:
            conn.close()
        log_activity(f"Deduction {did} proposed for {asg['assignment_id']} "
                     f"(£{amount:.2f}) (CLI)")
        print(f"Recorded {did}.")
    except sqlite3.Error as e:
        logger.exception("Deduction insert failed")
        print(f"Error: {e}")


def _moveout_show_deductions(asg: dict) -> None:
    _section("Deductions")
    rows = _moveout_list_deductions(asg['assignment_id'])
    _print_table(rows, [
        ("deduction_id", "Deduction", 18),
        ("description", "Description", 48),
        ("amount_str", "Amount", 10),
        ("status", "Status", 12),
    ])


def _moveout_finalise(asg: dict) -> None:
    if not _yes_no(
            f"Finalise move-out for {asg['student_name']} "
            f"(room {asg['room_number']})? This terminates the assignment, "
            f"frees the room, and auto-promotes the waitlist.", default=False):
        return
    now = datetime.datetime.now().isoformat(timespec='seconds')
    today = datetime.date.today().isoformat()
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE housing_assignments
                   SET status='Terminated', actual_move_out_date=?,
                       updated_at=?
                 WHERE assignment_id=?
            ''', (today, now, asg['assignment_id']))
            cur.execute('''
                UPDATE housing_rooms
                   SET status='Available',
                       current_occupants = MAX(0, current_occupants - 1),
                       updated_at=?
                 WHERE room_id=?
            ''', (now, asg['room_id']))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Finalise failed")
        print(f"Error: {e}")
        return
    log_update('housing_assignments', asg['assignment_id'],
               f"Move-out finalised on {today} (CLI)")
    revoked = extras.revoke_cards(asg['assignment_id'],
                                   reason="Move-out finalised (CLI)")
    print(f"Finalised. Revoked {revoked} card(s).")
    try:
        promotion = waitlist_service.promote_room_to_next(
            asg['room_id'], created_by=_current_user())
        if promotion:
            print(f"Waitlist promoted: student {promotion['student_id']} -> "
                  f"assignment {promotion['assignment_id']} (Pending).")
        else:
            print("No matching waitlist entry — room left Available.")
    except Exception:
        logger.exception("Waitlist promotion failed (CLI move-out)")
        print("Waitlist promotion failed (see logs).")


def _latest_moveout_inspection(room_id: str) -> dict | None:
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute('''
                SELECT * FROM housing_inspections
                WHERE room_id = ? AND inspection_type='Move-out'
                ORDER BY inspection_date DESC, created_at DESC LIMIT 1
            ''', (room_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Latest move-out inspection load failed")
        return None


def _moveout_held_deposit(assignment_id: str) -> float:
    try:
        conn = get_connection()
        try:
            v = conn.execute('''
                SELECT COALESCE(SUM(amount), 0) FROM payments
                WHERE reference_id = ? AND source_type='housing'
                  AND payment_type='Deposit' AND status='Completed'
            ''', (assignment_id,)).fetchone()[0]
            return float(v or 0)
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Held deposit lookup failed")
        return 0.0


def _moveout_list_deductions(assignment_id: str) -> list[dict]:
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT deduction_id, description, amount, status
                FROM housing_deposit_deductions
                WHERE assignment_id = ? ORDER BY created_at
            ''', (assignment_id,)).fetchall()
            out = [dict(r) for r in rows]
            for r in out:
                r['amount_str'] = f"£{float(r['amount']):,.2f}"
            return out
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Deduction list failed")
        return []


# ── Shared: pick an assignment ─────────────────────────────────────────

def _pick_assignment(*, active_only: bool = True) -> dict | None:
    sql = '''
        SELECT a.assignment_id, a.student_id,
               s.first_name || ' ' || s.last_name AS student_name,
               a.room_id, r.room_number, b.building_name,
               a.move_in_date, a.planned_move_out_date, a.status
        FROM housing_assignments a
        JOIN students s ON s.student_id = a.student_id
        JOIN housing_rooms r ON r.room_id = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
    '''
    if active_only:
        sql += " WHERE a.status='Active' AND a.actual_move_out_date IS NULL"
    sql += " ORDER BY b.building_name, r.room_number"
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(sql).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Pick assignment query failed")
        print(f"Error: {e}")
        return None
    if not rows:
        print("(no matching assignments)")
        return None
    for i, r in enumerate(rows, 1):
        print(f"{i:>3}. {r['assignment_id']} · {r['student_name']} "
              f"({r['student_id']}) · Room {r['room_number']} "
              f"{r['building_name']}")
    pick = input(f"Pick 1-{len(rows)} (Enter to cancel): ").strip()
    if not pick.isdigit():
        return None
    n = int(pick)
    return rows[n - 1] if 1 <= n <= len(rows) else None


# ── 2. Waitlist ────────────────────────────────────────────────────────

def display_waitlist_menu() -> None:
    _menu_loop("Waitlist", [
        ("List Waiting entries", lambda: _waitlist_list("Waiting")),
        ("List Promoted entries", lambda: _waitlist_list("Promoted")),
        ("List Removed entries", lambda: _waitlist_list("Removed")),
        ("List all entries", lambda: _waitlist_list(None)),
        ("Add application to waitlist", _waitlist_add),
        ("Remove waitlist entry", _waitlist_remove),
        ("Promote first match for available room", _waitlist_promote_room),
        ("Auto-promote all available rooms", _waitlist_promote_all),
    ])


def _waitlist_list(status: str | None) -> None:
    rows = waitlist_service.list_waitlist(status=status)
    _print_table(rows, [
        ("waitlist_id", "Waitlist", 18),
        ("student_name", "Student", 24),
        ("building_name", "Building", 24),
        ("room_type", "Type", 12),
        ("priority", "Pri", 4),
        ("status", "Status", 10),
        ("added_at", "Added", 20),
    ])


def _waitlist_add() -> None:
    app_id = _prompt("Application ID")
    if not app_id:
        return
    try:
        pri = int(_prompt("Priority (higher first, default 0)", "0"))
    except ValueError:
        pri = 0
    notes = _prompt("Notes (optional)") or None
    wid = waitlist_service.add_to_waitlist(app_id, priority=pri, notes=notes)
    if wid:
        print(f"Added: {wid}")
    else:
        print("Could not add — see logs.")


def _waitlist_remove() -> None:
    wid = _prompt("Waitlist ID")
    if not wid:
        return
    reason = _prompt("Reason (optional)") or None
    if waitlist_service.remove(wid, reason=reason):
        print("Removed.")
    else:
        print("No change (not found or already terminal).")


def _waitlist_promote_room() -> None:
    room_id = _prompt("Room ID")
    if not room_id:
        return
    summary = waitlist_service.promote_room_to_next(
        room_id, created_by=_current_user())
    if summary:
        print(f"Promoted: student {summary['student_id']} -> assignment "
              f"{summary['assignment_id']}")
    else:
        print("No match (or room not available).")


def _waitlist_promote_all() -> None:
    try:
        conn = get_connection()
        try:
            rooms = [r[0] for r in conn.execute(
                "SELECT room_id FROM housing_rooms WHERE status='Available'")]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("List rooms failed")
        print(f"Error: {e}")
        return
    promoted = 0
    for rid in rooms:
        try:
            if waitlist_service.promote_room_to_next(
                    rid, created_by=_current_user()):
                promoted += 1
        except Exception:
            logger.exception("Promote room %s failed", rid)
    print(f"Scanned {len(rooms)} room(s), promoted {promoted}.")


# ── 3. Vacancy board ───────────────────────────────────────────────────

def cli_vacancy_board() -> None:
    _section("Vacancy board")
    building = _prompt("Building name filter (blank = any)") or None
    room_type = _prompt("Room type filter (blank = any)") or None
    max_rent_raw = _prompt("Max rent (blank = none)") or None
    accessible_only = _yes_no("Accessible only?", False)
    try:
        max_rent = float(max_rent_raw) if max_rent_raw else None
    except ValueError:
        print("Max rent must be numeric.")
        return
    sql = '''
        SELECT b.building_name, r.room_number, r.floor_number,
               r.room_type, r.monthly_rent, r.is_accessible,
               r.current_occupants, r.max_occupants
        FROM housing_rooms r
        JOIN housing_buildings b ON b.building_id = r.building_id
        WHERE r.status='Available'
    '''
    args: list = []
    if building:
        sql += " AND b.building_name LIKE ?"
        args.append(f"%{building}%")
    if room_type:
        sql += " AND r.room_type LIKE ?"
        args.append(f"%{room_type}%")
    if max_rent is not None:
        sql += " AND r.monthly_rent <= ?"
        args.append(max_rent)
    if accessible_only:
        sql += " AND r.is_accessible = 1"
    sql += " ORDER BY b.building_name, r.room_number"
    try:
        conn = get_connection()
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Vacancy board query failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no available rooms)")
        return
    print(f"\n{'Building':24}  {'Room':6}  {'Flr':4}  {'Type':14}  "
          f"{'Rent':>10}  {'Acc':3}  {'Occ':>7}")
    print("-" * 78)
    for bn, rn, fl, rt, rent, acc, cur_occ, max_occ in rows:
        print(f"{(bn or '')[:24]:24}  {(rn or '')[:6]:6}  "
              f"{str(fl if fl is not None else '-')[:4]:4}  "
              f"{(rt or '')[:14]:14}  £{float(rent or 0):>9,.2f}  "
              f"{'Yes' if acc else 'No':3}  "
              f"{cur_occ or 0}/{max_occ or 0}")
    print(f"\n{len(rows)} available room(s).")


# ── 4. Bulk operations ────────────────────────────────────────────────

def display_bulk_menu() -> None:
    _menu_loop("Bulk operations", [
        ("Bulk-approve pending applications", _bulk_approve),
        ("Mass move-out by building", _bulk_mass_moveout),
        ("Building-wide rent adjustment", _bulk_rent_adjust),
    ])


def _bulk_approve() -> None:
    _section("Bulk approve")
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            apps = [dict(r) for r in conn.execute('''
                SELECT a.application_id, a.student_id,
                       s.first_name || ' ' || s.last_name AS student_name,
                       a.preferred_building_id, a.preferred_room_type,
                       a.status
                FROM housing_applications a
                LEFT JOIN students s ON s.student_id = a.student_id
                WHERE a.status IN ('Pending','More Info Needed')
                ORDER BY a.application_date
            ''').fetchall()]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Bulk approve list failed")
        print(f"Error: {e}")
        return
    if not apps:
        print("(no pending applications)")
        return
    for i, a in enumerate(apps, 1):
        print(f"{i:>3}. {a['application_id']} · {a['student_name']} · "
              f"{a['preferred_room_type']} ({a['status']})")
    raw = _prompt("IDs to approve (comma-separated indexes, or 'all')")
    if not raw:
        return
    if raw.lower() == 'all':
        picks = list(range(1, len(apps) + 1))
    else:
        try:
            picks = [int(x.strip()) for x in raw.split(',')]
        except ValueError:
            print("Bad index list.")
            return

    now = datetime.datetime.now().isoformat(timespec='seconds')
    today = datetime.date.today().isoformat()
    plus_year = (datetime.date.today()
                  + datetime.timedelta(days=365)).isoformat()
    who = _current_user()
    approved = 0
    no_room = 0
    errors = 0
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            for idx in picks:
                if not 1 <= idx <= len(apps):
                    continue
                a = apps[idx - 1]
                try:
                    room = _find_first_room(cur,
                                              a['preferred_building_id'],
                                              a['preferred_room_type'])
                    if room is None:
                        cur.execute('''
                            UPDATE housing_applications
                               SET status='Waiting List', reviewed_by=?,
                                   review_date=?, updated_at=?
                             WHERE application_id=?
                        ''', (who, now, now, a['application_id']))
                        no_room += 1
                        continue
                    room_id, _bid, _rn, _fl, _rt, rent = room
                    asg = generate_id('ASG')
                    cur.execute('''
                        INSERT INTO housing_assignments
                        (assignment_id, application_id, student_id, room_id,
                         move_in_date, planned_move_out_date, monthly_rent,
                         status, assigned_by, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
                    ''', (asg, a['application_id'], a['student_id'], room_id,
                          today, plus_year, float(rent or 0), who, now, now))
                    cur.execute('''
                        UPDATE housing_rooms
                           SET status='Reserved',
                               current_occupants = current_occupants + 1,
                               updated_at=?
                         WHERE room_id=?
                    ''', (now, room_id))
                    cur.execute('''
                        UPDATE housing_applications
                           SET status='Approved', reviewed_by=?,
                               review_date=?, updated_at=?
                         WHERE application_id=?
                    ''', (who, now, now, a['application_id']))
                    approved += 1
                    log_activity(
                        f"CLI bulk-approved {a['application_id']} -> "
                        f"assignment {asg} (room {room_id})")
                except sqlite3.Error as e:
                    logger.exception("Bulk approve row %s failed",
                                     a['application_id'])
                    print(f"  ! {a['application_id']}: {e}")
                    errors += 1
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Bulk approve outer failure")
        print(f"Error: {e}")
        return
    print(f"\nApproved: {approved} · No-room: {no_room} · Errors: {errors}")


def _find_first_room(cur, building_id, room_type):
    if building_id:
        cur.execute('''
            SELECT room_id, building_id, room_number, floor_number,
                   room_type, monthly_rent
            FROM housing_rooms
            WHERE building_id=? AND room_type=? AND status='Available'
            ORDER BY floor_number, room_number LIMIT 1
        ''', (building_id, room_type))
        r = cur.fetchone()
        if r:
            return r
    cur.execute('''
        SELECT room_id, building_id, room_number, floor_number,
               room_type, monthly_rent
        FROM housing_rooms
        WHERE room_type=? AND status='Available'
        ORDER BY building_id, floor_number, room_number LIMIT 1
    ''', (room_type,))
    return cur.fetchone()


def _bulk_mass_moveout() -> None:
    _section("Mass move-out")
    building_id = _pick_building(allow_any=False)
    if not building_id:
        return
    date = _prompt("Move-out date (YYYY-MM-DD)",
                    datetime.date.today().isoformat())
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        print("Bad date.")
        return
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute('''
                SELECT a.assignment_id, a.room_id, a.student_id,
                       s.first_name || ' ' || s.last_name AS student_name,
                       r.room_number
                FROM housing_assignments a
                JOIN students s ON s.student_id = a.student_id
                JOIN housing_rooms r ON r.room_id = a.room_id
                WHERE r.building_id = ?
                  AND a.status='Active'
                  AND a.actual_move_out_date IS NULL
            ''', (building_id,)).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Mass move-out list failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no active assignments in that building)")
        return
    for i, r in enumerate(rows, 1):
        print(f"{i:>3}. {r['assignment_id']} · {r['student_name']} · "
              f"Room {r['room_number']}")
    raw = _prompt("Indexes to terminate (comma, or 'all')")
    if not raw:
        return
    if raw.lower() == 'all':
        picks = list(range(1, len(rows) + 1))
    else:
        try:
            picks = [int(x.strip()) for x in raw.split(',')]
        except ValueError:
            print("Bad index list.")
            return
    if not _yes_no(f"Terminate {len(picks)} assignment(s) on {date}?",
                    False):
        return
    now = datetime.datetime.now().isoformat(timespec='seconds')
    finalised: list[str] = []
    errors = 0
    rooms_freed: list[str] = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            for idx in picks:
                if not 1 <= idx <= len(rows):
                    continue
                a = rows[idx - 1]
                try:
                    cur.execute('''
                        UPDATE housing_assignments
                           SET status='Terminated', actual_move_out_date=?,
                               updated_at=?
                         WHERE assignment_id=?
                    ''', (date, now, a['assignment_id']))
                    cur.execute('''
                        UPDATE housing_rooms
                           SET status='Available',
                               current_occupants = MAX(0, current_occupants - 1),
                               updated_at=?
                         WHERE room_id=?
                    ''', (now, a['room_id']))
                    finalised.append(a['assignment_id'])
                    rooms_freed.append(a['room_id'])
                except sqlite3.Error as e:
                    logger.exception("Mass move-out row failed")
                    print(f"  ! {a['assignment_id']}: {e}")
                    errors += 1
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Mass move-out outer failure")
        print(f"Error: {e}")
        return
    promoted = 0
    for rid in rooms_freed:
        try:
            if waitlist_service.promote_room_to_next(
                    rid, created_by=_current_user()):
                promoted += 1
        except Exception:
            logger.exception("Promotion failed during mass move-out (CLI)")
    for asg_id in finalised:
        log_activity(f"CLI mass move-out: {asg_id} terminated ({date})")
    print(f"\nTerminated: {len(finalised)} · "
          f"Waitlist promoted: {promoted} · Errors: {errors}")


def _bulk_rent_adjust() -> None:
    _section("Building-wide rent adjustment")
    building_id = _pick_building(allow_any=False)
    if not building_id:
        return
    room_type = _prompt("Room type (blank = all)") or None
    mode = _prompt("Mode (percent / flat)", "percent").lower()
    if mode not in ("percent", "flat"):
        print("Mode must be 'percent' or 'flat'.")
        return
    try:
        amt = float(_prompt(
            "Amount (e.g. 5 for +5% or -25 for -£25)"))
    except ValueError:
        print("Amount must be numeric.")
        return
    sql = "SELECT room_id, monthly_rent FROM housing_rooms WHERE building_id=?"
    args: list = [building_id]
    if room_type:
        sql += " AND room_type = ?"
        args.append(room_type)
    try:
        conn = get_connection()
        cur = conn.cursor()
        rows = cur.execute(sql, args).fetchall()
    except sqlite3.Error as e:
        logger.exception("Rent adjust list failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no matching rooms)")
        conn.close()
        return
    old_total = sum(float(r[1] or 0) for r in rows)
    if mode == 'percent':
        new_total = sum(round((float(r[1] or 0)) * (1 + amt / 100), 2)
                          for r in rows)
    else:
        new_total = sum(round(max(0.0, (float(r[1] or 0)) + amt), 2)
                          for r in rows)
    print(f"{len(rows)} room(s): roll £{old_total:,.2f} -> "
          f"£{new_total:,.2f} (Δ £{new_total - old_total:+,.2f})")
    if not _yes_no("Apply?", False):
        conn.close()
        return
    now = datetime.datetime.now().isoformat(timespec='seconds')
    updated = 0
    skipped = 0
    try:
        for rid, cur_rent in rows:
            cur_f = float(cur_rent or 0)
            new_f = (cur_f * (1 + amt / 100)) if mode == 'percent' \
                else (cur_f + amt)
            new_f = round(max(0.0, new_f), 2)
            if abs(new_f - cur_f) < 0.005:
                skipped += 1
                continue
            cur.execute(
                "UPDATE housing_rooms SET monthly_rent=?, updated_at=? "
                "WHERE room_id=?", (new_f, now, rid))
            updated += 1
        conn.commit()
    except sqlite3.Error as e:
        logger.exception("Rent adjust apply failed")
        print(f"Error: {e}")
        return
    finally:
        conn.close()
    log_activity(f"CLI bulk rent adjust: building={building_id} "
                 f"type={room_type or 'any'} mode={mode} amount={amt} "
                 f"updated={updated} skipped={skipped}")
    print(f"Updated {updated} room(s), skipped {skipped} (no change).")


# ── 5. Broadcasts ──────────────────────────────────────────────────────

def display_broadcast_menu() -> None:
    _menu_loop("Resident broadcasts", [
        ("Compose & send", _broadcast_compose),
        ("History", _broadcast_history),
    ])


def _broadcast_compose() -> None:
    from education_system.post_18.university_system.modules.shared.utils.email_service import (
        send_email,
    )
    _section("Compose broadcast")
    building_id = _pick_building(allow_any=True)
    room_type = _prompt("Room type filter (blank = all)") or None
    subject = _prompt("Subject")
    if not subject:
        return
    print("Body (single paragraph; press Enter when done):")
    body = input("> ").strip()
    if not body:
        return
    recips = _resolve_broadcast_audience(building_id, room_type)
    print(f"Audience: {len(recips)} resident(s).")
    if not recips:
        return
    if not _yes_no("Send now?", False):
        return
    delivered = 0
    failed = 0
    for r in recips:
        addr = (r.get('email_address') or '').strip()
        if not addr:
            failed += 1
            continue
        try:
            send_email(addr, subject, body)
            delivered += 1
        except Exception:
            logger.exception("Broadcast send failed for %s", addr)
            failed += 1
    bid = generate_id('BC')
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        # Re-use the GUI module's schema (created by extras / broadcasts on
        # first GUI use). Defensive create here too so CLI works standalone.
        conn = get_connection()
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS housing_broadcasts (
                    broadcast_id TEXT PRIMARY KEY, subject TEXT, body TEXT,
                    audience_building_id TEXT, audience_room_type TEXT,
                    recipient_count INTEGER, sent_by TEXT, sent_at TEXT
                )
            ''')
            conn.execute('''
                INSERT INTO housing_broadcasts
                (broadcast_id, subject, body, audience_building_id,
                 audience_room_type, recipient_count, sent_by, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bid, subject, body, building_id, room_type,
                  delivered, _current_user(), now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Broadcast record failed (CLI)")
    log_activity(f"CLI broadcast {bid} sent ({delivered} delivered, "
                 f"{failed} failed) — '{subject[:60]}'")
    print(f"Sent: {delivered} · Failed: {failed} (broadcast {bid}).")


def _broadcast_history() -> None:
    try:
        conn = get_connection()
        try:
            rows = conn.execute('''
                SELECT bc.broadcast_id, bc.sent_at, bc.sent_by,
                       bc.subject,
                       COALESCE(b.building_name, '(any)'),
                       COALESCE(bc.audience_room_type, '(any)'),
                       bc.recipient_count
                FROM housing_broadcasts bc
                LEFT JOIN housing_buildings b
                    ON b.building_id = bc.audience_building_id
                ORDER BY bc.sent_at DESC
            ''').fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Broadcast history failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no broadcasts yet)")
        return
    for bid, sent_at, sender, subj, b, rt, cnt in rows:
        print(f"{sent_at} · {bid} · by {sender} · {b}/{rt} · "
              f"to {cnt} · '{subj[:60]}'")


def _resolve_broadcast_audience(building_id, room_type) -> list[dict]:
    sql = '''
        SELECT a.student_id, s.email_address
        FROM housing_assignments a
        JOIN students s ON s.student_id = a.student_id
        JOIN housing_rooms r ON r.room_id = a.room_id
        WHERE a.status='Active'
    '''
    args: list = []
    if building_id:
        sql += " AND r.building_id = ?"
        args.append(building_id)
    if room_type:
        sql += " AND r.room_type = ?"
        args.append(room_type)
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Audience resolve failed")
        return []


# ── 6. Resident search ────────────────────────────────────────────────

def cli_resident_search() -> None:
    _section("Resident search")
    q = _prompt("Search (name / id / email / room)")
    if not q:
        return
    active_only = _yes_no("Active only?", True)
    sql = '''
        SELECT s.student_id,
               s.first_name || ' ' || s.last_name AS name,
               s.email_address, b.building_name, r.room_number,
               r.room_type, a.status, a.assignment_id
        FROM housing_assignments a
        JOIN students s ON s.student_id = a.student_id
        JOIN housing_rooms r ON r.room_id = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
    '''
    clauses: list[str] = []
    args: list = []
    if active_only:
        clauses.append("a.status='Active'")
    like = f"%{q}%"
    clauses.append(
        "(s.first_name LIKE ? OR s.last_name LIKE ? OR "
        "(s.first_name || ' ' || s.last_name) LIKE ? OR "
        "s.student_id LIKE ? OR s.email_address LIKE ? OR "
        "r.room_number LIKE ?)")
    args.extend([like, like, like, like, like, like])
    sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY b.building_name, r.room_number, s.last_name"
    try:
        conn = get_connection()
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Resident search failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no matches)")
        return
    for sid, name, email, bn, rn, rt, status, asg in rows:
        print(f"  {sid:>10} · {name:<24} · {(email or '-'):<28} · "
              f"{bn[:18]:<18} · Room {rn:<6} · {rt:<10} · {status:<10} · {asg}")
    print(f"\n{len(rows)} match(es).")


# ── 7. Keys ────────────────────────────────────────────────────────────

def display_keys_menu() -> None:
    _menu_loop("Keys & access cards", [
        ("Issue card for assignment", _keys_issue),
        ("Revoke card(s) for assignment", _keys_revoke),
        ("List cards for assignment", _keys_list),
    ])


def _keys_issue() -> None:
    asg = _pick_assignment(active_only=False)
    if not asg:
        return
    expiry = _prompt("Expiry date (YYYY-MM-DD, blank = none)") or None
    if expiry:
        try:
            datetime.date.fromisoformat(expiry)
        except ValueError:
            print("Bad date.")
            return
    cnum = extras.issue_card(asg['assignment_id'],
                              issued_by=_current_user(),
                              expiry_date=expiry)
    if cnum:
        log_activity(f"Access card {cnum} issued for {asg['assignment_id']} "
                     f"(CLI)")
        print(f"Issued: {cnum}")
    else:
        print("Issue failed (see logs).")


def _keys_revoke() -> None:
    asg_id = _prompt("Assignment ID")
    if not asg_id:
        return
    reason = _prompt("Reason", "Manual revoke")
    n = extras.revoke_cards(asg_id, reason=reason)
    log_activity(f"CLI revoked {n} card(s) for {asg_id} (reason={reason!r})")
    print(f"Revoked {n} card(s).")


def _keys_list() -> None:
    asg_id = _prompt("Assignment ID")
    if not asg_id:
        return
    cards = extras.list_cards_for_assignment(asg_id)
    if not cards:
        print("(no cards)")
        return
    for c in cards:
        print(f"  {c['card_number']:<18} · {c['status']:<8} · "
              f"issued {c.get('issue_date') or '-'} · "
              f"expires {c.get('expiry_date') or '-'} · "
              f"by {c.get('issued_by') or '-'}")


# ── 8. Contracts ───────────────────────────────────────────────────────

def display_contracts_menu() -> None:
    _menu_loop("Contracts / Leases", [
        ("Upload contract for assignment", _contracts_upload),
        ("List contracts for assignment", _contracts_list),
        ("Delete contract document", _contracts_delete),
    ])


def _contracts_upload() -> None:
    asg_id = _prompt("Assignment ID")
    path = _prompt("Path to file")
    if not asg_id or not path:
        return
    if not Path(path).is_file():
        print("File not found.")
        return
    notes = _prompt("Notes (optional)") or None
    did = extras.save_contract_document(
        asg_id, path, uploaded_by=_current_user(), notes=notes)
    if did:
        log_activity(f"CLI contract {did} uploaded for {asg_id}")
        print(f"Saved as {did}")
    else:
        print("Upload failed (see logs).")


def _contracts_list() -> None:
    asg_id = _prompt("Assignment ID")
    if not asg_id:
        return
    docs = extras.list_contract_documents(asg_id)
    if not docs:
        print("(no documents)")
        return
    for d in docs:
        print(f"  {d['doc_id']:<18} · {d['original_filename']:<40} · "
              f"{d['uploaded_at']} · by {d['uploaded_by']}")
        print(f"      stored: {d['stored_path']}")


def _contracts_delete() -> None:
    did = _prompt("Document ID")
    if not did or not _yes_no(f"Delete {did}?", False):
        return
    if extras.delete_contract_document(did):
        log_activity(f"CLI contract {did} deleted")
        print("Deleted.")
    else:
        print("Delete failed (not found or DB error).")


# ── 9. Checklists ──────────────────────────────────────────────────────

def display_checklists_menu() -> None:
    _menu_loop("Move-in / move-out checklists", [
        ("Create move-in checklist for assignment",
         lambda: _checklist_create('move-in')),
        ("Create move-out checklist for assignment",
         lambda: _checklist_create('move-out')),
        ("List checklists for assignment", _checklist_list),
        ("Walk checklist items (update)", _checklist_walk),
        ("Attach photo to item", _checklist_attach_photo),
        ("Complete checklist", _checklist_complete),
    ])


def _checklist_create(template: str) -> None:
    asg_id = _prompt("Assignment ID")
    if not asg_id:
        return
    cid = extras.create_checklist(asg_id, template)
    if cid:
        log_activity(f"CLI checklist {cid} ({template}) created for {asg_id}")
        print(f"Created {cid}")
    else:
        print("Create failed (see logs).")


def _checklist_list() -> None:
    asg_id = _prompt("Assignment ID")
    if not asg_id:
        return
    rows = extras.list_checklists(asg_id)
    if not rows:
        print("(no checklists)")
        return
    for c in rows:
        print(f"  {c['checklist_id']:<18} · {c['template']:<10} · "
              f"created {c['created_at']} · "
              f"completed_by {c.get('completed_by') or '-'} "
              f"@ {c.get('completed_at') or '-'}")


def _checklist_walk() -> None:
    cid = _prompt("Checklist ID")
    if not cid:
        return
    items = extras.list_checklist_items(cid)
    if not items:
        print("(no items)")
        return
    for it in items:
        print(f"\n[{it['area']}] {it['description']}")
        print(f"  current condition: {it.get('condition') or '(unset)'}")
        cond = _prompt("Condition (Good/Damaged/Missing, blank to skip)",
                        it.get('condition') or "") or None
        notes = _prompt("Notes (blank to skip)",
                         it.get('notes') or "") or None
        if cond is not None or notes is not None:
            extras.update_checklist_item(it['item_id'],
                                          condition=cond, notes=notes)
    log_activity(f"CLI checklist {cid} walked")
    print("\nDone.")


def _checklist_attach_photo() -> None:
    item_id = _prompt("Checklist item ID")
    path = _prompt("Path to photo")
    if not item_id or not path:
        return
    caption = _prompt("Caption (optional)") or None
    pid = extras.attach_photo(item_id, path, caption=caption)
    if pid:
        log_activity(f"CLI photo {pid} attached to item {item_id}")
        print(f"Attached {pid}")
    else:
        print("Attach failed (see logs).")


def _checklist_complete() -> None:
    cid = _prompt("Checklist ID")
    if not cid:
        return
    notes = _prompt("Completion notes (optional)") or None
    if extras.complete_checklist(cid, completed_by=_current_user(),
                                   notes=notes):
        log_activity(f"CLI checklist {cid} completed")
        print("Marked complete.")
    else:
        print("Complete failed (see logs).")


# ── 10. Guest passes ───────────────────────────────────────────────────

def display_guests_menu() -> None:
    _menu_loop("Guest passes", [
        ("List pending requests", lambda: _guests_list("Pending")),
        ("List all passes", lambda: _guests_list(None)),
        ("New request", _guests_new),
        ("Approve / Deny / Cancel a pass", _guests_decide),
    ])


def _guests_list(status: str | None) -> None:
    rows = extras.list_guest_passes(status=status)
    if not rows:
        print("(none)")
        return
    for r in rows:
        print(f"  {r['pass_id']:<14} · {r['status']:<10} · "
              f"{r['guest_name']:<22} · "
              f"{r['start_date']}→{r['end_date']} · "
              f"resident {r['student_name']} (Room {r['room_number']}, "
              f"{r['building_name']})")


def _guests_new() -> None:
    asg_id = _prompt("Assignment ID (resident)")
    guest_name = _prompt("Guest name")
    if not asg_id or not guest_name:
        return
    relation = _prompt("Relation (optional)") or None
    id_type = _prompt("ID type (optional)") or None
    id_ref = _prompt("ID reference (optional)") or None
    start = _prompt("Start date (YYYY-MM-DD)",
                     datetime.date.today().isoformat())
    end = _prompt("End date (YYYY-MM-DD)",
                    datetime.date.today().isoformat())
    overnight = _yes_no("Overnight?", False)
    pid = extras.request_guest_pass(
        asg_id, guest_name=guest_name, guest_relation=relation,
        id_type=id_type, id_reference=id_ref,
        start_date=start, end_date=end, overnight=overnight,
        requested_by=_current_user())
    if pid:
        log_activity(f"CLI guest pass {pid} requested for {asg_id}")
        print(f"Created {pid}")
    else:
        print("Create failed (see logs).")


def _guests_decide() -> None:
    pid = _prompt("Pass ID")
    if not pid:
        return
    print("Action: 1=Approve  2=Deny  3=Cancel")
    a = _prompt("Choose")
    notes = _prompt("Notes (optional)") or None
    who = _current_user()
    ok = False
    if a == '1':
        ok = extras.decide_guest_pass(pid, approved=True, decision_by=who,
                                        notes=notes)
        log_activity(f"CLI Approved guest pass {pid}")
    elif a == '2':
        ok = extras.decide_guest_pass(pid, approved=False, decision_by=who,
                                        notes=notes)
        log_activity(f"CLI Denied guest pass {pid}")
    elif a == '3':
        ok = extras.cancel_guest_pass(pid, by=who)
        log_activity(f"CLI Cancelled guest pass {pid}")
    else:
        print("Bad choice.")
        return
    print("Done." if ok else "No change.")


# ── 11. Damages ledger ─────────────────────────────────────────────────

def cli_damages_ledger() -> None:
    _section("Damages ledger (per room)")
    building_id = _pick_building(allow_any=True)
    try:
        min_amt = float(_prompt("Min total £", "0") or 0)
    except ValueError:
        print("Bad number.")
        return
    sql = '''
        SELECT r.room_id, r.room_number, b.building_name, r.room_type,
               COUNT(d.deduction_id), COALESCE(SUM(d.amount), 0),
               MAX(d.created_at)
        FROM housing_rooms r
        JOIN housing_buildings b ON b.building_id = r.building_id
        JOIN housing_assignments a ON a.room_id = r.room_id
        JOIN housing_deposit_deductions d ON d.assignment_id = a.assignment_id
        WHERE d.status IN ('Proposed','Applied')
    '''
    args: list = []
    if building_id:
        sql += " AND r.building_id = ?"
        args.append(building_id)
    sql += " GROUP BY r.room_id HAVING COALESCE(SUM(d.amount), 0) >= ? " \
           "ORDER BY 6 DESC"
    args.append(min_amt)
    try:
        conn = get_connection()
        try:
            rooms = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Damages roll-up failed")
        print(f"Error: {e}")
        return
    if not rooms:
        print("(no rooms with damages above threshold)")
        return
    print(f"\n{'Room':6}  {'Building':24}  {'Type':12}  "
          f"{'Count':>5}  {'Total':>10}  {'Last':<20}")
    print("-" * 80)
    for room_id, rn, bn, rt, cnt, total, last in rooms:
        print(f"{(rn or '')[:6]:6}  {(bn or '')[:24]:24}  "
              f"{(rt or '')[:12]:12}  {cnt:>5}  "
              f"£{float(total or 0):>9,.2f}  {(last or '-')[:20]:<20}")
    drill = _prompt("Drill into Room ID (blank to skip)") or None
    if not drill:
        return
    try:
        conn = get_connection()
        try:
            rows = conn.execute('''
                SELECT d.created_at, d.assignment_id,
                       s.first_name || ' ' || s.last_name,
                       d.description, d.amount, d.status
                FROM housing_deposit_deductions d
                JOIN housing_assignments a ON a.assignment_id = d.assignment_id
                JOIN students s ON s.student_id = a.student_id
                WHERE a.room_id = ?
                ORDER BY d.created_at DESC
            ''', (drill,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Drill-down failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no deductions for that room)")
        return
    for d_at, asg, tenant, desc, amt, stat in rows:
        print(f"  {d_at} · {asg} · {tenant:<22} · "
              f"£{float(amt or 0):>9,.2f} · {stat:<10} · {desc}")


# ── 12. Audit log viewer ──────────────────────────────────────────────

_LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"
    r"\s-\s(?P<level>\w+)\s-\s(?P<logger>[\w\.\-]+)\s-\s(?P<msg>.*)$"
)


def cli_audit_log() -> None:
    _section("Activity / audit log")
    q = _prompt("Filter substring", "housing")
    level = _prompt("Level (any/INFO/WARNING/ERROR/DEBUG/CRITICAL)",
                     "any").upper()
    try:
        cap = int(_prompt("Max rows", "200"))
    except ValueError:
        cap = 200
    log_dir = _resolve_log_dir()
    if not log_dir or not log_dir.is_dir():
        print(f"Log directory not found: {log_dir}")
        return
    files: list[Path] = sorted(log_dir.glob("app.*.log"))
    cur_log = log_dir / "app.log"
    if cur_log.exists():
        files.append(cur_log)
    lines: list[str] = []
    for p in files:
        try:
            with p.open("r", encoding="utf-8", errors="replace") as f:
                lines.extend(line.rstrip("\n") for line in f)
        except OSError:
            logger.exception("Read %s failed", p)
    q_l = q.lower()
    kept = 0
    for raw in reversed(lines):
        m = _LOG_LINE.match(raw)
        if not m:
            continue
        if level != "ANY" and m.group('level') != level:
            continue
        msg = m.group('msg')
        src = m.group('logger')
        if q_l and q_l not in msg.lower() and q_l not in src.lower():
            continue
        print(f"{m.group('ts')}  {m.group('level'):<7}  {src}  {msg}")
        kept += 1
        if kept >= cap:
            break
    print(f"\nShown: {kept} (cap {cap}).")


def _resolve_log_dir() -> Path | None:
    try:
        from education_system.post_18.university_system.core import paths
        ld = getattr(paths, 'LOG_DIR', None)
        if ld:
            return Path(ld)
    except Exception:
        logger.debug("paths module unavailable", exc_info=True)
    return Path("education_system/post_18/university_system/logs")


# ── 13. Roommate finder (staff) ───────────────────────────────────────

def cli_roommate_finder() -> None:
    """The roommate-matching code lives in the GUI module. The CLI
    surrogate is a same-spec query: pick a student, propose roommates
    among other current residents sharing their building/room_type
    preferences, ordered by simple overlap signals.
    """
    _section("Roommate finder (staff)")
    student_id = _prompt("Student ID (applicant)")
    if not student_id:
        return
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            target = conn.execute('''
                SELECT a.preferred_building_id, a.preferred_room_type
                FROM housing_applications a
                WHERE a.student_id = ?
                ORDER BY a.application_date DESC LIMIT 1
            ''', (student_id,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Roommate target lookup failed")
        print(f"Error: {e}")
        return
    if not target:
        print("(no application on file for that student)")
        return
    pref_building, pref_type = target['preferred_building_id'], \
        target['preferred_room_type']
    print(f"Applicant prefs: building={pref_building or 'any'}, "
          f"type={pref_type or 'any'}")
    sql = '''
        SELECT s.student_id,
               s.first_name || ' ' || s.last_name AS name,
               r.room_type, b.building_name,
               r.current_occupants, r.max_occupants, r.room_id
        FROM housing_assignments a
        JOIN students s ON s.student_id = a.student_id
        JOIN housing_rooms r ON r.room_id = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
        WHERE a.status='Active' AND s.student_id != ?
          AND r.current_occupants < r.max_occupants
    '''
    args: list = [student_id]
    if pref_type:
        sql += " AND r.room_type = ?"
        args.append(pref_type)
    if pref_building:
        sql += " AND r.building_id = ?"
        args.append(pref_building)
    sql += " ORDER BY (r.max_occupants - r.current_occupants) DESC, " \
           "b.building_name"
    try:
        conn = get_connection()
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Roommate candidates failed")
        print(f"Error: {e}")
        return
    if not rows:
        print("(no candidate roommates)")
        return
    print(f"\n{'Student ID':>10}  {'Name':<26}  {'Type':<12}  "
          f"{'Building':<24}  {'Free':>4}")
    print("-" * 80)
    for sid, name, rt, bn, cur_occ, max_occ, _rid in rows:
        free = (max_occ or 0) - (cur_occ or 0)
        print(f"{sid:>10}  {name[:26]:<26}  {(rt or '')[:12]:<12}  "
              f"{(bn or '')[:24]:<24}  {free:>4}")


# ── Helpers shared across menus ───────────────────────────────────────

def _pick_building(*, allow_any: bool) -> str | None:
    try:
        conn = get_connection()
        try:
            rows = [(r[0], r[1]) for r in conn.execute(
                "SELECT building_id, building_name FROM housing_buildings "
                "ORDER BY building_name")]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("Building list failed")
        print(f"Error: {e}")
        return None
    if not rows:
        print("(no buildings)")
        return None
    if allow_any:
        print("  0. (any)")
    for i, (_id, name) in enumerate(rows, 1):
        print(f"  {i}. {name}")
    raw = _prompt(f"Pick building 1-{len(rows)}"
                   + (" (0 = any)" if allow_any else ""))
    if not raw.isdigit():
        return None
    n = int(raw)
    if allow_any and n == 0:
        return None
    if 1 <= n <= len(rows):
        return rows[n - 1][0]
    return None
