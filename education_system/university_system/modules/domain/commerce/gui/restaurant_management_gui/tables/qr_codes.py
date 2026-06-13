from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def generate_qr_dialog(self):
    """Show QR code management menu"""
    dialog = tk.Toplevel(self.root)
    dialog.title("QR Code Management")
    dialog.geometry("500x600")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="QR Code Management",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Generate QR Codes section
    generate_section = ttk.LabelFrame(main_frame, text="Generate QR Codes", padding=15)
    generate_section.pack(fill='x', pady=10)
    ttk.Button(generate_section, text="Generate Single QR Code",
              command=self.create_qr_code_image,
              width=30).pack(pady=5)
    ttk.Button(generate_section, text="Generate Enhanced Branded QR",
              command=self.create_enhanced_qr_image,
              width=30).pack(pady=5)
    ttk.Button(generate_section, text="Batch Print QR Codes",
              command=self.print_qr_codes,
              width=30).pack(pady=5)
    # Analytics section
    analytics_section = ttk.LabelFrame(main_frame, text="QR Code Analytics", padding=15)
    analytics_section.pack(fill='x', pady=10)
    ttk.Button(analytics_section, text="View QR Code Usage Analytics",
              command=self.scan_qr_code_usage,
              width=30).pack(pady=5)
    # Management section
    mgmt_section = ttk.LabelFrame(main_frame, text="QR Code Database", padding=15)
    mgmt_section.pack(fill='x', pady=10)
    ttk.Button(mgmt_section, text="Update QR Database Records",
              command=self.update_qr_database_record,
              width=30).pack(pady=5)
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

def create_qr_code_image(self):
    """Generate individual QR code image for a table"""
    try:
        import qrcode
        from tkinter import filedialog
        import os
        # Ask for table number
        table_number = simpledialog.askstring("Generate QR Code",
                                              "Enter table number:")
        if not table_number:
            return
        # Create QR code data
        qr_data = f"https://restaurant.example.com/table/{table_number}"
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        # Ask where to save
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=f"table_{table_number}_qr.png"
        )
        if filename:
            img.save(filename)
            # Update database
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS qr_codes (
                        qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_number TEXT,
                        qr_data TEXT,
                        generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        image_path TEXT
                    )
                ''')
                cursor.execute('''
                    INSERT INTO qr_codes (table_number, qr_data, image_path)
                    VALUES (?, ?, ?)
                ''', (table_number, qr_data, filename))
                conn.commit()
                conn.close()
            messagebox.showinfo("Success",
                               f"QR code generated successfully!\n\n" +
                               f"Table: {table_number}\n" +
                               f"Saved to: {filename}\n" +
                               f"Size: High resolution (suitable for printing)")
    except ImportError:
        messagebox.showerror("Missing Library",
                            "QR code generation requires the 'qrcode' library.\n\n" +
                            "Install with: pip install qrcode[pil]")
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate QR code:\n{str(e)}")

def create_enhanced_qr_image(self):
    """Generate branded QR code with logo and colors"""
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
        from tkinter import filedialog
        # Ask for table number
        table_number = simpledialog.askstring("Generate Enhanced QR",
                                              "Enter table number:")
        if not table_number:
            return
        # Ask for customization
        include_label = messagebox.askyesno("Customization",
                                           "Include table number label on QR code?")
        # Create QR code data
        qr_data = f"https://restaurant.example.com/table/{table_number}"
        # Generate QR code with higher error correction for logo overlay
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        # Create image with white background
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        if include_label:
            # Add label below QR code
            from PIL import ImageDraw, ImageFont
            width, height = img.size
            new_img = Image.new('RGB', (width, height + 80), 'white')
            new_img.paste(img, (0, 0))
            draw = ImageDraw.Draw(new_img)
            try:
                # Try to use a nice font
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except (OSError, IOError):
                # Fallback to default
                font = ImageFont.load_default()
            text = f"Table {table_number}"
            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (width - text_width) // 2
            text_y = height + 20
            draw.text((text_x, text_y), text, fill="black", font=font)
            img = new_img
        # Ask where to save
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=f"table_{table_number}_branded_qr.png"
        )
        if filename:
            img.save(filename, quality=95)
            # Update database
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS qr_codes (
                        qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        table_number TEXT,
                        qr_data TEXT,
                        generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        image_path TEXT,
                        is_branded BOOLEAN DEFAULT 0
                    )
                ''')
                cursor.execute('''
                    INSERT INTO qr_codes (table_number, qr_data, image_path, is_branded)
                    VALUES (?, ?, ?, 1)
                ''', (table_number, qr_data, filename))
                conn.commit()
                conn.close()
            messagebox.showinfo("Success",
                               f"Enhanced QR code generated!\n\n" +
                               f"Table: {table_number}\n" +
                               f"Saved to: {filename}\n" +
                               f"Features: High quality, labeled")
    except ImportError:
        messagebox.showerror("Missing Library",
                            "Enhanced QR code generation requires 'qrcode' and 'Pillow'.\n\n" +
                            "Install with: pip install qrcode[pil] Pillow")
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate enhanced QR code:\n{str(e)}")

def print_qr_codes(self):
    """Batch generate and print QR codes for multiple tables"""
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
        from tkinter import filedialog
        # Ask for table range
        start_table = simpledialog.askinteger("Batch Generate",
                                             "Start table number:",
                                             minvalue=1, maxvalue=100)
        if not start_table:
            return
        end_table = simpledialog.askinteger("Batch Generate",
                                           "End table number:",
                                           minvalue=start_table, maxvalue=100)
        if not end_table:
            return
        # Ask for save directory
        save_dir = filedialog.askdirectory(title="Select folder to save QR codes")
        if not save_dir:
            return
        generated_count = 0
        errors = []
        for table_num in range(start_table, end_table + 1):
            try:
                # Create QR code
                qr_data = f"https://restaurant.example.com/table/{table_num}"
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                # Add label
                width, height = img.size
                new_img = Image.new('RGB', (width, height + 80), 'white')
                new_img.paste(img, (0, 0))
                draw = ImageDraw.Draw(new_img)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                except (OSError, IOError):
                    font = ImageFont.load_default()
                text = f"Table {table_num}"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_x = (width - text_width) // 2
                text_y = height + 20
                draw.text((text_x, text_y), text, fill="black", font=font)
                # Save
                import os
                filename = os.path.join(save_dir, f"table_{table_num:03d}_qr.png")
                new_img.save(filename, quality=95)
                # Update database
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS qr_codes (
                            qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            table_number TEXT,
                            qr_data TEXT,
                            generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            image_path TEXT,
                            is_branded BOOLEAN DEFAULT 0
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO qr_codes (table_number, qr_data, image_path, is_branded)
                        VALUES (?, ?, ?, 1)
                    ''', (str(table_num), qr_data, filename))
                    conn.commit()
                    conn.close()
                generated_count += 1
            except sqlite3.Error as e:
                errors.append(f"Table {table_num}: {str(e)}")
        # Show results
        result_msg = f"Batch QR Code Generation Complete!\n\n"
        result_msg += f"Successfully generated: {generated_count} QR codes\n"
        result_msg += f"Saved to: {save_dir}\n"
        if errors:
            result_msg += f"\nErrors ({len(errors)}):\n"
            result_msg += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                result_msg += f"\n... and {len(errors) - 5} more"
        messagebox.showinfo("Batch Generation Complete", result_msg)
    except ImportError:
        messagebox.showerror("Missing Library",
                            "Batch QR code generation requires 'qrcode' and 'Pillow'.\n\n" +
                            "Install with: pip install qrcode[pil] Pillow")
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Batch generation failed:\n{str(e)}")

def scan_qr_code_usage(self):
    """Display QR code scanning analytics"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qr_scans (
                scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number TEXT,
                scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                customer_id INTEGER,
                device_type TEXT
            )
        ''')
        conn.commit()
        # Get analytics data
        cursor.execute('''
            SELECT COUNT(*) FROM qr_scans
        ''')
        total_scans = cursor.fetchone()[0]
        cursor.execute('''
            SELECT table_number, COUNT(*) as scan_count
            FROM qr_scans
            GROUP BY table_number
            ORDER BY scan_count DESC
            LIMIT 10
        ''')
        top_tables = cursor.fetchall()
        cursor.execute('''
            SELECT strftime('%H', scan_time) as hour, COUNT(*) as count
            FROM qr_scans
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 5
        ''')
        peak_hours = cursor.fetchall()
        cursor.execute('''
            SELECT DATE(scan_time) as date, COUNT(*) as count
            FROM qr_scans
            WHERE scan_time >= date('now', '-7 days')
            GROUP BY date
            ORDER BY date DESC
        ''')
        recent_scans = cursor.fetchall()
        conn.close()
        # Display analytics
        analytics_dialog = tk.Toplevel(self.root)
        analytics_dialog.title("QR Code Usage Analytics")
        analytics_dialog.geometry("800x600")
        analytics_dialog.transient(self.root)
        main_frame = ttk.Frame(analytics_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="QR Code Usage Analytics",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Create scrolled text for report
        report_text = ScrolledText(main_frame, height=30, width=90)
        report_text.pack(fill='both', expand=True)
        report = "QR CODE USAGE ANALYTICS\n"
        report += "=" * 80 + "\n\n"
        report += f"OVERALL STATISTICS:\n"
        report += "-" * 80 + "\n"
        report += f"Total Scans: {total_scans}\n\n"
        report += "TOP 10 MOST SCANNED TABLES:\n"
        report += "-" * 80 + "\n"
        report += f"{'Table':<15} {'Scan Count':<15} {'Engagement':<20}\n"
        report += "-" * 80 + "\n"
        for table, count in top_tables:
            engagement = "High" if count > 50 else "Medium" if count > 20 else "Low"
            report += f"{table:<15} {count:<15} {engagement:<20}\n"
        report += "\n\nPEAK SCANNING HOURS:\n"
        report += "-" * 80 + "\n"
        report += f"{'Hour':<15} {'Scan Count':<15} {'Time Period':<20}\n"
        report += "-" * 80 + "\n"
        for hour, count in peak_hours:
            if hour:
                hour_int = int(hour)
                period = "Breakfast" if 6 <= hour_int < 11 else "Lunch" if 11 <= hour_int < 15 else "Dinner" if 17 <= hour_int < 22 else "Other"
                report += f"{hour:02d}:00{' '*9} {count:<15} {period:<20}\n"
        report += "\n\nSCANS BY DATE (Last 7 Days):\n"
        report += "-" * 80 + "\n"
        report += f"{'Date':<15} {'Scan Count':<15} {'Trend':<20}\n"
        report += "-" * 80 + "\n"
        for date, count in recent_scans:
            trend = "▲" if count > 30 else "▼" if count < 10 else "■"
            report += f"{date:<15} {count:<15} {trend:<20}\n"
        report += "\n\nKEY INSIGHTS:\n"
        report += "-" * 80 + "\n"
        if total_scans == 0:
            report += "• No QR code scans recorded yet\n"
            report += "• Generate and distribute QR codes to tables\n"
            report += "• Encourage customers to scan for digital menus\n"
        else:
            report += f"• Average scans per table: {total_scans / max(len(top_tables), 1):.1f}\n"
            if peak_hours:
                report += f"• Peak usage hour: {peak_hours[0][0]}:00\n"
            if top_tables:
                report += f"• Most popular table: {top_tables[0][0]} ({top_tables[0][1]} scans)\n"
            report += "• QR code effectiveness: " + ("High" if total_scans > 100 else "Medium" if total_scans > 30 else "Low") + "\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        # Add simulate scan button for testing
        def simulate_scan():
            table = simpledialog.askstring("Simulate Scan", "Enter table number:")
            if table:
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO qr_scans (table_number, device_type)
                            VALUES (?, 'Mobile')
                        ''', (table,))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("Success", f"Simulated scan for Table {table}")
                        analytics_dialog.destroy()
                        self.scan_qr_code_usage()  # Refresh
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to simulate scan: {e}")
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Simulate Scan (Testing)",
                  command=simulate_scan).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close",
                  command=analytics_dialog.destroy).pack(side='left', padx=5)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load QR analytics:\n{str(e)}")

def update_qr_database_record(self):
    """Update QR code database records"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Create table if doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qr_codes (
                qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number TEXT,
                qr_data TEXT,
                generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                is_branded BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                version INTEGER DEFAULT 1
            )
        ''')
        conn.commit()
        # Get all QR codes
        cursor.execute('''
            SELECT qr_id, table_number, generated_date, is_active, version
            FROM qr_codes
            ORDER BY table_number
        ''')
        qr_records = cursor.fetchall()
        conn.close()
        if not qr_records:
            messagebox.showinfo("No Records",
                               "No QR code records found in database.\n\n" +
                               "Generate QR codes first to create records.")
            return
        # Show management dialog
        mgmt_dialog = tk.Toplevel(self.root)
        mgmt_dialog.title("QR Code Database Management")
        mgmt_dialog.geometry("800x500")
        mgmt_dialog.transient(self.root)
        main_frame = ttk.Frame(mgmt_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="QR Code Database Records",
                 font=('Arial', 12, 'bold')).pack(pady=10)
        # Create treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)
        columns = ('ID', 'Table', 'Generated', 'Active', 'Version')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        for record in qr_records:
            qr_id, table, gen_date, is_active, version = record
            active_status = "Yes" if is_active else "No"
            tree.insert('', 'end', values=(qr_id, table, gen_date, active_status, version))
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        # Action buttons
        def regenerate_qr():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a QR code to regenerate")
                return
            item = tree.item(selection[0])
            qr_id = item['values'][0]
            table_num = item['values'][1]
            if messagebox.askyesno("Confirm", f"Regenerate QR code for Table {table_num}?"):
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE qr_codes
                            SET version = version + 1,
                                generated_date = CURRENT_TIMESTAMP
                            WHERE qr_id = ?
                        ''', (qr_id,))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("Success", f"QR code record updated for Table {table_num}")
                        mgmt_dialog.destroy()
                        self.update_qr_database_record()  # Refresh
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to update record: {e}")
        def toggle_active():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a QR code")
                return
            item = tree.item(selection[0])
            qr_id = item['values'][0]
            table_num = item['values'][1]
            current_status = item['values'][3]
            new_status = 0 if current_status == "Yes" else 1
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE qr_codes
                        SET is_active = ?
                        WHERE qr_id = ?
                    ''', (new_status, qr_id))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success",
                                       f"Table {table_num} QR code " +
                                       ("activated" if new_status else "deactivated"))
                    mgmt_dialog.destroy()
                    self.update_qr_database_record()  # Refresh
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to update status: {e}")
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Regenerate Selected",
                  command=regenerate_qr).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Toggle Active/Inactive",
                  command=toggle_active).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close",
                  command=mgmt_dialog.destroy).pack(side='left', padx=5)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to manage QR database:\n{str(e)}")

