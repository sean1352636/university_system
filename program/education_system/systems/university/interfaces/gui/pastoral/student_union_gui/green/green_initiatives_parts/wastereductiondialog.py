"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class WasteReductionDialog:
    """Dialog for waste reduction tracking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.windows.waste_reduction_tracking', default="Waste Reduction Tracking"))
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh_stats()
        self.load_log()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.waste_reduction_recycling', default="Waste Reduction & Recycling"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Stats
        self.stats_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.waste_statistics_from_database', default="Waste Statistics (from database)"))
        self.stats_frame.pack(fill='x', pady=(0, 10))
        self.stats_label = ttk.Label(self.stats_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.loading', default="Loading..."),
                                      justify='left', font=('Courier', 10))
        self.stats_label.pack(padx=15, pady=10)

        # Log new entry form
        form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.log_waste_data', default="Log Waste Data"))
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.event_name', default="Event Name:")).pack(side='left')
        self.event_name_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.event_name_var, width=40).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)

        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.waste_generated_kg', default="Waste Generated (kg):")).pack(side='left')
        self.waste_gen_var = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.waste_gen_var, width=10).pack(side='left', padx=5)

        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.recycled_kg', default="Recycled (kg):")).pack(side='left', padx=(10, 0))
        self.waste_rec_var = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.waste_rec_var, width=10).pack(side='left', padx=5)

        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.composted_kg', default="Composted (kg):")).pack(side='left', padx=(10, 0))
        self.waste_comp_var = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.waste_comp_var, width=10).pack(side='left', padx=5)

        row3 = ttk.Frame(form_frame)
        row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.notes', default="Notes:")).pack(side='left')
        self.notes_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.notes_var, width=60).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(row3, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.buttons.save_entry', default="Save Entry"), command=self.save_entry).pack(side='right', padx=5)

        # History treeview
        hist_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.labels.waste_log_history', default="Waste Log History"))
        hist_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Event', 'Generated', 'Recycled', 'Composted', 'Landfill', 'Rate %', 'Date')
        self.tree = ttk.Treeview(hist_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=90)
        self.tree.column('Event', width=160)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.buttons.refresh', default="Refresh"), command=self._refresh_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def _refresh_all(self):
        self.refresh_stats()
        self.load_log()

    def refresh_stats(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) as entries,
                    COALESCE(SUM(waste_generated), 0) as total_gen,
                    COALESCE(SUM(waste_recycled), 0) as total_rec,
                    COALESCE(SUM(waste_composted), 0) as total_comp,
                    COALESCE(SUM(waste_landfill), 0) as total_land
                FROM waste_reduction_log
            ''')
            row = cursor.fetchone()
            conn.close()

            entries = row['entries']
            total_gen = row['total_gen']
            total_rec = row['total_rec']
            total_comp = row['total_comp']
            total_land = row['total_land']
            rate = (total_rec / total_gen * 100) if total_gen > 0 else 0
            diversion = ((total_rec + total_comp) / total_gen * 100) if total_gen > 0 else 0

            stats_text = (
                f"Events Logged: {entries}\n"
                f"Total Waste Generated: {total_gen:.1f} kg\n"
                f"Recycled: {total_rec:.1f} kg ({rate:.1f}%)\n"
                f"Composted: {total_comp:.1f} kg\n"
                f"Landfill: {total_land:.1f} kg\n"
                f"Landfill Diversion Rate: {diversion:.1f}%\n"
                f"Target: 80% diversion from landfill"
            )
            self.stats_label.config(text=stats_text)
        except Exception as e:
            self.stats_label.config(text=f"Error loading stats: {e}")

    def load_log(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT log_id, event_name, waste_generated, waste_recycled,
                       waste_composted, waste_landfill, recycling_rate, recorded_date
                FROM waste_reduction_log ORDER BY recorded_date DESC LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['log_id'], r['event_name'] or '',
                    f"{r['waste_generated']:.1f}", f"{r['waste_recycled']:.1f}",
                    f"{r['waste_composted']:.1f}", f"{r['waste_landfill']:.1f}",
                    f"{r['recycling_rate']:.1f}", r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading waste log: {e}")

    def save_entry(self):
        event_name = self.event_name_var.get().strip()
        if not event_name:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.please_enter_an_event_name', default="Please enter an event name."))
            return
        try:
            generated = float(self.waste_gen_var.get() or 0)
            recycled = float(self.waste_rec_var.get() or 0)
            composted = float(self.waste_comp_var.get() or 0)
        except ValueError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.please_enter_valid_numbers_for_waste_amounts', default="Please enter valid numbers for waste amounts."))
            return

        if recycled + composted > generated:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.recycled_composted_cannot_exceed_total_waste_generated', default="Recycled + composted cannot exceed total waste generated."))
            return

        landfill = generated - recycled - composted
        rate = (recycled / generated * 100) if generated > 0 else 0

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO waste_reduction_log
                    (event_name, waste_generated, waste_recycled, waste_composted,
                     waste_landfill, recycling_rate, notes, recorded_by, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_name, generated, recycled, composted, landfill, rate,
                self.notes_var.get().strip(),
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.success', default="Success"),
                                f"Waste data saved for '{event_name}'.\n"
                                f"Recycling rate: {rate:.1f}%")
            self.event_name_var.set('')
            self.waste_gen_var.set('0')
            self.waste_rec_var.set('0')
            self.waste_comp_var.set('0')
            self.notes_var.set('')
            self._refresh_all()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.wastereductiondialog.dialogs.error', default="Error"), f"Failed to save: {e}")
