# Package exports & backward compatibility
# This file exports all classes and functions that were originally in student_union_gui.py

# Core GUI class
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.main_gui import (
    StudentUnionGUI,
)

# Core utilities
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.utilities import (
    DatabaseQueryDialog,
    SearchDialog,
    CLIGUIBridge,
    get_gui_instance,
    launch_gui,
    launch_cli,
    run_gui_with_cli_fallback,
    main_menu,
)

# Misc functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.misc import (
    main,
    launch_student_union_gui,
)

# Club dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.club_dialogs import (
    ClubJoinDialog,
    ClubCreateDialog,
    ClubManageDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.club_discussions import (
    ClubDiscussionsDialog,
    ClubMediaDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.club_finance import (
    ClubFinancialReportsDialog,
    ClubBudgetDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.club_members import (
    ClubMemberDirectoryDialog,
)

# Event dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_dialogs import (
    EventRegistrationDialog,
    EventManagementDialog,
    EventAttendanceDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_finance import (
    EventFinancesDialog,
    EventFinancialTrackingDialog,
    AddIncomeDialog,
    AddExpenseDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_recurring import (
    RecurringEventDialog,
    RecurringEventsDialog,
    CreateRecurringSeriesDialog,
    EditRecurringSeriesDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_ticketing import (
    EventTicketingDialog,
    CreateTicketTypeDialog,
    ProcessRefundDialog,
    ManageWaitlistDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_virtual import (
    VirtualEventsDialog,
    CreateVirtualEventDialog,
    SetupHybridEventDialog,
    VirtualAttendanceDialog,
    VirtualTechSupportDialog,
)

# Facility dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.facilities.facility_booking import (
    FacilityBookingDialog,
    FacilityApprovalDialog,
    ApproveFacilityBookingsDialog,
)

# Finance dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.finance.expenses import (
    ExpenseSubmitDialog,
    ExpenseApprovalDialog,
)

# Competition dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.competitions.competition_views import (
    CompetitionsDialog,
    CompetitionHistoryDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.competitions.competition_registration import (
    CompetitionRegistrationDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.competitions.competition_results import (
    CompetitionResultsDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.competitions.competition_admin import (
    CreateCompetitionDialog,
    UpdateCompetitionScoresDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.competitions.interclub_competitions import (
    InterClubCompetitionsDialog,
    ActiveCompetitionsDialog,
    RegisterClubCompetitionDialog,
)

# Support dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.support.support_groups import (
    SupportGroupsDialog,
    CreateSupportGroupDialog,
    MySupportGroupsDialog,
    BrowseSupportGroupsDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.support.wellness import (
    WellnessResourcesDialog,
    CrisisResourcesDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.support.peer_support import (
    PeerSupportWellnessDialog,
    AnonymousPeerMatchingDialog,
    ManagePeerSupportDialog,
)

# Equipment dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_browse import (
    EquipmentBrowseDialog,
    BrowseAvailableEquipmentDialog,
    ViewEquipmentDetailsDialog,
    SearchEquipmentDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_checkout import (
    EquipmentCheckoutDialog,
    MyEquipmentDialog,
    CheckOutEquipmentDialog,
    ReturnEquipmentDialog,
    ViewMyEquipmentCheckoutsDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_admin import (
    ManageEquipmentSystemDialog,
    AddNewEquipmentDialog,
    UpdateEquipmentStatusDialog,
    EquipmentMaintenanceTrackingDialog,
    GenerateEquipmentReportsDialog,
)

# Gamification dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.gamification.rewards import (
    GamificationDialog,
    LeaderboardDialog,
    AvailableBadgesDialog,
    CreateBadgeDialog,
    EditBadgeDialog,
    RewardSystemAdminDialog,
)

# Mentorship dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.mentorship.mentorship import (
    MentorshipBrowseDialog,
    MyMentorshipsDialog,
    MentorshipSessionsDialog,
    ScheduleMentorshipSessionDialog,
    RateMentorshipDialog,
)

# Book club dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.book_clubs.book_clubs import (
    BookClubDialog,
    BookSelectionDialog,
    ScheduleUpdateDialog,
    BookReviewDialog,
)

# Election dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_core import (
    ElectionsDialog,
    CandidatesDialog,
    VotingDialog,
    NominationDialog,
    ElectionResultsDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_setup import (
    CampaignMaterialsDialog,
    SetupElectionDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_campaigns import (
    TrackCampaignExpensesDialog,
    ViewCandidateProfilesDialog,
    CampaignExpenseSubmissionDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_accessibility import (
    ElectionAccessibilityFeaturesDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_compliance import (
    MonitorCampaignComplianceDialog,
    ElectionSecurityAuditDialog,
    VoteIntegrityCheckDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_voting_methods import (
    ManageEnhancedVotingDialog,
    RankedChoiceVotingDialog,
    ConfigureVotingMethodsDialog,
)

# Green initiatives dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.green.green_initiatives import (
    GreenInitiativesDialog,
    CarbonTrackingDialog,
    WasteReductionDialog,
    GreenTransportDialog,
    EnvironmentalReportsDialog,
)

# Volunteer dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.volunteer.volunteer import (
    VolunteerOpportunitiesDialog,
    MyVolunteerActivitiesDialog,
    CommunityServiceHoursDialog,
    CommunityEngagementDialog,
)

# Analytics dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.analytics.analytics import (
    AdvancedAnalyticsDialog,
    EngagementTrendAnalysisDialog,
    MemberRetentionInsightsDialog,
    LearningAnalyticsDashboardDialog,
)

# Live streaming dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.streaming.live_streaming import (
    LiveStreamingDialog,
    ManageLiveStreamingDialog,
    InteractiveVirtualFeaturesDialog,
    RecordingManagementDialog,
)

# Knowledge sharing dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.knowledge.knowledge_sharing import (
    KnowledgeSharingDialog,
    ProposeSessionDialog,
)

# Academic dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.academic.academic_support import (
    AcademicSupportDialog,
    MyAcademicActivityDialog,
    LearningIntegrationDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.academic.study_groups import (
    StudyGroupsDialog,
    CreateStudyGroupDialog,
    ExamPrepGroupsDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.academic.tutoring import (
    PeerTutoringDialog,
    AcademicWorkshopsDialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.academic.resources import (
    SharedResourcesDialog,
    ResourcePreviewDialog,
)

# Conference dialogs
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.conferences.conferences import (
    AcademicConferencesDialog,
    AcademicConferencesOrganizerDialog,
    ResearchPresentationDialog,
)

# Export all for convenience
__all__ = [
    # Core
    'StudentUnionGUI',
    'main',
    'launch_student_union_gui',
    'DatabaseQueryDialog',
    'SearchDialog',
    'CLIGUIBridge',
    'get_gui_instance',
    'launch_gui',
    'launch_cli',
    'run_gui_with_cli_fallback',
    'main_menu',
    # Club dialogs
    'ClubJoinDialog',
    'ClubCreateDialog',
    'ClubManageDialog',
    'ClubDiscussionsDialog',
    'ClubMediaDialog',
    'ClubFinancialReportsDialog',
    'ClubBudgetDialog',
    'ClubMemberDirectoryDialog',
    # Event dialogs
    'EventRegistrationDialog',
    'EventManagementDialog',
    'EventAttendanceDialog',
    'EventFinancesDialog',
    'EventFinancialTrackingDialog',
    'AddIncomeDialog',
    'AddExpenseDialog',
    'RecurringEventDialog',
    'RecurringEventsDialog',
    'CreateRecurringSeriesDialog',
    'EditRecurringSeriesDialog',
    'EventTicketingDialog',
    'CreateTicketTypeDialog',
    'ProcessRefundDialog',
    'ManageWaitlistDialog',
    'VirtualEventsDialog',
    'CreateVirtualEventDialog',
    'SetupHybridEventDialog',
    'VirtualAttendanceDialog',
    'VirtualTechSupportDialog',
    # Facility dialogs
    'FacilityBookingDialog',
    'FacilityApprovalDialog',
    'ApproveFacilityBookingsDialog',
    # Finance dialogs
    'ExpenseSubmitDialog',
    'ExpenseApprovalDialog',
    # Competition dialogs
    'CompetitionsDialog',
    'CompetitionHistoryDialog',
    'CompetitionRegistrationDialog',
    'CompetitionResultsDialog',
    'CreateCompetitionDialog',
    'UpdateCompetitionScoresDialog',
    'InterClubCompetitionsDialog',
    'ActiveCompetitionsDialog',
    'RegisterClubCompetitionDialog',
    # Support dialogs
    'SupportGroupsDialog',
    'CreateSupportGroupDialog',
    'MySupportGroupsDialog',
    'BrowseSupportGroupsDialog',
    'WellnessResourcesDialog',
    'CrisisResourcesDialog',
    'PeerSupportWellnessDialog',
    'AnonymousPeerMatchingDialog',
    'ManagePeerSupportDialog',
    # Equipment dialogs
    'EquipmentBrowseDialog',
    'BrowseAvailableEquipmentDialog',
    'ViewEquipmentDetailsDialog',
    'SearchEquipmentDialog',
    'EquipmentCheckoutDialog',
    'MyEquipmentDialog',
    'CheckOutEquipmentDialog',
    'ReturnEquipmentDialog',
    'ViewMyEquipmentCheckoutsDialog',
    'ManageEquipmentSystemDialog',
    'AddNewEquipmentDialog',
    'UpdateEquipmentStatusDialog',
    'EquipmentMaintenanceTrackingDialog',
    'GenerateEquipmentReportsDialog',
    # Gamification dialogs
    'GamificationDialog',
    'LeaderboardDialog',
    'AvailableBadgesDialog',
    'CreateBadgeDialog',
    'EditBadgeDialog',
    'RewardSystemAdminDialog',
    # Mentorship dialogs
    'MentorshipBrowseDialog',
    'MyMentorshipsDialog',
    'MentorshipSessionsDialog',
    'ScheduleMentorshipSessionDialog',
    'RateMentorshipDialog',
    # Book club dialogs
    'BookClubDialog',
    'BookSelectionDialog',
    'ScheduleUpdateDialog',
    'BookReviewDialog',
    # Election dialogs
    'ElectionsDialog',
    'CandidatesDialog',
    'VotingDialog',
    'NominationDialog',
    'ElectionResultsDialog',
    'CampaignMaterialsDialog',
    'SetupElectionDialog',
    'TrackCampaignExpensesDialog',
    'ViewCandidateProfilesDialog',
    'CampaignExpenseSubmissionDialog',
    'ElectionAccessibilityFeaturesDialog',
    'MonitorCampaignComplianceDialog',
    'ElectionSecurityAuditDialog',
    'VoteIntegrityCheckDialog',
    'ManageEnhancedVotingDialog',
    'RankedChoiceVotingDialog',
    'ConfigureVotingMethodsDialog',
    # Green initiatives dialogs
    'GreenInitiativesDialog',
    'CarbonTrackingDialog',
    'WasteReductionDialog',
    'GreenTransportDialog',
    'EnvironmentalReportsDialog',
    # Volunteer dialogs
    'VolunteerOpportunitiesDialog',
    'MyVolunteerActivitiesDialog',
    'CommunityServiceHoursDialog',
    'CommunityEngagementDialog',
    # Analytics dialogs
    'AdvancedAnalyticsDialog',
    'EngagementTrendAnalysisDialog',
    'MemberRetentionInsightsDialog',
    'LearningAnalyticsDashboardDialog',
    # Live streaming dialogs
    'LiveStreamingDialog',
    'ManageLiveStreamingDialog',
    'InteractiveVirtualFeaturesDialog',
    'RecordingManagementDialog',
    # Knowledge sharing dialogs
    'KnowledgeSharingDialog',
    'ProposeSessionDialog',
    # Academic dialogs
    'AcademicSupportDialog',
    'MyAcademicActivityDialog',
    'LearningIntegrationDialog',
    'StudyGroupsDialog',
    'CreateStudyGroupDialog',
    'ExamPrepGroupsDialog',
    'PeerTutoringDialog',
    'AcademicWorkshopsDialog',
    'SharedResourcesDialog',
    'ResourcePreviewDialog',
    # Conference dialogs
    'AcademicConferencesDialog',
    'AcademicConferencesOrganizerDialog',
    'ResearchPresentationDialog',
]
