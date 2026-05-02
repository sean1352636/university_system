# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

# Import utility functions
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    _safe_entry_insert,
    _safe_set_combobox,
)

# Import i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import database connection
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — single source of truth for student-row loading and
# column access.
#
# Pre-8.117.16 this file had two near-identical loaders (``view_students``,
# ``view_students_in_window``) and two near-identical double-click handlers.
# The records list also drilled into ``students[0]``..``students[10]``
# positionally, which broke whenever the schema gained a column. Both
# loaders now delegate to ``_load_students_into`` and ``show_student_details``
# uses ``_row_get`` for column access — so adding a column is no longer a
# silent risk.
# ---------------------------------------------------------------------------

# Canonical column list for the records list view. Matches what the tree
# treeview headers expect (id / full_name / email / course / reg_date).
_LIST_COLS_SQL = (
    "student_id, first_name, middle_name, last_name, "
    "email_address, course, registration_datetime"
)


def _row_get(row, key, default=None):
    """Read a column from a sqlite3 row by name with a graceful fallback.

    ``sqlite3.Row`` doesn't expose ``.get`` so a missing column raises
    IndexError. This wrapper turns that into the supplied default so
    we can read newer columns without breaking on older databases."""
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return default


def _load_students_into(self, tree, *, search_term=None, search_field=None):
    """Single canonical loader for the records list treeview.

    Used by ``view_students`` (legacy panel hook used by
    ``student_crud_gui`` after CRUD), ``view_students_in_window`` (the
    Toplevel records window) and the inline search filter. Always
    selects an explicit named column list — never ``SELECT *`` — so
    schema additions can't shift indices.

    *search_term* + *search_field*, when given, narrow the result set
    server-side. Field is validated against an allow-list before being
    interpolated into the SQL because parameter substitution doesn't
    apply to identifiers."""
    if tree is None:
        return
    try:
        if not tree.winfo_exists():
            return
    except tk.TclError:
        return

    # Clear existing rows
    try:
        for item in tree.get_children():
            tree.delete(item)
    except tk.TclError:
        return

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            messagebox.showerror(
                _t("common.error"),
                _t("student.failed_load_student_data",
                   error="database connection unavailable"),
            )
            return

        # Default ordering (by surname, forename); search overrides
        # the WHERE clause but keeps the same SELECT list + ORDER BY.
        params = []
        where = ""
        if self.auth and not self.auth.check_permission('view_any_student'):
            where = "WHERE student_id = ?"
            params.append(self.auth.current_user.get('student_id'))
        elif search_term and search_field:
            allowed = {
                'first_name', 'last_name', 'student_id',
                'course', 'email_address',
            }
            if search_field in allowed:
                safe = validate_identifier(search_field, "column")
                if search_field == 'student_id':
                    where = f"WHERE [{safe}] = ?"
                    params.append(search_term)
                else:
                    where = f"WHERE LOWER([{safe}]) LIKE LOWER(?)"
                    params.append(f"%{search_term}%")

        sql = (
            f"SELECT {_LIST_COLS_SQL} FROM students "
            f"{where} ORDER BY last_name, first_name"
        )
        cursor = conn.cursor()
        cursor.execute(sql, params)

        for r in cursor.fetchall():
            # Tuple-positional but bound to our explicit SELECT list,
            # not to the underlying schema — order matches _LIST_COLS_SQL.
            sid, first, middle, last, email, course, reg = r
            full_name = " ".join(
                p for p in (first, middle, last) if p
            ).strip() or sid
            tree.insert(
                "", tk.END,
                values=(
                    sid,
                    full_name,
                    email or "",
                    course or "",
                    (reg[:10] if reg else "N/A"),
                ),
            )
    except tk.TclError:
        return
    except Exception as exc:
        messagebox.showerror(
            _t("common.error"),
            _t("student.failed_load_student_data", error=str(exc)),
        )
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

def show_student_records(self):
    """Show student records interface inside the main GUI's content
    area when a workspace is available, or as a Toplevel otherwise.

    Pre-8.117.38 always opened a 1400×800 ``tk.Toplevel(self.root)``.
    User asked for it to fit inside the main content section instead.
    Now goes through ``UnifiedManagementGUI.open_in_workspace``
    (8.117.18 mechanism) when the post-login workspace notebook is
    alive — Library uses Toplevel-style sizing (8.117.34), but the
    Student Records list view fits a tab-frame nicely (less dense
    than Library's notebook-of-notebooks)."""
    # Check if current user is a student - if so, show only their own record
    if self.auth and self.auth.current_user:
        user_role = self.auth.current_user.get('role', '')

        # If student, directly show their own record
        if user_role == 'student':
            student_id = self.auth.current_user.get('student_id') or self.auth.current_user.get('username')
            if student_id:
                print(f"✅ Student user '{student_id}' viewing their own record")
                self.show_student_details(student_id)
                return
            else:
                messagebox.showerror(_t("common.error"), _t("student.unable_retrieve_id"))
                return

    title = _t("student.records_management")

    def _build(host, close_action):
        """Construct the records UI inside *host*. *close_action* is
        a callable supplied by the caller — calls ``nb.forget(host)``
        when ``host`` is a workspace tab frame, ``host.destroy()``
        when it's a Toplevel inner frame."""
        _build_student_records(self, host, close_action)

    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        # Workspace path: tab inside the main GUI's content notebook.
        # ``open_in_workspace`` returns the new tab Frame; the
        # close-action removes that tab.
        nb = getattr(self, "workspace_notebook", None)
        def _close_tab(host=None, _nb=nb):
            try:
                if _nb is not None and host is not None:
                    _nb.forget(host)
            except Exception:
                pass
        # Builder receives the tab frame + the close action bound
        # to it.
        opener(title, lambda host: _build(host, lambda: _close_tab(host)))
        return

    # Fallback: classic Toplevel — same shape as pre-8.117.38.
    records_window = tk.Toplevel(self.root)
    _install_clean_close(records_window)
    records_window.title(title)
    records_window.geometry("1400x800")
    records_window.transient(self.root)
    main_outer = ttk.Frame(records_window)
    main_outer.pack(fill=tk.BOTH, expand=True)
    _build(main_outer, lambda: records_window.destroy())


def _build_student_records(self, host, close_action):
    """Internal: build the records list UI inside *host*. Refactored
    out of ``show_student_records`` (8.117.38) so the same widget
    construction works whether *host* is a workspace tab Frame or a
    Toplevel inner frame.

    *close_action* is a no-arg callable that closes the host —
    forgetting the workspace tab or destroying the Toplevel."""
    main_frame = ttk.Frame(host, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(main_frame, text=_t("student.records_management"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Action buttons frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Button(button_frame, text=_t("student.create_student"),
              command=self.create_student_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("student.export_data"),
              command=self.export_data_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.refresh"),
              command=lambda: self.view_students_in_window(tree)).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.close"),
              command=close_action).pack(side=tk.RIGHT, padx=5)

    # Inline search bar — replaces the modal search dialog. Filters the
    # currently-loaded rows in-memory on KeyRelease so the result set
    # narrows as the user types. The legacy ``search_students_dialog``
    # is still defined for any external caller but the records window
    # no longer surfaces it as a button.
    search_bar = ttk.Frame(main_frame)
    search_bar.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(search_bar, text=_t("student.search_term")).pack(side=tk.LEFT, padx=(0, 6))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_bar, textvariable=search_var, width=40)
    search_entry.pack(side=tk.LEFT)
    status_var = tk.StringVar(value="")
    ttk.Label(search_bar, textvariable=status_var,
              foreground='#555555').pack(side=tk.LEFT, padx=(12, 0))
    ttk.Button(search_bar, text="✕",
               command=lambda: search_var.set(""),
               width=3).pack(side=tk.LEFT, padx=(6, 0))

    # Create student list interface
    records_frame = ttk.LabelFrame(main_frame, text=_t("student.records"), padding="10")
    records_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # Create treeview in this window
    tree_frame = ttk.Frame(records_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (_t("student.col_id"), _t("student.col_name"), _t("student.col_email"), _t("student.col_course"), _t("student.col_reg_date"))
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)

    # Configure columns + bind heading-clicks for ascending/descending
    # sort by column. Standard ttk pattern — store the most-recent
    # sort direction per column so a second click reverses.
    sort_state = {"col": None, "reverse": False}

    def _sort_by(col):
        try:
            data = [
                (tree.set(k, col), k) for k in tree.get_children("")
            ]
            # Numeric-aware sort: try to coerce so "10" sorts after "9"
            def _key(pair):
                v = pair[0]
                try:
                    return (0, float(v))
                except (TypeError, ValueError):
                    return (1, (v or "").lower())
            reverse = sort_state["col"] == col and not sort_state["reverse"]
            data.sort(key=_key, reverse=reverse)
            for index, (_v, k) in enumerate(data):
                tree.move(k, "", index)
            sort_state["col"] = col
            sort_state["reverse"] = reverse
            # Visual marker so the user can see sort state
            for c in columns:
                tree.heading(c, text=c)
            tree.heading(col, text=f"{col}  {'▼' if reverse else '▲'}")
        except tk.TclError:
            pass

    for col in columns:
        tree.heading(col, text=col, command=lambda c=col: _sort_by(c))
        tree.column(col, width=200)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Bind double-click event
    tree.bind('<Double-1>', lambda event: self.on_student_double_click_window(event, tree))

    # Right-click cross-jumps to every module keyed by student_id.
    # The student record is the canonical hub — for the first time this
    # tree points outward (Email Manager, Finance, Library, Audit Log,
    # Loyalty / Careers snapshots, Course Mgmt) instead of just being
    # the destination everything else jumps to.
    try:
        from education_system.university_system.modules.shared.gui.main.students._cross_links import (
            attach_cross_link_menu,
        )
        attach_cross_link_menu(tree, parent=host, app=self)
    except Exception:
        logger.debug("student records cross-link menu unavailable", exc_info=True)

    # Store reference to this window's tree
    self.student_tree = tree

    # Load student data
    self.view_students_in_window(tree)

    # ── Inline search filter ────────────────────────────────────────
    # Snapshot every loaded row so KeyRelease can rebuild from the
    # cached snapshot rather than re-querying the DB on every
    # keystroke. Refreshing the tree (e.g. after a CRUD operation)
    # rebuilds the snapshot.
    full_rows: list[tuple] = []

    def _snapshot():
        full_rows.clear()
        for iid in tree.get_children(""):
            full_rows.append(tuple(tree.item(iid, "values") or ()))

    def _refresh_status():
        n = len(tree.get_children(""))
        total = len(full_rows)
        if n == total:
            status_var.set(f"{n} student(s)")
        else:
            status_var.set(f"{n} of {total} student(s)")

    def _apply_filter(*_args):
        term = (search_var.get() or "").strip().lower()
        try:
            for iid in tree.get_children(""):
                tree.delete(iid)
        except tk.TclError:
            return
        for row in full_rows:
            if not term or any(term in str(v).lower() for v in row):
                tree.insert("", tk.END, values=row)
        _refresh_status()

    _snapshot()
    _refresh_status()
    search_var.trace_add("write", _apply_filter)
    search_entry.bind("<Escape>", lambda _e: search_var.set(""))

    # Wrap the existing refresh button so a re-load also re-snapshots
    # for the in-memory filter. Walk the buttons in button_frame to
    # find the Refresh widget by its translated label.
    refresh_label = _t("gui.refresh")
    for child in button_frame.winfo_children():
        try:
            if isinstance(child, ttk.Button) and child.cget("text") == refresh_label:
                child.configure(command=lambda: (
                    self.view_students_in_window(tree),
                    _snapshot(),
                    _apply_filter(),
                ))
                break
        except tk.TclError:
            pass
def create_student_treeview(self, parent):
    """Create treeview widget for displaying student data"""
    tree_frame = ttk.Frame(parent)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (_t("student.col_id"), _t("student.col_name"), _t("student.col_email"), _t("student.col_course"), _t("student.col_reg_date"))
    self.student_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)

    # Configure columns
    for col in columns:
        self.student_tree.heading(col, text=col)
        self.student_tree.column(col, width=150)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.student_tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.student_tree.xview)
    self.student_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.student_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Bind events
    self.student_tree.bind('<Double-1>', self.on_student_double_click)
def view_students(self):
    """Refresh the panel-mode student tree (used by ``student_crud_gui``
    after create / update / delete operations). Thin delegate over
    :func:`_load_students_into` — kept as a method for backward compat
    with ``hasattr(self, 'view_students')`` checks elsewhere."""
    tree = getattr(self, 'student_tree', None)
    if tree is None:
        return
    _load_students_into(self, tree)


def view_students_in_window(self, tree):
    """Refresh the records-window tree. Thin delegate."""
    _load_students_into(self, tree)


def _double_click_handler(self, tree):
    """Shared double-click handler — drills the selected student into
    the detail window. Used by both the panel-mode and window-mode
    trees; previously had two near-identical copies."""
    try:
        if tree is None or not tree.winfo_exists():
            return
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0]).get('values', []) or []
        if values:
            self.show_student_details(values[0])
    except (AttributeError, IndexError, tk.TclError):
        messagebox.showerror(_t("common.error"),
                              _t("student.unable_access_details"))
    except Exception as e:
        messagebox.showerror(_t("common.error"),
                              _t("student.error_occurred", error=str(e)))


def on_student_double_click(self, event):
    """Panel-mode double-click handler."""
    _double_click_handler(self, getattr(self, 'student_tree', None))


def on_student_double_click_window(self, event, tree):
    """Window-mode double-click handler."""
    _double_click_handler(self, tree)
def show_student_details(self, student_id):
    """Enhanced student details viewer with comprehensive information display.

    Writes a GDPR-relevant audit entry naming the viewer + the subject
    student before opening the window, so every read of a student
    record is auditable. The write is best-effort — a transient audit
    DB failure won't block the viewer from rendering, but a sustained
    gap shows up as missing rows in the audit log itself which is a
    different (and detectable) compliance signal."""
    try:
        from education_system.university_system.modules.shared.gui.main.students._cross_links import (
            audit_student_view,
        )
        viewer = self.auth.current_user if self.auth else None
        if viewer:
            audit_student_view(
                viewer.get('id'),
                viewer.get('username'),
                student_id,
            )
    except Exception:
        logger.debug("student view audit hook failed", exc_info=True)

    detail_window = tk.Toplevel(self.root)
    _install_clean_close(detail_window)
    detail_window.title(_t("student_details.window_title", student_id=student_id))
    detail_window.geometry("900x700")
    detail_window.transient(self.root)

    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student_details.error_db_connection"))
            detail_window.destroy()
            return

        # Switch to a Row factory so we can index columns by name
        # (``student['first_name']``) instead of position. Column
        # additions in the schema can no longer shift indices and
        # silently break this view.
        import sqlite3 as _sqlite3
        try:
            conn.row_factory = _sqlite3.Row
        except Exception:
            pass
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            messagebox.showerror(_t("common.error"), _t("student_details.error_student_not_found"))
            detail_window.destroy()
            return

        # Create notebook for tabbed interface
        notebook = ttk.Notebook(detail_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information Tab
        personal_tab = ttk.Frame(notebook)
        notebook.add(personal_tab, text=_t("student_details.tab_personal_info"))

        # ── Personal info tab: structured cards instead of monospaced blob ──
        na = _t("student_details.na")
        s_id = _row_get(student, 'student_id')
        s_email = _row_get(student, 'email_address')
        s_title = _row_get(student, 'title')
        s_first = _row_get(student, 'first_name')
        s_middle = _row_get(student, 'middle_name')
        s_last = _row_get(student, 'last_name')
        s_gender = _row_get(student, 'gender')
        s_dob = _row_get(student, 'dob')
        s_age = _row_get(student, 'age')
        s_course = _row_get(student, 'course')
        s_reg = _row_get(student, 'registration_datetime')

        title = s_title if s_title else na
        first_name = s_first if s_first else na
        middle_name = s_middle if s_middle else ''
        last_name = s_last if s_last else na
        gender = s_gender.title() if s_gender else na
        course = s_course if s_course else na

        name_parts = [p for p in (s_title, s_first, s_middle, s_last) if p]
        full_name = ' '.join(name_parts) if name_parts else na

        # Hero header
        hero = ttk.Frame(personal_tab, padding=(20, 14))
        hero.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(hero, text=full_name, font=('Arial', 18, 'bold')).pack(anchor='w')
        sub_bits = []
        if s_id:
            sub_bits.append(f"ID: {s_id}")
        if course not in (na, ''):
            sub_bits.append(course)
        if s_email:
            sub_bits.append(s_email)
        if sub_bits:
            ttk.Label(hero, text=' · '.join(sub_bits),
                      font=('Arial', 10), foreground='#555555').pack(anchor='w', pady=(2, 0))
        ttk.Separator(personal_tab, orient='horizontal').pack(fill=tk.X, padx=10, pady=(8, 4))

        # Scrollable container for the cards (works on small windows)
        canvas = tk.Canvas(personal_tab, borderwidth=0, highlightthickness=0)
        vbar = ttk.Scrollbar(personal_tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side='left', fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        vbar.pack(side='right', fill='y', pady=(0, 10))

        cards = ttk.Frame(canvas)
        cards_window = canvas.create_window((0, 0), window=cards, anchor='nw')

        def _on_inner(_event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas(event):
            canvas.itemconfigure(cards_window, width=event.width)

        cards.bind('<Configure>', _on_inner)
        canvas.bind('<Configure>', _on_canvas)

        def _add_field(parent, row, label, value):
            ttk.Label(parent, text=label, font=('Arial', 10, 'bold'),
                      foreground='#333333').grid(row=row, column=0, sticky='w', padx=(0, 16), pady=3)
            ttk.Label(parent, text=str(value), font=('Arial', 10)).grid(
                row=row, column=1, sticky='w', pady=3,
            )

        # Card 1 — Identity
        identity = ttk.LabelFrame(cards, text=_t("student_details.header_personal_info"),
                                  padding=15)
        identity.pack(fill=tk.X, pady=6)
        identity.columnconfigure(1, weight=1)
        years_text = _t("student_details.label_years")
        _add_field(identity, 0, _t("student_details.label_student_id"), s_id or na)
        _add_field(identity, 1, _t("student_details.label_email_address"), s_email or na)
        _add_field(identity, 2, _t("student_details.label_title"), title)
        _add_field(identity, 3, _t("student_details.label_first_name"), first_name)
        _add_field(identity, 4, _t("student_details.label_middle_name"), middle_name or na)
        _add_field(identity, 5, _t("student_details.label_last_name"), last_name)
        _add_field(identity, 6, _t("student_details.label_full_name"), full_name)

        # Card 2 — Demographics
        demographics = ttk.LabelFrame(cards, text=_t("student_details.header_demographics"),
                                      padding=15)
        demographics.pack(fill=tk.X, pady=6)
        demographics.columnconfigure(1, weight=1)
        age_value = (
            f"{s_age} {years_text}" if s_age not in (None, '') else na
        )
        _add_field(demographics, 0, _t("student_details.label_gender"), gender)
        _add_field(demographics, 1, _t("student_details.label_date_of_birth"), s_dob or na)
        _add_field(demographics, 2, _t("student_details.label_age"), age_value)

        # Card 3 — Academic info
        academic_info_card = ttk.LabelFrame(cards, text=_t("student_details.header_academic_info"),
                                            padding=15)
        academic_info_card.pack(fill=tk.X, pady=6)
        academic_info_card.columnconfigure(1, weight=1)
        _add_field(academic_info_card, 0, _t("student_details.label_course"), course)
        _add_field(academic_info_card, 1, _t("student_details.label_registration"),
                   s_reg or na)

        # Academic Information Tab
        academic_tab = ttk.Frame(notebook)
        notebook.add(academic_tab, text=_t("student_details.tab_academic_records"))

        # Top bar: summary line on the left, refresh on the right
        top_bar = ttk.Frame(academic_tab)
        top_bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        academic_summary = ttk.Label(top_bar, text="", font=('Arial', 10, 'italic'),
                                     foreground='#555555')
        academic_summary.pack(side=tk.LEFT)
        ttk.Button(
            top_bar,
            text=_t("common.refresh", default="Refresh"),
            command=lambda: self._load_academic_data(
                student_id, modules_tree, grades_tree, attendance_tree,
                academic_summary, na,
            ),
        ).pack(side=tk.RIGHT)

        # Scrollable container — three Treeviews can't all fit when the
        # window is 700px tall, so wrap them in a Canvas + Scrollbar.
        ac_canvas = tk.Canvas(academic_tab, borderwidth=0, highlightthickness=0)
        ac_vbar = ttk.Scrollbar(academic_tab, orient='vertical', command=ac_canvas.yview)
        ac_canvas.configure(yscrollcommand=ac_vbar.set)
        ac_canvas.pack(side='left', fill=tk.BOTH, expand=True, padx=(10, 0), pady=(8, 10))
        ac_vbar.pack(side='right', fill='y', pady=(8, 10))

        ac_inner = ttk.Frame(ac_canvas)
        ac_window = ac_canvas.create_window((0, 0), window=ac_inner, anchor='nw')

        def _on_ac_inner(_event):
            ac_canvas.configure(scrollregion=ac_canvas.bbox('all'))

        def _on_ac_canvas(event):
            ac_canvas.itemconfigure(ac_window, width=event.width)

        ac_inner.bind('<Configure>', _on_ac_inner)
        ac_canvas.bind('<Configure>', _on_ac_canvas)

        # ── Mousewheel scrolling, scoped to the academic-tab canvas ──
        # The previous implementation used ``bind_all`` (process-global)
        # which leaked: closing this detail window did not unbind, so
        # the next Toplevel's wheel events fired callbacks against a
        # destroyed canvas and produced
        # ``TclError: invalid command name ".!toplevel.!canvas"``
        # on stderr. Now bound directly on the canvas + the inner frame
        # + its children via ``bind`` (window-local), so they go away
        # naturally when the detail window is destroyed.
        def _on_ac_wheel(event):
            try:
                delta = -1 if (getattr(event, 'num', None) == 5
                               or getattr(event, 'delta', 0) < 0) else 1
                ac_canvas.yview_scroll(-delta, 'units')
            except tk.TclError:
                # Canvas already destroyed — race with window close.
                pass
            return "break"

        def _bind_wheel_recursive(widget):
            try:
                for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                    widget.bind(seq, _on_ac_wheel, add="+")
                for child in widget.winfo_children():
                    _bind_wheel_recursive(child)
            except tk.TclError:
                pass

        # Bind on the canvas itself + the scrolling inner frame; the
        # children-walk catches the Treeviews and labels added below
        # so wheel events anywhere in the academic tab scroll the
        # outer canvas. Re-bind whenever the inner frame's contents
        # change so newly-added widgets pick up the binding.
        ac_canvas.bind('<MouseWheel>', _on_ac_wheel, add="+")
        ac_canvas.bind('<Button-4>', _on_ac_wheel, add="+")
        ac_canvas.bind('<Button-5>', _on_ac_wheel, add="+")
        ac_inner.bind('<Map>', lambda _e: _bind_wheel_recursive(ac_inner))

        # Three stacked panels with Treeviews (now inside the scrollable inner frame)
        modules_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_enrolled_modules", default="Enrolled Modules"),
            padding=10,
        )
        modules_frame.pack(fill=tk.X, padx=4, pady=(0, 6))
        modules_tree = ttk.Treeview(
            modules_frame, columns=("type", "code", "name"),
            show="headings", height=6,
        )
        modules_tree.heading("type", text="Type")
        modules_tree.heading("code", text="Code")
        modules_tree.heading("name", text="Module Name")
        modules_tree.column("type", width=110, anchor="w")
        modules_tree.column("code", width=110, anchor="w")
        modules_tree.column("name", width=400, anchor="w")
        mod_vsb = ttk.Scrollbar(modules_frame, orient="vertical", command=modules_tree.yview)
        modules_tree.configure(yscrollcommand=mod_vsb.set)
        modules_tree.pack(side="left", fill=tk.X, expand=True)
        mod_vsb.pack(side="right", fill="y")
        modules_tree.tag_configure("group", background="#eef2f7", font=('Arial', 10, 'bold'))

        grades_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_grades_assessments", default="Grades & Assessments"),
            padding=10,
        )
        grades_frame.pack(fill=tk.X, padx=4, pady=6)
        grades_tree = ttk.Treeview(
            grades_frame, columns=("module", "assessment", "grade", "date"),
            show="headings", height=6,
        )
        grades_tree.heading("module", text="Module")
        grades_tree.heading("assessment", text="Assessment")
        grades_tree.heading("grade", text="Grade")
        grades_tree.heading("date", text="Date")
        grades_tree.column("module", width=110, anchor="w")
        grades_tree.column("assessment", width=300, anchor="w")
        grades_tree.column("grade", width=80, anchor="center")
        grades_tree.column("date", width=160, anchor="w")
        gr_vsb = ttk.Scrollbar(grades_frame, orient="vertical", command=grades_tree.yview)
        grades_tree.configure(yscrollcommand=gr_vsb.set)
        grades_tree.pack(side="left", fill=tk.X, expand=True)
        gr_vsb.pack(side="right", fill="y")
        grades_tree.tag_configure("good", foreground="#1b7f3a")
        grades_tree.tag_configure("warn", foreground="#b87a00")
        grades_tree.tag_configure("fail", foreground="#b00020")

        attendance_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_recent_attendance", default="Recent Attendance"),
            padding=10,
        )
        attendance_frame.pack(fill=tk.X, padx=4, pady=(6, 0))
        attendance_tree = ttk.Treeview(
            attendance_frame, columns=("date", "module", "status", "notes"),
            show="headings", height=6,
        )
        attendance_tree.heading("date", text="Date")
        attendance_tree.heading("module", text="Module")
        attendance_tree.heading("status", text="Status")
        attendance_tree.heading("notes", text="Notes")
        attendance_tree.column("date", width=120, anchor="w")
        attendance_tree.column("module", width=110, anchor="w")
        attendance_tree.column("status", width=100, anchor="center")
        attendance_tree.column("notes", width=320, anchor="w")
        att_vsb = ttk.Scrollbar(attendance_frame, orient="vertical", command=attendance_tree.yview)
        attendance_tree.configure(yscrollcommand=att_vsb.set)
        attendance_tree.pack(side="left", fill=tk.X, expand=True)
        att_vsb.pack(side="right", fill="y")
        attendance_tree.tag_configure("present", foreground="#1b7f3a")
        attendance_tree.tag_configure("late", foreground="#b87a00")
        attendance_tree.tag_configure("absent", foreground="#b00020")

        self._load_academic_data(
            student_id, modules_tree, grades_tree, attendance_tree,
            academic_summary, na,
        )

        # Library activity tab — embedded summary widget driven by the
        # cross-module API. Renders an empty/zero panel when the
        # student has no library records.
        try:
            from education_system.university_system.modules.domain.academics.gui.library.cross_module_api import (
                LibrarySummaryFrame,
            )
            library_tab = ttk.Frame(notebook)
            notebook.add(library_tab, text="📚 Library")
            LibrarySummaryFrame(
                library_tab,
                user_id=student_id,
                on_open_library=getattr(self, "show_library_management", None),
            ).pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not embed LibrarySummaryFrame")

        # ── Summary tab ─────────────────────────────────────────
        # Cross-domain at-a-glance metrics: finance / attendance /
        # disciplinary cases. Same shape as the Library tab — small
        # in-process panel that reads bus-side tables directly. Keeps
        # the user from having to drill into 4 separate windows just
        # to see "is this student in trouble".
        try:
            summary_tab = ttk.Frame(notebook)
            notebook.add(summary_tab, text="📊 Summary")
            _build_student_summary(
                summary_tab, student_id, na,
                on_open_finance=lambda: self.show_student_finance_account()
                    if hasattr(self, 'show_student_finance_account') else None,
                on_open_attendance=lambda: self.view_student_attendance(
                    student_id, s_email, s_first, s_last)
                    if hasattr(self, 'view_student_attendance') else None,
            )
        except Exception:
            logger.exception("Could not build student summary tab")

        # ── Actions tab ─────────────────────────────────────────
        # Reduced from the 8.117.15 footprint: the Edit / Manage Grades
        # / View Attendance / View Timetable / Export / Send Email
        # actions are also exposed on the records-list right-click
        # menu (8.117.16) so the user rarely needs to drill in just to
        # fire one. The tab is kept for the contact pane and as a
        # discoverability surface for users who haven't found the
        # right-click yet.
        actions_tab = ttk.Frame(notebook)
        notebook.add(actions_tab, text=_t("student_details.tab_actions"))

        actions_frame = ttk.LabelFrame(actions_tab, text=_t("student_details.available_actions"), padding=20)
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if self.auth.check_permission('update_any_student'):
            ttk.Button(actions_frame, text=_t("student_details.btn_edit_student"),
                      command=lambda: self.update_student_dialog(student_id),
                      width=30).pack(pady=10)

        if self.auth.check_permission('manage_grades'):
            ttk.Button(actions_frame, text=_t("student_details.btn_manage_grades"),
                      command=lambda: self.manage_student_grades(student_id, s_first, s_last),
                      width=30).pack(pady=5)

        own_record = self.auth.current_user and self.auth.current_user.get('student_id') == student_id
        if self.auth.check_permission('manage_attendance') or own_record:
            ttk.Button(actions_frame, text=_t("student_details.btn_view_attendance"),
                      command=lambda: self.view_student_attendance(student_id, s_email, s_first, s_last),
                      width=30).pack(pady=5)

        ttk.Button(actions_frame, text=_t("student_details.btn_view_timetable"),
                  command=lambda: self.view_student_timetable(student_id, s_first, s_last),
                  width=30).pack(pady=5)

        if self.auth.check_permission('export_data'):
            ttk.Button(actions_frame, text=_t("student_details.btn_export_data"),
                      command=lambda: self.export_individual_student_data(student_id, s_first, s_last),
                      width=30).pack(pady=5)

        contact_frame = ttk.LabelFrame(actions_tab, text=_t("student_details.contact_information"), padding=20)
        contact_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Label(contact_frame, text=f"{_t('student_details.label_email')} {s_email}").pack(anchor=tk.W)
        ttk.Button(contact_frame, text=_t("student_details.btn_send_email"),
                  command=lambda: self.send_email_to_student(s_email, s_first, s_last),
                  width=20).pack(pady=5)

        conn.close()

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student_details.error_load_details", error=str(e)))
        detail_window.destroy()

def _load_academic_data(self, student_id, modules_tree, grades_tree,
                        attendance_tree, summary_label, na):
    """Refresh the three academic Treeviews and the summary line."""
    # Clear
    for tree in (modules_tree, grades_tree, attendance_tree):
        for item in tree.get_children():
            tree.delete(item)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.module_type, sm.module_code, m.module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY m.module_type, sm.module_code
        ''', (student_id,))
        modules = cursor.fetchall()

        cursor.execute('''
            SELECT a.module_code, a.title as assessment_name,
                   s.grade, s.submission_date as grade_date
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE s.student_id = ? AND s.grade IS NOT NULL
            UNION ALL
            SELECT a.module_code, a.assessment_name,
                   g.score as grade, g.submission_date as grade_date
            FROM assessments a
            LEFT JOIN grades g ON a.assessment_id = g.assessment_id
            WHERE g.student_id = ? AND g.score IS NOT NULL
            ORDER BY grade_date DESC
            LIMIT 20
        ''', (student_id, student_id))
        grades = cursor.fetchall()

        cursor.execute('''
            SELECT module_code, date, status, notes
            FROM attendance_records
            WHERE student_id = ?
            ORDER BY date DESC
            LIMIT 10
        ''', (student_id,))
        attendance = cursor.fetchall()

        conn.close()

        # Modules — group by type with a faint header row before each block
        if modules:
            current_type = object()
            for module in modules:
                module_type = (module[0] or _t("student_details.unknown")).strip()
                if module_type != current_type:
                    current_type = module_type
                    modules_tree.insert(
                        "", tk.END,
                        values=(module_type.upper(), "", ""),
                        tags=("group",),
                    )
                modules_tree.insert(
                    "", tk.END,
                    values=(
                        "",
                        module[1] if module[1] else na,
                        module[2] if module[2] else _t("student_details.unknown_module"),
                    ),
                )
        else:
            modules_tree.insert(
                "", tk.END,
                values=("", "", _t("student_details.no_modules_enrolled")),
            )

        # Grades — colour-code by score band
        if grades:
            for grade in grades:
                module_code = grade[0] if grade[0] else na
                assessment_name = grade[1] if grade[1] else _t("student_details.unknown_assessment")
                raw_grade = grade[2]
                grade_value = (
                    raw_grade if raw_grade not in (None, "")
                    else _t("student_details.no_grade")
                )
                grade_date = grade[3] if grade[3] else _t("student_details.unknown_date")

                tag = ()
                try:
                    score = float(raw_grade)
                    if score >= 70:
                        tag = ("good",)
                    elif score >= 40:
                        tag = ("warn",)
                    else:
                        tag = ("fail",)
                except (TypeError, ValueError):
                    pass

                grades_tree.insert(
                    "", tk.END,
                    values=(module_code, assessment_name, grade_value, grade_date),
                    tags=tag,
                )
        else:
            grades_tree.insert(
                "", tk.END,
                values=("", _t("student_details.no_grades_recorded"), "", ""),
            )

        # Attendance — colour-code present/late/absent
        if attendance:
            for att in attendance:
                module_code = att[0] if att[0] else na
                att_date = att[1] if att[1] else _t("student_details.unknown_date")
                status = att[2] if att[2] else _t("student_details.unknown")
                notes = att[3] or ""

                status_lc = (status or "").strip().lower()
                if status_lc == "present":
                    tag = ("present",)
                elif status_lc == "late":
                    tag = ("late",)
                elif status_lc in ("absent", "unauthorised", "unauthorized"):
                    tag = ("absent",)
                else:
                    tag = ()

                attendance_tree.insert(
                    "", tk.END,
                    values=(att_date, module_code, status, notes),
                    tags=tag,
                )
        else:
            attendance_tree.insert(
                "", tk.END,
                values=("", "", _t("student_details.no_attendance_records"), ""),
            )

        summary_label.config(
            text=f"{len(modules)} module(s) · {len(grades)} grade(s) · "
                 f"{len(attendance)} recent attendance entry(ies)"
        )

    except Exception as e:
        summary_label.config(text=f"Error loading academic data: {e}",
                             foreground='#b00020')

def _build_student_summary(tab, student_id, na,
                           *, on_open_finance=None, on_open_attendance=None):
    """Render the cross-domain summary tab.

    Pulls one-shot counters for finance (open student_fees, total
    outstanding balance), attendance (recent rate %), and disciplinary
    + academic-misconduct cases (open count). All queries are scoped
    by ``student_id`` and tolerate missing tables — older deployments
    that don't have ``disciplinary_records`` / ``student_fees`` see an
    "n/a" tile rather than a stack trace."""
    import sqlite3
    from education_system.university_system.modules.shared.constants.paths import (
        DEFAULT_DB_PATH,
    )

    title_lbl = ttk.Label(tab, text="At-a-glance summary",
                          font=('Arial', 14, 'bold'))
    title_lbl.pack(anchor='w', padx=14, pady=(14, 6))
    ttk.Label(tab, text=f"Cross-domain status for {student_id} — drawn live "
              "from the finance, attendance, and cases tables.",
              foreground='#555555').pack(anchor='w', padx=14, pady=(0, 12))

    grid = ttk.Frame(tab, padding=10)
    grid.pack(fill='both', expand=True)
    for col in range(3):
        grid.columnconfigure(col, weight=1)

    def _tile(parent, row, col, title, value, sub="", color=None,
              on_click=None):
        card = ttk.LabelFrame(parent, text=title, padding=14)
        card.grid(row=row, column=col, sticky='nsew', padx=8, pady=8)
        big = tk.Label(card, text=str(value),
                       font=('Arial', 22, 'bold'),
                       fg=color or "#222222", anchor='w')
        big.pack(anchor='w')
        if sub:
            tk.Label(card, text=sub, fg='#555555',
                     font=('Arial', 9)).pack(anchor='w', pady=(2, 0))
        if callable(on_click):
            ttk.Button(card, text="Open →",
                       command=on_click).pack(anchor='e', pady=(8, 0))
        return card

    open_fines = "—"
    finance_balance = "—"
    finance_color = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount), 0) "
                "FROM student_fees WHERE student_id = ? "
                "AND status != 'paid'",
                (str(student_id),)
            ).fetchone()
            if row:
                open_fines = int(row[0] or 0)
                bal = float(row[1] or 0.0)
                finance_balance = f"£{bal:,.2f}"
                if bal > 500:
                    finance_color = "#b00020"
                elif bal > 0:
                    finance_color = "#b87a00"
                else:
                    finance_color = "#1b7f3a"
        except sqlite3.OperationalError:
            open_fines = na
        conn.close()
    except Exception:
        logger.debug("finance summary lookup failed", exc_info=True)

    _tile(grid, 0, 0, "💰 Outstanding balance",
          finance_balance,
          sub=f"{open_fines} open fee(s)" if open_fines != "—" else "",
          color=finance_color,
          on_click=on_open_finance if callable(on_open_finance) else None)

    att_rate = "—"
    att_sub = ""
    att_color = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            row = conn.execute(
                "SELECT "
                " SUM(CASE WHEN LOWER(status)='present' THEN 1 ELSE 0 END), "
                " COUNT(*) "
                "FROM attendance_records WHERE student_id = ?",
                (str(student_id),)
            ).fetchone()
            if row and row[1]:
                pct = (float(row[0] or 0) / float(row[1])) * 100
                att_rate = f"{pct:.0f}%"
                att_sub = f"{int(row[0] or 0)} present of {int(row[1])}"
                if pct >= 85:
                    att_color = "#1b7f3a"
                elif pct >= 60:
                    att_color = "#b87a00"
                else:
                    att_color = "#b00020"
            elif row:
                att_rate = na
                att_sub = "no records yet"
        except sqlite3.OperationalError:
            att_rate = na
        conn.close()
    except Exception:
        logger.debug("attendance summary lookup failed", exc_info=True)

    _tile(grid, 0, 1, "✅ Attendance",
          att_rate, sub=att_sub, color=att_color,
          on_click=on_open_attendance if callable(on_open_attendance) else None)

    open_cases = 0
    case_sub = ""
    case_color = None
    case_seen = False
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_records "
                "WHERE user_id = ? AND COALESCE(status, 'Open') != 'Closed'",
                (str(student_id),)
            ).fetchone()
            if row:
                open_cases += int(row[0] or 0)
                case_seen = True
        except sqlite3.OperationalError:
            pass
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM academic_misconduct_cases "
                "WHERE student_id = ? AND COALESCE(status, '') != 'Closed'",
                (str(student_id),)
            ).fetchone()
            if row:
                open_cases += int(row[0] or 0)
                case_seen = True
        except sqlite3.OperationalError:
            pass
        conn.close()
        if case_seen:
            case_sub = "open disciplinary + AM cases"
            if open_cases > 0:
                case_color = "#b00020"
            else:
                case_color = "#1b7f3a"
        else:
            open_cases = na
            case_sub = ""
    except Exception:
        logger.debug("cases summary lookup failed", exc_info=True)

    _tile(grid, 0, 2, "🚨 Open cases",
          open_cases, sub=case_sub, color=case_color)


def search_students_dialog(self):
    """Create search dialog"""
    dialog = self.create_themed_toplevel(_t("student.search_students"), "400x300")
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Search criteria
    ttk.Label(main_frame, text=_t("student.search_by")).grid(row=0, column=0, sticky=tk.W, pady=5)
    search_type = ttk.Combobox(main_frame, values=[
        _t("student.first_name"), _t("student.last_name"), _t("student.student_id"), _t("student.col_course"), _t("common.email")
    ], state='readonly', width=25)
    search_type.grid(row=0, column=1, pady=5, padx=(10, 0))
    search_type.set(_t("student.first_name"))

    ttk.Label(main_frame, text=_t("student.search_term")).grid(row=1, column=0, sticky=tk.W, pady=5)
    search_term = ttk.Entry(main_frame, width=28)
    search_term.grid(row=1, column=1, pady=5, padx=(10, 0))

    def perform_search():
        """Perform search and update treeview"""
        term = search_term.get().strip()
        if not term:
            messagebox.showerror(_t("common.error"), _t("student.enter_search_term"))
            return

        try:
            # Check if student_tree exists
            if not hasattr(self, 'student_tree') or not self.student_tree:
                # Offer to open Student Records window
                if messagebox.askyesno(_t("student.open_records_title"),
                                      _t("student.open_records_msg")):
                    dialog.destroy()
                    self.show_student_records()
                return

            # Clear existing data
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Build query based on search type
                search_field_map = {
                    _t("student.first_name"): 'first_name',
                    _t("student.last_name"): 'last_name',
                    _t("student.student_id"): 'student_id',
                    _t("student.col_course"): 'course',
                    _t("common.email"): 'email_address'
                }

                field = search_field_map.get(search_type.get(), 'first_name')

                safe_field = validate_identifier(field, "column")
                if field == 'student_id':
                    query = 'SELECT * FROM students WHERE [' + safe_field + '] = ?'
                    cursor.execute(query, (term,))
                else:
                    query = 'SELECT * FROM students WHERE LOWER([' + safe_field + ']) LIKE LOWER(?)'
                    cursor.execute(query, (f'%{term}%',))

                results = cursor.fetchall()

                # Populate treeview with results
                for student in results:
                    student_id = student[0]
                    email_address = student[1]
                    first_name = student[3] or ''
                    middle_name = student[4] or ''
                    last_name = student[5] or ''
                    course = student[9]
                    reg_date = student[10]
                    full_name = f"{first_name} {middle_name} {last_name}".replace('  ', ' ').strip()

                    self.student_tree.insert('', tk.END, values=(
                        student_id, full_name, email_address, course, reg_date[:10] if reg_date else 'N/A'
                    ))

                conn.close()

                if not results:
                    messagebox.showinfo(_t("student.search_students"), _t("student.no_results"))
                else:
                    messagebox.showinfo(_t("student.search_students"), _t("student.found_results").replace("{count}", str(len(results))))

                dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Search failed: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=2, column=0, columnspan=2, pady=20)

    def show_all_and_close():
        """Show all students and close search dialog"""
        try:
            if hasattr(self, 'student_tree') and self.student_tree:
                self.view_students()
            dialog.destroy()
        except Exception as e:
            print(f"Error showing all students: {e}")
            dialog.destroy()

    ttk.Button(button_frame, text=_t("common.search"), command=perform_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.show_all"), command=show_all_and_close).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    search_term.focus()
