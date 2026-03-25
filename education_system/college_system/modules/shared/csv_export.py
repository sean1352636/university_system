"""Shared CSV export helper for exporting Treeview data to CSV files."""

import csv
import tkinter as tk
from tkinter import filedialog, messagebox


def export_treeview_to_csv(tree: "tk.Widget", default_filename: str = "export.csv") -> None:
    """Export all data from a ttk.Treeview widget to a CSV file.

    Prompts the user with a Save As dialog, then writes the column headings
    and all row data to the chosen file.

    Args:
        tree: A ttk.Treeview widget whose data should be exported.
        default_filename: Suggested filename for the Save As dialog.
    """
    filepath = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile=default_filename,
    )
    if not filepath:
        return  # User cancelled

    columns = tree["columns"]
    headings = [tree.heading(col, "text") for col in columns]
    rows = [tree.item(iid, "values") for iid in tree.get_children()]

    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headings)
            writer.writerows(rows)
        messagebox.showinfo(
            "Export Successful",
            f"Exported {len(rows)} row(s) to:\n{filepath}",
        )
    except OSError as exc:
        messagebox.showerror("Export Failed", f"Could not write file:\n{exc}")
