"""Small reusable Tkinter helpers for POS panels."""
from .context import tk, ttk

def clear_tree(tree):
    tree.delete(*tree.get_children())

def button_row(parent, **kwargs):
    frame = tk.Frame(parent, **kwargs)
    frame.pack(fill="x")
    return frame
