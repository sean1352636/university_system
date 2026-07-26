from education_system.systems.university.interfaces.gui.finance.finance_reporting.archive_backup._imports import (
    sys, tk, ttk, messagebox, filedialog, ScrolledText, FigureCanvasTkAgg, _,
)


def show_cli_report_in_window(self, report_func, title, width=1000, height=700):
    """
    Wrapper to display CLI report functions in GUI windows.
    Captures print() output and displays in a ScrolledText widget.
    """
    from io import StringIO

    try:
        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry(f"{width}x{height}")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=title,
                 font=('Arial', 16, 'bold')).pack(pady=(0, 10))

        # Create scrolled text widget for report
        report_text = ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 9))
        report_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Capture print output
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        # Run the report function
        report_func()

        # Get captured output
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # Display in window
        report_text.insert('1.0', output)
        report_text.config(state='disabled')

        # Add close button
        ttk.Button(main_frame, text=_("common.close"), command=report_window.destroy).pack(pady=10)

    except Exception as e:
        sys.stdout = old_stdout  # Restore stdout
        messagebox.showerror(_("common.error"), _("finance_reporting.messages.report_error").format(error=e))

def show_chart_window(self, title, figure, width=1400, height=900):
    """
    Display a matplotlib figure in a full-screen window with a close button

    Args:
        title: Window title
        figure: matplotlib Figure object
        width: Window width (default 1400)
        height: Window height (default 900)
    """
    # Create a new top-level window
    chart_window = tk.Toplevel(self.root)
    chart_window.title(title)

    # Make it nearly full screen
    screen_width = chart_window.winfo_screenwidth()
    screen_height = chart_window.winfo_screenheight()
    window_width = min(width, int(screen_width * 0.95))
    window_height = min(height, int(screen_height * 0.95))
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    chart_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Create main frame
    main_frame = ttk.Frame(chart_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create canvas for the chart
    canvas = FigureCanvasTkAgg(figure, master=main_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Create button frame at bottom
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

    # Add close button
    close_btn = ttk.Button(
        button_frame,
        text=_("common.close"),
        command=chart_window.destroy
    )
    close_btn.pack(side=tk.RIGHT, padx=5)

    # Add export button
    def export_chart():
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[(_("finance_reporting.filetypes.png"), "*.png"), (_("finance_reporting.filetypes.pdf"), "*.pdf"), (_("finance_reporting.filetypes.all"), "*.*")]
        )
        if filepath:
            figure.savefig(filepath, dpi=300, bbox_inches='tight')
            messagebox.showinfo(_("common.success"), _("finance_reporting.messages.chart_exported").format(filepath=filepath))

    export_btn = ttk.Button(
        button_frame,
        text=_("finance_reporting.buttons.export_chart"),
        command=export_chart
    )
    export_btn.pack(side=tk.RIGHT, padx=5)

    return chart_window
