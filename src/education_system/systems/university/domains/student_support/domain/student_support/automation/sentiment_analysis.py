"""
Sentiment analysis and AI suggestions.
"""

import datetime
import logging


from education_system.systems.university.domains.student_support.domain.student_support.config import (
    TicketSentiment
)

logger = logging.getLogger(__name__)

def _analyze_sentiment(text):
    """Simple sentiment analysis based on keywords"""
    frustrated_keywords = [
        'frustrated', 'angry', 'terrible', 'awful', 'horrible', 'hate',
        'worst', 'furious', 'disgusted', 'outraged', 'urgent', 'immediately',
        'ridiculous', 'unacceptable', 'disappointed'
    ]

    positive_keywords = [
        'thank', 'appreciate', 'great', 'excellent', 'wonderful', 'amazing',
        'perfect', 'love', 'fantastic', 'awesome', 'pleased'
    ]

    text_lower = text.lower()

    frustrated_count = sum(1 for keyword in frustrated_keywords if keyword in text_lower)
    positive_count = sum(1 for keyword in positive_keywords if keyword in text_lower)

    if frustrated_count > 2:
        return TicketSentiment.FRUSTRATED.value
    elif frustrated_count > 0:
        return TicketSentiment.NEGATIVE.value
    elif positive_count > 0:
        return TicketSentiment.POSITIVE.value
    else:
        return TicketSentiment.NEUTRAL.value

def _suggest_category(text):
    """The UK support category the text most likely belongs to (plain
    keyword counts), or None."""
    category_keywords = {
        'IT': ['password', 'login', 'computer', 'wifi', 'wi-fi', 'internet', 'email', 'software',
               'laptop', 'printer', 'moodle', 'account', 'website', 'app'],
        'Academic Registry': ['grade', 'module', 'assignment', 'exam', 'transcript', 'graduation',
                              'credit', 'enrolment', 'enrollment', 'register', 'registration',
                              'resit', 'extension', 'mitigating', 'certificate', 'timetable'],
        'Fees & Funding': ['fee', 'fees', 'tuition', 'payment', 'loan', 'student finance',
                           'bursary', 'scholarship', 'hardship', 'funding', 'invoice', 'refund'],
        'Accommodation': ['halls', 'accommodation', 'flat', 'room', 'landlord', 'tenancy',
                          'rent', 'housing', 'maintenance', 'flatmate'],
        'Wellbeing': ['counselling', 'counseling', 'stress', 'anxiety', 'depression',
                      'wellbeing', 'lonely', 'mental health', 'struggling', 'overwhelmed'],
        'Disability & Reasonable Adjustments': ['disability', 'disabled', 'dyslexia', 'adhd',
                                                'autism', 'reasonable adjustment', 'dsa',
                                                'accessibility', 'support plan'],
        'International/Visa': ['visa', 'cas', 'brp', 'evisa', 'immigration', 'ukvi',
                               'international', 'passport', 'right to study'],
        'Careers': ['job', 'career', 'internship', 'placement', 'cv', 'interview', 'graduate scheme',
                    'employability'],
    }

    text_lower = f" {text.lower()} "
    category_scores = {}

    for category, keywords in category_keywords.items():
        score = sum(1 for keyword in keywords if f" {keyword}" in text_lower)
        if score > 0:
            category_scores[category] = score

    if category_scores:
        return max(category_scores, key=category_scores.get)

    return None

def _get_auto_assignment(category, priority, staff_assignments=None, *, team=None):
    """The member of the ticket's team to give it to: the least-loaded
    active member under their capacity, round robin on ties
    (``routing.pick_assignee``). ``staff_assignments`` is accepted for
    older callers and ignored. None when nobody is free."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    try:
        return routing.pick_assignee(team or routing.route(category))
    except Exception:
        logger.warning("Auto-assignment failed for category %s", category, exc_info=True)
        return None

def _estimate_resolution_time(category, priority, *, team=None):
    """When a new ticket is due to be resolved: the team / priority SLA on
    the business-hours clock (``sla``)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
        sla,
        store,
    )
    try:
        with store.reading() as conn:
            t = sla.targets(conn, team or routing.route(category), priority)
            due = sla.Clock(conn).add(datetime.datetime.now(), t['resolution_hours'],
                                      t['business_hours_only'])
        return due.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        logger.warning("Could not work out the resolution time", exc_info=True)
        resolution_time = datetime.datetime.now() + datetime.timedelta(hours=24)
        return resolution_time.strftime('%Y-%m-%d %H:%M:%S')
