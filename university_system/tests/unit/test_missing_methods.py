#!/usr/bin/env python3
"""
Test script to identify potential missing methods and attributes that could cause AttributeErrors.
"""

import re
import sys

def scan_for_potential_issues():
    """Scan the code for potential missing method/attribute issues"""
    print("🔍 Scanning for potential AttributeError sources...")

    try:
        with open('university_system/interfaces/gui/grade_tracking_gui.py', 'r') as f:
            content = f.read()

        # Find all method calls that start with self.
        method_calls = re.findall(r'self\.(\w+)\(', content)
        attribute_access = re.findall(r'self\.(\w+)(?:\[|\.|$)', content)

        # Find all defined methods
        defined_methods = re.findall(r'def (\w+)\(', content)

        # Find potentially missing methods (called but not defined)
        called_methods = set(method_calls)
        defined_methods_set = set(defined_methods)

        potentially_missing = called_methods - defined_methods_set

        # Filter out common attributes that aren't methods
        common_attributes = {
            'root', 'cursor', 'conn', 'current_view', 'content_frame', 'notebook',
            'status_var', 'student_combo', 'assessment_combo', 'transcript_student_combo',
            'grades_tree', 'student_tree', 'assessment_tree', 'module_tree',
            'transcript_student_var', 'transcript_format', 'transcript_status'
        }

        potentially_missing = potentially_missing - common_attributes

        print(f"✅ Found {len(defined_methods)} defined methods")
        print(f"✅ Found {len(called_methods)} method calls")

        if potentially_missing:
            print(f"⚠️  Potentially missing methods:")
            for method in sorted(potentially_missing):
                print(f"   - {method}()")
        else:
            print("✅ No obviously missing methods detected")

        # Check for combo box references that might cause issues
        combo_refs = re.findall(r'self\.(\w+_combo)\[', content)
        unique_combos = set(combo_refs)

        print(f"\n📋 Found references to {len(unique_combos)} different combo boxes:")
        for combo in sorted(unique_combos):
            print(f"   - {combo}")

        return len(potentially_missing) == 0

    except Exception as e:
        print(f"❌ Error scanning file: {e}")
        return False

def main():
    """Run the scan"""
    print("=" * 60)
    print("MISSING METHODS/ATTRIBUTES DETECTION")
    print("=" * 60)

    if scan_for_potential_issues():
        print("\n🎉 No obvious missing methods detected!")
        print("\n✅ RECENT FIXES:")
        print("   - Added generate_interventions_for_filter() method")
        print("   - Added safe combo box value copying")
        print("   - Added transcript student auto-population")
        return True
    else:
        print("\n⚠️  Potential issues detected - review above")
        return False

if __name__ == "__main__":
    main()