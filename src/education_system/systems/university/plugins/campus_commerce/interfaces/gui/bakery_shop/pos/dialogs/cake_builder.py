
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class CakeBuilderDialogMixin:
    def _cakebuilder_open(self):
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.dialogs.cake_builder.windows.cake_builder', default="Cake Builder"))
        d.geometry("520x560"); d.transient(self.root); d.grab_set()
        bg = self.colors["background"]; d.configure(bg=bg)

        fields = {}
        def row(label, widget, r):
            tk.Label(d, text=label, bg=bg).grid(row=r, column=0,
                                                 padx=8, pady=6, sticky="e")
            widget.grid(row=r, column=1, padx=8, pady=6, sticky="w")

        size_v = tk.StringVar(value=self.CAKE_SIZES[0])
        row("Size:", ttk.Combobox(d, textvariable=size_v,
                                  values=self.CAKE_SIZES, state="readonly",
                                  width=28), 0)
        fields["size"] = size_v
        flav_v = tk.StringVar(value=self.CAKE_FLAVOURS[0])
        row("Flavour:", ttk.Combobox(d, textvariable=flav_v,
                                     values=self.CAKE_FLAVOURS, state="readonly",
                                     width=28), 1)
        fields["flavour"] = flav_v
        fill_v = tk.StringVar(value=self.CAKE_FILLINGS[0])
        row("Filling:", ttk.Combobox(d, textvariable=fill_v,
                                     values=self.CAKE_FILLINGS, state="readonly",
                                     width=28), 2)
        fields["filling"] = fill_v
        msg_v = tk.StringVar()
        row("Message on cake:", tk.Entry(d, textvariable=msg_v, width=30), 3)
        fields["message"] = msg_v
        diet_v = tk.StringVar()
        row("Dietary (eg. gluten-free):",
            tk.Entry(d, textvariable=diet_v, width=30), 4)
        fields["dietary"] = diet_v
        date_v = tk.StringVar(value=(datetime.now() + timedelta(days=3)
                                     ).strftime("%Y-%m-%d"))
        row("Collection date:",
            tk.Entry(d, textvariable=date_v, width=14), 5)
        fields["date"] = date_v
        email_v = tk.StringVar()
        row("Email:", tk.Entry(d, textvariable=email_v, width=30), 6)
        fields["email"] = email_v
        phone_v = tk.StringVar()
        row("Phone:", tk.Entry(d, textvariable=phone_v, width=20), 7)
        fields["phone"] = phone_v

        # Auto-quote based on size keyword
        def quote():
            sz = size_v.get().lower()
            if "serves 50" in sz: return 95.00
            if "serves 25" in sz: return 55.00
            if "serves 20" in sz: return 45.00
            if "serves 12" in sz: return 32.00
            return 22.00
        quote_lbl = tk.Label(d, text="", bg=bg, font=("Arial", 13, "bold"),
                             fg=self.colors["primary"])
        quote_lbl.grid(row=8, column=0, columnspan=2, pady=6)
        def refresh_quote(*_):
            quote_lbl.config(text=f"Auto-quoted price: £{quote():.2f}")
        size_v.trace_add("write", refresh_quote)
        refresh_quote()

        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            qprice = quote()
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_custom_orders "
                    "(user, cake_type, size, flavours, message_on_cake, "
                    "dietary_requirements, collection_date, contact_email, "
                    "contact_phone, quoted_price, status, created_at, "
                    "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self.current_user or "guest",
                     fields["filling"].get() and "Custom" or "Custom",
                     fields["size"].get(),
                     f"{fields['flavour'].get()} / {fields['filling'].get()}",
                     fields["message"].get(),
                     fields["dietary"].get(),
                     fields["date"].get(),
                     fields["email"].get(),
                     fields["phone"].get(),
                     qprice, "requested", now, now))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.dialogs.cake_builder.dialogs.cake', default="Cake"),
                                f"Order saved. Quoted £{qprice:.2f}.",
                                parent=d)
            d.destroy(); self._cakebuilder_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.cake_builder.buttons.submit_order', default="✅ Submit order"), command=save,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=8).grid(row=9, column=0, columnspan=2, pady=12)

