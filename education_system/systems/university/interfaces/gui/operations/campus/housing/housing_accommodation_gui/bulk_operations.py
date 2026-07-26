"""Bulk operations for housing administration.

Three sections, each its own collapsible card inside one screen so the
admin can switch between operations without re-navigating:

1. Bulk-approve pending applications — picks the first matching
   available room for each selected application and creates a Pending
   assignment.
2. End-of-term mass move-out — terminates a batch of active
   assignments on a chosen date, frees their rooms, and triggers
   waitlist auto-promotion for each.
3. Building-wide rent adjustment — apply a percentage or flat-£ change
   to every room in a building, optionally restricted to a room type.

Each operation runs inside a single SQLite transaction per batch and
collects per-row outcomes so we can show the admin a complete summary
including failures rather than aborting on the first error.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_activity,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation import (
    waitlist as waitlist_service,
)
from education_system.systems.university.domain.operations.campus.housing.services.housing_accommodation.common import (
    generate_id,
)

logger = logging.getLogger(__name__)


# ── Entry point ────────────────────────────────────────────────────────

def show_bulk_operations(gui_instance) -> None:
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Bulk Operations",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True, padx=8, pady=4)

    tab_apps = ttk.Frame(nb, padding=8)
    tab_mout = ttk.Frame(nb, padding=8)
    tab_rent = ttk.Frame(nb, padding=8)
    nb.add(tab_apps, text="Approve Applications")
    nb.add(tab_mout, text="Mass Move-Out")
    nb.add(tab_rent, text="Rent Adjustment")

    _build_bulk_approve(gui_instance, tab_apps)
    _build_mass_moveout(gui_instance, tab_mout)
    _build_rent_adjustment(gui_instance, tab_rent)


# ── 1. Bulk approve applications ───────────────────────────────────────

def _build_bulk_approve(gui_instance, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Tick applications to approve. Each gets the first "
                    "matching available room (preferred building first, "
                    "then any building). Applications with no match are "
                    "skipped — use the Waitlist screen for those."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                       pady=(0, 6))

    cols = ("app_id", "student", "building", "room_type", "applied", "status")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=12,
                         selectmode="extended")
    for k, lbl, w in [
        ("app_id", "Application ID", 140),
        ("student", "Student", 240),
        ("building", "Preferred building", 200),
        ("room_type", "Room type", 110),
        ("applied", "Applied", 110),
        ("status", "Status", 90),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    status_var = tk.StringVar()
    ttk.Label(parent, textvariable=status_var,
              foreground="#666").pack(anchor="w", pady=(4, 0))

    def reload() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            conn = get_connection()
            try:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('''
                    SELECT a.application_id, a.student_id,
                           s.first_name || ' ' || s.last_name AS student_name,
                           COALESCE(b.building_name, '(any building)') AS bname,
                           a.preferred_room_type,
                           a.application_date, a.status
                    FROM housing_applications a
                    LEFT JOIN students          s ON s.student_id = a.student_id
                    LEFT JOIN housing_buildings b ON b.building_id = a.preferred_building_id
                    WHERE a.status IN ('Pending', 'More Info Needed')
                    ORDER BY a.application_date
                ''').fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Bulk approve: load failed")
            messagebox.showerror("Bulk approve",
                                  f"Could not load applications:\n\n{e}",
                                  parent=gui_instance.root)
            return
        for r in rows:
            tree.insert("", "end", iid=r['application_id'], values=(
                r['application_id'],
                f"{r['student_name']} ({r['student_id']})",
                r['bname'], r['preferred_room_type'],
                r['application_date'], r['status'],
            ))
        status_var.set(f"{len(rows)} pending application(s)")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Refresh", command=reload).pack(side="left")
    ttk.Button(bar, text="Select all",
               command=lambda: tree.selection_set(tree.get_children())).pack(
        side="left", padx=4)
    ttk.Button(bar, text="Approve selected →",
               command=lambda: _run_bulk_approve(
                   gui_instance, tree.selection(), reload)).pack(side="right")

    reload()


def _run_bulk_approve(gui_instance, app_ids: tuple,
                      on_done) -> None:
    if not app_ids:
        messagebox.showinfo("Bulk approve",
                            "Select at least one application.",
                            parent=gui_instance.root)
        return
    if not messagebox.askyesno("Bulk approve",
                                f"Approve {len(app_ids)} application(s)?\n\n"
                                "Each will be matched to the first available "
                                "room of the requested type.",
                                parent=gui_instance.root):
        return

    now = datetime.datetime.now().isoformat(timespec='seconds')
    today = datetime.date.today().isoformat()
    plus_year = (datetime.date.today()
                  + datetime.timedelta(days=365)).isoformat()
    who = (gui_instance.auth.current_user.get('username')
            if gui_instance.auth and gui_instance.auth.current_user
            else 'bulk-admin')

    approved: list[str] = []
    no_room: list[str] = []
    errors: list[tuple[str, str]] = []

    try:
        conn = get_connection()
    except sqlite3.Error as e:
        logger.exception("Bulk approve: DB connect failed")
        messagebox.showerror("Bulk approve", f"DB error: {e}",
                              parent=gui_instance.root)
        return

    try:
        for app_id in app_ids:
            try:
                cur = conn.cursor()
                cur.execute('''
                    SELECT student_id, preferred_building_id, preferred_room_type
                    FROM housing_applications
                    WHERE application_id = ?
                ''', (app_id,))
                app = cur.fetchone()
                if not app:
                    errors.append((app_id, "application not found"))
                    continue
                student_id, pref_building, pref_type = app

                room = _find_first_available_room(cur, pref_building, pref_type)
                if room is None:
                    # No room for this app — leave on waitlist via app status.
                    cur.execute('''
                        UPDATE housing_applications
                           SET status='Waiting List', reviewed_by=?,
                               review_date=?, updated_at=?
                         WHERE application_id=?
                    ''', (who, now, now, app_id))
                    no_room.append(app_id)
                    continue

                room_id, _bid, _rn, _floor, _rt, rent = room
                assignment_id = generate_id('ASG')
                cur.execute('''
                    INSERT INTO housing_assignments
                    (assignment_id, application_id, student_id, room_id,
                     move_in_date, planned_move_out_date, monthly_rent,
                     status, assigned_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
                ''', (assignment_id, app_id, student_id, room_id,
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
                       SET status='Approved', reviewed_by=?, review_date=?,
                           updated_at=?
                     WHERE application_id=?
                ''', (who, now, now, app_id))
                approved.append(app_id)
                log_activity(f"Bulk-approved application {app_id} -> "
                             f"assignment {assignment_id} (room {room_id})")
            except sqlite3.Error as e:
                logger.exception("Bulk approve: row %s failed", app_id)
                errors.append((app_id, str(e)))
        conn.commit()
    finally:
        conn.close()

    msg = (f"Approved: {len(approved)}\n"
           f"No matching room (left as Waiting List): {len(no_room)}\n"
           f"Errors: {len(errors)}")
    if errors:
        msg += "\n\nFirst few errors:\n" + "\n".join(
            f"  {a}: {m}" for a, m in errors[:5])
    messagebox.showinfo("Bulk approve — result", msg,
                         parent=gui_instance.root)
    logger.info("Bulk approve summary: approved=%d, no_room=%d, errors=%d",
                len(approved), len(no_room), len(errors))
    on_done()


def _find_first_available_room(cur, building_id: str | None,
                                room_type: str | None) -> tuple | None:
    if building_id:
        cur.execute('''
            SELECT room_id, building_id, room_number, floor_number,
                   room_type, monthly_rent
            FROM housing_rooms
            WHERE building_id = ? AND room_type = ? AND status = 'Available'
            ORDER BY floor_number, room_number LIMIT 1
        ''', (building_id, room_type))
        row = cur.fetchone()
        if row:
            return row
    cur.execute('''
        SELECT room_id, building_id, room_number, floor_number,
               room_type, monthly_rent
        FROM housing_rooms
        WHERE room_type = ? AND status = 'Available'
        ORDER BY building_id, floor_number, room_number LIMIT 1
    ''', (room_type,))
    return cur.fetchone()


# ── 2. Mass move-out ───────────────────────────────────────────────────

def _build_mass_moveout(gui_instance, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Pick a move-out date and tick assignments to "
                    "terminate. Each will be marked Terminated, the room "
                    "freed, and any matching waitlist entry promoted."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                       pady=(0, 6))

    top = ttk.Frame(parent)
    top.pack(fill="x")
    ttk.Label(top, text="Move-out date (YYYY-MM-DD):").pack(side="left",
                                                              padx=(0, 4))
    date_var = tk.StringVar(value=datetime.date.today().isoformat())
    ttk.Entry(top, textvariable=date_var, width=14).pack(side="left",
                                                          padx=(0, 12))
    ttk.Label(top, text="Filter by building:").pack(side="left")
    building_var = tk.StringVar()
    building_combo = ttk.Combobox(top, textvariable=building_var,
                                    state="readonly", width=28)
    building_combo.pack(side="left", padx=(4, 0))
    buildings = _load_buildings()
    building_combo['values'] = ["(any)"] + [b[1] for b in buildings]
    building_combo.current(0)

    cols = ("asg", "student", "room", "building", "move_in")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=12,
                         selectmode="extended")
    for k, lbl, w in [
        ("asg", "Assignment", 140),
        ("student", "Student", 240),
        ("room", "Room", 80),
        ("building", "Building", 220),
        ("move_in", "Move-in", 100),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=4)

    status_var = tk.StringVar()
    ttk.Label(parent, textvariable=status_var,
              foreground="#666").pack(anchor="w")

    def reload() -> None:
        for i in tree.get_children():
            tree.delete(i)
        bsel = building_combo.current()
        b_id = buildings[bsel - 1][0] if bsel > 0 else None
        sql = '''
            SELECT a.assignment_id, a.student_id,
                   s.first_name || ' ' || s.last_name,
                   r.room_number, b.building_name, a.move_in_date,
                   r.room_id
            FROM housing_assignments a
            JOIN students s ON s.student_id = a.student_id
            JOIN housing_rooms r ON r.room_id = a.room_id
            JOIN housing_buildings b ON b.building_id = r.building_id
            WHERE a.status = 'Active' AND a.actual_move_out_date IS NULL
        '''
        args: list = []
        if b_id:
            sql += " AND b.building_id = ?"
            args.append(b_id)
        sql += " ORDER BY b.building_name, r.room_number"
        try:
            conn = get_connection()
            try:
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Mass move-out: load failed")
            messagebox.showerror("Mass move-out",
                                  f"Could not load assignments:\n\n{e}",
                                  parent=gui_instance.root)
            return
        for asg_id, sid, sname, rn, bn, mi, rid in rows:
            tree.insert("", "end", iid=asg_id,
                        values=(asg_id, f"{sname} ({sid})", rn, bn, mi))
            # Cache the room id for the finaliser.
            tree.set(asg_id, "_room_id", rid) if False else None
        status_var.set(f"{len(rows)} active assignment(s)")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Refresh", command=reload).pack(side="left")
    ttk.Button(bar, text="Select all",
               command=lambda: tree.selection_set(tree.get_children())).pack(
        side="left", padx=4)
    ttk.Button(bar, text="Finalise selected →",
               command=lambda: _run_mass_moveout(
                   gui_instance, tree.selection(),
                   date_var.get().strip(), reload)).pack(side="right")

    reload()


def _run_mass_moveout(gui_instance, asg_ids: tuple,
                      move_out_date: str, on_done) -> None:
    if not asg_ids:
        messagebox.showinfo("Mass move-out",
                            "Select at least one assignment.",
                            parent=gui_instance.root)
        return
    try:
        datetime.date.fromisoformat(move_out_date)
    except ValueError:
        messagebox.showwarning("Mass move-out",
                                "Move-out date must be YYYY-MM-DD.",
                                parent=gui_instance.root)
        return
    if not messagebox.askyesno("Mass move-out",
                                f"Terminate {len(asg_ids)} assignment(s) "
                                f"with move-out date {move_out_date}?\n\n"
                                "Issued refunds and deductions are NOT "
                                "processed here — finalise individually if "
                                "deposits need handling.",
                                parent=gui_instance.root):
        return

    now = datetime.datetime.now().isoformat(timespec='seconds')
    finalised: list[str] = []
    promoted: list[dict[str, Any]] = []
    errors: list[tuple[str, str]] = []

    try:
        conn = get_connection()
    except sqlite3.Error as e:
        logger.exception("Mass move-out: DB connect failed")
        messagebox.showerror("Mass move-out", f"DB error: {e}",
                              parent=gui_instance.root)
        return

    room_ids: list[str] = []
    try:
        cur = conn.cursor()
        for asg_id in asg_ids:
            try:
                cur.execute(
                    "SELECT room_id FROM housing_assignments "
                    "WHERE assignment_id = ?", (asg_id,))
                r = cur.fetchone()
                if not r:
                    errors.append((asg_id, "assignment not found"))
                    continue
                room_id = r[0]
                cur.execute('''
                    UPDATE housing_assignments
                       SET status='Terminated', actual_move_out_date=?,
                           updated_at=?
                     WHERE assignment_id=?
                ''', (move_out_date, now, asg_id))
                cur.execute('''
                    UPDATE housing_rooms
                       SET status='Available',
                           current_occupants = MAX(0, current_occupants - 1),
                           updated_at=?
                     WHERE room_id=?
                ''', (now, room_id))
                finalised.append(asg_id)
                room_ids.append(room_id)
            except sqlite3.Error as e:
                logger.exception("Mass move-out: row %s failed", asg_id)
                errors.append((asg_id, str(e)))
        conn.commit()
    finally:
        conn.close()

    # Now run waitlist promotion outside the main loop so its own
    # transaction failures don't unwind the move-outs.
    for rid in room_ids:
        try:
            summary = waitlist_service.promote_room_to_next(
                rid,
                created_by=(gui_instance.auth.current_user.get('username')
                            if gui_instance.auth and gui_instance.auth.current_user
                            else 'bulk-admin'))
            if summary:
                promoted.append(summary)
        except Exception:
            logger.exception("Promotion failed during mass move-out for "
                              "room %s", rid)

    for asg_id in finalised:
        log_activity(f"Mass move-out: {asg_id} terminated "
                     f"({move_out_date})")

    msg = (f"Terminated: {len(finalised)}\n"
           f"Waitlist auto-promotions: {len(promoted)}\n"
           f"Errors: {len(errors)}")
    if errors:
        msg += "\n\nFirst few errors:\n" + "\n".join(
            f"  {a}: {m}" for a, m in errors[:5])
    messagebox.showinfo("Mass move-out — result", msg,
                         parent=gui_instance.root)
    logger.info("Mass move-out summary: finalised=%d, promoted=%d, errors=%d",
                len(finalised), len(promoted), len(errors))
    on_done()


# ── 3. Building-wide rent adjustment ───────────────────────────────────

def _build_rent_adjustment(gui_instance, parent: ttk.Frame) -> None:
    ttk.Label(parent,
              text=("Choose a building (and optionally a room type) "
                    "then a percentage or flat-£ change. New rents are "
                    "rounded to 2dp; future bookings use the new rate. "
                    "Existing assignments keep their own monthly_rent "
                    "unless you re-issue contracts."),
              wraplength=820, foreground="#555").pack(anchor="w",
                                                       pady=(0, 6))

    row = ttk.Frame(parent)
    row.pack(fill="x", pady=4)
    ttk.Label(row, text="Building:").pack(side="left", padx=(0, 4))
    building_var = tk.StringVar()
    building_combo = ttk.Combobox(row, textvariable=building_var,
                                    state="readonly", width=30)
    buildings = _load_buildings()
    building_combo['values'] = [b[1] for b in buildings]
    if buildings:
        building_combo.current(0)
    building_combo.pack(side="left", padx=(0, 12))

    ttk.Label(row, text="Room type (optional):").pack(side="left")
    type_var = tk.StringVar()
    type_combo = ttk.Combobox(row, textvariable=type_var,
                                state="readonly", width=18)
    type_combo['values'] = ["(all)"] + _load_room_types()
    type_combo.current(0)
    type_combo.pack(side="left", padx=(4, 12))

    row2 = ttk.Frame(parent)
    row2.pack(fill="x", pady=4)
    mode_var = tk.StringVar(value="percent")
    ttk.Radiobutton(row2, text="Percent change (e.g. 5 = +5%)",
                    variable=mode_var, value="percent").pack(side="left",
                                                              padx=4)
    ttk.Radiobutton(row2, text="Flat £ change (e.g. -25 = £25 off)",
                    variable=mode_var, value="flat").pack(side="left",
                                                            padx=4)

    row3 = ttk.Frame(parent)
    row3.pack(fill="x", pady=4)
    ttk.Label(row3, text="Amount:").pack(side="left", padx=(0, 4))
    amt_var = tk.StringVar()
    ttk.Entry(row3, textvariable=amt_var, width=12).pack(side="left",
                                                          padx=(0, 12))

    preview_var = tk.StringVar()
    ttk.Label(parent, textvariable=preview_var,
              foreground="#444").pack(anchor="w", pady=(6, 4))

    def _selected_building_id() -> str | None:
        idx = building_combo.current()
        return buildings[idx][0] if idx >= 0 and idx < len(buildings) else None

    def _selected_room_type() -> str | None:
        return type_var.get() if type_combo.current() > 0 else None

    def preview() -> None:
        b_id = _selected_building_id()
        if not b_id:
            preview_var.set("Pick a building first.")
            return
        try:
            amt = float(amt_var.get().strip())
        except ValueError:
            preview_var.set("Amount must be numeric.")
            return
        try:
            conn = get_connection()
            try:
                sql = ("SELECT room_id, monthly_rent FROM housing_rooms "
                       "WHERE building_id = ?")
                args: list = [b_id]
                rt = _selected_room_type()
                if rt:
                    sql += " AND room_type = ?"
                    args.append(rt)
                rows = conn.execute(sql, args).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Rent preview query failed")
            messagebox.showerror("Rent adjustment",
                                  f"Could not load rooms:\n\n{e}",
                                  parent=gui_instance.root)
            return
        if not rows:
            preview_var.set("No matching rooms.")
            return
        new_total = 0.0
        old_total = 0.0
        for _rid, cur_rent in rows:
            cur_f = float(cur_rent or 0)
            new_f = (cur_f * (1 + amt / 100)) if mode_var.get() == 'percent' \
                else (cur_f + amt)
            new_f = round(max(0.0, new_f), 2)
            old_total += cur_f
            new_total += new_f
        preview_var.set(
            f"{len(rows)} room(s) affected · "
            f"old monthly roll £{old_total:,.2f} → "
            f"new £{new_total:,.2f} "
            f"(Δ £{new_total - old_total:+,.2f})")

    def apply() -> None:
        b_id = _selected_building_id()
        if not b_id:
            messagebox.showinfo("Rent adjustment", "Pick a building first.",
                                 parent=gui_instance.root)
            return
        try:
            amt = float(amt_var.get().strip())
        except ValueError:
            messagebox.showwarning("Rent adjustment",
                                    "Amount must be numeric.",
                                    parent=gui_instance.root)
            return
        rt = _selected_room_type()
        if not messagebox.askyesno(
                "Rent adjustment",
                ("Apply " +
                 (f"{amt:+.2f}% change" if mode_var.get() == 'percent'
                  else f"£{amt:+.2f} flat change") +
                 (f" to all {rt} rooms" if rt else " to all rooms") +
                 f" in {building_var.get()}?"),
                parent=gui_instance.root):
            return

        now = datetime.datetime.now().isoformat(timespec='seconds')
        updated = 0
        skipped = 0
        try:
            conn = get_connection()
            try:
                cur = conn.cursor()
                sql = ("SELECT room_id, monthly_rent FROM housing_rooms "
                       "WHERE building_id = ?")
                args: list = [b_id]
                if rt:
                    sql += " AND room_type = ?"
                    args.append(rt)
                rows = cur.execute(sql, args).fetchall()
                for rid, cur_rent in rows:
                    cur_f = float(cur_rent or 0)
                    new_f = (cur_f * (1 + amt / 100)) \
                        if mode_var.get() == 'percent' \
                        else (cur_f + amt)
                    new_f = round(max(0.0, new_f), 2)
                    if abs(new_f - cur_f) < 0.005:
                        skipped += 1
                        continue
                    cur.execute(
                        "UPDATE housing_rooms SET monthly_rent=?, "
                        "updated_at=? WHERE room_id=?",
                        (new_f, now, rid))
                    updated += 1
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Rent adjustment apply failed")
            messagebox.showerror("Rent adjustment",
                                  f"Could not apply:\n\n{e}",
                                  parent=gui_instance.root)
            return

        log_activity(f"Bulk rent adjustment in {building_var.get()}"
                     + (f" / {rt}" if rt else "")
                     + f": mode={mode_var.get()}, amount={amt}, "
                     f"updated={updated}, skipped={skipped}")
        messagebox.showinfo("Rent adjustment",
                             f"Updated {updated} room(s). "
                             f"Skipped {skipped} (no change).",
                             parent=gui_instance.root)
        preview()

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(4, 0))
    ttk.Button(bar, text="Preview", command=preview).pack(side="left")
    ttk.Button(bar, text="Apply →", command=apply).pack(side="right")


# ── Shared helpers ─────────────────────────────────────────────────────

def _load_buildings() -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        try:
            return [(r[0], r[1]) for r in conn.execute(
                "SELECT building_id, building_name "
                "FROM housing_buildings ORDER BY building_name")]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load buildings")
        return []


def _load_room_types() -> list[str]:
    try:
        conn = get_connection()
        try:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT room_type FROM housing_rooms "
                "WHERE room_type IS NOT NULL ORDER BY room_type")]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not load room types")
        return []
