"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiPagesDonationsMixin:
    def show_donations(self):
        """Display donation management interface."""
        self.clear_content()

        title = tk.Label(
            self.content_frame,
            text=_t("church.donations.title"),
            font=("Georgia", 24, "bold"),
            bg="white",
            fg="#4a4a8a"
        )
        title.pack(pady=20)

        # Total donations
        total = sum(d['amount'] for d in self.donations)
        tk.Label(
            self.content_frame,
            text=_t("church.donations.total_donations", amount=f"£{total:,.2f}"),
            font=("Arial", 18, "bold"),
            bg="white",
            fg="#27ae60"
        ).pack()

        btn_frame = tk.Frame(self.content_frame, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text=_t("church.donations.record_donation"), command=self.add_donation,
                  bg="#27ae60", fg="white", font=("Arial", 10), cursor="hand2").pack(side=tk.LEFT, padx=5)

        # Donations list
        columns = ("ID", "Donor", "Amount", "Date", "Type", "Payment Method")
        self.donation_tree = ttk.Treeview(self.content_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.donation_tree.heading(col, text=col)
            self.donation_tree.column(col, width=120)

        for i, donation in enumerate(self.donations, 1):
            self.donation_tree.insert("", tk.END, values=(
                i, donation['donor'], f"£{donation['amount']:,.2f}",
                donation['date'], donation['type'], donation.get('payment_method', 'Cash')
            ))

        self.donation_tree.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
