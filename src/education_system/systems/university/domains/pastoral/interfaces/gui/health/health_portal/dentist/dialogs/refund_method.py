from .. import *  # shared compatibility dependencies

class RefundMethodDialogMixin:
        def _show_refund_method_dialog(self, amount: float, user_id: str) -> Optional[str]:
            """Show refund method selection dialog."""
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.labels.select_refund_method"))
            dialog.geometry("450x400")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'method': None}

            # Refund info frame
            info_frame = ttk.LabelFrame(dialog, text=_t("dentist.labels.refund_details"), padding="10")
            info_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(info_frame, text=f"User ID: {user_id}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
                     font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

            # Student account balance
            balance = self._get_student_account_balance_by_user(user_id)
            if balance is not None:
                ttk.Label(info_frame, text=f"Current Account Balance: GBP {balance:.2f}").pack(
                    anchor=tk.W, pady=(5, 0))
                ttk.Label(info_frame, text=f"Balance After Refund: GBP {balance + amount:.2f}",
                         foreground='green').pack(anchor=tk.W)

            # Refund method selection
            method_frame = ttk.LabelFrame(dialog, text=_t("dentist.labels.select_refund_method"), padding="10")
            method_frame.pack(fill=tk.X, padx=10, pady=10)

            def select_method(method):
                result['method'] = method
                dialog.destroy()

            # Cash button
            ttk.Button(method_frame, text=_t("dentist.btn.cash"), width=30,
                      command=lambda: select_method('Cash')).pack(pady=5)

            # Card button
            ttk.Button(method_frame, text=_t("dentist.labels.card_original"), width=30,
                      command=lambda: select_method('Card')).pack(pady=5)

            # Student Account button
            ttk.Button(method_frame, text=_t("dentist.btn.student_finance"), width=30,
                      command=lambda: select_method('Student Account')).pack(pady=5)

            # Cancel button
            ttk.Button(dialog, text=_t("dentist.btn.cancel"), command=dialog.destroy).pack(pady=10)

            dialog.wait_window()
            return result['method']
