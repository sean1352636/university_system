"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_phonetic_search(self, search_term):
    """Perform phonetic name search using Soundex algorithm"""
    try:
        def soundex(word):
            """Generate Soundex code for phonetic matching"""
            if not word:
                return "0000"

            word = word.upper()
            soundex_code = word[0]

            # Mapping for consonants
            mapping = {
                'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
                'L': '4', 'MN': '5', 'R': '6'
            }

            for char in word[1:]:
                for key, value in mapping.items():
                    if char in key:
                        if soundex_code[-1] != value:
                            soundex_code += value
                        break

            # Pad or truncate to 4 characters
            soundex_code = (soundex_code + '0000')[:4]
            return soundex_code

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        search_soundex = soundex(search_term)
        matched_students = []

        for student in all_students:
            first_name = student[3] if len(student) > 3 else ""
            last_name = student[5] if len(student) > 5 else ""

            if (soundex(first_name) == search_soundex or
                soundex(last_name) == search_soundex):
                matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Phonetic search error: {str(e)}")
