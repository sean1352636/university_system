"""Reusable Tk dashboard for college apprenticeship progression."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.cross_system import apprenticeship_applications as service


def render(host, source_system: str, *, parent=None) -> None:
    """Render applications and progression actions into a college host."""
    frame = parent or host.content_frame
    if parent is None:
        if hasattr(host, "clear_content"):
            host.clear_content()
        else:
            for child in frame.winfo_children():
                child.destroy()

    ttk.Label(frame, text="Apprenticeship Progression",
              font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        text=("Consent-aware applications sent to the Apprenticeship System. "
              "Submitting creates an Applicant, never an active apprentice."),
        foreground="#555", wraplength=900, justify="left",
    ).pack(anchor="w", pady=(2, 10))

    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    columns = ("learner", "programme", "status", "started", "transition")
    tree = ttk.Treeview(holder, columns=columns, show="headings", height=14)
    for key, label, width in (
        ("learner", "Learner", 120), ("programme", "Reason / programme", 280),
        ("status", "Application status", 170), ("started", "Created", 140),
        ("transition", "Transition", 260),
    ):
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor="w")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    def reload() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = service.list_applications(source_system=source_system)
        except Exception as exc:  # pragma: no cover - GUI guard
            messagebox.showerror("Applications", str(exc), parent=host.root)
            return
        for row in rows:
            tree.insert("", "end", iid=row["transition_id"], values=(
                _source_student(row) or "—", row.get("reason") or "—",
                row["application_status"], row.get("initiated_at") or "—",
                row["transition_id"],
            ))
        if hasattr(host, "set_status"):
            host.set_status(f"{len(rows)} apprenticeship application(s)")
        elif hasattr(host, "status_var"):
            host.status_var.set(f"{len(rows)} apprenticeship application(s)")

    def selected() -> str | None:
        choice = tree.selection()
        if not choice:
            messagebox.showinfo("Select an application",
                                "Select an application first.", parent=host.root)
            return None
        return choice[0]

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(10, 0))
    ttk.Button(actions, text="Progress learner to apprenticeship",
               command=lambda: _application_dialog(
                   host, source_system, after=reload)).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Accept offer and approve handover",
               command=lambda: _accept_selected(
                   host, source_system, selected(), reload)).pack(side="left", padx=6)
    ttk.Button(actions, text="View learner journey",
               command=lambda: _journey(host, selected())).pack(side="left", padx=6)
    ttk.Button(actions, text="Refresh", command=reload).pack(side="left", padx=6)
    reload()


def _application_dialog(host, source_system: str, *, after,
                        transition_id: str | None = None) -> None:
    win = tk.Toplevel(host.root)
    win.title("Progress to Apprenticeship")
    win.transient(host.root)
    body = ttk.Frame(win, padding=14)
    body.pack(fill="both", expand=True)
    fields: dict[str, tk.StringVar] = {}
    definitions = (
        ("student_id", "College learner ID", ""),
        ("programme", "Intended programme / standard", ""),
        ("level", "Level", ""),
        ("eligibility", "Eligibility evidence", ""),
        ("attainment", "Prior attainment / English and maths", ""),
        ("careers", "Career interest", ""),
        ("vacancy", "Preferred vacancy", ""),
        ("employer", "Preferred employer", ""),
        ("reason", "Application reason", "Apprenticeship progression"),
    )
    for row, (key, label, default) in enumerate(definitions):
        ttk.Label(body, text=label + ":").grid(
            row=row, column=0, sticky="e", padx=(0, 8), pady=3)
        var = fields[key] = tk.StringVar(value=default)
        ttk.Entry(body, textvariable=var, width=52).grid(
            row=row, column=1, sticky="ew", pady=3)
    if transition_id:
        from education_system.platform.cross_system import enrolments, transitions
        transition = transitions.get_transition(transition_id)
        source = (enrolments.get_enrolment(transition["source_enrolment_id"])
                  if transition and transition.get("source_enrolment_id") else None)
        if source and source.get("local_student_id"):
            fields["student_id"].set(source["local_student_id"])
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        body, variable=consent,
        text="Learner consents to SEND, medical and support information transfer",
    ).grid(row=len(definitions), column=0, columnspan=2, sticky="w", pady=(8, 4))
    body.columnconfigure(1, weight=1)

    def values():
        programme = {"title": fields["programme"].get().strip()}
        if fields["level"].get().strip():
            programme["level"] = fields["level"].get().strip()
        return {
            "intended_programme": programme,
            "eligibility_evidence": fields["eligibility"].get().strip(),
            "prior_attainment": fields["attainment"].get().strip() or None,
            "careers_record": fields["careers"].get().strip() or None,
            "preferred_vacancy": fields["vacancy"].get().strip() or None,
            "employer_details": fields["employer"].get().strip() or None,
            "consent": consent.get(),
        }

    def show_preview() -> bool:
        try:
            result = service.preview(
                source_system, fields["student_id"].get().strip(), **values())
        except Exception as exc:
            messagebox.showerror("Cannot preview", str(exc), parent=win)
            return False
        lines = ["Information included:", *[f"  • {x}" for x in result.included]]
        if result.withheld_no_consent:
            lines += ["", "Withheld without consent:",
                      *[f"  • {x}" for x in result.withheld_no_consent]]
        if result.withheld_restricted:
            lines += ["", "Restricted (reference only):",
                      *[f"  • {x}" for x in result.withheld_restricted]]
        if result.missing_required:
            lines += ["", "Missing required information:",
                      *[f"  • {x}" for x in result.missing_required]]
        messagebox.showinfo("Handover preview", "\n".join(lines), parent=win)
        return result.ready

    def save() -> None:
        if not show_preview():
            return
        try:
            if transition_id:
                service.accept_offer(
                    transition_id,
                    accepted_by=fields["student_id"].get().strip(),
                    **values())
            else:
                service.submit(
                    source_system, fields["student_id"].get().strip(),
                    reason=fields["reason"].get().strip(), **values())
        except Exception as exc:
            messagebox.showerror("Application not submitted", str(exc), parent=win)
            return
        messagebox.showinfo(
            "Application submitted",
            ("The offer is accepted and the approved handover is recorded."
             if transition_id else
             "The learner now has an Applicant record in Apprenticeships."),
            parent=win)
        win.destroy()
        after()

    bar = ttk.Frame(body)
    bar.grid(row=len(definitions) + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Preview transfer", command=show_preview).pack(side="left", padx=4)
    ttk.Button(bar, text="Submit application", command=save).pack(side="left", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left", padx=4)


def _accept_selected(host, source_system: str, transition_id: str | None, after) -> None:
    if not transition_id:
        return
    messagebox.showinfo(
        "Offer acceptance",
        "Open the learner application form and confirm the current handover "
        "information before accepting. This prevents stale data being released.",
        parent=host.root)
    _application_dialog(host, source_system, after=after,
                        transition_id=transition_id)


def _journey(host, transition_id: str | None) -> None:
    if not transition_id:
        return
    from education_system.platform.cross_system import transitions, student_view
    row = transitions.get_transition(transition_id)
    if not row:
        return
    overview = student_view.build_overview(row["journey_id"])
    messagebox.showinfo("Learner journey", student_view.format_overview_text(overview),
                        parent=host.root)


def _source_student(row: dict) -> str | None:
    from education_system.platform.cross_system import enrolments
    source_id = row.get("source_enrolment_id")
    source = enrolments.get_enrolment(source_id) if source_id else None
    return source.get("local_student_id") if source else None


__all__ = ["render"]
