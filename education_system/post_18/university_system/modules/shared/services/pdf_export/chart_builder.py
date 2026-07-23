"""Chart builder for PDF export visualization.

This module creates charts and diagrams for the PDF export using matplotlib.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from education_system.post_18.university_system.core.i18n import get_text, _

logger = logging.getLogger(__name__)

plt = None
Figure = None


def _ensure_matplotlib() -> bool:
    """Import matplotlib lazily so chart generation works in test environments."""
    global plt, Figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as _plt
        from matplotlib.figure import Figure as _Figure
        plt = _plt
        Figure = _Figure
        return True
    except Exception as exc:
        logger.warning("matplotlib not available - charts will be text-based: %s", exc)
        return False


MATPLOTLIB_AVAILABLE = _ensure_matplotlib()


class ChartBuilder:
    """Creates charts and visualizations for PDF export."""

    # Color palette for charts
    COLORS = [
        "#3498db",  # Blue
        "#2ecc71",  # Green
        "#e74c3c",  # Red
        "#f39c12",  # Orange
        "#9b59b6",  # Purple
        "#1abc9c",  # Teal
        "#34495e",  # Dark gray
        "#e67e22",  # Dark orange
        "#16a085",  # Dark teal
        "#c0392b",  # Dark red
    ]

    def __init__(self):
        """Initialize the chart builder."""
        self.matplotlib_available = MATPLOTLIB_AVAILABLE or _ensure_matplotlib()

    def create_pie_chart(
        self,
        data: Dict[str, int],
        title: str,
        figsize: Tuple[float, float] = (6, 4),
    ) -> Optional[io.BytesIO]:
        """Create a pie chart from the given data.

        Args:
            data: Dictionary mapping labels to values.
            title: Chart title.
            figsize: Figure size tuple (width, height).

        Returns:
            BytesIO buffer containing the chart image, or None if failed.
        """
        if not self.matplotlib_available or not data:
            return None

        try:
            fig, ax = plt.subplots(figsize=figsize)

            labels = list(data.keys())
            values = list(data.values())
            colors = self.COLORS[: len(labels)]

            # Create pie chart
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                colors=colors,
                startangle=90,
                pctdistance=0.75,
            )

            # Style the text
            for text in texts:
                text.set_fontsize(8)
            for autotext in autotexts:
                autotext.set_fontsize(7)
                autotext.set_color("white")

            ax.set_title(title, fontsize=10, fontweight="bold", pad=10)
            ax.axis("equal")

            # Save to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            logger.error(f"Error creating pie chart: {e}")
            return None

    def create_bar_chart(
        self,
        data: Dict[str, int],
        title: str,
        xlabel: str = "",
        ylabel: str = "Count",
        figsize: Tuple[float, float] = (8, 4),
        horizontal: bool = False,
    ) -> Optional[io.BytesIO]:
        """Create a bar chart from the given data.

        Args:
            data: Dictionary mapping labels to values.
            title: Chart title.
            xlabel: X-axis label.
            ylabel: Y-axis label.
            figsize: Figure size tuple (width, height).
            horizontal: If True, create horizontal bar chart.

        Returns:
            BytesIO buffer containing the chart image, or None if failed.
        """
        if not self.matplotlib_available or not data:
            return None

        try:
            fig, ax = plt.subplots(figsize=figsize)

            labels = list(data.keys())
            values = list(data.values())
            colors = self.COLORS[: len(labels)]

            if horizontal:
                bars = ax.barh(labels, values, color=colors)
                ax.set_xlabel(ylabel)
                ax.set_ylabel(xlabel)
            else:
                bars = ax.bar(labels, values, color=colors)
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)

                # Rotate x-axis labels if many items
                if len(labels) > 5:
                    plt.xticks(rotation=45, ha="right")

            ax.set_title(title, fontsize=10, fontweight="bold", pad=10)

            # Add value labels on bars
            for bar, value in zip(bars, values):
                if horizontal:
                    ax.text(
                        value,
                        bar.get_y() + bar.get_height() / 2,
                        f" {value}",
                        va="center",
                        fontsize=8,
                    )
                else:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        str(value),
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            logger.error(f"Error creating bar chart: {e}")
            return None

    def create_table_size_chart(
        self,
        table_data: List[Tuple[str, int]],
        title: str = "Database Table Sizes",
        figsize: Tuple[float, float] = (10, 6),
    ) -> Optional[io.BytesIO]:
        """Create a horizontal bar chart showing table sizes.

        Args:
            table_data: List of (table_name, row_count) tuples.
            title: Chart title.
            figsize: Figure size tuple.

        Returns:
            BytesIO buffer containing the chart image, or None if failed.
        """
        if not self.matplotlib_available or not table_data:
            return None

        try:
            # Take top 15 tables
            table_data = sorted(table_data, key=lambda x: x[1], reverse=True)[:15]
            table_data.reverse()  # Reverse for display (largest at top)

            fig, ax = plt.subplots(figsize=figsize)

            tables = [t[0].replace("_", " ").title()[:25] for t in table_data]
            counts = [t[1] for t in table_data]

            # Create gradient colors based on value
            norm_counts = [c / max(counts) if max(counts) > 0 else 0 for c in counts]
            colors = plt.cm.Blues(
                [0.3 + 0.6 * n for n in norm_counts]
            )

            bars = ax.barh(tables, counts, color=colors)

            ax.set_xlabel("Number of Records")
            ax.set_title(title, fontsize=11, fontweight="bold", pad=10)

            # Add value labels
            for bar, count in zip(bars, counts):
                ax.text(
                    count + max(counts) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{count:,}",
                    va="center",
                    fontsize=8,
                )

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            logger.error(f"Error creating table size chart: {e}")
            return None

    def create_summary_dashboard(
        self,
        stats: Dict[str, Any],
        figsize: Tuple[float, float] = (12, 8),
    ) -> Optional[io.BytesIO]:
        """Create a dashboard summary with multiple charts.

        Args:
            stats: Dictionary with various statistics.
            figsize: Figure size tuple.

        Returns:
            BytesIO buffer containing the dashboard image, or None if failed.
        """
        if not self.matplotlib_available:
            return None

        try:
            fig = plt.figure(figsize=figsize)

            # Create grid layout
            gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

            # Summary box (top left)
            ax1 = fig.add_subplot(gs[0, 0])
            ax1.axis("off")
            summary_text = (
                f"Database Summary\n"
                f"{'─' * 30}\n"
                f"Total Tables: {stats.get('total_tables', 0):,}\n"
                f"Total Records: {stats.get('total_records', 0):,}\n"
                f"Tables with Data: {stats.get('tables_with_data', 0):,}\n"
                f"Empty Tables: {stats.get('empty_tables', 0):,}\n"
                f"Export Date: {stats.get('export_timestamp', 'N/A')[:10]}"
            )
            ax1.text(
                0.5,
                0.5,
                summary_text,
                transform=ax1.transAxes,
                fontsize=10,
                verticalalignment="center",
                horizontalalignment="center",
                family="monospace",
                bbox=dict(boxstyle="round", facecolor="#f8f9fa", edgecolor="#dee2e6"),
            )
            ax1.set_title("Overview", fontsize=11, fontweight="bold")

            # Table sizes chart (top right)
            ax2 = fig.add_subplot(gs[0, 1])
            largest = stats.get("largest_tables", [])[:8]
            if largest:
                tables = [t[0].replace("_", " ")[:15] for t in largest]
                counts = [t[1] for t in largest]
                tables.reverse()
                counts.reverse()
                colors = plt.cm.Blues([0.4 + 0.05 * i for i in range(len(tables))])
                ax2.barh(tables, counts, color=colors)
                ax2.set_xlabel("Records")
                ax2.set_title("Largest Tables", fontsize=11, fontweight="bold")
                for i, (t, c) in enumerate(zip(tables, counts)):
                    ax2.text(c + max(counts) * 0.02, i, f"{c:,}", va="center", fontsize=7)
            else:
                ax2.text(0.5, 0.5, "No data", ha="center", va="center")
                ax2.set_title("Largest Tables", fontsize=11, fontweight="bold")

            # Data vs Empty tables pie (bottom left)
            ax3 = fig.add_subplot(gs[1, 0])
            tables_with_data = stats.get("tables_with_data", 0)
            empty_tables = stats.get("empty_tables", 0)
            if tables_with_data > 0 or empty_tables > 0:
                ax3.pie(
                    [tables_with_data, empty_tables],
                    labels=["With Data", "Empty"],
                    autopct="%1.1f%%",
                    colors=["#2ecc71", "#e74c3c"],
                    startangle=90,
                )
                ax3.set_title("Table Status", fontsize=11, fontweight="bold")
            else:
                ax3.text(0.5, 0.5, "No data", ha="center", va="center")
                ax3.axis("off")

            # Category breakdown (bottom right)
            ax4 = fig.add_subplot(gs[1, 1])
            ax4.axis("off")
            category_text = "Data Categories\n" + "─" * 25
            ax4.text(
                0.5,
                0.5,
                category_text,
                transform=ax4.transAxes,
                fontsize=10,
                verticalalignment="center",
                horizontalalignment="center",
                family="monospace",
                bbox=dict(boxstyle="round", facecolor="#f8f9fa", edgecolor="#dee2e6"),
            )
            ax4.set_title("Categories", fontsize=11, fontweight="bold")

            # Save to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            logger.error(f"Error creating summary dashboard: {e}")
            return None

    def create_text_based_chart(
        self,
        data: Dict[str, int],
        title: str,
        width: int = 40,
    ) -> str:
        """Create a text-based bar chart for when matplotlib is unavailable.

        Args:
            data: Dictionary mapping labels to values.
            title: Chart title.
            width: Maximum width of bars.

        Returns:
            String representation of the chart.
        """
        if not data:
            return f"{title}\n{'─' * 40}\nNo data available"

        lines = [title, "─" * 40]
        max_value = max(data.values()) if data.values() else 1
        max_label_len = max(len(str(k)) for k in data.keys())

        for label, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
            bar_len = int((value / max_value) * width) if max_value > 0 else 0
            bar = "█" * bar_len
            lines.append(f"{label:<{max_label_len}} │{bar} {value:,}")

        return "\n".join(lines)
