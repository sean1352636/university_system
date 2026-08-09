from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import send_confirmation_email

class EmailNotificationGateway:
    def send(self, recipient: str, subject: str, body: str) -> bool:
        return bool(send_confirmation_email(recipient, subject, body))
