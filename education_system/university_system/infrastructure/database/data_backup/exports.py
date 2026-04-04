"""Export backup data to CSV, JSON, and XML formats."""

import json
import os
from xml.etree.ElementTree import Element, SubElement, ElementTree, ParseError  # nosemgrep: use-defused-xml

import pandas as pd

from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.infrastructure.database.data_backup.operations import (
    get_database_tables,
    validate_table_name,
)

logger = configure_logging(name=__name__)


def export_to_csv(backup_path: str, output_dir: str) -> bool:
    """Export backup to CSV files"""
    conn = None
    try:
        conn = get_connection(db_path=backup_path, row_factory=False)
        tables = get_database_tables()

        os.makedirs(output_dir, exist_ok=True)

        for table in tables:
            # Validate table name to prevent SQL injection
            validate_table_name(table, conn)
            df = pd.read_sql_query("SELECT * FROM [" + table + "]", conn)
            csv_path = os.path.join(output_dir, f"{table}.csv")
            df.to_csv(csv_path, index=False)

        logger.info(f"Exported backup to CSV files in {output_dir}")
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in CSV export: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error exporting to CSV: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error exporting to CSV: {e}")
        return False
    except pd.errors.DatabaseError as e:
        logger.error(f"Pandas database error exporting to CSV: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")


def export_to_json(backup_path: str, output_file: str) -> bool:
    """Export backup to JSON file"""
    conn = None
    try:
        conn = get_connection(db_path=backup_path, row_factory=False)
        data = {}

        tables = get_database_tables()
        for table in tables:
            # Validate table name to prevent SQL injection
            validate_table_name(table, conn)

            cursor = conn.cursor()
            # Table name validated above - safe to use in query with bracket quoting
            cursor.execute("SELECT * FROM [" + table + "]")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            data[table] = [dict(zip(columns, row)) for row in rows]

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4, default=str)

        logger.info(f"Exported backup to JSON: {output_file}")
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in JSON export: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error exporting to JSON: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error exporting to JSON: {e}")
        return False
    except (TypeError, json.JSONDecodeError) as e:
        logger.error(f"JSON serialization error: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")


def export_to_xml(backup_path: str, output_file: str) -> bool:
    """Export backup to XML file"""
    conn = None
    try:
        conn = get_connection(db_path=backup_path, row_factory=False)
        root = Element("database")

        tables = get_database_tables()
        for table_name in tables:
            # Validate table name to prevent SQL injection
            validate_table_name(table_name, conn)

            table_elem = SubElement(root, "table", name=table_name)

            cursor = conn.cursor()
            # Table name validated above - safe to use in query with bracket quoting
            cursor.execute("SELECT * FROM [" + table_name + "]")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            for row in rows:
                row_elem = SubElement(table_elem, "row")
                for col, val in zip(columns, row):
                    col_elem = SubElement(row_elem, col)
                    col_elem.text = str(val) if val is not None else ""

        tree = ElementTree(root)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)

        logger.info(f"Exported backup to XML: {output_file}")
        return True
    except ValueError as ve:
        logger.error(f"Invalid table name in XML export: {ve}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error exporting to XML: {e}")
        return False
    except (OSError, IOError) as e:
        logger.error(f"I/O error exporting to XML: {e}")
        return False
    except ParseError as e:
        logger.error(f"XML parsing error: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing connection: {e}")
