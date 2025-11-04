from __future__ import annotations

from datetime import datetime

from university_system.modules.core.services.health_misc.health_context import cipher_suite

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
    except:
        return encrypted_data

def truthy(x):
    return str(x).strip().lower() in ("1", "true", "yes", "y", "t")

def validate_csv_format(filename):
    """Validate CSV file format before import"""
    if not filename:
        return False, "No filename provided"

    if not os.path.exists(filename):
        return False, f"File '{filename}' not found"

    if not filename.lower().endswith('.csv'):
        return False, "File must have .csv extension"

    try:
        # Check file size (warn if very large)
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:  # 50MB
            return False, f"File too large ({file_size / (1024*1024):.1f}MB). Maximum recommended size is 50MB"

        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            # Read sample to detect format
            sample = csvfile.read(1024)
            csvfile.seek(0)

            if not sample.strip():
                return False, "File appears to be empty"

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
                return False, "No header row found"

            # Clean fieldnames (remove whitespace)
            clean_fieldnames = [field.strip().lower() for field in reader.fieldnames]
            required_lower = [field.lower() for field in required_fields]

            missing_fields = []
            for field in required_lower:
                if field not in clean_fieldnames:
                    missing_fields.append(field)

            if missing_fields:
                return False, f"Missing required columns: {', '.join(missing_fields)}. Found: {', '.join(reader.fieldnames)}"

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
                        validation_errors.append(f"Row {row_count + 1}: Empty '{field}' field")

                # Validate date format
                date_value = row.get('record_date', '').strip()
                if date_value:
                    try:
                        parsed_date = datetime.strptime(date_value, '%Y-%m-%d')
                        # Check reasonable date range
                        current_year = datetime.now().year
                        if parsed_date.year < 1900 or parsed_date.year > current_year + 1:
                            validation_errors.append(f"Row {row_count + 1}: Date '{date_value}' outside reasonable range")
                    except ValueError:
                        validation_errors.append(f"Row {row_count + 1}: Invalid date format '{date_value}' (expected YYYY-MM-DD)")

                # Validate record type if present
                record_type = row.get('record_type', '').strip()
                if record_type:
                    valid_types = ['medical_exam', 'vaccination', 'injury', 'illness', 'mental_health', 'prescription', 'other']
                    if record_type.lower() not in [t.lower() for t in valid_types]:
                        validation_errors.append(f"Row {row_count + 1}: Invalid record type '{record_type}'. Valid types: {', '.join(valid_types)}")

                # Validate confidential field if present
                confidential = row.get('confidential', '').strip().lower()
                if confidential and confidential not in ['true', 'false', '1', '0', 'yes', 'no', 'y', 'n']:
                    validation_errors.append(f"Row {row_count + 1}: Invalid confidential value '{confidential}' (use true/false)")

            # Return validation results
            if validation_errors:
                error_summary = f"Found {len(validation_errors)} validation errors in first {row_count} rows:"
                for error in validation_errors[:5]:  # Show first 5 errors
                    error_summary += f"\n  - {error}"
                if len(validation_errors) > 5:
                    error_summary += f"\n  ... and {len(validation_errors) - 5} more errors"
                return False, error_summary

            return True, f"Validation passed: {row_count} sample rows checked, delimiter='{delimiter}'"

    except UnicodeDecodeError:
        return False, "File encoding error. Ensure file is saved as UTF-8"
    except PermissionError:
        return False, "Permission denied accessing file"
    except Exception as e:
        return False, f"Error validating file: {str(e)}"
