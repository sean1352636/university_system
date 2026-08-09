"""Barber Shop GUI - Service management feature methods."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.domains.operations.interfaces.gui.commerce.barber.common import (
    tk, ttk, messagebox, filedialog, logging,
    datetime, timedelta,
    _t, log_activity,
)

logger = logging.getLogger(__name__)


class ServicesMixin:
    """Mixin providing service management methods for BarberGUI."""

    def add_service(self):
        """Add a new service."""
        name = self.service_name_var.get().strip()
        service_type_display = self.service_type_combo.get()
        duration_str = self.service_duration_var.get().strip()
        price_str = self.service_price_var.get().strip()
        description = self.service_desc_text.get("1.0", tk.END).strip()

        if not name or not service_type_display or not price_str:
            messagebox.showerror(_t("common.error"), _t("barber.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 30
            price = float(price_str)

            service_types = self._get_service_types()
            service_type = next((k for k, v in service_types.items() if v == service_type_display), 'haircut')

            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
            service_id = ServiceManager.add_service(
                name=name, service_type=service_type, price=price,
                duration_minutes=duration, description=description
            )

            log_activity('create', 'barber_service',
                        user_id=self.current_user.get('user_id'),
                        details={'service_id': service_id})

            messagebox.showinfo(_t("common.success"), _t("barber.messages.service_added"))
            self._clear_service_form()
            self._load_services()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("barber.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def update_service(self):
        """Update selected service."""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_service"))
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]

        name = self.service_name_var.get().strip()
        service_type_display = self.service_type_combo.get()
        duration_str = self.service_duration_var.get().strip()
        price_str = self.service_price_var.get().strip()

        if not name or not price_str:
            messagebox.showerror(_t("common.error"), _t("barber.errors.fill_required"))
            return

        try:
            duration = int(duration_str) if duration_str else 30
            price = float(price_str)

            service_types = self._get_service_types()
            service_type = next((k for k, v in service_types.items() if v == service_type_display), 'haircut')

            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
            ServiceManager.update_service(
                service_id, name=name, service_type=service_type,
                price=price, duration_minutes=duration
            )

            log_activity('update', 'barber_service',
                        user_id=self.current_user.get('user_id'),
                        details={'service_id': service_id})

            messagebox.showinfo(_t("common.success"), _t("barber.messages.service_updated"))
            self._load_services()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("barber.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    # ==================== SERVICE ENHANCEMENT FUNCTIONS ====================

    def create_service_package(self):
        """Create service package."""
        pkg_window = tk.Toplevel(self.parent)
        pkg_window.title(_t('gui.operations.commerce.barber.features.services.windows.create_service_package', default="Create Service Package"))
        pkg_window.geometry("450x450")
        pkg_window.transient(self.parent)
        pkg_window.grab_set()

        ttk.Label(pkg_window, text=_t('gui.operations.commerce.barber.features.services.labels.create_service_package', default="Create Service Package"),
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(pkg_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.package_name', default="Package Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.description', default="Description:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        desc_text = tk.Text(frame, height=3, width=25)
        desc_text.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.package_price', default="Package Price (£):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(frame, textvariable=price_var, width=15).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.select_services', default="Select Services:")).grid(row=3, column=0, sticky=tk.W, pady=5)

        services_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=6, width=30)
        services_listbox.grid(row=3, column=1, pady=5)

        for svc in self.appt_service_combo['values']:
            services_listbox.insert(tk.END, svc)

        def save_package():
            if not name_var.get().strip() or not price_var.get().strip():
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), _t('gui.operations.commerce.barber.features.services.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields."))
                return
            try:
                selected_indices = services_listbox.curselection()
                service_ids = []
                for idx in selected_indices:
                    svc_str = services_listbox.get(idx)
                    service_ids.append(int(svc_str.split(':')[0]))

                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServicePackageManager
                ServicePackageManager.create_package(
                    name=name_var.get().strip(),
                    description=desc_text.get('1.0', tk.END).strip(),
                    price=float(price_var.get()),
                    service_ids=service_ids
                )
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.services.dialogs.package_created', default="Package created!"))
                pkg_window.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

        ttk.Button(pkg_window, text=_t('gui.operations.commerce.barber.features.services.buttons.create_package', default="Create Package"), command=save_package).pack(pady=10)

    def set_service_availability(self):
        """Set service availability."""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.services.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.services.dialogs.please_select_a_service', default="Please select a service."))
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]
        service_name = item['values'][1]

        avail_window = tk.Toplevel(self.parent)
        avail_window.title(f"Availability - {service_name}")
        avail_window.geometry("400x350")
        avail_window.transient(self.parent)
        avail_window.grab_set()

        ttk.Label(avail_window, text=f"Set Availability for {service_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(avail_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.available_days', default="Available Days:")).pack(anchor=tk.W)
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_vars = {}
        for day in days:
            var = tk.BooleanVar(value=True)
            day_vars[day] = var
            ttk.Checkbutton(frame, text=day, variable=var).pack(anchor=tk.W)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.available_hours', default="Available Hours:")).pack(anchor=tk.W, pady=(10, 0))
        hours_frame = ttk.Frame(frame)
        hours_frame.pack(fill=tk.X)

        ttk.Label(hours_frame, text=_t('gui.operations.commerce.barber.features.services.labels.from', default="From:")).pack(side=tk.LEFT)
        from_combo = ttk.Combobox(hours_frame, values=self._get_time_slots(), width=8)
        from_combo.set('09:00')
        from_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(hours_frame, text=_t('gui.operations.commerce.barber.features.services.labels.to', default="To:")).pack(side=tk.LEFT, padx=(10, 0))
        to_combo = ttk.Combobox(hours_frame, values=self._get_time_slots(), width=8)
        to_combo.set('17:00')
        to_combo.pack(side=tk.LEFT, padx=5)

        def save_availability():
            try:
                available_days = [day for day, var in day_vars.items() if var.get()]
                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
                ServiceManager.set_availability(
                    service_id=service_id,
                    available_days=available_days,
                    start_time=from_combo.get(),
                    end_time=to_combo.get()
                )
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.services.dialogs.availability_updated', default="Availability updated!"))
                avail_window.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

        ttk.Button(avail_window, text=_t('gui.operations.commerce.barber.features.services.buttons.save', default="Save"), command=save_availability).pack(pady=10)

    def add_service_addon(self):
        """Add service addon."""
        addon_window = tk.Toplevel(self.parent)
        addon_window.title(_t('gui.operations.commerce.barber.features.services.windows.add_service_addon', default="Add Service Addon"))
        addon_window.geometry("400x350")
        addon_window.transient(self.parent)
        addon_window.grab_set()

        ttk.Label(addon_window, text=_t('gui.operations.commerce.barber.features.services.labels.add_service_addon', default="Add Service Addon"),
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(addon_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.addon_name', default="Addon Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=25).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.price', default="Price (£):")).grid(row=1, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        ttk.Entry(frame, textvariable=price_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.duration_min', default="Duration (min):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        duration_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=duration_var, width=10).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.for_service', default="For Service:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, values=['All Services'] + list(self.appt_service_combo['values']), width=25)
        service_combo.set('All Services')
        service_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.description', default="Description:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        desc_text = tk.Text(frame, height=3, width=25)
        desc_text.grid(row=4, column=1, pady=5)

        def save_addon():
            if not name_var.get().strip() or not price_var.get().strip():
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), _t('gui.operations.commerce.barber.features.services.dialogs.name_and_price_are_required', default="Name and price are required."))
                return
            try:
                service_id = None
                if service_combo.get() != 'All Services':
                    service_id = int(service_combo.get().split(':')[0])

                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceAddonManager
                ServiceAddonManager.add_addon(
                    name=name_var.get().strip(),
                    price=float(price_var.get()),
                    duration=int(duration_var.get()),
                    service_id=service_id,
                    description=desc_text.get('1.0', tk.END).strip()
                )
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.services.dialogs.addon_created', default="Addon created!"))
                addon_window.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

        ttk.Button(addon_window, text=_t('gui.operations.commerce.barber.features.services.buttons.save_addon', default="Save Addon"), command=save_addon).pack(pady=10)

    def duplicate_service(self):
        """Duplicate service."""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.services.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.services.dialogs.please_select_a_service_to_duplicate', default="Please select a service to duplicate."))
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
            new_id = ServiceManager.duplicate_service(service_id)
            messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), f"Service duplicated! New ID: {new_id}")
            self._load_services()
        except Exception as e:
            messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

    def archive_service(self):
        """Archive service."""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.services.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.services.dialogs.please_select_a_service_to_archive', default="Please select a service to archive."))
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]
        service_name = item['values'][1]

        if not messagebox.askyesno(_t('gui.operations.commerce.barber.features.services.dialogs.confirm', default="Confirm"), f"Archive service '{service_name}'?"):
            return

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
            ServiceManager.archive_service(service_id)
            messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.services.dialogs.service_archived', default="Service archived!"))
            self._load_services()
        except Exception as e:
            messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

    def set_seasonal_pricing(self):
        """Set seasonal pricing."""
        selected = self.services_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.services.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.services.dialogs.please_select_a_service', default="Please select a service."))
            return

        item = self.services_tree.item(selected[0])
        service_id = item['values'][0]
        service_name = item['values'][1]

        pricing_window = tk.Toplevel(self.parent)
        pricing_window.title(f"Seasonal Pricing - {service_name}")
        pricing_window.geometry("400x350")
        pricing_window.transient(self.parent)
        pricing_window.grab_set()

        ttk.Label(pricing_window, text=f"Set Seasonal Pricing for {service_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(pricing_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.season', default="Season:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        season_combo = ttk.Combobox(frame, values=['Spring', 'Summer', 'Autumn', 'Winter', 'Holiday', 'Custom'], width=15)
        season_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.start_date', default="Start Date:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        start_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=start_var, width=12).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.end_date', default="End Date:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        end_var = tk.StringVar(value=(datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=end_var, width=12).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.price_adjustment', default="Price Adjustment (%):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        adjust_var = tk.StringVar(value="10")
        ttk.Entry(frame, textvariable=adjust_var, width=10).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.services.labels.positive_increase_negative_discount', default="(Positive = increase, Negative = discount)")).grid(row=4, column=0, columnspan=2, pady=5)

        def save_pricing():
            try:
                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
                ServiceManager.set_seasonal_pricing(
                    service_id=service_id,
                    season=season_combo.get(),
                    start_date=start_var.get(),
                    end_date=end_var.get(),
                    adjustment_percent=float(adjust_var.get())
                )
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.services.dialogs.seasonal_pricing_set', default="Seasonal pricing set!"))
                pricing_window.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

        ttk.Button(pricing_window, text=_t('gui.operations.commerce.barber.features.services.buttons.save', default="Save"), command=save_pricing).pack(pady=10)

    def view_service_popularity(self):
        """View service popularity."""
        pop_window = tk.Toplevel(self.parent)
        pop_window.title(_t('gui.operations.commerce.barber.features.services.windows.service_popularity', default="Service Popularity"))
        pop_window.geometry("600x400")
        pop_window.transient(self.parent)

        columns = ('rank', 'service', 'bookings', 'revenue', 'avg_rating')
        tree = ttk.Treeview(pop_window, columns=columns, show='headings', height=15)

        tree.heading('rank', text=_t('gui.operations.commerce.barber.features.services.headings.rank', default='Rank'))
        tree.heading('service', text=_t('gui.operations.commerce.barber.features.services.headings.service', default='Service'))
        tree.heading('bookings', text=_t('gui.operations.commerce.barber.features.services.headings.bookings', default='Bookings'))
        tree.heading('revenue', text=_t('gui.operations.commerce.barber.features.services.headings.revenue', default='Revenue'))
        tree.heading('avg_rating', text=_t('gui.operations.commerce.barber.features.services.headings.avg_rating', default='Avg Rating'))

        tree.column('rank', width=50)
        tree.column('service', width=200)
        tree.column('bookings', width=100)
        tree.column('revenue', width=120)
        tree.column('avg_rating', width=100)

        scrollbar = ttk.Scrollbar(pop_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import AnalyticsManager
            popularity = AnalyticsManager.get_service_popularity()
            for i, svc in enumerate(popularity, 1):
                tree.insert('', tk.END, values=(
                    i, svc['name'], svc['booking_count'],
                    f"£{svc['total_revenue']:.2f}", f"{svc['avg_rating']:.1f}/5"
                ))
        except Exception as e:
            logger.error(f"Error loading popularity: {e}")

    def reorder_services(self):
        """Reorder services display order."""
        reorder_window = tk.Toplevel(self.parent)
        reorder_window.title(_t('gui.operations.commerce.barber.features.services.windows.reorder_services', default="Reorder Services"))
        reorder_window.geometry("400x450")
        reorder_window.transient(self.parent)
        reorder_window.grab_set()

        ttk.Label(reorder_window, text=_t('gui.operations.commerce.barber.features.services.labels.drag_to_reorder_services', default="Drag to Reorder Services"),
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        listbox = tk.Listbox(reorder_window, height=15, width=40)
        listbox.pack(padx=20, pady=10)

        for svc in self.appt_service_combo['values']:
            listbox.insert(tk.END, svc)

        btn_frame = ttk.Frame(reorder_window)
        btn_frame.pack(pady=5)

        def move_up():
            idx = listbox.curselection()
            if idx and idx[0] > 0:
                item = listbox.get(idx[0])
                listbox.delete(idx[0])
                listbox.insert(idx[0] - 1, item)
                listbox.selection_set(idx[0] - 1)

        def move_down():
            idx = listbox.curselection()
            if idx and idx[0] < listbox.size() - 1:
                item = listbox.get(idx[0])
                listbox.delete(idx[0])
                listbox.insert(idx[0] + 1, item)
                listbox.selection_set(idx[0] + 1)

        ttk.Button(btn_frame, text=_t('gui.operations.commerce.barber.features.services.buttons.move_up', default="Move Up"), command=move_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.operations.commerce.barber.features.services.buttons.move_down', default="Move Down"), command=move_down).pack(side=tk.LEFT, padx=5)

        def save_order():
            try:
                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import ServiceManager
                order = []
                for i in range(listbox.size()):
                    svc_str = listbox.get(i)
                    service_id = int(svc_str.split(':')[0])
                    order.append((service_id, i + 1))
                ServiceManager.update_display_order(order)
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.services.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.services.dialogs.order_saved', default="Order saved!"))
                reorder_window.destroy()
                self._load_services()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.services.dialogs.error', default="Error"), str(e))

        ttk.Button(reorder_window, text=_t('gui.operations.commerce.barber.features.services.buttons.save_order', default="Save Order"), command=save_order).pack(pady=10)
