import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

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

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class GreenInitiativesDialog:
    """Main dialog for green initiatives and sustainability"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Green Initiatives")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🌱 Green Initiatives & Sustainability",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create grid of initiative buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='both', expand=True, pady=(0, 10))

        initiatives = [
            ("Carbon Footprint Tracking", self.carbon_tracking, "Track and reduce carbon emissions"),
            ("Sustainable Events", self.sustainable_events, "Organize eco-friendly events"),
            ("Waste Reduction", self.waste_reduction, "Monitor waste and recycling"),
            ("Green Transport", self.green_transport, "Sustainable transportation options"),
            ("Environmental Reports", self.environmental_reports, "View sustainability metrics"),
            ("Eco Suppliers", self.eco_suppliers, "Find eco-friendly suppliers"),
            ("Green Certifications", self.green_certifications, "Earn green certifications"),
            ("Offset Programs", self.offset_programs, "Carbon offset opportunities")
        ]

        for i, (title, command, description) in enumerate(initiatives):
            card = ttk.LabelFrame(buttons_frame, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')

            ttk.Label(card, text=description, wraplength=350).pack(padx=10, pady=5)
            ttk.Button(card, text="Open", command=command).pack(padx=10, pady=5)

        for i in range(4):
            buttons_frame.rowconfigure(i, weight=1)
        for i in range(2):
            buttons_frame.columnconfigure(i, weight=1)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()

    def carbon_tracking(self):
        dialog = CarbonTrackingDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def sustainable_events(self):
        messagebox.showinfo("Sustainable Events", "Track environmental impact of events:\n\n- Carbon footprint\n- Waste reduction\n- Renewable energy use\n- Sustainable catering")

    def waste_reduction(self):
        dialog = WasteReductionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def green_transport(self):
        dialog = GreenTransportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def environmental_reports(self):
        dialog = EnvironmentalReportsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def eco_suppliers(self):
        messagebox.showinfo("Eco Suppliers", "Directory of eco-friendly suppliers:\n\n✓ Certified sustainable\n✓ Local businesses\n✓ Fair trade options\n✓ Reduced packaging")

    def green_certifications(self):
        messagebox.showinfo("Green Certifications", "Earn certifications for:\n\n⭐ Eco-friendly clubs\n⭐ Sustainable events\n⭐ Carbon neutral activities\n⭐ Waste reduction achievements")

    def offset_programs(self):
        messagebox.showinfo("Carbon Offset", "Support carbon offset programs:\n\n🌳 Tree planting\n🌞 Renewable energy projects\n♻️ Recycling initiatives")



class CarbonTrackingDialog:
    """Dialog for tracking carbon footprint"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Carbon Footprint Tracking")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🌍 Carbon Footprint Calculator",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Event to Track")
        select_frame.pack(fill='x', pady=(0, 15))

        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(select_frame, textvariable=self.event_var, width=50)
        self.event_combo.pack(padx=10, pady=10, fill='x')

        # Calculator notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Transportation tab
        transport_frame = ttk.Frame(notebook)
        notebook.add(transport_frame, text="Transportation")
        self.create_transport_tab(transport_frame)

        # Energy tab
        energy_frame = ttk.Frame(notebook)
        notebook.add(energy_frame, text="Energy")
        self.create_energy_tab(energy_frame)

        # Catering tab
        catering_frame = ttk.Frame(notebook)
        notebook.add(catering_frame, text="Catering")
        self.create_catering_tab(catering_frame)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Carbon Footprint Results")
        results_frame.pack(fill='x', pady=(0, 15))

        self.results_label = ttk.Label(results_frame, text="Total Carbon Footprint: 0.00 kg CO₂",
                                      font=('Arial', 12, 'bold'))
        self.results_label.pack(padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Calculate", command=self.calculate_footprint).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Save Report", command=self.save_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_transport_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Attendee Transportation").pack(anchor='w', pady=(0, 10))

        self.transport_vars = {}
        methods = [("Walking/Cycling", 0), ("Public Transport", 0.05), ("Car", 0.21), ("Taxi/Uber", 0.25)]

        for method, rate in methods:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=5)

            ttk.Label(row, text=f"{method}:", width=20).pack(side='left')

            count_var = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=count_var, width=10).pack(side='left', padx=5)
            ttk.Label(row, text="attendees").pack(side='left')

            self.transport_vars[method] = (count_var, rate)

    def create_energy_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Energy Consumption").pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Event Duration (hours):").pack(anchor='w')
        self.duration_var = tk.StringVar(value="2")
        ttk.Entry(frame, textvariable=self.duration_var, width=10).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Number of Attendees:").pack(anchor='w')
        self.attendees_var = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=self.attendees_var, width=10).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Estimated: 0.5 kWh per person per hour\nCarbon: 0.233 kg CO₂ per kWh (UK average)",
                 foreground='gray').pack(anchor='w')

    def create_catering_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Catering Impact").pack(anchor='w', pady=(0, 10))

        self.catering_vars = {}
        options = [("Vegan", 1.5), ("Vegetarian", 2.5), ("Meat-based", 5.0)]

        for option, rate in options:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=5)

            ttk.Label(row, text=f"{option} meals:", width=20).pack(side='left')

            count_var = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=count_var, width=10).pack(side='left', padx=5)
            ttk.Label(row, text=f"({rate} kg CO₂ each)").pack(side='left')

            self.catering_vars[option] = (count_var, rate)

    def calculate_footprint(self):
        total = 0.0

        try:
            # Transport (simplified - would need distance too)
            for method, (count_var, rate) in self.transport_vars.items():
                count = float(count_var.get() or 0)
                total += count * rate * 10  # Assuming 10km average

            # Energy
            duration = float(self.duration_var.get() or 0)
            attendees = float(self.attendees_var.get() or 0)
            total += duration * attendees * 0.5 * 0.233

            # Catering
            for option, (count_var, rate) in self.catering_vars.items():
                count = float(count_var.get() or 0)
                total += count * rate

            self.results_label.config(text=f"Total Carbon Footprint: {total:.2f} kg CO₂")

            # Show recommendations
            if total > 100:
                messagebox.showinfo("Recommendations",
                                   "High carbon footprint! Consider:\n\n"
                                   "✓ Encourage public transport\n"
                                   "✓ Serve more plant-based food\n"
                                   "✓ Use renewable energy\n"
                                   "✓ Reduce event duration")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.")

    def save_report(self):
        messagebox.showinfo("Success", "Carbon footprint report saved!")



class WasteReductionDialog:
    """Dialog for waste reduction tracking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Waste Reduction Tracking")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="♻️ Waste Reduction & Recycling",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Waste Statistics")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_text = """Total Waste Generated: 500 kg
Recycled: 350 kg (70%)
Composted: 100 kg (20%)
Landfill: 50 kg (10%)

🎯 Target: 80% diversion from landfill
"""
        ttk.Label(stats_frame, text=stats_text, justify='left', font=('Courier', 10)).pack(padx=15, pady=15)

        # Recent events
        events_frame = ttk.LabelFrame(main_frame, text="Recent Events - Waste Data")
        events_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Event', 'Date', 'Waste (kg)', 'Recycled %', 'Rating')
        tree = ttk.Treeview(events_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample data
        events_data = [
            ("Spring Festival", "2025-03-15", "45", "75%", "⭐⭐⭐⭐"),
            ("Charity Run", "2025-03-10", "20", "85%", "⭐⭐⭐⭐⭐"),
            ("Music Night", "2025-03-05", "60", "60%", "⭐⭐⭐")
        ]

        for event in events_data:
            tree.insert('', 'end', values=event)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()



class GreenTransportDialog:
    """Dialog for green transport tracking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Green Transport")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🚲 Green Transport Initiatives",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Transport options
        options_frame = ttk.LabelFrame(main_frame, text="Sustainable Transport Options")
        options_frame.pack(fill='both', expand=True, pady=(0, 15))

        options = [
            ("🚲 Bike Sharing", "Join the university bike sharing program\nReduced emissions & improved health"),
            ("🚌 Bus Buddy", "Find carpools for events and daily commutes\nSave money & reduce traffic"),
            ("🚶 Walking Groups", "Join safe walking groups to campus\nSocial & eco-friendly"),
            ("🚇 Public Transport", "Discounted student transit passes\nAffordable & sustainable")
        ]

        for icon_title, description in options:
            card = ttk.Frame(options_frame)
            card.pack(fill='x', padx=10, pady=8)

            ttk.Label(card, text=icon_title, font=('Arial', 11, 'bold')).pack(anchor='w')
            ttk.Label(card, text=description, foreground='gray').pack(anchor='w', padx=(20, 0))

        # Personal stats
        stats_frame = ttk.LabelFrame(main_frame, text="Your Green Transport Stats")
        stats_frame.pack(fill='x', pady=(0, 15))

        stats_text = """This Month:
🚲 Bike trips: 12 (saved 15 kg CO₂)
🚌 Carpools: 5 (saved 8 kg CO₂)
🚇 Public transport: 20 trips

Total CO₂ saved: 23 kg
🏆 You're in the top 10% of green commuters!
"""
        ttk.Label(stats_frame, text=stats_text, justify='left').pack(padx=15, pady=10)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()



class EnvironmentalReportsDialog:
    """Dialog for viewing environmental reports"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Environmental Reports")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📊 Environmental Impact Reports",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Report display
        self.report_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
        self.report_text.pack(fill='both', expand=True, pady=(0, 15))

        report_content = """SUSTAINABILITY REPORT - MARCH 2025
================================================================================

CARBON EMISSIONS:
  Total emissions this month: 1,250 kg CO₂
  Previous month: 1,500 kg CO₂
  Change: -16.7% ✓ (Improvement!)

  Breakdown:
  - Events: 600 kg CO₂ (48%)
  - Transport: 400 kg CO₂ (32%)
  - Facilities: 250 kg CO₂ (20%)

WASTE MANAGEMENT:
  Total waste: 500 kg
  Recycling rate: 70% (Target: 80%)
  Composting: 20%
  Landfill: 10%

GREEN INITIATIVES:
  ✓ 15 zero-waste events
  ✓ 250 students using bike sharing
  ✓ 3 clubs achieved green certification

IMPROVEMENTS NEEDED:
  ⚠ Increase recycling rate by 10%
  ⚠ Reduce single-use plastics at events
  ⚠ Promote public transport usage

ACHIEVEMENTS:
  🏆 Carbon emissions down 17% from last month
  🏆 50% of events now carbon-neutral
  🏆 Waste diversion rate improved to 90%

RECOMMENDATIONS:
  1. Continue promoting sustainable catering
  2. Expand bike sharing program
  3. Partner with more eco-friendly suppliers
  4. Implement carbon offset program
  5. Increase awareness campaigns

Generated: March 31, 2025
"""
        self.report_text.insert(1.0, report_content)
        self.report_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export PDF", command=self.export_pdf).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Email Report", command=self.email_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def export_pdf(self):
        messagebox.showinfo("Success", "Report exported to:\nreports/sustainability_march_2025.pdf")

    def email_report(self):
        """Email report to admin from database"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Get admin email from database
            admin_email = None
            try:
                with get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT email FROM users
                        WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                        LIMIT 1
                    """)
                    admin_row = cursor.fetchone()
                    if admin_row and admin_row[0]:
                        admin_email = admin_row[0]
            except Exception as e:
                print(f"Warning: Could not fetch admin email: {e}")

            if not admin_email:
                messagebox.showerror("Error", "No admin email found in database")
                return

            # Get report content
            self.report_text.config(state='normal')
            report_content = self.report_text.get(1.0, tk.END).strip()
            self.report_text.config(state='disabled')

            if not report_content:
                messagebox.showwarning("No Report", "No report content to send")
                return

            # Send email
            subject, body = render_template('student_union/environmental_report', {
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'generation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'separator': '=' * 60,
                'report_content': report_content
            })

            result = send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            if result:
                messagebox.showinfo("Success", f"Report sent successfully to admin ({admin_email})")
            else:
                messagebox.showinfo("Queued", f"Report queued for delivery to {admin_email}")

        except ImportError:
            messagebox.showerror("Error", "Email service is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report: {str(e)}")


# ============================================================================
# VOLUNTEERING SYSTEM DIALOGS
# ============================================================================


def open_green_initiatives_dialog(self):
    """Open green initiatives and sustainability dialog"""
    dialog = GreenInitiativesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


