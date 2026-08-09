"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def bulk_export(self):
    """Export search results in bulk"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.no_results_to_export"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"💾 {_t('advanced_search.bulk_export_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.export_options"), style='Title.TLabel').pack(pady=(0, 20))

    format_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.bulk_export.values.csv', default="csv"))
    formats = [
        (_t("advanced_search.bulk_operations.csv_format"), "csv"),
        (_t("advanced_search.bulk_operations.json_format"), "json"),
        (_t("advanced_search.bulk_operations.excel_format"), "xlsx"),
        (_t("advanced_search.bulk_operations.text_format"), "txt"),
    ]

    for text, value in formats:
        ttk.Radiobutton(frame, text=text, variable=format_var, value=value).pack(anchor='w', pady=2)

    def do_export():
        format_type = format_var.get()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"bulk_export_{timestamp}.{format_type}"

        try:
            if format_type == "csv":
                self.export_to_csv(filename)
            elif format_type == "json":
                self.export_to_json(filename)
            elif format_type == "txt":
                self.export_to_text(filename)
            else:
                # Excel export
                try:
                    import openpyxl
                    from openpyxl.styles import Font, Alignment, PatternFill

                    wb = openpyxl.Workbook()
                    ws = wb.active
                    ws.title = "Search Results"

                    # Get results data from tree
                    if hasattr(self, 'results_tree') and self.results_tree:
                        # Get column headers
                        headers = [self.results_tree.heading(col)['text'] for col in self.results_tree['columns']]
                        ws.append(headers)

                        # Style headers
                        for col_num, cell in enumerate(ws[1], 1):
                            cell.font = Font(bold=True)
                            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
                            cell.alignment = Alignment(horizontal='center')

                        # Add data rows
                        for item in self.results_tree.get_children():
                            values = self.results_tree.item(item)['values']
                            ws.append(values)

                        # Auto-adjust column widths
                        for column in ws.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            for cell in column:
                                try:
                                    if cell.value:
                                        max_length = max(max_length, len(str(cell.value)))
                                except Exception:

                                    pass
                            adjusted_width = min(max_length + 2, 50)
                            ws.column_dimensions[column_letter].width = adjusted_width

                        wb.save(filename)
                        messagebox.showinfo(_t("advanced_search.bulk_operations.success_title"), _t("advanced_search.bulk_operations.exported_to_excel", filename=filename))
                    else:
                        messagebox.showwarning(_t("advanced_search.bulk_operations.no_data_title"), _t("advanced_search.bulk_operations.no_results_to_export"))

                except ImportError:
                    if messagebox.askyesno(_t("advanced_search.bulk_operations.excel_not_found_title"),
                                          _t("advanced_search.bulk_operations.excel_not_found_msg")):
                        csv_filename = filename.replace('.xlsx', '.csv')
                        self.export_to_csv(csv_filename)
                except Exception as e:
                    messagebox.showerror(_t("advanced_search.bulk_operations.export_error_title"), _t("advanced_search.bulk_operations.export_failed_msg", error=e))

            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("advanced_search.bulk_operations.export_error_title"), _t("advanced_search.bulk_operations.could_not_export", error=str(e)))

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=f"💾 {_t('advanced_search.bulk_operations.export_btn')}", command=do_export).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
