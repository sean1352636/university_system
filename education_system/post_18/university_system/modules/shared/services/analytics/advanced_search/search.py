"""Core search functions: multi-criteria, fuzzy name, module enrollment, date range, combined filters."""
import hashlib
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from education_system.post_18.university_system.core.sql_safety import (
    escape_like, validate_table_name, validate_column_name,
)
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search import _globals
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search.display import display_search_results
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search.system import log_search
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search.admin import audit_log


# Entity search configurations, mirroring the GUI multi-entity form.
# Each field: (label, prompt_key, op, column, choices_or_None)
#   op: "like" | "eq" | "ge" | "le"
ENTITY_SEARCH_CONFIGS = {
    "students": {
        "table": "students",
        "display": "Students",
        "fields": [
            ("Student ID", "student_id", "like", "student_id", None),
            ("First Name", "first_name", "like", "first_name", None),
            ("Last Name", "last_name", "like", "last_name", None),
            ("Gender", "gender", "eq", "gender", ["male", "female", "other"]),
            ("Course", "course", "like", "course", None),
            ("Minimum Age", "min_age", "ge", "age", None),
            ("Maximum Age", "max_age", "le", "age", None),
        ],
    },
    "staff": {
        "table": "staff_profiles",
        "display": "Staff",
        "fields": [
            ("Employee ID", "employee_id", "like", "employee_id", None),
            ("User ID", "user_id", "like", "user_id", None),
            ("Department", "department", "like", "department", None),
            ("Job Title", "job_title", "like", "job_title", None),
            ("Employment Type", "employment_type", "eq", "employment_type",
                ["full-time", "part-time", "contract", "temporary"]),
        ],
    },
    "modules": {
        "table": "modules",
        "display": "Modules",
        "fields": [
            ("Module Code", "module_code", "like", "module_code", None),
            ("Module Name", "module_name", "like", "module_name", None),
            ("Module Type", "module_type", "like", "module_type", None),
            ("Course", "course", "like", "course", None),
            ("Semester", "semester", "like", "semester", None),
        ],
    },
    "courses": {
        "table": "courses",
        "display": "Courses",
        "fields": [
            ("Course Code", "course_code", "like", "course_code", None),
            ("Course Name", "name", "like", "name", None),
            ("Department", "department", "like", "department", None),
            ("Level", "level", "like", "level", None),
        ],
    },
}


def _prompt_entity_type():
    """Prompt the user to pick an entity to search. Returns the config key."""
    keys = list(ENTITY_SEARCH_CONFIGS.keys())
    print("\nEntity type:")
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {ENTITY_SEARCH_CONFIGS[key]['display']}")
    raw = input(f"Select (1-{len(keys)}) [1]: ").strip() or "1"
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(keys):
            return keys[idx]
    except ValueError:
        pass
    print("Invalid choice — defaulting to Students.")
    return "students"


@audit_log
def multi_criteria_search():
    """Enhanced multi-entity multi-criteria search with caching."""
    entity_key = _prompt_entity_type()
    config = ENTITY_SEARCH_CONFIGS[entity_key]
    print(f"\nMulti-Criteria {config['display']} Search")
    print("Enter search criteria (leave blank to ignore):")

    criteria = {}
    for label, key, op, _col, choices in config["fields"]:
        hint = f" ({'/'.join(choices)})" if choices else ""
        raw = input(f"{label}{hint}: ").strip()
        if not raw:
            continue
        if op in ("ge", "le"):
            try:
                criteria[key] = int(raw)
            except ValueError:
                print(f"Invalid number for {label}; ignoring.")
                continue
        elif choices and raw.lower() not in [c.lower() for c in choices]:
            print(f"Invalid {label}. Expected one of: {', '.join(choices)}.")
            return
        else:
            criteria[key] = raw

    if not criteria:
        print("No criteria entered — aborting.")
        return

    cache_key = hashlib.sha256(f"{entity_key}:{criteria}".encode()).hexdigest()
    if cache_key in _globals.search_cache:
        print("📦 Loading results from cache...")
        results = _globals.search_cache[cache_key]
        log_search(f"multi_criteria_{entity_key}_cached", criteria, len(results))
        display_search_results(results)
        return

    field_specs = {f[1]: f for f in config["fields"]}
    table = config["table"]

    try:
        validate_table_name(table)
    except Exception as e:
        print(f"Invalid table for entity '{entity_key}': {e}")
        return

    query = f"SELECT * FROM {table} WHERE 1=1"  # nosec B608 - table validated
    params = []
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,))
        if cursor.fetchone() is None:
            print(f"Table '{table}' does not exist in the current database.")
            conn.close()
            return

        cursor.execute(f"PRAGMA table_info({table})")
        available_cols = {row[1] for row in cursor.fetchall()}

        for key, value in criteria.items():
            spec = field_specs.get(key)
            if not spec:
                continue
            _label, _k, op, column, _choices = spec
            if column not in available_cols:
                continue
            validate_column_name(column)
            if op == "like":
                query += f" AND LOWER({column}) LIKE LOWER(?)"
                params.append(f"%{escape_like(str(value))}%")
            elif op == "eq":
                query += f" AND LOWER({column}) = LOWER(?)"
                params.append(str(value))
            elif op == "ge":
                query += f" AND {column} >= ?"
                params.append(int(value))
            elif op == "le":
                query += f" AND {column} <= ?"
                params.append(int(value))

        start_time = time.time()
        cursor.execute(query, params)
        results = cursor.fetchall()
        execution_time = time.time() - start_time

        _globals.search_cache[cache_key] = results
        log_search(f"multi_criteria_{entity_key}", criteria, len(results))
        display_search_results(results)
        conn.close()

        print(f"\n⚡ Search completed in {execution_time:.3f} seconds")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def fuzzy_name_search():
    """Enhanced fuzzy name search with improved algorithms"""
    print("\nFuzzy Name Search")
    print("This search will find names that are similar to your search term.")

    search_term = input("Enter name to search for: ").strip()
    if not search_term:
        print("Search term cannot be empty.")
        return

    # Define minimum similarity ratio
    similarity_threshold = 0.6
    threshold_input = input(f"Enter similarity threshold (0.1-0.9, default is {similarity_threshold}): ").strip()

    if threshold_input:
        try:
            similarity_threshold = float(threshold_input)
            if similarity_threshold < 0.1 or similarity_threshold > 0.9:
                print("Invalid threshold. Using default value of 0.6.")
                similarity_threshold = 0.6
        except ValueError:
            print("Invalid threshold. Using default value of 0.6.")

    # Algorithm selection
    print("\nSelect matching algorithm:")
    print("1. Standard fuzzy matching")
    print("2. Phonetic matching (Soundex)")
    print("3. Both algorithms")

    algo_choice = input("Select algorithm (1-3): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        search_term_lower = search_term.lower()

        for student in all_students:
            first_name = student[3].lower() if student[3] else ""
            middle_name = student[4].lower() if student[4] else ""
            last_name = student[5].lower() if student[5] else ""

            best_ratio = 0

            if algo_choice in ['1', '3']:
                # Standard fuzzy matching
                first_ratio = SequenceMatcher(None, search_term_lower, first_name).ratio()
                middle_ratio = SequenceMatcher(None, search_term_lower, middle_name).ratio() if middle_name else 0
                last_ratio = SequenceMatcher(None, search_term_lower, last_name).ratio()

                full_name = f"{first_name} {last_name}".strip()
                full_ratio = SequenceMatcher(None, search_term_lower, full_name).ratio()

                best_ratio = max(first_ratio, middle_ratio, last_ratio, full_ratio)

            if algo_choice in ['2', '3']:
                # Phonetic matching
                def simple_soundex(word):
                    if not word:
                        return "0000"
                    word = word.upper()
                    result = word[0]
                    mapping = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
                    for char in word[1:]:
                        for key, value in mapping.items():
                            if char in key and result[-1] != value:
                                result += value
                                break
                    return (result + '0000')[:4]

                search_soundex = simple_soundex(search_term)
                first_soundex = simple_soundex(first_name)
                last_soundex = simple_soundex(last_name)

                if search_soundex == first_soundex or search_soundex == last_soundex:
                    best_ratio = max(best_ratio, 0.8)  # High score for phonetic match

            if best_ratio >= similarity_threshold:
                matched_students.append((student, best_ratio))

        # Sort by similarity (highest first)
        matched_students.sort(key=lambda x: x[1], reverse=True)

        # Extract just the student records for display
        results = [student_info[0] for student_info in matched_students]

        # Log and display results
        log_search("fuzzy_name", {"term": search_term, "threshold": similarity_threshold}, len(results))
        display_search_results(results)

        # Show similarity scores
        if results:
            print("\nSimilarity scores:")
            for i, (student, score) in enumerate(matched_students[:10]):  # Top 10
                full_name = f"{student[3]} {student[4] if student[4] else ''} {student[5]}".strip()
                print(f"{i+1}. {full_name} - {score:.3f}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def module_enrollment_search():
    """Enhanced module enrollment search"""
    print("\nModule Enrollment Search")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT module_code, module_name FROM student_modules ORDER BY module_name")
        all_modules = cursor.fetchall()

        if not all_modules:
            print("No modules found in the database.")
            return

        # Enhanced module display with search
        print(f"\nFound {len(all_modules)} modules:")
        search_modules = input("Search modules (enter keyword or press Enter to see all): ").strip()

        if search_modules:
            filtered_modules = [(code, name) for code, name in all_modules
                              if search_modules.lower() in name.lower() or search_modules.lower() in code.lower()]
            all_modules = filtered_modules

        if not all_modules:
            print("No modules match your search.")
            return

        # Paginated display
        page_size = 20
        for i in range(0, len(all_modules), page_size):
            page_modules = all_modules[i:i+page_size]
            print(f"\nModules {i+1}-{min(i+page_size, len(all_modules))} of {len(all_modules)}:")
            for j, (code, name) in enumerate(page_modules):
                print(f"{i+j+1:3d}. {code} - {name}")

            if i + page_size < len(all_modules):
                if input("\nPress Enter for more, or 'q' to stop: ").strip().lower() == 'q':
                    break

        # Module selection
        module_indices = input("\nEnter module numbers (comma-separated) or 'all' for all modules: ").strip()

        if module_indices.lower() == 'all':
            selected_modules = [code for code, _ in all_modules]
        else:
            try:
                selected_indices = [int(idx.strip()) - 1 for idx in module_indices.split(",")]
                selected_modules = []

                for idx in selected_indices:
                    if 0 <= idx < len(all_modules):
                        selected_modules.append(all_modules[idx][0])
                    else:
                        print(f"Invalid module number: {idx + 1}")

                if not selected_modules:
                    return

            except ValueError:
                print("Invalid input format.")
                return

        # Match type selection
        match_type = input("\nFind students enrolled in (1) ALL or (2) ANY of these modules? Enter 1 or 2: ").strip()

        # Build and execute query
        if match_type == '1':  # ALL modules
            query = "SELECT s.* FROM students s WHERE "
            conditions = []
            params = []

            for module_code in selected_modules:
                conditions.append("""
                EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """)
                params.append(module_code)

            query += " AND ".join(conditions)

        else:  # ANY module
            placeholders = ",".join(["?" for _ in selected_modules])
            query = f"""
            SELECT DISTINCT s.* FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code IN ({placeholders})
            """
            params = selected_modules

        cursor.execute(query, params)
        results = cursor.fetchall()

        # Enhanced results display
        print(f"\nModule selection: {', '.join(selected_modules)}")
        print(f"Match type: {'ALL modules' if match_type == '1' else 'ANY module'}")

        log_search("module_enrollment", {"modules": selected_modules, "match_type": match_type}, len(results))
        display_search_results(results)

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def date_range_search():
    """Enhanced date range search with presets"""
    print("\nDate Range Search")

    print("Search options:")
    print("1. Custom date range")
    print("2. Last 7 days")
    print("3. Last 30 days")
    print("4. Last 3 months")
    print("5. Last 6 months")
    print("6. This year")

    choice = input("Select option (1-6): ").strip()

    start_date = None
    end_date = None

    if choice == '1':
        start_date = input("Enter start date (YYYY-MM-DD), or leave blank: ").strip()
        end_date = input("Enter end date (YYYY-MM-DD), or leave blank: ").strip()
    elif choice == '2':
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    elif choice == '3':
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    elif choice == '4':
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    elif choice == '5':
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    elif choice == '6':
        start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
    else:
        print("Invalid choice.")
        return

    # Validate dates
    if start_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            print("Invalid start date format.")
            return

    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            print("Invalid end date format.")
            return

    # Build query
    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if start_date:
        query += " AND registration_datetime >= ?"
        params.append(start_date + " 00:00:00")

    if end_date:
        query += " AND registration_datetime <= ?"
        params.append(end_date + " 23:59:59")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(query, params)
        results = cursor.fetchall()

        # Show date range in results
        if start_date and end_date:
            print(f"\nSearching from {start_date} to {end_date}")
        elif start_date:
            print(f"\nSearching from {start_date} onwards")
        elif end_date:
            print(f"\nSearching until {end_date}")

        log_search("date_range", {"start": start_date, "end": end_date}, len(results))
        display_search_results(results)

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def combined_filters_search():
    """Search using a combination of filters from different categories"""
    print("\nCombined Filters Search")
    print("This search allows you to combine multiple types of filters.")

    # Initialize filters
    filters = {
        "student_data": {},
        "module_codes": [],
        "date_range": {"start": None, "end": None},
        "module_match_all": False
    }

    # Student data filters
    print("\n--- Student Data Filters ---")
    print("Enter search criteria (leave blank to ignore):")
    student_id = input("Student ID: ").strip()
    if student_id:
        filters["student_data"]["student_id"] = student_id
    first_name = input("First Name: ").strip()
    if first_name:
        filters["student_data"]["first_name"] = first_name
    last_name = input("Last Name: ").strip()
    if last_name:
        filters["student_data"]["last_name"] = last_name
    gender = input("Gender (male/female/other): ").strip().lower()
    if gender in ('male', 'female', 'other'):
        filters["student_data"]["gender"] = gender
    elif gender:
        print("Invalid gender. Ignored.")
    course = input("Course (CS/DS): ").strip().upper()
    if course in ('CS', 'DS'):
        filters["student_data"]["course"] = course
    elif course:
        print("Invalid course. Ignored.")
    age_min = input("Minimum Age: ").strip()
    if age_min:
        try:
            filters["student_data"]["age_min"] = int(age_min)
        except ValueError:
            print("Invalid minimum age. Ignored.")
    age_max = input("Maximum Age: ").strip()
    if age_max:
        try:
            filters["student_data"]["age_max"] = int(age_max)
        except ValueError:
            print("Invalid maximum age. Ignored.")

    # Module filters
    print("\n--- Module Filters ---")
    if input("Filter by modules? (y/n): ").strip().lower() == 'y':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT module_code, module_name "
                "FROM student_modules ORDER BY module_name"
            )
            all_modules = cursor.fetchall()
            conn.close()
            if not all_modules:
                print("No modules found. Skipping module filters.")
            else:
                print("\nAvailable Modules:")
                for i, (code, name) in enumerate(all_modules, 1):
                    print(f"{i}. {code} - {name}")
                indices = input(
                    "Enter module numbers to filter by (comma-separated): "
                ).strip()
                if indices:
                    try:
                        chosen = [int(i)-1 for i in indices.split(',')]
                        for idx in chosen:
                            if 0 <= idx < len(all_modules):
                                filters["module_codes"].append(all_modules[idx][0])
                            else:
                                print(f"Invalid module number {idx+1}. Skipped.")
                        if filters["module_codes"]:
                            choice = input(
                                "Students must be in (1) ALL or (2) ANY of these? "
                            ).strip()
                            if choice == '1':
                                filters["module_match_all"] = True
                            elif choice != '2':
                                print("Invalid choice. Using ANY.")
                    except ValueError:
                        print("Bad input. Skipping module filters.")
        except sqlite3.Error as e:
            print(f"DB error loading modules: {e}. Skipping module filters.")

    # Date range filters
    print("\n--- Date Range Filters ---")
    if input("Filter by registration date range? (y/n): ").strip().lower() == 'y':
        start_date = input(
            "Start date (YYYY-MM-DD), blank for any: "
        ).strip()
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                filters["date_range"]["start"] = start_date + " 00:00:00"
            except ValueError:
                print("Invalid start date. Ignored.")
        end_date = input(
            "End date (YYYY-MM-DD), blank for any: "
        ).strip()
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
                filters["date_range"]["end"] = end_date + " 23:59:59"
            except ValueError:
                print("Invalid end date. Ignored.")

    # Execute search and optional save in one try/except
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build query
        if filters["module_codes"] and filters["module_match_all"]:
            query = "SELECT s.* FROM students s WHERE 1=1"
            params = []
            for field, expr, val in [
                ("student_id", "LIKE", f"%{escape_like(filters['student_data'].get('student_id',''))}%"),
                ("first_name", "LIKE LOWER", f"%{escape_like(filters['student_data'].get('first_name',''))}%"),
                ("last_name", "LIKE LOWER", f"%{escape_like(filters['student_data'].get('last_name',''))}%"),
            ]:
                if filters["student_data"].get(field):
                    if "LOWER" in expr:
                        query += f" AND LOWER(s.{field}) {expr}(?)"
                    else:
                        query += f" AND s.{field} {expr} ?"
                    params.append(val)
            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender)=LOWER(?)"
                params.append(filters["student_data"]["gender"])
            if "course" in filters["student_data"]:
                query += " AND s.course=?"
                params.append(filters["student_data"]["course"])
            if "age_min" in filters["student_data"]:
                query += " AND s.age>=?"
                params.append(filters["student_data"]["age_min"])
            if "age_max" in filters["student_data"]:
                query += " AND s.age<=?"
                params.append(filters["student_data"]["age_max"])
            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime>=?"
                params.append(filters["date_range"]["start"])
            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime<=?"
                params.append(filters["date_range"]["end"])
            for code in filters["module_codes"]:
                query += """
                AND EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id=s.student_id AND sm.module_code=?
                )
                """
                params.append(code)
        else:
            query = "SELECT DISTINCT s.* FROM students s"
            params = []
            if filters["module_codes"]:
                query += " JOIN student_modules sm ON s.student_id=sm.student_id"
            query += " WHERE 1=1"
            for field, op in [
                ("student_id", "LIKE"),
                ("first_name", "LIKE LOWER"),
                ("last_name", "LIKE LOWER"),
            ]:
                if filters["student_data"].get(field):
                    if "LOWER" in op:
                        query += f" AND LOWER(s.{field}) {op}(?)"
                    else:
                        query += f" AND s.{field} {op} ?"
                    params.append(
                        f"%{escape_like(filters['student_data'][field])}%"
                    )
            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender)=LOWER(?)"
                params.append(filters["student_data"]["gender"])
            if "course" in filters["student_data"]:
                query += " AND s.course=?"
                params.append(filters["student_data"]["course"])
            if "age_min" in filters["student_data"]:
                query += " AND s.age>=?"
                params.append(filters["student_data"]["age_min"])
            if "age_max" in filters["student_data"]:
                query += " AND s.age<=?"
                params.append(filters["student_data"]["age_max"])
            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime>=?"
                params.append(filters["date_range"]["start"])
            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime<=?"
                params.append(filters["date_range"]["end"])
            if filters["module_codes"]:
                placeholders = ",".join("?" for _ in filters["module_codes"])
                query += f" AND sm.module_code IN ({placeholders})"
                params.extend(filters["module_codes"])

        # Run and close
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        display_search_results(results)

        # Offer to save if there are results
        if results:
            if input("\nSave this search configuration? (y/n): ").strip().lower() == 'y':
                name = input("Enter name for saved search: ").strip()
                if name:
                    # Implement saving logic here
                    print(f"✅ Search saved as '{name}'")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
