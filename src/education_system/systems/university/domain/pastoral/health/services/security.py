from __future__ import annotations

import csv
import os
from datetime import datetime

from education_system.systems.university.domain.pastoral.health.services.health_context import cipher_suite
from education_system.systems.university.infrastructure.i18n import get_text as _t

def encrypt_sensitive_data(data):
    """Encrypt sensitive health data"""
    if data is None:
        return None
    return cipher_suite.encrypt(str(data).encode()).decode()

def decrypt_sensitive_data(encrypted_data):
    """Decrypt sensitive health data"""
    if encrypted_data is None:
        return None
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return encrypted_data

def truthy(x):
    return str(x).strip().lower() in ("1", "true", "yes", "y", "t")

def validate_csv_format(filename):
    """Validate CSV file format before import"""
    if not filename:
        return False, _t("health_misc.security.no_filename")

    if not os.path.exists(filename):
        return False, _t("health_misc.security.file_not_found", filename=filename)

    if not filename.lower().endswith('.csv'):
        return False, _t("health_misc.security.csv_extension_required")

    try:
        # Check file size (warn if very large)
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:  # 50MB
            return False, _t("health_misc.security.file_too_large", size=f"{file_size / (1024*1024):.1f}")

        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            # Read sample to detect format
            sample = csvfile.read(1024)
            csvfile.seek(0)

            if not sample.strip():
                return False, _t("health_misc.security.file_empty")

            # Detect CSV dialect
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
            except csv.Error:
                # Fallback to common delimiters
                delimiter = ','
                if '\t' in sample:
                    delimiter = '\t'
                elif ';' in sample:
                    delimiter = ';'

            csvfile.seek(0)
            reader = csv.DictReader(csvfile, delimiter=delimiter)

            # Validate headers
            required_fields = ['student_id', 'record_type', 'record_date', 'description']
            optional_fields = ['provider', 'confidential']

            if not reader.fieldnames:
                return False, _t("health_misc.security.no_header_row")

            # Clean fieldnames (remove whitespace)
            clean_fieldnames = [field.strip().lower() for field in reader.fieldnames]
            required_lower = [field.lower() for field in required_fields]

            missing_fields = []
            for field in required_lower:
                if field not in clean_fieldnames:
                    missing_fields.append(field)

            if missing_fields:
                return False, _t("health_misc.security.missing_columns", missing=', '.join(missing_fields), found=', '.join(reader.fieldnames))

            # Validate sample data rows
            row_count = 0
            validation_errors = []

            for row in reader:
                row_count += 1
                if row_count > 10:  # Check first 10 rows
                    break

                # Skip empty rows
                if not any(value.strip() for value in row.values()):
                    continue

                # Check required fields are not empty
                for field in required_fields:
                    if not row.get(field, '').strip():
                        validation_errors.append(_t("health_misc.security.empty_field", row=row_count + 1, field=field))

                # Validate date format
                date_value = row.get('record_date', '').strip()
                if date_value:
                    try:
                        parsed_date = datetime.strptime(date_value, '%Y-%m-%d')
                        # Check reasonable date range
                        current_year = datetime.now().year
                        if parsed_date.year < 1900 or parsed_date.year > current_year + 1:
                            validation_errors.append(_t("health_misc.security.date_outside_range", row=row_count + 1, date=date_value))
                    except ValueError:
                        validation_errors.append(_t("health_misc.security.invalid_date_format", row=row_count + 1, date=date_value))

                # Validate record type if present
                record_type = row.get('record_type', '').strip()
                if record_type:
                    valid_types = ['medical_exam', 'vaccination', 'injury', 'illness', 'mental_health', 'prescription', 'other']
                    if record_type.lower() not in [t.lower() for t in valid_types]:
                        validation_errors.append(_t("health_misc.security.invalid_record_type", row=row_count + 1, record_type=record_type, valid_types=', '.join(valid_types)))

                # Validate confidential field if present
                confidential = row.get('confidential', '').strip().lower()
                if confidential and confidential not in ['true', 'false', '1', '0', 'yes', 'no', 'y', 'n']:
                    validation_errors.append(_t("health_misc.security.invalid_confidential", row=row_count + 1, value=confidential))

            # Return validation results
            if validation_errors:
                error_summary = _t("health_misc.security.validation_errors_found", count=len(validation_errors), rows=row_count)
                for error in validation_errors[:5]:  # Show first 5 errors
                    error_summary += f"\n  - {error}"
                if len(validation_errors) > 5:
                    error_summary += "\n  " + _t("health_misc.security.more_errors", count=len(validation_errors) - 5)
                return False, error_summary

            return True, _t("health_misc.security.validation_passed", rows=row_count, delimiter=delimiter)

    except UnicodeDecodeError:
        return False, _t("health_misc.security.encoding_error")
    except PermissionError:
        return False, _t("health_misc.security.permission_denied")
    except Exception as e:
        return False, _t("health_misc.security.validation_error", error=str(e))
