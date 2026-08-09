"""Extracted ChurchManagementSystem behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from ... import *

from .payment_dialog import PaymentDialog
from ...services.payments import record_revenue
from ...services.receipts import send_receipt_email

class ChurchUiDialogsDonationDialogMixin:
    def add_donation(self):
        """Record a new donation with payment processing."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.donations.record_title"))
        dialog.geometry("450x450")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 450) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        # Pre-fill with current user info
        default_name = self.get_user_display_name()
        default_email = self.get_user_email()

        tk.Label(dialog, text=_t("church.donations.record_title"), font=("Georgia", 16, "bold"),
                bg="white", fg="#4a4a8a").pack(pady=15)

        form_frame = tk.Frame(dialog, bg="white")
        form_frame.pack(padx=30, fill=tk.X)

        # Donor info (read-only, from current user)
        tk.Label(form_frame, text=_t("church.donations.fields.donor"), bg="white", font=("Arial", 11)).grid(row=0, column=0, pady=10, sticky="e")
        donor_label = tk.Label(form_frame, text=default_name, bg="#f0f0f0", font=("Arial", 11),
                              padx=10, pady=5, anchor="w", width=25)
        donor_label.grid(row=0, column=1, pady=10, padx=10, sticky="w")

        tk.Label(form_frame, text=_t("church.donations.fields.email"), bg="white", font=("Arial", 11)).grid(row=1, column=0, pady=10, sticky="e")
        email_label = tk.Label(form_frame, text=default_email or "Not provided", bg="#f0f0f0",
                              font=("Arial", 11), padx=10, pady=5, anchor="w", width=25)
        email_label.grid(row=1, column=1, pady=10, padx=10, sticky="w")

        # Amount
        tk.Label(form_frame, text=_t("church.donations.fields.amount"), bg="white", font=("Arial", 11)).grid(row=2, column=0, pady=10, sticky="e")
        amount_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        amount_entry.grid(row=2, column=1, pady=10, padx=10)

        # Type
        tk.Label(form_frame, text=_t("church.donations.fields.type"), bg="white", font=("Arial", 11)).grid(row=3, column=0, pady=10, sticky="e")
        type_combo = ttk.Combobox(form_frame, values=["Tithe", "Offering", "Building Fund", "Missions", "Other"], width=27)
        type_combo.set("Tithe")
        type_combo.grid(row=3, column=1, pady=10, padx=10)

        # Notes
        tk.Label(form_frame, text=_t("church.donations.fields.notes"), bg="white", font=("Arial", 11)).grid(row=4, column=0, pady=10, sticky="e")
        notes_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        notes_entry.grid(row=4, column=1, pady=10, padx=10)

        def process_donation():
            try:
                amount = float(amount_entry.get())
                if amount <= 0:
                    messagebox.showerror(_t('gui.operations.campus.community.church_management.ui.dialogs.donation_dialog.dialogs.error', default="Error"), _t('gui.operations.campus.community.church_management.ui.dialogs.donation_dialog.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount!"))
                    return

                # Open payment dialog
                payment_dialog = PaymentDialog(dialog, amount, f"{type_combo.get()} Donation", self.current_user)
                dialog.wait_window(payment_dialog)

                if payment_dialog.result and payment_dialog.result.get('success'):
                    transaction_ref = payment_dialog.result['transaction_ref']
                    payment_method = payment_dialog.result['payment_method']

                    # Record donation
                    donation = {
                        'donor': default_name,
                        'donor_email': default_email,
                        'donor_id': self.current_user.get('student_id') or self.current_user.get('username'),
                        'amount': amount,
                        'type': type_combo.get(),
                        'notes': notes_entry.get(),
                        'date': datetime.now().strftime("%Y-%m-%d"),
                        'payment_method': payment_method,
                        'transaction_ref': transaction_ref
                    }
                    self.donations.append(donation)
                    self.save_data()

                    # Record to finance system
                    record_revenue(
                        student_id=self.current_user.get('student_id'),
                        amount=amount,
                        category=f"Church {type_combo.get()}",
                        transaction_ref=transaction_ref,
                        payment_method=payment_method,
                        notes=f"Donation from {default_name}"
                    )

                    # Send receipt email
                    if default_email:
                        send_receipt_email(default_email, default_name, amount,
                                         type_combo.get(), transaction_ref, payment_method)

                    # Show success with balance update if student account
                    success_msg = _t("church.donations.success_recorded", amount=f"£{amount:.2f}", receipt=transaction_ref)
                    if 'new_balance' in payment_dialog.result:
                        success_msg += _t("church.donations.new_balance", balance=f"£{payment_dialog.result['new_balance']:.2f}")

                    messagebox.showinfo(_t("church.common.success"), success_msg)
                    dialog.destroy()
                    self.show_donations()

            except ValueError:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.valid_amount"))

        tk.Button(dialog, text=_t("church.donations.continue_payment"), command=process_donation,
                 bg="#27ae60", fg="white", font=("Arial", 11, "bold"), width=20,
                 cursor="hand2").pack(pady=25)
