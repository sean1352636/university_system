"""Backup export operations (CSV, JSON, XML, PDF, TXT)."""
import os
import json
import xml.etree.ElementTree as ET

from education_system.university_system.modules.shared.gui.database.shared_imports import logger
from education_system.university_system.modules.shared.gui.database.operations.backup_ops import (
    get_database_tables_from_connection,
)

# Late import to avoid circular - sqlite3 imported from shared_imports
try:
    from education_system.university_system.infrastructure.database.db import sqlite3
    from education_system.university_system.modules.shared.utils.sql_safety import (
        validate_table_name,
        SQLIdentifierError,
    )
except ImportError:
    pass


def export_to_csv(backup_path, output_dir):
    """Export backup to CSV files"""
    try:
        import csv
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        os.makedirs(output_dir, exist_ok=True)

        for table in tables:
            safe_table = validate_table_name(table, conn=conn)
            cursor = conn.execute("SELECT * FROM [" + safe_table + "]")
            with open(os.path.join(output_dir, f"{table}.csv"), 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Write headers
                writer.writerow([description[0] for description in cursor.description])
                # Write data
                writer.writerows(cursor.fetchall())

        conn.close()
        logger.info(f"Exported backup to CSV: {output_dir}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return False

def export_to_json(backup_path, output_file):
    """Export backup to JSON file"""
    try:
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        data = {}
        for table in tables:
            safe_table = validate_table_name(table, conn=conn)
            cursor = conn.execute("SELECT * FROM [" + safe_table + "]")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            data[table] = [dict(zip(columns, row)) for row in rows]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        conn.close()
        logger.info(f"Exported backup to JSON: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")
        return False

def export_to_xml(backup_path, output_file):
    """Export backup to XML file"""
    try:
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        root = ET.Element("database")

        for table in tables:
            table_elem = ET.SubElement(root, "table", name=table)
            safe_table = validate_table_name(table, conn=conn)
            cursor = conn.execute("SELECT * FROM [" + safe_table + "]")
            columns = [description[0] for description in cursor.description]

            for row in cursor.fetchall():
                row_elem = ET.SubElement(table_elem, "row")
                for col, val in zip(columns, row):
                    col_elem = ET.SubElement(row_elem, col)
                    col_elem.text = str(val) if val is not None else ""

        tree = ET.ElementTree(root)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)

        conn.close()
        logger.info(f"Exported backup to XML: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to XML: {e}")
        return False

def export_to_pdf(backup_path, output_file):
    """Export backup to PDF file"""
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch

        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        doc = SimpleDocTemplate(output_file, pagesize=landscape(letter),
                               leftMargin=0.5*inch, rightMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("<b>Database Backup Export</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 0.3*inch))

        for table in tables:
            # Validate table name to prevent SQL injection
            try:
                validated_table = validate_table_name(table, conn=conn)
            except SQLIdentifierError as e:
                logger.warning(f"Skipping invalid table name in PDF export: {table} - {e}")
                continue

            # Table title
            table_title = Paragraph(f"<b>Table: {validated_table}</b>", styles['Heading2'])
            elements.append(table_title)
            elements.append(Spacer(1, 0.1*inch))

            # Get table data (validated table name with bracket quoting)
            cursor = conn.execute("SELECT * FROM [" + validated_table + "] LIMIT 100")  # Limit rows for PDF
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            if rows:
                # Prepare table data
                table_data = [columns]
                for row in rows:
                    table_data.append([str(val) if val is not None else "" for val in row])

                # Create table with auto column widths
                pdf_table = Table(table_data)
                pdf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                elements.append(pdf_table)
            else:
                elements.append(Paragraph("<i>No data</i>", styles['Normal']))

            elements.append(PageBreak())

        doc.build(elements)
        conn.close()
        logger.info(f"Exported backup to PDF: {output_file}")
        return True
    except ImportError:
        logger.error("ReportLab is required for PDF export. Install with: pip install reportlab")
        return False
    except Exception as e:
        logger.error(f"Error exporting to PDF: {e}")
        return False

def export_to_txt(backup_path, output_file):
    """Export backup to TXT file"""
    try:
        conn = sqlite3.connect(backup_path)
        tables = get_database_tables_from_connection(conn)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("DATABASE BACKUP EXPORT\n")
            f.write("=" * 80 + "\n\n")

            for table in tables:
                f.write(f"\nTABLE: {table}\n")
                f.write("-" * 80 + "\n")

                safe_table = validate_table_name(table, conn=conn)
                cursor = conn.execute("SELECT * FROM [" + safe_table + "]")
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                # Write column headers
                f.write(" | ".join(columns) + "\n")
                f.write("-" * 80 + "\n")

                # Write rows
                for row in rows:
                    f.write(" | ".join(str(val) if val is not None else "" for val in row) + "\n")

                f.write("\n")

        conn.close()
        logger.info(f"Exported backup to TXT: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to TXT: {e}")
        return False
