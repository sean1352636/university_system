"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class GridViewWindow:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler

        self.window = tk.Toplevel(parent)
        self.window.title(_t('gui.academics.module_scheduling.dialogs_parts.gridviewwindow.windows.schedule_grid_view', default="Schedule Grid View"))
        self.window.geometry("1200x800")
        self.window.transient(parent)

        self.create_grid_view()
        self.center_window()

    def create_grid_view(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.gridviewwindow.labels.weekly_schedule_grid_view', default="Weekly Schedule Grid View"), font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Create grid frame with scrollbars
        grid_frame = ttk.Frame(main_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for scrolling
        canvas = tk.Canvas(grid_frame)
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Create the actual grid
        self.create_schedule_grid(scrollable_frame)

        # Pack scrollbars and canvas
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_schedule_grid(self, parent_frame):
        """Create the schedule grid with proper boxes"""
        try:
            # Get all schedules
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
                       r.building, r.room_number, ms.session_type
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                ORDER BY ms.day_of_week, ms.start_time
                ''')

                schedules = cursor.fetchall()

            # Create grid data structure
            grid_data = {}
            for day in DAYS_OF_WEEK:
                grid_data[day] = {}
                for time_slot in TIME_SLOTS:
                    grid_data[day][time_slot] = []

            # Populate grid with schedule data
            for schedule in schedules:
                module_code, day, start_time, end_time, building, room_number, session_type = schedule

                # Find the closest time slot
                closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

                # Create session info
                room_str = f"{building}-{room_number}" if building and room_number else "TBA"
                session_info = {
                    'module': module_code,
                    'type': session_type,
                    'room': room_str,
                    'time': f"{start_time}-{end_time}"
                }

                if day in grid_data and closest_slot in grid_data[day]:
                    grid_data[day][closest_slot].append(session_info)

            # Create grid with proper boxes
            # Header row with time column
            time_header = tk.Label(parent_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.gridviewwindow.labels.time', default="Time"), font=('Arial', 11, 'bold'),
                                   relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                   width=12, height=2)
            time_header.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")

            # Day headers
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                day_header = tk.Label(parent_frame, text=day, font=('Arial', 11, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                      width=20, height=2)
                day_header.grid(row=0, column=col, padx=2, pady=2, sticky="nsew")

            # Create time slots and schedule cells
            for row, time_slot in enumerate(TIME_SLOTS, 1):
                # Time label with box
                time_label = tk.Label(parent_frame, text=time_slot, font=('Arial', 10, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                      width=12, height=4)
                time_label.grid(row=row, column=0, padx=2, pady=2, sticky="nsew")

                # Schedule cells for each day
                for col, day in enumerate(DAYS_OF_WEEK, 1):
                    entries = grid_data[day][time_slot]

                    # Create cell frame with visible border
                    cell_frame = tk.Frame(parent_frame, relief=tk.SOLID, borderwidth=2,
                                         bg='#d4edda' if entries else 'white',
                                         width=180, height=100)
                    cell_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    cell_frame.grid_propagate(False)

                    if entries:
                        # Create inner container for better padding
                        inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                        inner_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                        # Display schedule entries
                        for i, entry in enumerate(entries):
                            if i < 2:  # Limit to 2 entries per cell
                                # Create a box for each session
                                session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                       bg='#c3e6cb', padx=3, pady=3)
                                session_box.pack(fill=tk.X, pady=2)

                                # Module code - bold and larger
                                module_label = tk.Label(session_box, text=entry['module'],
                                                        font=('Arial', 9, 'bold'),
                                                        bg='#c3e6cb', fg='#155724')
                                module_label.pack(anchor='w')

                                # Session type
                                type_label = tk.Label(session_box, text=entry['type'],
                                                      font=('Arial', 8),
                                                      bg='#c3e6cb', fg='#155724')
                                type_label.pack(anchor='w')

                                # Room
                                room_label = tk.Label(session_box, text=f"Room: {entry['room']}",
                                                      font=('Arial', 7),
                                                      bg='#c3e6cb', fg='#155724')
                                room_label.pack(anchor='w')

                                # Time
                                time_label = tk.Label(session_box, text=entry['time'],
                                                      font=('Arial', 7, 'italic'),
                                                      bg='#c3e6cb', fg='#155724')
                                time_label.pack(anchor='w')

                        if len(entries) > 2:
                            more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                                  font=('Arial', 7, 'italic'),
                                                  bg='#d4edda', fg='#155724')
                            more_label.pack(pady=2)
                    else:
                        # Empty cell indicator
                        empty_label = tk.Label(cell_frame, text="-", font=('Arial', 12),
                                               bg='white', fg='#cccccc')
                        empty_label.place(relx=0.5, rely=0.5, anchor='center')

            # Configure grid weights for proper resizing
            for i in range(len(TIME_SLOTS) + 1):
                parent_frame.grid_rowconfigure(i, weight=0, minsize=100)
            for i in range(len(DAYS_OF_WEEK) + 1):
                parent_frame.grid_columnconfigure(i, weight=0, minsize=180 if i > 0 else 100)

        except Exception as e:
            error_label = ttk.Label(parent_frame, text=f"Error creating grid: {str(e)}")
            error_label.pack(pady=20)

    def center_window(self):
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
