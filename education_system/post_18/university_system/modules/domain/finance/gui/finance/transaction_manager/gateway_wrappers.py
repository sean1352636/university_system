"""Third-party payment gateway GUI wrappers (Stripe, QR)"""

from education_system.post_18.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, _, process_stripe_payment, generate_qr_payment_code,
)


class GatewayWrappersMixin:
    """Mixin for third-party payment gateway UIs"""

    def gui_process_stripe_payment(self):
        """GUI wrapper for process_stripe_payment"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.stripe_payment_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.stripe_details_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Amount
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Payment method ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.payment_method_id_label")).pack(anchor='w', pady=5)
        payment_method_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=payment_method_var).pack(anchor='w', fill='x', pady=5)

        def process_payment():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                payment_method_id = payment_method_var.get().strip()

                if not all([student_id, amount > 0, payment_method_id]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                result = process_stripe_payment(student_id, amount, payment_method_id)
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.stripe_payment_success", transaction_id=result.get('id', 'N/A')))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.stripe_payment_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_process_payment"), command=process_payment).pack(pady=20)


    def gui_generate_qr_payment_code(self):
        """GUI wrapper for generate_qr_payment_code"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.qr_payment_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.payment_details_frame"), padding=20)
        form_frame.pack(fill='x', padx=20, pady=20)

        # Student ID
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label")).pack(anchor='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=student_id_var).pack(anchor='w', fill='x', pady=5)

        # Amount
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.amount_label")).pack(anchor='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var).pack(anchor='w', fill='x', pady=5)

        # Description
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.description_label")).pack(anchor='w', pady=5)
        desc_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=desc_var).pack(anchor='w', fill='x', pady=5)

        # QR Code display
        qr_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.qr_code_frame"), padding=20)
        qr_frame.pack(fill='both', expand=True, padx=20, pady=10)

        qr_label = ttk.Label(qr_frame, text=_("finance_gui.transaction_manager.qr_placeholder"))
        qr_label.pack(pady=20)

        def generate_qr():
            try:
                student_id = student_id_var.get().strip()
                amount = float(amount_var.get())
                description = desc_var.get().strip()

                if not all([student_id, amount > 0]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_amount_required"))
                    return

                qr_code_data = generate_qr_payment_code(student_id, amount, description)
                qr_label.config(text=_("finance_gui.transaction_manager.qr_generated", student_id=student_id, amount=amount))
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.qr_success"))

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.qr_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.transaction_manager.btn_generate_qr"), command=generate_qr).pack(pady=20)
