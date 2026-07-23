"""
Student Job Board Module

On-campus employment management system with job postings, work-study tracking,
skill-based matching, and performance management.
"""

from education_system.post_18.university_system.modules.domain.student_affairs.student_jobs.services.job_service import (
    JobPostingManager,
    JobApplicationManager,
    EmploymentManager,
    WorkHoursManager,
    SkillMatchingManager,
    PerformanceManager
)

from education_system.post_18.university_system.modules.domain.student_affairs.student_jobs.cli.jobs_cli import (
    StudentJobsCLI
)

from education_system.post_18.university_system.modules.domain.student_affairs.student_jobs.gui.jobs_gui import (
    StudentJobsGUI
)

__all__ = [
    # Service layer
    'JobPostingManager',
    'JobApplicationManager',
    'EmploymentManager',
    'WorkHoursManager',
    'SkillMatchingManager',
    'PerformanceManager',
    # Interface layer
    'StudentJobsCLI',
    'StudentJobsGUI'
]
