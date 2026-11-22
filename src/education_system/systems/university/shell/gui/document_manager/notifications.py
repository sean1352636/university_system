import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


# ----------------------------------------------------------------------
# Real recipient selection and delivery.
#
# The standalone ``notifications`` table was retired (the Hub is an inbox
# over ``messages``), so Document Manager notices are delivered the way the
# rest of the university does it: e-mail through ``email_service.send_email``
# (the outbox, which honours the delivery mode, unsubscribes and retries)
# and the in-app copy through ``messages_inbox.deliver_inbox_message``.
# SMS goes through ``communication.sms_service`` only when a real provider
# is configured in ``sms_config``; otherwise it is reported as skipped.
# ----------------------------------------------------------------------

# Join documents to their student whichever schema shape wrote the row
# (``owner_id`` + source_type='student' from upload, legacy ``student_id``).
_DOC_OWNER = "COALESCE(NULLIF(d.owner_id, ''), d.student_id)"

RECIPIENT_FILTERS = {
    "all_students": None,
    "pending_docs": "d.verification_status = 'Pending'",
    "rejected_docs": "d.verification_status = 'Rejected'",
    "expiring_docs": ("d.expiry_date IS NOT NULL AND d.expiry_date != '' "
                      "AND date(d.expiry_date) > date('now') "
                      "AND date(d.expiry_date) <= date('now', '+30 days')"),
    "expired_or_expiring": ("d.expiry_date IS NOT NULL AND d.expiry_date != '' "
                            "AND date(d.expiry_date) <= date('now', '+30 days')"),
}


def resolve_student_recipients(option, custom_ids=None):
    """Students selected by a recipient option, with their affected documents.

    Returns a list of dicts: student_id, name, email, phone, documents
    (list of "Type (status)" strings for the documents that matched), and
    pending_count (that student's documents awaiting review).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        params = []
        if option == "custom":
            ids = [i.strip() for i in (custom_ids or []) if str(i).strip()]
            if not ids:
                return []
            marks = ",".join("?" * len(ids))
            # db-audit: ignore[DBW001] - only module-constant SQL fragments / placeholder joins are interpolated
            cur.execute(f"SELECT student_id, first_name, last_name, email_address, phone "
                        f"FROM students WHERE student_id IN ({marks})", ids)
        elif option == "missing_docs":
            # db-audit: ignore[DBW001] - only module-constant SQL fragments / placeholder joins are interpolated
            cur.execute(f"""
                SELECT s.student_id, s.first_name, s.last_name, s.email_address, s.phone
                FROM students s
                WHERE NOT EXISTS (SELECT 1 FROM documents d WHERE {_DOC_OWNER} = s.student_id)
            """)
        elif option in RECIPIENT_FILTERS and RECIPIENT_FILTERS[option]:
            # db-audit: ignore[DBW001] - only module-constant SQL fragments / placeholder joins are interpolated
            cur.execute(f"""
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address, s.phone
                FROM students s
                JOIN documents d ON {_DOC_OWNER} = s.student_id
                WHERE COALESCE(d.is_current_version, 1) = 1 AND {RECIPIENT_FILTERS[option]}
            """)
        else:
            cur.execute("SELECT student_id, first_name, last_name, email_address, phone FROM students")
        students = [tuple(r) for r in cur.fetchall()]

        doc_filter = RECIPIENT_FILTERS.get(option) or "1=1"
        recipients = []
        for sid, first, last, email, phone in students:
            # db-audit: ignore[DBW001] - only module-constant SQL fragments / placeholder joins are interpolated
            cur.execute(f"""
                SELECT COALESCE(dt.type_name, d.document_type, d.original_filename, 'Document'),
                       COALESCE(d.verification_status, d.status, ''), d.expiry_date
                FROM documents d
                LEFT JOIN document_types dt
                       ON dt.type_id = COALESCE(d.type_id, d.document_type_id)
                WHERE {_DOC_OWNER} = ? AND COALESCE(d.is_current_version, 1) = 1
                  AND {doc_filter}
                ORDER BY d.upload_date DESC
            """, (sid,))
            docs = []
            for name, status, expiry in cur.fetchall():
                label = f"{name} ({status})" if status else str(name)
                if option in ("expiring_docs", "expired_or_expiring") and expiry:
                    label += f" - expires {expiry}"
                docs.append(label)
            # db-audit: ignore[DBW001] - only module-constant SQL fragments / placeholder joins are interpolated
            cur.execute(f"SELECT COUNT(*) FROM documents d WHERE {_DOC_OWNER} = ? "
                        "AND d.verification_status = 'Pending' "
                        "AND COALESCE(d.is_current_version, 1) = 1", (sid,))
            pending = cur.fetchone()[0]
            recipients.append({
                'student_id': str(sid),
                'name': f"{first or ''} {last or ''}".strip() or str(sid),
                'email': (email or '').strip(),
                'phone': (phone or '').strip(),
                'documents': docs,
                'pending_count': pending,
            })
        return recipients


def render_for_student(text, recipient):
    """Fill the {{placeholder}} tokens the campaign editor advertises."""
    values = {
        'student_name': recipient['name'],
        'student_id': recipient['student_id'],
        'pending_count': str(recipient['pending_count']),
        'document_list': "\n".join(f"- {d}" for d in recipient['documents']) or "- (none)",
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def _configured_sms_service():
    """An SMSService on the configured real provider, or None."""
    try:
        from education_system.systems.university.infrastructure.auth.sms_provider import (
            load_sms_config,
        )
        from education_system.systems.university.infrastructure.communication.sms_service import (
            SMSProvider, SMSService,
        )
        provider = SMSProvider(str(load_sms_config().get('primary_provider') or '').lower())
    except Exception:
        return None
    if provider == SMSProvider.MOCK:
        return None
    return SMSService(provider)


def deliver_to_students(recipients, subject, body, *, email=True, inbox=True, sms=False,
                        sender_id=None, kind="bulk", category="documents"):
    """Deliver a notice to each recipient on the chosen channels.

    Returns counts: email_sent, email_failed, no_email, inbox_sent,
    inbox_failed (no university account), sms_sent, sms_failed, no_phone,
    sms_unavailable (bool).
    """
    stats = {'email_sent': 0, 'email_failed': 0, 'no_email': 0,
             'inbox_sent': 0, 'inbox_failed': 0,
             'sms_sent': 0, 'sms_failed': 0, 'no_phone': 0, 'sms_unavailable': False}
    send_email = deliver_inbox_message = None
    if email:
        from education_system.systems.university.infrastructure.email.email_service import send_email
    if inbox:
        from education_system.systems.university.infrastructure.email.messages_inbox import deliver_inbox_message
    sms_service = _configured_sms_service() if sms else None
    if sms and sms_service is None:
        stats['sms_unavailable'] = True

    for r in recipients:
        r_subject = render_for_student(subject, r)
        r_body = render_for_student(body, r)
        if email:
            if not r['email']:
                stats['no_email'] += 1
            else:
                try:
                    ok = send_email(r['email'], r_subject, r_body, kind=kind,
                                    category=category, to_ref=r['student_id'])
                except Exception as exc:
                    logger.warning("Document notice e-mail to %s failed: %s", r['email'], exc)
                    ok = False
                stats['email_sent' if ok else 'email_failed'] += 1
        if inbox:
            msg_id = deliver_inbox_message(r['student_id'], r_subject, r_body, sender_id=sender_id)
            stats['inbox_sent' if msg_id else 'inbox_failed'] += 1
        if sms_service is not None:
            if not r['phone']:
                stats['no_phone'] += 1
            else:
                ok = sms_service.send_sms(r['phone'], f"{r_subject}: {r_body}"[:1600],
                                          student_id=r['student_id'], related_to='document_manager')
                stats['sms_sent' if ok else 'sms_failed'] += 1
    return stats


def delivery_summary(stats, recipient_count, email=True, inbox=True, sms=False):
    """Human-readable result lines for a deliver_to_students() run."""
    lines = [f"Recipients: {recipient_count}"]
    if email:
        line = f"E-mail queued: {stats['email_sent']}"
        if stats['email_failed']:
            line += f", failed: {stats['email_failed']}"
        if stats['no_email']:
            line += f", no address: {stats['no_email']}"
        lines.append(line)
    if inbox:
        line = f"Portal inbox messages: {stats['inbox_sent']}"
        if stats['inbox_failed']:
            line += f" ({stats['inbox_failed']} without a portal account)"
        lines.append(line)
    if sms:
        if stats['sms_unavailable']:
            lines.append("SMS: not sent - no SMS provider is configured")
        else:
            line = f"SMS sent: {stats['sms_sent']}"
            if stats['sms_failed']:
                line += f", failed: {stats['sms_failed']}"
            if stats['no_phone']:
                line += f", no phone: {stats['no_phone']}"
            lines.append(line)
    return "\n".join(lines)


def _sender_id(gui):
    user = getattr(gui, 'current_user', None) or {}
    return user.get('id') if isinstance(user, dict) else None


# The notification queue is the university outbox, limited to the
# e-mails this module sends (category 'documents').
_QUEUE_FILTERS = {
    'All': None,
    'Pending': "status IN ('queued', 'sending')",
    'Sent': "status IN ('sent', 'stored')",
    'Failed': "status IN ('failed', 'bounced', 'suppressed', 'cancelled')",
}


def queue_rows(status_filter='Pending', limit=500):
    """(id, recipient, channel, subject, created, kind, status) outbox rows."""
    where = _QUEUE_FILTERS.get(status_filter)
    sql = ("SELECT message_id, COALESCE(NULLIF(to_ref, ''), to_address), 'E-mail', subject, "
           "created_at, kind, status FROM email_outbox WHERE category = 'documents'")
    if where:
        # db-audit: ignore[DBW001] - only module-constant SQL fragments / placeholder joins are interpolated
        sql += f" AND {where}"
    sql += " ORDER BY message_id DESC LIMIT ?"
    with get_connection() as conn:
        # db-audit: ignore[DBW001] - only module-constant SQL fragments are interpolated
        return [tuple(r) for r in conn.execute(sql, (int(limit),)).fetchall()]


def queue_counts():
    """pending / sent today / failed counts for the documents outbox."""
    with get_connection() as conn:
        # db-audit: ignore[DBW001] - only module-constant SQL fragments are interpolated
        pending = conn.execute("SELECT COUNT(*) FROM email_outbox WHERE category = 'documents' "
                               f"AND {_QUEUE_FILTERS['Pending']}").fetchone()[0]
        sent_today = conn.execute("SELECT COUNT(*) FROM email_outbox WHERE category = 'documents' "
                                  "AND status IN ('sent', 'stored') "
                                  "AND date(COALESCE(sent_at, created_at)) = date('now')").fetchone()[0]
        # db-audit: ignore[DBW001] - only module-constant SQL fragments are interpolated
        failed = conn.execute("SELECT COUNT(*) FROM email_outbox WHERE category = 'documents' "
                              f"AND {_QUEUE_FILTERS['Failed']}").fetchone()[0]
    return pending, sent_today, failed


def _actor(gui):
    user = getattr(gui, 'current_user', None) or {}
    return user.get('username') or 'unknown', user.get('role') or ''


def queue_send(gui, message_ids):
    """Retry failed/cancelled messages and start a delivery pass.

    Returns (requeued, already_queued, refused) where refused is a list of
    "id: reason" strings.
    """
    from education_system.systems.university.application.mail import outbox as email_outbox
    from education_system.systems.university.infrastructure.email import outbox_delivery
    actor, role = _actor(gui)
    requeued, waiting, refused = 0, 0, []
    with get_connection() as conn:
        for mid in message_ids:
            row = conn.execute("SELECT status FROM email_outbox WHERE message_id = ?", (mid,)).fetchone()
            if not row:
                refused.append(f"{mid}: not found")
                continue
            if row[0] in ('queued', 'sending'):
                waiting += 1
                continue
            try:
                email_outbox.retry(conn, actor, role, mid)
                requeued += 1
            except (PermissionError, ValueError) as exc:
                refused.append(f"{mid}: {exc}")
        conn.commit()
    outbox_delivery.kick()
    return requeued, waiting, refused


def queue_cancel(gui, message_ids):
    """Cancel queued messages. Returns (cancelled, refused)."""
    from education_system.systems.university.application.mail import outbox as email_outbox
    actor, role = _actor(gui)
    cancelled, refused = 0, []
    with get_connection() as conn:
        for mid in message_ids:
            try:
                email_outbox.cancel(conn, actor, role, mid)
                cancelled += 1
            except (PermissionError, ValueError) as exc:
                refused.append(f"{mid}: {exc}")
        conn.commit()
    return cancelled, refused


def _refused_text(refused):
    if not refused:
        return ""
    shown = "\n".join(refused[:10])
    more = f"\n... and {len(refused) - 10} more" if len(refused) > 10 else ""
    return f"\n\nNot changed:\n{shown}{more}"


class NotificationManager:
    """Manages notification center, templates, bulk sends, and notification campaigns."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def notification_center(self):
        """Full notification center interface"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.shell.document_manager.notifications.windows.notification_center', default="Notification Center"))
        dialog.geometry("800x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Create notebook for notification management
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Pending Notifications Tab
        pending_frame = ttk.Frame(notebook, padding=15)
        notebook.add(pending_frame, text=_t('gui.shell.document_manager.notifications.tabs.pending_notifications', default="Pending Notifications"))

        ttk.Label(pending_frame, text=_t('gui.shell.document_manager.notifications.labels.pending_notifications', default="Pending Notifications"), font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Notifications list
        notif_columns = ('ID', 'Recipient', 'Type', 'Title', 'Created', 'Priority', 'Status')
        self.notifications_tree = ttk.Treeview(pending_frame, columns=notif_columns, show='headings', height=12)

        for col in notif_columns:
            self.notifications_tree.heading(col, text=col)
            self.notifications_tree.column(col, width=100)

        notif_scrollbar = ttk.Scrollbar(pending_frame, orient='vertical', command=self.notifications_tree.yview)
        self.notifications_tree.configure(yscrollcommand=notif_scrollbar.set)

        self.notifications_tree.pack(side='left', fill='both', expand=True)
        notif_scrollbar.pack(side='right', fill='y')

        # Notification actions
        notif_actions_frame = ttk.Frame(pending_frame)
        notif_actions_frame.pack(fill='x', pady=10)

        ttk.Button(notif_actions_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_selected', default="Send Selected"), command=self.send_selected_notifications).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text=_t('gui.shell.document_manager.notifications.buttons.mark_as_sent', default="Mark as Sent"), command=self.mark_notifications_sent).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text=_t('gui.shell.document_manager.notifications.buttons.delete', default="Delete"), command=self.delete_notifications).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text=_t('gui.shell.document_manager.notifications.buttons.refresh', default="Refresh"), command=self.load_notifications).pack(side='right', padx=5)

        # Send Notification Tab
        send_frame = ttk.Frame(notebook, padding=15)
        notebook.add(send_frame, text=_t('gui.shell.document_manager.notifications.tabs.send_notification', default="Send Notification"))

        ttk.Label(send_frame, text=_t('gui.shell.document_manager.notifications.labels.send_custom_notification', default="Send Custom Notification"), font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        # Recipient selection
        ttk.Label(send_frame, text=_t('gui.shell.document_manager.notifications.labels.recipient', default="Recipient:")).pack(anchor='w')
        self.notif_recipient = ttk.Combobox(send_frame, width=40)
        self.notif_recipient.pack(fill='x', pady=5)

        # Load recipients
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, first_name, last_name FROM students')
            students = cursor.fetchall()
            conn.close()

            recipient_values = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
            self.notif_recipient['values'] = recipient_values
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        # Notification type
        ttk.Label(send_frame, text=_t('gui.shell.document_manager.notifications.labels.type', default="Type:")).pack(anchor='w', pady=(10, 0))
        self.notif_type = ttk.Combobox(send_frame, values=['document_reminder', 'verification_complete', 'expiry_warning', 'general', 'urgent'])
        self.notif_type.set('general')
        self.notif_type.pack(fill='x', pady=5)

        # Priority
        ttk.Label(send_frame, text=_t('gui.shell.document_manager.notifications.labels.priority', default="Priority:")).pack(anchor='w', pady=(10, 0))
        self.notif_priority = ttk.Combobox(send_frame, values=['low', 'normal', 'high', 'urgent'])
        self.notif_priority.set('normal')
        self.notif_priority.pack(fill='x', pady=5)

        # Title
        ttk.Label(send_frame, text=_t('gui.shell.document_manager.notifications.labels.title', default="Title:")).pack(anchor='w', pady=(10, 0))
        self.notif_title = tk.Entry(send_frame, width=50)
        self.notif_title.pack(fill='x', pady=5)

        # Message
        ttk.Label(send_frame, text=_t('gui.shell.document_manager.notifications.labels.message', default="Message:")).pack(anchor='w', pady=(10, 0))
        self.notif_message = tk.Text(send_frame, height=6, width=50)
        self.notif_message.pack(fill='x', pady=5)

        ttk.Button(send_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_notification', default="Send Notification"), command=self.send_custom_notification).pack(pady=15)

        # Templates Tab
        templates_frame = ttk.Frame(notebook, padding=15)
        notebook.add(templates_frame, text=_t('gui.shell.document_manager.notifications.tabs.templates', default="Templates"))

        ttk.Label(templates_frame, text=_t('gui.shell.document_manager.notifications.labels.notification_templates', default="Notification Templates"), font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        template_list = [
            ("Document Upload Confirmation", "Your document has been uploaded successfully."),
            ("Verification Complete", "Your document has been verified and approved."),
            ("Document Rejected", "Your document requires attention. Please review and resubmit."),
            ("Expiry Warning", "Your document will expire soon. Please renew."),
            ("Missing Document Reminder", "You have missing required documents.")
        ]

        for title, template in template_list:
            template_frame = ttk.Frame(templates_frame)
            template_frame.pack(fill='x', pady=5)

            ttk.Label(template_frame, text=title, width=30).pack(side='left')
            ttk.Button(template_frame, text=_t('gui.shell.document_manager.notifications.buttons.use_template', default="Use Template"),
                      command=lambda t=title, msg=template: self.use_notification_template(t, msg)).pack(side='right')

        # Load initial data
        self.load_notifications()

        ttk.Button(main_frame, text=_t('gui.shell.document_manager.notifications.buttons.close', default="Close"), command=dialog.destroy).pack()

    def load_notifications(self):
        """Load pending notifications (queued Document Manager e-mails)"""
        if hasattr(self, 'notifications_tree'):
            try:
                rows = queue_rows('Pending', limit=100)

                # Clear existing items
                for item in self.notifications_tree.get_children():
                    self.notifications_tree.delete(item)

                if not rows:
                    self.notifications_tree.insert('', 'end', values=(
                        '', _t('gui.shell.document_manager.notifications.labels.queue_empty',
                               default="Nothing waiting to be sent"), '', '', '', '', ''))
                    return
                for row in rows:
                    self.notifications_tree.insert('', 'end', values=row)

            except Exception as e:
                logger.error("Error loading notifications: %s", e)

    def send_custom_notification(self):
        """Send custom notification"""
        recipient = self.notif_recipient.get()
        notif_type = self.notif_type.get()
        priority = self.notif_priority.get()
        title = self.notif_title.get()
        message = self.notif_message.get('1.0', 'end-1c')

        if not recipient or not title or not message:
            messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), _t('gui.shell.document_manager.notifications.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields"))
            return

        try:
            # Extract recipient ID
            recipient_id = recipient.split(' - ')[0].strip()
            recipients = resolve_student_recipients("custom", [recipient_id])
            if not recipients:
                messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"),
                                     f"No student with ID {recipient_id}.", parent=self.notif_title.winfo_toplevel())
                return
            subject = f"[{priority.upper()}] {title}" if priority in ('high', 'urgent') else title
            stats = deliver_to_students(recipients, subject, message, email=True, inbox=True,
                                        sender_id=_sender_id(self.gui), kind="transactional")
            self.gui.log_event('send', 'notification', details={
                'recipient_id': recipient_id, 'type': notif_type, 'priority': priority, 'stats': stats})

            messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.success', default="Success"),
                                delivery_summary(stats, 1), parent=self.notif_title.winfo_toplevel())

            # Clear form
            self.notif_title.delete(0, 'end')
            self.notif_message.delete('1.0', 'end')
            self.load_notifications()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to send notification: {str(e)}")

    def _selected_queue_ids(self, tree):
        ids = []
        for item in tree.selection():
            values = tree.item(item).get('values') or []
            if values and str(values[0]).isdigit():
                ids.append(int(values[0]))
        return ids

    def send_selected_notifications(self):
        """Send selected notifications (retry failed ones, then deliver)"""
        ids = self._selected_queue_ids(self.notifications_tree)
        if not ids:
            messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.no_selection', default="No Selection"), _t('gui.shell.document_manager.notifications.dialogs.please_select_notifications_to_send_variant_2', default="Please select notifications to send."),
                                   parent=self.notifications_tree.winfo_toplevel())
            return

        try:
            requeued, waiting, refused = queue_send(self.gui, ids)
            messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.success', default="Success"),
                                f"Re-queued: {requeued}\nAlready queued: {waiting}\n"
                                "A delivery pass has been started (no e-mail leaves while the "
                                "outbox is in inbox-only mode)." + _refused_text(refused),
                                parent=self.notifications_tree.winfo_toplevel())
            self.load_notifications()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to send notifications: {str(e)}")

    def mark_notifications_sent(self):
        """Mark selected notifications as handled so they are not e-mailed"""
        ids = self._selected_queue_ids(self.notifications_tree)
        parent = self.notifications_tree.winfo_toplevel()
        if not ids:
            messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.no_selection', default="No Selection"), _t('gui.shell.document_manager.notifications.dialogs.please_select_notifications_to_mark_as_sent', default="Please select notifications to mark as sent."),
                                   parent=parent)
            return

        if messagebox.askyesno(_t('gui.shell.document_manager.notifications.dialogs.confirm', default="Confirm"),
                               _t('gui.shell.document_manager.notifications.dialogs.mark_handled_confirm',
                                  default="Mark the selected notifications as handled?\n\n"
                                          "They will be taken out of the queue and not e-mailed. "
                                          "The student's portal inbox copy is kept."),
                               parent=parent):
            try:
                cancelled, refused = queue_cancel(self.gui, ids)
                messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.success', default="Success"),
                                    f"Marked handled: {cancelled}" + _refused_text(refused), parent=parent)
                self.load_notifications()

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to mark notifications: {str(e)}")

    def delete_notifications(self):
        """Delete (cancel) selected queued notifications"""
        ids = self._selected_queue_ids(self.notifications_tree)
        parent = self.notifications_tree.winfo_toplevel()
        if not ids:
            messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.no_selection', default="No Selection"), _t('gui.shell.document_manager.notifications.dialogs.please_select_notifications_to_delete_variant_2', default="Please select notifications to delete."),
                                   parent=parent)
            return

        if messagebox.askyesno(_t('gui.shell.document_manager.notifications.dialogs.confirm_delete', default="Confirm Delete"),
                               f"Cancel {len(ids)} selected notification(s)? They will not be sent; "
                               "the outbox keeps a cancelled record for audit.", parent=parent):
            try:
                cancelled, refused = queue_cancel(self.gui, ids)
                messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.success', default="Success"),
                                    f"Cancelled: {cancelled}" + _refused_text(refused), parent=parent)
                self.load_notifications()

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to delete notifications: {str(e)}")

    def use_notification_template(self, title, message):
        """Use notification template"""
        title_entry = getattr(self, 'notif_title', None)
        try:
            alive = title_entry is not None and title_entry.winfo_exists()
        except tk.TclError:
            alive = False
        if not alive:
            # Open the Send Notification form so the template has somewhere to go.
            self.notification_center()
        self.notif_title.delete(0, 'end')
        self.notif_title.insert(0, title)

        self.notif_message.delete('1.0', 'end')
        self.notif_message.insert('1.0', message)

    def notification_templates(self):
        """Manage notification templates"""
        try:
            templates_window = tk.Toplevel(self.root)
            templates_window.title(_t('gui.shell.document_manager.notifications.windows.notification_templates', default="Notification Templates"))
            templates_window.geometry("900x700")

            main_frame = ttk.Frame(templates_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.notification_templates', default="Notification Templates"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Pre-defined templates
            templates = [
                ("Document Expiring Soon", "Your {document_type} will expire on {expiry_date}. Please renew it soon."),
                ("Document Verified", "Your {document_type} has been verified and approved."),
                ("Document Rejected", "Your {document_type} was rejected. Reason: {reason}"),
                ("Missing Document", "You are missing a required {document_type}. Please upload it."),
                ("Workflow Step Complete", "Workflow step '{step_name}' has been completed for your {document_type}.")
            ]

            # Create list
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox
            template_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10))
            template_listbox.pack(side='left', fill='both', expand=True)

            for name, _ in templates:
                template_listbox.insert(tk.END, name)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=template_listbox.yview)
            template_listbox.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')

            # Template preview
            preview_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.notifications.labels.template_preview', default="Template Preview"), padding=10)
            preview_frame.pack(fill='x', pady=10)

            preview_text = tk.Text(preview_frame, height=5, wrap=tk.WORD)
            preview_text.pack(fill='x')

            def show_template(event):
                selection = template_listbox.curselection()
                if selection:
                    _, template_text = templates[selection[0]]
                    preview_text.delete('1.0', tk.END)
                    preview_text.insert('1.0', template_text)

            template_listbox.bind('<<ListboxSelect>>', show_template)

            # Buttons
            button_frame = ttk.Frame(templates_window)
            button_frame.pack(pady=10)

            def use_selected():
                selection = template_listbox.curselection()
                if not selection:
                    messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.no_selection', default="No Selection"),
                                           _t('gui.shell.document_manager.notifications.dialogs.select_a_template', default="Select a template first."),
                                           parent=templates_window)
                    return
                name, text = templates[selection[0]]
                self.use_notification_template(name, text)

            ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.use_template', default="Use Template"),
                      command=use_selected).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.close', default="Close"), command=templates_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to open templates: {e}")

    def create_notification(self, recipient_id, title, message, notification_type='info',
                          priority='normal', related_document_id=None):
        """
        Notify a student (portal inbox + e-mail) or a user (portal inbox)

        Args:
            recipient_id: Student ID, username or users.id
            title: Notification title
            message: Notification message
            notification_type: Type of notification (info, warning, error, success)
            priority: Priority level (low, normal, high)
            related_document_id: Related document ID (optional)

        Returns:
            the portal inbox message id if delivered, None otherwise
        """
        try:
            recipients = resolve_student_recipients("custom", [str(recipient_id)])
            if recipients:
                stats = deliver_to_students(recipients, title, message, email=True, inbox=True,
                                            sender_id=_sender_id(self.gui), kind="transactional")
                delivered = stats['inbox_sent'] or stats['email_sent']
                notification_id = related_document_id if delivered else None
            else:
                from education_system.systems.university.infrastructure.email.messages_inbox import deliver_inbox_message
                notification_id = deliver_inbox_message(recipient_id, title, message,
                                                        sender_id=_sender_id(self.gui))
                delivered = notification_id is not None

            self.gui.log_event('create', 'notification', related_document_id, {
                'recipient_id': recipient_id,
                'type': notification_type,
                'priority': priority,
                'delivered': bool(delivered),
            })

            return notification_id if delivered else None

        except Exception as e:
            logger.error("Error creating notification: %s", e)
            return None

    def view_pending_notifications(self):
        """
        View pending/queued notifications
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.shell.document_manager.notifications.windows.pending_notifications', default="Pending Notifications"))
            dialog.geometry("1100x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.pending_notifications', default="Pending Notifications"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                pending, sent_today, failed = queue_counts()

                self.gui.create_stat_card(summary_frame, "Pending", pending, '#f39c12', 0)
                self.gui.create_stat_card(summary_frame, "Sent Today", sent_today, '#27ae60', 1)
                self.gui.create_stat_card(summary_frame, "Failed", failed, '#e74c3c', 2)

            except Exception:


                logger.debug("Suppressed exception", exc_info=True)

            # Filter frame
            filter_frame = ttk.Frame(main_frame)
            filter_frame.pack(fill='x', pady=(0, 10))

            ttk.Label(filter_frame, text=_t('gui.shell.document_manager.notifications.labels.filter', default="Filter:")).pack(side='left', padx=5)
            filter_status = ttk.Combobox(filter_frame, values=['All', 'Pending', 'Sent', 'Failed'], width=15, state='readonly')
            filter_status.set('Pending')
            filter_status.pack(side='left', padx=5)

            # Notifications list
            notif_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.notifications.labels.notification_queue', default="Notification Queue"), padding=10)
            notif_frame.pack(fill='both', expand=True)

            columns = ('ID', 'Recipient', 'Type', 'Title', 'Created', 'Status', 'Priority')
            notif_tree = ttk.Treeview(notif_frame, columns=columns, show='headings', height=15)

            for col in columns:
                notif_tree.heading(col, text=col)
                if col == 'ID':
                    notif_tree.column(col, width=50)
                elif col in ['Type', 'Status', 'Priority']:
                    notif_tree.column(col, width=80)
                else:
                    notif_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(notif_frame, orient='vertical', command=notif_tree.yview)
            notif_tree.configure(yscrollcommand=scrollbar.set)
            notif_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load notifications
            def load_notifications():
                notif_tree.delete(*notif_tree.get_children())
                try:
                    for notif in queue_rows(filter_status.get()):
                        notif_tree.insert('', 'end', values=notif)

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to load notifications: {e}",
                                         parent=dialog)

            load_notifications()
            filter_status.bind('<<ComboboxSelected>>', lambda e: load_notifications())

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            def send_selected():
                ids = self._selected_queue_ids(notif_tree)
                if not ids:
                    messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.notifications.dialogs.please_select_notifications_to_send', default="Please select notifications to send"),
                                           parent=dialog)
                    return

                response = messagebox.askyesno(_t('gui.shell.document_manager.notifications.dialogs.confirm_send', default="Confirm Send"),
                                             f"Send {len(ids)} selected notifications?", parent=dialog)
                if response:
                    try:
                        requeued, waiting, refused = queue_send(self.gui, ids)
                        messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.success', default="Success"),
                                            f"Re-queued: {requeued}\nAlready queued: {waiting}\n"
                                            "A delivery pass has been started." + _refused_text(refused),
                                            parent=dialog)
                        load_notifications()

                    except Exception as e:
                        messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to send notifications: {e}",
                                             parent=dialog)

            def delete_selected():
                ids = self._selected_queue_ids(notif_tree)
                if not ids:
                    messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.notifications.dialogs.please_select_notifications_to_delete', default="Please select notifications to delete"),
                                           parent=dialog)
                    return

                response = messagebox.askyesno(_t('gui.shell.document_manager.notifications.dialogs.confirm_delete', default="Confirm Delete"),
                                             f"Cancel {len(ids)} selected notifications? They will not be sent.",
                                             parent=dialog)
                if response:
                    try:
                        cancelled, refused = queue_cancel(self.gui, ids)
                        messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.success', default="Success"),
                                            f"Cancelled: {cancelled}" + _refused_text(refused), parent=dialog)
                        load_notifications()

                    except Exception as e:
                        messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to delete notifications: {e}",
                                             parent=dialog)

            ttk.Button(action_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_selected', default="Send Selected"), command=send_selected).pack(side='left', padx=5)
            ttk.Button(action_frame, text=_t('gui.shell.document_manager.notifications.buttons.delete_selected', default="Delete Selected"), command=delete_selected).pack(side='left', padx=5)
            ttk.Button(action_frame, text=_t('gui.shell.document_manager.notifications.buttons.refresh', default="Refresh"), command=load_notifications).pack(side='left', padx=5)
            ttk.Button(action_frame, text=_t('gui.shell.document_manager.notifications.buttons.close', default="Close"), command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to open pending notifications: {e}")

    def bulk_notification_send(self):
        """Send notifications to multiple students"""
        try:
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.shell.document_manager.notifications.windows.bulk_notification_send', default="Bulk Notification Send"))
            dialog.geometry("850x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.send_bulk_notifications', default="Send Bulk Notifications"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Recipient selection
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.select_recipients_variant_2', default="Select Recipients:"), font=('Arial', 10, 'bold')).pack(anchor='w')

            recipient_frame = ttk.Frame(main_frame)
            recipient_frame.pack(fill='x', pady=10)

            recipient_var = tk.StringVar(value=_t('gui.shell.document_manager.notifications.values.all_students', default="all_students"))
            ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.all_students', default="All Students"), variable=recipient_var,
                           value="all_students").pack(anchor='w')
            ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.students_with_expiring_documents', default="Students with Expiring Documents"),
                           variable=recipient_var, value="expiring_docs").pack(anchor='w')
            ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.students_with_missing_documents', default="Students with Missing Documents"),
                           variable=recipient_var, value="missing_docs").pack(anchor='w')

            # Notification type
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.notification_type', default="Notification Type:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            notification_type = ttk.Combobox(main_frame, values=['Email', 'SMS', 'In-App'], state='readonly', width=30)
            notification_type.set('Email')
            notification_type.pack(anchor='w')

            # Subject
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.subject', default="Subject:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            subject_entry = tk.Entry(main_frame, width=50)
            subject_entry.pack(fill='x')

            # Message
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.notifications.labels.message', default="Message:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            message_text = tk.Text(main_frame, height=8, width=50)
            message_text.pack(fill='both', expand=True)

            def send_notifications():
                subject = subject_entry.get().strip()
                message = message_text.get("1.0", tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.notifications.dialogs.please_enter_both_subject_and_message', default="Please enter both subject and message"))
                    return

                channel = notification_type.get()
                try:
                    recipients = resolve_student_recipients(recipient_var.get())
                    if not recipients:
                        messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.no_recipients', default="No Recipients"),
                                            _t('gui.shell.document_manager.notifications.dialogs.no_students_match', default="No students match the selected recipients."),
                                            parent=dialog)
                        return
                    if not messagebox.askyesno(_t('gui.shell.document_manager.notifications.dialogs.confirm_send', default="Confirm Send"),
                                               f"Send '{subject}' by {channel} to {len(recipients)} student(s)?",
                                               parent=dialog):
                        return
                    use_email, use_sms, use_inbox = channel == 'Email', channel == 'SMS', channel == 'In-App'
                    stats = deliver_to_students(recipients, subject, message, email=use_email,
                                                inbox=use_inbox, sms=use_sms,
                                                sender_id=_sender_id(self.gui))
                    summary = delivery_summary(stats, len(recipients), email=use_email,
                                               inbox=use_inbox, sms=use_sms)
                    self.gui.log_event('send', 'bulk_notification',
                                       details={'recipients': recipient_var.get(), 'channel': channel,
                                                'count': len(recipients), 'stats': stats})
                    messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.bulk_send_result', default="Bulk Send Result"),
                                        summary, parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"),
                                         f"Failed to send notifications: {e}", parent=dialog)

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_notifications', default="Send Notifications"), command=send_notifications).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"), f"Failed to open notification dialog: {e}")

    def bulk_notification_campaign(self):
        """Send bulk notifications to students"""
        if not self.gui.ensure_login():
            return

        # Create campaign window
        campaign_window = tk.Toplevel(self.root)
        campaign_window.title(_t('gui.shell.document_manager.notifications.windows.bulk_notification_campaign', default="Bulk Notification Campaign"))
        campaign_window.geometry("900x700")
        campaign_window.transient(self.root)
        campaign_window.grab_set()

        # Title
        ttk.Label(campaign_window, text=_t('gui.shell.document_manager.notifications.labels.bulk_notification_campaign', default="Bulk Notification Campaign"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Recipient selection frame
        recipient_frame = ttk.LabelFrame(campaign_window, text=_t('gui.shell.document_manager.notifications.labels.select_recipients', default="Select Recipients"), padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=5)

        recipient_option = tk.StringVar(value=_t('gui.shell.document_manager.notifications.values.all_students', default="all_students"))

        ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.all_students', default="All Students"),
                       variable=recipient_option, value="all_students").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.students_with_pending_documents', default="Students with Pending Documents"),
                       variable=recipient_option, value="pending_docs").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.students_with_expiring_documents', default="Students with Expiring Documents"),
                       variable=recipient_option, value="expiring_docs").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.students_with_rejected_documents', default="Students with Rejected Documents"),
                       variable=recipient_option, value="rejected_docs").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text=_t('gui.shell.document_manager.notifications.buttons.custom_student_list_comma_separated_ids', default="Custom Student List (comma-separated IDs)"),
                       variable=recipient_option, value="custom").pack(anchor='w')

        custom_ids_entry = ttk.Entry(recipient_frame, width=70)
        custom_ids_entry.pack(fill='x', padx=20, pady=5)

        # Message frame
        message_frame = ttk.LabelFrame(campaign_window, text=_t('gui.shell.document_manager.notifications.labels.notification_message', default="Notification Message"), padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=5)

        ttk.Label(message_frame, text=_t('gui.shell.document_manager.notifications.labels.subject', default="Subject:")).pack(anchor='w')
        subject_entry = ttk.Entry(message_frame, width=80)
        subject_entry.insert(0, "Important Update Regarding Your Documents")
        subject_entry.pack(fill='x', pady=5)

        ttk.Label(message_frame, text=_t('gui.shell.document_manager.notifications.labels.message_body', default="Message Body:")).pack(anchor='w')
        message_text = tk.Text(message_frame, width=80, height=15)
        message_text.insert('1.0', """Dear Student,

This is a notification regarding your documents in our system.

Available placeholders:
{{student_name}} - Student's full name
{{student_id}} - Student ID number
{{pending_count}} - Number of pending documents
{{document_list}} - List of affected documents

Please log in to the portal to view your document status.

Best regards,
Administration""")
        message_text.pack(fill='both', expand=True, pady=5)

        # Options frame
        options_frame = ttk.LabelFrame(campaign_window, text=_t('gui.shell.document_manager.notifications.labels.notification_options', default="Notification Options"), padding=10)
        options_frame.pack(fill='x', padx=10, pady=5)

        send_email_var = tk.BooleanVar(value=True)
        send_sms_var = tk.BooleanVar(value=False)
        create_portal_alert_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_via_email', default="Send via Email"),
                       variable=send_email_var).pack(anchor='w')
        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_via_sms', default="Send via SMS"),
                       variable=send_sms_var).pack(anchor='w')
        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.notifications.buttons.create_portal_alert', default="Create Portal Alert"),
                       variable=create_portal_alert_var).pack(anchor='w')

        # Button frame
        button_frame = ttk.Frame(campaign_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        def campaign_recipients():
            custom = custom_ids_entry.get().split(',') if recipient_option.get() == "custom" else None
            return resolve_student_recipients(recipient_option.get(), custom)

        def preview_campaign():
            """Preview campaign details against the real recipient list"""
            try:
                recipients = campaign_recipients()
            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.error', default="Error"),
                                     f"Could not load recipients: {e}", parent=campaign_window)
                return
            body = message_text.get('1.0', 'end-1c')
            with_email = sum(1 for r in recipients if r['email'])
            preview_text = (f"Recipients: {len(recipients)} student(s) "
                            f"({with_email} with an e-mail address)\n"
                            f"Delivery: e-mail {'yes' if send_email_var.get() else 'no'}, "
                            f"SMS {'yes' if send_sms_var.get() else 'no'}, "
                            f"portal alert {'yes' if create_portal_alert_var.get() else 'no'}\n\n")
            if recipients:
                first = recipients[0]
                preview_text += (f"As sent to {first['name']} ({first['student_id']}):\n\n"
                                 f"Subject: {render_for_student(subject_entry.get(), first)}\n\n"
                                 f"{render_for_student(body, first)}")
            else:
                preview_text += "No students match this selection - nothing would be sent."

            preview = tk.Toplevel(campaign_window)
            preview.title(_t('gui.shell.document_manager.notifications.dialogs.campaign_preview', default="Campaign Preview"))
            preview.geometry("640x520")
            preview.transient(campaign_window)
            text = tk.Text(preview, wrap='word')
            text.insert('1.0', preview_text)
            text.config(state='disabled')
            text.pack(fill='both', expand=True, padx=10, pady=10)
            ttk.Button(preview, text=_t('gui.shell.document_manager.notifications.buttons.close', default="Close"),
                       command=preview.destroy).pack(pady=(0, 10))

        def send_campaign():
            """Send the notification campaign"""
            use_email = send_email_var.get()
            use_sms = send_sms_var.get()
            use_inbox = create_portal_alert_var.get()
            if not (use_email or use_sms or use_inbox):
                messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.warning', default="Warning"),
                                       _t('gui.shell.document_manager.notifications.dialogs.choose_a_delivery_method', default="Choose at least one delivery method."),
                                       parent=campaign_window)
                return
            subject = subject_entry.get().strip()
            body = message_text.get('1.0', 'end-1c').strip()
            if not subject or not body:
                messagebox.showwarning(_t('gui.shell.document_manager.notifications.dialogs.warning', default="Warning"),
                                       _t('gui.shell.document_manager.notifications.dialogs.please_enter_both_subject_and_message', default="Please enter both subject and message"),
                                       parent=campaign_window)
                return
            try:
                recipients = campaign_recipients()
            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.send_error', default="Send Error"),
                                     f"Could not load recipients: {e}", parent=campaign_window)
                return
            if not recipients:
                messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.no_recipients', default="No Recipients"),
                                    _t('gui.shell.document_manager.notifications.dialogs.no_students_match', default="No students match the selected recipients."),
                                    parent=campaign_window)
                return
            if not messagebox.askyesno(_t('gui.shell.document_manager.notifications.dialogs.confirm_send', default="Confirm Send"),
                                      f"Send this notification campaign to {len(recipients)} student(s)?",
                                      parent=campaign_window):
                return

            try:
                option = recipient_option.get()
                stats = deliver_to_students(recipients, subject, body, email=use_email,
                                            inbox=use_inbox, sms=use_sms,
                                            sender_id=_sender_id(self.gui))
                summary = delivery_summary(stats, len(recipients), email=use_email,
                                           inbox=use_inbox, sms=use_sms)

                # Log activity
                self.gui.log_event('send', 'bulk_notification_campaign',
                              details={'recipients': option, 'count': len(recipients),
                                       'subject': subject, 'stats': stats})

                messagebox.showinfo(_t('gui.shell.document_manager.notifications.dialogs.campaign_sent', default="Campaign Sent"),
                                    f"Subject: {subject}\n\n{summary}", parent=campaign_window)
                campaign_window.destroy()

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.notifications.dialogs.send_error', default="Send Error"),
                                     f"Failed to send campaign: {e}", parent=campaign_window)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.preview_campaign', default="Preview Campaign"),
                  command=preview_campaign).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.send_campaign', default="Send Campaign"),
                  command=send_campaign).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.notifications.buttons.cancel', default="Cancel"),
                  command=campaign_window.destroy).pack(side='right', padx=5)

    def bulk_email_notifications(self):
        """Send bulk email notifications"""
        # This is handled by bulk_notification_campaign()
        self.bulk_notification_campaign()
