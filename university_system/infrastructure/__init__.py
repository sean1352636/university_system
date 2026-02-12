"""
University System Infrastructure Package

Provides core infrastructure services including:
- Authentication and Authorization
- Database connectivity with connection pooling
- Email services with async queue
- AI/chatbot integration
- Communication services
- Data repositories
- Security features (rate limiting, audit trail, encryption)
- Input validation and sanitization
- Caching with TTL support
- Async utilities for background tasks
"""

# Lazy imports to prevent circular dependencies
# All imports are deferred until first use via __getattr__

_LAZY_AUTH_EXPORTS = {
    'UserAuth', 'require_permission', 'require_role', 'permission_required'
}

_LAZY_DATABASE_EXPORTS = {
    'get_connection', 'transaction', 'DatabaseManager'
}

_LAZY_SECURITY_EXPORTS = {
    'RateLimiter', 'RateLimitExceeded', 'RateLimitConfig', 'rate_limit',
    'login_limiter', 'password_reset_limiter', 'AuditLogger', 'AuditEntry',
    'AuditAction', 'audit_data_access', 'log_activity', 'get_audit_logger',
    'generate_secure_password', 'generate_simple_password', 'generate_temp_password',
    'generate_passphrase', 'check_password_strength', 'AuditLogViewerGUI',
    'AnomalyDetector', 'show_audit_log_viewer'
}

_LAZY_VALIDATION_EXPORTS = {
    'Validators', 'ValidationError', 'ValidationResult', 'validate',
    'validate_email', 'validate_phone', 'validate_student_id', 'validate_date',
    'validate_password_strength', 'is_valid_email', 'is_valid_phone',
    'is_valid_student_id', 'Sanitizers', 'sanitize_input', 'sanitize_html',
    'sanitize_sql_value', 'sanitize_filename', 'escape_html', 'strip_tags',
    'ValidationRule', 'Required', 'MinLength', 'MaxLength', 'Pattern',
    'Email', 'Phone', 'DateFormat', 'InRange', 'OneOf', 'Custom',
    'validate_fields'
}

def __getattr__(name):
    """Lazy load infrastructure components to prevent circular imports."""
    if name in _LAZY_AUTH_EXPORTS:
        from university_system.infrastructure import auth
        return getattr(auth, name)

    if name in _LAZY_DATABASE_EXPORTS:
        from university_system.infrastructure import database
        return getattr(database, name)

    if name in _LAZY_SHARED_CONTEXT_EXPORTS:
        from university_system.infrastructure import shared_context
        return getattr(shared_context, name)

    # Availability flags
    if name == 'SECURITY_AVAILABLE':
        try:
            from university_system.infrastructure import security
            return True
        except ImportError:
            return False

    if name == 'VALIDATION_AVAILABLE':
        try:
            from university_system.infrastructure import validation
            return True
        except ImportError:
            return False

    if name == 'CACHE_AVAILABLE':
        try:
            from university_system.infrastructure import cache
            return True
        except ImportError:
            return False

    if name == 'ASYNC_UTILS_AVAILABLE':
        try:
            from university_system.infrastructure import async_utils
            return True
        except ImportError:
            return False

    if name == 'ML_AVAILABLE':
        try:
            from university_system.infrastructure import ml
            return True
        except ImportError:
            return False

    # Module exports with fallback to None
    if name in _LAZY_SECURITY_EXPORTS:
        try:
            from university_system.infrastructure import security
            return getattr(security, name)
        except ImportError:
            return None

    if name in _LAZY_VALIDATION_EXPORTS:
        try:
            from university_system.infrastructure import validation
            return getattr(validation, name)
        except ImportError:
            return None

    if name in _LAZY_CACHE_EXPORTS:
        try:
            from university_system.infrastructure import cache
            return getattr(cache, name)
        except ImportError:
            return None

    if name in _LAZY_ASYNC_EXPORTS:
        try:
            from university_system.infrastructure import async_utils
            return getattr(async_utils, name)
        except ImportError:
            return None

    if name in _LAZY_ML_EXPORTS:
        try:
            from university_system.infrastructure import ml
            return getattr(ml, name)
        except ImportError:
            return None

    if name == 'WORKFLOWS_AVAILABLE':
        try:
            from university_system.infrastructure import workflows
            return True
        except ImportError:
            return False

    if name in _LAZY_WORKFLOW_EXPORTS:
        try:
            from university_system.infrastructure import workflows
            return getattr(workflows, name)
        except ImportError:
            return None

    if name == 'SEARCH_AVAILABLE':
        try:
            from university_system.infrastructure import search
            return True
        except ImportError:
            return False

    if name in _LAZY_SEARCH_EXPORTS:
        try:
            from university_system.infrastructure import search
            return getattr(search, name)
        except ImportError:
            return None

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    Validators = None
    ValidationError = Exception

# Add more lazy export categories

_LAZY_CACHE_EXPORTS = {
    'CacheManager', 'CacheEntry', 'CacheStats', 'cached', 'get_cache',
    'default_cache', 'student_cache', 'course_cache', 'clear_all_caches'
}

_LAZY_ASYNC_EXPORTS = {
    'BackgroundTaskRunner', 'TaskStatus', 'TaskResult', 'run_in_background',
    'run_with_progress', 'cancel_task', 'get_task_status', 'AsyncDatabaseWrapper',
    'async_query', 'async_execute', 'async_transaction', 'GUIAsyncMixin',
    'TkinterAsyncBridge', 'schedule_gui_update', 'run_async_operation'
}

_LAZY_SHARED_CONTEXT_EXPORTS = {'get_auth', 'set_auth'}

_LAZY_ML_EXPORTS = {
    'CourseRecommender', 'RecommendationEngine', 'EssayGrader', 'GradingRubric',
    'EssayFeedback', 'AdvancedPlagiarismDetector', 'CodePlagiarismDetector',
    'StudentSuccessPredictor', 'CoursePerformancePredictor', 'LearningPathOptimizer',
    'get_course_recommender', 'get_essay_grader', 'get_plagiarism_detector',
    'get_success_predictor', 'get_path_optimizer'
}

_LAZY_WORKFLOW_EXPORTS = {
    'WorkflowEngine', 'Workflow', 'WorkflowStep', 'WorkflowInstance', 'WorkflowStatus',
    'StepType', 'ApprovalStatus', 'ApprovalStep', 'AutomatedStep', 'ConditionalStep',
    'ParallelStep', 'NotificationStep', 'WorkflowTemplates', 'WorkflowMonitor',
    'WorkflowAnalytics', 'get_workflow_engine', 'get_workflow_monitor',
    'get_workflow_analytics', 'create_scholarship_workflow', 'create_leave_request_workflow',
    'create_grade_appeal_workflow', 'create_course_approval_workflow',
    'create_budget_approval_workflow', 'get_workflow_template'
}

_LAZY_SEARCH_EXPORTS = {
    'SearchService', 'AutocompleteService', 'SearchAnalytics', 'SearchIndexer',
    'SearchResult', 'SearchQuery', 'get_search_service', 'get_autocomplete_service',
    'get_search_analytics', 'get_search_indexer'
}

__all__ = [
    # Authentication
    'UserAuth',
    'require_permission',
    'require_role',
    'permission_required',
    # Database
    'get_connection',
    'transaction',
    'DatabaseManager',
    # Security - Rate Limiting
    'RateLimiter',
    'RateLimitExceeded',
    'RateLimitConfig',
    'rate_limit',
    'login_limiter',
    'password_reset_limiter',
    # Security - Audit Trail
    'AuditLogger',
    'AuditEntry',
    'AuditAction',
    'audit_data_access',
    'log_activity',
    'get_audit_logger',
    # Security - Password Generation
    'generate_secure_password',
    'generate_simple_password',
    'generate_temp_password',
    'generate_passphrase',
    'check_password_strength',
    # Security - Audit Log Viewer
    'AuditLogViewerGUI',
    'AnomalyDetector',
    'show_audit_log_viewer',
    # Validation
    'Validators',
    'ValidationError',
    'ValidationResult',
    'validate',
    'validate_email',
    'validate_phone',
    'validate_student_id',
    'validate_date',
    'validate_password_strength',
    'is_valid_email',
    'is_valid_phone',
    'is_valid_student_id',
    # Sanitizers
    'Sanitizers',
    'sanitize_input',
    'sanitize_html',
    'sanitize_sql_value',
    'sanitize_filename',
    'escape_html',
    'strip_tags',
    # Validation Rules
    'ValidationRule',
    'Required',
    'MinLength',
    'MaxLength',
    'Pattern',
    'Email',
    'Phone',
    'DateFormat',
    'InRange',
    'OneOf',
    'Custom',
    'validate_fields',
    # Cache
    'CacheManager',
    'CacheEntry',
    'CacheStats',
    'cached',
    'get_cache',
    'default_cache',
    'student_cache',
    'course_cache',
    'clear_all_caches',
    # Async Utilities
    'BackgroundTaskRunner',
    'TaskStatus',
    'TaskResult',
    'run_in_background',
    'run_with_progress',
    'cancel_task',
    'get_task_status',
    'AsyncDatabaseWrapper',
    'async_query',
    'async_execute',
    'async_transaction',
    'GUIAsyncMixin',
    'TkinterAsyncBridge',
    'schedule_gui_update',
    'run_async_operation',
    # Shared Context
    'get_auth',
    'set_auth',
    # Availability flags
    'SECURITY_AVAILABLE',
    'VALIDATION_AVAILABLE',
    'CACHE_AVAILABLE',
    'ASYNC_UTILS_AVAILABLE',
    'ML_AVAILABLE',
    'WORKFLOWS_AVAILABLE',
    'SEARCH_AVAILABLE',
    # Machine Learning
    'CourseRecommender',
    'RecommendationEngine',
    'EssayGrader',
    'GradingRubric',
    'EssayFeedback',
    'AdvancedPlagiarismDetector',
    'CodePlagiarismDetector',
    'StudentSuccessPredictor',
    'CoursePerformancePredictor',
    'LearningPathOptimizer',
    'get_course_recommender',
    'get_essay_grader',
    'get_plagiarism_detector',
    'get_success_predictor',
    'get_path_optimizer',
    # Workflow Automation
    'WorkflowEngine',
    'Workflow',
    'WorkflowStep',
    'WorkflowInstance',
    'WorkflowStatus',
    'StepType',
    'ApprovalStatus',
    'ApprovalStep',
    'AutomatedStep',
    'ConditionalStep',
    'ParallelStep',
    'NotificationStep',
    'WorkflowTemplates',
    'WorkflowMonitor',
    'WorkflowAnalytics',
    'get_workflow_engine',
    'get_workflow_monitor',
    'get_workflow_analytics',
    'create_scholarship_workflow',
    'create_leave_request_workflow',
    'create_grade_appeal_workflow',
    'create_course_approval_workflow',
    'create_budget_approval_workflow',
    'get_workflow_template',
    # Advanced Search
    'SearchService',
    'AutocompleteService',
    'SearchAnalytics',
    'SearchIndexer',
    'SearchResult',
    'SearchQuery',
    'get_search_service',
    'get_autocomplete_service',
    'get_search_analytics',
    'get_search_indexer',
]

__version__ = '5.0.0'
