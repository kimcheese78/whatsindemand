"""Thin email wrapper. Resend if RESEND_API_KEY is set, else log-only no-op for dev."""

import logging
import os

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """
    Send an email. Returns True on success, False on failure.
    No-op (logs and returns True) if no provider is configured — keeps dev unblocked.
    """
    api_key = os.environ.get('RESEND_API_KEY')
    sender = os.environ.get('EMAIL_FROM', 'noreply@whatsindemand.com')

    if not api_key:
        logger.warning(
            'RESEND_API_KEY not set — email to %s skipped. Subject: %s\n%s',
            to, subject, text
        )
        return True

    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            'from': sender,
            'to': [to],
            'subject': subject,
            'html': html,
            'text': text,
        })
        return True
    except Exception as e:
        logger.exception('Email send failed to %s: %s', to, e)
        return False
