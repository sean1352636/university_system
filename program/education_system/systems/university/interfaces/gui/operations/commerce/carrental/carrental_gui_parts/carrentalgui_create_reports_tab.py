"""Methods create_reports_tab through book_rental."""

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarRentalGUI:
    def create_reports_tab(self):
        """Create the reports and analytics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.reports"))

        # Left panel - Report options
        left_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.report_options"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Button(left_frame, text=_t("carrental.btn.fleet_summary"),
                   command=self.show_fleet_summary, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.revenue_report"),
                   command=self.show_revenue_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.popular_vehicles"),
                   command=self.show_popular_vehicles, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.generate_admin_report"),
                   command=self.generate_admin_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("carrental.btn.email_admin_report"),
                   command=self.email_admin_report, width=25).pack(pady=5)

        # Right panel - Report display
        right_frame = ttk.LabelFrame(tab, text=_t("carrental.labels.report_output"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(right_frame, wrap=tk.WORD, font=('Courier', 10))
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_categories(self):
        """Get vehicle categories"""
        return VEHICLE_CATEGORIES

    def _load_vehicles(self):
        """Load vehicles into the treeview"""
        for item in self.vehicles_tree.get_children():
            self.vehicles_tree.delete(item)

        category = self.vehicle_category_filter.get()
        vehicles = VehicleManager.get_all_vehicles()

        for v in vehicles:
            if category == 'All' or v['category'] == category:
                self.vehicles_tree.insert('', tk.END, values=(
                    v['vehicle_id'], v['registration_number'], v['make'],
                    v['model'], v['category'], f"£{v['daily_rate']:.2f}", v['status']
                ))

        # Also update available vehicles for rentals
        self._load_available_vehicles()

    def _load_available_vehicles(self):
        """Load available vehicles for rental tab"""
        for item in self.available_tree.get_children():
            self.available_tree.delete(item)

        vehicles = VehicleManager.get_available_vehicles()
        for v in vehicles:
            self.available_tree.insert('', tk.END, values=(
                v['vehicle_id'],
                f"{v['make']} {v['model']} ({v['registration_number']})",
                v['category'],
                f"£{v['daily_rate']:.2f}"
            ))

    def _load_rentals(self):
        """Load rentals data"""
        pass  # Rentals are loaded in _load_active_rentals

    def _load_active_rentals(self):
        """Load active rentals into the returns tab"""
        for item in self.active_rentals_tree.get_children():
            self.active_rentals_tree.delete(item)

        # Respect the status picker (defaults to active + reserved)
        selected = 'Active + Reserved'
        if hasattr(self, 'rental_status_filter'):
            selected = self.rental_status_filter.get() or 'Active + Reserved'

        if selected == 'Active + Reserved':
            rentals = RentalManager.get_rentals_by_status('active')
            rentals += RentalManager.get_rentals_by_status('reserved')
        elif selected == 'All':
            rentals = RentalManager.get_rentals_by_status()
        else:
            rentals = RentalManager.get_rentals_by_status(selected)

        for r in rentals:
            self.active_rentals_tree.insert('', tk.END, values=(
                r['rental_id'], r['rental_number'], r['customer_name'],
                f"{r['make']} {r['model']}", r['return_date'],
                f"£{r['total_amount']:.2f}"
            ))

    def add_vehicle(self):
        """Add a new vehicle to the fleet"""
        try:
            reg = self.vehicle_entries['registration'].get().strip()
            make = self.vehicle_entries['make'].get().strip()
            model = self.vehicle_entries['model'].get().strip()
            year = self.vehicle_entries['year'].get().strip()
            daily_rate = self.vehicle_entries['daily_rate'].get().strip()
            category = self.vehicle_category_combo.get()

            if not all([reg, make, model, year, daily_rate, category]):
                messagebox.showerror(_t("common.error"), _t("carrental.errors.fill_required"))
                return

            vehicle_id = VehicleManager.add_vehicle(
                registration_number=reg,
                make=make,
                model=model,
                year=int(year),
                category=category,
                daily_rate=float(daily_rate),
                color=self.vehicle_entries['color'].get().strip() or None,
                seats=int(self.vehicle_entries['seats'].get() or 5),
                mileage=int(self.vehicle_entries['mileage'].get() or 0),
                transmission=self.vehicle_transmission_combo.get(),
                fuel_type=self.vehicle_fuel_combo.get()
            )

            if vehicle_id:
                messagebox.showinfo(_t("common.success"),
                    _t("carrental.messages.vehicle_added").format(reg=reg))
                self._clear_vehicle_form()
                self._load_vehicles()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.add_failed"))
        except ValueError:
            messagebox.showerror(_t("common.error"), _t("carrental.errors.invalid_input"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def update_vehicle(self):
        """Update selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_vehicle_selected"))
            return

        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]

        try:
            updates = {}
            if self.vehicle_entries['daily_rate'].get():
                updates['daily_rate'] = float(self.vehicle_entries['daily_rate'].get())
            if self.vehicle_entries['mileage'].get():
                updates['mileage'] = int(self.vehicle_entries['mileage'].get())
            if self.vehicle_entries['color'].get():
                updates['color'] = self.vehicle_entries['color'].get()

            if VehicleManager.update_vehicle(vehicle_id, **updates):
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.vehicle_updated"))
                self._load_vehicles()
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.update_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _clear_vehicle_form(self):
        """Clear the vehicle form"""
        for entry in self.vehicle_entries.values():
            entry.delete(0, tk.END)
        self.vehicle_category_combo.set('')
        self.vehicle_transmission_combo.set('automatic')
        self.vehicle_fuel_combo.set('petrol')

    def _on_vehicle_select(self, event):
        """Handle vehicle selection"""
        selected = self.vehicles_tree.selection()
        if selected:
            values = self.vehicles_tree.item(selected[0])['values']
            self.vehicle_entries['registration'].delete(0, tk.END)
            self.vehicle_entries['registration'].insert(0, values[1])
            self.vehicle_entries['make'].delete(0, tk.END)
            self.vehicle_entries['make'].insert(0, values[2])
            self.vehicle_entries['model'].delete(0, tk.END)
            self.vehicle_entries['model'].insert(0, values[3])
            self.vehicle_category_combo.set(values[4])
            self.vehicle_entries['daily_rate'].delete(0, tk.END)
            self.vehicle_entries['daily_rate'].insert(0, values[5].replace('$', ''))

    def _select_vehicle_for_rental(self, event):
        """Select vehicle for rental booking"""
        selected = self.available_tree.selection()
        if selected:
            values = self.available_tree.item(selected[0])['values']
            self.selected_vehicle_id = values[0]
            self.selected_vehicle_var.set(f"{values[1]} - {values[3]}/day")
            self._calculate_rental_cost()

    def _calculate_rental_cost(self):
        """Calculate estimated rental cost"""
        if not self.selected_vehicle_id:
            return

        try:
            vehicle = VehicleManager.get_vehicle(self.selected_vehicle_id)
            if not vehicle:
                return

            pickup_date = datetime.strptime(self.rental_entries['pickup_date'].get(), '%Y-%m-%d')
            return_date = datetime.strptime(self.rental_entries['return_date'].get(), '%Y-%m-%d')
            days = max(1, (return_date - pickup_date).days)

            total = vehicle['daily_rate'] * days
            self.rental_cost_var.set(f"£{total:.2f} ({days} days)")
        except Exception:
            pass

    def _clear_rental_form(self):
        """Clear the rental form"""
        for entry in self.rental_entries.values():
            entry.delete(0, tk.END)
        self.selected_vehicle_id = None
        self.selected_vehicle_var.set("")
        self.rental_cost_var.set("£0.00")

        # Reset default dates
        today = datetime.now()
        self.rental_entries['pickup_date'].insert(0, today.strftime('%Y-%m-%d'))
        self.rental_entries['pickup_time'].insert(0, '10:00')
        tomorrow = today + timedelta(days=1)
        self.rental_entries['return_date'].insert(0, tomorrow.strftime('%Y-%m-%d'))
        self.rental_entries['return_time'].insert(0, '10:00')

    def book_rental(self):
        """Book a new rental"""
        if not self.selected_vehicle_id:
            messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_vehicle_selected"))
            return

        try:
            # Use stored customer details from current user
            customer_name = self.rental_customer_name
            customer_email = self.rental_customer_email
            license_number = self.rental_entries['license_number'].get().strip()
            pickup_date = self.rental_entries['pickup_date'].get().strip()
            return_date = self.rental_entries['return_date'].get().strip()

            if not all([license_number, pickup_date, return_date]):
                messagebox.showerror(_t("common.error"), _t("carrental.errors.fill_required"))
                return

            vehicle = VehicleManager.get_vehicle(self.selected_vehicle_id)

            # Get customer_id from current user
            customer_id = (self.current_user.get('student_id') or
                          self.current_user.get('username') or
                          self.current_user.get('id') or 'GUEST')

            rental_id = RentalManager.create_rental(
                vehicle_id=self.selected_vehicle_id,
                customer_id=customer_id,
                customer_name=customer_name,
                license_number=license_number,
                pickup_date=pickup_date,
                pickup_time=self.rental_entries['pickup_time'].get() or '10:00',
                return_date=return_date,
                return_time=self.rental_entries['return_time'].get() or '10:00',
                daily_rate=vehicle['daily_rate'],
                customer_email=customer_email,
                created_by=self.current_user.get('username')
            )

            if rental_id:
                rental = RentalManager.get_rental(rental_id)
                messagebox.showinfo(_t("common.success"),
                    _t("carrental.messages.rental_booked").format(
                        rental_num=rental['rental_number'],
                        amount=rental['total_amount']
                    ))
                self._clear_rental_form()
                self.refresh_all_data()
                self.send_receipt_email(rental_id)
            else:
                messagebox.showerror(_t("common.error"), _t("carrental.errors.booking_failed"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))
