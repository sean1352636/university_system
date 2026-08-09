"""Seating tab — layout management, allocation, visual chart, exports.

Pass 2 of the exam-seating feature. The backend service in
exam_management.seating handles all writes and the allocation algorithm; this
tab is a thin form + a Canvas grid that visualises layouts and allocations.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.academics.domain.services.exam_management import seating as _seating

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

def _export_pdf(exam_id, filepath, layout, allocations_by_seat, room_label):
    """Render the chart to PDF via reportlab. Falls back to .ps if unavailable."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.units import mm
    except ImportError:
        return False

    rows_n, cols_n = layout['rows_n'], layout['cols_n']
    seats = {(s['row_n'], s['col_n']): s for s in layout['seats']}

    page_w, page_h = landscape(A4)
    margin = 15 * mm
    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin - 25 * mm  # header room

    cell_w = usable_w / (cols_n + 1)  # +1 for row-letter column
    cell_h = min(usable_h / (rows_n + 2), cell_w)  # +2 = header + spacing

    c = pdf_canvas.Canvas(filepath, pagesize=landscape(A4))
    c.setTitle(f"Seating chart — exam {exam_id}")

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, page_h - margin, f"Seating Plan — Exam {exam_id}")
    c.setFont("Helvetica", 10)
    c.drawString(margin, page_h - margin - 14,
                 f"Room: {room_label}   ·   Grid: {rows_n} rows × {cols_n} cols")
    c.drawString(margin, page_h - margin - 26,
                 "Legend:  [W] wheelchair-accessible    [L] left-handed    "
                 "[X] out-of-service    [—] unassigned")

    top_y = page_h - margin - 40
    # Column headers
    c.setFont("Helvetica-Bold", 9)
    for col in range(1, cols_n + 1):
        x = margin + col * cell_w
        c.drawString(x + cell_w / 2 - 3, top_y, str(col))
    # Rows
    for r in range(1, rows_n + 1):
        y = top_y - r * cell_h
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin + cell_w / 2 - 3, y + cell_h / 3,
                     _seating._row_letter(r))
        for col in range(1, cols_n + 1):
            x = margin + col * cell_w
            seat = seats.get((r, col))
            if not seat:
                continue
            # Box
            if seat['is_disabled']:
                c.setFillColorRGB(0.85, 0.85, 0.85)
                c.rect(x, y, cell_w - 2, cell_h - 2, fill=1, stroke=1)
                c.setFillColorRGB(0, 0, 0)
                c.setFont("Helvetica", 8)
                c.drawString(x + 3, y + cell_h / 2 - 3, f"{seat['seat_label']}  X")
                continue
            allocation = allocations_by_seat.get(seat['seat_id'])
            if allocation:
                c.setFillColorRGB(0.78, 0.92, 0.78)  # green for occupied
            else:
                c.setFillColorRGB(1, 1, 1)
            c.rect(x, y, cell_w - 2, cell_h - 2, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(x + 3, y + cell_h - 12, seat['seat_label'])
            tag = []
            if seat['is_accessible']:
                tag.append('W')
            if seat['is_left_handed']:
                tag.append('L')
            if tag:
                c.setFont("Helvetica", 7)
                c.drawString(x + cell_w - 18, y + cell_h - 12, ''.join(tag))
            if allocation:
                c.setFont("Helvetica", 8)
                c.drawString(x + 3, y + cell_h / 2 - 4,
                             str(allocation['student_id'])[:14])
                if allocation['accommodation_notes']:
                    c.setFont("Helvetica-Oblique", 6)
                    c.drawString(x + 3, y + 4,
                                 allocation['accommodation_notes'][:22])
            else:
                c.setFont("Helvetica", 9)
                c.drawString(x + cell_w / 2 - 4, y + cell_h / 2 - 4, '—')

    c.showPage()
    c.save()
    return True


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class SeatingTabMixin:
    """Adds a 'Seating' tab to the exam scheduler app."""

    # ── State ────────────────────────────────────────────────────────
    _seating_state = None  # set in create_seating_tab

    def create_seating_tab(self):
        try:
            _seating.init_seating_db()
        except Exception:
            logger.exception("seating init failed")

        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=_t('gui.academics.exam_management.tabs.seating_tab.tabs.seating', default="Seating"))

        self._seating_state = {
            'exam_id': None,
            'layout': None,
            'room_id': None,
            'room_label': None,
            'allocations_by_seat': {},
            'invigilators': [],
            'seat_screen_boxes': {},  # seat_id → (x1,y1,x2,y2)
        }

        # Top controls
        top = ttk.Frame(tab)
        top.pack(fill='x', pady=(0, 8))

        ttk.Label(top, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.exam', default="Exam:")).pack(side='left', padx=(0, 4))
        self._seating_exam_combo = ttk.Combobox(top, width=70, state='readonly')
        self._seating_exam_combo.pack(side='left', padx=4)
        ttk.Button(top, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.reload_exams', default="Reload exams"),
                   command=self._seating_load_exam_options).pack(side='left', padx=4)
        self._seating_load_exam_options()
        self._seating_exam_combo.bind(
            '<<ComboboxSelected>>', lambda _e: self._seating_on_exam_selected())

        # Action row
        actions = ttk.Frame(tab)
        actions.pack(fill='x', pady=(0, 8))

        ttk.Label(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.policy', default="Policy:")).pack(side='left', padx=(0, 4))
        self._seating_policy = ttk.Combobox(
            actions, values=list(_seating.POLICIES), state='readonly', width=14)
        self._seating_policy.set('alphabetical')
        self._seating_policy.pack(side='left', padx=4)

        ttk.Button(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.define_edit_layout', default="Define / Edit Layout"),
                   command=self._seating_define_layout).pack(side='left', padx=4)
        ttk.Button(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.auto_allocate', default="Auto-allocate"),
                   command=self._seating_auto_allocate).pack(side='left', padx=4)
        ttk.Button(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.clear_allocation', default="Clear allocation"),
                   command=self._seating_clear_allocation).pack(side='left', padx=4)
        ttk.Button(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.export_csv', default="Export CSV"),
                   command=self._seating_export_csv).pack(side='left', padx=4)
        ttk.Button(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.export_pdf', default="Export PDF"),
                   command=self._seating_export_pdf).pack(side='left', padx=4)
        ttk.Button(actions, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.invigilator_zones', default="Invigilator zones…"),
                   command=self._seating_zones_dialog).pack(side='left', padx=4)

        # Status line
        self._seating_status = ttk.Label(tab, text="", foreground='#444')
        self._seating_status.pack(fill='x', pady=(0, 4))

        # Canvas with scrollbars
        body = ttk.Frame(tab)
        body.pack(fill='both', expand=True)
        self._seating_canvas = tk.Canvas(body, background='#ffffff',
                                         highlightthickness=1,
                                         highlightbackground='#888')
        vsb = ttk.Scrollbar(body, orient='vertical',
                            command=self._seating_canvas.yview)
        hsb = ttk.Scrollbar(body, orient='horizontal',
                            command=self._seating_canvas.xview)
        self._seating_canvas.configure(yscrollcommand=vsb.set,
                                       xscrollcommand=hsb.set)
        self._seating_canvas.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self._seating_canvas.bind('<Button-1>', self._seating_on_canvas_click)

    # ── Data plumbing ────────────────────────────────────────────────

    def _seating_load_exam_options(self):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT id, module_code, COALESCE(module_name, ''),
                       date, room
                FROM exams
                ORDER BY date DESC, start_time DESC
                LIMIT 200
            ''')
            rows = cur.fetchall()
        finally:
            conn.close()
        self._seating_exam_options = rows
        self._seating_exam_combo['values'] = [
            f"[{eid}] {code} {name[:32]} — {date} ({room or '—'})"
            for eid, code, name, date, room in rows
        ]

    def _seating_on_exam_selected(self):
        idx = self._seating_exam_combo.current()
        if idx < 0 or idx >= len(getattr(self, '_seating_exam_options', [])):
            return
        eid = self._seating_exam_options[idx][0]
        self._seating_state['exam_id'] = eid
        self._seating_refresh()

    def _seating_refresh(self):
        st = self._seating_state
        eid = st['exam_id']
        if not eid:
            self._seating_status.config(text="")
            self._seating_canvas.delete('all')
            return
        conn = get_connection()
        try:
            cur = conn.cursor()
            room_id, room_label = _seating._resolve_room_id(cur, eid)
            st['room_id'] = room_id
            st['room_label'] = room_label
        finally:
            conn.close()
        if not room_id:
            self._seating_status.config(
                text=f"Exam {eid}: room '{room_label or '—'}' not found in rooms table. "
                     f"Edit the exam to point to a registered room.")
            self._seating_canvas.delete('all')
            st['layout'] = None
            return
        layout = _seating.get_layout(room_id)
        st['layout'] = layout
        allocations = _seating.list_allocations(eid)
        zones = _seating.list_zones(eid)
        st['invigilators'] = zones
        # Map seat_id → row (joined back to layout's seats list)
        if layout:
            seat_id_by_label = {s['seat_label']: s for s in layout['seats']}
            alloc_by_seat = {}
            for a in allocations:
                # Find the seat_id for this seat_label.
                s = seat_id_by_label.get(a['seat_label'])
                if s:
                    alloc_by_seat[s['seat_id']] = a
            st['allocations_by_seat'] = alloc_by_seat
            self._seating_status.config(
                text=f"Room: {room_label} ({layout['rows_n']}×{layout['cols_n']}, "
                     f"{layout['seats_total']} usable). Allocated: {len(allocations)}. "
                     f"Zones: {len(zones)}.")
        else:
            st['allocations_by_seat'] = {}
            self._seating_status.config(
                text=f"Room: {room_label} — no layout defined yet. "
                     f"Click 'Define / Edit Layout'.")
        self._seating_redraw()

    # ── Canvas drawing ───────────────────────────────────────────────

    _CELL = 90  # pixels per seat
    _CELL_H = 60
    _MARGIN = 30

    def _seating_redraw(self):
        canvas = self._seating_canvas
        canvas.delete('all')
        st = self._seating_state
        st['seat_screen_boxes'] = {}
        layout = st['layout']
        if not layout:
            canvas.create_text(20, 20, anchor='nw',
                               text="(no layout — define one to begin)",
                               fill='#888')
            return
        rows_n, cols_n = layout['rows_n'], layout['cols_n']
        m = self._MARGIN
        cw, ch = self._CELL, self._CELL_H

        # Column headers
        for c in range(1, cols_n + 1):
            x = m + c * cw + cw / 2
            canvas.create_text(x, m + 8, text=str(c),
                               font=('Arial', 10, 'bold'))
        # Row letters + seats
        for r in range(1, rows_n + 1):
            y = m + r * ch + 12
            canvas.create_text(m + cw / 2, y + ch / 2,
                               text=_seating._row_letter(r),
                               font=('Arial', 10, 'bold'))
            for c in range(1, cols_n + 1):
                x = m + c * cw
                seat = next((s for s in layout['seats']
                             if s['row_n'] == r and s['col_n'] == c), None)
                if not seat:
                    continue
                x1, y1, x2, y2 = x + 4, y + 4, x + cw - 4, y + ch - 4
                allocation = st['allocations_by_seat'].get(seat['seat_id'])
                if seat['is_disabled']:
                    fill, outline = '#dddddd', '#999'
                elif allocation:
                    fill, outline = '#cfe9cf', '#3a7d3a'
                elif seat['is_accessible']:
                    fill, outline = '#cfe0f5', '#3a6ab0'
                elif seat['is_left_handed']:
                    fill, outline = '#f6e1c0', '#a26a1f'
                else:
                    fill, outline = '#ffffff', '#666'
                canvas.create_rectangle(x1, y1, x2, y2,
                                        fill=fill, outline=outline, width=1)
                st['seat_screen_boxes'][seat['seat_id']] = (x1, y1, x2, y2)
                # Seat label
                canvas.create_text(x1 + 6, y1 + 4, anchor='nw',
                                   text=seat['seat_label'],
                                   font=('Arial', 9, 'bold'))
                # Markers
                markers = []
                if seat['is_accessible']:
                    markers.append('W')
                if seat['is_left_handed']:
                    markers.append('L')
                if seat['is_disabled']:
                    markers.append('X')
                if markers:
                    canvas.create_text(x2 - 6, y1 + 4, anchor='ne',
                                       text=''.join(markers),
                                       font=('Arial', 8), fill='#444')
                # Student
                if allocation:
                    canvas.create_text(
                        (x1 + x2) / 2, (y1 + y2) / 2 + 4,
                        text=str(allocation['student_id'])[:14],
                        font=('Arial', 9))
                    if allocation['accommodation_notes']:
                        canvas.create_text(
                            (x1 + x2) / 2, y2 - 8,
                            text=allocation['accommodation_notes'][:18],
                            font=('Arial', 7, 'italic'), fill='#444')
                elif not seat['is_disabled']:
                    canvas.create_text(
                        (x1 + x2) / 2, (y1 + y2) / 2 + 4,
                        text='—', font=('Arial', 11), fill='#aaa')

        total_w = m * 2 + (cols_n + 1) * cw
        total_h = m * 2 + (rows_n + 1) * ch + 12
        canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _seating_on_canvas_click(self, event):
        """Click a seat → toggle attributes (out-of-service / accessible / left-handed)
        if no allocation, or reassign student if allocated."""
        st = self._seating_state
        if not st['layout']:
            return
        cx = self._seating_canvas.canvasx(event.x)
        cy = self._seating_canvas.canvasy(event.y)
        for seat_id, (x1, y1, x2, y2) in st['seat_screen_boxes'].items():
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                self._seating_seat_menu(seat_id)
                return

    def _seating_seat_menu(self, seat_id):
        st = self._seating_state
        seat = next((s for s in st['layout']['seats']
                     if s['seat_id'] == seat_id), None)
        if not seat:
            return
        allocation = st['allocations_by_seat'].get(seat_id)

        win = tk.Toplevel(self.notebook)
        win.title(f"Seat {seat['seat_label']}")
        win.transient(self.notebook.winfo_toplevel())

        info = (
            f"Seat: {seat['seat_label']} "
            f"(row {seat['row_n']}, col {seat['col_n']})\n"
            f"Accessible: {'yes' if seat['is_accessible'] else 'no'}    "
            f"Left-handed: {'yes' if seat['is_left_handed'] else 'no'}    "
            f"Out-of-service: {'yes' if seat['is_disabled'] else 'no'}"
        )
        ttk.Label(win, text=info, justify='left').pack(padx=10, pady=8)

        if allocation:
            ttk.Label(
                win, foreground='#0a7a2f',
                text=f"Allocated to {allocation['student_id']}"
                     + (f" — {allocation['accommodation_notes']}"
                        if allocation['accommodation_notes'] else "")
            ).pack(padx=10)
        else:
            ttk.Label(win, foreground='#888',
                      text=_t('gui.academics.exam_management.tabs.seating_tab.labels.unallocated', default="Unallocated")).pack(padx=10)

        btns = ttk.Frame(win)
        btns.pack(padx=10, pady=10)

        def reassign():
            new_sid = simpledialog.askstring(
                _t('gui.academics.exam_management.tabs.seating_tab.dialogs.reassign', default="Reassign"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.student_id_for_this_seat_blank_to_clear', default="Student ID for this seat "
                "(blank to clear):"), parent=win)
            if new_sid is None:
                return
            new_sid = new_sid.strip() or None
            conn = get_connection()
            try:
                cur = conn.cursor()
                eid = st['exam_id']
                if new_sid is None:
                    cur.execute(
                        'DELETE FROM exam_seat_allocations '
                        'WHERE exam_id=? AND seat_id=?', (eid, seat_id))
                else:
                    # Clear any other seat this student holds for this exam.
                    cur.execute(
                        'DELETE FROM exam_seat_allocations '
                        'WHERE exam_id=? AND student_id=?', (eid, new_sid))
                    cur.execute(
                        'DELETE FROM exam_seat_allocations '
                        'WHERE exam_id=? AND seat_id=?', (eid, seat_id))
                    import datetime as _dt
                    ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cur.execute('''
                        INSERT INTO exam_seat_allocations
                        (exam_id, student_id, seat_id, accommodation_notes, created_at)
                        VALUES (?, ?, ?, NULL, ?)
                    ''', (eid, new_sid, seat_id, ts))
                conn.commit()
            finally:
                conn.close()
            win.destroy()
            self._seating_refresh()

        def toggle_attr(column, label):
            new_val = 0 if seat[column.replace('is_', '')
                              if False else  # just use raw name
                              column.split('_', 1)[1]] else 1
            # Robust mapping:
            field_map = {'is_accessible': 'is_accessible',
                         'is_left_handed': 'is_left_handed',
                         'is_disabled': 'is_disabled'}
            key = column.split('is_', 1)[1] if column.startswith('is_') else column
            current = bool(seat[{'accessible': 'is_accessible',
                                 'left_handed': 'is_left_handed',
                                 'disabled': 'is_disabled'}.get(key, key)])
            new_val = 0 if current else 1
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    f'UPDATE exam_seats SET {column} = ? WHERE seat_id = ?',
                    (new_val, seat_id))
                conn.commit()
            finally:
                conn.close()
            win.destroy()
            self._seating_refresh()

        ttk.Button(btns, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.reassign_clear_student', default="Reassign / clear student"),
                   command=reassign).pack(side='left', padx=4)
        ttk.Button(btns, text=("Mark in-service" if seat['is_disabled']
                               else "Mark out-of-service"),
                   command=lambda: toggle_attr('is_disabled', 'disabled')).pack(
            side='left', padx=4)
        ttk.Button(btns, text=("Remove accessibility" if seat['is_accessible']
                               else "Mark accessible"),
                   command=lambda: toggle_attr('is_accessible', 'accessible')).pack(
            side='left', padx=4)
        ttk.Button(btns, text=("Remove left-handed" if seat['is_left_handed']
                               else "Mark left-handed"),
                   command=lambda: toggle_attr(
                       'is_left_handed', 'left_handed')).pack(side='left', padx=4)
        ttk.Button(btns, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.close', default="Close"),
                   command=win.destroy).pack(side='right', padx=4)

    # ── Actions ──────────────────────────────────────────────────────

    def _seating_define_layout(self):
        st = self._seating_state
        room_id = st['room_id']
        if not room_id:
            messagebox.showwarning(
                _t('gui.academics.exam_management.tabs.seating_tab.dialogs.no_room', default="No room"),
                _t('gui.academics.exam_management.tabs.seating_tab.dialogs.select_an_exam_first_its_room_is_used_as_the_layout_target', default="Select an exam first — its room is used as the layout target."))
            return

        existing = _seating.get_layout(room_id)
        win = tk.Toplevel(self.notebook)
        win.title(f"Layout for room {st['room_label']}")
        win.transient(self.notebook.winfo_toplevel())

        ttk.Label(win, text=f"Room: {st['room_label']}",
                  font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=10, pady=(10, 4))

        ttk.Label(win, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.rows', default="Rows:")).grid(row=1, column=0, sticky='e', padx=8, pady=4)
        rows_e = ttk.Entry(win, width=8)
        rows_e.grid(row=1, column=1, sticky='w', padx=8, pady=4)
        rows_e.insert(0, str(existing['rows_n']) if existing else '8')

        ttk.Label(win, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.cols', default="Cols:")).grid(row=2, column=0, sticky='e', padx=8, pady=4)
        cols_e = ttk.Entry(win, width=8)
        cols_e.grid(row=2, column=1, sticky='w', padx=8, pady=4)
        cols_e.insert(0, str(existing['cols_n']) if existing else '10')

        ttk.Label(win, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.accessible_csv_labels', default="Accessible (CSV labels):")).grid(
            row=3, column=0, sticky='e', padx=8, pady=4)
        acc_e = ttk.Entry(win, width=40)
        acc_e.grid(row=3, column=1, sticky='w', padx=8, pady=4)
        ttk.Label(win, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.left_handed_csv_labels', default="Left-handed (CSV labels):")).grid(
            row=4, column=0, sticky='e', padx=8, pady=4)
        lh_e = ttk.Entry(win, width=40)
        lh_e.grid(row=4, column=1, sticky='w', padx=8, pady=4)
        ttk.Label(win, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.out_of_service_csv_labels', default="Out-of-service (CSV labels):")).grid(
            row=5, column=0, sticky='e', padx=8, pady=4)
        dis_e = ttk.Entry(win, width=40)
        dis_e.grid(row=5, column=1, sticky='w', padx=8, pady=4)

        if existing:
            acc_e.insert(0, ','.join(s['seat_label'] for s in existing['seats']
                                     if s['is_accessible']))
            lh_e.insert(0, ','.join(s['seat_label'] for s in existing['seats']
                                    if s['is_left_handed']))
            dis_e.insert(0, ','.join(s['seat_label'] for s in existing['seats']
                                     if s['is_disabled']))

        def save():
            try:
                rows_n = int(rows_e.get())
                cols_n = int(cols_e.get())
            except ValueError:
                messagebox.showerror(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.invalid', default="Invalid"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.rows_and_cols_must_be_integers', default="Rows and cols must be integers."),
                                     parent=win)
                return
            acc = {tok.strip().upper() for tok in acc_e.get().split(',') if tok.strip()}
            lh = {tok.strip().upper() for tok in lh_e.get().split(',') if tok.strip()}
            dis = {tok.strip().upper() for tok in dis_e.get().split(',') if tok.strip()}
            try:
                _seating.define_room_layout(
                    room_id, rows_n, cols_n,
                    accessible_seats=acc, left_handed_seats=lh,
                    disabled_seats=dis,
                )
            except (ValueError, RuntimeError) as e:
                messagebox.showerror(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.cannot_save', default="Cannot save"), str(e), parent=win)
                return
            win.destroy()
            self._seating_refresh()
            messagebox.showinfo(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.saved', default="Saved"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.layout_saved', default="Layout saved."))

        ttk.Button(win, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.save', default="Save"), command=save).grid(
            row=6, column=0, columnspan=2, pady=10)

    def _seating_auto_allocate(self):
        st = self._seating_state
        if not st['exam_id']:
            messagebox.showwarning(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.select', default="Select"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.pick_an_exam_first', default="Pick an exam first."))
            return
        if not st['layout']:
            messagebox.showwarning(
                _t('gui.academics.exam_management.tabs.seating_tab.dialogs.no_layout', default="No layout"),
                _t('gui.academics.exam_management.tabs.seating_tab.dialogs.define_a_layout_for_this_room_before_allocating_seats', default="Define a layout for this room before allocating seats."))
            return
        policy = self._seating_policy.get()
        if not messagebox.askyesno(
            _t('gui.academics.exam_management.tabs.seating_tab.dialogs.allocate', default="Allocate?"),
            f"Run auto-allocation with policy '{policy}'?\n\n"
            "This clears any existing allocation for the exam first."):
            return
        try:
            result = _seating.auto_allocate(st['exam_id'], policy=policy)
        except ValueError as e:
            messagebox.showerror(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.error', default="Error"), str(e))
            return
        lines = [
            f"Allocated: {result['allocated']}",
            f"Unallocated: {len(result['unallocated'])}",
        ]
        for sid, reason in result['unallocated'][:8]:
            lines.append(f"  - {sid}: {reason}")
        if len(result['unallocated']) > 8:
            lines.append(f"  …and {len(result['unallocated']) - 8} more.")
        for w in result['warnings']:
            lines.append(f"⚠ {w}")
        messagebox.showinfo(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.allocation_result', default="Allocation result"), "\n".join(lines))
        self._seating_refresh()

    def _seating_clear_allocation(self):
        st = self._seating_state
        if not st['exam_id']:
            return
        if not messagebox.askyesno(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.clear', default="Clear"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.clear_all_allocations_for_this_exam', default="Clear all allocations for this exam?")):
            return
        n = _seating.clear_allocation(st['exam_id'])
        messagebox.showinfo(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.cleared', default="Cleared"), f"Removed {n} allocation(s).")
        self._seating_refresh()

    def _seating_export_csv(self):
        st = self._seating_state
        if not st['exam_id'] or not st['layout']:
            messagebox.showwarning(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.nothing_to_export', default="Nothing to export"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.pick_an_exam_with_a_layout', default="Pick an exam with a layout."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            initialfile=f"exam_{st['exam_id']}_seating.csv",
            filetypes=[('CSV files', '*.csv')])
        if not path:
            return
        try:
            n = _seating.export_chart_csv(st['exam_id'], path)
        except RuntimeError as e:
            messagebox.showerror(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.export_failed', default="Export failed"), str(e))
            return
        messagebox.showinfo(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.exported', default="Exported"), f"Wrote {n} row(s) to:\n{path}")

    def _seating_export_pdf(self):
        st = self._seating_state
        if not st['exam_id'] or not st['layout']:
            messagebox.showwarning(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.nothing_to_export', default="Nothing to export"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.pick_an_exam_with_a_layout', default="Pick an exam with a layout."))
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.pdf',
            initialfile=f"exam_{st['exam_id']}_seating.pdf",
            filetypes=[('PDF files', '*.pdf')])
        if not path:
            return
        ok = _export_pdf(st['exam_id'], path, st['layout'],
                         st['allocations_by_seat'], st['room_label'])
        if ok:
            messagebox.showinfo(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.exported', default="Exported"), f"PDF saved to:\n{path}")
        else:
            # Fallback: write the Canvas as PostScript.
            ps_path = path.rsplit('.', 1)[0] + '.ps'
            self._seating_canvas.postscript(file=ps_path)
            messagebox.showwarning(
                _t('gui.academics.exam_management.tabs.seating_tab.dialogs.reportlab_unavailable', default="reportlab unavailable"),
                f"PDF backend not installed — saved PostScript to:\n{ps_path}")

    # ── Invigilator zones dialog ─────────────────────────────────────

    def _seating_zones_dialog(self):
        st = self._seating_state
        if not st['exam_id']:
            messagebox.showwarning(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.select', default="Select"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.pick_an_exam_first', default="Pick an exam first."))
            return
        eid = st['exam_id']
        win = tk.Toplevel(self.notebook)
        win.title(_t('gui.academics.exam_management.tabs.seating_tab.windows.invigilator_zones', default="Invigilator zones"))
        win.transient(self.notebook.winfo_toplevel())

        cols = ('id', 'invigilator', 'zone', 'rows', 'cols')
        tree = ttk.Treeview(win, columns=cols, show='headings', height=8)
        for c, t, w in [('id', 'ID', 50), ('invigilator', 'Invigilator', 150),
                        ('zone', 'Zone label', 180),
                        ('rows', 'Rows', 80), ('cols', 'Cols', 80)]:
            tree.heading(c, text=t)
            tree.column(c, width=w)
        tree.pack(fill='both', expand=True, padx=10, pady=8)

        def refresh():
            for i in tree.get_children():
                tree.delete(i)
            for z in _seating.list_zones(eid):
                rspec = (f"{z['row_start']}–{z['row_end']}"
                         if z['row_start'] or z['row_end'] else '')
                cspec = (f"{z['col_start']}–{z['col_end']}"
                         if z['col_start'] or z['col_end'] else '')
                tree.insert('', tk.END, iid=str(z['zone_id']),
                            values=(z['zone_id'], z['invigilator'],
                                    z['zone_label'], rspec, cspec))
        refresh()

        # Add zone
        form = ttk.LabelFrame(win, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.add_zone', default="Add zone"), padding=8)
        form.pack(fill='x', padx=10, pady=(0, 8))
        invig_e = ttk.Entry(form, width=20)
        invig_e.grid(row=0, column=1, padx=4, pady=2, sticky='w')
        label_e = ttk.Entry(form, width=20)
        label_e.grid(row=1, column=1, padx=4, pady=2, sticky='w')
        rs_e = ttk.Entry(form, width=6)
        rs_e.grid(row=2, column=1, padx=4, pady=2, sticky='w')
        re_e = ttk.Entry(form, width=6)
        re_e.grid(row=2, column=3, padx=4, pady=2, sticky='w')
        cs_e = ttk.Entry(form, width=6)
        cs_e.grid(row=3, column=1, padx=4, pady=2, sticky='w')
        ce_e = ttk.Entry(form, width=6)
        ce_e.grid(row=3, column=3, padx=4, pady=2, sticky='w')
        ttk.Label(form, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.invigilator', default="Invigilator:")).grid(row=0, column=0, sticky='e')
        ttk.Label(form, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.zone_label', default="Zone label:")).grid(row=1, column=0, sticky='e')
        ttk.Label(form, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.row_start', default="Row start:")).grid(row=2, column=0, sticky='e')
        ttk.Label(form, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.row_end', default="Row end:")).grid(row=2, column=2, sticky='e')
        ttk.Label(form, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.col_start', default="Col start:")).grid(row=3, column=0, sticky='e')
        ttk.Label(form, text=_t('gui.academics.exam_management.tabs.seating_tab.labels.col_end', default="Col end:")).grid(row=3, column=2, sticky='e')

        def _opt_int(s):
            s = s.strip()
            if not s:
                return None
            try:
                return int(s)
            except ValueError:
                return None

        def add():
            if not invig_e.get().strip() or not label_e.get().strip():
                messagebox.showerror(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.required', default="Required"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.invigilator_and_label_required', default="Invigilator and label required."),
                                     parent=win)
                return
            _seating.assign_invigilator_zone(
                eid, invig_e.get().strip(), label_e.get().strip(),
                row_start=_opt_int(rs_e.get()),
                row_end=_opt_int(re_e.get()),
                col_start=_opt_int(cs_e.get()),
                col_end=_opt_int(ce_e.get()),
            )
            for e in (invig_e, label_e, rs_e, re_e, cs_e, ce_e):
                e.delete(0, tk.END)
            refresh()

        ttk.Button(form, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.add', default="Add"), command=add).grid(row=4, column=0,
                                                       columnspan=4, pady=6)

        def clear_all():
            if messagebox.askyesno(_t('gui.academics.exam_management.tabs.seating_tab.dialogs.clear_variant_2', default="Clear?"), _t('gui.academics.exam_management.tabs.seating_tab.dialogs.clear_all_zones_for_this_exam', default="Clear all zones for this exam?"),
                                   parent=win):
                _seating.clear_zones(eid)
                refresh()

        btns = ttk.Frame(win)
        btns.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(btns, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.clear_all_zones', default="Clear all zones"),
                   command=clear_all).pack(side='left')
        ttk.Button(btns, text=_t('gui.academics.exam_management.tabs.seating_tab.buttons.close', default="Close"),
                   command=win.destroy).pack(side='right')
