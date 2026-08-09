# Dark Mode Integration Guide

This guide explains how to integrate dark mode support into any GUI module in the University Management System.

## Overview

The system uses a centralized `ThemeManager` (singleton pattern) that manages theme colors and notifies all registered GUI modules when the theme changes.

## Quick Start for New GUI Modules

### 1. Import the Theme Manager

```python
from university_system.modules.shared.gui.theme_config import get_theme_manager
```

### 2. Initialize in Your GUI Class

```python
class YourGUI:
    def __init__(self, root, auth):
        self.root = root
        self.auth = auth

        # Get theme manager
        self.theme_manager = get_theme_manager()

        # Register for theme change notifications
        self.theme_manager.register_observer(self.on_theme_changed)

        # Apply theme to your ttk style
        self.style = ttk.Style()
        self.theme_manager.apply_theme_to_style(self.style)

        # Apply theme to your window
        self.theme_manager.apply_theme_to_window(self.root)
```

### 3. Handle Theme Changes

```python
def on_theme_changed(self):
    """Called when theme changes"""
    # Update style
    self.theme_manager.apply_theme_to_style(self.style)

    # Update your window
    self.theme_manager.apply_theme_to_window(self.root)

    # Update any custom widgets you created
    theme = self.theme_manager.get_current_theme()
    # Apply theme colors to custom widgets...

    self.root.update_idletasks()
```

### 4. Create Themed Child Windows

```python
def open_dialog(self):
    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("My Dialog")
    dialog.geometry("400x300")

    # Apply theme
    self.theme_manager.apply_theme_to_window(dialog)

    # Create dialog content...
```

## Accessing Theme Colors

Get the current theme colors dictionary:

```python
theme = self.theme_manager.get_current_theme()

# Available colors:
# - theme['bg']                 # Background color
# - theme['fg']                 # Foreground/text color
# - theme['select_bg']          # Selection background
# - theme['select_fg']          # Selection foreground
# - theme['button_bg']          # Button background
# - theme['button_fg']          # Button foreground
# - theme['entry_bg']           # Entry/input background
# - theme['entry_fg']           # Entry/input foreground
# - theme['frame_bg']           # Frame background
# - theme['label_bg']           # Label background
# - theme['label_fg']           # Label foreground
# - theme['treeview_bg']        # Treeview background
# - theme['treeview_fg']        # Treeview foreground
# - theme['treeview_selected']  # Treeview selection color
```

## Example: Complete GUI Module

```python
import tkinter as tk
from tkinter import ttk
from university_system.modules.shared.gui.theme_config import get_theme_manager

class ExampleGUI:
    def __init__(self, root, auth):
        self.root = root
        self.auth = auth

        # Setup theme
        self.theme_manager = get_theme_manager()
        self.theme_manager.register_observer(self.on_theme_changed)

        self.style = ttk.Style()
        self.theme_manager.apply_theme_to_style(self.style)

        # Build UI
        self.build_ui()

        # Apply initial theme
        self.theme_manager.apply_theme_to_window(self.root)

    def build_ui(self):
        """Build the user interface"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Example GUI").pack(pady=10)
        ttk.Button(main_frame, text="Open Dialog",
                   command=self.open_dialog).pack(pady=5)

    def open_dialog(self):
        """Open a themed dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Example Dialog")
        dialog.geometry("300x200")
        dialog.transient(self.root)

        # Apply theme to dialog
        self.theme_manager.apply_theme_to_window(dialog)

        # Dialog content
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="This is a themed dialog").pack(pady=10)
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=5)

    def on_theme_changed(self):
        """Handle theme change"""
        # Update style
        self.theme_manager.apply_theme_to_style(self.style)

        # Update window
        self.theme_manager.apply_theme_to_window(self.root)

        # Update any custom widgets
        # theme = self.theme_manager.get_current_theme()
        # self.my_custom_widget.configure(bg=theme['bg'])

        self.root.update_idletasks()
```

## Best Practices

1. **Always Register for Updates**: Register your GUI module with the theme manager to receive automatic updates
2. **Use TTK Widgets**: TTK widgets automatically support theming when styled
3. **Apply to Toplevel Windows**: Always apply theme to new Toplevel windows
4. **Handle Custom Widgets**: If you use tk.Canvas, tk.Text, or tk.Listbox, update them in `on_theme_changed()`
5. **Don't Hardcode Colors**: Always use theme colors from `get_current_theme()`
6. **Unregister on Destroy**: If your GUI is destroyed, unregister from the theme manager

## Unregistering (Cleanup)

```python
def __del__(self):
    """Cleanup when GUI is destroyed"""
    self.theme_manager.unregister_observer(self.on_theme_changed)
```

## Checking Current Mode

```python
if self.theme_manager.is_dark_mode():
    # Dark mode specific logic
    pass
else:
    # Light mode specific logic
    pass
```

## Testing Your Integration

1. Run your GUI module
2. Toggle dark mode using the theme button in the main GUI
3. Verify all colors update correctly
4. Open dialogs and verify they're themed
5. Check text readability in both modes

## Troubleshooting

**Problem**: My dialog doesn't change theme
- **Solution**: Call `self.theme_manager.apply_theme_to_window(dialog)` after creating it

**Problem**: My custom Canvas widget stays white/black
- **Solution**: Update it manually in `on_theme_changed()`:
  ```python
  theme = self.theme_manager.get_current_theme()
  self.my_canvas.configure(bg=theme['bg'])
  ```

**Problem**: Theme changes don't affect my module
- **Solution**: Make sure you called `self.theme_manager.register_observer(self.on_theme_changed)`

## Support

For questions or issues, check the implementation in:
- `modules/shared/gui/theme_config.py` - Theme manager
- `modules/shared/gui/main_gui.py` - Reference implementation
