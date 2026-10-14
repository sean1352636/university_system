"""Shared college dashboard for University applications."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from education_system.platform.cross_system import university_applications as service


def render(host, source_system: str, *, parent=None, read_only: bool = False) -> None:
    """The applications board for ``source_system``.

    ``read_only`` hides the button that submits a new application, for a
    host whose user may watch the board but not act on it.
    """
    frame = parent or host.content_frame
    if parent is None:
        if hasattr(host, "clear_content"):
            host.clear_content()
        else:
            for child in frame.winfo_children():
                child.destroy()
    ttk.Label(frame, text="University Applications",
              font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text=("UCAS-linked applications. University owns offers, conditions, "
              "confirmation and enrolment; this dashboard displays its live status."),
        foreground="#555", wraplength=900, justify="left",
    ).pack(anchor="w", pady=(2, 10))
    columns = ("status", "university_status", "application", "reference",
               "created", "transition")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
    for key, title, width in (
        ("status", "Progress", 200), ("university_status", "University status", 150),
        ("application", "Application ID", 100), ("reference", "UCAS / ref", 110),
        ("created", "Created", 140), ("transition", "Transition", 240),
    ):
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")

    # Action bar before the table, so the table is what the window gives its
    # extra height to.
    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(0, 8))
    tree.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = service.list_applications(source_system=source_system)
        except Exception as exc:
            messagebox.showerror("University applications", str(exc), parent=host.root)
            return
        unavailable = 0
        for row in rows:
            failed = row.get("university_lookup_failed")
            unavailable += bool(failed)
            # "Unavailable" and "—" are different answers: one means the
            # university could not be read, the other that this learner has
            # no record there yet.
            status = ("Unavailable" if failed
                      else row.get("university_status") or "—")
            tree.insert("", "end", iid=row["transition_id"], values=(
                row["application_status"], status,
                row.get("university_application_id") or "—",
                row.get("application_reference") or "—",
                row.get("initiated_at") or "—", row["transition_id"]))
        if unavailable:
            messagebox.showwarning(
                "University applications",
                f"The university's admissions database could not be read, so "
                f"the university status of {unavailable} application(s) is "
                f"unknown rather than absent.", parent=host.root)
        if hasattr(host, "set_status"):
            host.set_status(f"{len(rows)} university application(s)")

    if not read_only:
        ttk.Button(bar, text=("New university application"
                              if source_system not in service.UCAS_SOURCES
                              else "New UCAS-linked application"),
                   command=lambda: _new(host, source_system, refresh)).pack(
                       side="left", padx=(0, 6))
    ttk.Button(bar, text="Refresh status", command=refresh).pack(side="left", padx=6)
    ttk.Button(bar, text="View learner journey",
               command=lambda: _journey(host, tree)).pack(side="left", padx=6)
    refresh()


def _actor(host) -> str:
    """Who is filling this in — recorded as having taken the consent."""
    # The apprenticeships shell carries its user as a resolved Actor.
    username = getattr(getattr(host, "actor", None), "username", None)
    if isinstance(username, str) and username.strip():
        return username.strip()
    for attr in ("current_username", "username", "current_user"):
        value = getattr(host, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict) and value.get("username"):
            return str(value["username"])
    return ""


def _new(host, source_system: str, after) -> None:
    win = tk.Toplevel(host.root)
    win.title("University application")
    body = ttk.Frame(win, padding=14)
    body.pack(fill="both", expand=True)
    ucas_route = source_system in service.UCAS_SOURCES
    definitions = (
        ("student", "College learner ID" if ucas_route else "Apprentice ID"),
        ("ucas", "UCAS personal ID (10 digits)" if ucas_route
         else "UCAS personal ID (optional)"),
        ("predicted", "Predicted qualifications"),
        ("achieved", "Achieved qualifications"),
        ("statement", "Personal statement"), ("reference", "Academic reference"),
    )
    values = {key: tk.StringVar() for key, _ in definitions}
    for row, (key, label) in enumerate(definitions):
        ttk.Label(body, text=label + ":").grid(row=row, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Entry(body, textvariable=values[key], width=55).grid(
            row=row, column=1, sticky="ew", pady=3)
    body.columnconfigure(1, weight=1)
    next_row = len(definitions)

    # ── Choices ──────────────────────────────────────────────────────
    # UCAS is a five-choice scheme, and the firm/insurance selection later
    # in the flow is a choice *out of a list*. Collecting one made the
    # college re-enter the learner's application rather than record it.
    ttk.Label(body, text=f"Course choices (up to {service.MAX_CHOICES}, in order):",
              font=("", 10, "bold")).grid(row=next_row, column=0, columnspan=2,
                                          sticky="w", pady=(12, 2))
    next_row += 1
    grid = ttk.Frame(body)
    grid.grid(row=next_row, column=0, columnspan=2, sticky="ew")
    next_row += 1
    for column, (title, width) in enumerate(
            (("#", 3), ("University", 24), ("Course code", 14),
             ("Course name", 26), ("Entry year", 8))):
        ttk.Label(grid, text=title, width=width,
                  font=("", 9, "bold")).grid(row=0, column=column, padx=2, sticky="w")
    choice_vars = []
    default_year = str(date.today().year + 1)
    for rank in range(1, service.MAX_CHOICES + 1):
        entry = {key: tk.StringVar() for key in
                 ("university", "course_code", "course_name", "entry_year")}
        entry["entry_year"].set(default_year)
        ttk.Label(grid, text=str(rank)).grid(row=rank, column=0, padx=2)
        for column, (key, width) in enumerate(
                (("university", 24), ("course_code", 14),
                 ("course_name", 26), ("entry_year", 8)), start=1):
            ttk.Entry(grid, textvariable=entry[key], width=width).grid(
                row=rank, column=column, padx=2, pady=1)
        choice_vars.append(entry)

    # ── Consent ──────────────────────────────────────────────────────
    consent_given = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        body, variable=consent_given,
        text=("The learner has given and the college has recorded consent to "
              "this handover"),
    ).grid(row=next_row, column=0, columnspan=2, sticky="w", pady=(12, 2))
    next_row += 1
    sensitive = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        body, variable=sensitive,
        text="…including the academic reference and accessibility/support detail",
    ).grid(row=next_row, column=0, columnspan=2, sticky="w", padx=(20, 0))
    next_row += 1
    recorded_by = tk.StringVar(value=_actor(host))
    ttk.Label(body, text="Consent recorded by:").grid(
        row=next_row, column=0, sticky="e", padx=(0, 8), pady=3)
    ttk.Entry(body, textvariable=recorded_by, width=30).grid(
        row=next_row, column=1, sticky="w", pady=3)
    next_row += 1

    def fields():
        choices = []
        for entry in choice_vars:
            values_for = {key: var.get().strip() for key, var in entry.items()}
            if not any(values_for[k] for k in
                       ("university", "course_code", "course_name")):
                continue
            values_for["rank"] = len(choices) + 1
            choices.append(values_for)
        ucas_id = values["ucas"].get().strip()
        # No consent, no consent record — and preview() then refuses the
        # handover, rather than the college sending one on the strength of
        # an artefact this dialog invented.
        consent_scope = ("reference", "support_indicators") if sensitive.get() else ()
        handover_consent = (
            service.consent_record(
                recorded_by=recorded_by.get().strip(),
                scope=consent_scope,
                ucas_id=ucas_id or None,
                method="confirmed with the learner before submission")
            if consent_given.get() else None)
        return {
            "ucas_application": {"ucas_id": ucas_id, "status": "Submitted"},
            "choices": choices,
            "handover_consent": handover_consent,
            "personal_statement": values["statement"].get().strip() or None,
            "academic_reference": values["reference"].get().strip() or None,
            "predicted_qualifications": values["predicted"].get().strip() or None,
            "achieved_qualifications": values["achieved"].get().strip() or None,
            "consent": bool(consent_scope),
        }

    def preview_and_submit() -> None:
        try:
            result = service.preview(
                source_system, values["student"].get().strip(), **fields())
        except Exception as exc:
            messagebox.showerror("Cannot prepare handover", str(exc), parent=win)
            return
        detail = ["Included:", *[f"  • {x}" for x in result.included]]
        if result.withheld_no_consent:
            detail += ["", "Withheld without consent:",
                       *[f"  • {x}" for x in result.withheld_no_consent]]
        if not result.ready:
            # Say so, and say it as the outcome. Listing the gaps under a
            # "Submit?" prompt and then doing nothing when the user says yes
            # reads as the application having been sent.
            messagebox.showerror(
                "Cannot submit yet",
                "This handover is missing required information, so it has "
                "not been submitted:\n\n"
                + "\n".join(f"  • {x}" for x in result.missing_required),
                parent=win)
            return
        if not messagebox.askyesno(
                "Handover preview", "\n".join(detail) + "\n\nSubmit?", parent=win):
            return
        try:
            service.submit(source_system, values["student"].get().strip(), **fields())
        except Exception as exc:
            messagebox.showerror("Submission failed", str(exc), parent=win)
            return
        win.destroy()
        after()

    buttons = ttk.Frame(body)
    buttons.grid(row=next_row, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(buttons, text="Preview and submit", command=preview_and_submit).pack(side="left", padx=4)
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left", padx=4)


def _journey(host, tree) -> None:
    selected = tree.selection()
    if not selected:
        return
    from education_system.platform.cross_system import student_view, transitions
    row = transitions.get_transition(selected[0])
    if row:
        overview = student_view.build_overview(row["journey_id"])
        messagebox.showinfo("Learner journey", student_view.format_overview_text(overview),
                            parent=host.root)


__all__ = ["render"]
