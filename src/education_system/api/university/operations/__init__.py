"""Operations HTTP routes: campus, commerce, events, housing, platform.

``DOMAIN_BLUEPRINTS`` is what the university mount collects; see
``platform/delivery/api/registry.py``. One blueprint per route module.
"""

from education_system.systems.university.plugins.campus_commerce.api.barber_routes import barber_bp
from education_system.systems.university.plugins.campus_commerce.api.betting_routes import betting_bp
from education_system.systems.university.plugins.campus_commerce.api.butcher_routes import butcher_bp
from education_system.api.university.operations.campus_navigation_routes import campus_navigation_bp
from education_system.api.university.operations.campus_routes import campus_bp
from education_system.systems.university.plugins.campus_commerce.api.carrental_routes import carrental_bp
from education_system.systems.university.plugins.campus_commerce.api.cinema_routes import cinema_bp
from education_system.systems.university.plugins.campus_commerce.api.commerce_routes import commerce_bp
from education_system.systems.university.plugins.campus_commerce.api.dining_routes import dining_bp
from education_system.api.university.operations.equipment_routes import equipment_bp
from education_system.api.university.operations.event_routes import event_bp
from education_system.api.university.operations.events_discovery_routes import events_discovery_bp
from education_system.api.university.operations.facilities_mgmt_routes import facilities_mgmt_bp
from education_system.api.university.operations.facility_routes import facility_bp
from education_system.api.university.operations.feedback_system_routes import feedback_system_bp
from education_system.systems.university.plugins.campus_commerce.api.gym_routes import gym_bp
from education_system.api.university.operations.housing_routes import housing_bp
from education_system.api.university.operations.institutional_analytics_routes import institutional_analytics_bp
from education_system.api.university.operations.lost_found_routes import lost_found_bp
from education_system.api.university.operations.mail_routes import mail_bp
from education_system.api.university.operations.email_routes import email_bp
from education_system.systems.university.plugins.campus_commerce.api.marketplace_routes import marketplace_bp
from education_system.api.university.operations.mobility_routes import mobility_bp
from education_system.systems.university.plugins.campus_commerce.api.musicshop_routes import musicshop_bp
from education_system.systems.university.plugins.campus_commerce.api.nailbar_routes import nailbar_bp
from education_system.api.university.operations.operations_routes import operations_bp
from education_system.api.university.operations.parking_routes import parking_bp
from education_system.systems.university.plugins.campus_commerce.api.phoneshop_routes import phoneshop_bp
from education_system.systems.university.plugins.campus_commerce.api.printing_routes import printing_bp
from education_system.api.university.operations.roommate_finder_routes import roommate_finder_bp
from education_system.api.university.operations.security_routes import security_bp
from education_system.api.university.operations.study_rooms_routes import study_rooms_bp
from education_system.systems.university.plugins.campus_commerce.api.textbooks_routes import textbooks_bp

from education_system.api.university.operations.announcement_routes import announcement_bp
from education_system.api.university.operations.chat_routes import chat_bp
from education_system.api.university.operations.dashboard_routes import dashboard_bp
from education_system.api.university.operations.notification_routes import notification_bp
from education_system.api.university.operations.user_routes import user_bp

DOMAIN_BLUEPRINTS = [
    announcement_bp,
    chat_bp,
    dashboard_bp,
    notification_bp,
    user_bp,
    barber_bp,
    betting_bp,
    butcher_bp,
    campus_navigation_bp,
    campus_bp,
    carrental_bp,
    cinema_bp,
    commerce_bp,
    dining_bp,
    equipment_bp,
    event_bp,
    events_discovery_bp,
    facilities_mgmt_bp,
    facility_bp,
    feedback_system_bp,
    gym_bp,
    housing_bp,
    institutional_analytics_bp,
    lost_found_bp,
    mail_bp,
    email_bp,
    marketplace_bp,
    mobility_bp,
    musicshop_bp,
    nailbar_bp,
    operations_bp,
    parking_bp,
    phoneshop_bp,
    printing_bp,
    roommate_finder_bp,
    security_bp,
    study_rooms_bp,
    textbooks_bp,
]

__all__ = ["DOMAIN_BLUEPRINTS", "announcement_bp", "chat_bp", "dashboard_bp", "notification_bp", "user_bp", "barber_bp", "betting_bp", "butcher_bp", "campus_navigation_bp", "campus_bp", "carrental_bp", "cinema_bp", "commerce_bp", "dining_bp", "equipment_bp", "event_bp", "events_discovery_bp", "facilities_mgmt_bp", "facility_bp", "feedback_system_bp", "gym_bp", "housing_bp", "institutional_analytics_bp", "lost_found_bp", "mail_bp", "email_bp", "marketplace_bp", "mobility_bp", "musicshop_bp", "nailbar_bp", "operations_bp", "parking_bp", "phoneshop_bp", "printing_bp", "roommate_finder_bp", "security_bp", "study_rooms_bp", "textbooks_bp"]
