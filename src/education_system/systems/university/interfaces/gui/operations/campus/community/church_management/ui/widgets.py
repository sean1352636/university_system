from tkinter import ttk

def create_table(parent, columns):
    return ttk.Treeview(parent, columns=columns, show="headings")
