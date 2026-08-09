"""Club payment management tab mixin for LayoutManager."""

from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _

try:
    from education_system.systems.university.infrastructure.database.db import get_db_connection
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    get_db_connection = None


# Enumerations that match what already lives in the `payments` table.
_PAYMENT_TYPES = (
    "membership_fee",
    "event_fee",
    "sponsorship",
    "fundraising",
    "equipment",
    "travel",
    "other",
)
_PAYMENT_METHODS = (
    "cash",
    "card",
    "bank_transfer",
    "cheque",
    "online",
    "other",
)


class ClubPaymentsMixin:
    """Club payment management launcher tab."""

    def create_club_payments_tab(self):
        """Create club payments tab; build the notebook lazily on first show."""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['club_payments'] = frame
        self._club_payments_built = False

        frame.bind('<Map>', self._on_club_payments_tab_shown, add='+')

    def _on_club_payments_tab_shown(self, _event):
        if getattr(self, '_club_payments_built', False):
            return
        frame = self.tab_frames.get('club_payments')
        if frame is None:
            return
        try:
            main_frame = ttk.Frame(frame, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(
                main_frame,
                text=_("finance_gui.club_payments_tab.header"),
                font=('Arial', 16, 'bold'),
            ).pack(pady=10)

            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            overview_frame = ttk.Frame(notebook, padding="10")
            notebook.add(overview_frame, text=_("finance_gui.club_payments_tab.tabs.overview"))
            self._create_club_payment_overview(overview_frame)

            record_frame = ttk.Frame(notebook, padding="10")
            notebook.add(record_frame, text=_("finance_gui.club_payments_tab.tabs.record"))
            self._create_club_record_payment(record_frame)

            history_frame = ttk.Frame(notebook, padding="10")
            notebook.add(history_frame, text=_("finance_gui.club_payments_tab.tabs.history"))
            self._create_club_payment_history(history_frame)

            self._club_payments_built = True
        except Exception as e:
            messagebox.showerror(
                _("common.error"),
                _("finance_gui.club_payments_tab.failed_to_open", error=str(e)),
            )
            print(f"Club Payment Management error: {e}")

    def _create_club_payment_overview(self, parent):
        """Create payment overview sub-tab for club payments"""
        try:
            if not DB_AVAILABLE or not get_db_connection:
                ttk.Label(parent, text=_("finance_gui.club_payments_tab.db_unavailable")).pack(pady=20)
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total_payments,
                    SUM(amount) as total_amount,
                    COUNT(DISTINCT reference_id) as clubs_with_payments
                FROM payments
                WHERE source_type = 'club'
                  AND payment_date >= date('now', '-30 days')
            ''')
            stats = cursor.fetchone()

            stats_frame = ttk.LabelFrame(parent, text=_("finance_gui.club_payments_tab.stats_section"), padding="10")
            stats_frame.pack(fill=tk.X, pady=10)

            if stats:
                ttk.Label(stats_frame,
                         text=_("finance_gui.club_payments_tab.total_payments", count=stats[0] or 0),
                         font=('Arial', 12)).pack(anchor='w', pady=5)
                ttk.Label(stats_frame,
                         text=_("finance_gui.club_payments_tab.total_amount", amount=f"{stats[1] or 0:.2f}"),
                         font=('Arial', 12)).pack(anchor='w', pady=5)
                ttk.Label(stats_frame,
                         text=_("finance_gui.club_payments_tab.clubs_with_payments", count=stats[2] or 0),
                         font=('Arial', 12)).pack(anchor='w', pady=5)

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=_("finance_gui.club_payments_tab.error_loading_stats", error=str(e))).pack()

    def _create_club_record_payment(self, parent):
        """Record a new club payment — form that writes to the `payments` table."""
        if not DB_AVAILABLE or not get_db_connection:
            ttk.Label(parent, text=_("finance_gui.club_payments_tab.db_unavailable")).pack(pady=20)
            return

        # Pull club list (id + name) for the picker.
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    "SELECT club_id, club_name FROM student_clubs "
                    "WHERE COALESCE(status,'active') != 'archived' ORDER BY club_name"
                ).fetchall()
            clubs = [(r[0], r[1]) for r in rows]
        except Exception as e:
            ttk.Label(parent, text=_("finance_gui.club_payments_tab.error_loading_history", error=str(e))).pack(pady=10)
            return

        form = ttk.LabelFrame(parent, text=_("finance_gui.club_payments_tab.record_form_title"), padding=15)
        form.pack(fill=tk.X, padx=20, pady=20)
        for col in (1,):
            form.columnconfigure(col, weight=1)

        # --- Club picker ---
        ttk.Label(form, text=_("finance_gui.club_payments_tab.field_club")).grid(row=0, column=0, sticky='w', pady=5)
        club_labels = [f"{name} (#{cid})" for cid, name in clubs] or ["(no clubs found)"]
        club_var = tk.StringVar(value=club_labels[0])
        club_combo = ttk.Combobox(form, textvariable=club_var, values=club_labels, state='readonly')
        club_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

        # --- Amount ---
        ttk.Label(form, text=_("finance_gui.club_payments_tab.field_amount")).grid(row=1, column=0, sticky='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form, textvariable=amount_var).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        # --- Payment type ---
        ttk.Label(form, text=_("finance_gui.club_payments_tab.field_payment_type")).grid(row=2, column=0, sticky='w', pady=5)
        type_var = tk.StringVar(value=_PAYMENT_TYPES[0])
        ttk.Combobox(form, textvariable=type_var, values=list(_PAYMENT_TYPES), state='readonly').grid(
            row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        # --- Method ---
        ttk.Label(form, text=_("finance_gui.club_payments_tab.field_method")).grid(row=3, column=0, sticky='w', pady=5)
        method_var = tk.StringVar(value=_PAYMENT_METHODS[0])
        ttk.Combobox(form, textvariable=method_var, values=list(_PAYMENT_METHODS), state='readonly').grid(
            row=3, column=1, sticky='ew', pady=5, padx=(10, 0))

        # --- Date (YYYY-MM-DD) ---
        ttk.Label(form, text=_("finance_gui.club_payments_tab.field_date")).grid(row=4, column=0, sticky='w', pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form, textvariable=date_var).grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))

        # --- Notes ---
        ttk.Label(form, text=_("finance_gui.club_payments_tab.field_notes")).grid(row=5, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(form, height=3, width=40, wrap='word')
        notes_text.grid(row=5, column=1, sticky='ew', pady=5, padx=(10, 0))

        status_var = tk.StringVar(value="")
        status_label = ttk.Label(form, textvariable=status_var, foreground='#666')
        status_label.grid(row=7, column=0, columnspan=2, sticky='w', pady=(5, 0))

        def _save():
            if not clubs:
                status_var.set(_("finance_gui.club_payments_tab.no_clubs"))
                return
            # Parse + validate
            try:
                amount = float(amount_var.get().strip())
                if amount <= 0:
                    raise ValueError("amount must be positive")
            except Exception:
                status_var.set(_("finance_gui.club_payments_tab.invalid_amount"))
                return

            date_str = date_var.get().strip()
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except Exception:
                status_var.set(_("finance_gui.club_payments_tab.invalid_date"))
                return

            # Map the label the user chose back to (club_id, club_name).
            idx = club_labels.index(club_var.get()) if club_var.get() in club_labels else 0
            club_id, club_name = clubs[idx]

            processed_by = None
            auth = getattr(self, 'auth', None)
            if auth and getattr(auth, 'current_user', None):
                processed_by = auth.current_user.get('username') or auth.current_user.get('id')

            payment_row_id = None
            try:
                with get_db_connection() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO payments (
                            amount, currency, payment_method, payment_date, status, notes,
                            source_type, payment_type, reference_type, reference_id, processed_by,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            amount, 'GBP', method_var.get(), date_str, 'completed',
                            notes_text.get('1.0', 'end').strip() or None,
                            'club', type_var.get(), 'club', str(club_id),
                            processed_by,
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        ),
                    )
                    payment_row_id = cur.lastrowid
                    conn.commit()
            except Exception as exc:
                status_var.set(_("finance_gui.club_payments_tab.save_failed", error=str(exc)))
                return

            # Auto-post to GL (never raises)
            if payment_row_id is not None:
                try:
                    from education_system.systems.university.domain.finance.ledger import notify_ledger
                    notify_ledger('payment', payment_row_id, posted_by=processed_by or 'club_payments')
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            status_var.set(_(
                "finance_gui.club_payments_tab.save_success",
                amount=f"{amount:.2f}", club=club_name,
            ))
            amount_var.set("")
            notes_text.delete('1.0', 'end')

        button_row = ttk.Frame(form)
        button_row.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(button_row, text=_("finance_gui.club_payments_tab.save_button"), command=_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_row, text=_("finance_gui.club_payments_tab.clear_button"),
            command=lambda: (amount_var.set(""), notes_text.delete('1.0', 'end'),
                             date_var.set(datetime.now().strftime('%Y-%m-%d')),
                             status_var.set("")),
        ).pack(side=tk.LEFT, padx=5)

    def _create_club_payment_history(self, parent):
        """Show recent club payments in a readable table."""
        if not DB_AVAILABLE or not get_db_connection:
            ttk.Label(parent, text=_("finance_gui.club_payments_tab.db_unavailable")).pack(pady=20)
            return

        # Toolbar with a refresh button sits above the tree.
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        columns = ('date', 'club', 'amount', 'type', 'method', 'status')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=18)
        headings = {
            'date':   _("finance_gui.club_payments_tab.history_col_date"),
            'club':   _("finance_gui.club_payments_tab.history_col_club"),
            'amount': _("finance_gui.club_payments_tab.history_col_amount"),
            'type':   _("finance_gui.club_payments_tab.history_col_type"),
            'method': _("finance_gui.club_payments_tab.history_col_method"),
            'status': _("finance_gui.club_payments_tab.history_col_status"),
        }
        widths = {'date': 130, 'club': 260, 'amount': 110, 'type': 140, 'method': 120, 'status': 110}
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=widths[col], anchor='center' if col in ('amount', 'status') else 'w')

        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        count_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=count_var, foreground='#666').pack(side=tk.LEFT, padx=10)

        def _load():
            # Remove any prior rows so refresh shows a clean slate.
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                with get_db_connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT
                            p.payment_date,
                            COALESCE(c.club_name, 'Club #' || p.reference_id) AS club,
                            p.amount,
                            p.currency,
                            p.payment_type,
                            p.payment_method,
                            p.status
                        FROM payments p
                        LEFT JOIN student_clubs c ON CAST(p.reference_id AS INTEGER) = c.club_id
                        WHERE p.source_type = 'club'
                        ORDER BY p.payment_date DESC
                        LIMIT 200
                        """
                    ).fetchall()
            except Exception as exc:
                ttk.Label(parent, text=_("finance_gui.club_payments_tab.error_loading_history", error=str(exc))).pack(pady=10)
                return

            for r in rows:
                date_s = (r[0] or '').split('T')[0] if isinstance(r[0], str) else str(r[0] or '')
                amt = f"{(r[2] or 0):.2f} {r[3] or 'GBP'}"
                # Pass an explicit tuple of strings so Treeview doesn't call str()
                # on the sqlite3.Row object and render "<sqlite3.Row ...>".
                tree.insert('', 'end', values=(
                    date_s,
                    r[1] or '',
                    amt,
                    r[4] or '',
                    r[5] or '',
                    r[6] or '',
                ))
            count_var.set(_(
                "finance_gui.club_payments_tab.history_count",
                count=len(rows),
            ))

        ttk.Button(toolbar, text=_("finance_gui.club_payments_tab.refresh_button"),
                   command=_load).pack(side=tk.LEFT)
        _load()
