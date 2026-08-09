"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_fuzzy_search(self, search_term, threshold, algorithm):
    """Perform fuzzy search with given parameters"""
    try:
        from difflib import SequenceMatcher

        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        all_rows = cursor.fetchall()
        conn.close()

        matched_students = []
        search_term_lower = search_term.lower()

        for row in all_rows:
            # Use named column access to avoid schema index mismatch
            first_name = (row["first_name"] or "").lower()
            last_name = (row["last_name"] or "").lower()

            best_ratio = 0

            if algorithm in ['1', '3']:  # Standard fuzzy matching
                first_ratio = SequenceMatcher(None, search_term_lower, first_name).ratio()
                last_ratio = SequenceMatcher(None, search_term_lower, last_name).ratio()
                full_name = f"{first_name} {last_name}".strip()
                full_ratio = SequenceMatcher(None, search_term_lower, full_name).ratio()
                best_ratio = max(first_ratio, last_ratio, full_ratio)

            if algorithm in ['2', '3']:  # Phonetic matching
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
                    best_ratio = max(best_ratio, 0.8)

            if best_ratio >= threshold:
                matched_students.append(tuple(row))

        return matched_students

    except Exception as e:
        raise Exception(f"Fuzzy search error: {str(e)}")
