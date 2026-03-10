"""Rewards management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pastoral_care.rewards.services.rewards_service import RewardsService
from education_system.primary_school.infrastructure.database.constants import REWARD_TYPES
import traceback

HOUSES = ["Red", "Blue", "Green", "Yellow"]


class _RewardsDialog(tk.Toplevel):
    """Add / Edit reward record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Reward" if record else "Add Reward")
        self.geometry("480x400")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("pupil_id", "Pupil ID *")
        self._add_combo("reward_type", "Reward Type *", list(REWARD_TYPES))
        self._add_field("reason", "Reason")
        self._add_combo("house", "House", HOUSES)
        self._add_field("points", "Points")
        self._add_field("awarded_by", "Awarded By")

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("reward_type"):
            messagebox.showwarning("Validation", "Reward type is required.", parent=self)
            return
        self.result = data
        self.destroy()


class RewardsFrame(tk.Frame):
    """Main rewards management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = RewardsService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Rewards Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Reward", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Reward Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + list(REWARD_TYPES),
                                          state="readonly", width=14)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="House Points", command=self._show_house_points).pack(side="left", padx=3)

        # Treeview
        columns = ("reward_id", "pupil_id", "reward_type", "reason", "house",
                    "points", "award_date")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("reward_id", width=80)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        type_filter = self._type_filter.get()
        reward_type = None if type_filter == "All" else type_filter
        try:
            records = self._service.get_rewards(reward_type=reward_type)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("reward_id", r.get("id")), values=(
                    r.get("reward_id", r.get("id")), r.get("pupil_id", ""),
                    r.get("reward_type", ""), r.get("reason", ""),
                    r.get("house", ""), r.get("points", ""),
                    r.get("award_date", ""),
                ))
            self._status_var.set(f"{len(records)} reward(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load rewards: {e}")

    def _show_house_points(self):
        try:
            summary = self._service.get_house_points_summary()
            lines = ["House Points Summary", "=" * 30]
            for house_name in HOUSES:
                pts = summary.get(house_name, 0)
                lines.append(f"{house_name}: {pts} points")
            messagebox.showinfo("House Points", "\n".join(lines))
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load house points: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a reward first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _RewardsDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.award_reward(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_rewards()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Reward not found.")
            return
        dlg = _RewardsDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_reward(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete reward {rid}?"):
            return
        try:
            self._service.delete_reward(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
