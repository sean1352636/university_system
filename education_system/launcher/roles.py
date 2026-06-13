"""Superadmin role-picker dialogs (GUI and CLI)."""

_ROLE_OPTIONS = [
    ("admin", "Admin", "Full access to all modules and settings"),
    ("staff", "Staff", "Staff-level access to most modules"),
    ("teacher", "Teacher", "Teaching-focused access to academic modules"),
    ("student", "Student", "Student portal with limited access"),
    ("parent", "Parent", "Parent portal for communication and reports"),
]

_ROLE_COLOURS = {
    "admin": "#c0392b",
    "staff": "#2980b9",
    "teacher": "#27ae60",
    "student": "#8e44ad",
    "parent": "#e67e22",
}

SYSTEM_NAMES = {
    "university": "University System",
    "college":    "Sixth Form System",
    "school":     "Secondary School System",
    "primary":    "Primary School System",
    "nursery":    "Nursery System",
}


def is_superadmin(user_info) -> bool:
    """Check whether user_info represents a superadmin (admin in the university system)."""
    if not user_info:
        return False
    systems = user_info.get("systems", [])
    admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
    return "university" in admin_keys


def pick_role_gui(target_system: str) -> str:
    """Show a GUI dialog for superadmin to choose which role to enter as.

    Returns the selected role string, or 'admin' if the dialog is closed.
    """
    import tkinter as _tk

    chosen = {"role": "admin"}
    dlg = _tk.Tk()
    dlg.title("Select Role")
    dlg.geometry("420x440")
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

    for role_key, role_label, role_desc in _ROLE_OPTIONS:
        colour = _ROLE_COLOURS[role_key]
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
    from education_system.shared.cli.cli_helpers import print_header, print_menu, get_choice

    sys_name = SYSTEM_NAMES.get(target_system, target_system.title())
    print_header(f"Entering {sys_name} — Select Role")
    print_menu([
        ("1", "Admin   — Full access to all modules and settings"),
        ("2", "Staff   — Staff-level access to most modules"),
        ("3", "Teacher — Teaching-focused access to academic modules"),
        ("4", "Student — Student portal with limited access"),
        ("5", "Parent  — Parent portal for communication and reports"),
    ])
    role_map = {"1": "admin", "2": "staff", "3": "teacher",
                "4": "student", "5": "parent"}
    while True:
        choice = get_choice()
        if choice in role_map:
            return role_map[choice]
        print("  Invalid option. Please select 1-5.")
