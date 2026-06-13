#!/usr/bin/env python3
"""
Script to update all Python files to use centralized email template system
"""

import re
import os

from education_system.university_system.core.i18n import get_text as _t

# File paths and their email template mappings
file_updates = {
    # Student Union GUI
    'university_system/modules/interfaces/gui/student_union_gui.py': {
        'imports': 'from education_system.university_system.infrastructure.email.template_utils import render_template',
        'replacements': [
            {
                'pattern': r'subject = f"🎉 New Club Alert: \{club_name\} Now Available!"\s+for email, first_name, last_name in students:\s+message = f"""Dear \{first_name\} \{last_name\},.*?"""',
                'replacement': '''template_vars = {'club_name': club_name}
            subject_template, body_template = render_template('club_announcement', template_vars)

            for email, first_name, last_name in students:
                template_vars_personal = template_vars.copy()
                template_vars_personal['recipient_name'] = f"{first_name} {last_name}"
                subject, message = render_template('club_announcement', template_vars_personal)''',
                'flags': re.DOTALL
            }
        ]
    }
}

def update_file_simple(filepath):
    """Simple approach: Just add the import statement"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if import already exists
        if 'from education_system.university_system.infrastructure.email.template_utils import render_template' in content:
            print(_t("scripts.update_email_templates.already_has_import", filename=os.path.basename(filepath)))
            return

        # Find a good place to add the import (after other imports)
        import_lines = []
        other_lines = []
        in_imports = True

        for line in content.split('\n'):
            if in_imports and (line.startswith('import ') or line.startswith('from ') or line.strip() == '' or line.strip().startswith('#')):
                import_lines.append(line)
            else:
                if in_imports and line.strip() and not line.strip().startswith('#'):
                    in_imports = False
                    # Add our import before the first non-import line
                    import_lines.append('from education_system.university_system.infrastructure.email.template_utils import render_template')
                other_lines.append(line)

        new_content = '\n'.join(import_lines) + '\n' + '\n'.join(other_lines)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(_t("scripts.update_email_templates.import_added", filename=os.path.basename(filepath)))

    except Exception as e:
        print(_t("scripts.update_email_templates.error", filename=os.path.basename(filepath), error=e))

# List of all files to update
files_to_update = [
    'university_system/modules/interfaces/gui/student_union_gui.py',
    'university_system/modules/domain/student_affairs/gui/alumni/main_gui.py',
    'university_system/modules/domain/student_affairs/gui/internship_management/internship_gui.py',
    'university_system/modules/interfaces/gui/health_portal_gui.py',
    'university_system/modules/domain/academics/gui/attendance_tracker/',
    'university_system/modules/interfaces/gui/library_gui.py',
    'university_system/modules/interfaces/gui/restaurant_management_gui.py',
    'university_system/modules/interfaces/gui/shop_management_gui.py',
    'university_system/modules/domain/academics/gui/module_scheduling/',
    'university_system/modules/domain/student_affairs/student_union/administration/admin_management.py',
    'university_system/modules/core/services/student_union_misc/voting.py',
]

if __name__ == '__main__':
    print(_t("scripts.update_email_templates.updating_files"))
    for filepath in files_to_update:
        if os.path.exists(filepath):
            update_file_simple(filepath)
        else:
            print(_t("scripts.update_email_templates.file_not_found", filename=os.path.basename(filepath)))
    print(_t("scripts.update_email_templates.completion_message"))
