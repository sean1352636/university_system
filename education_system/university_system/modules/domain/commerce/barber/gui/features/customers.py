"""Barber Shop GUI - Customer management feature methods."""

from education_system.university_system.modules.domain.commerce.barber.gui.common import (
    tk, ttk, messagebox, filedialog, logging, csv, json,
    _t, log_activity,
    EMAIL_AVAILABLE,
)

logger = logging.getLogger(__name__)


class CustomersMixin:
    """Mixin providing customer management methods for BarberGUI."""

    def create_customer_profile(self):
        """Create customer profile."""
        profile_window = tk.Toplevel(self.parent)
        profile_window.title("Create Customer Profile")
        profile_window.geometry("400x400")
        profile_window.transient(self.parent)
        profile_window.grab_set()

        ttk.Label(profile_window, text="Create Customer Profile",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(profile_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=email_var, width=30).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Phone:").grid(row=2, column=0, sticky=tk.W, pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=phone_var, width=30).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Preferred Barber:").grid(row=3, column=0, sticky=tk.W, pady=5)
        barber_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=20)
        barber_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Notes:").grid(row=4, column=0, sticky=tk.W, pady=5)
        notes_text = tk.Text(frame, height=4, width=25)
        notes_text.grid(row=4, column=1, pady=5)

        def save_profile():
            if not name_var.get().strip():
                messagebox.showerror("Error", "Name is required.")
                return
            try:
                preferred_staff = None
                if barber_combo.get() and barber_combo.get() != 'Any':
                    preferred_staff = int(barber_combo.get().split(':')[0])

                from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
                customer_id = name_var.get().strip().replace(' ', '_').lower()[:20]

                # Build preferences string with preferred staff
                prefs = f"Preferred staff: {preferred_staff}" if preferred_staff else ""

                CustomerManager.create_profile(
                    customer_id=customer_id,
                    name=name_var.get().strip(),
                    email=email_var.get().strip(),
                    phone=phone_var.get().strip(),
                    preferences=prefs,
                    notes=notes_text.get('1.0', tk.END).strip()
                )
                messagebox.showinfo("Success", "Customer profile created!")
                profile_window.destroy()
                self._load_customers()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(profile_window, text="Save Profile", command=save_profile).pack(pady=10)

    def view_customer_details(self):
        """View customer details."""
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return

        item = self.customers_tree.item(selected[0])
        customer_id = item['values'][0]

        details_window = tk.Toplevel(self.parent)
        details_window.title("Customer Details")
        details_window.geometry("600x500")
        details_window.transient(self.parent)

        try:
            from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
            customer = CustomerManager.get_customer(customer_id)

            if not customer:
                messagebox.showerror("Error", "Customer not found.")
                details_window.destroy()
                return

            # Customer info
            info_frame = ttk.LabelFrame(details_window, text="Customer Information", padding="10")
            info_frame.pack(fill=tk.X, padx=20, pady=10)

            ttk.Label(info_frame, text=f"Name: {customer['name']}", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Email: {customer.get('email', 'N/A')}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Phone: {customer.get('phone', 'N/A')}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Total Visits: {customer.get('visit_count', 0)}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Last Visit: {customer.get('last_visit', 'N/A')}").pack(anchor=tk.W)

            # Notes
            notes_frame = ttk.LabelFrame(details_window, text="Notes", padding="10")
            notes_frame.pack(fill=tk.X, padx=20, pady=10)

            notes_text = tk.Text(notes_frame, height=5, width=50)
            notes_text.pack(fill=tk.X)
            notes_text.insert('1.0', customer.get('notes', ''))
            notes_text.config(state='disabled')

            # Recent appointments
            appt_frame = ttk.LabelFrame(details_window, text="Recent Appointments", padding="10")
            appt_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            columns = ('date', 'service', 'barber', 'status')
            tree = ttk.Treeview(appt_frame, columns=columns, show='headings', height=6)
            for col in columns:
                tree.heading(col, text=col.title())
                tree.column(col, width=120)
            tree.pack(fill=tk.BOTH, expand=True)

            appointments = CustomerManager.get_customer_appointments(customer_id, limit=10)
            for appt in appointments:
                tree.insert('', tk.END, values=(
                    appt['appointment_date'], appt.get('service_name', 'N/A'),
                    appt.get('staff_name', 'Any'), appt['status']
                ))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_customer_notes(self):
        """Add customer notes."""
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return

        item = self.customers_tree.item(selected[0])
        customer_id = item['values'][0]
        customer_name = item['values'][1]

        notes_window = tk.Toplevel(self.parent)
        notes_window.title(f"Notes for {customer_name}")
        notes_window.geometry("400x300")
        notes_window.transient(self.parent)
        notes_window.grab_set()

        ttk.Label(notes_window, text=f"Add Note for {customer_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        notes_text = tk.Text(notes_window, height=8, width=45)
        notes_text.pack(padx=20, pady=10)

        def save_note():
            note = notes_text.get('1.0', tk.END).strip()
            if not note:
                return
            try:
                from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
                CustomerManager.add_note(
                    customer_id=customer_id,
                    note=note,
                    created_by=self.current_user.get('username')
                )
                messagebox.showinfo("Success", "Note added!")
                notes_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(notes_window, text="Save Note", command=save_note).pack(pady=10)

    def search_customers(self):
        """Search customers."""
        search_term = self.customer_search_var.get().strip()
        if not search_term:
            self._load_customers()
            return

        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)

        try:
            from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
            customers = CustomerManager.search_customers(search_term)
            for cust in customers:
                self.customers_tree.insert('', tk.END, values=(
                    cust['customer_id'], cust['name'], cust.get('email', ''),
                    cust.get('phone', ''), cust.get('visit_count', 0),
                    cust.get('last_visit', 'N/A'),
                    'Yes' if cust.get('is_favorite') else 'No'
                ))
        except Exception as e:
            logger.error(f"Error searching customers: {e}")

    def view_favorite_customers(self):
        """View favorite customers."""
        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)

        try:
            from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
            customers = CustomerManager.get_vip_customers()
            for cust in customers:
                self.customers_tree.insert('', tk.END, values=(
                    cust['customer_id'], cust['name'], cust.get('email', ''),
                    cust.get('phone', ''), cust.get('total_visits', 0),
                    cust.get('last_visit', 'N/A'), 'Yes'
                ))
        except Exception as e:
            logger.error(f"Error loading favorites: {e}")

    def send_customer_message(self):
        """Send message to customer."""
        selected = self.customers_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a customer.")
            return

        item = self.customers_tree.item(selected[0])
        customer_id = item['values'][0]
        customer_name = item['values'][1]
        customer_email = item['values'][2]

        if not customer_email:
            messagebox.showerror("Error", "Customer has no email address.")
            return

        msg_window = tk.Toplevel(self.parent)
        msg_window.title(f"Message to {customer_name}")
        msg_window.geometry("450x350")
        msg_window.transient(self.parent)
        msg_window.grab_set()

        ttk.Label(msg_window, text=f"Send Message to {customer_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(msg_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"To: {customer_email}").pack(anchor=tk.W)

        ttk.Label(frame, text="Subject:").pack(anchor=tk.W, pady=(10, 0))
        subject_var = tk.StringVar(value="Message from Barber Shop")
        ttk.Entry(frame, textvariable=subject_var, width=40).pack(fill=tk.X)

        ttk.Label(frame, text="Message:").pack(anchor=tk.W, pady=(10, 0))
        msg_text = tk.Text(frame, height=8, width=40)
        msg_text.pack(fill=tk.BOTH, expand=True)

        def send_message():
            if not EMAIL_AVAILABLE:
                messagebox.showerror("Error", "Email service not available.")
                return
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email
                send_email(
                    customer_email,
                    subject_var.get(),
                    msg_text.get('1.0', tk.END).strip()
                )
                messagebox.showinfo("Success", "Message sent!")
                msg_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(msg_window, text="Send", command=send_message).pack(pady=10)

    def view_customer_feedback(self):
        """View customer feedback."""
        selected = self.customers_tree.selection()
        customer_id = None
        if selected:
            item = self.customers_tree.item(selected[0])
            customer_id = item['values'][0]

        feedback_window = tk.Toplevel(self.parent)
        feedback_window.title("Customer Feedback")
        feedback_window.geometry("700x450")
        feedback_window.transient(self.parent)

        columns = ('id', 'date', 'customer', 'rating', 'comments')
        tree = ttk.Treeview(feedback_window, columns=columns, show='headings', height=15)

        tree.heading('id', text='ID')
        tree.heading('date', text='Date')
        tree.heading('customer', text='Customer')
        tree.heading('rating', text='Rating')
        tree.heading('comments', text='Comments')

        tree.column('id', width=50)
        tree.column('date', width=100)
        tree.column('customer', width=150)
        tree.column('rating', width=80)
        tree.column('comments', width=300)

        scrollbar = ttk.Scrollbar(feedback_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from education_system.university_system.modules.domain.commerce.barber.services.barber_core import FeedbackManager
            feedback_list = FeedbackManager.get_customer_feedback(customer_id=customer_id)
            for fb in feedback_list:
                tree.insert('', tk.END, values=(
                    fb['feedback_id'], fb['created_at'][:10],
                    fb.get('customer_id', ''), f"{fb['rating']}/5", fb.get('comment', '')
                ))
        except Exception as e:
            logger.error(f"Error loading feedback: {e}")

    def merge_customer_profiles(self):
        """Merge customer profiles."""
        merge_window = tk.Toplevel(self.parent)
        merge_window.title("Merge Customer Profiles")
        merge_window.geometry("400x300")
        merge_window.transient(self.parent)
        merge_window.grab_set()

        ttk.Label(merge_window, text="Merge Customer Profiles",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(merge_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Primary Customer ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        primary_var = tk.StringVar()
        ttk.Entry(frame, textvariable=primary_var, width=20).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Secondary Customer ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        secondary_var = tk.StringVar()
        ttk.Entry(frame, textvariable=secondary_var, width=20).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="(Secondary will be merged into Primary)").grid(row=2, column=0, columnspan=2, pady=10)

        def merge():
            if not primary_var.get() or not secondary_var.get():
                messagebox.showerror("Error", "Please enter both customer IDs.")
                return
            if not messagebox.askyesno("Confirm", "Are you sure you want to merge these profiles? This cannot be undone."):
                return
            try:
                from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
                CustomerManager.merge_profiles(primary_var.get(), secondary_var.get())
                messagebox.showinfo("Success", "Profiles merged!")
                merge_window.destroy()
                self._load_customers()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(merge_window, text="Merge Profiles", command=merge).pack(pady=10)

    def export_customer_list(self):
        """Export customer list."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")],
            title="Export Customer List"
        )
        if not file_path:
            return

        try:
            from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager
            customers = CustomerManager.get_all_customers()

            if file_path.endswith('.json'):
                with open(file_path, 'w') as f:
                    json.dump(customers, f, indent=2, default=str)
            else:
                with open(file_path, 'w', newline='') as f:
                    if customers:
                        writer = csv.DictWriter(f, fieldnames=customers[0].keys())
                        writer.writeheader()
                        writer.writerows(customers)

            messagebox.showinfo("Success", f"Exported {len(customers)} customers to {file_path}")
            log_activity('export', 'barber_customers', details={'count': len(customers)})

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def import_customers(self):
        """Import customers."""
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")],
            title="Import Customers"
        )
        if not file_path:
            return

        try:
            from education_system.university_system.modules.domain.commerce.barber.services.barber_core import CustomerManager

            customers = []
            if file_path.endswith('.json'):
                with open(file_path, 'r') as f:
                    customers = json.load(f)
            else:
                with open(file_path, 'r') as f:
                    reader = csv.DictReader(f)
                    customers = list(reader)

            imported = 0
            for cust in customers:
                try:
                    CustomerManager.create_profile(
                        name=cust.get('name', ''),
                        email=cust.get('email', ''),
                        phone=cust.get('phone', '')
                    )
                    imported += 1
                except Exception:
                    pass

            messagebox.showinfo("Success", f"Imported {imported} customers.")
            log_activity('import', 'barber_customers', details={'count': imported})
            self._load_customers()

        except Exception as e:
            messagebox.showerror("Error", str(e))
