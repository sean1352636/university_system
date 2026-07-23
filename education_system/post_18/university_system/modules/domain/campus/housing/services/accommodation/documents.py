import os
import logging
import shutil
from datetime import datetime

from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, UPLOADS_DIR, get_auth, get_current_user, get_text,
    SECURE_UPLOAD_AVAILABLE, validate_upload, secure_filename, logger,
)
from education_system.post_18.university_system.modules.domain.campus.housing.services.accommodation.audit import log_action


def upload_accommodation_document(accommodation_id):
    """Upload a document for an accommodation by copying the file to a managed directory."""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_upload", "You must be logged in to upload documents."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_upload", "You don't have permission to upload documents."))
        return

    try:
        document_name = input(get_text("housing.accommodation.input.enter_document_name", "Enter document name: ")).strip()
        if not document_name:
            print(get_text("housing.accommodation.error.document_name_required", "Error: Document name is required."))
            return

        file_path = input(get_text("housing.accommodation.input.enter_file_path", "Enter full path to the file: ")).strip()
        if not file_path or not os.path.exists(file_path):
            print(get_text("housing.accommodation.error.invalid_file_path", "Error: File path is invalid or file does not exist."))
            return

        # Read file content for secure validation
        original_filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Validate file using secure upload handler
        if SECURE_UPLOAD_AVAILABLE and validate_upload:
            validation = validate_upload(original_filename, file_content, category='documents')
            if not validation['valid']:
                print(f"Error: File validation failed - {validation['error']}")
                logger.warning(f"Secure upload validation failed for {original_filename}: {validation['error']}")
                return
            safe_name = validation['safe_filename']
        else:
            safe_name = secure_filename(original_filename)

        # Ensure uploads directory exists with restrictive permissions
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        try:
            os.chmod(UPLOADS_DIR, 0o700)
        except OSError:
            pass

        # Create a safe unique filename
        ext = os.path.splitext(safe_name)[1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{accommodation_id}_{timestamp}{ext}"
        destination_path = os.path.join(UPLOADS_DIR, unique_filename)

        # Copy the file to uploads dir securely
        shutil.copy(file_path, destination_path)

        # Set restrictive permissions on uploaded file
        try:
            os.chmod(destination_path, 0o600)
        except OSError:
            pass

        logger.info(f"Accommodation document uploaded securely: {unique_filename}")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = get_current_user()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents
                (source_type, reference_id, reference_type, document_name,
                 file_path, uploaded_by, upload_date)
                VALUES ('accommodation', ?, 'accommodation', ?, ?, ?, ?)
            ''', (str(accommodation_id), document_name, destination_path, user, now))
            conn.commit()

        print(get_text("housing.accommodation.success.document_uploaded", "Document uploaded and recorded successfully."))
        log_action('upload_document', accommodation_id, f"Uploaded document: {document_name}")

    except Exception as e:
        logging.error(f"Error uploading document: {e}")
        print(get_text("housing.accommodation.error.uploading_document", "Error uploading document: {error}").format(error=e))
