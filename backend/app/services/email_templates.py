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


def weekly_digest(user, role_title: str, d: dict, unsubscribe_url: str):
    """
    Weekly "what changed in your role" digest.

    `d` keys (all optional — sections render only when data exists):
      growth_pct        int    postings growth vs previous month
      ai_pct            float  share of postings asking for AI skills
      ai_delta          float  pct-point change in AI share over ~3 months
      rising_skills     list   [{name, growth_pct, demand}]
      surging_company   dict   {name, growth_pct}
      total_jobs        int
      gap_skill         str    user's highest-demand missing skill (if known)
    """
    name = user.full_name or 'there'
    subject_bits = []
    if d.get('growth_pct') is not None:
        subject_bits.append(f"postings {'+' if d['growth_pct'] >= 0 else ''}{d['growth_pct']}%")
    if d.get('rising_skills'):
        subject_bits.append(f"{d['rising_skills'][0]['name']} rising")
    subject = f"{role_title} this week: " + ', '.join(subject_bits) if subject_bits \
        else f"What changed in {role_title} this week"

    lines_txt = [f"Hi {name},", "", f"Your weekly {role_title} market check:"]
    rows_html = []

    if d.get('growth_pct') is not None:
        arrow = '↑' if d['growth_pct'] > 0 else ('↓' if d['growth_pct'] < 0 else '→')
        lines_txt.append(f"- Postings {arrow} {d['growth_pct']:+d}% vs last month")
        rows_html.append(
            f"<p style='margin:8px 0;'><strong>Postings {arrow} {d['growth_pct']:+d}%</strong> vs last month"
            + (f" across {d['total_jobs']:,} active openings" if d.get('total_jobs') else '') + ".</p>"
        )

    if d.get('ai_pct') is not None:
        delta_txt = ''
        if d.get('ai_delta') is not None and abs(d['ai_delta']) >= 1:
            delta_txt = f" ({'+' if d['ai_delta'] > 0 else ''}{d['ai_delta']:.0f} pts over 3 months)"
        lines_txt.append(f"- {d['ai_pct']:.0f}% of postings now ask for AI skills{delta_txt}")
        rows_html.append(
            f"<p style='margin:8px 0;'><strong>{d['ai_pct']:.0f}%</strong> of postings now ask for AI skills{delta_txt}.</p>"
        )

    if d.get('rising_skills'):
        names = ', '.join(
            f"{s['name']} ({'+' if s['growth_pct'] > 0 else ''}{s['growth_pct']:.0f}%)"
            for s in d['rising_skills'][:3]
        )
        lines_txt.append(f"- Rising skills: {names}")
        rows_html.append(f"<p style='margin:8px 0;'><strong>Rising:</strong> {names}</p>")

    if d.get('surging_company'):
        c = d['surging_company']
        lines_txt.append(f"- {c['name']} ramped up hiring ({'+' if c['growth_pct'] > 0 else ''}{c['growth_pct']:.0f}%)")
        rows_html.append(
            f"<p style='margin:8px 0;'><strong>{c['name']}</strong> ramped up hiring "
            f"({'+' if c['growth_pct'] > 0 else ''}{c['growth_pct']:.0f}%).</p>"
        )

    if d.get('gap_skill'):
        lines_txt.append(f"- Your top gap is still {d['gap_skill']} — highest-demand skill you haven't added")
        rows_html.append(
            f"<p style='margin:8px 0;'><strong>Your top gap:</strong> {d['gap_skill']} — "
            f"the highest-demand skill not on your profile.</p>"
        )

    dash_url = f"{_web_url()}/dashboard"
    lines_txt += ["", f"Full picture: {dash_url}", "", f"Unsubscribe: {unsubscribe_url}"]

    html = _layout(
        f"<h2 style='margin:0 0 4px;'>{role_title}</h2>"
        f"<p style='margin:0 0 16px;font-size:13px;color:#888;'>Your weekly market check</p>"
        + ''.join(rows_html)
        + f"<p style='margin:24px 0 0;'><a href='{dash_url}' style='display:inline-block;padding:12px 20px;"
          f"background:#fff;color:#000;text-decoration:none;font-weight:500;'>See the full picture</a></p>"
        + f"<p style='font-size:12px;color:#666;margin-top:24px;'>"
          f"<a href='{unsubscribe_url}' style='color:#888;'>Unsubscribe from this digest</a></p>"
    )
    return subject, html, '\n'.join(lines_txt)
