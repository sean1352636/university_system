"""
Cinema Reports - Chart creation functions (bar, line, pie).

Requires matplotlib (guarded by MATPLOTLIB_AVAILABLE in _imports).
"""

from tkinter import ttk

from education_system.post_18.university_system.modules.domain.commerce.cinema.gui.cinema_gui.reports._imports import FigureCanvasTkAgg, Figure


def create_bar_chart(self, labels, values, title, xlabel, ylabel):
    """Create a bar chart."""
    chart_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    chart_frame.pack(fill="both", expand=True, pady=10)

    fig = Figure(figsize=(8, 4), facecolor='#16213e')
    ax = fig.add_subplot(111)

    ax.set_facecolor('#16213e')
    ax.bar(range(len(labels)), values, color='#e94560')

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8, color='white')
    ax.set_ylabel(ylabel, color='white')
    ax.set_xlabel(xlabel, color='white')
    ax.set_title(title, color='#e94560', fontsize=12, fontweight='bold')
    ax.tick_params(colors='white')

    for spine in ax.spines.values():
        spine.set_color('#0f3460')

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def create_line_chart(self, labels, values, title, xlabel, ylabel):
    """Create a line chart."""
    chart_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    chart_frame.pack(fill="both", expand=True, pady=10)

    fig = Figure(figsize=(8, 4), facecolor='#16213e')
    ax = fig.add_subplot(111)

    ax.set_facecolor('#16213e')
    ax.plot(range(len(labels)), values, color='#4ecca3', linewidth=2, marker='o')
    ax.fill_between(range(len(labels)), values, alpha=0.3, color='#4ecca3')

    step = max(1, len(labels) // 10)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)],
                      rotation=45, ha='right', fontsize=8, color='white')
    ax.set_ylabel(ylabel, color='white')
    ax.set_xlabel(xlabel, color='white')
    ax.set_title(title, color='#e94560', fontsize=12, fontweight='bold')
    ax.tick_params(colors='white')

    for spine in ax.spines.values():
        spine.set_color('#0f3460')

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def create_pie_chart(self, labels, values, title):
    """Create a pie chart."""
    chart_frame = ttk.Frame(self.report_display, style="Card.TFrame")
    chart_frame.pack(fill="both", expand=True, pady=10)

    fig = Figure(figsize=(6, 4), facecolor='#16213e')
    ax = fig.add_subplot(111)

    colors = ['#e94560', '#4ecca3', '#0f3460', '#ffa500', '#ff6b6b', '#45b7d1']

    wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                      colors=colors[:len(labels)], textprops={'color': 'white'})

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(9)

    ax.set_title(title, color='#e94560', fontsize=12, fontweight='bold')

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)
