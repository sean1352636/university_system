"""Superadmin role-picker dialogs (GUI and CLI)."""

_ROLE_OPTIONS = [
    ("admin", "Admin", "Full access to all modules and settings"),
    ("staff", "Staff", "Staff-level access to most modules"),
    ("teacher", "Teacher", "Teaching-focused access to academic modules"),
    ("student", "Student", "Student portal with limited access"),
    ("parent", "Parent", "Parent portal for communication and reports"),
]

# The apprenticeships system does not use the school vocabulary: an
# apprenticeship has five parties round it, two of them (the employer
# and the independent end-point assessor) outside the provider
# altogether. Offering a superadmin "teacher" or "parent" there would
# land them in a role the system has no screens for.
_APPRENTICESHIP_ROLE_OPTIONS = [
    ("admin", "Provider Admin", "Programmes, employers, funding and compliance"),
    ("staff", "Tutor / Assessor", "Caseload, training delivery and portfolio assessment"),
    ("apprentice", "Apprentice", "Own record, off-the-job log and portfolio"),
    ("employer", "Employer", "Own apprentices, approvals and progress reviews"),
    ("end_point_assessor", "End-Point Assessor", "Gateway decisions and EPA grading"),
]

# SEND is a staff tool for now (no learner or parent screens), so a
# superadmin enters it as one of the two staff roles.
_SEND_ROLE_OPTIONS = [
    ("admin", "SEND Admin", "Every SEND area, records and reports"),
    ("staff", "SENCO / Staff", "Learners, plans, EHCPs, provision and meetings"),
]

# Adult Education is staff-only too (no learner portal yet).
_ADULT_EDUCATION_ROLE_OPTIONS = [
    ("admin", "Adult Education Admin", "Every area: courses, funding, fees and reports"),
    ("staff", "Tutor / Staff", "Learners, enrolments, registers, goals and support"),
]

# Alternative Provision is staff-only too (no pupil or parent screens yet).
_ALTERNATIVE_PROVISION_ROLE_OPTIONS = [
    ("admin", "AP Admin", "Every area: referrals, placements, providers, invoices, reports"),
    ("staff", "Key Worker / Staff", "Pupils, registers, behaviour, safeguarding and plans"),
]

# Training Provider is staff-only too (no learner or client portal yet).
_TRAINING_PROVIDER_ROLE_OPTIONS = [
    ("admin", "TP Admin", "Every area: clients, courses, sessions, invoices, reports"),
    ("staff", "Trainer / Staff", "Learners, bookings, registers, results and certificates"),
]

# Local Authority Education is council staff only (no parent or school portal yet).
_LOCAL_AUTHORITY_ROLE_OPTIONS = [
    ("admin", "LA Admin", "Every area, including deleting records and the schools register"),
    ("staff", "Education Officer", "Children, admissions, welfare, exclusions, SEND, transport"),
]

_ROLE_COLOURS = {
    "admin": "#c0392b",
    "staff": "#2980b9",
    "teacher": "#27ae60",
    "student": "#8e44ad",
    "parent": "#e67e22",
    "apprentice": "#8e44ad",
    "employer": "#16a085",
    "end_point_assessor": "#d35400",
}

# Derived from the per-system manifests. This table already used the canonical
# "<Name> System" form that each system's own SYSTEM_NAME uses; the other two
# launcher tables had drifted away from it.
from education_system.systems.registry import display_names

SYSTEM_NAMES = display_names()


def role_options(target_system: str):
    """Roles a superadmin may enter *target_system* as."""
    if target_system == "apprenticeships":
        return _APPRENTICESHIP_ROLE_OPTIONS
    if target_system == "special_education":
        return _SEND_ROLE_OPTIONS
    if target_system == "adult_education":
        return _ADULT_EDUCATION_ROLE_OPTIONS
    if target_system == "alternative_provision":
        return _ALTERNATIVE_PROVISION_ROLE_OPTIONS
    if target_system == "training_provider":
        return _TRAINING_PROVIDER_ROLE_OPTIONS
    if target_system == "local_authority":
        return _LOCAL_AUTHORITY_ROLE_OPTIONS
    return _ROLE_OPTIONS


def is_superadmin(user_info) -> bool:
    """Check whether ``user_info`` represents a platform superadmin.

    University administrators are system-scoped administrators.  The platform
    superadmin dashboard is reserved for accounts with admin access across all
    core systems, matching the universal GUI and CLI login flows.
    """
    if not user_info:
        return False
    systems = user_info.get("systems", [])
    admin_keys = {
        s.get("system_key") for s in systems if s.get("role") == "admin"
    }
    return admin_keys >= {"university", "sixth_form", "secondary", "primary"}


def pick_role_gui(target_system: str) -> str:
    """Show a GUI dialog for superadmin to choose which role to enter as.

    Returns the selected role string, or 'admin' if the dialog is closed.
    """
    import tkinter as _tk

    options = role_options(target_system)
    chosen = {"role": "admin"}
    dlg = _tk.Tk()
    dlg.title("Select Role")
    # Grow with the option list rather than clipping the last button.
    dlg.geometry(f"460x{240 + len(options) * 42}")
    dlg.resizable(False, False)

    sys_name = SYSTEM_NAMES.get(target_system, target_system.title())

    body = _tk.Frame(dlg, padx=30, pady=20)
    body.pack(fill=_tk.BOTH, expand=True)

    _tk.Label(body, text=f"Entering {sys_name}",
              font=("Helvetica", 15, "bold")).pack(pady=(0, 4))
    _tk.Label(body, text="Select the role you want to use:",
              font=("Helvetica", 11), fg="#555").pack(pady=(0, 16))

    btn_style = {"font": ("Helvetica", 11), "fg": "white", "relief": _tk.FLAT,
                 "cursor": "hand2", "width": 32, "height": 2}

    def _select(r):
        chosen["role"] = r
        dlg.destroy()

    for role_key, role_label, role_desc in options:
        colour = _ROLE_COLOURS.get(role_key, "#2980b9")
        frm = _tk.Frame(body)
        frm.pack(fill="x", pady=3)
        _tk.Button(
            frm, text=f"{role_label}  —  {role_desc}",
            bg=colour, activebackground=colour, activeforeground="white",
            command=lambda r=role_key: _select(r), **btn_style,
        ).pack(fill="x")

    _tk.Button(body, text="Cancel", font=("Helvetica", 11), relief=_tk.FLAT,
               padx=20, pady=6, cursor="hand2",
               command=dlg.destroy).pack(pady=(12, 0))

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    dlg.update_idletasks()
    w, h = dlg.winfo_width(), dlg.winfo_height()
    x = (dlg.winfo_screenwidth() - w) // 2
    y = (dlg.winfo_screenheight() - h) // 2
    dlg.geometry(f"+{x}+{y}")
    dlg.mainloop()
    return chosen["role"]


def pick_role_cli(target_system: str) -> str:
    """CLI prompt for superadmin to choose which role to enter as."""
    from education_system.platform.delivery.cli.cli_helpers import print_header, print_menu, get_choice

    options = role_options(target_system)
    sys_name = SYSTEM_NAMES.get(target_system, target_system.title())
    width = max(len(label) for _, label, _ in options)
    print_header(f"Entering {sys_name} — Select Role")
    print_menu([
        (str(i), f"{label:<{width}} — {desc}")
        for i, (_, label, desc) in enumerate(options, 1)
    ])
    role_map = {str(i): key for i, (key, _, _) in enumerate(options, 1)}
    while True:
        choice = get_choice()
        if choice in role_map:
            return role_map[choice]
        print(f"  Invalid option. Please select 1-{len(options)}.")
