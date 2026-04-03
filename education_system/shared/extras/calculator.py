import tkinter as tk
from tkinter import font, filedialog, messagebox
import ast
import operator
import os

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculator")
        self.root.geometry("400x550")
        self.root.resizable(False, False)
        self.root.configure(bg='#2b2b2b')

        self.expression = ""
        self.result_var = tk.StringVar()
        self.result_var.set("0")

        # Secret menu storage
        self.stored_items = []
        self.storage_path = os.path.join(os.path.expanduser("~"), ".calculator_storage")

        # Create custom fonts
        self.display_font = font.Font(family='Arial', size=32, weight='bold')
        self.button_font = font.Font(family='Arial', size=18)

        self.create_display()
        self.create_buttons()

    def create_display(self):
        """Create the calculator display"""
        display_frame = tk.Frame(self.root, bg='#2b2b2b')
        display_frame.pack(expand=True, fill='both', padx=10, pady=(10, 5))

        display = tk.Entry(
            display_frame,
            textvariable=self.result_var,
            font=self.display_font,
            bg='#1e1e1e',
            fg='#ffffff',
            bd=0,
            justify='right',
            readonlybackground='#1e1e1e',
            state='readonly'
        )
        display.pack(expand=True, fill='both', ipady=20, padx=5, pady=5)

    def create_buttons(self):
        """Create calculator buttons"""
        button_frame = tk.Frame(self.root, bg='#2b2b2b')
        button_frame.pack(expand=True, fill='both', padx=10, pady=(5, 10))

        # Button layout
        buttons = [
            ['C', '⌫', '%', '/'],
            ['7', '8', '9', '*'],
            ['4', '5', '6', '-'],
            ['1', '2', '3', '+'],
            ['0', '.', '=']
        ]

        # Button colors
        colors = {
            'number': {'bg': '#3a3a3a', 'fg': '#ffffff', 'active_bg': '#4a4a4a'},
            'operator': {'bg': '#ff9500', 'fg': '#ffffff', 'active_bg': '#ffb143'},
            'special': {'bg': '#505050', 'fg': '#ffffff', 'active_bg': '#606060'},
            'equals': {'bg': '#ff9500', 'fg': '#ffffff', 'active_bg': '#ffb143'}
        }

        for i, row in enumerate(buttons):
            for j, button_text in enumerate(row):
                # Determine button color
                if button_text in ['C', '⌫', '%']:
                    color = colors['special']
                elif button_text in ['/', '*', '-', '+']:
                    color = colors['operator']
                elif button_text == '=':
                    color = colors['equals']
                else:
                    color = colors['number']

                # Special handling for '0' and '=' buttons (span multiple columns)
                if button_text == '0':
                    btn = tk.Button(
                        button_frame,
                        text=button_text,
                        font=self.button_font,
                        bg=color['bg'],
                        fg=color['fg'],
                        activebackground=color['active_bg'],
                        activeforeground='#ffffff',
                        bd=0,
                        command=lambda x=button_text: self.on_button_click(x)
                    )
                    btn.grid(row=i, column=j, columnspan=2, sticky='nsew', padx=2, pady=2)
                elif button_text == '=':
                    btn = tk.Button(
                        button_frame,
                        text=button_text,
                        font=self.button_font,
                        bg=color['bg'],
                        fg=color['fg'],
                        activebackground=color['active_bg'],
                        activeforeground='#ffffff',
                        bd=0,
                        command=lambda x=button_text: self.on_button_click(x)
                    )
                    btn.grid(row=i, column=j+1, columnspan=2, sticky='nsew', padx=2, pady=2)
                else:
                    btn = tk.Button(
                        button_frame,
                        text=button_text,
                        font=self.button_font,
                        bg=color['bg'],
                        fg=color['fg'],
                        activebackground=color['active_bg'],
                        activeforeground='#ffffff',
                        bd=0,
                        command=lambda x=button_text: self.on_button_click(x)
                    )
                    btn.grid(row=i, column=j, sticky='nsew', padx=2, pady=2)

        # Configure grid weights for responsive layout
        for i in range(5):
            button_frame.grid_rowconfigure(i, weight=1)
        for j in range(4):
            button_frame.grid_columnconfigure(j, weight=1)

    @staticmethod
    def _safe_eval(expression):
        """Safely evaluate a math expression using AST parsing.
        Only allows numbers and basic arithmetic operators."""
        allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def _eval_node(node):
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)
            elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif isinstance(node, ast.BinOp) and type(node.op) in allowed_operators:
                left = _eval_node(node.left)
                right = _eval_node(node.right)
                return allowed_operators[type(node.op)](left, right)
            elif isinstance(node, ast.UnaryOp) and type(node.op) in allowed_operators:
                return allowed_operators[type(node.op)](_eval_node(node.operand))
            else:
                raise ValueError(f"Unsupported expression")

        tree = ast.parse(expression, mode='eval')
        return _eval_node(tree)

    def on_button_click(self, value):
        """Handle button clicks"""
        if value == 'C':
            self.expression = ""
            self.result_var.set("0")
        elif value == '⌫':
            self.expression = self.expression[:-1]
            self.result_var.set(self.expression if self.expression else "0")
        elif value == '=':
            try:
                result = str(self._safe_eval(self.expression))
                self.result_var.set(result)
                self.expression = result

                # Check if result is 104 - open secret menu
                if result == "104":
                    self.open_secret_menu()
            except Exception:
                self.result_var.set("Error")
                self.expression = ""
        else:
            if self.result_var.get() == "Error" or (self.result_var.get() == "0" and value not in ['+', '-', '*', '/', '%']):
                self.expression = value
            else:
                self.expression += value
            self.result_var.set(self.expression)

    def open_secret_menu(self):
        """Open the secret menu window when result equals 104"""
        menu_window = tk.Toplevel(self.root)
        menu_window.title("Secret Menu")
        menu_window.geometry("600x500")
        menu_window.configure(bg='#2b2b2b')

        # Title
        title = tk.Label(
            menu_window,
            text="🔓 Secret Storage Menu",
            font=font.Font(family='Arial', size=20, weight='bold'),
            bg='#2b2b2b',
            fg='#ff9500'
        )
        title.pack(pady=20)

        # Button frame
        button_frame = tk.Frame(menu_window, bg='#2b2b2b')
        button_frame.pack(pady=10)

        upload_btn = tk.Button(
            button_frame,
            text="📁 Upload File",
            font=font.Font(family='Arial', size=14),
            bg='#ff9500',
            fg='#ffffff',
            activebackground='#ffb143',
            bd=0,
            padx=20,
            pady=10,
            command=lambda: self.upload_file(listbox)
        )
        upload_btn.pack(side='left', padx=5)

        view_btn = tk.Button(
            button_frame,
            text="👁 View Selected",
            font=font.Font(family='Arial', size=14),
            bg='#505050',
            fg='#ffffff',
            activebackground='#606060',
            bd=0,
            padx=20,
            pady=10,
            command=lambda: self.view_file(listbox)
        )
        view_btn.pack(side='left', padx=5)

        delete_btn = tk.Button(
            button_frame,
            text="🗑 Delete Selected",
            font=font.Font(family='Arial', size=14),
            bg='#d32f2f',
            fg='#ffffff',
            activebackground='#f44336',
            bd=0,
            padx=20,
            pady=10,
            command=lambda: self.delete_file(listbox)
        )
        delete_btn.pack(side='left', padx=5)

        # Listbox frame
        list_frame = tk.Frame(menu_window, bg='#2b2b2b')
        list_frame.pack(expand=True, fill='both', padx=20, pady=10)

        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        # Listbox
        listbox = tk.Listbox(
            list_frame,
            font=font.Font(family='Arial', size=12),
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#ff9500',
            selectforeground='#ffffff',
            bd=0,
            yscrollcommand=scrollbar.set
        )
        listbox.pack(expand=True, fill='both')
        scrollbar.config(command=listbox.yview)

        # Load existing items
        self.load_items(listbox)

        # Info label
        info_label = tk.Label(
            menu_window,
            text="Tip: Calculate to 104 to access this menu anytime!",
            font=font.Font(family='Arial', size=10, slant='italic'),
            bg='#2b2b2b',
            fg='#888888'
        )
        info_label.pack(pady=10)

    def load_items(self, listbox):
        """Load stored items into the listbox"""
        listbox.delete(0, tk.END)
        if os.path.exists(self.storage_path):
            for item in os.listdir(self.storage_path):
                listbox.insert(tk.END, item)
        else:
            os.makedirs(self.storage_path, exist_ok=True)

    def upload_file(self, listbox):
        """Upload a file to the secret storage"""
        file_path = filedialog.askopenfilename(
            title="Select a file to upload",
            filetypes=[("All files", "*.*")]
        )

        if file_path:
            filename = os.path.basename(file_path)
            destination = os.path.join(self.storage_path, filename)

            # Copy file to storage
            try:
                import shutil
                shutil.copy2(file_path, destination)
                messagebox.showinfo("Success", f"File '{filename}' uploaded successfully!")
                self.load_items(listbox)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload file: {str(e)}")

    def view_file(self, listbox):
        """View/open the selected file"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to view.")
            return

        filename = listbox.get(selection[0])
        file_path = os.path.join(self.storage_path, filename)

        try:
            # Open file with default system application
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # macOS and Linux
                import subprocess
                if os.uname().sysname == 'Darwin':  # macOS
                    subprocess.call(['open', file_path])
                else:  # Linux
                    subprocess.call(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")

    def delete_file(self, listbox):
        """Delete the selected file"""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to delete.")
            return

        filename = listbox.get(selection[0])

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            file_path = os.path.join(self.storage_path, filename)
            try:
                os.remove(file_path)
                messagebox.showinfo("Success", f"File '{filename}' deleted successfully!")
                self.load_items(listbox)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {str(e)}")

    def run(self):
        """Start the calculator"""
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    calculator = Calculator(root)
    calculator.run()
