#!/usr/bin/env python3
"""
Script to systematically replace debug print() statements with proper Python logging.

This script:
1. Adds logging import and logger initialization if not present
2. Replaces debug/error print statements with appropriate logging calls
3. Preserves user-facing CLI print statements
"""

import re
import os
from pathlib import Path

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


def has_logger(content):
    """Check if file already has logger defined."""
    return bool(re.search(r'^logger\s*=\s*logging\.getLogger', content, re.MULTILINE))


def has_logging_import(content):
    """Check if file has logging import."""
    return 'import logging' in content


def add_logger_if_missing(content):
    """Add logger initialization if missing."""
    if has_logger(content):
        return content

    if not has_logging_import(content):
        # Add import at the top
        lines = content.split('\n')
        # Find first import or module docstring
        insert_line = 0
        in_docstring = False
        for i, line in enumerate(lines):
            if line.strip().startswith('"""') or line.strip().startswith("'''"):
                if in_docstring:
                    in_docstring = False
                    insert_line = i + 1
                else:
                    in_docstring = True
            elif not in_docstring and line.startswith('import ') or line.startswith('from '):
                insert_line = i
                break

        lines.insert(insert_line, 'import logging')
        content = '\n'.join(lines)

    # Add logger after imports
    lines = content.split('\n')
    last_import = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import = i

    lines.insert(last_import + 1, '\n# Initialize logger')
    lines.insert(last_import + 2, 'logger = logging.getLogger(__name__)\n')

    return '\n'.join(lines)


def replace_debug_prints(content):
    """Replace debug print statements with logging calls."""

    # Patterns for debug/error prints (not user-facing)
    replacements = [
        # Error prints
        (r'print\(f"❌\s*(.+?)"\)', r'logger.error(f"\1")'),
        (r"print\(f'❌\s*(.+?)'\)", r"logger.error(f'\1')"),
        (r'print\("❌\s*(.+?)"\)', r'logger.error("\1")'),
        (r'print\(f"Error\s*(.+?)"\)', r'logger.error(f"Error \1")'),
        (r'print\(f".*error:\s*\{e\}"\)', r'logger.error(f"Error: {e}")'),
        (r'print\(f"Database error:\s*\{e\}"\)', r'logger.error(f"Database error: {e}")'),
        (r'print\(f"(.+?)\s+error:\s*\{e\}"\)', r'logger.error(f"\1 error: {e}")'),

        # Warning prints
        (r'print\(f"⚠️\s*(.+?)"\)', r'logger.warning(f"\1")'),
        (r"print\(f'⚠️\s*(.+?)'\)", r"logger.warning(f'\1')"),
        (r'print\("⚠️\s*(.+?)"\)', r'logger.warning("\1")'),

        # Success/Info prints
        (r'print\(f"✅\s*(.+?)"\)', r'logger.info(f"\1")'),
        (r"print\(f'✅\s*(.+?)'\)", r"logger.info(f'\1')"),
        (r'print\("✅\s*(.+?)"\)', r'logger.info("\1")'),

        # Debug prints
        (r'print\(f"Debug:\s*(.+?)"\)', r'logger.debug(f"\1")'),
        (r'print\("Debug:\s*(.+?)"\)', r'logger.debug("\1")'),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    return content


def process_file(filepath):
    """Process a single Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip if it's a test file or already fully migrated
        if 'test_' in os.path.basename(filepath):
            return False, _t("scripts.fix_logging.skipped_test_file")

        original_content = content

        # Add logger if missing
        content = add_logger_if_missing(content)

        # Replace debug prints
        content = replace_debug_prints(content)

        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, _t("scripts.fix_logging.updated")

        return False, _t("scripts.fix_logging.no_changes_needed")

    except Exception as e:
        return False, _t("scripts.fix_logging.error", error=str(e))


def main():
    """Main function to process all priority files."""
    base_dir = Path('/home/seancatchpole989/university_system')

    # Priority files from improvements.txt
    priority_files = [
        base_dir / 'infrastructure/auth/user_authentication.py',
        base_dir / 'infrastructure/database/data_backup.py',
        base_dir / 'infrastructure/email/admin.py',
        base_dir / 'infrastructure/email/announcements.py',
        base_dir / 'infrastructure/email/chat_rooms.py',
        base_dir / 'infrastructure/email/database.py',
        base_dir / 'infrastructure/email/email_manager.py',
        base_dir / 'infrastructure/email/email_service.py',
        base_dir / 'infrastructure/email/misc.py',
        base_dir / 'infrastructure/email/reports.py',
        base_dir / 'infrastructure/email/template_utils.py',
    ]

    # Process GUI files
    gui_dir = base_dir / 'modules/interfaces/gui'
    if gui_dir.exists():
        priority_files.extend(gui_dir.glob('*.py'))

    print("=" * 80)
    print(_t("scripts.fix_logging.title"))
    print("=" * 80)
    print(_t("scripts.fix_logging.processing_files", count=len(priority_files)))

    updated = []
    skipped = []
    errors = []

    for filepath in priority_files:
        if not filepath.exists():
            skipped.append((str(filepath), _t("scripts.fix_logging.file_not_found")))
            continue

        success, message = process_file(filepath)

        if success:
            updated.append(str(filepath))
            print(_t("scripts.fix_logging.file_updated", name=filepath.name, message=message))
        elif _t("scripts.fix_logging.error", error="") in message:
            errors.append((str(filepath), message))
            print(_t("scripts.fix_logging.file_error", name=filepath.name, message=message))
        else:
            skipped.append((str(filepath), message))
            print(_t("scripts.fix_logging.file_skipped", name=filepath.name, message=message))

    # Summary
    print("\n" + "=" * 80)
    print(_t("scripts.fix_logging.summary_title"))
    print("=" * 80)
    print(_t("scripts.fix_logging.updated_count", count=len(updated)))
    print(_t("scripts.fix_logging.skipped_count", count=len(skipped)))
    print(_t("scripts.fix_logging.errors_count", count=len(errors)))

    if updated:
        print(_t("scripts.fix_logging.updated_files_header"))
        for f in updated:
            print(f"  - {f}")

    if errors:
        print(_t("scripts.fix_logging.errors_header"))
        for f, msg in errors:
            print(f"  - {f}: {msg}")


if __name__ == '__main__':
    main()
