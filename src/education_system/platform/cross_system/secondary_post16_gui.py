"""Secondary School Post-16 Destinations dashboard."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from education_system.platform.cross_system import secondary_post16 as service

LABELS = {"sixth_form": "Sixth Form", "fe_college": "FE College",
          "apprenticeships": "Apprenticeship"}


def render(host) -> None:
    frame = host.content_frame
    for child in frame.winfo_children():
        child.destroy()
    ttk.Label(frame, text="Post-16 Destinations", font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(frame, text=("Track parallel Year 11 applications. Secondary remains open "
                           "until one destination is confirmed and enrolment completes."),
              foreground="#555", wraplength=900).pack(anchor="w", pady=(2, 10))
    columns = ("pupil", "destination", "programme", "stage", "confirmed")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
    for key, title, width in (("pupil", "Pupil", 110),
                              ("destination", "Destination", 150),
                              ("programme", "Programme", 250),
                              ("stage", "Status", 210),
                              ("confirmed", "Confirmed", 90)):
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    tree.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for row in service.list_applications():
            tree.insert("", "end", iid=row["transition_id"], values=(
                row["pupil_id"], LABELS.get(row["destination_system"], row["destination_system"]),
                row.get("programme_label") or row.get("destination_label") or "—",
                row["stage"], "Yes" if row["confirmed"] else "No"))
        host.status_var.set(f"{len(tree.get_children())} post-16 application(s)")

    def selected() -> str | None:
        rows = tree.selection()
        if not rows:
            messagebox.showinfo("Post-16 destinations", "Select an application first.",
                                parent=host.root)
            return None
        return rows[0]

    def confirm() -> None:
        transition_id = selected()
        if not transition_id:
            return
        try:
            service.confirm_destination(transition_id)
        except Exception as exc:
            messagebox.showerror("Cannot confirm destination", str(exc), parent=host.root)
            return
        refresh()

    def journey() -> None:
        transition_id = selected()
        if not transition_id:
            return
        from education_system.platform.cross_system import student_view, transitions
        transition = transitions.get_transition(transition_id)
        if transition:
            overview = student_view.build_overview(transition["journey_id"])
            messagebox.showinfo("Learner journey", student_view.format_overview_text(overview),
                                parent=host.root)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(10, 0))
    ttk.Button(bar, text="Add destination", command=lambda: _new(host, refresh)).pack(
        side="left", padx=(0, 6))
    ttk.Button(bar, text="Confirm destination", command=confirm).pack(side="left", padx=6)
    ttk.Button(bar, text="View learner journey", command=journey).pack(side="left", padx=6)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left", padx=6)
    refresh()


def _new(host, after) -> None:
    win = tk.Toplevel(host.root)
    win.title("Add post-16 destination")
    body = ttk.Frame(win, padding=14)
    body.pack(fill="both", expand=True)
    destination = tk.StringVar(value="sixth_form")
    ttk.Label(body, text="Destination:").grid(row=0, column=0, sticky="e", padx=(0, 8))
    ttk.Combobox(body, textvariable=destination, state="readonly",
                 values=sorted(service.DESTINATIONS), width=45).grid(row=0, column=1)
    definitions = (("pupil", "Pupil ID"), ("institution", "Institution / employer"),
                   ("programme", "Course, subjects or standard"), ("level", "Level"),
                   ("predicted", "Predicted GCSE grades"),
                   ("achieved", "Achieved GCSE results"),
                   ("attainment", "English, maths and prior attainment"),
                   ("careers", "Career intention"),
                   ("eligibility", "Eligibility evidence"),
                   ("interview", "Interview / assessment requirements"))
    values = {key: tk.StringVar() for key, _ in definitions}
    for offset, (key, label) in enumerate(definitions, 1):
        ttk.Label(body, text=label + ":").grid(
            row=offset, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Entry(body, textvariable=values[key], width=52).grid(
            row=offset, column=1, sticky="ew", pady=3)
    consent = tk.BooleanVar(value=False)
    ttk.Checkbutton(body, variable=consent,
                    text="Learner/parent consents to SEND, medical and support transfer").grid(
        row=len(definitions) + 1, column=0, columnspan=2, sticky="w", pady=6)
    body.columnconfigure(1, weight=1)

    def fields() -> dict:
        dest = destination.get()
        programme = values["programme"].get().strip()
        base = {
            "predicted_grades": values["predicted"].get().strip(),
            "achieved_gcse_results": values["achieved"].get().strip() or None,
            "prior_attainment": values["attainment"].get().strip(),
            "careers_intentions": values["careers"].get().strip() or None,
            "interview_requirements": values["interview"].get().strip() or None,
            "consent_record": {"reference": f"POST16-{values['pupil'].get().strip()}",
                               "recorded_at": date.today().isoformat()},
            "consent": consent.get(),
        }
        if dest == "sixth_form":
            base["subjects"] = [part.strip() for part in programme.split(",")]
        elif dest == "fe_college":
            base["course_request"] = {
                "course": programme, "qualification_type": programme,
                "level": values["level"].get().strip(),
                "campus": values["institution"].get().strip()}
        else:
            base.update({
                "intended_programme": {"title": programme,
                                       "level": values["level"].get().strip()},
                "eligibility_evidence": values["eligibility"].get().strip(),
                "preferred_vacancy": values["institution"].get().strip() or None})
        return base

    def save() -> None:
        try:
            result = service.preview(
                values["pupil"].get().strip(), destination.get(), **fields())
        except Exception as exc:
            messagebox.showerror("Cannot preview", str(exc), parent=win)
            return
        detail = ["Included:", *[f"  • {x}" for x in result.included]]
        if result.withheld_no_consent:
            detail += ["", "Withheld without consent:",
                       *[f"  • {x}" for x in result.withheld_no_consent]]
        if result.missing_required:
            detail += ["", "Missing required:",
                       *[f"  • {x}" for x in result.missing_required]]
        if not messagebox.askyesno("Handover preview", "\n".join(detail) + "\n\nSubmit?",
                                   parent=win) or not result.ready:
            return
        try:
            service.submit(values["pupil"].get().strip(), destination.get(),
                           destination_label=values["institution"].get().strip(),
                           programme_label=values["programme"].get().strip(), **fields())
        except Exception as exc:
            messagebox.showerror("Submission failed", str(exc), parent=win)
            return
        win.destroy()
        after()

    buttons = ttk.Frame(body)
    buttons.grid(row=len(definitions) + 2, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(buttons, text="Preview and submit", command=save).pack(side="left", padx=4)
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left", padx=4)


__all__ = ["render"]
