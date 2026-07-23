"""PDF generator for database export.

This module creates PDF documents with tables, charts, and formatted content
using ReportLab.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from education_system.post_18.university_system.core.i18n import get_text, _

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generates PDF documents for database export."""

    # Style configuration
    HEADER_COLOR = colors.HexColor("#2c3e50")
    ACCENT_COLOR = colors.HexColor("#3498db")
    TABLE_HEADER_BG = colors.HexColor("#34495e")
    TABLE_ALT_ROW = colors.HexColor("#f8f9fa")
    TABLE_BORDER = colors.HexColor("#dee2e6")

    def __init__(self, output_path: str, page_size=letter):
        """Initialize the PDF generator.

        Args:
            output_path: Path where the PDF will be saved.
            page_size: Page size (letter, A4, etc.).
        """
        self.output_path = output_path
        self.page_size = page_size
        self.elements = []
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                spaceAfter=30,
                textColor=self.HEADER_COLOR,
                alignment=TA_CENTER,
            )
        )

        # Subtitle style
        self.styles.add(
            ParagraphStyle(
                name="CustomSubtitle",
                parent=self.styles["Normal"],
                fontSize=12,
                spaceAfter=20,
                textColor=colors.gray,
                alignment=TA_CENTER,
            )
        )

        # Section header style
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=10,
                textColor=self.HEADER_COLOR,
                borderWidth=1,
                borderColor=self.ACCENT_COLOR,
                borderPadding=5,
            )
        )

        # Subsection header style
        self.styles.add(
            ParagraphStyle(
                name="SubsectionHeader",
                parent=self.styles["Heading3"],
                fontSize=12,
                spaceBefore=15,
                spaceAfter=8,
                textColor=self.ACCENT_COLOR,
            )
        )

        # Table description style
        self.styles.add(
            ParagraphStyle(
                name="TableDescription",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=colors.gray,
                spaceAfter=5,
            )
        )

        # Stats style
        self.styles.add(
            ParagraphStyle(
                name="Stats",
                parent=self.styles["Normal"],
                fontSize=10,
                leftIndent=20,
                spaceAfter=3,
            )
        )

    def add_title_page(
        self,
        title: str,
        subtitle: str = "",
        stats: Optional[Dict[str, Any]] = None,
    ):
        """Add a title page to the PDF.

        Args:
            title: Main title text.
            subtitle: Subtitle text.
            stats: Optional statistics to display.
        """
        # Add some space at top
        self.elements.append(Spacer(1, 2 * inch))

        # Title
        self.elements.append(Paragraph(title, self.styles["CustomTitle"]))

        # Subtitle with timestamp
        if subtitle:
            self.elements.append(Paragraph(subtitle, self.styles["CustomSubtitle"]))

        timestamp = datetime.now().strftime("%B %d, %Y at %H:%M:%S")
        self.elements.append(
            Paragraph(f"Generated: {timestamp}", self.styles["CustomSubtitle"])
        )

        self.elements.append(Spacer(1, 0.5 * inch))

        # Statistics summary box
        if stats:
            self.elements.append(Spacer(1, 0.5 * inch))
            self.elements.append(
                Paragraph("Export Summary", self.styles["SectionHeader"])
            )

            stats_data = [
                ["Total Tables", str(stats.get("total_tables", 0))],
                ["Total Records", f"{stats.get('total_records', 0):,}"],
                ["Tables with Data", str(stats.get("tables_with_data", 0))],
                ["Empty Tables", str(stats.get("empty_tables", 0))],
            ]

            stats_table = Table(stats_data, colWidths=[3 * inch, 2 * inch])
            stats_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, -1), self.TABLE_ALT_ROW),
                        ("TEXTCOLOR", (0, 0), (-1, -1), self.HEADER_COLOR),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 11),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, self.TABLE_BORDER),
                    ]
                )
            )
            self.elements.append(stats_table)

        self.elements.append(PageBreak())

    def add_section_header(self, text: str):
        """Add a section header.

        Args:
            text: Header text.
        """
        self.elements.append(Paragraph(text, self.styles["SectionHeader"]))

    def add_subsection_header(self, text: str):
        """Add a subsection header.

        Args:
            text: Header text.
        """
        self.elements.append(Paragraph(text, self.styles["SubsectionHeader"]))

    def add_text(self, text: str, style: str = "Normal"):
        """Add a paragraph of text.

        Args:
            text: Text content.
            style: Style name to use.
        """
        self.elements.append(Paragraph(text, self.styles.get(style, self.styles["Normal"])))

    def add_description(self, text: str):
        """Add a description paragraph.

        Args:
            text: Description text.
        """
        self.elements.append(Paragraph(text, self.styles["TableDescription"]))

    def add_spacer(self, height: float = 0.25):
        """Add vertical space.

        Args:
            height: Height in inches.
        """
        self.elements.append(Spacer(1, height * inch))

    def add_chart(self, chart_buffer: io.BytesIO, width: float = 5, height: float = 3):
        """Add a chart image from a BytesIO buffer.

        Args:
            chart_buffer: BytesIO buffer containing image data.
            width: Image width in inches.
            height: Image height in inches.
        """
        if chart_buffer:
            try:
                chart_buffer.seek(0)
                img = Image(chart_buffer, width=width * inch, height=height * inch)
                self.elements.append(img)
                self.elements.append(Spacer(1, 0.25 * inch))
            except Exception as e:
                logger.error(f"Error adding chart to PDF: {e}")

    def add_data_table(
        self,
        headers: List[str],
        data: List[Tuple],
        table_name: str = "",
        description: str = "",
        max_rows: int = 50,
        max_col_width: float = 1.5,
    ):
        """Add a data table to the PDF.

        Args:
            headers: List of column headers.
            data: List of data rows.
            table_name: Name of the table for the header.
            description: Description text.
            max_rows: Maximum number of rows to display.
            max_col_width: Maximum column width in inches.
        """
        if table_name:
            self.add_subsection_header(table_name)

        if description:
            self.add_description(description)

        if not headers or not data:
            self.elements.append(
                Paragraph("<i>No data available</i>", self.styles["TableDescription"])
            )
            self.add_spacer(0.25)
            return

        # Truncate data if needed
        truncated = False
        if len(data) > max_rows:
            data = data[:max_rows]
            truncated = True

        # Calculate column widths
        num_cols = len(headers)
        available_width = 7.5  # inches (letter width minus margins)
        col_width = min(max_col_width, available_width / num_cols)

        # Truncate column headers and data
        def truncate_text(text, max_len=20):
            text = str(text) if text is not None else ""
            return text[:max_len] + "..." if len(text) > max_len else text

        truncated_headers = [truncate_text(h, 15) for h in headers]

        # Prepare table data
        table_data = [truncated_headers]
        for row in data:
            table_data.append([truncate_text(cell, 18) for cell in row])

        # Create table
        table = Table(table_data, colWidths=[col_width * inch] * num_cols)

        # Style the table
        style_commands = [
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), self.TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            # Data rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("ALIGN", (0, 1), (-1, -1), "LEFT"),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, self.TABLE_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # Padding
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]

        # Add alternating row colors
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style_commands.append(
                    ("BACKGROUND", (0, i), (-1, i), self.TABLE_ALT_ROW)
                )

        table.setStyle(TableStyle(style_commands))
        self.elements.append(table)

        if truncated:
            self.elements.append(
                Paragraph(
                    f"<i>Showing first {max_rows} of {len(data) + (len(data) - max_rows)} rows...</i>",
                    self.styles["TableDescription"],
                )
            )

        self.add_spacer(0.25)

    def add_table_summary(
        self,
        table_name: str,
        row_count: int,
        column_count: int,
        description: str = "",
    ):
        """Add a summary card for a table without data.

        Args:
            table_name: Name of the table.
            row_count: Number of rows in the table.
            column_count: Number of columns.
            description: Optional description.
        """
        summary_data = [
            [table_name, f"{row_count:,} records", f"{column_count} columns"],
        ]

        if description:
            summary_data[0].append(description[:40])

        table = Table(summary_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), self.ACCENT_COLOR),
                    ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.TABLE_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        self.elements.append(table)
        self.add_spacer(0.15)

    def add_page_break(self):
        """Add a page break."""
        self.elements.append(PageBreak())

    def add_table_of_contents_entry(self, entries: List[Tuple[str, int]]):
        """Add a table of contents.

        Args:
            entries: List of (section_name, page_number) tuples.
        """
        self.add_section_header("Table of Contents")

        toc_data = []
        for name, count in entries:
            toc_data.append([name, f"{count:,} records"])

        if toc_data:
            table = Table(toc_data, colWidths=[5 * inch, 2 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("ALIGN", (0, 0), (0, -1), "LEFT"),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.5, self.TABLE_BORDER),
                    ]
                )
            )
            self.elements.append(table)

        self.add_page_break()

    def save(self) -> bool:
        """Save the PDF document.

        Returns:
            True if successful, False otherwise.
        """
        try:
            doc = SimpleDocTemplate(
                self.output_path,
                pagesize=self.page_size,
                rightMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                topMargin=0.5 * inch,
                bottomMargin=0.5 * inch,
            )
            doc.build(self.elements)
            logger.info(f"PDF saved successfully to {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving PDF: {e}")
            return False
