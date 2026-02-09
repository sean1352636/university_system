"""Export manager for PDF generation.

This module provides the main interface for exporting database data to PDF.
It coordinates the data aggregation, chart building, and PDF generation.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from university_system.modules.shared.constants import paths
from university_system.modules.shared.services.pdf_export.chart_builder import ChartBuilder
from university_system.modules.shared.services.pdf_export.data_aggregator import DataAggregator
from university_system.modules.shared.services.pdf_export.pdf_generator import PDFGenerator
from university_system.modules.shared.utils.i18n import get_text, _

logger = logging.getLogger(__name__)


class PDFExportManager:
    """Manages the full database PDF export process."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize the export manager.

        Args:
            db_path: Optional path to the database file.
            output_dir: Optional directory for output files.
        """
        self.db_path = db_path or str(paths.DEFAULT_DB_PATH)
        self.output_dir = output_dir or str(paths.EXPORTS_DIR)

        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.aggregator = DataAggregator(self.db_path)
        self.chart_builder = ChartBuilder()

    def export_full_database(
        self,
        output_filename: Optional[str] = None,
        include_data: bool = True,
        include_charts: bool = True,
        max_rows_per_table: int = 50,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> str:
        """Export the full database to a PDF file.

        Args:
            output_filename: Optional custom filename for the output.
            include_data: Whether to include actual table data.
            include_charts: Whether to include charts and visualizations.
            max_rows_per_table: Maximum number of rows to include per table.
            progress_callback: Optional callback for progress updates.
                Signature: callback(message: str, percent: int)

        Returns:
            Path to the generated PDF file.

        Raises:
            Exception: If export fails.
        """

        def update_progress(msg: str, pct: int):
            if progress_callback:
                progress_callback(msg, pct)
            logger.info(f"Export progress ({pct}%): {msg}")

        update_progress("Starting export...", 0)

        # Generate output filename
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"database_export_{timestamp}.pdf"

        output_path = os.path.join(self.output_dir, output_filename)

        # Initialize PDF generator
        pdf = PDFGenerator(output_path)

        update_progress("Collecting database statistics...", 5)

        # Get summary statistics
        stats = self.aggregator.get_summary_statistics()

        # Add title page
        update_progress("Creating title page...", 10)
        pdf.add_title_page(
            title="University Management System",
            subtitle="Complete Database Export Report",
            stats=stats,
        )

        # Add summary dashboard chart if charts enabled
        if include_charts:
            update_progress("Generating summary dashboard...", 15)
            dashboard_chart = self.chart_builder.create_summary_dashboard(stats)
            if dashboard_chart:
                pdf.add_section_header("Database Overview Dashboard")
                pdf.add_chart(dashboard_chart, width=7, height=5)
                pdf.add_page_break()

            # Add table size chart
            update_progress("Generating table size chart...", 20)
            if stats.get("largest_tables"):
                table_chart = self.chart_builder.create_table_size_chart(
                    stats["largest_tables"],
                    title="Top 15 Largest Tables by Record Count",
                )
                if table_chart:
                    pdf.add_section_header("Database Table Analysis")
                    pdf.add_chart(table_chart, width=7, height=4)
                    pdf.add_page_break()

        # Get categorized tables
        update_progress("Organizing table data...", 25)
        categorized_tables = self.aggregator.get_categorized_tables()

        # Add table of contents
        toc_entries = []
        for category, tables in categorized_tables.items():
            for table_info in tables:
                toc_entries.append(
                    (table_info.get("display_name", table_info["name"]), table_info["row_count"])
                )
        pdf.add_table_of_contents_entry(toc_entries)

        # Process each category
        total_categories = len(categorized_tables)
        for cat_idx, (category, tables) in enumerate(categorized_tables.items()):
            base_pct = 30 + int((cat_idx / total_categories) * 60)
            update_progress(f"Processing category: {category}...", base_pct)

            pdf.add_section_header(f"{category}")

            # Add category-specific charts
            if include_charts and category == "Academic":
                student_stats = self.aggregator.get_student_statistics()
                if student_stats.get("by_status"):
                    chart = self.chart_builder.create_pie_chart(
                        student_stats["by_status"],
                        "Students by Status",
                    )
                    if chart:
                        pdf.add_chart(chart, width=4, height=3)

            if include_charts and category == "Finance":
                finance_stats = self.aggregator.get_financial_statistics()
                pdf.add_text(
                    f"Total Scholarships: {finance_stats.get('scholarship_count', 0):,}",
                    style="Stats",
                )
                pdf.add_text(
                    f"Total Scholarship Value: ${finance_stats.get('scholarship_total', 0):,.2f}",
                    style="Stats",
                )
                pdf.add_spacer(0.25)

            if include_charts and category == "Events":
                event_stats = self.aggregator.get_event_statistics()
                if event_stats.get("by_type"):
                    chart = self.chart_builder.create_bar_chart(
                        event_stats["by_type"],
                        "Events by Type",
                        ylabel="Count",
                    )
                    if chart:
                        pdf.add_chart(chart, width=5, height=3)

            # Add tables in this category
            for table_info in tables:
                table_name = table_info["name"]
                display_name = table_info.get("display_name", table_name)
                description = table_info.get("description", "")
                row_count = table_info["row_count"]
                columns = table_info.get("column_names", [])

                if row_count == 0:
                    # Just show summary for empty tables
                    pdf.add_table_summary(
                        display_name,
                        row_count,
                        len(columns),
                        description,
                    )
                elif include_data:
                    # Get actual data
                    headers, data = self.aggregator.get_table_data(
                        table_name, limit=max_rows_per_table
                    )
                    pdf.add_data_table(
                        headers=headers,
                        data=data,
                        table_name=f"{display_name} ({row_count:,} records)",
                        description=description,
                        max_rows=max_rows_per_table,
                    )
                else:
                    # Show summary only
                    pdf.add_table_summary(
                        display_name,
                        row_count,
                        len(columns),
                        description,
                    )

            pdf.add_page_break()

        # Save the PDF
        update_progress("Saving PDF file...", 95)
        if pdf.save():
            update_progress("Export complete!", 100)
            logger.info(f"Database export saved to: {output_path}")

            # Log activity
            try:
                from university_system.modules.shared.utils.activity_logger import log_activity

                log_activity(
                    "export",
                    "database_pdf_export",
                    details={
                        "output_path": output_path,
                        "total_tables": stats.get("total_tables", 0),
                        "total_records": stats.get("total_records", 0),
                        "include_data": include_data,
                        "include_charts": include_charts,
                    },
                )
            except ImportError:
                pass

            return output_path
        else:
            raise Exception(f"Failed to save PDF to {output_path}")

    def export_summary_only(
        self,
        output_filename: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> str:
        """Export a summary report without full table data.

        Args:
            output_filename: Optional custom filename.
            progress_callback: Optional progress callback.

        Returns:
            Path to the generated PDF file.
        """
        return self.export_full_database(
            output_filename=output_filename,
            include_data=False,
            include_charts=True,
            progress_callback=progress_callback,
        )

    def get_export_preview(self) -> Dict[str, Any]:
        """Get a preview of what will be exported.

        Returns:
            Dictionary with export preview information.
        """
        stats = self.aggregator.get_summary_statistics()
        categorized = self.aggregator.get_categorized_tables()

        preview = {
            "statistics": stats,
            "categories": {},
            "estimated_pages": 0,
        }

        total_tables = 0
        for category, tables in categorized.items():
            preview["categories"][category] = {
                "table_count": len(tables),
                "tables": [
                    {
                        "name": t.get("display_name", t["name"]),
                        "rows": t["row_count"],
                        "columns": len(t.get("column_names", [])),
                    }
                    for t in tables
                ],
            }
            total_tables += len(tables)

        # Rough estimate: 2 pages per table + 5 for overview
        preview["estimated_pages"] = total_tables * 2 + 5

        return preview


def export_database_to_pdf(
    output_path: Optional[str] = None,
    include_data: bool = True,
    include_charts: bool = True,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> str:
    """Convenience function to export database to PDF.

    Args:
        output_path: Optional full path for the output file.
        include_data: Whether to include table data.
        include_charts: Whether to include charts.
        progress_callback: Optional progress callback.

    Returns:
        Path to the generated PDF file.
    """
    manager = PDFExportManager()

    if output_path:
        output_dir = os.path.dirname(output_path)
        output_filename = os.path.basename(output_path)
        manager.output_dir = output_dir or manager.output_dir
    else:
        output_filename = None

    return manager.export_full_database(
        output_filename=output_filename,
        include_data=include_data,
        include_charts=include_charts,
        progress_callback=progress_callback,
    )
