"""Timetable GUI frame with weekly grid layout."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService
from education_system.college_system.modules.domain.timetable.services.room_service import RoomService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.i18n import t


class TimetableFrame(tk.Frame):
    """Timetable management frame with grid view."""

    _DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    _TIME_ROWS = [
        ("Period 1", "09:00", "10:00"),
        ("Period 2", "10:00", "11:00"),
        ("Break",    "11:00", "11:20"),
        ("Period 3", "11:20", "12:20"),
        ("Lunch",    "12:20", "13:00"),
        ("Period 4", "13:00", "14:00"),
        ("Period 5", "14:00", "15:00"),
    ]

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TimetableService(db_path)
        self._room_svc = RoomService(db_path)
        self._course_svc = CourseService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("timetable.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._generate_btn = ttk.Button(header, text=t("timetable.generate"),
                                        command=self._generate_timetable)
        # Initially hidden — shown for admin in refresh()

        self._my_btn = ttk.Button(header, text=t("timetable.my_timetable"),
                                   command=self._show_my_timetable)
        self._my_btn.pack(side="right", padx=20, pady=10)

        # Admin form (hidden for non-admin roles in refresh)
        self._slot_form = tk.LabelFrame(self, text=t("timetable.add_delete_slot"), bg="#ecf0f1", padx=10, pady=8)
        self._slot_form.pack(fill="x", padx=15, pady=(8, 0))

        row = tk.Frame(self._slot_form, bg="#ecf0f1")
        row.pack(fill="x", pady=2)

        tk.Label(row, text=t("timetable.course_id_colon"), bg="#ecf0f1").pack(side="left")
        self._course_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._course_var, width=8).pack(side="left", padx=5)

        tk.Label(row, text=t("timetable.day_colon"), bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._day_var = tk.StringVar(value="Mon")
        ttk.Combobox(row, textvariable=self._day_var, values=self._DAYS,
                     width=5, state="readonly").pack(side="left", padx=5)

        tk.Label(row, text=t("timetable.start_colon"), bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._start_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._start_var, width=6).pack(side="left", padx=5)

        tk.Label(row, text=t("timetable.end_colon"), bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._end_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._end_var, width=6).pack(side="left", padx=5)

        row2 = tk.Frame(self._slot_form, bg="#ecf0f1")
        row2.pack(fill="x", pady=2)

        tk.Label(row2, text=t("timetable.room_colon"), bg="#ecf0f1").pack(side="left")
        self._room_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self._room_var, width=12).pack(side="left", padx=5)

        tk.Label(row2, text=t("timetable.instructor_colon"), bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._instructor_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self._instructor_var, width=20).pack(side="left", padx=5)

        ttk.Button(row2, text=t("timetable.add_slot"), command=self._add_slot).pack(side="left", padx=(20, 0))
        ttk.Button(row2, text=t("timetable.delete_slot_by_id"), command=self._delete_slot).pack(side="left", padx=5)

        # Notebook for timetable grid + rooms tab
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=5, pady=5)

        self._grid_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._grid_tab, text=t("timetable.tab_timetable"))

        self._rooms_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._rooms_tab, text=t("timetable.tab_rooms"))
        self._build_rooms_tab()

        # Grid area — canvas with scrollbars for the weekly grid
        grid_container = tk.Frame(self._grid_tab, bg="#ecf0f1")
        grid_container.pack(fill="both", expand=True, padx=15, pady=10)

        self._canvas = tk.Canvas(grid_container, bg="#ecf0f1", highlightthickness=0)
        v_scroll = ttk.Scrollbar(grid_container, orient="vertical", command=self._canvas.yview)
        h_scroll = ttk.Scrollbar(grid_container, orient="horizontal", command=self._canvas.xview)
        self._grid_frame = tk.Frame(self._canvas, bg="#ecf0f1")

        self._grid_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._grid_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

    def _build_rooms_tab(self):
        """Build the Rooms management tab."""
        toolbar = tk.Frame(self._rooms_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=10, pady=5)

        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_rooms).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("timetable.add_room"), command=self._add_room_dialog).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="right", padx=5)

        columns = ("id", "room_code", "room_type", "capacity", "building", "status")
        self._room_tree = ttk.Treeview(self._rooms_tab, columns=columns,
                                        show="headings", selectmode="browse")
        for col, heading, w in [
            ("id", t("timetable.col_id"), 50), ("room_code", t("timetable.col_code"), 100),
            ("room_type", t("timetable.col_type"), 100), ("capacity", t("timetable.col_capacity"), 80),
            ("building", t("timetable.col_building"), 100), ("status", t("timetable.col_status"), 90),
        ]:
            self._room_tree.heading(col, text=heading)
            self._room_tree.column(col, width=w, anchor="center")

        room_vsb = ttk.Scrollbar(self._rooms_tab, orient="vertical",
                                  command=self._room_tree.yview)
        self._room_tree.configure(yscrollcommand=room_vsb.set)
        self._room_tree.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        room_vsb.pack(side="right", fill="y", pady=5)

    def _load_rooms(self):
        self._room_tree.delete(*self._room_tree.get_children())
        try:
            rooms = self._room_svc.list_rooms()
            for r in rooms:
                self._room_tree.insert("", "end", values=(
                    r["id"], r["room_code"], r["room_type"],
                    r["capacity"], r.get("building", ""), r["status"],
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _add_room_dialog(self):
        code = simpledialog.askstring(t("timetable.add_room"), t("timetable.room_code_prompt"), parent=self)
        if not code:
            return
        try:
            room = self._room_svc.create_room(room_code=code)
            messagebox.showinfo(t("common.success"), t("timetable.room_created", code=code, id=room['id']))
            self._load_rooms()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------
    # Refresh / data loading
    # ------------------------------------------------------------------

    def refresh(self):
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")

        # Show/hide Generate Timetable button (admin only)
        if role == "admin":
            self._generate_btn.pack(side="right", padx=(0, 10), pady=10)
        else:
            self._generate_btn.pack_forget()

        # Show/hide Add/Delete Slot form (admin and staff only)
        if role not in ("admin", "staff"):
            self._slot_form.pack_forget()

        self._load_grid()
        self._load_rooms()

    def _fetch_all_slots(self) -> list[dict]:
        """Fetch all timetable slots from the database."""
        from education_system.college_system.infrastructure.database.db import connect
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                """SELECT ts.*, c.course_code, c.title as course_title
                   FROM timetable_slots ts
                   JOIN courses c ON ts.course_id = c.id
                   ORDER BY ts.day_of_week, ts.start_time"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _load_grid(self, slots: list[dict] | None = None, show_study: bool = False):
        """Build the weekly grid from timetable slots.

        When *show_study* is True, empty teaching cells are labelled
        "Study Period" instead of showing a dash (used for My Timetable).
        """
        # Clear previous grid
        for widget in self._grid_frame.winfo_children():
            widget.destroy()

        if slots is None:
            try:
                slots = self._fetch_all_slots()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
                return

        # Organise slots into a lookup: (day, start_time) -> list of entries
        grid_data: dict[tuple[str, str], list[dict]] = {}
        for day in self._DAYS:
            for _, start, _ in self._TIME_ROWS:
                grid_data[(day, start)] = []

        for s in slots:
            key = (s["day_of_week"], s["start_time"])
            if key in grid_data:
                grid_data[key].append(s)

        # Header row — Time column + day columns
        tk.Label(self._grid_frame, text=t("timetable.time"), font=("Arial", 10, "bold"),
                 relief="solid", borderwidth=2, bg="#4a90e2", fg="white",
                 width=14, height=2).grid(row=0, column=0, padx=1, pady=1, sticky="nsew")

        for col, day in enumerate(self._DAYS, 1):
            tk.Label(self._grid_frame, text=day, font=("Arial", 10, "bold"),
                     relief="solid", borderwidth=2, bg="#4a90e2", fg="white",
                     width=20, height=2).grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

        # Time rows
        for row_idx, (label, start, end) in enumerate(self._TIME_ROWS, 1):
            is_break = label in ("Break", "Lunch")

            # Time label
            time_text = f"{label}\n{start}-{end}"
            bg_time = "#f5d6c8" if is_break else "#e8f4f8"
            tk.Label(self._grid_frame, text=time_text, font=("Arial", 9, "bold"),
                     relief="solid", borderwidth=2, bg=bg_time,
                     width=14, height=4).grid(
                row=row_idx, column=0, padx=1, pady=1, sticky="nsew")

            for col, day in enumerate(self._DAYS, 1):
                if is_break:
                    cell = tk.Frame(self._grid_frame, relief="solid", borderwidth=2,
                                    bg="#e0e0e0", width=180, height=80)
                    cell.grid(row=row_idx, column=col, padx=1, pady=1, sticky="nsew")
                    cell.grid_propagate(False)
                    tk.Label(cell, text=label, font=("Arial", 9, "italic"),
                             bg="#e0e0e0", fg="#666").place(relx=0.5, rely=0.5, anchor="center")
                    continue

                entries = grid_data.get((day, start), [])
                has_entries = bool(entries)

                if has_entries:
                    bg_cell = "#d4edda"
                    cell = tk.Frame(self._grid_frame, relief="solid", borderwidth=2,
                                    bg=bg_cell, width=180, height=80)
                    cell.grid(row=row_idx, column=col, padx=1, pady=1, sticky="nsew")
                    cell.grid_propagate(False)

                    inner = tk.Frame(cell, bg=bg_cell)
                    inner.pack(fill="both", expand=True, padx=3, pady=3)

                    for i, entry in enumerate(entries):
                        if i >= 2:
                            tk.Label(inner, text=f"+ {len(entries) - 2} more...",
                                     font=("Arial", 7, "italic"),
                                     bg=bg_cell, fg="#155724").pack(anchor="w", pady=1)
                            break

                        box = tk.Frame(inner, relief="raised", borderwidth=1,
                                       bg="#c3e6cb", padx=2, pady=2)
                        box.pack(fill="x", pady=1)

                        tk.Label(box, text=entry.get("course_code", ""),
                                 font=("Arial", 8, "bold"),
                                 bg="#c3e6cb", fg="#155724").pack(anchor="w")

                        room_text = entry.get("room", "") or ""
                        teacher_text = entry.get("instructor_name", "") or ""
                        detail = f"{room_text}  {teacher_text}".strip()
                        if detail:
                            tk.Label(box, text=detail,
                                     font=("Arial", 7),
                                     bg="#c3e6cb", fg="#155724").pack(anchor="w")

                elif show_study:
                    # Show study period for personal timetable view
                    bg_study = "#fff3cd"
                    cell = tk.Frame(self._grid_frame, relief="solid", borderwidth=2,
                                    bg=bg_study, width=180, height=80)
                    cell.grid(row=row_idx, column=col, padx=1, pady=1, sticky="nsew")
                    cell.grid_propagate(False)
                    tk.Label(cell, text=t("timetable.study_period"),
                             font=("Arial", 9, "bold"),
                             bg=bg_study, fg="#856404").place(relx=0.5, rely=0.5, anchor="center")

                else:
                    cell = tk.Frame(self._grid_frame, relief="solid", borderwidth=2,
                                    bg="white", width=180, height=80)
                    cell.grid(row=row_idx, column=col, padx=1, pady=1, sticky="nsew")
                    cell.grid_propagate(False)
                    tk.Label(cell, text="-", font=("Arial", 12),
                             bg="white", fg="#ccc").place(relx=0.5, rely=0.5, anchor="center")

        # Configure grid weights
        for i in range(len(self._TIME_ROWS) + 1):
            self._grid_frame.grid_rowconfigure(i, weight=0, minsize=80 if i > 0 else 40)
        for i in range(len(self._DAYS) + 1):
            self._grid_frame.grid_columnconfigure(i, weight=0, minsize=180 if i > 0 else 120)

    # ------------------------------------------------------------------
    # Slot actions
    # ------------------------------------------------------------------

    def _add_slot(self):
        try:
            cid = int(self._course_var.get())
            slot = self._svc.add_slot(
                cid,
                self._day_var.get(),
                self._start_var.get(),
                self._end_var.get(),
                self._room_var.get() or None,
                self._instructor_var.get() or None,
            )
            messagebox.showinfo(t("common.success"), t("timetable.slot_added", id=slot['id']))
            self._load_grid()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_slot(self):
        slot_id_str = simpledialog.askstring(
            t("timetable.delete_slot"), t("timetable.enter_slot_id"),
            parent=self,
        )
        if not slot_id_str:
            return
        try:
            slot_id = int(slot_id_str)
            self._svc.delete_slot(slot_id)
            messagebox.showinfo(t("common.success"), t("timetable.slot_deleted", id=slot_id))
            self._load_grid()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------
    # Generate timetable
    # ------------------------------------------------------------------

    def _generate_timetable(self):
        schedule_info = (
            "This will replace ALL existing timetable slots with an auto-generated schedule:\n\n"
            "  Period 1:  09:00 - 10:00\n"
            "  Period 2:  10:00 - 11:00\n"
            "  Break:     11:00 - 11:20\n"
            "  Period 3:  11:20 - 12:20\n"
            "  Lunch:     12:20 - 13:00\n"
            "  Period 4:  13:00 - 14:00\n"
            "  Period 5:  14:00 - 15:00\n\n"
            "Each course rotates through different periods across the week.\n"
            "Double lessons (2hrs) are added on 2 days per course.\n"
            "Remaining gaps show as Study Periods on student timetables.\n\n"
            "Continue?"
        )
        if not messagebox.askyesno(t("timetable.generate"), schedule_info):
            return

        try:
            result = self._svc.generate_full_timetable()
            summary = (
                f"Timetable generated successfully!\n\n"
                f"Slots created: {result['slots_created']}\n"
                f"Double lessons added: {result.get('doubles_added', 0)}\n"
                f"Courses scheduled: {result['courses_scheduled']}/{result['courses_total']}"
            )
            if result["partial"]:
                summary += f"\nPartially scheduled: {', '.join(result['partial'])}"
            if result["unscheduled"]:
                summary += f"\nUnscheduled: {', '.join(result['unscheduled'])}"

            messagebox.showinfo(t("timetable.generation_complete"), summary)
            self._load_grid()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------
    # My timetable
    # ------------------------------------------------------------------

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._room_tree, default_filename="timetable_rooms.csv")

    def _show_my_timetable(self):
        try:
            from education_system.college_system.infrastructure.database.db import connect
            conn = connect(self._db_path)
            try:
                student = conn.execute(
                    "SELECT id FROM students WHERE user_id = ?",
                    (self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None,),
                ).fetchone()
            finally:
                conn.close()

            if not student:
                messagebox.showinfo(t("common.info"), t("timetable.no_student_record"))
                return

            slots = self._svc.get_student_timetable(student["id"])
            self._load_grid(slots=slots, show_study=True)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
