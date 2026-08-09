"""Methods _resource_register_course through _resolve_user_email."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class FirstAidPortal:
    def _resource_register_course(self, course):
        """Open a registration form for a training course and persist the
        sign-up to the central DB (``first_aid_training_registrations``)."""
        win = self._resource_window(f"Register — {course}", f"🎓  {course}",
                                    width=520, height=440)

        form = tk.Frame(win, bg=self.colors["card"], relief="raised", bd=1)
        form.pack(fill="both", expand=True, padx=25, pady=10)

        tk.Label(
            form,
            text="Reserve a place on the next available course. The "
                 "Health Center will confirm your slot by email.",
            font=("Segoe UI", 9), bg=self.colors["card"], fg="#7f8c8d",
            wraplength=440, justify="left",
        ).pack(anchor="w", padx=20, pady=(15, 10))

        vars_ = {}
        rows = [
            ("Full Name:", "name"),
            ("Student/Staff ID:", "user_id"),
            ("Email:", "email"),
            ("Contact Number:", "phone"),
            ("Preferred Date:", "preferred_date"),
        ]
        for label, key in rows:
            row = tk.Frame(form, bg=self.colors["card"])
            row.pack(fill="x", padx=20, pady=6)
            tk.Label(row, text=label, font=("Segoe UI", 10, "bold"),
                     bg=self.colors["card"], fg=self.colors["text"],
                     width=16, anchor="w").pack(side="left")
            var = tk.StringVar()
            vars_[key] = var
            tk.Entry(row, textvariable=var, font=("Segoe UI", 10),
                     relief="solid", bd=1).pack(side="left", fill="x",
                                                expand=True)

        # Pre-fill from the signed-in user.
        if self.user:
            vars_["name"].set(self.user_display)
            uid = (self.user.get('user_id') or self.user.get('id') or '')
            if uid:
                vars_["user_id"].set(str(uid))
            if self.user.get('email'):
                vars_["email"].set(str(self.user['email']))

        def _submit():
            name = vars_["name"].get().strip()
            if not name:
                messagebox.showwarning("Name Required",
                                       "Please enter your name to register.",
                                       parent=win)
                return
            reg_email = vars_["email"].get().strip()
            reg_phone = vars_["phone"].get().strip()
            if reg_email and not _is_valid_email(reg_email):
                messagebox.showwarning(
                    "Invalid Email",
                    "Please enter a valid email address so we can confirm "
                    "your place (or leave it blank).", parent=win)
                return
            if reg_phone and not _is_valid_phone(reg_phone):
                messagebox.showwarning(
                    "Invalid Phone Number",
                    "Please enter a valid contact number with at least 7 "
                    "digits (or leave it blank).", parent=win)
                return
            if not self.db:
                messagebox.showerror(
                    "Database Unavailable",
                    "Cannot save your registration — the database is not "
                    "reachable. Please contact the Health Center.",
                    parent=win)
                return
            reg = {
                "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "course": course,
                "user_id": vars_["user_id"].get().strip(),
                "name": name,
                "email": reg_email,
                "phone": reg_phone,
                "preferred_date": vars_["preferred_date"].get().strip(),
                "notes": "",
            }
            try:
                reg_id = self.db.add_registration(reg)
            except sqlite3.Error:
                logger.exception("Course registration failed (user=%s)",
                                 self.user_display)
                messagebox.showerror("Save Error",
                                     "Could not save your registration.",
                                     parent=win)
                return
            logger.info("Training registration id=%s course=%s user=%s",
                        reg_id, course, self.user_display)

            # Email integration: send the user a sign-up confirmation.
            reference = f"REG-{reg_id:04d}"
            recipient = reg["email"] or self._resolve_user_email(reg["user_id"])
            confirmation_sent = False
            if recipient:
                confirmation_sent = self._send_template_email(
                    recipient, "health/first_aid_course_confirmation", {
                        "name": reg["name"],
                        "reference": reference,
                        "course": course,
                        "preferred_date": reg["preferred_date"] or "To be confirmed",
                        "submitted_at": reg["submitted_at"],
                    })

            if confirmation_sent:
                tail = f"A confirmation email has been sent to {recipient}."
            else:
                tail = ("The University Health Center will email you to "
                        "confirm your place.")
            messagebox.showinfo(
                "Registration Received",
                f"✓ You're registered for {course}.\n\n"
                f"Reference: {reference}\n\n"
                f"{tail}",
                parent=win)
            win.destroy()

        btns = tk.Frame(form, bg=self.colors["card"])
        btns.pack(pady=18)
        tk.Button(btns, text="Submit Registration",
                  font=("Segoe UI", 10, "bold"), bg=self.colors["accent"],
                  fg="white", relief="flat", padx=20, pady=6, cursor="hand2",
                  command=_submit).pack(side="left", padx=5)
        tk.Button(btns, text="Cancel", font=("Segoe UI", 10),
                  bg="#bdc3c7", fg="white", relief="flat", padx=20, pady=6,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=5)

    def _resource_download_handbook(self):
        """Generate the first aid handbook from the portal's own content
        and open it with the OS default application."""
        lines = [
            "UNIVERSITY FIRST AID HANDBOOK",
            "=" * 60,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "For any life-threatening emergency, call 911 immediately.",
            "",
            "EMERGENCY CONTACTS",
            "-" * 60,
        ]
        for c in self.emergency_contacts:
            lines.append(f"{c['name']}: {c['number']}")
            lines.append(f"    {c['description']}")
            lines.append(f"    Location: {c['location']}")
            lines.append("")

        lines.append("")
        lines.append("FIRST AID PROCEDURES")
        lines.append("-" * 60)
        for condition, instructions in self.first_aid_data.items():
            lines.append("")
            lines.append(condition.upper())
            lines.append(instructions.strip())
            lines.append("")

        lines.append("")
        lines.append("This handbook is a quick-reference guide and is not a "
                     "substitute for professional medical training.")

        content = "\n".join(lines)
        fname = (f"University_First_Aid_Handbook_"
                 f"{datetime.now().strftime('%Y%m%d')}.txt")
        # Prefer the user's Downloads folder; fall back to the temp dir.
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        target_dir = downloads if os.path.isdir(downloads) else tempfile.gettempdir()
        path = os.path.join(target_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError:
            logger.exception("Could not write handbook file")
            messagebox.showerror("Download Failed",
                                 "Could not save the handbook file.")
            return
        logger.info("First aid handbook generated at %s (user=%s)",
                    path, self.user_display)
        self._open_path(path)
        messagebox.showinfo(
            "Handbook Downloaded",
            f"✓ The first aid handbook has been saved to:\n\n{path}\n\n"
            f"It should now open automatically.")

    def _resource_watch_videos(self):
        """List reputable first aid training videos; each opens in the
        default web browser."""
        win = self._resource_window("Training Videos",
                                    "🎥  First Aid Training Videos",
                                    width=620, height=440)
        videos = [
            ("CPR & AED — British Heart Foundation",
             "https://www.youtube.com/watch?v=ILxjxfB4zNk"),
            ("How to do CPR — British Red Cross",
             "https://www.youtube.com/watch?v=2PngCv7NjaI"),
            ("Recovery position — British Red Cross",
             "https://www.youtube.com/watch?v=dPYUViGTVMM"),
            ("Choking (adult) — British Red Cross",
             "https://www.youtube.com/watch?v=7CgtIgSyAiU"),
            ("Treating severe bleeding — British Red Cross",
             "https://www.youtube.com/watch?v=NxO5LvgqZe0"),
        ]
        body = tk.Frame(win, bg=self.colors["bg"])
        body.pack(fill="both", expand=True, padx=25, pady=10)
        for title, url in videos:
            card = tk.Frame(body, bg=self.colors["card"], relief="raised", bd=1)
            card.pack(fill="x", pady=6)
            tk.Label(card, text=title, font=("Segoe UI", 11, "bold"),
                     bg=self.colors["card"], fg=self.colors["text"]).pack(
                side="left", padx=15, pady=12)
            tk.Button(card, text="▶ Watch", font=("Segoe UI", 9, "bold"),
                      bg=self.colors["secondary"], fg="white", relief="flat",
                      padx=15, pady=4, cursor="hand2",
                      command=lambda u=url: self._open_url(u)).pack(
                side="right", padx=15)

    def _resource_view_schedule(self):
        """Show upcoming workshops with dates relative to today."""
        win = self._resource_window("Workshop Schedule",
                                    "🗓  Upcoming Workshops & Events",
                                    width=640, height=480)
        today = datetime.now()
        workshops = [
            (7, "CPR & AED Certification", "University Health Center, Bldg H",
             "Hands-on certification with the campus first aid team."),
            (14, "Basic First Aid Workshop", "Student Services, Bldg C",
             "Bleeding, burns, sprains and the recovery position."),
            (21, "Mental Health First Aid", "Counselling Centre, Bldg C",
             "Recognising and supporting peers in crisis."),
            (35, "Red Cross Community Day", "Main Quad",
             "Open demonstrations, free kits and Q&A sessions."),
            (49, "AED & Choking Response", "Sports Centre",
             "Defibrillator use and adult/child choking procedures."),
        ]
        body = tk.Frame(win, bg=self.colors["bg"])
        body.pack(fill="both", expand=True, padx=25, pady=10)
        for offset, name, location, desc in workshops:
            when = today + timedelta(days=offset)
            card = tk.Frame(body, bg=self.colors["card"], relief="raised", bd=1)
            card.pack(fill="x", pady=6)
            tk.Label(card, text=when.strftime("%a %d %b %Y"),
                     font=("Segoe UI", 10, "bold"), bg=self.colors["card"],
                     fg=self.colors["primary"], width=16, anchor="w").pack(
                side="left", padx=(15, 5), pady=12)
            info = tk.Frame(card, bg=self.colors["card"])
            info.pack(side="left", fill="x", expand=True, pady=8)
            tk.Label(info, text=name, font=("Segoe UI", 11, "bold"),
                     bg=self.colors["card"], fg=self.colors["text"]).pack(
                anchor="w")
            tk.Label(info, text=f"📍 {location}", font=("Segoe UI", 9),
                     bg=self.colors["card"], fg="#7f8c8d").pack(anchor="w")
            tk.Label(info, text=desc, font=("Segoe UI", 9),
                     bg=self.colors["card"], fg="#7f8c8d", wraplength=380,
                     justify="left").pack(anchor="w")
        tk.Button(win, text="Register for a Course",
                  font=("Segoe UI", 9, "bold"), bg=self.colors["accent"],
                  fg="white", relief="flat", padx=15, pady=5, cursor="hand2",
                  command=lambda: self._resource_register_course(
                      "First Aid Workshop")).pack(pady=10)

    def _resource_kit_locations(self):
        """Show the campus directory of first aid kits and AEDs."""
        win = self._resource_window("First Aid Kit & AED Locations",
                                    "🧰  First Aid Kit & AED Locations",
                                    width=640, height=500)
        locations = [
            ("Main Reception, Building A", "Kit + AED", "Ground floor, by the desk"),
            ("Library, Building B", "Kit + AED", "Entrance lobby, left wall"),
            ("Student Services, Building C", "Kit", "Help desk, 1st floor"),
            ("Science Labs, Building D", "Kit + AED", "Corridor outside Lab 3"),
            ("Sports Centre", "Kit + AED", "Reception & poolside"),
            ("University Health Center, Building H", "Kit + AED", "Treatment room"),
            ("Cafeteria / Dining Hall", "Kit", "Behind the serving counter"),
            ("Halls of Residence", "Kit + AED", "Each block's ground-floor lobby"),
        ]
        body = tk.Frame(win, bg=self.colors["bg"])
        body.pack(fill="both", expand=True, padx=25, pady=10)
        for place, kind, detail in locations:
            card = tk.Frame(body, bg=self.colors["card"], relief="raised", bd=1)
            card.pack(fill="x", pady=4)
            badge = self.colors["primary"] if "AED" in kind else self.colors["accent"]
            tk.Label(card, text=kind, font=("Segoe UI", 8, "bold"),
                     bg=badge, fg="white", width=10).pack(side="left",
                                                          padx=10, pady=10)
            info = tk.Frame(card, bg=self.colors["card"])
            info.pack(side="left", fill="x", expand=True, pady=6)
            tk.Label(info, text=place, font=("Segoe UI", 11, "bold"),
                     bg=self.colors["card"], fg=self.colors["text"]).pack(
                anchor="w")
            tk.Label(info, text=detail, font=("Segoe UI", 9),
                     bg=self.colors["card"], fg="#7f8c8d").pack(anchor="w")
        tk.Label(win, text="AED = Automated External Defibrillator",
                 font=("Segoe UI", 8, "italic"), bg=self.colors["bg"],
                 fg="#7f8c8d").pack(pady=(0, 4))
        tk.Button(win, text="Open Campus Map in Browser",
                  font=("Segoe UI", 9, "bold"), bg=self.colors["secondary"],
                  fg="white", relief="flat", padx=15, pady=5, cursor="hand2",
                  command=lambda: self._open_url(
                      "https://www.openstreetmap.org/")).pack(pady=8)

    def _resource_get_app(self):
        """Show the University Safety App details and store links."""
        win = self._resource_window("University Safety App",
                                    "📱  University Safety App",
                                    width=520, height=420)
        card = tk.Frame(win, bg=self.colors["card"], relief="raised", bd=1)
        card.pack(fill="both", expand=True, padx=25, pady=10)
        tk.Label(card, text="Carry emergency information, first aid guides "
                            "and one-tap campus security calling wherever "
                            "you go.",
                 font=("Segoe UI", 10), bg=self.colors["card"],
                 fg=self.colors["text"], wraplength=440,
                 justify="left").pack(padx=20, pady=(20, 10))
        features = [
            "• Offline first aid procedures",
            "• One-tap call to Campus Security & 911",
            "• Nearest AED & first aid kit finder",
            "• Push alerts for campus emergencies",
        ]
        for f in features:
            tk.Label(card, text=f, font=("Segoe UI", 10),
                     bg=self.colors["card"], fg="#34495e",
                     anchor="w").pack(fill="x", padx=40, pady=2)
        store = tk.Frame(card, bg=self.colors["card"])
        store.pack(pady=20)
        tk.Button(store, text=" App Store", font=("Segoe UI", 10, "bold"),
                  bg="#2c3e50", fg="white", relief="flat", padx=20, pady=8,
                  cursor="hand2",
                  command=lambda: self._open_url(
                      "https://www.apple.com/app-store/")).pack(side="left",
                                                                padx=8)
        tk.Button(store, text="▶ Google Play", font=("Segoe UI", 10, "bold"),
                  bg="#27ae60", fg="white", relief="flat", padx=20, pady=8,
                  cursor="hand2",
                  command=lambda: self._open_url(
                      "https://play.google.com/store")).pack(side="left",
                                                             padx=8)

    def _open_url(self, url):
        """Open a URL in the default browser, reporting failure to the user."""
        try:
            webbrowser.open(url)
            logger.info("Opened resource URL: %s", url)
        except Exception:
            logger.exception("Could not open URL %s", url)
            messagebox.showerror("Cannot Open Link",
                                 f"Could not open your browser.\n\n{url}")

    def _open_path(self, path):
        """Open a local file with the OS default application (best-effort)."""
        try:
            if sys.platform.startswith("darwin"):
                import subprocess
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception:
            logger.exception("Could not auto-open file %s", path)

    def _resolve_user_email(self, user_id=""):
        """Best-effort email lookup for the signed-in user.

        Prefers the email carried on the auth session, then falls back to
        the ``users`` / ``students`` tables keyed by the supplied id.
        Returns '' if nothing can be resolved."""
        if self.user and self.user.get("email"):
            return str(self.user["email"]).strip()
        uid = str(user_id or "").strip()
        if not uid:
            return ""
        try:
            from education_system.systems.university.domains.pastoral.infrastructure.health.storage import (
                get_connection,
            )
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT email FROM users "
                    "WHERE (username = ? OR id = ?) "
                    "  AND email IS NOT NULL AND email != '' LIMIT 1",
                    (uid, uid),
                ).fetchone()
                if row and row[0]:
                    return str(row[0]).strip()
                row = conn.execute(
                    "SELECT email_address FROM students "
                    "WHERE student_id = ? "
                    "  AND email_address IS NOT NULL "
                    "  AND email_address != '' LIMIT 1",
                    (uid,),
                ).fetchone()
                if row and row[0]:
                    return str(row[0]).strip()
        except Exception:
            logger.debug("Could not resolve email for %s", uid, exc_info=True)
        return ""
