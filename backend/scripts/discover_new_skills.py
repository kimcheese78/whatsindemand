"""Incremental skill discovery — runs after each scrape.

Scans only jobs scraped since the last discovery run and writes candidates
to a JSON file for review. Approved candidates are added to the skills
taxonomy manually. Promotion to job_skills happens via extract_skills.py.

Full-corpus mode (first run or --full flag): processes all jobs.

Run standalone:
    PYTHONPATH=. venv/bin/python scripts/discover_new_skills.py
    PYTHONPATH=. venv/bin/python scripts/discover_new_skills.py --full
    PYTHONPATH=. venv/bin/python scripts/discover_new_skills.py --output /tmp/candidates.json
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
AUTO_PROMOTE_MIN_JOBS      = 3
AUTO_PROMOTE_MIN_COMPANIES = 3
LOG_EVERY = 500

# For full-corpus fallback when no prior run exists, look back this far.
INITIAL_LOOKBACK_DAYS = 90

# ---------------------------------------------------------------------------
# Extraction patterns (unchanged from original)
# ---------------------------------------------------------------------------
_CONTEXT_PATTERNS = []

def _cp(tag: str, pattern: str):
    _CONTEXT_PATTERNS.append((tag, re.compile(pattern, re.IGNORECASE)))

_cp('ctx_exp',   r'\bexperience\s+(?:with|in|using)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_prof',  r'\bproficien(?:t|cy)\s+(?:in|with)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_know',  r'\bknowledge\s+of\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_fam',   r'\bfamili(?:ar(?:ity)?)\s+with\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_exp2',  r'\bexpertise\s+in\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_hands', r'\bhands[- ]on\s+experience\s+with\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_built', r'\b(?:written|built|implemented|developed)\s+(?:in|with|using)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,40}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_tools', r'\btools?\s+(?:like|such as|including)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_tech',  r'\btechnolog(?:y|ies)\s+(?:like|such as|including)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_fw',    r'\b(?:frameworks?|libraries|platforms?|languages?)\s+(?:like|such as|including)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_wk',    r'\bworking\s+knowledge\s+of\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_und',   r'\bunderstanding\s+of\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_expo',  r'\bexposure\s+to\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,50}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')
_cp('ctx_list',  r'\b(?:using|with)\s+[A-Z]\w{1,30}(?:\.\w+)?\s*,\s*([A-Z]\w{1,30}(?:\.\w+)?(?:\s*,\s*[A-Z]\w{1,30}(?:\.\w+)?){0,5})')
_cp('ctx_cert',  r'\b(?:certified\s+in|certification\s+in)\s+((?:[A-Za-z0-9][A-Za-z0-9+#.\-/ ]{1,60}?)(?=\s*[,;()\n]|$|\band\b|\bor\b))')

_BULLET_RE = re.compile(r'^\s*[-•*·▪▸►✓✔○●]\s*(.+)')
_VERB_STARTERS = re.compile(
    r'^(?:manage|develop|design|build|create|implement|maintain|ensure|provide|'
    r'support|help|work|lead|drive|own|coordinate|define|establish|partner|'
    r'collaborate|communicate|deliver|execute|identify|monitor|improve|leverage|'
    r'utilize|analyze|report|research|track|evaluate|review)\b',
    re.IGNORECASE,
)
_INLINE_LIST_SPLIT = re.compile(r'[,;]\s+')


def _extract_bullet_items(text: str):
    for line in text.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            content = m.group(1).strip().rstrip('.')
            if _VERB_STARTERS.match(content):
                continue
            words = content.split()
            if 2 <= len(words) <= 8:
                if words[0][0].isupper() or words[0].upper() == words[0]:
                    yield content
            elif len(words) == 1 and len(content) >= 2:
                if content[0].isupper():
                    yield content


_LEADING_JUNK = re.compile(
    r'^(?:a|an|the|our|your|their|its|strong|good|excellent|solid|deep|broad|'
    r'extensive|proven|demonstrated|exceptional|advanced|basic|general|'
    r'relevant|applicable|appropriate|significant|substantial|considerable)\s+',
    re.IGNORECASE,
)
_TRAILING_JUNK = re.compile(
    r'\s*(?:skills?|experience|knowledge|background|expertise|tools?|ability|'
    r'capabilities?|proficiency|understanding|principles?|concepts?|practices?|'
    r'methodologies?|frameworks?)\s*$',
    re.IGNORECASE,
)
_PAREN_STRIP = re.compile(r'\s*\(.*?\)\s*$')

_DISCOVERY_NOISE = {
    'pregnancy', 'childbirth', 'disability', 'accommodation', 'breastfeeding',
    'marital status', 'national origin', 'sexual orientation', 'gender identity',
    'veteran status', 'religion', 'race', 'ethnicity', 'age', 'color',
    'etc', 'other', 'similar', 'relevant tools', 'various', 'any',
    'best practices', 'methodologies', 'various tools', 'qualifications',
    'requirements', 'preferred qualifications', 'additional skills',
    'catered meals', 'free lunch', 'dental', 'vision', 'wellness',
    'paid time off', 'equity', 'vacation', 'benefits',
    'hiring', 'staffing', 'recruiting', 'onboarding',
    'using one', 'layout', 'specificity', 'readiness', 'please',
    'including', 'such', 'especially', 'best', 'secure', 'web',
    'frontend', 'backend', 'full stack', 'full-stack',
    'mobile', 'cloud', 'data', 'software', 'systems',
    'platform', 'service', 'services', 'application', 'applications',
    'integration', 'infrastructure', 'architecture', 'development',
    'engineering', 'design', 'product', 'operations',
    'especially', 'particularly', 'specifically', 'primarily',
    'additional', 'relevant', 'applicable', 'related',
}

_EEO_RE = re.compile(
    r'\b(?:equal\s+opportunity|affirmative\s+action|eeo|protected\s+class|'
    r'unlawful\s+discriminat|applicable\s+law|criminal\s+histor|'
    r'applicants?\s+with\s+disabilities)\b',
    re.IGNORECASE,
)


def _clean_candidate(raw: str) -> str | None:
    c = raw.strip()
    c = _PAREN_STRIP.sub('', c).strip()
    while True:
        cleaned = _LEADING_JUNK.sub('', c).strip()
        if cleaned == c:
            break
        c = cleaned
    stripped = _TRAILING_JUNK.sub('', c).strip()
    if stripped and len(stripped) >= 2:
        c = stripped
    c = c.strip().rstrip('.')
    if len(c) < 2 or len(c) > 50:
        return None
    if not re.search(r'[A-Za-z]', c):
        return None
    if re.fullmatch(r'[a-z]{1,3}', c):
        return None
    if re.fullmatch(r'\d{1,2}\+?\s*years?', c, re.IGNORECASE):
        return None
    if len(c.split()) > 6:
        return None
    if c.lower() in _DISCOVERY_NOISE:
        return None
    _SENTENCE_RE = re.compile(
        r'\b(?:is|are|was|were|have|has|had|will|would|can|could|should|must|'
        r'need to|able to|required to|expected to)\b',
        re.IGNORECASE,
    )
    if _SENTENCE_RE.search(c):
        return None
    _PURE_ADJECTIVE_RE = re.compile(
        r'^(?:fast[- ]paced|large[- ]scale|high[- ]growth|early[- ]stage|'
        r'cross[- ]functional|regulated|modern|legacy|agile|complex|'
        r'distributed|scalable|global|local|remote|hybrid)\b',
        re.IGNORECASE,
    )
    if _PURE_ADJECTIVE_RE.match(c):
        return None
    _FRAGMENT_RE = re.compile(
        r'^(?:focus(?:ing)?\s+on|building\s+|working\s+(?:with|in|on)|'
        r'managing\s+|leading\s+|designing\s+|developing\s+)',
        re.IGNORECASE,
    )
    if _FRAGMENT_RE.match(c):
        return None
    _OCCUPATION_RE = re.compile(
        r'^(?:engineers?|developers?|designers?|managers?|analysts?|'
        r'scientists?|researchers?|architects?|consultants?|specialists?|'
        r'coordinators?|directors?|executives?|PMs?|VPs?|ICs?|devs?)$',
        re.IGNORECASE,
    )
    if _OCCUPATION_RE.match(c):
        return None
    return c


def _split_list_candidate(raw: str):
    parts = _INLINE_LIST_SPLIT.split(raw)
    if len(parts) > 1:
        for p in parts:
            c = _clean_candidate(p.strip())
            if c:
                yield c
    else:
        c = _clean_candidate(raw)
        if c:
            yield c


def _build_taxonomy_set(skills):
    names = set()
    for s in skills:
        names.add(s.name.lower())
        for alias in (s.aliases or []):
            names.add(alias.lower())
    return names


def _is_in_taxonomy(candidate_lower: str, taxonomy_set: set, threshold: float = 0.88) -> bool:
    if candidate_lower in taxonomy_set:
        return True
    for name in taxonomy_set:
        if candidate_lower in name or name in candidate_lower:
            if min(len(candidate_lower), len(name)) >= 4:
                return True
    for name in taxonomy_set:
        if abs(len(candidate_lower) - len(name)) > 15:
            continue
        if SequenceMatcher(None, candidate_lower, name).ratio() >= threshold:
            return True
    return False


try:
    import spacy
    _NLP = spacy.load('en_core_web_sm')
    _SPACY_AVAILABLE = True
except Exception:
    _NLP = None
    _SPACY_AVAILABLE = False


def _spacy_candidates(text: str):
    if not _SPACY_AVAILABLE or not _NLP:
        return
    doc = _NLP(text[:3000])
    for ent in doc.ents:
        if ent.label_ in ('PRODUCT', 'ORG', 'WORK_OF_ART'):
            c = _clean_candidate(ent.text)
            if c:
                yield c
    for chunk in doc.noun_chunks:
        if any(t.pos_ == 'PROPN' for t in chunk):
            c = _clean_candidate(chunk.text)
            if c:
                yield c


def _extract_from_text(req_text: str, full_text: str):
    for tag, pattern in _CONTEXT_PATTERNS:
        for m in pattern.finditer(req_text):
            start = max(0, m.start() - 100)
            context_window = req_text[start:m.end() + 50]
            if _EEO_RE.search(context_window):
                continue
            raw = m.group(1).strip()
            for candidate in _split_list_candidate(raw):
                yield candidate, tag
    for item in _extract_bullet_items(req_text):
        for candidate in _split_list_candidate(item):
            yield candidate, 'bullet'
    for candidate in _spacy_candidates(req_text):
        yield candidate, 'spacy'


# ---------------------------------------------------------------------------
# Promotion helpers
# ---------------------------------------------------------------------------

def _llm_validate_candidates(candidates: list[str]) -> dict[str, bool]:
    """Batch-validate candidates via Claude haiku.
    Returns {name: is_real_skill}.
    Raises RuntimeError if validation cannot be completed — callers should
    leave candidates as pending rather than promoting blindly.
    """
    if not candidates:
        return {}

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY not set — cannot validate candidates')

    try:
        import anthropic
    except ImportError:
        raise RuntimeError('anthropic package not installed — run: pip install anthropic')

    client = anthropic.Anthropic(api_key=api_key)
    results = {}

    for i in range(0, len(candidates), 20):
        batch = candidates[i:i + 20]
        items = '\n'.join(f'{j + 1}. {c}' for j, c in enumerate(batch))
        prompt = (
            'For each item, reply YES if it is a specific learnable professional skill, '
            'tool, technology, certification, or methodology — or NO if it is generic, '
            'vague, or not a skill in itself.\n\n'
            f'{items}\n\n'
            'Reply with only a numbered list, one per line:\n1. YES\n2. NO\n...'
        )
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=150,
            messages=[{'role': 'user', 'content': prompt}],
        )
        lines = resp.content[0].text.strip().split('\n')
        for j, line in enumerate(lines):
            if j < len(batch):
                results[batch[j]] = 'YES' in line.upper()

    return results


def _classify_skill(name: str) -> str:
    """Assign category: technical / soft / domain."""
    n = name.lower()
    _TECH = {
        'python', 'java', 'javascript', 'typescript', 'golang', 'rust', 'c++', 'c#',
        'ruby', 'scala', 'kotlin', 'swift', 'php', 'aws', 'azure', 'gcp', 'kubernetes',
        'docker', 'terraform', 'ansible', 'linux', 'sql', 'nosql', 'spark', 'kafka',
        'airflow', 'dbt', 'pytorch', 'tensorflow', 'scikit', 'pandas', 'numpy',
        'snowflake', 'databricks', 'bigquery', 'redshift', 'postgres', 'mysql',
        'mongodb', 'elasticsearch', 'redis', 'git', 'ci/cd', 'devops', 'mlops',
        'api', 'rest', 'graphql', 'grpc', 'microservices', 'agile', 'scrum',
        'tdd', 'siem', 'firewall', 'vpn', 'tcp/ip', 'iam', 'oauth', 'saml',
        'sdk', 'llm', 'nlp', 'neural', 'cloud', 'serverless', 'container',
        'firmware', 'fpga', 'pcb', 'cad', 'matlab', 'plc', 'tableau', 'power bi',
        'looker', 'salesforce', 'hubspot', 'marketo', 'jira', 'sap', 'oracle',
        'workday', 'network engineer', 'hardware design', 'hardware test',
        'cloud-native', 'cloud native', 'security scanning', 'api development',
    }
    _SOFT = {
        'communication', 'leadership', 'collaboration', 'teamwork', 'problem',
        'critical thinking', 'emotional', 'time management', 'adaptability',
        'negotiation', 'mentoring', 'coaching', 'storytelling', 'stakeholder',
        'influencing',
    }
    for sig in _TECH:
        if sig in n:
            return 'Technical'
    for sig in _SOFT:
        if sig in n:
            return 'Soft'
    tech_suffixes = ('js', '.js', 'db', 'ops', 'sql', 'sdk', 'api', 'net', 'lang')
    if any(n.endswith(s) for s in tech_suffixes):
        return 'Technical'
    return 'Domain'


def _promote_candidate(candidate, taxonomy_set: set) -> bool:
    """Promote a SkillCandidate to the skills table and backfill job_skills.
    Returns True if promoted, False if already in taxonomy.
    """
    from app.models import db, Skill, JobSkill, SkillCandidateJob

    if _is_in_taxonomy(candidate.name.lower(), taxonomy_set):
        candidate.status = 'rejected'
        candidate.rejected_reason = 'already_in_taxonomy'
        return False

    # Look up aliases from import_skill_candidates module
    try:
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from import_skill_candidates import ALIASES
        aliases = ALIASES.get(candidate.name, [])
        for canonical, alts in ALIASES.items():
            if canonical.lower() == candidate.name.lower():
                aliases = alts
                break
    except ImportError:
        aliases = []

    skill = Skill(
        name=candidate.name,
        category=_classify_skill(candidate.name),
        is_verified=True,
        total_job_count=candidate.job_count,
        trending_score=0.0,
        aliases=aliases or [],
    )
    db.session.add(skill)
    db.session.flush()

    # Backfill job_skills for all historical jobs that mentioned this candidate
    db.session.execute(
        db.text(
            """
            INSERT INTO job_skills (job_id, skill_id, is_required, created_at)
            SELECT scj.job_id, :skill_id, true, NOW()
            FROM skill_candidate_jobs scj
            WHERE scj.candidate_id = :cid
            AND NOT EXISTS (
                SELECT 1 FROM job_skills js
                WHERE js.job_id = scj.job_id AND js.skill_id = :skill_id
            )
            """
        ),
        {'skill_id': skill.id, 'cid': candidate.id},
    )

    candidate.status = 'approved'
    candidate.promoted_skill_id = skill.id
    candidate.promoted_at = datetime.utcnow()

    # Add to local taxonomy set so subsequent promotions in same run don't re-add it
    taxonomy_set.add(candidate.name.lower())
    for a in aliases:
        taxonomy_set.add(a.lower())

    return True


def _check_and_promote(taxonomy_set: set) -> int:
    """Report qualifying candidates for manual review. No auto-promotion.

    Candidates meeting the threshold are left as 'pending' and reviewed
    in conversation with Claude on review day. After approval, promote via
    DB inserts then run scripts/backfill_skills.py for historical jobs.
    """
    from app.models import db

    rows = db.session.execute(db.text(
        """
        SELECT sc.name, sc.job_count, COUNT(DISTINCT j.company_id) AS co_count
        FROM skill_candidates sc
        JOIN skill_candidate_jobs scj ON scj.candidate_id = sc.id
        JOIN jobs j ON j.id = scj.job_id
        WHERE sc.status = 'pending'
        GROUP BY sc.id, sc.name, sc.job_count
        HAVING sc.job_count >= :min_jobs
           AND COUNT(DISTINCT j.company_id) >= :min_cos
        ORDER BY sc.job_count DESC
        """
    ), {'min_jobs': AUTO_PROMOTE_MIN_JOBS, 'min_cos': AUTO_PROMOTE_MIN_COMPANIES}).fetchall()

    if not rows:
        log('  No new candidates meet the promotion threshold.')
        return 0

    log(f'  {len(rows)} candidate(s) meet threshold (>={AUTO_PROMOTE_MIN_JOBS} jobs, >={AUTO_PROMOTE_MIN_COMPANIES} companies) — pending manual review:')
    for r in rows[:20]:
        log(f'    {r[0]:<45} jobs={r[1]}  cos={r[2]}')
    if len(rows) > 20:
        log(f'    ... and {len(rows) - 20} more')
    log('  Review candidates in conversation with Claude, then promote approved ones to taxonomy.')
    return 0


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db, Job, Skill, DiscoveryRun
from app.services.skill_extractor import extract_requirements_text

app = create_app()


def log(msg: str):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def _get_since_dt(force_full: bool) -> datetime:
    """Return the cutoff datetime for incremental processing."""
    if force_full:
        return datetime(2000, 1, 1)
    with app.app_context():
        last_run = db.session.execute(db.text(
            "SELECT MAX(started_at) FROM discovery_runs WHERE status = 'completed'"
        )).scalar()
    if last_run:
        return last_run
    # No prior run — process last INITIAL_LOOKBACK_DAYS days
    return datetime.utcnow() - timedelta(days=INITIAL_LOOKBACK_DAYS)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run(since_dt: datetime | None = None, force_full: bool = False,
        output_path: str | None = None):
    """Run incremental discovery. Called by weekly_scrape.py or standalone."""
    if output_path is None:
        output_path = f'/tmp/candidates_{datetime.utcnow().strftime("%Y%m%d")}.json'
    with app.app_context():
        if since_dt is None:
            since_dt = _get_since_dt(force_full)

        run_record = DiscoveryRun(started_at=datetime.utcnow(), status='running')
        run_record._output_path = output_path
        db.session.add(run_record)
        db.session.commit()

        try:
            _run_inner(run_record, since_dt)
        except Exception as e:
            run_record.status = 'failed'
            run_record.error = str(e)
            run_record.completed_at = datetime.utcnow()
            db.session.commit()
            raise


def _run_inner(run_record: 'DiscoveryRun', since_dt: datetime):
    log(f'Discovery run — processing jobs scraped since {since_dt.date()}')

    log('Loading skill taxonomy...')
    existing_skills = Skill.query.all()
    taxonomy_set = _build_taxonomy_set(existing_skills)
    log(f'  {len(existing_skills)} skills, {len(taxonomy_set)} names+aliases')

    log('Loading jobs...')
    jobs = db.session.query(
        Job.id,
        Job.company_id,
        Job.description_text,
        Job.posted_at,
    ).filter(
        Job.scraped_at >= since_dt,
        Job.description_text.isnot(None),
        Job.description_text != '',
    ).all()
    log(f'  {len(jobs):,} new jobs to process')

    if not jobs:
        log('No new jobs — nothing to do.')
        run_record.status = 'completed'
        run_record.completed_at = datetime.utcnow()
        db.session.commit()
        return

    # in-memory candidate accumulator: lower(name) → dict
    candidates: dict = {}
    closed_names: set = set()

    # batch_agg: candidate_lower → extraction data for this run's new jobs
    batch_agg = defaultdict(lambda: {
        'display_votes': defaultdict(int),
        'job_ids': set(),
        'company_ids': set(),
        'methods': set(),
        'contexts': [],
        'first_seen': None,
        'last_seen': None,
    })

    t0 = time.time()
    for idx, (job_id, company_id, desc_text, posted_at) in enumerate(jobs):
        if idx and idx % LOG_EVERY == 0:
            elapsed = time.time() - t0
            rate = idx / elapsed
            remaining = (len(jobs) - idx) / rate if rate > 0 else 0
            log(f'  {idx:,}/{len(jobs):,} ({rate:.0f}/s, ~{remaining/60:.1f} min remaining)')

        req_text, _ = extract_requirements_text(desc_text)
        seen_this_job = set()

        for candidate, method in _extract_from_text(req_text, desc_text):
            key = candidate.lower()
            if key in seen_this_job:
                continue
            seen_this_job.add(key)

            if key in closed_names:
                continue
            if _is_in_taxonomy(key, taxonomy_set):
                continue

            rec = batch_agg[key]
            rec['display_votes'][candidate] += 1
            rec['job_ids'].add(job_id)
            rec['company_ids'].add(company_id)
            rec['methods'].add(method)
            if posted_at:
                if rec['first_seen'] is None or posted_at < rec['first_seen']:
                    rec['first_seen'] = posted_at
                if rec['last_seen'] is None or posted_at > rec['last_seen']:
                    rec['last_seen'] = posted_at
            if len(rec['contexts']) < 3 and method.startswith('ctx'):
                rec['contexts'].append(candidate[:80])

    elapsed = time.time() - t0
    log(f'Extraction done in {elapsed:.0f}s — {len(batch_agg):,} unique candidates found')

    # Build in-memory candidate list (no DB writes for candidates)
    for key, rec in batch_agg.items():
        display_name = max(rec['display_votes'], key=rec['display_votes'].get)
        company_count_new = len(rec['company_ids'])
        job_count_new = len(rec['job_ids'])

        if key in candidates:
            c = candidates[key]
            c['job_count'] += job_count_new
            c['company_count'] = max(c['company_count'], company_count_new)
            if rec['last_seen']:
                last = rec['last_seen'].date().isoformat()
                if c['last_seen'] is None or last > c['last_seen']:
                    c['last_seen'] = last
            c['methods'] = list(set(c['methods']) | rec['methods'])
            for ctx in rec['contexts']:
                if ctx not in c['example_contexts'] and len(c['example_contexts']) < 3:
                    c['example_contexts'].append(ctx)
        else:
            candidates[key] = {
                'name': display_name,
                'job_count': job_count_new,
                'company_count': company_count_new,
                'first_seen': rec['first_seen'].date().isoformat() if rec['first_seen'] else None,
                'last_seen': rec['last_seen'].date().isoformat() if rec['last_seen'] else None,
                'methods': list(rec['methods']),
                'example_contexts': rec['contexts'][:3],
            }

    output_path = run_record._output_path
    sorted_candidates = sorted(candidates.values(), key=lambda x: x['job_count'], reverse=True)
    with open(output_path, 'w') as f:
        json.dump(sorted_candidates, f, indent=2)
    log(f'Wrote {len(sorted_candidates)} candidates to {output_path}')

    run_record.jobs_processed = len(jobs)
    run_record.candidates_upserted = len(sorted_candidates)
    run_record.candidates_promoted = 0
    run_record.status = 'completed'
    run_record.completed_at = datetime.utcnow()
    db.session.commit()

    log(f'Discovery run complete: {len(jobs)} jobs, {len(sorted_candidates)} candidates pending review')
    log(f'Review {output_path} and add approved skills via update_ai_taxonomy.py pattern')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=f'/tmp/candidates_{datetime.utcnow().strftime("%Y%m%d")}.json')
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    run(force_full=args.full, output_path=args.output)


if __name__ == '__main__':
    main()
