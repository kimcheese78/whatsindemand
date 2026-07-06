#!/usr/bin/env python3
"""
Weekly LinkedIn content generator.

Pulls current numbers from prod, renders branded chart cards (PNG, 1200x1500
portrait — LinkedIn's best-performing image shape), and drafts post copy with
the live numbers filled in. Output lands in backend/content_out/<date>/;
review, tweak the opening line, post.

Run with system python3 (matplotlib lives there, not in the venv):
    DATABASE_URL='<prod-dsn>' python3 scripts/generate_social_content.py

Every published number obeys product thresholds: roles only appear in the
Index with >=500 active postings; all counts are distinct active postings.
"""
import os
import sys
from datetime import datetime

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from app import create_app
from app.models import db

app = create_app()

# ---- Brand (mirrors the product's dark theme) ----
BG = '#0a0a0a'
PANEL = '#141414'
INK = '#f0f0f0'
MUTED = '#9a9a9a'
FAINT = '#666666'
UP = '#4ade80'
LINE = '#2a2a2a'

W, H = 12, 15  # inches at dpi=100 -> 1200x1500

MONTH = datetime.utcnow().strftime('%B %Y')
OUT_DIR = os.path.join(backend_dir, 'content_out', datetime.utcnow().strftime('%Y-%m-%d'))


def _card(fig):
    fig.patch.set_facecolor(BG)


def _footer(fig, total_postings):
    fig.text(0.06, 0.045, 'WHATSINDEMAND', color=INK, fontsize=15,
             fontweight='bold', ha='left')
    fig.text(0.06, 0.025, f'{total_postings:,} live postings · 3,300+ companies · {MONTH}',
             color=FAINT, fontsize=11, ha='left')
    fig.text(0.94, 0.035, 'whatsindemand.com', color=MUTED, fontsize=12, ha='right')


def q(sql, **kw):
    return db.session.execute(db.text(sql), kw).fetchall()


def card_skill_bars(total_postings):
    """AI skills vs the established stack — horizontal bars, snapshot."""
    rows = q("""
        SELECT s.name, count(DISTINCT js.job_id) c
        FROM skills s JOIN job_skills js ON js.skill_id = s.id
        JOIN jobs j ON j.id = js.job_id AND j.is_active = true
        WHERE s.name IN ('LLMs','Java','Docker','React','Claude','AI agents','GPT','Angular')
        GROUP BY s.name ORDER BY c DESC
    """)
    ai_skills = {'LLMs', 'Claude', 'AI agents', 'GPT'}
    names = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    colors = [UP if n in ai_skills else '#555555' for n in names]

    fig, ax = plt.subplots(figsize=(W, H), dpi=100)
    _card(fig)
    ax.set_facecolor(BG)
    fig.subplots_adjust(left=0.22, right=0.92, top=0.74, bottom=0.12)

    ypos = range(len(names) - 1, -1, -1)
    ax.barh(list(ypos), counts, color=colors, height=0.62)
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names, color=INK, fontsize=17)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=12)
    ax.get_xaxis().set_visible(False)
    for y, c in zip(ypos, counts):
        ax.text(c + max(counts) * 0.012, y, f'{c:,}', va='center',
                color=INK, fontsize=15, fontweight='bold')

    fig.text(0.06, 0.92, 'LLMs now appear in more live', color=INK,
             fontsize=30, fontweight='bold')
    fig.text(0.06, 0.885, 'job postings than Java.', color=INK,
             fontsize=30, fontweight='bold')
    fig.text(0.06, 0.845, 'Skills named in live postings across 3,300+ companies',
             color=MUTED, fontsize=15)
    fig.text(0.06, 0.79, '■ AI-era skills', color=UP, fontsize=13)
    fig.text(0.22, 0.79, '■ Established stack', color='#888888', fontsize=13)
    _footer(fig, total_postings)
    path = os.path.join(OUT_DIR, 'card1_llms_vs_java.png')
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path, {r[0]: r[1] for r in rows}


def card_ai_index(total_postings):
    """AI Exposure Index — league table of roles by AI-skill share."""
    rows = q("""
        SELECT r.normalized_title,
               count(DISTINCT j.id) AS total,
               count(DISTINCT ai.job_id) AS ai_jobs
        FROM roles r
        JOIN jobs j ON j.role_id = r.id AND j.is_active = true
        LEFT JOIN (
            SELECT DISTINCT js.job_id
            FROM job_skills js JOIN skills s ON s.id = js.skill_id
            WHERE s.subcategory = 'AI & Machine Learning' AND s.is_verified = true
        ) ai ON ai.job_id = j.id
        WHERE r.total_active_jobs >= 500
        GROUP BY r.id
        HAVING count(DISTINCT j.id) >= 500
        ORDER BY count(DISTINCT ai.job_id)::float / count(DISTINCT j.id) DESC
        LIMIT 12
    """)
    data = [(t, round(a / n * 100) if n else 0, n) for t, n, a in rows]

    fig = plt.figure(figsize=(W, H), dpi=100)
    _card(fig)
    fig.text(0.06, 0.93, 'AI Exposure Index', color=INK, fontsize=34, fontweight='bold')
    fig.text(0.06, 0.895, f'Share of live postings requiring AI skills, by role — {MONTH}',
             color=MUTED, fontsize=15)

    y = 0.83
    for i, (title, pct, n) in enumerate(data, 1):
        fig.text(0.06, y, f'{i:>2}', color=FAINT, fontsize=17)
        fig.text(0.11, y, title, color=INK, fontsize=18,
                 fontweight='bold' if i <= 3 else 'normal')
        fig.text(0.76, y, f'{pct}%', color=UP if pct >= 40 else INK,
                 fontsize=18, fontweight='bold', ha='right')
        # bar
        bar_w = 0.14 * (pct / 100)
        fig.patches.append(plt.Rectangle((0.78, y - 0.004), 0.14, 0.014,
                                         transform=fig.transFigure, color=LINE))
        fig.patches.append(plt.Rectangle((0.78, y - 0.004), bar_w, 0.014,
                                         transform=fig.transFigure,
                                         color=UP if pct >= 40 else '#777777'))
        y -= 0.056
    fig.text(0.06, y - 0.01, 'Only roles with 500+ live postings shown.',
             color=FAINT, fontsize=11)
    _footer(fig, total_postings)
    path = os.path.join(OUT_DIR, 'card2_ai_exposure_index.png')
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path, data


def card_single_stat(total_postings, role_title, pct, delta):
    """One huge number."""
    fig = plt.figure(figsize=(W, H), dpi=100)
    _card(fig)
    fig.text(0.5, 0.60, f'{pct}%', color=UP, fontsize=170,
             fontweight='bold', ha='center')
    fig.text(0.5, 0.47, f'of {role_title} postings', color=INK,
             fontsize=30, ha='center')
    fig.text(0.5, 0.435, 'now ask for AI skills', color=INK,
             fontsize=30, ha='center')
    if delta is not None:
        fig.text(0.5, 0.37, f'up {delta:+.0f} pts in the last 3 months',
                 color=MUTED, fontsize=18, ha='center')
    _footer(fig, total_postings)
    path = os.path.join(OUT_DIR, f'card3_{role_title.lower().replace(" ", "_")}_stat.png')
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


def write_post_copy(skill_counts, index_data, stat_role, stat_pct, stat_delta, total_postings=0):
    posts = f"""# LinkedIn post drafts — {MONTH}
Review numbers, personalize the first line, post the image WITHOUT a link in
the body (put the link in the first comment — links in the body cut reach).

---
## Post A (intro — text only, no image, post this FIRST)

I've spent the last few months building a tracker that watches {total_postings:,} live job postings at 3,300+ companies — the Greenhouse/Lever/Ashby crowd that adopts new tech first.

I built it because I kept reading takes about AI changing careers, and almost none of them came with data.

Some things the data says that surprised me:

→ "LLMs" now appears in more live postings than Java ({skill_counts.get('LLMs', 0):,} vs {skill_counts.get('Java', 0):,})
→ {stat_pct}% of {stat_role} postings now require AI skills
→ Claude alone is named in {skill_counts.get('Claude', 0):,} postings — two-thirds of React

I'll be posting what changes every week. No hype, just what employers are actually asking for.

---
## Post B (crossover card — attach card1_llms_vs_java.png)

Java: {skill_counts.get('Java', 0):,} live job postings.
LLMs: {skill_counts.get('LLMs', 0):,}.

The crossover already happened, and almost nobody noticed.

This is from live postings at 3,300+ companies, not a survey. Employers moved faster than the discourse did.

(What's in your role's postings? Link in comments.)

---
## Post C (AI Exposure Index — attach card2_ai_exposure_index.png)

Which roles are being rewritten by AI the fastest?

I measured the share of live postings that now list AI skills as requirements, role by role:

{chr(10).join(f'{i}. {t} — {p}%' for i, (t, p, n) in enumerate(index_data[:5], 1))}

The pattern: it's not engineers first. It's every role that touches product, content, or customers.

I'll publish this index monthly. Follow along if you want to see where your role lands.

---
## Post D (single stat — attach card3 image)

{stat_pct}% of {stat_role} job postings now ask for AI skills.

Three months ago it was {stat_pct - (stat_delta or 0):.0f}%.

At this rate, "comfortable with AI tools" stops being a differentiator and becomes the default within a year — the same way "proficient in Excel" did.

The window where this skill set makes you stand out is now.

---
## Cadence
- Week 1: Mon = Post A (intro), Thu = Post B (crossover)
- Week 2: Tue = Post C (index), Thu = Post D (stat)
- Always: reply to every comment in the first 2 hours; link only in first comment
  (https://whatsindemand.com?utm_source=linkedin&utm_medium=organic)
"""
    path = os.path.join(OUT_DIR, 'post_drafts.md')
    with open(path, 'w') as f:
        f.write(posts)
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with app.app_context():
        total = q("SELECT count(*) FROM jobs WHERE is_active = true")[0][0]

        p1, skill_counts = card_skill_bars(total)
        print('✓', p1)

        p2, index_data = card_ai_index(total)
        print('✓', p2)

        # Single-stat: use the top consumer-recognizable role from the index
        stat_role, stat_pct = None, None
        for t, p, n in index_data:
            if t in ('Product Manager', 'Software Engineer', 'Data Analyst', 'Marketing Manager'):
                stat_role, stat_pct = t, p
                break
        if not stat_role:
            stat_role, stat_pct = index_data[0][0], index_data[0][1]

        # Real 3-month delta from the same cohort-locked pipeline the product
        # uses — never publish a number the dashboard wouldn't show.
        client = app.test_client()
        resp = client.post('/api/roles/insights', json={'role': stat_role})
        ai = (resp.get_json() or {}).get('ai_exposure') or {}
        stat_delta = ai.get('delta_pct_points')

        p3 = card_single_stat(total, stat_role, stat_pct, stat_delta)
        print('✓', p3)

        p4 = write_post_copy(skill_counts, index_data, stat_role, stat_pct, stat_delta, total)
        print('✓', p4)

        print(f"\nDone → {OUT_DIR}")


if __name__ == '__main__':
    main()
