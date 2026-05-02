"""Library → other-GUI cross-links.

Right-click context menus on Library tables (overdue, books, loans,
reservations) gain "Open in <other module>" items that jump to the
matching GUI with row context (student_id, book_id, …) attached. The
parent GUI's IPC poller — started by ``UnifiedManagementGUI.__init__``
in ``main_gui.py`` — picks up the request within ~1.5 s, lifts the main
window to front, and dispatches.

Wiring uses :func:`request_open` from
``shared.gui.main.features.academic_link_bar``. All cross-link
destinations must already be registered in either ``_MODULES`` or
``_EXTRA_DESTINATIONS`` over there. New jumps for this module use:

  - ``student_records`` (show_student_records)
  - ``email_manager``   (show_email_manager)
  - ``audit_viewer``    (show_audit_log_viewer)
  - ``finance_mgmt``    (show_finance_management)
  - ``student_finance`` (show_student_finance_account)
  - ``course_mgmt``     (show_course_management)
  - ``university_shop`` (show_university_shop)
  - ``textbook_store``  (show_textbook_store_gui)
  - ``marketplace``     (show_marketplace_gui)
  - ``printing``        (show_printing_services_gui)
  - ``room_booking``    (show_study_room_booking_gui)
  - ``document_manager`` (show_document_manager)

In addition to navigation jumps the menu also exposes **actions** that
write through the cross-domain buses directly in-process:

  - :func:`open_disciplinary_case_for_loan` — raises a disciplinary
    record via ``services.cases_bus.open_case``. The Disciplinary
    Portal itself is a subprocess launcher so we can't pass academic
    context across the process boundary; the in-process action
    sidesteps that by writing through the same unified case-spine the
    portal reads from.
  - :func:`show_loyalty_snapshot` and :func:`show_careers_snapshot` —
    read-only popups built directly off the loyalty / careers buses.
    Neither bus has a full GUI launcher today; the snapshot is the
    minimum useful surface and stays in-process so it can render
    immediately from a right-click without spinning up a new window.

If the import of the link-bar module fails (e.g. running in CLI/test
mode), every helper here degrades to a silent no-op so Library still
opens.
"""
from __future__ import annotations

import logging
import tkinter as tk

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
        request_open as _request_open,
    )
except Exception:  # pragma: no cover
    def _request_open(action, context=None):  # type: ignore
        logger.debug("link-bar unavailable; ignoring request_open(%s)", action)


def _jump(action: str, context: dict | None = None):
    try:
        _request_open(action, context or {})
    except Exception:
        logger.exception("cross-jump failed: %s ctx=%s", action, context)


# ---------------------------------------------------------------------------
# Library-internal action dialogs
# ---------------------------------------------------------------------------
def send_overdue_notice(user_id, book_title=None, days_overdue=None,
                        fine_amount=None, parent=None):
    """Open a small compose dialog pre-filled with an overdue-notice
    template addressed to *user_id*. Sends via the shared
    ``send_email_as_system`` service. Library-internal — no IPC."""
    try:
        from education_system.university_system.modules.domain.academics.gui.library.checkout_return import (
            _get_user_email,
        )
        from education_system.university_system.infrastructure.email.email_service import (
            send_email_as_system,
        )
    except Exception:
        logger.exception("Email helpers not available")
        from tkinter import messagebox
        messagebox.showerror(
            "Email unavailable",
            "Email service / user lookup helpers aren't available.",
            parent=parent)
        return

    first_name, email = _get_user_email(str(user_id))
    if not email:
        from tkinter import messagebox
        messagebox.showwarning(
            "No email",
            f"Could not find an email address for user {user_id}.",
            parent=parent)
        return

    # Build the prefilled template.
    name = first_name or str(user_id)
    title_part = f"\"{book_title}\"" if book_title else "your borrowed item"
    days_part = f" ({int(days_overdue)} days overdue)" if days_overdue else ""
    fine_part = (f"\n\nYour current outstanding fine is "
                 f"£{float(fine_amount):.2f}." if fine_amount else "")

    subject = f"[Library] Overdue notice — {book_title or 'borrowed item'}"
    body = (
        f"Hi {name},\n\n"
        f"This is a reminder that {title_part}{days_part} is overdue. "
        f"Please return it to the library at your earliest convenience "
        f"to avoid further fines.{fine_part}\n\n"
        f"If you've already returned this item, please ignore this notice.\n\n"
        f"— University Library"
    )

    # Compose dialog
    import tkinter as tk
    from tkinter import ttk, messagebox
    from tkinter.scrolledtext import ScrolledText

    win = tk.Toplevel(parent)
    win.title(f"Send overdue notice → {email}")
    win.geometry("640x520")
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass

    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)

    ttk.Label(form, text="To:").grid(row=0, column=0, sticky="w")
    to_var = tk.StringVar(value=email)
    ttk.Entry(form, textvariable=to_var, width=60).grid(
        row=0, column=1, sticky="ew", padx=(8, 0))
    ttk.Label(form, text="Subject:").grid(row=1, column=0, sticky="w",
                                          pady=(6, 0))
    subj_var = tk.StringVar(value=subject)
    ttk.Entry(form, textvariable=subj_var, width=60).grid(
        row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
    form.columnconfigure(1, weight=1)

    ttk.Label(form, text="Message:").grid(row=2, column=0, columnspan=2,
                                           sticky="w", pady=(8, 2))
    body_text = ScrolledText(form, wrap="word", height=18)
    body_text.grid(row=3, column=0, columnspan=2, sticky="nsew")
    body_text.insert("1.0", body)
    form.rowconfigure(3, weight=1)

    bar = ttk.Frame(win, padding=(10, 0, 10, 10))
    bar.pack(fill="x")

    def _do_send():
        recip = to_var.get().strip()
        subj = subj_var.get().strip()
        msg = body_text.get("1.0", "end-1c")
        if not recip or "@" not in recip:
            messagebox.showwarning("Invalid recipient",
                                   "Enter a valid email address.",
                                   parent=win)
            return
        try:
            ok = send_email_as_system(recip, subj, msg, system_name="Library")
        except Exception as exc:
            logger.exception("send_email_as_system failed")
            messagebox.showerror("Send failed",
                                 f"Could not send email:\n{exc}",
                                 parent=win)
            return
        if ok:
            messagebox.showinfo("Sent", f"Overdue notice sent to {recip}.",
                                parent=win)
            win.destroy()
        else:
            messagebox.showerror(
                "Send failed",
                "Email service rejected the message. Check the email "
                "configuration / app log.", parent=win)

    ttk.Button(bar, text="📤 Send", command=_do_send).pack(side="left")
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")


def open_disciplinary_case_for_loan(user_id, *, loan_id=None, book_title=None,
                                    fine_amount=None, days_overdue=None,
                                    parent=None):
    """Confirm + raise a disciplinary case via ``cases_bus.open_case``.

    Used as a right-click escalation from the Library fines tab when a
    fine is persistently unpaid or a borrower has racked up multiple
    overdue items. Goes through the unified case spine
    (``services.cases_bus``) — same write path Disciplinary Portal
    uses — so the case shows up wherever existing dashboards already
    read from ``disciplinary_records``. No subprocess hop required.

    The Disciplinary Portal itself is a subprocess launcher (see
    ``main_gui._launch_new_feature_module``); a navigation-style jump
    there can't carry the parent's academic context across the process
    boundary, so this action *creates the row* in-process and offers a
    follow-up "Open Disciplinary Portal" button to view it. That button
    is a plain quickbar-style launcher with no context payload — the
    user finds the new case by date in the portal."""
    if not user_id:
        return
    import tkinter as tk
    from tkinter import ttk, messagebox

    try:
        from education_system.university_system.modules.services.cases_bus import (
            open_case,
        )
    except Exception:
        logger.exception("cases_bus unavailable; cannot escalate")
        messagebox.showerror(
            "Disciplinary unavailable",
            "The cases bus could not be loaded; the case was not "
            "raised.", parent=parent)
        return

    # Build a sensible default description from whatever the row gave us.
    bits = []
    if book_title:
        bits.append(f'"{book_title}"')
    if days_overdue:
        try:
            bits.append(f"{int(days_overdue)} days overdue")
        except (TypeError, ValueError):
            pass
    if fine_amount:
        try:
            bits.append(f"£{float(fine_amount):.2f} unpaid")
        except (TypeError, ValueError):
            pass
    if loan_id:
        bits.append(f"loan_id={loan_id}")
    default_desc = ("Library escalation: " + ", ".join(bits)) if bits else \
                   "Library escalation: persistent overdue / unpaid fine"

    win = tk.Toplevel(parent)
    win.title(f"Open disciplinary case → student {user_id}")
    win.geometry("600x420")
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass

    form = ttk.Frame(win, padding=10)
    form.pack(fill="both", expand=True)

    ttk.Label(form, text=f"Subject student: {user_id}",
              font=("Arial", 10, "bold")).grid(row=0, column=0,
                                                columnspan=2, sticky="w",
                                                pady=(0, 8))

    ttk.Label(form, text="Severity:").grid(row=1, column=0, sticky="w")
    sev_var = tk.StringVar(value="Minor")
    ttk.Combobox(form, textvariable=sev_var,
                 values=["Minor", "Moderate", "Major"],
                 state="readonly", width=15).grid(
        row=1, column=1, sticky="w", padx=(8, 0))

    ttk.Label(form, text="Offense type:").grid(row=2, column=0, sticky="w",
                                                pady=(6, 0))
    off_var = tk.StringVar(value="Library — overdue / unpaid fine")
    ttk.Entry(form, textvariable=off_var, width=50).grid(
        row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
    form.columnconfigure(1, weight=1)

    ttk.Label(form, text="Description:").grid(row=3, column=0,
                                                sticky="nw", pady=(6, 0))
    from tkinter.scrolledtext import ScrolledText
    desc_text = ScrolledText(form, wrap="word", height=10)
    desc_text.grid(row=4, column=0, columnspan=2, sticky="nsew",
                   pady=(2, 6))
    desc_text.insert("1.0", default_desc)
    form.rowconfigure(4, weight=1)

    bar = ttk.Frame(win, padding=(10, 0, 10, 10))
    bar.pack(fill="x")

    def _do_open():
        if not messagebox.askyesno(
            "Confirm",
            f"Open a disciplinary case for student {user_id}?\n\n"
            "This will write to disciplinary_records and the case "
            "will appear in the Disciplinary Portal.",
            parent=win):
            return
        try:
            new_id = open_case(
                kind="disciplinary",
                subject_id=str(user_id),
                description=desc_text.get("1.0", "end-1c").strip(),
                severity=sev_var.get().strip() or "Minor",
                offense_type=off_var.get().strip() or "Library escalation",
            )
        except Exception as exc:
            logger.exception("open_case failed")
            messagebox.showerror("Failed",
                                 f"Could not raise the case:\n{exc}",
                                 parent=win)
            return
        if not new_id:
            messagebox.showerror(
                "Failed",
                "The cases bus returned no record id. The case may "
                "not have been created — check the application log.",
                parent=win)
            return
        messagebox.showinfo(
            "Case opened",
            f"Disciplinary record #{new_id} opened for student "
            f"{user_id}.", parent=win)
        win.destroy()

    ttk.Button(bar, text="🚨 Open case",
               command=_do_open).pack(side="left")
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")


def show_loyalty_snapshot(user_id, parent=None):
    """Read-only popup showing a student's loyalty balance, tier, and
    the most recent ``loyalty_ledger`` entries. Driven entirely by
    ``services.loyalty_bus`` — no schema or table assumptions here.

    The loyalty bus has no GUI launcher of its own today; this popup
    is the minimum useful surface and stays library-local so it
    renders without a window-creation lag from a right-click."""
    if not user_id:
        return
    import tkinter as tk
    from tkinter import ttk, messagebox

    try:
        from education_system.university_system.modules.services.loyalty_bus import (
            points_balance, tier, list_recent,
        )
    except Exception:
        logger.exception("loyalty_bus unavailable")
        messagebox.showerror(
            "Loyalty unavailable",
            "The loyalty bus could not be loaded.", parent=parent)
        return

    try:
        balance = int(points_balance(user_id))
        tier_name = tier(user_id) or "Bronze"
        recent = list_recent(user_id, limit=25) or []
    except Exception:
        logger.exception("loyalty snapshot lookup failed")
        balance, tier_name, recent = 0, "Bronze", []

    win = tk.Toplevel(parent)
    win.title(f"Loyalty snapshot — student {user_id}")
    win.geometry("680x420")
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass

    header = tk.Frame(win, bg="#2c3e50", height=56)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header,
             text=f"⭐  {tier_name} tier · {balance:,} points",
             font=("Arial", 13, "bold"),
             bg="#2c3e50", fg="white").pack(side="left", padx=14, pady=12)
    tk.Label(header, text=f"Student {user_id}",
             font=("Arial", 10), bg="#2c3e50",
             fg="#bdc3c7").pack(side="right", padx=14)

    body = ttk.Frame(win, padding=8)
    body.pack(fill="both", expand=True)

    cols = ("entry", "source", "points", "reference", "description", "when")
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c, w in zip(cols, (60, 110, 70, 110, 220, 120)):
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=w, anchor="w")
    tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    sb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=sb.set)

    if recent:
        for r in recent:
            tree.insert("", "end", values=(
                r.get("entry_id", ""),
                r.get("source", "") or "",
                r.get("points", "") or 0,
                r.get("reference_id", "") or "",
                (r.get("description") or "")[:60],
                (r.get("created_at") or "")[:19],
            ))
    else:
        tree.insert("", "end", values=(
            "—", "(no ledger entries yet)", 0, "", "", ""))

    ttk.Button(win, text="Close",
               command=win.destroy).pack(pady=(0, 10))


def show_careers_snapshot(user_id, parent=None):
    """Read-only popup listing a student's careers engagements
    (apprenticeships, placements, internships, …) sourced from
    ``services.careers_bus.list_engagements``. Same rationale as the
    loyalty snapshot: no full GUI launcher exists yet, this is the
    minimum useful surface."""
    if not user_id:
        return
    import tkinter as tk
    from tkinter import ttk, messagebox

    try:
        from education_system.university_system.modules.services.careers_bus import (
            list_engagements,
        )
    except Exception:
        logger.exception("careers_bus unavailable")
        messagebox.showerror(
            "Careers unavailable",
            "The careers bus could not be loaded.", parent=parent)
        return

    try:
        rows = list_engagements(student_id=user_id) or []
    except Exception:
        logger.exception("careers snapshot lookup failed")
        rows = []

    win = tk.Toplevel(parent)
    win.title(f"Careers snapshot — student {user_id}")
    win.geometry("820x420")
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass

    header = tk.Frame(win, bg="#2c3e50", height=48)
    header.pack(fill="x")
    header.pack_propagate(False)
    active = sum(1 for r in rows if (r.get("status") or "") == "active")
    tk.Label(header,
             text=f"💼  {len(rows)} engagement(s) · {active} active",
             font=("Arial", 12, "bold"),
             bg="#2c3e50", fg="white").pack(side="left", padx=14, pady=10)
    tk.Label(header, text=f"Student {user_id}",
             font=("Arial", 10), bg="#2c3e50",
             fg="#bdc3c7").pack(side="right", padx=14)

    body = ttk.Frame(win, padding=8)
    body.pack(fill="both", expand=True)

    cols = ("id", "kind", "role", "employer", "started", "ended",
            "hours", "status")
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    widths = (60, 110, 160, 80, 100, 100, 90, 80)
    for c, w in zip(cols, widths):
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=w, anchor="w")
    tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    sb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=sb.set)

    if rows:
        for r in rows:
            logged = r.get("hours_logged") or 0
            req = r.get("hours_required") or 0
            hours = f"{float(logged):.0f}/{float(req):.0f}" if req else f"{float(logged):.0f}"
            tree.insert("", "end", values=(
                r.get("engagement_id", ""),
                r.get("kind", "") or "",
                (r.get("role") or "")[:40],
                r.get("employer_id", "") or "",
                (r.get("started_on") or "")[:10],
                (r.get("ended_on") or "")[:10],
                hours,
                r.get("status", "") or "",
            ))
    else:
        tree.insert("", "end", values=(
            "—", "(no engagements logged)", "", "", "", "", "", ""))

    ttk.Button(win, text="Close",
               command=win.destroy).pack(pady=(0, 10))


def show_reading_lists_with_book(book_id, parent=None):
    """Pop a window listing every reading list that contains *book_id*.
    Self-contained — runs against ``student_records.db`` directly."""
    import sqlite3
    import tkinter as tk
    from tkinter import ttk, messagebox
    from education_system.university_system.modules.shared.constants.paths import (
        DEFAULT_DB_PATH,
    )

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        rows = conn.execute(
            "SELECT rl.list_id, rl.name, rl.creator_id, rl.category, "
            "       rl.created_date, rli.notes "
            "FROM reading_list_items rli "
            "JOIN reading_lists rl ON rl.list_id = rli.list_id "
            "WHERE rli.book_id = ? "
            "ORDER BY rl.created_date DESC", (str(book_id),)
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.exception("reading-list reverse lookup failed")
        messagebox.showerror(
            "Lookup failed",
            f"Could not query reading lists:\n{exc}",
            parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title(f"Reading lists containing book {book_id}")
    win.geometry("780x420")
    if parent is not None:
        try:
            win.transient(parent)
        except Exception:
            pass

    header = tk.Frame(win, bg="#2c3e50", height=42)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header,
             text=f"📚  Reading lists containing book {book_id}",
             font=("Arial", 12, "bold"),
             bg="#2c3e50", fg="white").pack(side="left", padx=12)
    tk.Label(header, text=f"{len(rows)} list(s)",
             font=("Arial", 10), bg="#2c3e50",
             fg="#bdc3c7").pack(side="right", padx=12)

    body = ttk.Frame(win, padding=8)
    body.pack(fill="both", expand=True)

    cols = ("list_id", "name", "creator", "category", "created", "notes")
    tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c, w in zip(cols, (70, 220, 100, 110, 110, 200)):
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=w, anchor="w")
    tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    sb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=sb.set)

    if rows:
        for r in rows:
            tree.insert("", "end", values=(
                r[0],
                (r[1] or "")[:60],
                r[2] or "",
                r[3] or "",
                (r[4] or "")[:10],
                (r[5] or "")[:60],
            ))
    else:
        tree.insert("", "end", values=(
            "—", "(no reading lists contain this book)", "", "", "", ""))

    ttk.Button(win, text="Close",
               command=win.destroy).pack(pady=(0, 10))


def _get_selected_values(tree):
    """Return the ``values`` tuple of the first selected row, or None."""
    try:
        sel = tree.selection()
        if not sel:
            return None
        return tree.item(sel[0]).get("values") or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-tree menu builders. Each takes the row's ``values`` tuple and returns
# a list of (label, callable) suitable for ``tk.Menu.add_command``.
# ---------------------------------------------------------------------------
def overdue_menu_items(values, parent=None):
    """Columns: User ID, Book ID, Title, Due Date, Days Overdue,
    Fine Amount, Contact"""
    if not values:
        return []
    user_id = values[0] if len(values) > 0 else None
    book_id = values[1] if len(values) > 1 else None
    title = values[2] if len(values) > 2 else None
    days_overdue = values[4] if len(values) > 4 else None
    fine_str = values[5] if len(values) > 5 else None
    fine_amount = None
    if fine_str:
        try:
            fine_amount = float(str(fine_str).replace("£", "")
                                  .replace("$", "").strip())
        except (TypeError, ValueError):
            pass

    items = []
    if user_id:
        items.extend([
            ("👤 Open student profile",
             lambda u=user_id: _jump("student_records", {"student_id": str(u)})),
            ("📧 Send overdue notice",
             lambda u=user_id, t=title, d=days_overdue, f=fine_amount:
                 send_overdue_notice(u, book_title=t, days_overdue=d,
                                     fine_amount=f, parent=parent)),
            ("📨 Open in Email Manager",
             lambda u=user_id: _jump("email_manager", {"student_id": str(u)})),
            ("💰 Open finance account",
             lambda u=user_id, f=fine_amount: _jump(
                 "student_finance",
                 {"student_id": str(u),
                  **({"fine_amount": f} if f is not None else {})})),
        ])
    if book_id:
        items.append(
            ("📚 Reading lists containing this book",
             lambda b=book_id: show_reading_lists_with_book(b, parent=parent)),
        )
        items.append(
            ("🎓 Find course using this book",
             lambda b=book_id: _jump("course_mgmt", {"book_id": str(b)})),
        )
        items.append(
            ("🕓 View audit log for this book",
             lambda b=book_id: _jump("audit_viewer", {"book_id": str(b)})),
        )
        shop_ctx = {"book_id": str(book_id)}
        if title:
            shop_ctx["book_title"] = str(title)
        items.append(
            ("🛒 Buy replacement in University Shop",
             lambda c=shop_ctx: _jump("university_shop", c)),
        )
        items.append(
            ("📖 Find used replacement (Textbook Exchange)",
             lambda c=shop_ctx: _jump("textbook_store", c)),
        )
        items.append(
            ("🤝 Find replacement on Student Marketplace",
             lambda c=shop_ctx: _jump("marketplace", c)),
        )
    return items


def books_menu_items(values, parent=None):
    """Columns: ID, Title, Author, Category, Status, Location"""
    if not values:
        return []
    book_id = values[0] if len(values) > 0 else None
    title = values[1] if len(values) > 1 else None
    if not book_id:
        return []
    items = [
        ("📚 Reading lists containing this book",
         lambda b=book_id: show_reading_lists_with_book(b, parent=parent)),
        ("🎓 Find course using this book",
         lambda b=book_id: _jump("course_mgmt", {"book_id": str(b)})),
        ("🕓 View audit log for this book",
         lambda b=book_id: _jump("audit_viewer", {"book_id": str(b)})),
    ]
    shop_ctx = {"book_id": str(book_id)}
    if title:
        shop_ctx["book_title"] = str(title)
    items.append(
        ("🛒 Buy in University Shop",
         lambda c=shop_ctx: _jump("university_shop", c)),
    )
    items.append(
        ("📖 Find used in Textbook Exchange",
         lambda c=shop_ctx: _jump("textbook_store", c)),
    )
    items.append(
        ("🤝 Find on Student Marketplace",
         lambda c=shop_ctx: _jump("marketplace", c)),
    )
    items.append(
        ("🖨 Photocopy this book (Printing Services)",
         lambda c=shop_ctx: _jump("printing", c)),
    )
    return items


def loan_history_menu_items(values, parent=None):
    """Columns: Loan ID, User ID, Book ID, Title, Checkout Date,
    Due Date, Return Date, Status"""
    if not values:
        return []
    loan_id = values[0] if len(values) > 0 else None
    user_id = values[1] if len(values) > 1 else None
    book_id = values[2] if len(values) > 2 else None
    title = values[3] if len(values) > 3 else None
    items = []
    if user_id:
        items.extend([
            ("👤 Open student profile",
             lambda u=user_id: _jump("student_records", {"student_id": str(u)})),
            ("📧 Send overdue notice",
             lambda u=user_id, t=title:
                 send_overdue_notice(u, book_title=t, parent=parent)),
            ("📨 Open in Email Manager",
             lambda u=user_id: _jump("email_manager", {"student_id": str(u)})),
            ("💰 Open finance account",
             lambda u=user_id: _jump("student_finance",
                                     {"student_id": str(u)})),
        ])
    if book_id:
        items.append(
            ("📚 Reading lists containing this book",
             lambda b=book_id: show_reading_lists_with_book(b, parent=parent)),
        )
    if loan_id:
        items.append(
            ("🕓 View loan audit log",
             lambda l=loan_id: _jump("audit_viewer", {"loan_id": str(l)})),
        )
    if user_id:
        items.append(
            ("⭐ View loyalty snapshot",
             lambda u=user_id: show_loyalty_snapshot(u, parent=parent)),
        )
        items.append(
            ("💼 View careers engagements",
             lambda u=user_id: show_careers_snapshot(u, parent=parent)),
        )
    return items


def reservations_menu_items(values, parent=None):
    """Columns: ID, Book ID, Title, User, Date, Expires, Position, Status"""
    if not values:
        return []
    book_id = values[1] if len(values) > 1 else None
    title = values[2] if len(values) > 2 else None
    user_id = values[3] if len(values) > 3 else None
    items = []
    if user_id:
        items.extend([
            ("👤 Open student profile",
             lambda u=user_id: _jump("student_records", {"student_id": str(u)})),
            ("📧 Send notice (item ready)",
             lambda u=user_id, t=title:
                 send_overdue_notice(u, book_title=t, parent=parent)),
            ("📨 Open in Email Manager",
             lambda u=user_id: _jump("email_manager", {"student_id": str(u)})),
        ])
    if book_id:
        items.append(
            ("📚 Reading lists containing this book",
             lambda b=book_id: show_reading_lists_with_book(b, parent=parent)),
        )
    items.append(
        ("🪑 Book a study room",
         lambda u=user_id: _jump(
             "room_booking",
             {"student_id": str(u)} if u else {})),
    )
    return items


def fines_menu_items(values, parent=None):
    """Columns: Loan ID, Book Title, User, Fine Amount, Days Overdue"""
    if not values:
        return []
    loan_id = values[0] if len(values) > 0 else None
    book_title = values[1] if len(values) > 1 else None
    user_id = values[2] if len(values) > 2 else None
    fine_str = values[3] if len(values) > 3 else None
    fine_amount = None
    if fine_str:
        try:
            fine_amount = float(str(fine_str).replace("£", "")
                                  .replace("$", "").strip())
        except (TypeError, ValueError):
            pass
    days_overdue = values[4] if len(values) > 4 else None

    items = []
    if user_id:
        items.append(
            ("👤 Open student profile",
             lambda u=user_id: _jump("student_records", {"student_id": str(u)})),
        )
        items.append(
            ("💰 View on student finance account",
             lambda u=user_id, f=fine_amount, l=loan_id: _jump(
                 "student_finance",
                 {"student_id": str(u),
                  **({"fine_amount": f} if f is not None else {}),
                  **({"loan_id": str(l)} if l is not None else {})})),
        )
        items.append(
            ("📧 Send overdue notice",
             lambda u=user_id, t=book_title, d=days_overdue, f=fine_amount:
                 send_overdue_notice(u, book_title=t, days_overdue=d,
                                     fine_amount=f, parent=parent)),
        )
        items.append(
            ("📨 Open in Email Manager",
             lambda u=user_id: _jump("email_manager", {"student_id": str(u)})),
        )
    if loan_id:
        items.append(
            ("🕓 View audit log for this fine",
             lambda l=loan_id: _jump("audit_viewer", {"loan_id": str(l)})),
        )
    if user_id:
        items.append(
            ("⭐ View loyalty snapshot",
             lambda u=user_id: show_loyalty_snapshot(u, parent=parent)),
        )
        items.append(
            ("🚨 Open disciplinary case (escalate)",
             lambda u=user_id, l=loan_id, t=book_title,
                    f=fine_amount, d=days_overdue:
                 open_disciplinary_case_for_loan(
                     u, loan_id=l, book_title=t,
                     fine_amount=f, days_overdue=d, parent=parent)),
        )
    return items


# ---------------------------------------------------------------------------
# Helpers to extend or attach a context menu.
# ---------------------------------------------------------------------------
def append_cross_links(menu: tk.Menu, items):
    """Append a separator + the given (label, command) pairs to *menu*."""
    if not items:
        return
    try:
        menu.add_separator()
    except Exception:
        pass
    for label, cmd in items:
        try:
            menu.add_command(label=label, command=cmd)
        except Exception:
            logger.exception("Could not add menu item %s", label)


def attach_cross_link_menu(tree, builder, parent=None):
    """Bind a fresh right-click menu on *tree* whose contents are
    re-built from ``builder(values, parent=…)`` each click. *parent* is
    used as the dialog parent for any Library-internal popups (compose
    dialogs, reverse-lookup popups)."""
    def _show(event):
        try:
            row = tree.identify_row(event.y)
            if row:
                tree.selection_set(row)
            values = _get_selected_values(tree)
            try:
                items = builder(values, parent=parent)
            except TypeError:
                # Builder doesn't accept parent= (older signature).
                items = builder(values)
            if not items:
                return
            menu = tk.Menu(tree, tearoff=0)
            for label, cmd in items:
                menu.add_command(label=label, command=cmd)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        except Exception:
            logger.exception("attach_cross_link_menu show failed")
    try:
        tree.bind("<Button-3>", _show, add="+")
    except Exception:
        logger.exception("attach_cross_link_menu bind failed")
