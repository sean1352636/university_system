"""Club payment management tab mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.shared.utils.i18n import get_text as _

try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    get_db_connection = None


class ClubPaymentsMixin:
    """Club payment management launcher tab."""

    def create_club_payments_tab(self):
        """Create club payment management tab with launch button"""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['club_payments'] = frame

        # Add title
        title_label = tk.Label(
            frame,
            text=_("finance_gui.club_payments_tab.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            frame,
            text=_("finance_gui.club_payments_tab.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        launch_btn = tk.Button(
            frame,
            text=_("finance_gui.club_payments_tab.open_club_payments"),
            command=self._launch_club_payments,
            font=('Arial', 12, 'bold'),
            bg=self.colors['success'],
            fg='white',
            padx=30,
            pady=15
        )
        launch_btn.pack(pady=10)

    def _launch_club_payments(self):
        """Launch the Club Payment Management GUI in a new window"""
        try:
            payment_window = tk.Toplevel(self.root)
            payment_window.title(_("finance_gui.club_payments_tab.window_title"))
            payment_window.geometry("1200x800")
            try:
                payment_window.transient(self.root)
            except Exception:
                pass

            # Create main frame
            main_frame = ttk.Frame(payment_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            title_label = ttk.Label(
                main_frame,
                text=_("finance_gui.club_payments_tab.header"),
                font=('Arial', 16, 'bold')
            )
            title_label.pack(pady=10)

            # Create notebook for different sections
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            # Payment Overview Tab
            overview_frame = ttk.Frame(notebook, padding="10")
            notebook.add(overview_frame, text=_("finance_gui.club_payments_tab.tabs.overview"))
            self._create_club_payment_overview(overview_frame)

            # Record Payment Tab
            record_frame = ttk.Frame(notebook, padding="10")
            notebook.add(record_frame, text=_("finance_gui.club_payments_tab.tabs.record"))
            self._create_club_record_payment(record_frame)

            # Payment History Tab
            history_frame = ttk.Frame(notebook, padding="10")
            notebook.add(history_frame, text=_("finance_gui.club_payments_tab.tabs.history"))
            self._create_club_payment_history(history_frame)

            print("Club Payment Management opened successfully from Finance GUI")

        except Exception as e:
            messagebox.showerror(
                _("common.error"),
                _("finance_gui.club_payments_tab.failed_to_open", error=str(e))
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
        """Create sub-tab for recording new club payments"""
        ttk.Label(parent, text=_("finance_gui.club_payments_tab.record_description"),
                 font=('Arial', 12)).pack(pady=20)
        ttk.Label(parent, text=_("finance_gui.club_payments_tab.integration_note"),
                 font=('Arial', 10), foreground='gray').pack()

    def _create_club_payment_history(self, parent):
        """Create sub-tab for viewing club payment history"""
        try:
            if not DB_AVAILABLE or not get_db_connection:
                ttk.Label(parent, text=_("finance_gui.club_payments_tab.db_unavailable")).pack(pady=20)
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            columns = ('Date', 'Club', 'Amount', 'Type', 'Status')
            tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            tree.pack(fill=tk.BOTH, expand=True, pady=10)

            # Try to load payment data
            try:
                cursor.execute('''
                    SELECT payment_date, reference_id, amount, payment_type, status
                    FROM payments
                    WHERE source_type = 'club'
                    ORDER BY payment_date DESC
                    LIMIT 100
                ''')
                for row in cursor.fetchall():
                    tree.insert('', 'end', values=row)
            except Exception:
                pass

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=_("finance_gui.club_payments_tab.error_loading_history", error=str(e))).pack()
