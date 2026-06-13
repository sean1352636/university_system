"""
Standalone factory for creating GUI launchers.
No dependencies on other shared utils to avoid import issues.
"""

from education_system.university_system.core.i18n import get_text, _

def create_gui_launcher(title, description, cli_instruction=""):
    """
    Factory function to create a standardized GUI launcher.

    Args:
        title: Window title
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
            messagebox.showerror("Error", f"You must be logged in to access {title}.")
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

            info_frame = ttk.LabelFrame(main_frame, text="How to Access", padding="15")
            info_frame.pack(fill=tk.X, pady=20)
            ttk.Label(info_frame, text=cli_instruction or f"Use CLI: {title}", font=('Arial', 11)).pack()

            ttk.Button(main_frame, text="Close", command=window.destroy).pack(pady=10)

            print(f"✅ {title} GUI opened successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {title}: {str(e)}")
            print(f"❌ {title} error: {e}")

    return launcher_function


__all__ = ['create_gui_launcher']
