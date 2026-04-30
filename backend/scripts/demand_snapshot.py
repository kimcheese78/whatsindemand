"""Labor market demand snapshot: top roles, rising roles, skills, seniority, remote."""
from app import create_app
from app.models import db

app = create_app()

QUERIES = [
    ('Overall volume', """
        SELECT COUNT(*) total_jobs,
               COUNT(*) FILTER (WHERE is_active) active_jobs,
               COUNT(DISTINCT company_id) companies,
               COUNT(DISTINCT role_id) roles
        FROM jobs
    """),
    ('Top 20 roles by active jobs', """
        SELECT r.normalized_title, r.category, r.total_active_jobs
        FROM roles r
        WHERE r.total_active_jobs > 0
        ORDER BY r.total_active_jobs DESC
        LIMIT 20
    """),
    ('Category breakdown (active)', """
        SELECT r.category, SUM(r.total_active_jobs) active_jobs,
               COUNT(*) FILTER (WHERE r.total_active_jobs > 0) distinct_roles
        FROM roles r
        WHERE r.category IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
    """),
    ('Seniority mix (active)', """
        SELECT COALESCE(j.seniority_level, '(unspecified)') seniority,
               COUNT(*) jobs,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) pct
        FROM jobs j WHERE is_active
        GROUP BY 1 ORDER BY 2 DESC
    """),
    ('Remote share (active)', """
        SELECT location_is_remote, COUNT(*) jobs,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) pct
        FROM jobs WHERE is_active GROUP BY 1
    """),
    ('Top 15 locations (active, non-remote)', """
        SELECT location_city || COALESCE(', ' || location_state, '') city, COUNT(*) n
        FROM jobs WHERE is_active AND NOT location_is_remote AND location_city IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 15
    """),
    ('Top hiring companies', """
        SELECT c.name, COUNT(*) active_jobs
        FROM jobs j JOIN companies c ON c.id = j.company_id
        WHERE j.is_active GROUP BY 1 ORDER BY 2 DESC LIMIT 15
    """),
    ('Top 20 skills by active job count', """
        SELECT s.name, COUNT(DISTINCT j.id) jobs
        FROM skills s
        JOIN job_skills js ON js.skill_id = s.id
        JOIN jobs j ON j.id = js.job_id
        WHERE j.is_active
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20
    """),
    # Rising roles: compare role's share of last-14-day postings vs prior-60-day share.
    # Requires >= 15 postings in the recent window to avoid noise.
    ('Rising roles (share last 14d vs prior 60d)', """
        WITH recent AS (
          SELECT role_id, COUNT(*) n FROM jobs
          WHERE posted_at >= NOW() - INTERVAL '14 days'
          GROUP BY 1
        ),
        baseline AS (
          SELECT role_id, COUNT(*) n FROM jobs
          WHERE posted_at >= NOW() - INTERVAL '74 days'
            AND posted_at <  NOW() - INTERVAL '14 days'
          GROUP BY 1
        ),
        totals AS (
          SELECT (SELECT SUM(n) FROM recent) recent_total,
                 (SELECT SUM(n) FROM baseline) base_total
        )
        SELECT r.normalized_title,
               rec.n recent_n,
               COALESCE(b.n, 0) base_n,
               ROUND(100.0 * rec.n / t.recent_total, 2) recent_pct,
               ROUND(100.0 * COALESCE(b.n, 0) / NULLIF(t.base_total,0), 2) base_pct,
               ROUND((100.0 * rec.n / t.recent_total) /
                     NULLIF(100.0 * COALESCE(b.n, 1) / NULLIF(t.base_total,0), 0), 2) ratio
        FROM recent rec
        JOIN roles r ON r.id = rec.role_id
        LEFT JOIN baseline b ON b.role_id = rec.role_id
        CROSS JOIN totals t
        WHERE rec.n >= 15
        ORDER BY ratio DESC NULLS LAST
        LIMIT 20
    """),
    ('Fading roles (same windows, inverted)', """
        WITH recent AS (
          SELECT role_id, COUNT(*) n FROM jobs
          WHERE posted_at >= NOW() - INTERVAL '14 days' GROUP BY 1
        ),
        baseline AS (
          SELECT role_id, COUNT(*) n FROM jobs
          WHERE posted_at >= NOW() - INTERVAL '74 days'
            AND posted_at <  NOW() - INTERVAL '14 days' GROUP BY 1
        ),
        totals AS (
          SELECT (SELECT SUM(n) FROM recent) recent_total,
                 (SELECT SUM(n) FROM baseline) base_total
        )
        SELECT r.normalized_title,
               COALESCE(rec.n, 0) recent_n,
               b.n base_n,
               ROUND(100.0 * COALESCE(rec.n,0) / t.recent_total, 2) recent_pct,
               ROUND(100.0 * b.n / t.base_total, 2) base_pct
        FROM baseline b
        JOIN roles r ON r.id = b.role_id
        LEFT JOIN recent rec ON rec.role_id = b.role_id
        CROSS JOIN totals t
        WHERE b.n >= 30
        ORDER BY (100.0 * COALESCE(rec.n,0) / t.recent_total)
               / NULLIF(100.0 * b.n / t.base_total, 0) ASC NULLS FIRST
        LIMIT 15
    """),
    ('Rising skills (share last 14d vs prior 60d, min 30 recent)', """
        WITH recent AS (
          SELECT js.skill_id, COUNT(DISTINCT j.id) n
          FROM jobs j JOIN job_skills js ON js.job_id = j.id
          WHERE j.posted_at >= NOW() - INTERVAL '14 days'
          GROUP BY 1
        ),
        baseline AS (
          SELECT js.skill_id, COUNT(DISTINCT j.id) n
          FROM jobs j JOIN job_skills js ON js.job_id = j.id
          WHERE j.posted_at >= NOW() - INTERVAL '74 days'
            AND j.posted_at <  NOW() - INTERVAL '14 days'
          GROUP BY 1
        ),
        totals AS (
          SELECT (SELECT SUM(n) FROM recent) rt,
                 (SELECT SUM(n) FROM baseline) bt
        )
        SELECT s.name, rec.n recent_n, COALESCE(b.n,0) base_n,
               ROUND((100.0 * rec.n / t.rt) /
                     NULLIF(100.0 * COALESCE(b.n,1) / t.bt, 0), 2) ratio
        FROM recent rec
        JOIN skills s ON s.id = rec.skill_id
        LEFT JOIN baseline b ON b.skill_id = rec.skill_id
        CROSS JOIN totals t
        WHERE rec.n >= 30
        ORDER BY ratio DESC NULLS LAST
        LIMIT 20
    """),
]


def fmt(v):
    if v is None: return '-'
    if isinstance(v, float): return f'{v:.2f}'
    return str(v)


def main():
    with app.app_context():
        for title, sql in QUERIES:
            print(f'\n=== {title} ===')
            rows = db.session.execute(db.text(sql)).all()
            if not rows:
                print('(no rows)')
                continue
            cols = rows[0]._mapping.keys()
            widths = [max(len(c), max((len(fmt(r._mapping[c])) for r in rows), default=0)) for c in cols]
            print('  '.join(c.ljust(w) for c, w in zip(cols, widths)))
            print('  '.join('-' * w for w in widths))
            for r in rows:
                print('  '.join(fmt(r._mapping[c]).ljust(w) for c, w in zip(cols, widths)))


if __name__ == '__main__':
    main()
