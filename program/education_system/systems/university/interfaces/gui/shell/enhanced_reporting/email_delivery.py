"""Shared delivery support for generated and scheduled reports."""

from pathlib import Path


def send_report_email(recipients, report_path, template_name):
    """Send one generated report to each recipient and return delivery results."""
    from education_system.systems.university.infrastructure.email.email_service import send_email

    path = Path(report_path)
    if not path.is_file():
        raise FileNotFoundError(f"Generated report does not exist: {path}")
    if isinstance(recipients, str):
        addresses = [part.strip() for part in recipients.replace(";", ",").split(",")]
    else:
        addresses = [str(part).strip() for part in (recipients or [])]
    addresses = [address for address in addresses if address]
    if not addresses:
        raise ValueError("At least one report recipient is required")

    subject = f"Scheduled Report: {template_name}"
    body = "Please find the requested scheduled report attached."
    return {
        address: bool(send_email(
            recipient_email=address,
            subject=subject,
            body=body,
            attachments=[str(path)],
        ))
        for address in addresses
    }
