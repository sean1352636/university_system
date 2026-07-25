"""Data Mapping Tools Manager and CLI functions"""

from education_system.systems.university.services.integrations.integration_marketplace_core._imports import json, re, Any, Dict, List, get_connection, transaction


class DataMappingToolsManager:
    """Advanced data mapping tools"""

    @staticmethod
    def auto_detect_mappings(install_id: int, source_fields: List[str],
                            target_fields: List[str]) -> List[Dict[str, Any]]:
        """Automatically suggest field mappings based on names"""
        suggestions = []

        # Normalize field names for comparison
        def normalize(name):
            return re.sub(r'[^a-z0-9]', '', name.lower())

        source_normalized = {normalize(f): f for f in source_fields}
        target_normalized = {normalize(f): f for f in target_fields}

        # Find exact matches
        for src_norm, src_orig in source_normalized.items():
            if src_norm in target_normalized:
                suggestions.append({
                    'source_field': src_orig,
                    'target_field': target_normalized[src_norm],
                    'confidence': 1.0,
                    'match_type': 'exact'
                })

        # Find partial matches
        for src_norm, src_orig in source_normalized.items():
            if src_norm not in target_normalized:  # Skip already matched
                for tgt_norm, tgt_orig in target_normalized.items():
                    if tgt_norm not in [s['target_field'] for s in suggestions if s['confidence'] == 1.0]:
                        # Check if one contains the other
                        if src_norm in tgt_norm or tgt_norm in src_norm:
                            suggestions.append({
                                'source_field': src_orig,
                                'target_field': tgt_orig,
                                'confidence': 0.7,
                                'match_type': 'partial'
                            })

        # Common field name mappings
        common_mappings = {
            'firstname': ['first_name', 'fname', 'givenname'],
            'lastname': ['last_name', 'lname', 'surname', 'familyname'],
            'email': ['emailaddress', 'mail', 'e_mail'],
            'phone': ['phonenumber', 'tel', 'telephone', 'mobile'],
            'id': ['identifier', 'uuid', 'key'],
            'createdat': ['created', 'creationdate', 'datecreated'],
            'updatedat': ['updated', 'modifiedat', 'lastmodified']
        }

        for src_norm, src_orig in source_normalized.items():
            for base, alternatives in common_mappings.items():
                if src_norm == base or src_norm in alternatives:
                    for tgt_norm, tgt_orig in target_normalized.items():
                        if tgt_norm == base or tgt_norm in alternatives:
                            if not any(s['source_field'] == src_orig and s['target_field'] == tgt_orig for s in suggestions):
                                suggestions.append({
                                    'source_field': src_orig,
                                    'target_field': tgt_orig,
                                    'confidence': 0.8,
                                    'match_type': 'semantic'
                                })

        return sorted(suggestions, key=lambda x: -x['confidence'])

    @staticmethod
    def preview_transformation(mapping_id: int, sample_data: Any) -> Dict[str, Any]:
        """Preview transformation rule output on sample data"""
        result = {'mapping_id': mapping_id, 'input': sample_data, 'output': None, 'error': None}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transformation_rule FROM integration_data_mappings
                WHERE mapping_id = ?
            ''', (mapping_id,))
            mapping = cursor.fetchone()

        if not mapping:
            result['error'] = 'Mapping not found'
            return result

        rule = mapping['transformation_rule']
        if not rule:
            result['output'] = sample_data
            result['message'] = 'No transformation (direct copy)'
            return result

        try:
            # Apply common transformations
            if rule.upper().startswith('UPPER'):
                result['output'] = str(sample_data).upper()
            elif rule.upper().startswith('LOWER'):
                result['output'] = str(sample_data).lower()
            elif rule.upper().startswith('TRIM'):
                result['output'] = str(sample_data).strip()
            elif rule.startswith('{') and rule.endswith('}'):
                # JSON template
                template = json.loads(rule)
                result['output'] = template
            else:
                result['output'] = sample_data
                result['message'] = 'Unknown transformation, using direct copy'
        except Exception as e:
            result['error'] = str(e)

        return result

    @staticmethod
    def duplicate_mapping_set(install_id: int, new_install_id: int) -> Dict[str, Any]:
        """Clone an existing mapping configuration"""
        result = {'source_install_id': install_id, 'target_install_id': new_install_id, 'mappings_copied': 0}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT source_field, target_field, transformation_rule, is_active
                FROM integration_data_mappings
                WHERE install_id = ?
            ''', (install_id,))
            mappings = cursor.fetchall()

        with transaction() as conn:
            cursor = conn.cursor()
            for mapping in mappings:
                cursor.execute('''
                    INSERT INTO integration_data_mappings
                    (install_id, source_field, target_field, transformation_rule, is_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (new_install_id, mapping['source_field'], mapping['target_field'],
                      mapping['transformation_rule'], mapping['is_active']))
                result['mappings_copied'] += 1

        return result

    @staticmethod
    def import_mappings_from_template(install_id: int, template_name: str) -> Dict[str, Any]:
        """Import standard mapping templates"""
        templates = {
            'student_basic': [
                {'source': 'student_id', 'target': 'id', 'transform': None},
                {'source': 'first_name', 'target': 'firstName', 'transform': 'TRIM'},
                {'source': 'last_name', 'target': 'lastName', 'transform': 'TRIM'},
                {'source': 'email', 'target': 'emailAddress', 'transform': 'LOWER'},
                {'source': 'enrollment_date', 'target': 'enrolledAt', 'transform': None}
            ],
            'course_basic': [
                {'source': 'course_id', 'target': 'id', 'transform': None},
                {'source': 'course_name', 'target': 'title', 'transform': None},
                {'source': 'course_code', 'target': 'code', 'transform': 'UPPER'},
                {'source': 'credits', 'target': 'creditHours', 'transform': None}
            ],
            'grade_basic': [
                {'source': 'grade_id', 'target': 'id', 'transform': None},
                {'source': 'student_id', 'target': 'studentId', 'transform': None},
                {'source': 'course_id', 'target': 'courseId', 'transform': None},
                {'source': 'grade', 'target': 'letterGrade', 'transform': 'UPPER'},
                {'source': 'points', 'target': 'gradePoints', 'transform': None}
            ]
        }

        if template_name not in templates:
            return {'error': f"Template '{template_name}' not found. Available: {list(templates.keys())}"}

        result = {'install_id': install_id, 'template': template_name, 'mappings_created': 0}

        with transaction() as conn:
            cursor = conn.cursor()
            for mapping in templates[template_name]:
                cursor.execute('''
                    INSERT INTO integration_data_mappings
                    (install_id, source_field, target_field, transformation_rule, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (install_id, mapping['source'], mapping['target'], mapping['transform']))
                result['mappings_created'] += 1

        return result


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def auto_detect_mappings():
    """Automatically suggest field mappings based on names"""
    print("\n" + "="*50)
    print("      AUTO-DETECT FIELD MAPPINGS")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nEnter source fields (comma-separated):")
    source_input = input("> ").strip()
    if not source_input:
        print("Source fields are required.")
        return
    source_fields = [f.strip() for f in source_input.split(',')]

    print("\nEnter target fields (comma-separated):")
    target_input = input("> ").strip()
    if not target_input:
        print("Target fields are required.")
        return
    target_fields = [f.strip() for f in target_input.split(',')]

    try:
        suggestions = DataMappingToolsManager.auto_detect_mappings(install_id, source_fields, target_fields)

        if not suggestions:
            print("\nNo mapping suggestions found.")
            return

        print(f"\n--- SUGGESTED MAPPINGS ({len(suggestions)}) ---")
        print(f"{'Source':<25} {'Target':<25} {'Confidence':<12} {'Match Type':<12}")
        print("-" * 80)

        for s in suggestions:
            confidence = f"{s.get('confidence', 0) * 100:.0f}%"
            print(f"{s.get('source_field', 'N/A'):<25} "
                  f"{s.get('target_field', 'N/A'):<25} "
                  f"{confidence:<12} "
                  f"{s.get('match_type', 'N/A'):<12}")

        print("\nUse Data Mappings to create these mappings.")

    except Exception as e:
        print(f"\nError detecting mappings: {e}")


def preview_transformation():
    """Preview transformation rule output on sample data"""
    print("\n" + "="*50)
    print("      PREVIEW TRANSFORMATION")
    print("="*50)

    try:
        mapping_id = int(input("Enter mapping ID: ").strip())
    except ValueError:
        print("Invalid mapping ID.")
        return

    sample_data = input("Enter sample data to transform: ").strip()
    if not sample_data:
        print("Sample data is required.")
        return

    try:
        result = DataMappingToolsManager.preview_transformation(mapping_id, sample_data)

        print("\n--- TRANSFORMATION PREVIEW ---")
        print(f"  Input:  {result.get('input', 'N/A')}")
        print(f"  Output: {result.get('output', 'N/A')}")

        if result.get('error'):
            print(f"  Error: {result.get('error')}")
        elif result.get('message'):
            print(f"  Note: {result.get('message')}")

    except Exception as e:
        print(f"\nError previewing transformation: {e}")


def duplicate_mapping_set():
    """Clone an existing mapping configuration"""
    print("\n" + "="*50)
    print("      DUPLICATE MAPPING SET")
    print("="*50)

    try:
        source_id = int(input("Source install ID (copy from): ").strip())
        target_id = int(input("Target install ID (copy to): ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    if source_id == target_id:
        print("Source and target must be different.")
        return

    confirm = input(f"Copy all mappings from install {source_id} to {target_id}? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = DataMappingToolsManager.duplicate_mapping_set(source_id, target_id)
        print("\nMappings duplicated successfully!")
        print(f"  From: Install ID {result.get('source_install_id')}")
        print(f"  To: Install ID {result.get('target_install_id')}")
        print(f"  Mappings copied: {result.get('mappings_copied')}")

    except Exception as e:
        print(f"\nError duplicating mappings: {e}")


def import_mappings_from_template():
    """Import standard mapping templates"""
    print("\n" + "="*50)
    print("      IMPORT MAPPING TEMPLATE")
    print("="*50)

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    print("\nAvailable templates:")
    print("  - student_basic: Standard student fields")
    print("  - course_basic: Standard course fields")
    print("  - grade_basic: Standard grade fields")

    template_name = input("\nTemplate name: ").strip().lower()
    if not template_name:
        print("Template name is required.")
        return

    try:
        result = DataMappingToolsManager.import_mappings_from_template(install_id, template_name)

        if result.get('error'):
            print(f"\n[X] Error: {result.get('error')}")
            return

        print("\nTemplate imported successfully!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Template: {result.get('template')}")
        print(f"  Mappings created: {result.get('mappings_created')}")

    except Exception as e:
        print(f"\nError importing template: {e}")
