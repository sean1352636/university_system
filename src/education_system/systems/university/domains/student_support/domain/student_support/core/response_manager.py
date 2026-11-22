"""
Ticket response handling for Student Support.
"""

import datetime
import json
import logging

from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support import service as _service

logger = logging.getLogger(__name__)


def add_ticket_response(ticket_id, response_text, template_id=None, is_internal=False, attachments=None):
    """Add a response to a support ticket as the signed-in user.

    Students can only reply to their own tickets and can never add an
    internal note. Returns True.
    """
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to respond to a ticket")

    if not response_text:
        raise ValueError("Response text is required")

    _service.add_response(_auth_mod.auth, ticket_id, response_text, internal=bool(is_internal),
                          template_id=template_id, attachments=attachments)
    logger.info(f"Added response to ticket #{ticket_id} by {_auth_mod.auth.current_user['username']}")
    return True


def _apply_response_template(template_id, ticket_id, response_text, cursor):
    """Apply response template with variable substitution"""
    cursor.execute('SELECT content, variables FROM response_templates WHERE template_id = ? AND is_active = 1', (template_id,))
    template_data = cursor.fetchone()

    if not template_data:
        return response_text

    template_content, variables_json = template_data[0], template_data[1]
    variables = json.loads(variables_json or '[]')

    # Replace variables
    replacements = {
        'TICKET_ID': str(ticket_id),
        'USER_NAME': (_auth_mod.user_of() or {}).get('username', 'User'),
        'CURRENT_DATE': datetime.datetime.now().strftime('%Y-%m-%d'),
        'CURRENT_TIME': datetime.datetime.now().strftime('%H:%M:%S')
    }

    for var in variables:
        if var in replacements:
            template_content = template_content.replace(f'[{var}]', replacements[var])

    # Combine template with additional text
    if response_text and response_text != template_content:
        return f"{template_content}\n\n{response_text}"

    return template_content


def add_response_enhanced(support, ticket_id):
    """Add response with template support"""
    try:
        # Get response templates
        templates = support.get_response_templates()

        if templates and _auth_mod.is_support_staff():
            print("\n📝 Response Templates:")
            print("0. Write custom response")
            for i, template in enumerate(templates[:10], 1):  # Show first 10
                print(f"{i}. {template['name']}")

            template_choice = input("\nSelect template (0 for custom): ").strip()

            if template_choice.isdigit() and 1 <= int(template_choice) <= len(templates):
                template = templates[int(template_choice) - 1]
                response_text = template['content']
                print(f"\nUsing template: {template['name']}")
                print(f"Template content:\n{response_text}")

                additional = input("\nAdditional text (optional): ").strip()
                if additional:
                    response_text += f"\n\n{additional}"

                template_id = template['template_id']
            else:
                response_text = input("\nEnter your response: ").strip()
                template_id = None
        else:
            response_text = input("\nEnter your response: ").strip()
            template_id = None

        if not response_text:
            print("❌ Response cannot be empty.")
            return

        # Internal note option for staff
        is_internal = False
        if _auth_mod.is_support_staff():
            is_internal = input("Internal note (visible only to staff)? (y/n): ").lower() == 'y'

        # Add response
        support.add_ticket_response(ticket_id, response_text, template_id, is_internal)
        print("✅ Response added successfully!")

    except Exception as e:
        print(f"❌ Error adding response: {e}")
