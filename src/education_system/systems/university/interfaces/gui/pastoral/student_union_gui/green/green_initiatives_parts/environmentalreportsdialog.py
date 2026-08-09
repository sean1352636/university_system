"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EnvironmentalReportsDialog:
    """Dialog for viewing environmental reports generated from DB data"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.windows.environmental_reports', default="Environmental Reports"))
        self.dialog.geometry("950x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.generate_report()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.labels.environmental_impact_reports', default="Environmental Impact Reports"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Report display
        self.report_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
        self.report_text.pack(fill='both', expand=True, pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.buttons.regenerate_report', default="Regenerate Report"), command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.buttons.save_as_txt', default="Save as TXT"), command=self.save_as_txt).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.buttons.email_to_admin', default="Email to Admin"), command=self.email_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def generate_report(self):
        """Build the sustainability report from actual database data."""
        self.report_text.config(state='normal')
        self.report_text.delete(1.0, tk.END)

        now = datetime.now()
        report_date = now.strftime('%B %Y')
        separator = '=' * 80

        lines = []
        lines.append(f"SUSTAINABILITY REPORT - {report_date.upper()}")
        lines.append(separator)
        lines.append('')

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # --- Carbon Emissions ---
            month_start = now.strftime('%Y-%m-01')
            prev_month_start = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-01')

            cursor.execute('''
                SELECT COALESCE(SUM(total_carbon), 0) as total,
                       COALESCE(SUM(transport_carbon), 0) as transport,
                       COALESCE(SUM(energy_carbon), 0) as energy,
                       COALESCE(SUM(catering_carbon), 0) as catering,
                       COUNT(*) as records
                FROM carbon_tracking
                WHERE recorded_date >= ?
            ''', (month_start,))
            current = cursor.fetchone()

            cursor.execute('''
                SELECT COALESCE(SUM(total_carbon), 0) as total
                FROM carbon_tracking
                WHERE recorded_date >= ? AND recorded_date < ?
            ''', (prev_month_start, month_start))
            prev = cursor.fetchone()

            cur_total = current['total']
            prev_total = prev['total']
            change = ((cur_total - prev_total) / prev_total * 100) if prev_total > 0 else 0

            lines.append('CARBON EMISSIONS:')
            lines.append(f'  Records this month: {current["records"]}')
            lines.append(f'  Total emissions this month: {cur_total:,.1f} kg CO2')
            lines.append(f'  Previous month: {prev_total:,.1f} kg CO2')
            if prev_total > 0:
                direction = "Improvement" if change < 0 else "Increase"
                lines.append(f'  Change: {change:+.1f}% ({direction})')
            lines.append('')
            lines.append('  Breakdown:')
            lines.append(f'  - Transport: {current["transport"]:,.1f} kg CO2')
            lines.append(f'  - Energy: {current["energy"]:,.1f} kg CO2')
            lines.append(f'  - Catering: {current["catering"]:,.1f} kg CO2')
            lines.append('')

            # --- Waste Management ---
            cursor.execute('''
                SELECT COALESCE(SUM(waste_generated), 0) as gen,
                       COALESCE(SUM(waste_recycled), 0) as rec,
                       COALESCE(SUM(waste_composted), 0) as comp,
                       COALESCE(SUM(waste_landfill), 0) as land,
                       COUNT(*) as entries
                FROM waste_reduction_log
                WHERE recorded_date >= ?
            ''', (month_start,))
            waste = cursor.fetchone()

            w_gen = waste['gen']
            w_rec = waste['rec']
            w_comp = waste['comp']
            w_land = waste['land']
            rec_rate = (w_rec / w_gen * 100) if w_gen > 0 else 0
            div_rate = ((w_rec + w_comp) / w_gen * 100) if w_gen > 0 else 0

            lines.append('WASTE MANAGEMENT:')
            lines.append(f'  Events logged: {waste["entries"]}')
            lines.append(f'  Total waste: {w_gen:,.1f} kg')
            lines.append(f'  Recycled: {w_rec:,.1f} kg ({rec_rate:.1f}%)')
            lines.append(f'  Composted: {w_comp:,.1f} kg')
            lines.append(f'  Landfill: {w_land:,.1f} kg')
            lines.append(f'  Landfill diversion rate: {div_rate:.1f}% (Target: 80%)')
            lines.append('')

            # --- Green Transport ---
            cursor.execute('''
                SELECT transport_method,
                       COUNT(*) as trips,
                       COALESCE(SUM(distance_km), 0) as km,
                       COALESCE(SUM(carbon_saved), 0) as saved
                FROM green_transport_log
                WHERE trip_date >= ?
                GROUP BY transport_method
                ORDER BY saved DESC
            ''', (month_start,))
            transport_rows = cursor.fetchall()

            cursor.execute('''
                SELECT COUNT(DISTINCT recorded_by) as users,
                       COALESCE(SUM(carbon_saved), 0) as total_saved
                FROM green_transport_log
                WHERE trip_date >= ?
            ''', (month_start,))
            transport_totals = cursor.fetchone()

            lines.append('GREEN TRANSPORT:')
            lines.append(f'  Active users: {transport_totals["users"]}')
            lines.append(f'  Total CO2 saved: {transport_totals["total_saved"]:,.1f} kg')
            for tr in transport_rows:
                lines.append(f'  - {tr["transport_method"]}: {tr["trips"]} trips, '
                             f'{tr["km"]:.1f} km, {tr["saved"]:.1f} kg CO2 saved')
            lines.append('')

            # --- Green Initiatives ---
            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM green_initiatives
            ''')
            init_row = cursor.fetchone()
            lines.append('GREEN INITIATIVES:')
            lines.append(f'  Total initiatives: {init_row["total"]}')
            lines.append(f'  Active: {init_row["active"] or 0}')
            lines.append(f'  Completed: {init_row["completed"] or 0}')
            lines.append('')

            # --- Eco Suppliers ---
            cursor.execute('SELECT COUNT(*) as cnt FROM eco_suppliers')
            sup_cnt = cursor.fetchone()['cnt']
            lines.append(f'ECO SUPPLIERS: {sup_cnt} registered')
            lines.append('')

            # --- Certifications ---
            cursor.execute('''
                SELECT certification_level, COUNT(*) as cnt
                FROM green_certifications
                GROUP BY certification_level
                ORDER BY cnt DESC
            ''')
            cert_rows = cursor.fetchall()
            lines.append('GREEN CERTIFICATIONS:')
            if cert_rows:
                for cr in cert_rows:
                    lines.append(f'  {cr["certification_level"]}: {cr["cnt"]}')
            else:
                lines.append('  No certifications awarded yet.')
            lines.append('')

            # --- Recommendations ---
            lines.append('RECOMMENDATIONS:')
            rec_num = 1
            if rec_rate < 80 and w_gen > 0:
                lines.append(f'  {rec_num}. Increase recycling rate (currently {rec_rate:.0f}%, target 80%)')
                rec_num += 1
            if cur_total > 0 and current['transport'] > cur_total * 0.4:
                lines.append(f'  {rec_num}. Reduce transport emissions (currently {current["transport"]/cur_total*100:.0f}% of total)')
                rec_num += 1
            if transport_totals['users'] < 5:
                lines.append(f'  {rec_num}. Encourage more users to log green transport trips')
                rec_num += 1
            lines.append(f'  {rec_num}. Continue expanding green initiatives')
            lines.append('')

            conn.close()

        except Exception as e:
            lines.append(f'Error generating report: {e}')
            lines.append('')

        lines.append(separator)
        lines.append(f'Generated: {now.strftime("%Y-%m-%d %H:%M:%S")}')

        self.report_text.insert(1.0, '\n'.join(lines))
        self.report_text.config(state='disabled')

    def save_as_txt(self):
        """Save the report content to a TXT file."""
        self.report_text.config(state='normal')
        content = self.report_text.get(1.0, tk.END).strip()
        self.report_text.config(state='disabled')

        if not content:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.no_report', default="No Report"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.no_report_content_to_save', default="No report content to save."))
            return

        file_path = filedialog.asksaveasfilename(
            parent=self.dialog,
            title=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.save_environmental_report', default="Save Environmental Report"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"sustainability_report_{datetime.now().strftime('%Y%m%d')}.txt"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.success', default="Success"), f"Report saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.error', default="Error"), f"Failed to save report: {e}")

    def email_report(self):
        """Email report to admin from database"""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection as _gc
            from education_system.systems.university.infrastructure.email.email_service.core import send_email

            # Get admin email from database
            admin_email = None
            try:
                conn = _gc()
                cursor = conn.execute("""
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                admin_row = cursor.fetchone()
                if admin_row:
                    admin_email = admin_row['email'] if isinstance(admin_row, sqlite3.Row) else admin_row[0]
                conn.close()
            except Exception as e:
                print(f"Warning: Could not fetch admin email: {e}")

            if not admin_email:
                # Prompt user for email address
                admin_email = simpledialog.askstring(
                    _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.email_address', default="Email Address"),
                    _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.no_admin_email_found_in_database_enter_recipient_email', default="No admin email found in database.\nEnter recipient email:"),
                    parent=self.dialog
                )
                if not admin_email:
                    return

            # Get report content
            self.report_text.config(state='normal')
            report_content = self.report_text.get(1.0, tk.END).strip()
            self.report_text.config(state='disabled')

            if not report_content:
                messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.no_report', default="No Report"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.no_report_content_to_send', default="No report content to send."))
                return

            subject = f"Sustainability Report - {datetime.now().strftime('%B %Y')}"
            body = report_content

            # Try to use render_template if available, fall back to plain text
            try:
                subject, body = render_template('student_union/environmental_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'generation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'separator': '=' * 60,
                    'report_content': report_content
                })
            except Exception:
                pass  # Use plain text subject/body

            result = send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            if result:
                messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.success', default="Success"), f"Report sent successfully to {admin_email}")
            else:
                messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.queued', default="Queued"), f"Report queued for delivery to {admin_email}")

        except ImportError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.email_service_is_not_available', default="Email service is not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.environmentalreportsdialog.dialogs.error', default="Error"), f"Failed to send report: {str(e)}")
