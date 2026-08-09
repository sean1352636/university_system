"""Methods _check_out_visitor through _update_visitor_stats."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsGUI:
    def _check_out_visitor(self):
        """Check out selected visitor."""
        selected = self.visitors_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.please_select_a_visitor', default="Please select a visitor"))
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]
        current_status = item["values"][6]

        if current_status != "checked_in":
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.info', default="Info"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.visitor_is_not_checked_in', default="Visitor is not checked in"))
            return

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE visitor_registrations
                    SET status = 'checked_out', check_out_time = ?
                    WHERE visitor_id = ?
                """, (datetime.now().strftime("%H:%M:%S"), visitor_id))

            log_activity("update", "visitor_registration", visitor_id=visitor_id, details={"action": "checked_out"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.visitor_checked_out', default="Visitor checked out"))
            self._load_visitors()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.error', default="Error"), f"Failed to check out: {e}")

    def _cancel_visitor(self):
        """Cancel visitor registration."""
        selected = self.visitors_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.please_select_a_visitor', default="Please select a visitor"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.cancel_this_visitor_registration', default="Cancel this visitor registration?")):
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE visitor_registrations SET status = 'cancelled' WHERE visitor_id = ?", (visitor_id,))

            log_activity("update", "visitor_registration", visitor_id=visitor_id, details={"action": "cancelled"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.visitor_registration_cancelled', default="Visitor registration cancelled"))
            self._load_visitors()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.dialogs.error', default="Error"), f"Failed to cancel: {e}")

    def _update_visitor_stats(self):
        """Update today's visitor statistics."""
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total scheduled today
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ?", (today,))
                total = cursor.fetchone()[0]

                # Checked in
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ? AND status = 'checked_in'", (today,))
                checked_in = cursor.fetchone()[0]

                # Checked out
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ? AND status = 'checked_out'", (today,))
                checked_out = cursor.fetchone()[0]

                # Pending
                cursor.execute("SELECT COUNT(*) FROM visitor_registrations WHERE scheduled_date = ? AND status = 'scheduled'", (today,))
                pending = cursor.fetchone()[0]

                self.stats_label.config(text=f"Total: {total} | Checked In: {checked_in} | Checked Out: {checked_out} | Pending: {pending}")

        except Exception:
            self.stats_label.config(text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_check_out_visitor.text.stats_unavailable', default="Stats unavailable"))
