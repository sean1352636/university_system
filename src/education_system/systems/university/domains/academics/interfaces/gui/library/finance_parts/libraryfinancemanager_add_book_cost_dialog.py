"""Methods add_book_cost_dialog through create_overview_chart."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LibraryFinanceManager:
    def add_book_cost_dialog(self):
        """Dialog to add book cost information"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.windows.add_book_cost', default="Add Book Cost"))
        dialog.geometry("450x400")
        dialog.transient(self.root)

        fields = [
            ("Book ID:", tk.StringVar()),
            ("Purchase Price (£):", tk.StringVar()),
            ("Purchase Date (YYYY-MM-DD):", tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))),
            ("Supplier:", tk.StringVar()),
            ("Quantity:", tk.StringVar(value="1"))
        ]

        entries = {}
        for i, (label, var) in enumerate(fields):
            tk.Label(dialog, text=label, font=('Arial', 10)).grid(row=i, column=0, padx=10, pady=10, sticky='e')
            ttk.Entry(dialog, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=10)
            entries[label] = var

        def add():
            book_id = entries["Book ID:"].get().strip()
            price_str = entries["Purchase Price (£):"].get().strip()
            date = entries["Purchase Date (YYYY-MM-DD):"].get().strip()
            supplier = entries["Supplier:"].get().strip()
            qty_str = entries["Quantity:"].get().strip()

            if not book_id or not price_str:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.please_fill_required_fields', default="Please fill required fields."), parent=dialog)
                return

            try:
                price = float(price_str)
                qty = int(qty_str) if qty_str else 1

                if price < 0 or qty < 1:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.price_and_quantity_must_be_positive', default="Price and quantity must be positive."), parent=dialog)
                    return

                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ?
                    WHERE book_id = ?
                ''', (price, date, supplier, qty, book_id))

                if cursor.rowcount == 0:
                    messagebox.showerror(_("common.error"), f"Book ID {book_id} not found.", parent=dialog)
                    conn.close()
                    return

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.book_cost_information_added', default="Book cost information added."), parent=dialog)
                dialog.destroy()
                self.load_book_costs()

            except ValueError:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.please_enter_valid_numbers', default="Please enter valid numbers."), parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to add book cost:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.buttons.add_cost_info', default="Add Cost Info"), command=add, bg=self.colors['success'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).grid(row=len(fields), column=0, columnspan=2, pady=20)

    def edit_book_cost_dialog(self):
        """Dialog to edit book cost information"""
        selection = self.costs_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.no_selection', default="No Selection"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.please_select_a_book_to_edit', default="Please select a book to edit."))
            return

        values = self.costs_tree.item(selection[0])['values']
        book_id = values[0]
        current_price = float(str(values[4]).replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.windows.edit_book_cost', default="Edit Book Cost"))
        dialog.geometry("450x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Book ID: {book_id}", font=('Arial', 11, 'bold')).pack(pady=10)

        fields = [
            ("Purchase Price (£):", tk.StringVar(value=str(current_price))),
            ("Purchase Date (YYYY-MM-DD):", tk.StringVar(value=str(values[5]) if values[5] != 'N/A' else '')),
            ("Supplier:", tk.StringVar(value=str(values[6]) if values[6] != 'N/A' else '')),
            ("Quantity:", tk.StringVar(value=str(values[7])))
        ]

        entries = {}
        for label, var in fields:
            frame = tk.Frame(dialog)
            frame.pack(fill='x', padx=10, pady=5)
            tk.Label(frame, text=label, font=('Arial', 10), width=25, anchor='w').pack(side='left')
            ttk.Entry(frame, textvariable=var, width=25).pack(side='left', padx=5)
            entries[label] = var

        def update():
            price_str = entries["Purchase Price (£):"].get().strip()
            date = entries["Purchase Date (YYYY-MM-DD):"].get().strip()
            supplier = entries["Supplier:"].get().strip()
            qty_str = entries["Quantity:"].get().strip()

            try:
                price = float(price_str)
                qty = int(qty_str)

                if price < 0 or qty < 1:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.price_and_quantity_must_be_positive', default="Price and quantity must be positive."), parent=dialog)
                    return

                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ?
                    WHERE book_id = ?
                ''', (price, date, supplier, qty, book_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.book_cost_updated', default="Book cost updated."), parent=dialog)
                dialog.destroy()
                self.load_book_costs()

            except ValueError:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.please_enter_valid_numbers', default="Please enter valid numbers."), parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to update:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.buttons.update_cost', default="Update Cost"), command=update, bg=self.colors['warning'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).pack(pady=20)

    def show_cost_analysis(self):
        """Show book cost analysis"""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) as total_books,
                       SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)) as total_cost,
                       AVG(COALESCE(purchase_price, 0)) as avg_price,
                       MAX(COALESCE(purchase_price, 0)) as max_price,
                       MIN(COALESCE(purchase_price, 0)) as min_price
                FROM books
            ''')

            stats = cursor.fetchone()
            conn.close()

            total_books, total_cost, avg_price, max_price, min_price = stats

            report = f"""
BOOK COST ANALYSIS
{'='*60}

SUMMARY:
  Total Books in Collection:  {total_books:,}
  Total Investment:           £{total_cost or 0:,.2f}
  Average Book Price:         £{avg_price or 0:,.2f}
  Most Expensive Book:        £{max_price or 0:,.2f}
  Least Expensive Book:       £{min_price or 0:,.2f}

{'='*60}
"""
            messagebox.showinfo(_t('gui.academics.library.finance_parts.libraryfinancemanager_add_book_cost_dialog.dialogs.cost_analysis', default="Cost Analysis"), report)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate analysis:\n{str(e)}")

    def refresh_overview(self):
        """Refresh the overview dashboard"""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT SUM(fine_amount) FROM book_loans WHERE fine_amount >= 0.01')
            outstanding = cursor.fetchone()[0] or 0.0

            cursor.execute('''
                SELECT SUM(pa.amount)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')
            ''')
            this_month = cursor.fetchone()[0] or 0.0

            cursor.execute('''
                SELECT SUM(pa.amount)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND strftime('%Y', p.payment_date) = strftime('%Y', 'now')
            ''')
            ytd_revenue = cursor.fetchone()[0] or 0.0

            cursor.execute('SELECT SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)) FROM books')
            book_investment = cursor.fetchone()[0] or 0.0

            # Calculate total refunds from unified_refunds table
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM unified_refunds WHERE source_type = 'library'")
                total_refunds = cursor.fetchone()[0] or 0.0
            except Exception:
                total_refunds = 0.0  # Table might not exist yet

            conn.close()

            if hasattr(self, 'outstanding_fines_label'):
                self.outstanding_fines_label.config(text=f"£{outstanding:,.2f}")
            if hasattr(self, 'collected_this_month_label'):
                self.collected_this_month_label.config(text=f"£{this_month:,.2f}")
            if hasattr(self, 'total_revenue_ytd_label'):
                self.total_revenue_ytd_label.config(text=f"£{ytd_revenue:,.2f}")
            if hasattr(self, 'total_refunds_label'):
                self.total_refunds_label.config(text=f"£{total_refunds:,.2f}")
            if hasattr(self, 'book_investment_label'):
                self.book_investment_label.config(text=f"£{book_investment:,.2f}")

            self.create_overview_chart(outstanding, this_month, ytd_revenue, book_investment)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to refresh overview:\n{str(e)}")

    def create_overview_chart(self, outstanding, this_month, ytd, investment):
        """Create overview visualization"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            for widget in self.overview_chart_frame.winfo_children():
                widget.destroy()

            fig = Figure(figsize=(10, 6), dpi=100)

            ax1 = fig.add_subplot(1, 2, 1)
            categories = ['Outstanding Fines', 'Collected (Month)', 'YTD Revenue', 'Book Investment']
            values = [outstanding, this_month, ytd, investment]
            colors = [self.colors['danger'], self.colors['success'], self.colors['info'], self.colors['library']]

            filtered_data = [(cat, val, col) for cat, val, col in zip(categories, values, colors) if val > 0]

            if filtered_data:
                cats, vals, cols = zip(*filtered_data)
                ax1.pie(vals, labels=cats, autopct='%1.1f%%', colors=cols, startangle=90)
                ax1.set_title('Library Financial Overview', fontsize=12, fontweight='bold')
            else:
                ax1.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)

            ax2 = fig.add_subplot(1, 2, 2)
            x_pos = range(len(categories))
            ax2.bar(x_pos, values, color=colors)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(categories, rotation=45, ha='right', fontsize=9)
            ax2.set_ylabel('Amount (£)', fontweight='bold')
            ax2.set_title('Financial Metrics Comparison', fontsize=12, fontweight='bold')

            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.overview_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            print(f"Error creating overview chart: {e}")
