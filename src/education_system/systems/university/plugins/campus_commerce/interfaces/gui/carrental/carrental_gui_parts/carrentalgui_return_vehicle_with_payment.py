"""Methods return_vehicle_with_payment through generate_admin_report."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarRentalGUI:
    def return_vehicle_with_payment(self):
        """Return vehicle and process payment in one flow"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        values = self.active_rentals_tree.item(selected[0])['values']
        rental_id = values[0]
        base_amount = float(str(values[5]).replace('$', '').replace('£', ''))

        rental = RentalManager.get_rental(rental_id)
        if not rental:
            messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.carrental.carrental_gui_parts.carrentalgui_return_vehicle_with_payment.dialogs.rental_not_found', default="Rental not found"))
            return

        # Get return details from form
        try:
            return_mileage = int(self.return_mileage_entry.get() or 0)
            fuel_level = self.return_fuel_combo.get() or 'Full'
            fuel_fee = float(self.fuel_fee_entry.get() or 0)
            late_fee = float(self.late_fee_entry.get() or 0)
            damage_fee = float(self.damage_fee_entry.get() or 0)
        except ValueError:
            messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.carrental.carrental_gui_parts.carrentalgui_return_vehicle_with_payment.dialogs.invalid_fee_values', default="Invalid fee values"))
            return

        # Calculate total amount
        total_amount = base_amount + fuel_fee + late_fee + damage_fee

        # Create payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("carrental.windows.return_payment"))
        dialog.geometry("400x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Vehicle info
        ttk.Label(dialog, text=_t("carrental.labels.vehicle_return_summary"), font=('Helvetica', 14, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(dialog, padding="10")
        info_frame.pack(fill=tk.X, padx=20)

        ttk.Label(info_frame, text=f"Rental: {rental.get('rental_number', 'N/A')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Vehicle: {rental.get('make', '')} {rental.get('model', '')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Return Mileage: {return_mileage}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Fuel Level: {fuel_level}").pack(anchor=tk.W)

        # Fees breakdown
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        fees_frame = ttk.Frame(dialog, padding="10")
        fees_frame.pack(fill=tk.X, padx=20)

        ttk.Label(fees_frame, text=f"Base Rental: £{base_amount:.2f}").pack(anchor=tk.W)
        if fuel_fee > 0:
            ttk.Label(fees_frame, text=f"Fuel Fee: £{fuel_fee:.2f}").pack(anchor=tk.W)
        if late_fee > 0:
            ttk.Label(fees_frame, text=f"Late Fee: £{late_fee:.2f}").pack(anchor=tk.W)
        if damage_fee > 0:
            ttk.Label(fees_frame, text=f"Damage Fee: £{damage_fee:.2f}").pack(anchor=tk.W)

        ttk.Label(fees_frame, text=f"TOTAL: £{total_amount:.2f}", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(10, 0))

        # Payment method
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        payment_frame = ttk.Frame(dialog, padding="10")
        payment_frame.pack(fill=tk.X, padx=20)

        ttk.Label(payment_frame, text=_t("carrental.labels.payment_method")).pack(anchor=tk.W)

        # Check student finance account balance
        student_id = rental.get('customer_id')
        balance = get_student_finance_account_balance(student_id) if student_id else None

        payment_options = ['Cash', 'Card']
        if balance is not None:
            balance_text = f"Student Account (Balance: £{balance:.2f})"
            payment_options.append(balance_text)

        payment_method_var = tk.StringVar(value=_t('gui.operations.commerce.carrental.carrental_gui_parts.carrentalgui_return_vehicle_with_payment.values.card', default='Card'))
        for option in payment_options:
            ttk.Radiobutton(payment_frame, text=option, variable=payment_method_var, value=option).pack(anchor=tk.W)

        def confirm_return_and_payment():
            method = payment_method_var.get()
            actual_method = 'finance_account' if 'Student Account' in method else method.lower()

            # Check balance for student account
            if actual_method == 'finance_account':
                if balance is None or balance < total_amount:
                    messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.carrental.carrental_gui_parts.carrentalgui_return_vehicle_with_payment.dialogs.insufficient_balance_in_student_account', default="Insufficient balance in student account"))
                    return

            # Record payment in rental system (the domain service posts to Finance;
            # a finance-account debit that is refused returns None before any local write)
            trans_id = TransactionManager.record_payment(
                rental_id=rental_id,
                customer_id=student_id,
                amount=total_amount,
                payment_method=actual_method,
                processed_by=self.current_user.get('username'),
                description=f"Car rental return - {rental.get('rental_number', '')}",
            )
            if not trans_id:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.payment_failed"))
                return

            # Complete the return
            if not RentalManager.complete_rental(
                rental_id=rental_id,
                return_mileage=return_mileage,
                fuel_level=fuel_level,
                fuel_fee=fuel_fee,
                late_fee=late_fee,
                damage_fee=damage_fee
            ):
                messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.carrental.carrental_gui_parts.carrentalgui_return_vehicle_with_payment.dialogs.failed_to_complete_return', default="Failed to complete return"))
                return

            # Send receipt email
            self.send_receipt_email(rental_id)

            messagebox.showinfo(_t("common.success"),
                f"Vehicle returned and payment of £{total_amount:.2f} processed successfully!")
            dialog.destroy()
            self.refresh_all_data()

            # Clear return form
            self.return_mileage_entry.delete(0, tk.END)
            self.return_fuel_combo.set('')
            self.fuel_fee_entry.delete(0, tk.END)
            self.fuel_fee_entry.insert(0, "0")
            self.late_fee_entry.delete(0, tk.END)
            self.late_fee_entry.insert(0, "0")
            self.damage_fee_entry.delete(0, tk.END)
            self.damage_fee_entry.insert(0, "0")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("carrental.btn.confirm_pay"), command=confirm_return_and_payment).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("carrental.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def complete_return(self):
        """Complete a vehicle return (legacy - use return_vehicle_with_payment instead)"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        try:
            return_mileage = int(self.return_mileage_entry.get() or 0)
            fuel_level = self.return_fuel_combo.get()
            fuel_fee = float(self.fuel_fee_entry.get() or 0)
            late_fee = float(self.late_fee_entry.get() or 0)
            damage_fee = float(self.damage_fee_entry.get() or 0)

            if RentalManager.complete_rental(
                rental_id=rental_id,
                return_mileage=return_mileage,
                fuel_level=fuel_level,
                fuel_fee=fuel_fee,
                late_fee=late_fee,
                damage_fee=damage_fee
            ):
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.return_completed"))
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.return_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def process_payment(self):
        """Process payment for a rental with finance integration"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        values = self.active_rentals_tree.item(selected[0])['values']
        rental_id = values[0]
        amount = float(values[5].replace('$', ''))

        rental = RentalManager.get_rental(rental_id)
        if not rental:
            return

        # Payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("carrental.labels.process_payment"))
        dialog.geometry("350x280")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Amount: £{amount:.2f}", font=('Helvetica', 12, 'bold')).pack(pady=10)

        # Check student finance account balance if available
        student_id = rental.get('customer_id')
        balance = get_student_finance_account_balance(student_id) if student_id else None
        balance_text = f" (Balance: £{balance:.2f})" if balance is not None else ""

        ttk.Label(dialog, text=_t("carrental.labels.payment_method") + ":").pack(pady=5)
        payment_options = ['cash', 'card']
        if balance is not None:
            payment_options.append(f'finance_account{balance_text}')
        payment_method = ttk.Combobox(dialog, values=payment_options, width=30)
        payment_method.set('card')
        payment_method.pack(pady=5)

        def confirm_payment():
            method = payment_method.get()
            actual_method = 'finance_account' if 'finance_account' in method else method

            # Process payment via finance account if selected
            if actual_method == 'finance_account':
                if balance is None or balance < amount:
                    messagebox.showerror(_t("common.error"),
                        _t("carrental.errors.insufficient_balance"))
                    return

            # Record payment in rental system (the domain service posts to Finance)
            trans_id = TransactionManager.record_payment(
                rental_id=rental_id,
                customer_id=student_id,
                amount=amount,
                payment_method=actual_method,
                processed_by=self.current_user.get('username')
            )

            if trans_id:
                messagebox.showinfo(_t("common.success"),
                    _t("carrental.messages.payment_processed").format(amount=amount))
                dialog.destroy()
                self.refresh_all_data()
                self.send_receipt_email(rental_id)
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.payment_failed"))

        ttk.Button(dialog, text=_t("carrental.btn.confirm_payment"),
                   command=confirm_payment).pack(pady=20)

    def cancel_rental(self):
        """Cancel a rental"""
        selected = self.active_rentals_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_rental_selected"))
            return

        rental_id = self.active_rentals_tree.item(selected[0])['values'][0]

        if messagebox.askyesno(_t("common.confirm"), _t("carrental.confirm.cancel_rental")):
            if RentalManager.cancel_rental(rental_id, "Cancelled by user"):
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.rental_cancelled"))
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.cancel_failed"))

    def send_receipt_email(self, rental_id: int):
        """Send receipt email to customer"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            rental = RentalManager.get_rental(rental_id)
            if not rental:
                return

            # Check for valid email (must contain @ symbol)
            customer_email = rental.get('customer_email')
            if not customer_email or '@' not in customer_email:
                logger.info(f"No valid email for rental {rental.get('rental_number', rental_id)} - skipping receipt")
                return

            subject = _t("carrental.email.receipt_subject").format(rental_num=rental['rental_number'])
            body = _t("carrental.email.receipt_body").format(
                customer=rental['customer_name'],
                rental_num=rental['rental_number'],
                vehicle=f"{rental['make']} {rental['model']}",
                pickup=rental['pickup_date'],
                return_date=rental['return_date'],
                amount=rental['total_amount']
            )

            send_email(customer_email, subject, body)
            logger.info(f"Receipt email sent for rental {rental['rental_number']}")
        except Exception as e:
            logger.error(f"Failed to send receipt email: {e}")

    def show_fleet_summary(self):
        """Show fleet summary report"""
        summary = ReportManager.get_fleet_summary()
        report = f"""
FLEET SUMMARY
=============

Total Vehicles: {summary.get('total_vehicles', 0)}
Available: {summary.get('available', 0)}
Currently Rented: {summary.get('rented', 0)}
In Maintenance: {summary.get('maintenance', 0)}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_revenue_report(self):
        """Show revenue report"""
        revenue = ReportManager.get_revenue_report()
        # Handle None values safely
        total_rentals = revenue.get('total_rentals') or 0
        completed_rentals = revenue.get('completed_rentals') or 0
        total_revenue = revenue.get('total_revenue') or 0
        avg_rental_value = revenue.get('avg_rental_value') or 0
        report = f"""
REVENUE REPORT
==============

Total Rentals: {total_rentals}
Completed Rentals: {completed_rentals}
Total Revenue: £{total_revenue:.2f}
Average Rental Value: £{avg_rental_value:.2f}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_popular_vehicles(self):
        """Show popular vehicles report"""
        vehicles = ReportManager.get_popular_vehicles(10)
        report = "TOP 10 VEHICLES BY RENTALS\n" + "=" * 30 + "\n\n"

        for i, v in enumerate(vehicles, 1):
            report += f"{i}. {v['make']} {v['model']} ({v['category']})\n"
            report += f"   Rentals: {v['rental_count']} | Revenue: £{v['total_revenue'] or 0:.2f}\n\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def generate_admin_report(self):
        """Generate comprehensive admin report"""
        report = ReportManager.generate_admin_report()
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)
