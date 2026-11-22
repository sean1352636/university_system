from .. import *  # shared compatibility dependencies
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import make_toplevel

class PaymentMethodDialogMixin:
        def _show_payment_dialog(self, amount: float, description: str) -> Optional[str]:
            """Show payment method selection dialog. Returns payment method or None if cancelled."""
            dialog = make_toplevel(self.root)
            dialog.title(_t("dentist.labels.select_payment_method"))
            dialog.geometry("400x350")
            dialog.transient(self.root)
            dialog.grab_set()

            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
            y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

            result = {'method': None}

            # Payment info frame
            info_frame = ttk.LabelFrame(dialog, text=_t("dentist.btn.payment_details"), padding="10")
            info_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(info_frame, text=f"Description: {description}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Amount Due: GBP {amount:.2f}", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

            # Student account balance
            balance = self._get_student_account_balance()
            if balance is not None:
                ttk.Label(info_frame, text=f"Student Account Balance: GBP {balance:.2f}").pack(anchor=tk.W, pady=(5, 0))
                if balance < amount:
                    ttk.Label(info_frame, text=_t("dentist.labels.insufficient_funds"), foreground='red').pack(anchor=tk.W)

            # Payment method selection
            method_frame = ttk.LabelFrame(dialog, text=_t("dentist.labels.select_payment_method"), padding="10")
            method_frame.pack(fill=tk.X, padx=10, pady=10)

            payment_var = tk.StringVar(value="")

            def select_method(method):
                result['method'] = method
                dialog.destroy()

            # Cash button
            cash_btn = ttk.Button(method_frame, text=_t("dentist.btn.cash"), width=20,
                                 command=lambda: select_method('cash'))
            cash_btn.pack(pady=5)

            # Card button
            card_btn = ttk.Button(method_frame, text=_t("dentist.btn.card"), width=20,
                                 command=lambda: select_method('card'))
            card_btn.pack(pady=5)

            # Student Account button
            account_btn = ttk.Button(method_frame, text=_t("dentist.btn.student_account"), width=20,
                                    command=lambda: select_method('student_account'))
            account_btn.pack(pady=5)

            # Disable student account if insufficient funds
            if balance is None or balance < amount:
                account_btn.config(state='disabled')

            # Cancel button
            ttk.Button(dialog, text=_t("dentist.btn.cancel"), command=dialog.destroy).pack(pady=10)

            dialog.wait_window()
            return result['method']
