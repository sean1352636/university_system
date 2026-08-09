"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class GreenTransportDialog:
    """Dialog for green transport tracking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.windows.green_transport', default="Green Transport"))
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh_stats()
        self.load_log()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.green_transport_tracker', default="Green Transport Tracker"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Log trip form
        form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.log_a_green_trip', default="Log a Green Trip"))
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.transport_method', default="Transport Method:")).pack(side='left')
        self.method_var = tk.StringVar()
        method_combo = ttk.Combobox(row1, textvariable=self.method_var, width=20,
                                     values=["Walking", "Cycling", "Public Transport",
                                             "Carpooling", "Electric Vehicle"],
                                     state='readonly')
        method_combo.pack(side='left', padx=5)
        method_combo.current(0)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.distance_km', default="Distance (km):")).pack(side='left', padx=(15, 0))
        self.distance_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.distance_var, width=10).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):")).pack(side='left', padx=(15, 0))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(row1, textvariable=self.date_var, width=12).pack(side='left', padx=5)

        ttk.Button(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.buttons.save_trip', default="Save Trip"), command=self.save_trip).pack(side='right', padx=5)

        # Personal stats
        self.stats_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.your_green_transport_stats', default="Your Green Transport Stats"))
        self.stats_frame.pack(fill='x', pady=(0, 10))
        self.stats_label = ttk.Label(self.stats_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.loading', default="Loading..."), justify='left')
        self.stats_label.pack(padx=15, pady=10)

        # Trip history
        hist_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.labels.trip_history', default="Trip History"))
        hist_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Method', 'Distance (km)', 'CO2 Saved (kg)', 'Trip Date', 'Recorded')
        self.tree = ttk.Treeview(hist_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.column('ID', width=40)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.buttons.refresh', default="Refresh"), command=self._refresh_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.buttons.delete_selected', default="Delete Selected"), command=self.delete_trip).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def _refresh_all(self):
        self.refresh_stats()
        self.load_log()

    def _calc_carbon_saved(self, method, distance):
        """Calculate CO2 saved compared to driving a car."""
        car_rate = 0.21  # kg CO2 per km
        method_rates = {
            "Walking": 0,
            "Cycling": 0,
            "Public Transport": 0.05,
            "Carpooling": 0.105,
            "Electric Vehicle": 0.05,
        }
        rate = method_rates.get(method, 0)
        return distance * (car_rate - rate)

    def save_trip(self):
        method = self.method_var.get().strip()
        if not method:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.please_select_a_transport_method', default="Please select a transport method."))
            return
        try:
            distance = float(self.distance_var.get() or 0)
        except ValueError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.please_enter_a_valid_distance', default="Please enter a valid distance."))
            return
        if distance <= 0:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.distance_must_be_greater_than_zero', default="Distance must be greater than zero."))
            return

        trip_date = self.date_var.get().strip() or datetime.now().strftime('%Y-%m-%d')
        carbon_saved = self._calc_carbon_saved(method, distance)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO green_transport_log
                    (transport_method, distance_km, carbon_saved, trip_date,
                     recorded_by, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                method, distance, carbon_saved, trip_date,
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.success', default="Success"),
                                f"Trip logged: {method} {distance} km\n"
                                f"CO2 saved vs car: {carbon_saved:.2f} kg")
            self.distance_var.set('0')
            self._refresh_all()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.error', default="Error"), f"Failed to save trip: {e}")

    def refresh_stats(self):
        user_id = _get_current_user_id(self.auth)
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # This month stats
            month_start = datetime.now().strftime('%Y-%m-01')
            cursor.execute('''
                SELECT transport_method,
                       COUNT(*) as trips,
                       COALESCE(SUM(distance_km), 0) as total_km,
                       COALESCE(SUM(carbon_saved), 0) as total_saved
                FROM green_transport_log
                WHERE recorded_by = ? AND trip_date >= ?
                GROUP BY transport_method
            ''', (user_id, month_start))
            rows = cursor.fetchall()

            # All-time stats
            cursor.execute('''
                SELECT COUNT(*) as total_trips,
                       COALESCE(SUM(distance_km), 0) as total_km,
                       COALESCE(SUM(carbon_saved), 0) as total_saved
                FROM green_transport_log
                WHERE recorded_by = ?
            ''', (user_id,))
            totals = cursor.fetchone()
            conn.close()

            lines = ["This Month:"]
            month_saved = 0.0
            for r in rows:
                lines.append(f"  {r['transport_method']}: {r['trips']} trips, "
                             f"{r['total_km']:.1f} km, saved {r['total_saved']:.2f} kg CO2")
                month_saved += r['total_saved']

            if not rows:
                lines.append("  No trips logged this month yet.")

            lines.append(f"\nMonth CO2 Saved: {month_saved:.2f} kg")
            lines.append(f"\nAll-Time: {totals['total_trips']} trips, "
                         f"{totals['total_km']:.1f} km, "
                         f"{totals['total_saved']:.2f} kg CO2 saved")

            self.stats_label.config(text='\n'.join(lines))
        except Exception as e:
            self.stats_label.config(text=f"Error loading stats: {e}")

    def load_log(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT log_id, transport_method, distance_km, carbon_saved,
                       trip_date, recorded_date
                FROM green_transport_log
                ORDER BY recorded_date DESC LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['log_id'], r['transport_method'],
                    f"{r['distance_km']:.1f}", f"{r['carbon_saved']:.2f}",
                    r['trip_date'] or '', r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading transport log: {e}")

    def delete_trip(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.selection', default="Selection"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.please_select_a_trip_to_delete', default="Please select a trip to delete."))
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.confirm', default="Confirm"), f"Delete trip #{vals[0]}?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM green_transport_log WHERE log_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self._refresh_all()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greentransportdialog.dialogs.error', default="Error"), f"Failed to delete: {e}")
