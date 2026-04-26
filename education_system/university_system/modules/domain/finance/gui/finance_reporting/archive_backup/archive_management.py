from education_system.university_system.modules.domain.finance.gui.finance_reporting.archive_backup._imports import (
    tk, ttk, messagebox, scrolledtext, ScrolledText, datetime, timedelta, _,
)


def show_archive_management_dialog(self):
    """Show archive management dialog"""
    archive_window = tk.Toplevel(self.root)
    archive_window.title(_("finance_reporting.windows.archive_management"))
    archive_window.geometry("800x600")

    main_frame = ttk.Frame(archive_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Data Archive Management",
             style='Title.TLabel').pack(pady=(0, 20))

    # Archive statistics
    stats_frame = ttk.LabelFrame(main_frame, text="Archive Statistics", padding="10")
    stats_frame.pack(fill=tk.X, pady=(0, 10))

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Data age analysis
        cursor.execute('SELECT MIN(payment_date), MAX(payment_date), COUNT(*) FROM payments')
        payment_range = cursor.fetchone()

        if payment_range[0]:
            # payment_date may include a time component (e.g. "2025-11-21
            # 19:43:25") — slice to the date portion before parsing.
            oldest = datetime.strptime(payment_range[0][:10], '%Y-%m-%d')
            newest = datetime.strptime(payment_range[1][:10], '%Y-%m-%d')
            days_span = (newest - oldest).days

            ttk.Label(stats_frame, text=f"Payment Data Span: {days_span} days").pack(anchor=tk.W)
            ttk.Label(stats_frame, text=f"Oldest Payment: {payment_range[0]}").pack(anchor=tk.W)
            ttk.Label(stats_frame, text=f"Newest Payment: {payment_range[1]}").pack(anchor=tk.W)
            ttk.Label(stats_frame, text=f"Total Payments: {payment_range[2]:,}").pack(anchor=tk.W)

        # Archivable data
        archive_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date < ?', (archive_date,))
        archivable_payments = cursor.fetchone()[0]

        ttk.Label(stats_frame, text=f"Archivable Payments (>2 years): {archivable_payments:,}").pack(anchor=tk.W)

        conn.close()

    except Exception as e:
        ttk.Label(stats_frame, text=f"Error loading archive data: {e}",
                 foreground="red").pack(anchor=tk.W)

    # Archive operations
    operations_frame = ttk.LabelFrame(main_frame, text="Archive Operations", padding="10")
    operations_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    operations_text = ScrolledText(operations_frame, height=15, wrap=tk.WORD)
    operations_text.pack(fill=tk.BOTH, expand=True)

    operations_content = """Available Archive Operations:

    1. CREATE ARCHIVE TABLES
    • Set up separate tables for historical data
    • Maintain same structure as active tables
    • Implement archive indexing strategy

    2. DATA MIGRATION
    • Move records older than 2 years to archive
    • Maintain referential integrity
    • Create audit trail of archived records

    3. DATABASE OPTIMIZATION
    • Compact active tables after archiving
    • Update database statistics
    • Optimize query performance

    4. BACKUP CREATION
    • Full database backup before archiving
    • Incremental backups of archive data
    • Verify backup integrity

    5. ARCHIVE MAINTENANCE
    • Regular archive table optimization
    • Archive data validation checks
    • Archive access logging

    ARCHIVE POLICY:
    • Financial data retention: 7 years minimum
    • Student records: Permanent retention
    • Transaction logs: 5 years active, archive thereafter
    • Audit trails: Permanent retention

    STORAGE OPTIMIZATION:
    • Compressed archive storage
    • Offline backup for very old data
    • Cloud storage integration for archives

    COMPLIANCE REQUIREMENTS:
    • Maintain audit trail of all archiving operations
    • Ensure archived data remains accessible for audits
    • Implement secure archive access controls
    """

    operations_text.insert(1.0, operations_content)
    operations_text.configure(state='disabled')

    # Control buttons
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(fill=tk.X, pady=(10, 0))

    ttk.Button(buttons_frame, text="Create Archive Tables",
               command=lambda: self.create_archive_tables(archive_window)).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(buttons_frame, text="Run Archive Process",
               command=lambda: self.run_archive_process(archive_window)).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Create Backup",
               command=lambda: self.create_database_backup(archive_window)).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Close", command=archive_window.destroy).pack(side=tk.RIGHT)

def create_archive_tables(self, parent_window):
    """Create archive tables for historical data storage"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        # Confirm action
        if not messagebox.askyesno("Confirm",
            "This will create archive tables for historical financial data.\n\n"
            "Archive tables will be created for:\n"
            "• Transactions (older than 2 years)\n"
            "• Student payments (older than 2 years)\n"
            "• Financial aid records (older than 5 years)\n"
            "• Budget records (older than 3 years)\n\n"
            "Continue?", parent=parent_window):
            return

        # Create progress dialog
        progress_window = tk.Toplevel(parent_window)
        progress_window.title(_("finance_reporting.windows.creating_archive_tables"))
        progress_window.geometry("500x300")
        progress_window.transient(parent_window)
        progress_window.grab_set()

        ttk.Label(progress_window, text="Creating Archive Tables...",
                 font=('Arial', 12, 'bold')).pack(pady=20)

        progress_text = scrolledtext.ScrolledText(progress_window, height=10, wrap=tk.WORD)
        progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        def log_progress(message):
            progress_text.insert(tk.END, f"{message}\n")
            progress_text.see(tk.END)
            progress_window.update()

        conn = get_connection()
        cursor = conn.cursor()

        tables_created = 0

        # Archive table definitions
        archive_tables = [
            ('archived_transactions', '''
                CREATE TABLE IF NOT EXISTS archived_transactions (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    amount REAL,
                    transaction_type TEXT,
                    transaction_date TEXT,
                    description TEXT,
                    payment_method TEXT,
                    status TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('archived_payments', '''
                CREATE TABLE IF NOT EXISTS archived_payments (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    amount REAL,
                    payment_date TEXT,
                    payment_method TEXT,
                    category TEXT,
                    status TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('archived_financial_aid', '''
                CREATE TABLE IF NOT EXISTS archived_financial_aid (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    aid_type TEXT,
                    amount REAL,
                    academic_year TEXT,
                    status TEXT,
                    awarded_date TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('archived_budget_records', '''
                CREATE TABLE IF NOT EXISTS archived_budget_records (
                    id INTEGER PRIMARY KEY,
                    department TEXT,
                    category TEXT,
                    allocated_amount REAL,
                    spent_amount REAL,
                    fiscal_year TEXT,
                    archived_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('archive_metadata', '''
                CREATE TABLE IF NOT EXISTS archive_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT,
                    records_archived INTEGER,
                    archive_date TEXT,
                    archived_by TEXT,
                    date_range_start TEXT,
                    date_range_end TEXT
                )
            ''')
        ]

        log_progress("Starting archive table creation...")
        log_progress("=" * 60)

        for table_name, create_sql in archive_tables:
            try:
                cursor.execute(create_sql)

                # Create indices for better query performance
                from education_system.university_system.core.sql_safety import validate_table_name
                validated_tbl = validate_table_name(table_name, conn=conn)
                if table_name == 'archived_transactions':
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_trans_student ON [" + validated_tbl + "](student_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_trans_date ON [" + validated_tbl + "](transaction_date)")
                elif table_name == 'archived_payments':
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_pay_student ON [" + validated_tbl + "](student_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_pay_date ON [" + validated_tbl + "](payment_date)")
                elif table_name == 'archived_financial_aid':
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_aid_student ON [" + validated_tbl + "](student_id)")

                tables_created += 1
                log_progress(f"✓ Created table: {table_name}")

            except Exception as e:
                log_progress(f"✗ Error creating {table_name}: {e}")

        conn.commit()
        conn.close()

        log_progress("=" * 60)
        log_progress(f"\nArchive creation complete!")
        log_progress(f"Tables created: {tables_created}/{len(archive_tables)}")
        log_progress(f"Status: Ready for archiving operations")

        # Add close button
        ttk.Button(progress_window, text="Close",
                  command=progress_window.destroy).pack(pady=10)

        # Log activity
        try:
            from education_system.university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('create', 'archive_tables',
                       details={'tables_created': tables_created})
        except Exception:
            pass

    except Exception as e:
        messagebox.showerror("Error",
            f"Failed to create archive tables:\n{e}",
            parent=parent_window)
        import traceback
        traceback.print_exc()

def run_archive_process(self, parent_window):
    """Run the archive process to move old data to archive tables"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        # Confirm action
        if not messagebox.askyesno("Confirm Archive Process",
            "This will move old financial data to archive tables.\n\n"
            "Data Selection Criteria:\n"
            "• Transactions older than 2 years\n"
            "• Payments older than 2 years\n"
            "• Financial aid records older than 5 years\n"
            "• Budget records from completed fiscal years (3+ years old)\n\n"
            "Active data will be moved to archive tables and removed from main tables.\n"
            "This operation can take several minutes.\n\n"
            "Continue?", parent=parent_window):
            return

        # Create progress dialog
        progress_window = tk.Toplevel(parent_window)
        progress_window.title(_("finance_reporting.windows.running_archive_process"))
        progress_window.geometry("600x400")
        progress_window.transient(parent_window)
        progress_window.grab_set()

        ttk.Label(progress_window, text="Archiving Financial Data...",
                 font=('Arial', 12, 'bold')).pack(pady=20)

        progress_text = scrolledtext.ScrolledText(progress_window, height=15, wrap=tk.WORD)
        progress_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        progress_var = tk.IntVar(value=0)
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))

        def log_progress(message):
            progress_text.insert(tk.END, f"{message}\n")
            progress_text.see(tk.END)
            progress_window.update()

        conn = get_connection()
        cursor = conn.cursor()

        # Calculate cutoff dates
        two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        five_years_ago = (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d')
        three_years_ago = (datetime.now() - timedelta(days=1095)).strftime('%Y-%m-%d')

        log_progress("Starting archive process...")
        log_progress("=" * 70)
        log_progress(f"Archive date cutoffs:")
        log_progress(f"  • Transactions/Payments: Before {two_years_ago}")
        log_progress(f"  • Financial Aid: Before {five_years_ago}")
        log_progress(f"  • Budget Records: Before {three_years_ago}")
        log_progress("=" * 70)

        total_archived = 0

        # Archive transactions
        progress_var.set(10)
        log_progress("\n[1/4] Archiving old transactions...")
        try:
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
            if cursor.fetchone():
                # Note: We don't delete old payments as they're historical records
                # Just log that we checked them
                cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date < ?', (two_years_ago,))
                old_payments = cursor.fetchone()[0] or 0
                log_progress(f"  ℹ Found {old_payments} old payment records (retained for audit trail)")
            else:
                log_progress("  ⚠ Payments table not found - skipping")
        except Exception as e:
            log_progress(f"  ✗ Error archiving transactions: {e}")

        # Archive payments
        progress_var.set(35)
        log_progress("\n[2/4] Archiving old payments...")
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_payments'")
            if cursor.fetchone():
                cursor.execute('''
                    INSERT INTO archived_payments
                    SELECT *, CURRENT_TIMESTAMP FROM student_payments
                    WHERE payment_date < ?
                ''', (two_years_ago,))

                archived_count = cursor.rowcount

                cursor.execute('DELETE FROM student_payments WHERE payment_date < ?', (two_years_ago,))

                total_archived += archived_count
                log_progress(f"  ✓ Archived {archived_count} payment records")
            else:
                log_progress("  ⚠ Student payments table not found - skipping")
        except Exception as e:
            log_progress(f"  ✗ Error archiving payments: {e}")

        # Archive financial aid
        progress_var.set(60)
        log_progress("\n[3/4] Archiving old financial aid records...")
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='financial_aid'")
            if cursor.fetchone():
                cursor.execute('''
                    INSERT INTO archived_financial_aid
                    SELECT *, CURRENT_TIMESTAMP FROM financial_aid
                    WHERE awarded_date < ?
                ''', (five_years_ago,))

                archived_count = cursor.rowcount

                cursor.execute('DELETE FROM financial_aid WHERE awarded_date < ?', (five_years_ago,))

                total_archived += archived_count
                log_progress(f"  ✓ Archived {archived_count} financial aid records")
            else:
                log_progress("  ⚠ Financial aid table not found - skipping")
        except Exception as e:
            log_progress(f"  ✗ Error archiving financial aid: {e}")

        # Archive budget records
        progress_var.set(85)
        log_progress("\n[4/4] Archiving old budget records...")
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='budget_allocations'")
            if cursor.fetchone():
                cursor.execute('''
                    INSERT INTO archived_budget_records
                    SELECT *, CURRENT_TIMESTAMP FROM budget_allocations
                    WHERE fiscal_year < ?
                ''', (three_years_ago[:4],))  # Just year for budget records

                archived_count = cursor.rowcount

                cursor.execute('DELETE FROM budget_allocations WHERE fiscal_year < ?', (three_years_ago[:4],))

                total_archived += archived_count
                log_progress(f"  ✓ Archived {archived_count} budget records")
            else:
                log_progress("  ⚠ Budget allocations table not found - skipping")
        except Exception as e:
            log_progress(f"  ✗ Error archiving budget records: {e}")

        # Record archive metadata
        progress_var.set(95)
        log_progress("\n[Metadata] Recording archive operation...")
        try:
            current_user = "System"
            if self.auth and hasattr(self.auth, 'get_current_user'):
                user = self.auth.get_current_user()
                if user:
                    current_user = user.get('username', 'System')

            cursor.execute('''
                INSERT INTO archive_metadata
                (table_name, records_archived, archive_date, archived_by, date_range_start, date_range_end)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('all_tables', total_archived, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  current_user, five_years_ago, two_years_ago))

            log_progress("  ✓ Archive metadata recorded")
        except Exception as e:
            log_progress(f"  ⚠ Error recording metadata: {e}")

        # Vacuum database to reclaim space
        progress_var.set(98)
        log_progress("\n[Optimization] Optimizing database...")
        try:
            cursor.execute('VACUUM')
            log_progress("  ✓ Database optimized")
        except Exception as e:
            log_progress(f"  ⚠ Error optimizing database: {e}")

        conn.commit()
        conn.close()

        progress_var.set(100)
        log_progress("=" * 70)
        log_progress(f"\n✓ Archive process completed successfully!")
        log_progress(f"Total records archived: {total_archived}")
        log_progress(f"Archive date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_progress("\nThe database has been optimized and old data moved to archive tables.")

        # Add close button
        ttk.Button(progress_window, text="Close",
                  command=progress_window.destroy).pack(pady=10)

        # Log activity
        try:
            from education_system.university_system.modules.shared.utils.activity_logger import log_activity
            log_activity('archive', 'financial_data',
                       details={'records_archived': total_archived})
        except Exception:
            pass

    except Exception as e:
        messagebox.showerror("Error",
            f"Failed to run archive process:\n{e}",
            parent=parent_window)
        import traceback
        traceback.print_exc()
