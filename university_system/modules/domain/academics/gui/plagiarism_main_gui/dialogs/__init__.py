from .submission import DocumentSubmissionDialog
from .check import PlagiarismCheckDialog
from .comparison import DocumentComparisonDialog
from .results import CheckResultDialog, ResultDetailsDialog
from .statistics import StatisticsDialog
from .search import RepositorySearchDialog
from .advanced_search import AdvancedRepositorySearchDialog
from .document_details import DocumentDetailsDialog
from .bulk_operations import BulkOperationsDialog
from .workflow import DocumentWorkflowDialog
from .converter import FileFormatConverterDialog
from .backup_restore import BackupRestoreDialog
from .system_testing import SystemTestingDialog
from .setup_testing import SetupTestingDialog

__all__ = [
    'DocumentSubmissionDialog',
    'PlagiarismCheckDialog',
    'DocumentComparisonDialog',
    'CheckResultDialog',
    'ResultDetailsDialog',
    'StatisticsDialog',
    'RepositorySearchDialog',
    'AdvancedRepositorySearchDialog',
    'DocumentDetailsDialog',
    'BulkOperationsDialog',
    'DocumentWorkflowDialog',
    'FileFormatConverterDialog',
    'BackupRestoreDialog',
    'SystemTestingDialog',
    'SetupTestingDialog',
]
