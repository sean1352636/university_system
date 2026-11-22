"""Methods _resource_register_course through _resolve_user_email."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class FirstAidPortal:
    def _fa_sessions(self, course=None):
        """Upcoming scheduled course sessions (``first_aid_course_sessions``)."""
        from education_system.systems.university.domains.health.application.health import (
            first_aid as fa_rules,
        )
        from education_system.systems.university.domains.health.infrastructure.health.storage import (
            get_connection,
        )
        try:
            conn = get_connection()
            try:
                return fa_rules.sessions(conn, course=course)
            finally:
                conn.close()
        except Exception:
            logger.exception("Could not read first aid course sessions")
            return []

    @staticmethod
    def _session_label(session):
        when = str(session["starts_at"])[:16]
        where = f" — {session['location']}" if session.get("location") else ""
        return (f"#{session['id']}  {when}  {session['course']}{where}  "
                f"({session['places_left']} place{'s' if session['places_left'] != 1 else ''} left)")

    def _resource_register_course(self, course, session_id=None):
        """Open a registration form for a training course and persist the
        sign-up to the central DB (``first_aid_training_registrations``),
        booked onto a real session when one is chosen."""
        win = self._resource_window(f"Register — {course}", f"🎓  {course}",
                                    width=560, height=480)

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

        # Session picker: the course's scheduled sessions (any course's when
        # this one has none), or "no date yet" to be contacted.
        sessions = self._fa_sessions(course) or self._fa_sessions()
        no_date = "No suitable date yet — contact me when one is scheduled"
        choices = [self._session_label(x) for x in sessions if x["places_left"] > 0] + [no_date]
        row = tk.Frame(form, bg=self.colors["card"])
        row.pack(fill="x", padx=20, pady=6)
        tk.Label(row, text="Session:", font=("Segoe UI", 10, "bold"),
                 bg=self.colors["card"], fg=self.colors["text"],
                 width=16, anchor="w").pack(side="left")
        session_var = tk.StringVar()
        ttk.Combobox(row, textvariable=session_var, values=choices, state="readonly",
                     width=48).pack(side="left", fill="x", expand=True)
        wanted = next((c for c in choices if session_id and c.startswith(f"#{session_id} ")),
                      None)
        session_var.set(wanted or choices[0])
        by_label = {self._session_label(x): x for x in sessions}

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
            chosen = by_label.get(session_var.get())
            reg = {
                "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "course": chosen["course"] if chosen else course,
                "user_id": vars_["user_id"].get().strip(),
                "name": name,
                "email": reg_email,
                "phone": reg_phone,
                "preferred_date": str(chosen["starts_at"]) if chosen else "",
                "notes": "" if chosen else "No date chosen — contact when scheduled",
                "session_id": chosen["id"] if chosen else None,
            }
            if chosen:
                from education_system.systems.university.domains.health.application.health import (
                    first_aid as fa_rules,
                )
                from education_system.systems.university.domains.health.infrastructure.health.storage import (
                    get_connection,
                )
                conn = get_connection()
                try:
                    fa_rules.check_booking(conn, chosen["id"], reg["user_id"], reg_email)
                except ValueError as exc:
                    messagebox.showwarning("Session Unavailable", str(exc), parent=win)
                    return
                finally:
                    conn.close()
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
                        "course": reg["course"],
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
                f"✓ You're registered for {reg['course']}"
                f"{' on ' + reg['preferred_date'] if reg['preferred_date'] else ''}.\n\n"
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
            "For any life-threatening emergency, call 999 immediately (NHS 111 for urgent advice).",
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
        """Show the scheduled course sessions (``first_aid_course_sessions``;
        staff add them in Registers & RIDDOR → Course sessions)."""
        win = self._resource_window("Workshop Schedule",
                                    "🗓  Upcoming Workshops & Events",
                                    width=680, height=500)
        body = tk.Frame(win, bg=self.colors["bg"])
        body.pack(fill="both", expand=True, padx=25, pady=10)
        sessions = self._fa_sessions()
        if not sessions:
            tk.Label(body, text="No sessions are scheduled at the moment.\n\nRegister your "
                                "interest below and the Health Centre will contact you when "
                                "the next date is set.",
                     font=("Segoe UI", 10), bg=self.colors["bg"], fg="#7f8c8d",
                     justify="center").pack(pady=30)
        for session in sessions[:20]:
            card = tk.Frame(body, bg=self.colors["card"], relief="raised", bd=1)
            card.pack(fill="x", pady=6)
            try:
                when = datetime.fromisoformat(str(session["starts_at"])).strftime(
                    "%a %d %b %Y\n%H:%M" if len(str(session["starts_at"])) > 10 else "%a %d %b %Y")
            except ValueError:
                when = str(session["starts_at"])
            tk.Label(card, text=when,
                     font=("Segoe UI", 10, "bold"), bg=self.colors["card"],
                     fg=self.colors["primary"], width=16, anchor="w").pack(
                side="left", padx=(15, 5), pady=12)
            info = tk.Frame(card, bg=self.colors["card"])
            info.pack(side="left", fill="x", expand=True, pady=8)
            tk.Label(info, text=session["course"], font=("Segoe UI", 11, "bold"),
                     bg=self.colors["card"], fg=self.colors["text"]).pack(
                anchor="w")
            tk.Label(info, text=f"📍 {session.get('location') or 'Location to be confirmed'}"
                                f"   👤 {session.get('trainer') or 'Trainer TBC'}",
                     font=("Segoe UI", 9), bg=self.colors["card"], fg="#7f8c8d").pack(anchor="w")
            tk.Label(info, text=(session.get("description") or "") +
                     f"  ({session['places_left']} of {session['capacity']} places left)",
                     font=("Segoe UI", 9),
                     bg=self.colors["card"], fg="#7f8c8d", wraplength=380,
                     justify="left").pack(anchor="w")
            if session["places_left"] > 0:
                tk.Button(card, text="Book", font=("Segoe UI", 9, "bold"),
                          bg=self.colors["accent"], fg="white", relief="flat", padx=12,
                          cursor="hand2",
                          command=lambda x=session: self._resource_register_course(
                              x["course"], session_id=x["id"])).pack(side="right", padx=10)
            else:
                tk.Label(card, text="Full", font=("Segoe UI", 9, "bold"),
                         bg=self.colors["card"], fg=self.colors["warning"]).pack(
                    side="right", padx=10)
        tk.Button(win, text="Register for a Course",
                  font=("Segoe UI", 9, "bold"), bg=self.colors["accent"],
                  fg="white", relief="flat", padx=15, pady=5, cursor="hand2",
                  command=lambda: self._resource_register_course(
                      "First Aid Workshop")).pack(pady=10)

    def _resource_kit_locations(self):
        """Show the campus directory of first aid kits and AEDs from the kit
        register (``first_aid_kits``)."""
        from education_system.systems.university.domains.health.application.health import (
            first_aid as fa_rules,
        )
        from education_system.systems.university.domains.health.infrastructure.health.storage import (
            get_connection,
        )
        win = self._resource_window("First Aid Kit & AED Locations",
                                    "🧰  First Aid Kit & AED Locations",
                                    width=680, height=520)
        try:
            conn = get_connection()
            try:
                items = fa_rules.kits(conn)
            finally:
                conn.close()
        except Exception:
            logger.exception("Could not read the kit register")
            items = []
        outer = tk.Frame(win, bg=self.colors["bg"])
        outer.pack(fill="both", expand=True, padx=25, pady=10)
        canvas = tk.Canvas(outer, bg=self.colors["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=self.colors["bg"])
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        if not items:
            tk.Label(body, text="No first aid kits or AEDs are on the register yet.\n"
                                "The health team adds them in Registers & RIDDOR → Kits & AEDs.",
                     font=("Segoe UI", 10), bg=self.colors["bg"], fg="#7f8c8d",
                     justify="center").pack(pady=30)
        for item in items:
            card = tk.Frame(body, bg=self.colors["card"], relief="raised", bd=1)
            card.pack(fill="x", pady=4)
            kind = fa_rules.KIT_KINDS.get(item["kind"], item["kind"])
            badge = self.colors["primary"] if item["kind"] == "aed" else self.colors["accent"]
            tk.Label(card, text="AED" if item["kind"] == "aed" else item["kind"].title(),
                     font=("Segoe UI", 8, "bold"),
                     bg=badge, fg="white", width=10).pack(side="left",
                                                          padx=10, pady=10)
            info = tk.Frame(card, bg=self.colors["card"])
            info.pack(side="left", fill="x", expand=True, pady=6)
            tk.Label(info, text=f"{item['location']} — {item['label']}",
                     font=("Segoe UI", 11, "bold"),
                     bg=self.colors["card"], fg=self.colors["text"]).pack(
                anchor="w")
            detail = item.get("detail") or kind
            if item["status"] != "in_service":
                detail += f"  ⚠ {item['status'].replace('_', ' ')}"
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
            "• One-tap call to Campus Security & 999",
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
            from education_system.systems.university.domains.health.infrastructure.health.storage import (
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
