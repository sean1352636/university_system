"""
Faculty Schedule Builder GUI

Provides interface for:
- Weekly schedule view with colored blocks
- Block management (add/edit/delete)
- Teaching schedule import
- Template management
- Weekly summary
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.faculty_schedule_manager import FacultyScheduleManager
from education_system.university_system.modules.domain.operations.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)

DAY_NAMES = {
    0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
    4: 'Friday', 5: 'Saturday', 6: 'Sunday'
}

# Default colors for activity types when none specified
DEFAULT_TYPE_COLORS = {
    'teaching': '#4CAF50',
    'research': '#2196F3',
    'office_hours': '#FF9800',
    'meeting': '#9C27B0',
    'admin': '#607D8B',
    'other': '#795548',
}

# Grid layout constants
GRID_LEFT_MARGIN = 70
GRID_TOP_MARGIN = 30
GRID_COL_WIDTH = 120
GRID_ROW_HEIGHT = 20
GRID_START_HOUR = 7
GRID_END_HOUR = 21
GRID_SLOTS = (GRID_END_HOUR - GRID_START_HOUR) * 2  # 30-min slots


class FacultyScheduleGUI:
    """GUI for faculty schedule building."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        # Cache activity types and build lookup maps
        self.activity_types = []
        self.activity_type_map = {}
        self.activity_color_map = dict(DEFAULT_TYPE_COLORS)
        self._load_activity_types()

        # Track canvas item -> block_id mapping for click handling
        self._canvas_block_items = {}

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Schedule Builder")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def _load_activity_types(self):
        """Load activity types from the manager and build lookup maps."""
        try:
            self.activity_types = FacultyScheduleManager.get_activity_types()
        except Exception:
            self.activity_types = [
                {'type_id': 1, 'name': 'teaching', 'label': 'Teaching', 'color': '#4CAF50', 'sort_order': 1},
                {'type_id': 2, 'name': 'research', 'label': 'Research', 'color': '#2196F3', 'sort_order': 2},
                {'type_id': 3, 'name': 'office_hours', 'label': 'Office Hours', 'color': '#FF9800', 'sort_order': 3},
                {'type_id': 4, 'name': 'meeting', 'label': 'Meeting', 'color': '#9C27B0', 'sort_order': 4},
                {'type_id': 5, 'name': 'admin', 'label': 'Administration', 'color': '#607D8B', 'sort_order': 5},
                {'type_id': 6, 'name': 'other', 'label': 'Other', 'color': '#795548', 'sort_order': 6},
            ]
        self.activity_type_map = {at['name']: at for at in self.activity_types}
        for at in self.activity_types:
            if at.get('color'):
                self.activity_color_map[at['name']] = at['color']

    def _get_activity_type_names(self):
        """Return list of activity type name strings."""
        return [at['name'] for at in self.activity_types]

    def _get_activity_type_labels(self):
        """Return list of activity type label strings."""
        return [at.get('label', at['name']) for at in self.activity_types]

    def _get_color_for_type(self, activity_type):
        """Return color hex string for a given activity type."""
        return self.activity_color_map.get(activity_type, '#795548')

    # ==================== DUAL-MODE CREATION ====================

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Schedule")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Faculty Schedule Builder")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_weekly_view_tab()
        self._create_block_list_tab()
        self._create_import_tab()
        self._create_templates_tab()
        self._create_summary_tab()

    # ==================== TAB 1: WEEKLY VIEW ====================

    def _create_weekly_view_tab(self):
        """Create the weekly schedule view tab with a colored grid."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Weekly View")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Weekly Schedule", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._draw_schedule_grid).pack(side=tk.RIGHT, padx=5)

        # Legend frame
        legend_frame = ttk.Frame(tab)
        legend_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        ttk.Label(legend_frame, text="Legend: ").pack(side=tk.LEFT, padx=(0, 5))
        for at in self.activity_types:
            color = at.get('color', '#795548')
            label_text = at.get('label', at['name'])
            swatch = tk.Canvas(legend_frame, width=14, height=14, highlightthickness=0)
            swatch.create_rectangle(0, 0, 14, 14, fill=color, outline=color)
            swatch.pack(side=tk.LEFT, padx=(5, 2))
            ttk.Label(legend_frame, text=label_text, font=('Arial', 9)).pack(side=tk.LEFT, padx=(0, 8))

        # Canvas with scrollbars
        canvas_frame = ttk.Frame(tab)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        canvas_width = GRID_LEFT_MARGIN + GRID_COL_WIDTH * 7 + 20
        canvas_height = GRID_TOP_MARGIN + GRID_ROW_HEIGHT * GRID_SLOTS + 20

        self.schedule_canvas = tk.Canvas(
            canvas_frame, width=900, height=500,
            scrollregion=(0, 0, canvas_width, canvas_height),
            xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set,
            bg='white'
        )
        self.schedule_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        h_scroll.config(command=self.schedule_canvas.xview)
        v_scroll.config(command=self.schedule_canvas.yview)

        # Bind click on empty area
        self.schedule_canvas.bind('<Button-1>', self._on_canvas_click)

        self._draw_schedule_grid()

    def _draw_schedule_grid(self):
        """Draw the weekly grid with time labels, day headers, grid lines, and schedule blocks."""
        canvas = self.schedule_canvas
        canvas.delete('all')
        self._canvas_block_items = {}

        left = GRID_LEFT_MARGIN
        top = GRID_TOP_MARGIN
        col_w = GRID_COL_WIDTH
        row_h = GRID_ROW_HEIGHT

        # Draw day column headers
        for day_idx in range(7):
            x = left + day_idx * col_w
            day_label = DAY_NAMES[day_idx]
            canvas.create_text(
                x + col_w // 2, top // 2,
                text=day_label, font=('Arial', 10, 'bold'), fill='#333333'
            )

        # Draw time labels on the left and horizontal grid lines
        for slot_idx in range(GRID_SLOTS + 1):
            y = top + slot_idx * row_h
            hour = GRID_START_HOUR + slot_idx // 2
            minute = (slot_idx % 2) * 30
            time_str = f'{hour:02d}:{minute:02d}'

            # Time label on the left
            canvas.create_text(
                left - 8, y,
                text=time_str, anchor='e', font=('Arial', 8), fill='#666666'
            )

            # Horizontal grid line
            line_color = '#cccccc' if minute == 0 else '#e8e8e8'
            line_width = 1
            canvas.create_line(
                left, y, left + col_w * 7, y,
                fill=line_color, width=line_width
            )

        # Draw vertical grid lines
        for day_idx in range(8):
            x = left + day_idx * col_w
            canvas.create_line(
                x, top, x, top + GRID_SLOTS * row_h,
                fill='#cccccc', width=1
            )

        # Draw schedule blocks
        try:
            blocks = FacultyScheduleManager.get_user_schedule(self._get_user_id())
        except Exception:
            blocks = []

        for block in blocks:
            self._draw_block_on_canvas(canvas, block)

    def _draw_block_on_canvas(self, canvas, block):
        """Draw a single schedule block as a colored rectangle on the canvas."""
        day = block.get('day_of_week')
        start_time = block.get('start_time', '')
        end_time = block.get('end_time', '')
        activity_type = block.get('activity_type', 'other')
        title = block.get('title') or activity_type
        block_id = block.get('block_id')

        if day is None:
            return

        try:
            day = int(day)
        except (ValueError, TypeError):
            return

        # Parse start and end times into slot indices
        start_slot = self._time_to_slot(start_time)
        end_slot = self._time_to_slot(end_time)
        if start_slot is None or end_slot is None or end_slot <= start_slot:
            return

        left = GRID_LEFT_MARGIN
        top = GRID_TOP_MARGIN
        col_w = GRID_COL_WIDTH
        row_h = GRID_ROW_HEIGHT

        x1 = left + day * col_w + 2
        y1 = top + start_slot * row_h + 1
        x2 = left + (day + 1) * col_w - 2
        y2 = top + end_slot * row_h - 1

        color = block.get('color') or self._get_color_for_type(activity_type)

        # Draw filled rectangle
        rect_id = canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=color, outline='#333333', width=1
        )

        # Draw text inside the block
        display_text = title[:15] if len(title) > 15 else title
        location = block.get('location', '')
        if location:
            display_text += f'\n{location[:12]}'

        text_id = canvas.create_text(
            (x1 + x2) // 2, (y1 + y2) // 2,
            text=display_text, font=('Arial', 7), fill='white',
            width=col_w - 8, justify=tk.CENTER
        )

        # Map canvas items to block_id for click handling
        if block_id:
            self._canvas_block_items[rect_id] = block_id
            self._canvas_block_items[text_id] = block_id

    def _time_to_slot(self, time_str):
        """Convert a time string (HH:MM) to a slot index relative to GRID_START_HOUR."""
        if not time_str:
            return None
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            total_minutes = (hour - GRID_START_HOUR) * 60 + minute
            slot = total_minutes // 30
            if slot < 0 or slot > GRID_SLOTS:
                return None
            return slot
        except (ValueError, IndexError):
            return None

    def _slot_to_time(self, slot):
        """Convert a slot index to a time string (HH:MM)."""
        total_minutes = GRID_START_HOUR * 60 + slot * 30
        hour = total_minutes // 60
        minute = total_minutes % 60
        return f'{hour:02d}:{minute:02d}'

    def _on_canvas_click(self, event):
        """Handle click on the schedule canvas."""
        canvas = self.schedule_canvas
        # Convert to canvas coordinates
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)

        # Check if clicked on an existing block
        items = canvas.find_overlapping(cx - 1, cy - 1, cx + 1, cy + 1)
        for item_id in items:
            if item_id in self._canvas_block_items:
                block_id = self._canvas_block_items[item_id]
                self._edit_block_dialog(block_id=block_id)
                return

        # Determine day and time from click position
        left = GRID_LEFT_MARGIN
        top = GRID_TOP_MARGIN
        col_w = GRID_COL_WIDTH
        row_h = GRID_ROW_HEIGHT

        if cx < left or cy < top:
            return

        day = int((cx - left) / col_w)
        slot = int((cy - top) / row_h)

        if day < 0 or day > 6 or slot < 0 or slot >= GRID_SLOTS:
            return

        start_time = self._slot_to_time(slot)
        end_slot = min(slot + 2, GRID_SLOTS)  # default 1-hour block
        end_time = self._slot_to_time(end_slot)

        self._add_block_dialog(day=day, start_time=start_time, end_time=end_time)

    # ==================== TAB 2: BLOCK LIST ====================

    def _create_block_list_tab(self):
        """Create block list tab with filtering and CRUD buttons."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Block List")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Schedule Blocks", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter frame
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Day:").pack(side=tk.LEFT, padx=5)
        day_values = ['All'] + [DAY_NAMES[i] for i in range(7)]
        self.block_day_filter = ttk.Combobox(filter_frame, values=day_values, width=12, state='readonly')
        self.block_day_filter.set('All')
        self.block_day_filter.pack(side=tk.LEFT, padx=5)
        self.block_day_filter.bind('<<ComboboxSelected>>', lambda e: self._load_blocks())

        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT, padx=5)
        type_values = ['All'] + self._get_activity_type_names()
        self.block_type_filter = ttk.Combobox(filter_frame, values=type_values, width=14, state='readonly')
        self.block_type_filter.set('All')
        self.block_type_filter.pack(side=tk.LEFT, padx=5)
        self.block_type_filter.bind('<<ComboboxSelected>>', lambda e: self._load_blocks())

        ttk.Button(filter_frame, text="Refresh", command=self._load_blocks).pack(side=tk.LEFT, padx=10)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Day', 'Start', 'End', 'Type', 'Title', 'Location', 'Locked')
        self.blocks_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.blocks_tree.yview)

        widths = {'ID': 50, 'Day': 90, 'Start': 70, 'End': 70, 'Type': 100, 'Title': 180, 'Location': 140, 'Locked': 60}
        for col in columns:
            self.blocks_tree.heading(col, text=col)
            self.blocks_tree.column(col, width=widths.get(col, 100))

        self.blocks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tag colors for locked blocks
        self.blocks_tree.tag_configure('locked', background='#fff3cd')

        # Button frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Add Block", command=self._add_block_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Block", command=self._edit_selected_block).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Block", command=self._delete_block).pack(side=tk.LEFT, padx=5)

        self._load_blocks()

    def _load_blocks(self):
        """Populate the blocks treeview, applying day and type filters."""
        for item in self.blocks_tree.get_children():
            self.blocks_tree.delete(item)

        try:
            blocks = FacultyScheduleManager.get_user_schedule(self._get_user_id())
        except Exception:
            blocks = []

        # Apply day filter
        day_filter = self.block_day_filter.get()
        if day_filter != 'All':
            # Reverse-lookup day index from name
            day_index = None
            for idx, name in DAY_NAMES.items():
                if name == day_filter:
                    day_index = idx
                    break
            if day_index is not None:
                blocks = [b for b in blocks if b.get('day_of_week') == day_index]

        # Apply type filter
        type_filter = self.block_type_filter.get()
        if type_filter != 'All':
            blocks = [b for b in blocks if b.get('activity_type') == type_filter]

        for block in blocks:
            day_idx = block.get('day_of_week')
            day_name = DAY_NAMES.get(day_idx, str(day_idx))
            is_locked = block.get('is_locked', 0)
            tag = 'locked' if is_locked else ''

            self.blocks_tree.insert('', tk.END, values=(
                block.get('block_id'),
                day_name,
                block.get('start_time', ''),
                block.get('end_time', ''),
                block.get('activity_type', ''),
                block.get('title', '') or '',
                block.get('location', '') or '',
                'Yes' if is_locked else 'No'
            ), tags=(tag,))

    def _add_block_dialog(self, day=None, start_time=None, end_time=None):
        """Show dialog to add a new schedule block."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Schedule Block")
        dialog.geometry("450x420")
        dialog.transient(self.root)
        dialog.wait_visibility()
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Day
        ttk.Label(frame, text="Day:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        day_combo = ttk.Combobox(frame, values=[DAY_NAMES[i] for i in range(7)], width=20, state='readonly')
        day_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')
        if day is not None:
            day_combo.set(DAY_NAMES.get(day, ''))

        # Start time
        ttk.Label(frame, text="Start Time (HH:MM):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        start_entry = ttk.Entry(frame, width=10)
        start_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')
        if start_time:
            start_entry.insert(0, start_time)

        # End time
        ttk.Label(frame, text="End Time (HH:MM):").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        end_entry = ttk.Entry(frame, width=10)
        end_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')
        if end_time:
            end_entry.insert(0, end_time)

        # Activity type
        ttk.Label(frame, text="Activity Type:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(frame, values=self._get_activity_type_names(), width=20, state='readonly')
        type_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')
        if self.activity_types:
            type_combo.set(self.activity_types[0]['name'])

        # Title
        ttk.Label(frame, text="Title:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=30)
        title_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Location
        ttk.Label(frame, text="Location:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        location_entry = ttk.Entry(frame, width=30)
        location_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Course code
        ttk.Label(frame, text="Course Code:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        course_entry = ttk.Entry(frame, width=20)
        course_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')

        def save():
            # Validate day selection
            try:
                day_name = validate_combobox(day_combo, "Day")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Reverse-lookup day index
            selected_day = None
            for idx, name in DAY_NAMES.items():
                if name == day_name:
                    selected_day = idx
                    break
            if selected_day is None:
                messagebox.showerror("Error", "Please select a valid day", parent=dialog)
                return

            # Validate times
            try:
                s_time = validate_entry(start_entry, "Start Time")
                e_time = validate_entry(end_entry, "End Time")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            # Validate time format
            if not self._validate_time_format(s_time) or not self._validate_time_format(e_time):
                messagebox.showerror("Error", "Time must be in HH:MM format (e.g. 09:00)", parent=dialog)
                return

            # Validate activity type
            try:
                act_type = validate_combobox(type_combo, "Activity Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            title_val = title_entry.get().strip() or None
            location_val = location_entry.get().strip() or None
            course_val = course_entry.get().strip() or None

            try:
                block_id = FacultyScheduleManager.create_block(
                    user_id=self._get_user_id(),
                    day_of_week=selected_day,
                    start_time=s_time,
                    end_time=e_time,
                    activity_type=act_type,
                    title=title_val,
                    location=location_val,
                    course_code=course_val
                )
                messagebox.showinfo("Success", f"Block created successfully. ID: {block_id}", parent=dialog)
                dialog.destroy()
                self._load_blocks()
                self._draw_schedule_grid()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _edit_selected_block(self):
        """Edit the block currently selected in the treeview."""
        selection = self.blocks_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a block to edit")
            return
        item = self.blocks_tree.item(selection[0])
        block_id = item['values'][0]
        self._edit_block_dialog(block_id=block_id)

    def _edit_block_dialog(self, block_id=None):
        """Show dialog to edit an existing schedule block."""
        if block_id is None:
            messagebox.showinfo("Info", "No block selected")
            return

        try:
            block = FacultyScheduleManager.get_block(block_id)
        except Exception:
            block = None

        if not block:
            messagebox.showerror("Error", f"Block {block_id} not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Schedule Block #{block_id}")
        dialog.geometry("450x420")
        dialog.transient(self.root)
        dialog.wait_visibility()
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Day
        ttk.Label(frame, text="Day:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        day_combo = ttk.Combobox(frame, values=[DAY_NAMES[i] for i in range(7)], width=20, state='readonly')
        day_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')
        current_day = block.get('day_of_week')
        if current_day is not None:
            day_combo.set(DAY_NAMES.get(int(current_day), ''))

        # Start time
        ttk.Label(frame, text="Start Time (HH:MM):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        start_entry = ttk.Entry(frame, width=10)
        start_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')
        start_entry.insert(0, block.get('start_time', ''))

        # End time
        ttk.Label(frame, text="End Time (HH:MM):").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        end_entry = ttk.Entry(frame, width=10)
        end_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')
        end_entry.insert(0, block.get('end_time', ''))

        # Activity type
        ttk.Label(frame, text="Activity Type:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(frame, values=self._get_activity_type_names(), width=20, state='readonly')
        type_combo.grid(row=3, column=1, padx=10, pady=8, sticky='w')
        type_combo.set(block.get('activity_type', ''))

        # Title
        ttk.Label(frame, text="Title:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=30)
        title_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')
        title_entry.insert(0, block.get('title', '') or '')

        # Location
        ttk.Label(frame, text="Location:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        location_entry = ttk.Entry(frame, width=30)
        location_entry.grid(row=5, column=1, padx=10, pady=8, sticky='w')
        location_entry.insert(0, block.get('location', '') or '')

        # Course code
        ttk.Label(frame, text="Course Code:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        course_entry = ttk.Entry(frame, width=20)
        course_entry.grid(row=6, column=1, padx=10, pady=8, sticky='w')
        course_entry.insert(0, block.get('course_code', '') or '')

        def save():
            # Validate day selection
            try:
                day_name = validate_combobox(day_combo, "Day")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_day = None
            for idx, name in DAY_NAMES.items():
                if name == day_name:
                    selected_day = idx
                    break
            if selected_day is None:
                messagebox.showerror("Error", "Please select a valid day", parent=dialog)
                return

            # Validate times
            try:
                s_time = validate_entry(start_entry, "Start Time")
                e_time = validate_entry(end_entry, "End Time")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            if not self._validate_time_format(s_time) or not self._validate_time_format(e_time):
                messagebox.showerror("Error", "Time must be in HH:MM format (e.g. 09:00)", parent=dialog)
                return

            # Validate activity type
            try:
                act_type = validate_combobox(type_combo, "Activity Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            update_data = {
                'day_of_week': selected_day,
                'start_time': s_time,
                'end_time': e_time,
                'activity_type': act_type,
                'title': title_entry.get().strip() or None,
                'location': location_entry.get().strip() or None,
                'course_code': course_entry.get().strip() or None,
            }

            try:
                FacultyScheduleManager.update_block(block_id, **update_data)
                messagebox.showinfo("Success", "Block updated successfully", parent=dialog)
                dialog.destroy()
                self._load_blocks()
                self._draw_schedule_grid()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _delete_block(self):
        """Delete the selected schedule block after confirmation."""
        selection = self.blocks_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a block to delete")
            return

        item = self.blocks_tree.item(selection[0])
        block_id = item['values'][0]
        day_name = item['values'][1]
        start = item['values'][2]
        end = item['values'][3]

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete block on {day_name} ({start} - {end})?"
        ):
            return

        try:
            FacultyScheduleManager.delete_block(block_id)
            messagebox.showinfo("Success", "Block deleted successfully")
            self._load_blocks()
            self._draw_schedule_grid()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 3: IMPORT SCHEDULE ====================

    def _create_import_tab(self):
        """Create the import teaching schedule tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Import")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Import Teaching Schedule", style='Header.TLabel').pack(side=tk.LEFT)

        # Description
        desc_frame = ttk.Frame(tab)
        desc_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            desc_frame,
            text=(
                "Import your teaching schedule from the course management system. "
                "This will create locked schedule blocks for each assigned teaching slot. "
                "Existing blocks will not be affected unless there is a time conflict."
            ),
            wraplength=700, justify=tk.LEFT
        ).pack(anchor='w')

        # Form
        form_frame = ttk.LabelFrame(tab, text="Import Settings", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=15)

        ttk.Label(form_frame, text="Semester:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.import_semester_entry = ttk.Entry(form_frame, width=20)
        self.import_semester_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')
        self.import_semester_entry.insert(0, 'Fall')

        ttk.Label(form_frame, text="Academic Year:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.import_year_entry = ttk.Entry(form_frame, width=20)
        self.import_year_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')
        current_year = datetime.now().year
        self.import_year_entry.insert(0, f'{current_year}-{current_year + 1}')

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Import", command=self._import_schedule).pack()

        # Result area
        result_frame = ttk.LabelFrame(tab, text="Import Result", padding=15)
        result_frame.pack(fill=tk.X, padx=10, pady=10)

        self.import_result_label = ttk.Label(
            result_frame, text="No import performed yet.", font=('Arial', 11)
        )
        self.import_result_label.pack(anchor='w')

    def _import_schedule(self):
        """Run the teaching schedule import."""
        semester = self.import_semester_entry.get().strip() or None
        academic_year = self.import_year_entry.get().strip() or None

        try:
            count = FacultyScheduleManager.import_teaching_schedule(
                user_id=self._get_user_id(),
                semester=semester,
                academic_year=academic_year
            )

            if count > 0:
                self.import_result_label.config(
                    text=f"Successfully imported {count} teaching block(s).",
                    foreground='green'
                )
                messagebox.showinfo("Success", f"Imported {count} teaching block(s)")
                self._load_blocks()
                self._draw_schedule_grid()
            else:
                self.import_result_label.config(
                    text="No teaching blocks found to import. Check your course assignments.",
                    foreground='orange'
                )
                messagebox.showinfo("Info", "No teaching blocks found to import")
        except Exception as e:
            self.import_result_label.config(
                text=f"Import failed: {str(e)}",
                foreground='red'
            )
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: TEMPLATES ====================

    def _create_templates_tab(self):
        """Create the schedule templates tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Templates")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Schedule Templates", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_templates).pack(side=tk.RIGHT, padx=5)

        # Save section
        save_frame = ttk.LabelFrame(tab, text="Save Current Schedule as Template", padding=15)
        save_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(save_frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.template_name_entry = ttk.Entry(save_frame, width=30)
        self.template_name_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(save_frame, text="Description:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.template_desc_entry = ttk.Entry(save_frame, width=40)
        self.template_desc_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        self.template_shared_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            save_frame, text="Share with other faculty",
            variable=self.template_shared_var
        ).grid(row=2, column=0, columnspan=2, pady=5)

        ttk.Button(save_frame, text="Save Current", command=self._save_template).grid(
            row=3, column=0, columnspan=2, pady=10
        )

        # Templates list
        list_frame = ttk.LabelFrame(tab, text="Available Templates", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Name', 'Description', 'Created', 'Shared')
        self.templates_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.templates_tree.yview)

        widths = {'ID': 50, 'Name': 160, 'Description': 220, 'Created': 130, 'Shared': 70}
        for col in columns:
            self.templates_tree.heading(col, text=col)
            self.templates_tree.column(col, width=widths.get(col, 100))

        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load template buttons
        load_frame = ttk.Frame(list_frame)
        load_frame.pack(fill=tk.X, pady=10)

        self.clear_existing_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            load_frame, text="Clear existing non-locked blocks before loading",
            variable=self.clear_existing_var
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(load_frame, text="Load Template", command=self._load_selected_template).pack(side=tk.RIGHT, padx=10)

        self._load_templates()

    def _save_template(self):
        """Save the current schedule as a template."""
        name = self.template_name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Template name is required")
            return

        description = self.template_desc_entry.get().strip() or None
        is_shared = self.template_shared_var.get()

        try:
            template_id = FacultyScheduleManager.save_as_template(
                user_id=self._get_user_id(),
                name=name,
                description=description,
                is_shared=is_shared
            )
            messagebox.showinfo("Success", f"Template saved successfully. ID: {template_id}")
            self.template_name_entry.delete(0, tk.END)
            self.template_desc_entry.delete(0, tk.END)
            self.template_shared_var.set(False)
            self._load_templates()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_templates(self):
        """Load available templates into the treeview."""
        for item in self.templates_tree.get_children():
            self.templates_tree.delete(item)

        try:
            templates = FacultyScheduleManager.get_templates(
                user_id=self._get_user_id(), include_shared=True
            )
        except Exception:
            templates = []

        for t in templates:
            created = t.get('created_at', '')
            if created and len(created) > 16:
                created = created[:16]

            self.templates_tree.insert('', tk.END, values=(
                t.get('template_id'),
                t.get('name', ''),
                (t.get('description', '') or '')[:40],
                created,
                'Yes' if t.get('is_shared') else 'No'
            ))

    def _load_selected_template(self):
        """Load the selected template into the user's schedule."""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a template to load")
            return

        item = self.templates_tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]
        clear_existing = self.clear_existing_var.get()

        confirm_msg = f'Load template "{template_name}"?'
        if clear_existing:
            confirm_msg += '\n\nThis will remove all existing non-locked blocks first.'

        if not messagebox.askyesno("Confirm Load Template", confirm_msg):
            return

        try:
            count = FacultyScheduleManager.load_template(
                template_id=template_id,
                user_id=self._get_user_id(),
                clear_existing=clear_existing
            )
            messagebox.showinfo("Success", f"Loaded {count} block(s) from template")
            self._load_blocks()
            self._draw_schedule_grid()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 5: SUMMARY ====================

    def _create_summary_tab(self):
        """Create the weekly summary tab with hours breakdown and bar chart."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Summary")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Weekly Summary", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._refresh_summary).pack(side=tk.RIGHT, padx=5)

        # Total hours label
        total_frame = ttk.Frame(tab)
        total_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_hours_label = ttk.Label(
            total_frame, text="Total Weekly Hours: 0.0",
            font=('Arial', 16, 'bold')
        )
        self.total_hours_label.pack(anchor='w')

        # Bar chart canvas
        chart_frame = ttk.LabelFrame(tab, text="Hours by Activity Type", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.summary_canvas = tk.Canvas(chart_frame, bg='white', height=300)
        self.summary_canvas.pack(fill=tk.BOTH, expand=True)

        self._refresh_summary()

    def _refresh_summary(self):
        """Refresh the weekly summary data and redraw the bar chart."""
        try:
            summary = FacultyScheduleManager.get_weekly_summary(self._get_user_id())
        except Exception:
            summary = {'total_hours': 0, 'by_type': {}}

        total_hours = summary.get('total_hours', 0)
        by_type = summary.get('by_type', {})

        self.total_hours_label.config(text=f"Total Weekly Hours: {total_hours}")

        # Draw horizontal bar chart
        canvas = self.summary_canvas
        canvas.delete('all')

        if not by_type:
            canvas.create_text(
                300, 80, text="No schedule blocks found.",
                font=('Arial', 12), fill='#999999'
            )
            return

        bar_left = 150
        bar_max_width = 400
        bar_height = 30
        bar_gap = 15
        y_start = 30

        # Find max hours for scaling
        max_hours = max(by_type.values()) if by_type else 1

        sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)

        for i, (act_type, hours) in enumerate(sorted_types):
            y = y_start + i * (bar_height + bar_gap)

            # Activity type label on the left
            label = act_type.replace('_', ' ').title()
            at_info = self.activity_type_map.get(act_type)
            if at_info and at_info.get('label'):
                label = at_info['label']

            canvas.create_text(
                bar_left - 10, y + bar_height // 2,
                text=label, anchor='e', font=('Arial', 10), fill='#333333'
            )

            # Colored bar proportional to hours
            bar_width = (hours / max_hours) * bar_max_width if max_hours > 0 else 0
            color = self._get_color_for_type(act_type)

            canvas.create_rectangle(
                bar_left, y,
                bar_left + bar_width, y + bar_height,
                fill=color, outline=color
            )

            # Hours value on the right
            canvas.create_text(
                bar_left + bar_width + 10, y + bar_height // 2,
                text=f"{hours:.1f} hrs", anchor='w',
                font=('Arial', 10, 'bold'), fill='#333333'
            )

        # Update canvas scroll region to fit content
        total_chart_height = y_start + len(sorted_types) * (bar_height + bar_gap) + 20
        canvas.config(scrollregion=(0, 0, bar_left + bar_max_width + 100, total_chart_height))

    # ==================== UTILITY METHODS ====================

    @staticmethod
    def _validate_time_format(time_str):
        """Check if a time string is valid HH:MM format."""
        if not time_str:
            return False
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                return False
            hour = int(parts[0])
            minute = int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError):
            return False
