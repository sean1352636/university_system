"""
Operations modules for bulk actions, export, and merging.
"""

from education_system.systems.university.domain.pastoral.services.student_support.operations.bulk_operations import (
    bulk_assign_tickets_menu,
    bulk_operations_menu,
    bulk_update_category_menu,
    bulk_update_priority_menu,
    bulk_update_status_menu,
    bulk_update_tickets,
    export_filtered_results,
    perform_bulk_assign,
)
from education_system.systems.university.domain.pastoral.services.student_support.operations.export import (
    export_data,
    export_data_menu,
    export_filtered_tickets_menu,
    export_metrics_menu,
    export_responses_menu,
    export_tickets_menu,
)
from education_system.systems.university.domain.pastoral.services.student_support.operations.merge import (
    merge_tickets,
    merge_tickets_menu,
)

__all__ = [
    # Bulk Operations
    'bulk_update_tickets',
    'perform_bulk_assign',
    'bulk_operations_menu',
    'bulk_assign_tickets_menu',
    'bulk_update_status_menu',
    'bulk_update_priority_menu',
    'bulk_update_category_menu',
    'export_filtered_results',

    # Export
    'export_data',
    'export_data_menu',
    'export_tickets_menu',
    'export_responses_menu',
    'export_metrics_menu',
    'export_filtered_tickets_menu',

    # Merge
    'merge_tickets',
    'merge_tickets_menu',
]
