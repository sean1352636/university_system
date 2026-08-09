"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class GreenCertificationsDialog:
    """Dialog for managing green certifications."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.windows.green_certifications', default="Green Certifications"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_certifications()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.green_certification_management', default="Green Certification Management"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Standards info
        info_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.certification_levels', default="Certification Levels"))
        info_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(info_frame,
                  text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.bronze_70_79_pts_basic_sustainability_practices_silver_80_89_pts', default="Bronze (70-79 pts): Basic sustainability practices  |  "
                       "Silver (80-89 pts): Comprehensive management  |  "
                       "Gold (90-95 pts): 90%+ waste diverted  |  "
                       "Platinum (95+ pts): Net carbon negative"),
                  wraplength=800).pack(padx=10, pady=8)

        # Award certification form
        form_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.award_certification', default="Award Certification"))
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.entity_name', default="Entity Name:")).pack(side='left')
        self.entity_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.entity_var, width=25).pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.type', default="Type:")).pack(side='left', padx=(10, 0))
        self.type_var = tk.StringVar()
        ttk.Combobox(row1, textvariable=self.type_var, width=15,
                      values=["Club", "Event", "Individual", "Department"],
                      state='readonly').pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.level', default="Level:")).pack(side='left', padx=(10, 0))
        self.level_var = tk.StringVar()
        ttk.Combobox(row1, textvariable=self.level_var, width=12,
                      values=["Bronze", "Silver", "Gold", "Platinum"],
                      state='readonly').pack(side='left', padx=5)

        ttk.Label(row1, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.score', default="Score:")).pack(side='left', padx=(10, 0))
        self.score_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.score_var, width=6).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.notes', default="Notes:")).pack(side='left')
        self.notes_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.notes_var, width=60).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(row2, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.buttons.award', default="Award"), command=self.award_cert).pack(side='right', padx=5)

        # Certifications list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.labels.awarded_certifications', default="Awarded Certifications"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Entity', 'Type', 'Level', 'Score', 'Awarded', 'Expires', 'Notes')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        self.tree.column('ID', width=40)
        self.tree.column('Entity', width=160)
        self.tree.column('Notes', width=150)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.buttons.refresh', default="Refresh"), command=self.load_certifications).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.buttons.revoke_selected', default="Revoke Selected"), command=self.revoke_cert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right', padx=5)

    def load_certifications(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT cert_id, entity_name, entity_type, certification_level,
                       score, awarded_date, expires_date, notes
                FROM green_certifications
                ORDER BY awarded_date DESC
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['cert_id'], r['entity_name'], r['entity_type'] or '',
                    r['certification_level'], f"{r['score']:.0f}" if r['score'] else '',
                    r['awarded_date'] or '', r['expires_date'] or '',
                    r['notes'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading certifications: {e}")

    def award_cert(self):
        entity = self.entity_var.get().strip()
        etype = self.type_var.get().strip()
        level = self.level_var.get().strip()
        if not entity or not level:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.please_fill_in_entity_name_and_level', default="Please fill in entity name and level."))
            return
        try:
            score = float(self.score_var.get() or 0)
        except ValueError:
            score = 0

        awarded = datetime.now().strftime('%Y-%m-%d')
        expires = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO green_certifications
                    (entity_name, entity_type, certification_level, score,
                     awarded_date, expires_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (entity, etype or 'Other', level, score, awarded, expires,
                  self.notes_var.get().strip()))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.success', default="Success"),
                                f"{level} certification awarded to '{entity}'.\n"
                                f"Valid until: {expires}")
            self.entity_var.set('')
            self.type_var.set('')
            self.level_var.set('')
            self.score_var.set('0')
            self.notes_var.set('')
            self.load_certifications()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.error', default="Error"), f"Failed to award certification: {e}")

    def revoke_cert(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.selection', default="Selection"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.please_select_a_certification_to_revoke', default="Please select a certification to revoke."))
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.confirm', default="Confirm"), f"Revoke {vals[3]} certification for '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM green_certifications WHERE cert_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_certifications()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.greencertificationsdialog.dialogs.error', default="Error"), f"Failed to revoke: {e}")
