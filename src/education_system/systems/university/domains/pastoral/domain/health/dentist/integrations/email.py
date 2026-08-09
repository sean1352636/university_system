from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.dentist import _send_dentist_email

def send_dental_email(recipient, subject, body):
    return _send_dentist_email(recipient, subject, body)
