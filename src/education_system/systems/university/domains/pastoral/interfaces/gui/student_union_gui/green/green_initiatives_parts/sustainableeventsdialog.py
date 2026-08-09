"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class SustainableEventsDialog:
    """Dialog for tracking sustainability of events."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.sustainableeventsdialog.windows.sustainable_events', default="Sustainable Events"))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.sustainableeventsdialog.labels.sustainable_events_tracker', default="Sustainable Events Tracker"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        info_label = ttk.Label(main_frame,
                                text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.sustainableeventsdialog.labels.track_the_environmental_impact_of_events_use_carbon_tracking_and', default="Track the environmental impact of events. "
                                     "Use Carbon Tracking and Waste Reduction dialogs "
                                     "to log detailed data per event."),
                                wraplength=800, foreground='gray')
        info_label.pack(pady=(0, 10))

        # Events from sustainability_tracking (the existing core table)
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.sustainableeventsdialog.labels.events_with_sustainability_data', default="Events with Sustainability Data"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Event', 'Carbon (kg)', 'Waste (kg)', 'Recycled (kg)', 'Score', 'Date')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.column('Event', width=200)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.sustainableeventsdialog.buttons.refresh', default="Refresh"), command=self.load_events).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.sustainableeventsdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def load_events(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # Try reading from the core sustainability_tracking table
            cursor.execute('''
                SELECT st.tracking_id,
                       COALESCE(e.event_name, 'Event #' || st.event_id) as event_name,
                       st.carbon_footprint, st.waste_generated, st.waste_recycled,
                       st.sustainability_score, st.recorded_date
                FROM sustainability_tracking st
                LEFT JOIN union_events e ON st.event_id = e.event_id
                ORDER BY st.recorded_date DESC
                LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['event_name'] or '',
                    f"{r['carbon_footprint']:.1f}" if r['carbon_footprint'] else '0.0',
                    f"{r['waste_generated']:.1f}" if r['waste_generated'] else '0.0',
                    f"{r['waste_recycled']:.1f}" if r['waste_recycled'] else '0.0',
                    f"{r['sustainability_score']:.0f}" if r['sustainability_score'] else '-',
                    r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading sustainable events: {e}")
