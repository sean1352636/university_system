"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def open_file_prompt(file_path, file_type):
    """Prompt user to open the generated file"""
    if file_path:
        open_file = input(f"\nDo you want to open the {file_type} file? (y/n): ").lower() == 'y'
        if open_file:
            try:
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(file_path)}")
            except Exception as e:
                print(f"Error opening {file_type}: {e}")
                print(f"Please open the file manually: {file_path}")
