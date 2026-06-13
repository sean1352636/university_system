"""PrefsMixin — auto-split from bakery_shop.py."""
from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class PrefsMixin:
    def load_user_prefs(self):
        if not self.current_user:
            return {"theme": "classic", "text_scale": 1.0, "language": "en"}
        rows = self._query("""SELECT theme, text_scale, language
                              FROM bakery_user_prefs WHERE user=?""",
                           (self.current_user,))
        if not rows:
            return {"theme": "classic", "text_scale": 1.0, "language": "en"}
        return {"theme": rows[0][0] or "classic",
                "text_scale": float(rows[0][1] or 1.0),
                "language": rows[0][2] or "en"}

    def save_user_prefs(self, *, theme=None, text_scale=None, language=None):
        if not self.current_user:
            return False
        current = self.load_user_prefs()
        theme = theme if theme is not None else current["theme"]
        text_scale = float(text_scale if text_scale is not None
                            else current["text_scale"])
        language = language if language is not None else current["language"]
        try:
            self._exec("""INSERT INTO bakery_user_prefs
                          (user, theme, text_scale, language, updated_at)
                          VALUES (?, ?, ?, ?, ?)
                          ON CONFLICT(user) DO UPDATE SET
                            theme = excluded.theme,
                            text_scale = excluded.text_scale,
                            language = excluded.language,
                            updated_at = excluded.updated_at""",
                       (self.current_user, theme, text_scale, language,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            logger.info("Prefs saved user=%s theme=%s scale=%.2f lang=%s",
                        self.current_user, theme, text_scale, language)
            return True
        except Exception:
            logger.exception("save_user_prefs failed")
            return False

    def apply_theme(self, theme_name):
        """Swap palette and trigger a rebuild of the entire UI."""
        palette = THEMES.get(theme_name) or THEMES["classic"]
        self.colors = dict(palette)
        self._theme_name = theme_name
        try:
            # Repaint root + status bar + recreate widgets.
            self.root.configure(bg=self.colors["background"])
            if hasattr(self, "status_bar"):
                self.status_bar.config(bg=self.colors["primary"], fg="white")
            self._rebuild_ui()
            logger.info("Theme applied: %s", theme_name)
        except Exception:
            logger.exception("apply_theme failed")

    def apply_text_scale(self, scale):
        """Scale all Tk fonts. Affects widgets going forward."""
        try:
            scale = max(0.7, min(2.0, float(scale)))
            self.root.tk.call("tk", "scaling", float(scale))
            self._text_scale = scale
            logger.info("Text scale applied: %.2f", scale)
            # Rebuilding is needed for already-laid-out widgets to pick up
            # the new sizing.
            self._rebuild_ui()
        except Exception:
            logger.exception("apply_text_scale failed")

    def _rebuild_ui(self):
        """Tear down the header + notebook and rebuild from scratch."""
        try:
            for child in list(self.root.winfo_children()):
                child.destroy()
            self.create_widgets()
        except Exception:
            logger.exception("UI rebuild failed")

    def _bind_keyboard_shortcuts(self):
        """Bind global shortcuts: Ctrl+Enter checkout, Ctrl+S save cart,
        Ctrl+R restore saved cart, Ctrl+F focus search, Ctrl+K prefs."""
        bindings = {
            "<Control-Return>":  lambda e: self.checkout(),
            "<Control-s>":       lambda e: self._cart_save_action(),
            "<Control-r>":       lambda e: self._cart_restore_action(),
            "<Control-f>":       lambda e: (hasattr(self, "search_var")
                                              and self.search_var.set("")
                                              or self._show_panel("shop")),
            "<Control-k>":       lambda e: self._open_prefs_dialog(),
        }
        for seq, fn in bindings.items():
            try:
                self.root.bind_all(seq, fn)
            except Exception:
                logger.debug("Could not bind %s", seq, exc_info=True)

    def _open_prefs_dialog(self):
        d = tk.Toplevel(self.root); d.title("Preferences")
        d.geometry("420x340"); d.transient(self.root); d.grab_set()
        tk.Label(d, text="🎨 Preferences",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(pady=10)

        cur = self.load_user_prefs()
        theme_var = tk.StringVar(value=cur["theme"])
        scale_var = tk.DoubleVar(value=cur["text_scale"])
        lang_var = tk.StringVar(value=cur["language"])

        tk.Label(d, text="Theme",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        ttk.Combobox(d, textvariable=theme_var,
                     values=list(THEMES.keys()),
                     state="readonly", width=30
                     ).pack(padx=20)

        tk.Label(d, text="Text scale (1.0 = normal, 1.3 = larger)",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        tk.Spinbox(d, from_=0.8, to=1.6, increment=0.1,
                   textvariable=scale_var, width=10).pack(padx=20)

        tk.Label(d, text="Language",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        ttk.Combobox(d, textvariable=lang_var,
                     values=["en", "cy", "es", "fr", "de"],
                     state="readonly", width=30
                     ).pack(padx=20)
        tk.Label(d, text="(Translations come from the university i18n "
                         "module — if a string is missing it falls back "
                         "to English.)",
                 bg=self.colors["background"], font=("Arial", 9, "italic"),
                 wraplength=360, justify="left"
                 ).pack(padx=20, pady=(4, 0))

        def save():
            if not self.current_user:
                messagebox.showinfo("Sign in",
                                    "Sign in to save preferences.",
                                    parent=d)
                return
            self.save_user_prefs(theme=theme_var.get(),
                                  text_scale=scale_var.get(),
                                  language=lang_var.get())
            self.apply_text_scale(scale_var.get())
            self.apply_theme(theme_var.get())
            messagebox.showinfo("Saved", "Preferences applied.")
            d.destroy()

        tk.Button(d, text="Apply",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=save
                  ).pack(side="right", padx=20, pady=12)
        tk.Button(d, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_feedback_dialog(self, *, order_id=None):
        d = tk.Toplevel(self.root); d.title("💬 Feedback")
        d.geometry("440x520"); d.transient(self.root); d.grab_set()
        tk.Label(d, text=_i18n("bakery.feedback.title", "💬 Send Feedback"),
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(pady=10)

        cat_var = tk.StringVar(value=FEEDBACK_CATEGORIES[0])
        tk.Label(d, text=_i18n("bakery.feedback.category", "Category"),
                 bg=self.colors["background"]).pack(anchor="w", padx=20)
        ttk.Combobox(d, textvariable=cat_var,
                     values=FEEDBACK_CATEGORIES, state="readonly",
                     width=44).pack(padx=20)

        tk.Label(d, text=_i18n("bakery.feedback.subject", "Subject"),
                 bg=self.colors["background"]
                 ).pack(anchor="w", padx=20, pady=(8, 0))
        subj_e = tk.Entry(d, width=58); subj_e.pack(padx=20)

        tk.Label(d, text=_i18n("bakery.feedback.message", "Your message"),
                 bg=self.colors["background"]
                 ).pack(anchor="w", padx=20, pady=(8, 0))
        msg_t = tk.Text(d, width=58, height=8); msg_t.pack(padx=20)

        rating_var = tk.IntVar(value=5)
        row = tk.Frame(d, bg=self.colors["background"]); row.pack(pady=8)
        tk.Label(row, text=_i18n("bakery.feedback.rating", "Rating:"),
                 bg=self.colors["background"]).pack(side="left")
        for n in range(1, 6):
            tk.Radiobutton(row, text=str(n), variable=rating_var,
                            value=n, bg=self.colors["background"]
                            ).pack(side="left")

        order_lbl = tk.Label(d, bg=self.colors["background"],
                              fg=self.colors["text"],
                              font=("Arial", 9, "italic"))
        if order_id:
            order_lbl.config(text=f"Related order: {order_id}")
        order_lbl.pack(pady=2)

        def submit():
            msg = msg_t.get("1.0", "end").strip()
            if not msg:
                messagebox.showerror("Message required",
                                     "Please write a message.",
                                     parent=d)
                return
            fid = self.submit_feedback(
                category=cat_var.get(),
                subject=subj_e.get().strip()
                         or f"{cat_var.get()} via Bakery Shop",
                message=msg, rating=rating_var.get(),
                order_id=order_id,
            )
            if fid:
                messagebox.showinfo(
                    _i18n("bakery.feedback.thanks", "Thanks"),
                    _i18n("bakery.feedback.received",
                          "Feedback #{fid} received. A team member will "
                          "respond if needed.", fid=fid),
                    parent=self.root)
                d.destroy()
            else:
                messagebox.showerror("Error", "Could not submit feedback.",
                                     parent=d)

        tk.Button(d, text=_i18n("common.submit", "Submit"),
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=submit
                  ).pack(side="right", padx=20, pady=12)
        tk.Button(d, text=_i18n("common.cancel", "Cancel"),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_feedback_admin(self):
        d = tk.Toplevel(self.root); d.title("💬 Feedback queue")
        d.geometry("900x500"); d.transient(self.root); d.grab_set()
        cols = ("id", "user", "category", "subject", "rating",
                "ticket", "status", "when")
        tree = ttk.Treeview(d, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (40, 130, 130, 220, 60, 110, 80, 130)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def reload():
            for it in tree.get_children():
                tree.delete(it)
            for r in self.list_feedback():
                tree.insert("", "end", values=(
                    r[0], r[1] or "—", r[3] or "—", r[4] or "—",
                    r[6] or "—", r[7] or "—", r[8],
                    r[10],
                ), tags=("closed",) if r[8] == "closed" else ())

        tree.tag_configure("closed", foreground="#888")

        def respond():
            sel = tree.selection()
            if not sel:
                return
            fid = tree.item(sel[0])["values"][0]
            text = simpledialog.askstring(
                "Respond",
                "Your response (will mark this feedback as closed):",
                parent=d)
            if text is not None:
                self.respond_to_feedback(fid, text)
                reload()

        ctl = tk.Frame(d); ctl.pack(fill="x", padx=8, pady=4)
        tk.Button(ctl, text="📝 Respond",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10, pady=4, command=respond).pack(side="left", padx=4)
        tk.Button(ctl, text="🔄 Refresh",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", padx=10, pady=4,
                  command=reload).pack(side="left", padx=4)
        tk.Button(ctl, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=10, pady=4, command=d.destroy
                  ).pack(side="right", padx=4)
        reload()

