"""
Factory functions for creating standardized menu and GUI launchers.

This module provides reusable functions to generate CLI menus and GUI windows
for features, reducing code duplication across core files.
"""

from education_system.university_system.core.i18n import get_text as _t


def create_cli_menu(title, features, cli_instruction=""):
    """
    Factory function to create a standardized CLI menu.

    Args:
        title: Menu title (e.g., "LMS (Learning Management System)")
        features: Dict of menu options and their descriptions
        cli_instruction: Additional CLI instruction text

    Returns:
        A menu function that can be called with auth parameter
    """
    def menu_function(auth):
        """Display the CLI menu"""
        print("\n" + "="*50)
        print(f"    {title.upper()}")
        print("="*50)

        # Display menu options
        for i, (option, description) in enumerate(features.items(), 1):
            if i == len(features):
                print(f"{i}. {_t('shared.utils.feature_factory.return_to_main_menu')}")
            else:
                print(f"{i}. {option}")

        print("="*50)

        while True:
            try:
                choice = input(f"\n{_t('shared.utils.feature_factory.enter_choice', max_choice=len(features))}: ").strip()

                if choice == str(len(features)):  # Last option is always "Return"
                    break
                elif choice in [str(i) for i in range(1, len(features))]:
                    feature_list = list(features.keys())
                    selected = feature_list[int(choice) - 1]
                    description = features[selected]
                    print(f"\n{_t('shared.utils.feature_factory.feature_label', feature=selected)}")
                    print(f"   {description}")
                    if cli_instruction:
                        print(f"   {cli_instruction}")
                else:
                    print(_t("shared.utils.feature_factory.invalid_choice"))
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(_t("shared.utils.feature_factory.error", error=str(e)))

    return menu_function


def create_gui_launcher(title, description, cli_instruction=""):
    """
    Factory function to create a standardized GUI launcher.

    Args:
        title: Window title (e.g., "LMS (Learning Management System)")
        description: Multi-line feature description
        cli_instruction: CLI access instruction

    Returns:
        A GUI launcher function that can be called with root and auth parameters
    """
    def launcher_function(root, auth):
        """Launch the GUI window"""
        import tkinter as tk
        from tkinter import ttk, messagebox

        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(
                _t("shared.utils.feature_factory.error_title"),
                _t("shared.utils.feature_factory.login_required", title=title)
            )
            return

        try:
            window = tk.Toplevel(root)
            window.title(title)
            window.geometry("900x600")
            window.minsize(800, 500)

            main_frame = ttk.Frame(window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=title, font=('Arial', 16, 'bold')).pack(pady=10)
            ttk.Label(main_frame, text=description, justify=tk.LEFT, wraplength=800).pack(pady=10)

            info_frame = ttk.LabelFrame(main_frame, text=_t("shared.utils.feature_factory.how_to_access"), padding="15")
            info_frame.pack(fill=tk.X, pady=20)
            ttk.Label(info_frame, text=cli_instruction or _t("shared.utils.feature_factory.use_cli", title=title), font=('Arial', 11)).pack()

            ttk.Button(main_frame, text=_t("shared.utils.feature_factory.close"), command=window.destroy).pack(pady=10)

            print(f"{title} GUI opened successfully")

        except Exception as e:
            messagebox.showerror(
                _t("shared.utils.feature_factory.error_title"),
                _t("shared.utils.feature_factory.failed_to_open", title=title, error=str(e))
            )
            print(f"{title} error: {e}")

    return launcher_function


__all__ = [
    'create_cli_menu',
    'create_gui_launcher',
]
