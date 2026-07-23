# dialogs/details_dialog.py
# Dialog for showing accommodation details.

from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation._common import tk, ttk, ScrolledText, logger


class DetailsDialog:
    """Dialog for showing accommodation details"""

    def __init__(self, parent, accommodation, documents):
        # Normalize rows to dictionaries in case callers pass sqlite3.Row objects
        try:
            accommodation = dict(accommodation)
        except (TypeError, ValueError) as e:
            # Already a dict or incompatible type; leave as-is
            logger.debug(f"Accommodation data is already in expected format: {e}")

        normalized_docs = []
        for doc in documents:
            try:
                normalized_docs.append(dict(doc))
            except (TypeError, ValueError):
                normalized_docs.append(doc)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Accommodation Details - ID {accommodation['id']}")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets(accommodation, normalized_docs)

    def create_widgets(self, accommodation, documents):
        """Create detail widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Details text
        self.details_text = ScrolledText(main_frame, width=70, height=25)
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # Format details
        student_name = f"{accommodation['first_name'] or ''} {accommodation['last_name'] or ''}".strip() or 'N/A'

        details = f"""
ACCOMMODATION DETAILS
{'='*60}

ID: {accommodation['id']}
Student: {accommodation['student_id']} - {student_name}
Email: {accommodation['email_address'] or 'N/A'}
Type: {accommodation['accommodation_type']}
Description: {accommodation['description'] or 'N/A'}
Start Date: {accommodation['start_date'] or 'Not specified'}
End Date: {accommodation['end_date'] or 'Not specified'}
Status: {accommodation['status']}
Approved By: {accommodation.get('approved_by') or 'N/A'}
Approval Date: {accommodation.get('approval_date') or 'N/A'}
Notes: {accommodation['notes'] or 'N/A'}
Created: {accommodation['created_at']}
Last Updated: {accommodation['updated_at']}
"""

        if documents:
            details += f"\n\nATTACHED DOCUMENTS:\n{'-'*60}\n"
            for doc in documents:
                details += f"- {doc['document_name']} (Uploaded: {doc['uploaded_at']})\n"
        else:
            details += "\n\nNo attached documents."

        self.details_text.insert(tk.END, details)
        self.details_text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
