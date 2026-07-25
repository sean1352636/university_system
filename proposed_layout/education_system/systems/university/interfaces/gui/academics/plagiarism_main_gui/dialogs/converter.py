import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.config import GuiConfig
from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.common import logger


class FileFormatConverterDialog:
    """Dialog for converting between different file formats"""

    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        self.dialog = None
        self.input_file = None
        self.output_file = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Create interface first
        self.create_search_interface()
        self.load_all_documents()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
        self.create_interface()

    def create_interface(self):
        """Create the converter interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.file_format_converter"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Input file selection
        input_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.input_file"), padding=GuiConfig.PADDING_MEDIUM)
        input_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.input_var = tk.StringVar()
        input_entry = ttk.Entry(input_frame, textvariable=self.input_var, state='readonly', width=60)
        input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(input_frame, text="Browse...", command=self.select_input_file).pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Output file selection
        output_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.output_file"), padding=GuiConfig.PADDING_MEDIUM)
        output_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.output_var = tk.StringVar()
        output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=60)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(output_frame, text="Browse...", command=self.select_output_file).pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Format options
        format_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.conversion_options"), padding=GuiConfig.PADDING_MEDIUM)
        format_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(format_frame, text=_t("plagiarism.output_format")).grid(row=0, column=0, sticky=tk.W)

        self.format_var = tk.StringVar(value="txt")
        formats = [("Plain Text (.txt)", "txt"), ("HTML (.html)", "html"), ("Markdown (.md)", "md")]

        for i, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=text, variable=self.format_var, value=value).grid(row=i+1, column=0, sticky=tk.W)

        # Conversion options
        self.preserve_formatting_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(format_frame, text="Preserve formatting", variable=self.preserve_formatting_var).grid(row=4, column=0, sticky=tk.W, pady=(GuiConfig.PADDING_MEDIUM, 0))

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.status_var = tk.StringVar()
        self.status_var.set("Ready to convert")
        ttk.Label(main_frame, textvariable=self.status_var).pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))

        ttk.Button(button_frame, text="Convert", command=self.convert_file).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def select_input_file(self):
        """Select input file"""
        filename = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[
                ("All supported", "*.txt;*.pdf;*.docx;*.doc"),
                ("Text files", "*.txt"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx;*.doc"),
                ("All files", "*.*")
            ]
        )

        if filename:
            self.input_file = filename
            self.input_var.set(filename)

            # Auto-suggest output filename
            base_name = os.path.splitext(filename)[0]
            output_ext = {"txt": ".txt", "html": ".html", "md": ".md"}[self.format_var.get()]
            self.output_var.set(f"{base_name}_converted{output_ext}")

    def select_output_file(self):
        """Select output file"""
        format_ext = {"txt": ".txt", "html": ".html", "md": ".md"}[self.format_var.get()]

        filename = filedialog.asksaveasfilename(
            title="Save Converted File",
            defaultextension=format_ext,
            filetypes=[
                (f"{self.format_var.get().upper()} files", f"*{format_ext}"),
                ("All files", "*.*")
            ]
        )

        if filename:
            self.output_file = filename
            self.output_var.set(filename)

    def convert_file(self):
        """Convert the file"""
        if not self.input_file:
            messagebox.showwarning("No Input", "Please select an input file.")
            return

        output_file = self.output_var.get().strip()
        if not output_file:
            messagebox.showwarning("No Output", "Please specify an output file.")
            return

        def convert_task():
            try:
                self.dialog.after(0, lambda: self.status_var.set("Reading input file..."))
                self.dialog.after(0, lambda: self.progress_var.set(25))

                # Extract text from input file
                content, file_type = self.checker.extract_text_from_file(self.input_file)

                self.dialog.after(0, lambda: self.status_var.set("Converting format..."))
                self.dialog.after(0, lambda: self.progress_var.set(50))

                # Convert based on output format
                output_format = self.format_var.get()
                if output_format == "html":
                    converted_content = self.convert_to_html(content)
                elif output_format == "md":
                    converted_content = self.convert_to_markdown(content)
                else:  # txt
                    converted_content = content

                self.dialog.after(0, lambda: self.status_var.set("Writing output file..."))
                self.dialog.after(0, lambda: self.progress_var.set(75))

                # Write output file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(converted_content)

                self.dialog.after(0, lambda: self.progress_var.set(100))
                self.dialog.after(0, lambda: self.status_var.set("Conversion completed"))
                self.dialog.after(0, lambda: messagebox.showinfo("Success", f"File converted successfully!\nOutput: {output_file}"))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda: self.status_var.set("Conversion failed"))
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Conversion failed: {err}"))

        thread = threading.Thread(target=convert_task, daemon=True)
        thread.start()

    def convert_to_html(self, content):
        """Convert content to HTML format"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        html_content = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Converted Document</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .content {{ max-width: 800px; margin: 0 auto; }}
        </style>
    </head>
    <body>
        <div class="content">
            <h1>Converted Document</h1>
            <p>Converted on: {timestamp}</p>
            <hr>
            <div>
                {content.replace(chr(10), '<br>' + chr(10))}
            </div>
        </div>
    </body>
    </html>"""
        return html_content

    def convert_to_markdown(self, content):
        """Convert content to Markdown format"""
        markdown_content = f"""# Converted Document

**Converted on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{content}
"""
        return markdown_content
