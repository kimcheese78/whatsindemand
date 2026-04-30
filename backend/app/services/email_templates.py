"""Email templates. Plain Python f-strings; upgrade to Jinja later if needed."""

import os


def _web_url() -> str:
    return os.environ.get('WEB_URL', 'http://localhost:3000').rstrip('/')


def _layout(body_html: str) -> str:
    return f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;background:#0a0a0a;color:#f0f0f0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#141414;padding:32px;border:1px solid #2a2a2a;">
    {body_html}
    <hr style="border:none;border-top:1px solid #2a2a2a;margin:32px 0;" />
    <p style="font-size:12px;color:#888;">WhatsInDemand — if you didn't request this, you can safely ignore this email.</p>
  </div>
</body></html>"""


def password_reset(user, token: str):
    link = f"{_web_url()}/reset-password?token={token}"
    name = user.full_name or 'there'
    subject = 'Reset your WhatsInDemand password'
    text = (
        f"Hi {name},\n\n"
        f"Click the link below to reset your password. This link expires in 1 hour.\n\n"
        f"{link}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n"
    )
    html = _layout(
        f"<h2 style='margin:0 0 16px;'>Reset your password</h2>"
        f"<p>Hi {name},</p>"
        f"<p>Click the button below to reset your password. This link expires in 1 hour.</p>"
        f"<p><a href='{link}' style='display:inline-block;padding:12px 20px;background:#fff;color:#000;text-decoration:none;font-weight:500;'>Reset password</a></p>"
        f"<p style='font-size:13px;color:#aaa;'>Or paste this URL: {link}</p>"
    )
    return subject, html, text


def email_verify(user, token: str):
    link = f"{_web_url()}/verify-email?token={token}"
    name = user.full_name or 'there'
    subject = 'Verify your email'
    text = (
        f"Hi {name},\n\n"
        f"Confirm your email by clicking the link below. This link expires in 24 hours.\n\n"
        f"{link}\n"
    )
    html = _layout(
        f"<h2 style='margin:0 0 16px;'>Verify your email</h2>"
        f"<p>Hi {name},</p>"
        f"<p>Confirm your email by clicking the button below. This link expires in 24 hours.</p>"
        f"<p><a href='{link}' style='display:inline-block;padding:12px 20px;background:#fff;color:#000;text-decoration:none;font-weight:500;'>Verify email</a></p>"
        f"<p style='font-size:13px;color:#aaa;'>Or paste this URL: {link}</p>"
    )
    return subject, html, text


def email_change(user, token: str, new_email: str):
    link = f"{_web_url()}/verify-email?token={token}"
    name = user.full_name or 'there'
    subject = 'Confirm your new email'
    text = (
        f"Hi {name},\n\n"
        f"Confirm your new email address ({new_email}) by clicking the link below.\n"
        f"This link expires in 24 hours.\n\n"
        f"{link}\n"
    )
    html = _layout(
        f"<h2 style='margin:0 0 16px;'>Confirm your new email</h2>"
        f"<p>Hi {name},</p>"
        f"<p>Confirm <strong>{new_email}</strong> as your new email by clicking below. This link expires in 24 hours.</p>"
        f"<p><a href='{link}' style='display:inline-block;padding:12px 20px;background:#fff;color:#000;text-decoration:none;font-weight:500;'>Confirm new email</a></p>"
        f"<p style='font-size:13px;color:#aaa;'>Or paste this URL: {link}</p>"
    )
    return subject, html, text
