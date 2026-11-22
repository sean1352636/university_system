
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.domains.learners.interfaces.gui.alumni._service_imports import (
    init_alumni_db,
    view_events,
    create_enhanced_event,
    event_check_in_system,
    manage_business_directory,
    manage_alumni_forum,
    post_job_opportunity,
    view_job_board,
    schedule_career_counseling,
    view_engagement_leaderboard,
    view_my_badges,
    manage_photo_gallery,
    manage_class_reunions,
    generate_alumni_report,
    set_auth,
    setup_alumni_permissions,
    generate_engagement_recommendations,
    get_connection,
)



class DirectoryMixin:
        """Networking connections between alumni. Only alumni listed in the
        directory and open to networking can be found (the directory itself
        is ``AlumniOfficeRecordsMixin.show_directory``)."""

        def _ensure_connections_schema(self, conn=None):
            """``alumni_connections`` is created by migration e6a8c0d2f4b7
            (alumni_office_schema); make sure it exists on this database."""
            from education_system.systems.university.infrastructure.database.schemas import (
                alumni_office_schema,
            )
            own = conn is None
            if own:
                conn = db_get_connection()
            try:
                alumni_office_schema.apply_to_connection(conn)
            finally:
                if own:
                    conn.close()

        def _current_alumni_id(self):
            """The signed-in alumnus's alumni id (None for anyone else)."""
            who = getattr(self, "who", None)
            return who.alumni_id if who is not None else None

        def _respond_to_request(self, response):
            """Accept/decline the selected incoming connection request."""
            if not hasattr(self, 'incoming_requests_tree'):
                return

            selection = self.incoming_requests_tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.learners.alumni.directory.dialogs.no_selection', default="No Selection"), _t('gui.learners.alumni.directory.dialogs.please_select_a_request', default="Please select a request."))
                return

            connection_id = selection[0]  # tree iid is the connection_id
            me = self._current_alumni_id()
            try:
                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    conn.execute(
                        """
                        UPDATE alumni_connections
                        SET status = ?, response_date = datetime('now')
                        WHERE connection_id = ? AND recipient_id = ? AND status = 'pending'
                        """,
                        (response, connection_id, me))
                    conn.commit()

                messagebox.showinfo(_t('gui.learners.alumni.directory.dialogs.success', default="Success"), f"Request {response}!")
                self.view_connection_requests()  # Refresh

                try:
                    from education_system.systems.university.infrastructure.activity_logger import log_activity
                    log_activity('update', 'connection_request',
                                 details={'connection_id': connection_id, 'action': response})
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.directory.dialogs.database_error', default="Database Error"), f"Failed to respond: {str(e)}")

        def _search_alumni_for_connection(self):
            """Search alumni for connection requests"""
            try:
                # Clear existing results
                for item in self.connection_alumni_tree.get_children():
                    self.connection_alumni_tree.delete(item)

                search_term = self.connection_search.get().strip()
                if not search_term:
                    messagebox.showwarning(_t('gui.learners.alumni.directory.dialogs.search_required', default="Search Required"), _t('gui.learners.alumni.directory.dialogs.please_enter_a_search_term', default="Please enter a search term."))
                    return

                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    cursor = conn.cursor()
                    me = self._current_alumni_id()

                    query = """
                        SELECT a.alumni_id, a.first_name || ' ' || a.last_name,
                               a.graduation_year, a.industry,
                               COALESCE(a.city || ', ' || a.country, a.city, a.country, '') AS location,
                               CASE
                                   WHEN EXISTS (
                                       SELECT 1 FROM alumni_connections
                                       WHERE (requester_id = ? AND recipient_id = a.alumni_id)
                                       OR (requester_id = a.alumni_id AND recipient_id = ?)
                                   ) THEN 'Connected/Pending'
                                   ELSE 'Not Connected'
                               END as status
                        FROM alumni a
                        JOIN alumni_directory_settings d ON d.alumni_id = a.alumni_id
                        WHERE (a.first_name LIKE ? OR a.last_name LIKE ?)
                        AND a.alumni_id != ?
                        AND d.searchable = 1 AND d.networking_available = 1
                        AND a.deceased_at IS NULL AND a.anonymised_at IS NULL
                        ORDER BY a.last_name
                    """
                    cursor.execute(query, (me, me, f"%{escape_like(search_term)}%",
                                           f"%{escape_like(search_term)}%", me))
                    results = cursor.fetchall()

                    for alumni in results:
                        # iid carries the alumni_id; display the rest.
                        self.connection_alumni_tree.insert('', tk.END, iid=str(alumni[0]),
                                                           values=alumni[1:])

                    self.update_status(f"Found {len(results)} alumni")

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.directory.dialogs.database_error', default="Database Error"), f"Search failed: {str(e)}")

        def _send_selected_connection_request(self):
            """Send connection request to selected alumni"""
            if not hasattr(self, 'connection_alumni_tree'):
                return

            selection = self.connection_alumni_tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.learners.alumni.directory.dialogs.no_selection', default="No Selection"), _t('gui.learners.alumni.directory.dialogs.please_select_an_alumni_to_connect_with', default="Please select an alumni to connect with."))
                return

            item = self.connection_alumni_tree.item(selection[0])
            alumni_data = item['values']

            # Check if already connected
            if alumni_data[4] == 'Connected/Pending':
                messagebox.showinfo(_t('gui.learners.alumni.directory.dialogs.already_connected', default="Already Connected"),
                                  _t('gui.learners.alumni.directory.dialogs.you_already_have_a_connection_or_pending_request_with_this_alumn', default="You already have a connection or pending request with this alumni."))
                return

            # Create message dialog
            msg_window = tk.Toplevel(self.root)
            msg_window.title(_t('gui.learners.alumni.directory.windows.connection_request_message', default="Connection Request Message"))
            msg_window.geometry("500x300")
            msg_window.configure(bg='white')
            msg_window.grab_set()

            frame = ttk.Frame(msg_window, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=f"Send connection request to {alumni_data[0]}",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            ttk.Label(frame, text=_t('gui.learners.alumni.directory.labels.message_optional', default="Message (optional):")).pack(anchor='w')
            message_text = ScrolledText(frame, height=6, wrap=tk.WORD)
            message_text.pack(fill=tk.BOTH, expand=True, pady=(5, 20))

            recipient_id = selection[0]  # tree iid is the alumni_id

            def send_request():
                try:
                    with db_get_connection() as conn:
                        self._ensure_connections_schema(conn)
                        me = self._current_alumni_id()
                        conn.execute("""
                            INSERT INTO alumni_connections (
                                requester_id, recipient_id, status, message, request_date
                            ) VALUES (?, ?, 'pending', ?, datetime('now'))
                        """, (me, recipient_id, message_text.get(1.0, tk.END).strip()))
                        conn.commit()

                    messagebox.showinfo(_t('gui.learners.alumni.directory.dialogs.success', default="Success"), _t('gui.learners.alumni.directory.dialogs.connection_request_sent', default="Connection request sent!"))
                    msg_window.destroy()
                    self._search_alumni_for_connection()  # Refresh

                    try:
                        from education_system.systems.university.infrastructure.activity_logger import log_activity
                        log_activity('create', 'connection_request',
                                     details={'recipient': alumni_data[0]})
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)

                except sqlite3.Error as e:
                    messagebox.showerror(_t('gui.learners.alumni.directory.dialogs.database_error', default="Database Error"), f"Failed to send request: {str(e)}")

            ttk.Button(frame, text=_t('gui.learners.alumni.directory.buttons.send_request', default="Send Request"),
                      command=send_request).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(frame, text=_t('gui.learners.alumni.directory.buttons.cancel', default="Cancel"),
                      command=msg_window.destroy).pack(side=tk.LEFT)

        def send_connection_request(self):
            """Send connection request to another alumni"""
            self.clear_content()
            self.update_status("Send Connection Request")

            ttk.Label(self.content_frame, text=_t('gui.learners.alumni.directory.labels.send_connection_request', default="Send Connection Request"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Alumni search
            search_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.directory.labels.find_alumni', default="Find Alumni"), padding=10)
            search_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(search_frame, text=_t('gui.learners.alumni.directory.labels.search_by_name', default="Search by name:")).pack(side=tk.LEFT, padx=(0, 10))
            self.connection_search = tk.StringVar()
            ttk.Entry(search_frame, textvariable=self.connection_search, width=30).pack(side=tk.LEFT, padx=(0, 20))

            ttk.Button(search_frame, text=_t('gui.learners.alumni.directory.buttons.search', default="Search"),
                      command=self._search_alumni_for_connection).pack(side=tk.LEFT)

            # Search results
            results_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.directory.labels.alumni', default="Alumni"), padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            columns = ('Name', 'Graduation Year', 'Industry', 'Location', 'Status')
            self.connection_alumni_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

            for col in columns:
                self.connection_alumni_tree.heading(col, text=col)
                self.connection_alumni_tree.column(col, width=130)

            scrollbar_y = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                        command=self.connection_alumni_tree.yview)
            self.connection_alumni_tree.configure(yscrollcommand=scrollbar_y.set)

            self.connection_alumni_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Action buttons
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20)

            ttk.Button(button_frame, text=_t('gui.learners.alumni.directory.buttons.send_connection_request', default="Send Connection Request"),
                      command=self._send_selected_connection_request).pack(side=tk.LEFT)

        def show_connections(self):
            """Networking connections — uses the functional, DB-backed view."""
            self.view_connection_requests()

        def view_connection_requests(self):
            """View pending connection requests"""
            self.clear_content()
            self.update_status("Connection Requests")

            ttk.Label(self.content_frame, text=_t('gui.learners.alumni.directory.labels.connection_requests', default="Connection Requests"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 10))

            # Toolbar
            toolbar = ttk.Frame(self.content_frame)
            toolbar.pack(fill=tk.X, padx=20, pady=(0, 10))
            ttk.Button(toolbar, text=_t('gui.learners.alumni.directory.buttons.find_alumni_to_connect', default="➕ Find Alumni to Connect"),
                       command=self.send_connection_request).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(toolbar, text=_t('gui.learners.alumni.directory.buttons.refresh', default="🔄 Refresh"),
                       command=self.view_connection_requests).pack(side=tk.LEFT)

            # Tabs
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Incoming requests tab
            incoming_frame = ttk.Frame(notebook)
            notebook.add(incoming_frame, text=_t('gui.learners.alumni.directory.tabs.incoming_requests', default="Incoming Requests"))

            incoming_table = ttk.Frame(incoming_frame)
            incoming_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('From', 'Industry', 'Message', 'Date')
            self.incoming_requests_tree = ttk.Treeview(incoming_table, columns=columns, show='headings')

            for col in columns:
                self.incoming_requests_tree.heading(col, text=col)
                self.incoming_requests_tree.column(col, width=150)

            scrollbar_y = ttk.Scrollbar(incoming_table, orient=tk.VERTICAL,
                                        command=self.incoming_requests_tree.yview)
            self.incoming_requests_tree.configure(yscrollcommand=scrollbar_y.set)

            self.incoming_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            # Load incoming requests
            try:
                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    cursor = conn.cursor()
                    me = self._current_alumni_id()

                    query = """
                        SELECT c.connection_id, a.first_name || ' ' || a.last_name,
                               a.industry, c.message, c.request_date
                        FROM alumni_connections c
                        JOIN alumni a ON c.requester_id = a.alumni_id
                        WHERE c.recipient_id = ? AND c.status = 'pending'
                        ORDER BY c.request_date DESC
                    """
                    cursor.execute(query, (me,))
                    requests = cursor.fetchall()

                    for req in requests:
                        self.incoming_requests_tree.insert('', tk.END, iid=str(req[0]),
                                                           values=req[1:])

                    self.update_status(f"{len(requests)} incoming request(s)")

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.learners.alumni.directory.dialogs.database_error', default="Database Error"), f"Failed to load requests: {str(e)}")

            # Action buttons for incoming
            incoming_buttons = ttk.Frame(incoming_frame)
            incoming_buttons.pack(fill=tk.X, padx=10, pady=(0, 10))

            ttk.Button(incoming_buttons, text=_t('gui.learners.alumni.directory.buttons.accept', default="Accept"),
                      command=lambda: self._respond_to_request('accepted')).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(incoming_buttons, text=_t('gui.learners.alumni.directory.buttons.decline', default="Decline"),
                      command=lambda: self._respond_to_request('declined')).pack(side=tk.LEFT)

            # Outgoing requests tab
            outgoing_frame = ttk.Frame(notebook)
            notebook.add(outgoing_frame, text=_t('gui.learners.alumni.directory.tabs.sent_requests', default="Sent Requests"))

            outgoing_table = ttk.Frame(outgoing_frame)
            outgoing_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns_out = ('To', 'Industry', 'Status', 'Date')
            self.outgoing_requests_tree = ttk.Treeview(outgoing_table, columns=columns_out, show='headings')

            for col in columns_out:
                self.outgoing_requests_tree.heading(col, text=col)
                self.outgoing_requests_tree.column(col, width=150)

            scrollbar_y2 = ttk.Scrollbar(outgoing_table, orient=tk.VERTICAL,
                                         command=self.outgoing_requests_tree.yview)
            self.outgoing_requests_tree.configure(yscrollcommand=scrollbar_y2.set)

            self.outgoing_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar_y2.pack(side=tk.RIGHT, fill=tk.Y)

            # Load outgoing requests
            try:
                with db_get_connection() as conn:
                    self._ensure_connections_schema(conn)
                    cursor = conn.cursor()
                    me = self._current_alumni_id()

                    query = """
                        SELECT a.first_name || ' ' || a.last_name, a.industry,
                               c.status, c.request_date
                        FROM alumni_connections c
                        JOIN alumni a ON c.recipient_id = a.alumni_id
                        WHERE c.requester_id = ?
                        ORDER BY c.request_date DESC
                    """
                    cursor.execute(query, (me,))
                    requests = cursor.fetchall()

                    for req in requests:
                        self.outgoing_requests_tree.insert('', tk.END, values=req)

            except sqlite3.Error:
                pass  # Silently handle database errors in background refresh

