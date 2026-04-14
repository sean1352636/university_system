"""Favorites tab for Campus Navigation GUI."""

from education_system.university_system.modules.domain.campus.campus_navigation.gui._imports import tk, ttk, messagebox, _t


class FavoritesTabMixin:
    """Mixin for the favorites tab."""

    def setup_favorites_tab(self, parent):
        """Set up the favorites tab."""
        if not self.auth.current_user:
            ttk.Label(
                parent,
                text=_t("navigation.favorites.login_required", default="Please log in to use favorites"),
                font=("Arial", 12)
            ).pack(pady=50)
            return

        # Favorites list
        list_frame = ttk.LabelFrame(parent, text=_t("navigation.favorites.my_favorites", default="My Favorites"), padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview for favorites
        columns = ("nickname", "location", "type")
        self.favorites_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

        self.favorites_tree.heading("nickname", text=_t("navigation.favorites.nickname_header", default="Nickname"))
        self.favorites_tree.heading("location", text=_t("navigation.favorites.location_header", default="Location"))
        self.favorites_tree.heading("type", text=_t("navigation.favorites.type_header", default="Type"))

        self.favorites_tree.column("nickname", width=100)
        self.favorites_tree.column("location", width=150)
        self.favorites_tree.column("type", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                  command=self.favorites_tree.yview)
        self.favorites_tree.configure(yscrollcommand=scrollbar.set)

        self.favorites_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            button_frame,
            text=_t("navigation.favorites.refresh_button", default="Refresh"),
            command=self.load_favorites
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("navigation.favorites.remove_button", default="Remove Selected"),
            command=self.remove_favorite
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("navigation.favorites.navigate_button", default="Navigate To"),
            command=self.navigate_to_favorite
        ).pack(side=tk.LEFT, padx=5)

        # Load favorites
        self.load_favorites()

    def load_favorites(self):
        """Load user's favorite locations."""
        if not self.auth.current_user:
            return

        user = self.auth.get_current_user()
        favorites = self.service.get_favorites(user['username'])

        # Clear existing items
        for item in self.favorites_tree.get_children():
            self.favorites_tree.delete(item)

        # Add favorites
        for fav in favorites:
            nickname = fav.get('nickname', 'N/A')
            location = fav.get('location_name', 'N/A')
            loc_type = fav['location_type']

            self.favorites_tree.insert(
                '',
                tk.END,
                values=(nickname, location, loc_type),
                tags=(fav['favorite_id'],)
            )

    def remove_favorite(self):
        """Remove selected favorite."""
        selection = self.favorites_tree.selection()
        if not selection:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.select_favorite", default="Please select a favorite to remove."))
            return

        item = selection[0]
        tags = self.favorites_tree.item(item, 'tags')
        if tags:
            favorite_id = int(tags[0])

            if messagebox.askyesno(_t("navigation.dialogs.confirm", default="Confirm"), _t("navigation.dialogs.remove_favorite_confirm", default="Remove this favorite?")):
                self.service.remove_favorite(favorite_id)
                self.load_favorites()
                messagebox.showinfo(_t("navigation.dialogs.success", default="Success"), _t("navigation.messages.favorite_removed", default="Favorite removed!"))

    def navigate_to_favorite(self):
        """Navigate to selected favorite location."""
        selection = self.favorites_tree.selection()
        if not selection:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.select_favorite_location", default="Please select a favorite location."))
            return

        item = selection[0]
        values = self.favorites_tree.item(item, 'values')
        location_name = values[1]

        # Search for the location
        buildings = self.service.search_buildings(location_name)
        if buildings:
            self.show_building_details(buildings[0])
            messagebox.showinfo(_t("navigation.dialogs.info", default="Info"), _t("navigation.messages.showing_details", default="Showing details for {location_name}").format(location_name=location_name))
        else:
            messagebox.showinfo(_t("navigation.dialogs.info", default="Info"), _t("navigation.messages.location_found_no_details", default="Location found but details not available."))

    def add_to_favorites(self):
        """Add the currently selected building to favorites."""
        if not self.auth.current_user:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.login_required", default="Please log in to add favorites."))
            return

        if not self.selected_building:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.no_building_selected", default="No building selected."))
            return

        # Create dialog for nickname
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("navigation.messages.add_to_favorites_title", default="Add to Favorites"))
        dialog.geometry("400x150")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=_t("navigation.messages.add_to_favorites_text", default="Add '{building_name}' to favorites").format(building_name=self.selected_building['building_name']),
            font=("Arial", 10, "bold")
        ).pack(pady=10)

        ttk.Label(dialog, text=_t("navigation.messages.nickname_optional", default="Nickname (optional):")).pack(pady=5)
        nickname_entry = ttk.Entry(dialog, width=40)
        nickname_entry.pack(pady=5)
        nickname_entry.insert(0, self.selected_building['building_name'])

        def save_favorite():
            nickname = nickname_entry.get().strip()
            if not nickname:
                nickname = self.selected_building['building_name']

            try:
                user = self.auth.get_current_user()
                self.service.add_favorite(
                    user_id=user['username'],
                    location_type='building',
                    location_id=self.selected_building['building_id'],
                    nickname=nickname
                )
                messagebox.showinfo(_t("navigation.dialogs.success", default="Success"), _t("navigation.messages.building_added_to_favorites", default="Building added to favorites!"))
                dialog.destroy()
                # Refresh favorites if tab is visible
                self.load_favorites()
            except Exception as e:
                messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.failed_to_add_favorite", default="Failed to add favorite: {error}").format(error=str(e)))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("navigation.messages.add_button", default="Add"), command=save_favorite).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("navigation.messages.cancel_button", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
