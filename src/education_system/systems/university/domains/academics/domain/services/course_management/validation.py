import re


def validate_course_code(code):
    """
    Validate the format of a course code.

    Course codes must follow the pattern of 2-4 uppercase letters followed
    by 2-3 digits (e.g., 'CS101', 'MATH201', 'BIO99').

    Parameters
    ----------
    code : str
        The course code to validate.

    Returns
    -------
    bool
        True if the code matches the required format, False otherwise.

    Examples
    --------
    >>> validate_course_code('CS101')
    True
    >>> validate_course_code('MATH201')
    True
    >>> validate_course_code('invalid')
    False
    >>> validate_course_code('CS1')  # Too few digits
    False
    """
    pattern = r'^[A-Z]{2,4}\d{2,3}$'
    return bool(re.match(pattern, code))


def validate_email(email):
    """
    Validate the format of an email address.

    Checks if the email follows standard email format with local part,
    @ symbol, domain, and top-level domain.

    Parameters
    ----------
    email : str
        The email address to validate.

    Returns
    -------
    bool
        True if the email format is valid, False otherwise.

    Examples
    --------
    >>> validate_email('user@example.com')
    True
    >>> validate_email('john.doe+tag@university.edu')
    True
    >>> validate_email('invalid-email')
    False

    Notes
    -----
    This performs format validation only. It does not verify that the
    email address actually exists or can receive mail.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_time_format(time_str):
    """
    Validate a time string in 24-hour HH:MM format.

    Parameters
    ----------
    time_str : str
        The time string to validate (e.g., '09:30', '14:00', '23:59').

    Returns
    -------
    bool
        True if the time format is valid, False otherwise.

    Examples
    --------
    >>> validate_time_format('09:30')
    True
    >>> validate_time_format('14:00')
    True
    >>> validate_time_format('25:00')  # Invalid hour
    False
    >>> validate_time_format('12:60')  # Invalid minute
    False
    """
    pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(pattern, time_str))


def validate_days_of_week(days_str):
    """
    Validate a comma-separated string of days of the week.

    Each day must be a full day name (Monday, Tuesday, etc.) with
    proper capitalization.

    Parameters
    ----------
    days_str : str
        Comma-separated string of day names (e.g., 'Monday, Wednesday, Friday').

    Returns
    -------
    bool
        True if all days are valid day names, False otherwise.

    Examples
    --------
    >>> validate_days_of_week('Monday, Wednesday, Friday')
    True
    >>> validate_days_of_week('Saturday')
    True
    >>> validate_days_of_week('Mon, Wed')  # Abbreviations not allowed
    False
    >>> validate_days_of_week('Monday, Funday')  # Invalid day
    False
    """
    valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
    days = [day.strip() for day in days_str.split(',')]
    return all(day in valid_days for day in days)


def check_circular_prerequisite(cursor, course_id, prereq_id):
    """
    Check if adding a prerequisite would create a circular dependency.

    Performs a depth-first search through the prerequisite chain to detect
    if adding the proposed prerequisite would create a cycle. This prevents
    invalid prerequisite structures like: A requires B, B requires C, C requires A.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Active database cursor for executing queries.
    course_id : int
        The ID of the course that would have the prerequisite added.
    prereq_id : int
        The ID of the proposed prerequisite course.

    Returns
    -------
    bool
        True if adding this prerequisite would create a circular dependency,
        False if it is safe to add.

    Examples
    --------
    >>> # Check if CS201 can have CS101 as a prerequisite
    >>> with get_connection() as conn:
    ...     cursor = conn.cursor()
    ...     is_circular = check_circular_prerequisite(cursor, 201, 101)
    ...     if is_circular:
    ...         print("Cannot add: would create circular dependency")

    Notes
    -----
    The algorithm checks if prereq_id (the proposed prerequisite) has
    course_id anywhere in its own prerequisite chain. If so, adding
    course_id as requiring prereq_id would create a cycle.

    The function uses memoization (visited set) to avoid infinite loops
    when checking complex prerequisite graphs.
    """
    # Check if prereq_id has course_id as a prerequisite (direct or indirect)
    visited = set()

    def has_prerequisite(cid, target_id):
        if cid in visited:
            return False
        visited.add(cid)

        cursor.execute("SELECT prerequisite_course_id FROM course_prerequisites WHERE course_id = ?", (cid,))
        prereqs = cursor.fetchall()

        for (pid,) in prereqs:
            if pid == target_id:
                return True
            if has_prerequisite(pid, target_id):
                return True
        return False

    return has_prerequisite(prereq_id, course_id)
