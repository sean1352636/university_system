"""Filesystem layout constants for the assignments submission directory.

Each assignment workspace (``self.submission_dir``) has a standardised
subdirectory structure. Using named constants here keeps the layout
definition in one place so call sites don't duplicate string literals.
"""

SUBDIR_PENDING = "pending"
SUBDIR_SUBMITTED = "submitted"
SUBDIR_GRADED = "graded"
SUBDIR_FEEDBACK = "feedback"
SUBDIR_TEMPLATES = "templates"
SUBDIR_EXPORTS = "exports"
SUBDIR_BACKUPS = "backups"
SUBDIR_PREVIEWS = "previews"

SUBMISSION_SUBDIRS = (
    SUBDIR_PENDING,
    SUBDIR_SUBMITTED,
    SUBDIR_GRADED,
    SUBDIR_FEEDBACK,
    SUBDIR_TEMPLATES,
    SUBDIR_EXPORTS,
    SUBDIR_BACKUPS,
    SUBDIR_PREVIEWS,
)
