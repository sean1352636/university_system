
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ... import *
from ...services.payments import *
from ...services.receipts import *

class PaymentDialog(tk.Toplevel):
    """Dialog for selecting payment method and processing payment."""

    def __init__(self, parent, amount, description, current_user):
        super().__init__(parent)
        self.title(_t("church.payment.title"))
        self.geometry("450x400")
        self.configure(bg="white")
        self.resizable(False, False)
        self.transient(parent)

        self.amount = amount
        self.description = description
        self.current_user = current_user
        self.result = None
        self.student_balance = None

        # Get student identifier - use student_id if available, otherwise use username
        self.student_identifier = None
        if current_user:
            self.student_identifier = current_user.get('student_id') or current_user.get('username')

        # Get student balance if logged in
        if self.student_identifier:
            self.student_balance = get_student_account_balance(self.student_identifier)

        self.setup_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_visibility()
        self.grab_set()

    def setup_ui(self):
        # Header
        header = tk.Frame(self, bg="#4a4a8a", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="💰 " + _t("church.payment.select_method"), font=("Georgia", 16, "bold"),
                bg="#4a4a8a", fg="white").pack(pady=20)

        # Amount display
        amount_frame = tk.Frame(self, bg="white")
        amount_frame.pack(fill=tk.X, pady=20, padx=30)

        tk.Label(amount_frame, text=_t("church.payment.amount_due"), font=("Arial", 12),
                bg="white").pack(anchor="w")
        tk.Label(amount_frame, text=f"£{self.amount:.2f}", font=("Arial", 24, "bold"),
                bg="white", fg="#27ae60").pack(anchor="w")
        tk.Label(amount_frame, text=self.description, font=("Arial", 10),
                bg="white", fg="gray").pack(anchor="w")

        # Payment options
        options_frame = tk.Frame(self, bg="white")
        options_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        self.payment_var = tk.StringVar(value=_t('gui.operations.campus.community.church_management.ui.dialogs.payment_dialog.values.cash', default="cash"))

        # Cash option
        cash_frame = tk.Frame(options_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        cash_frame.pack(fill=tk.X, pady=5)
        tk.Radiobutton(cash_frame, text="💵 " + _t("church.payment.cash"), variable=self.payment_var, value="cash",
                      font=("Arial", 12), bg="#f5f5f5", activebackground="#f5f5f5",
                      cursor="hand2").pack(anchor="w", padx=15, pady=10)

        # Card option
        card_frame = tk.Frame(options_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        card_frame.pack(fill=tk.X, pady=5)
        tk.Radiobutton(card_frame, text="💳 " + _t("church.payment.card"), variable=self.payment_var, value="card",
                      font=("Arial", 12), bg="#f5f5f5", activebackground="#f5f5f5",
                      cursor="hand2").pack(anchor="w", padx=15, pady=10)

        # Student Account option (available for all logged in users)
        if self.current_user and self.student_identifier:
            account_frame = tk.Frame(options_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
            account_frame.pack(fill=tk.X, pady=5)

            account_text = "🎓 " + _t("church.payment.student_account")
            if self.student_balance is not None:
                account_text += f" ({_t('church.payment.balance', amount=f'£{self.student_balance:.2f}')})"
                if self.student_balance < self.amount:
                    account_text += " - " + _t("church.payment.insufficient")
            else:
                account_text += " (" + _t("church.payment.no_account") + ")"

            rb = tk.Radiobutton(account_frame, text=account_text, variable=self.payment_var,
                               value="student_account", font=("Arial", 12), bg="#f5f5f5",
                               activebackground="#f5f5f5", cursor="hand2")
            rb.pack(anchor="w", padx=15, pady=10)

            # Disable if no account or insufficient balance
            if self.student_balance is None or self.student_balance < self.amount:
                rb.config(state=tk.DISABLED)

        # Buttons
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(fill=tk.X, padx=30, pady=20)

        tk.Button(btn_frame, text=_t("church.payment.cancel"), command=self.destroy,
                 bg="#e74c3c", fg="white", font=("Arial", 11), width=12,
                 cursor="hand2").pack(side=tk.RIGHT)

        tk.Button(btn_frame, text=_t("church.payment.pay_now"), command=self.process_payment,
                 bg="#27ae60", fg="white", font=("Arial", 11, "bold"), width=12,
                 cursor="hand2").pack(side=tk.RIGHT, padx=10)

    def process_payment(self):
        payment_method = self.payment_var.get()
        transaction_ref = f"CHURCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if payment_method == "student_account":
            # Process through student finance account
            result = process_student_payment(self.student_identifier, self.amount, self.description, transaction_ref)

            if result.get('success'):
                self.result = {
                    'success': True,
                    'payment_method': 'Student Account',
                    'transaction_ref': transaction_ref,
                    'new_balance': result.get('new_balance')
                }
            else:
                messagebox.showerror(_t("church.payment.payment_failed"), result.get('message', _t("common.unknown_error")))
                return
        else:
            # Cash or card - just record it
            self.result = {
                'success': True,
                'payment_method': payment_method.title(),
                'transaction_ref': transaction_ref
            }

        self.destroy()
