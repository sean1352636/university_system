"""
Asset Management GUI

Asset issue / return / audit lifecycle for staff HR:
- Browse assets, add assets
- Assign assets and process returns
- Report and resolve issues
- View per-asset audit log and overall asset stats

Wired to the same AssetManager used by the asset CLI menu. This is a
separate feature from the equipment booking/reservation GUI.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from education_system.systems.university.domain.staff.staff_hr.services import (
    AssetManager,
)
from education_system.systems.university.interfaces.gui.staff.staff_hr.recruitment_gui import (
    _FormDialog,
)


class AssetsGUI:
    """GUI for the asset assign/return/issue/audit lifecycle."""

    def __init__(self, root, auth=None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Assets")
            return

        self.user_id = self.current_user.get('id') or self.current_user.get('username')

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    # ------------------------------------------------------------------
    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Assets")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Asset Management")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)
        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(
            side=tk.BOTTOM, anchor=tk.E, padx=10, pady=5)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_assets_tab()
        self._create_issues_tab()
        self._create_audit_tab()

    # ------------------------------------------------------------------
    # Assets: browse / add / assign / return
    # ------------------------------------------------------------------
    def _create_assets_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Assets")

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Assets", style='Header.TLabel').pack(side=tk.LEFT)

        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="Add Asset", command=self._add_asset).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Assign", command=self._assign_asset).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Process Return", command=self._return_asset).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Refresh", command=self._load_assets).pack(side=tk.LEFT, padx=3)

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text="Status:").pack(side=tk.LEFT, padx=5)
        self.asset_status = ttk.Combobox(filt, values=[
            'All', 'available', 'assigned', 'in_repair', 'returned', 'disposed'],
            width=14, state='readonly')
        self.asset_status.set('All')
        self.asset_status.pack(side=tk.LEFT, padx=5)
        self.asset_status.bind('<<ComboboxSelected>>', lambda e: self._load_assets())
        self.asset_stats_label = ttk.Label(filt, text="", foreground='gray')
        self.asset_stats_label.pack(side=tk.RIGHT, padx=10)

        cols = ('ID', 'Tag', 'Name', 'Category', 'Status', 'Condition', 'Location')
        self.assets_tree = self._make_tree(tab, cols)

    def _load_assets(self):
        status = self.asset_status.get()
        try:
            assets = AssetManager.get_assets(
                status=None if status == 'All' else status, limit=200)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load assets: {e}")
            return
        self.assets_tree.delete(*self.assets_tree.get_children())
        for a in assets:
            self.assets_tree.insert('', tk.END, values=(
                a.get('asset_id'), a.get('asset_tag', ''), a.get('name', ''),
                a.get('category_name', ''), a.get('status', ''),
                a.get('condition', ''), a.get('location', '')))
        self._update_stats()

    def _update_stats(self):
        try:
            stats = AssetManager.get_asset_stats()
            by_status = stats.get('by_status', {})
            self.asset_stats_label.config(text=(
                f"Assigned: {by_status.get('assigned', 0)} | "
                f"Available: {by_status.get('available', 0)} | "
                f"Open issues: {stats.get('open_issues', 0)}"))
        except Exception:
            self.asset_stats_label.config(text="")

    def _selected_asset_id(self):
        sel = self.assets_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select an asset first.")
            return None
        return self.assets_tree.item(sel[0])['values'][0]

    def _categories(self):
        try:
            return AssetManager.get_categories()
        except Exception:
            return []

    def _add_asset(self):
        cats = self._categories()
        cat_names = [c.get('name', '') for c in cats]
        dlg = _FormDialog(self.window or self.root, "Add Asset", [
            ('name', 'Asset Name', 'entry', None),
            ('category', 'Category', 'combo', cat_names),
            ('serial_number', 'Serial Number', 'entry', None),
            ('location', 'Location', 'entry', None),
            ('purchase_price', 'Purchase Price', 'entry', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        if not d.get('name'):
            messagebox.showwarning("Missing data", "Asset name is required.")
            return
        cat = next((c for c in cats if c.get('name') == d.get('category')), None)
        if not cat:
            messagebox.showwarning("Missing data", "A valid category is required.")
            return
        try:
            price = float(d['purchase_price']) if d.get('purchase_price') else None
            asset_id, tag = AssetManager.create_asset(
                name=d['name'], category_id=cat['category_id'], created_by=self.user_id,
                serial_number=d.get('serial_number'), location=d.get('location'),
                purchase_price=price)
            messagebox.showinfo("Created", f"Asset created (ID {asset_id}, tag {tag}).")
            self._load_assets()
        except Exception as e:
            messagebox.showerror("Error", f"Could not create asset: {e}")

    def _assign_asset(self):
        asset_id = self._selected_asset_id()
        if asset_id is None:
            return
        dlg = _FormDialog(self.window or self.root, "Assign Asset", [
            ('user_id', 'Assign to User ID', 'entry', None),
            ('purpose', 'Purpose', 'entry', None),
            ('expected_return_date', 'Expected Return (YYYY-MM-DD)', 'entry', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        if not d.get('user_id'):
            messagebox.showwarning("Missing data", "User ID is required.")
            return
        try:
            AssetManager.assign_asset(
                int(asset_id), d['user_id'], assigned_by=self.user_id,
                purpose=d.get('purpose'),
                expected_return_date=d.get('expected_return_date'))
            messagebox.showinfo("Assigned", "Asset assigned.")
            self._load_assets()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _return_asset(self):
        asset_id = self._selected_asset_id()
        if asset_id is None:
            return
        dlg = _FormDialog(self.window or self.root, "Process Return", [
            ('condition', 'Condition', 'combo', ['excellent', 'good', 'fair', 'poor', 'damaged']),
            ('notes', 'Notes', 'text', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        try:
            AssetManager.return_asset(
                int(asset_id), returned_by=self.user_id,
                condition=d.get('condition') or 'good', notes=d.get('notes'))
            messagebox.showinfo("Returned", "Asset returned.")
            self._load_assets()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------
    def _create_issues_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Issues")

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Asset Issues", style='Header.TLabel').pack(side=tk.LEFT)
        btns = ttk.Frame(header)
        btns.pack(side=tk.RIGHT)
        ttk.Button(btns, text="Report Issue", command=self._report_issue).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Resolve", command=self._resolve_issue).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="Refresh", command=self._load_issues).pack(side=tk.LEFT, padx=3)

        filt = ttk.Frame(tab)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text="Status:").pack(side=tk.LEFT, padx=5)
        self.issue_status = ttk.Combobox(filt, values=[
            'All', 'open', 'in_progress', 'resolved', 'closed'], width=14, state='readonly')
        self.issue_status.set('open')
        self.issue_status.pack(side=tk.LEFT, padx=5)
        self.issue_status.bind('<<ComboboxSelected>>', lambda e: self._load_issues())

        cols = ('ID', 'Asset', 'Tag', 'Type', 'Severity', 'Status', 'Title')
        self.issues_tree = self._make_tree(tab, cols)

    def _load_issues(self):
        status = self.issue_status.get()
        try:
            issues = AssetManager.get_issues(
                status=None if status == 'All' else status, limit=200)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load issues: {e}")
            return
        self.issues_tree.delete(*self.issues_tree.get_children())
        for i in issues:
            self.issues_tree.insert('', tk.END, values=(
                i.get('issue_id'), i.get('asset_name', ''), i.get('asset_tag', ''),
                i.get('issue_type', ''), i.get('severity', ''),
                i.get('status', ''), i.get('title', '')))

    def _report_issue(self):
        asset_id = self._selected_asset_id()
        if asset_id is None:
            messagebox.showinfo("Select asset", "Select an asset on the Assets tab first.")
            return
        dlg = _FormDialog(self.window or self.root, "Report Issue", [
            ('issue_type', 'Issue Type', 'combo', ['damage', 'malfunction', 'theft', 'loss', 'other']),
            ('severity', 'Severity', 'combo', ['low', 'medium', 'high', 'critical']),
            ('title', 'Title', 'entry', None),
            ('description', 'Description', 'text', None),
        ])
        if not dlg.result:
            return
        d = dlg.result
        try:
            iid = AssetManager.report_issue(
                int(asset_id), reported_by=self.user_id,
                issue_type=d.get('issue_type') or 'malfunction',
                title=d.get('title') or 'Issue',
                description=d.get('description') or '',
                severity=d.get('severity') or 'medium',
                reported_by_name=self.current_user.get('username'))
            messagebox.showinfo("Reported", f"Issue reported (ID {iid}).")
            self._load_issues()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _resolve_issue(self):
        sel = self.issues_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select an issue first.")
            return
        iid = self.issues_tree.item(sel[0])['values'][0]
        dlg = _FormDialog(self.window or self.root, "Resolve Issue", [
            ('resolution', 'Resolution', 'text', None)])
        if not dlg.result:
            return
        try:
            AssetManager.resolve_issue(
                int(iid), resolved_by=self.user_id,
                resolution=dlg.result.get('resolution') or 'Resolved',
                resolved_by_name=self.current_user.get('username'))
            messagebox.showinfo("Resolved", "Issue resolved.")
            self._load_issues()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------
    def _create_audit_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Audit Log")

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header, text="Asset Audit Log", style='Header.TLabel').pack(side=tk.LEFT)

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, padx=10)
        ttk.Label(ctrl, text="Asset ID:").pack(side=tk.LEFT, padx=5)
        self.audit_asset_entry = ttk.Entry(ctrl, width=12)
        self.audit_asset_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="View Audit", command=self._load_audit).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Use Selected Asset", command=self._audit_from_selection).pack(side=tk.LEFT, padx=5)

        cols = ('Date', 'Action', 'By', 'Notes')
        self.audit_tree = self._make_tree(tab, cols)

    def _audit_from_selection(self):
        asset_id = self._selected_asset_id()
        if asset_id is None:
            return
        self.audit_asset_entry.delete(0, tk.END)
        self.audit_asset_entry.insert(0, str(asset_id))
        self._load_audit()

    def _load_audit(self):
        raw = self.audit_asset_entry.get().strip()
        if not raw:
            messagebox.showwarning("Missing data", "Enter an asset ID.")
            return
        try:
            logs = AssetManager.get_audit_log(int(raw), limit=100)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load audit log: {e}")
            return
        self.audit_tree.delete(*self.audit_tree.get_children())
        for log in logs:
            self.audit_tree.insert('', tk.END, values=(
                log.get('action_date', ''), log.get('action', ''),
                log.get('action_by', ''), log.get('notes', '')))

    # ------------------------------------------------------------------
    def _make_tree(self, parent, cols):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        tree = ttk.Treeview(frame, columns=cols, show='headings', yscrollcommand=yscroll.set)
        yscroll.config(command=tree.yview)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=130, anchor=tk.W)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def refresh_all(self):
        self._load_assets()
        self._load_issues()
