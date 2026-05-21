#!/usr/bin/env python3
"""
Targeted job_skills backfill for newly promoted skills.

Run after promoting new skills on review day to tag historical jobs
without re-extracting all 132k jobs. Uses the same requirements-section
filtering as SkillExtractor so results are consistent.

Usage:
    python scripts/backfill_skills.py --skill-ids 4710 4711 4712
    python scripts/backfill_skills.py --min-id 4710   # all skills with id >= 4710
"""
import sys
import os
import re
import argparse

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

from app import create_app
from app.models import db, Skill, JobSkill
from app.services.skill_extractor import extract_requirements_text

app = create_app()


def _build_patterns(skill: Skill) -> list:
    terms = [skill.name] + (skill.aliases or [])
    patterns = []
    for term in terms:
        if term and len(term.strip()) >= 2:
            patterns.append(re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE))
    return patterns


def backfill_skill(skill: Skill) -> int:
    patterns = _build_patterns(skill)
    if not patterns:
        return 0

    # Load all jobs that don't already have this skill tagged
    rows = db.session.execute(db.text("""
        SELECT j.id, j.description_text
        FROM jobs j
        WHERE j.description_text IS NOT NULL
          AND j.description_text != ''
          AND NOT EXISTS (
              SELECT 1 FROM job_skills js
              WHERE js.job_id = j.id AND js.skill_id = :skill_id
          )
    """), {'skill_id': skill.id}).fetchall()

    inserted = 0
    for job_id, description_text in rows:
        # Use same section filtering as SkillExtractor
        search_text, _ = extract_requirements_text(description_text)
        if any(p.search(search_text) for p in patterns):
            db.session.execute(db.text("""
                INSERT INTO job_skills (job_id, skill_id, is_required, created_at)
                VALUES (:job_id, :skill_id, TRUE, NOW())
                ON CONFLICT DO NOTHING
            """), {'job_id': job_id, 'skill_id': skill.id})
            inserted += 1

    return inserted


def run(skill_ids: list) -> None:
    with app.app_context():
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        if not skills:
            print("No skills found for given IDs.")
            return

        print(f"Backfilling {len(skills)} skill(s) against all historical jobs...")
        total = 0
        for skill in skills:
            count = backfill_skill(skill)
            db.session.commit()
            print(f"  {skill.name:<50} +{count:,} job_skills")
            total += count

        print(f"\nDone. Inserted {total:,} job_skills rows total.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-ids', nargs='+', type=int, default=[],
        help='Specific skill IDs to backfill')
    parser.add_argument('--min-id', type=int, default=None,
        help='Backfill all skills with id >= this value (e.g. first newly promoted ID)')
    args = parser.parse_args()

    ids = list(args.skill_ids)
    if args.min_id:
        with app.app_context():
            ids += [s.id for s in Skill.query.filter(Skill.id >= args.min_id).all()]

    if not ids:
        print("Provide --skill-ids or --min-id. Exiting.")
        sys.exit(1)

    run(list(set(ids)))
