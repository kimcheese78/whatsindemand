"""Systematically update the AI skill taxonomy:
  1. Verify + fix category for existing unverified AI skills
  2. Enrich aliases on key existing skills
  3. Insert 17 new AI-native skills
  4. Deactivate zero-job Lightcast duplicates

Run (production):
  DATABASE_URL='postgresql://...' PYTHONPATH=. python3 scripts/update_ai_taxonomy.py
  DATABASE_URL='postgresql://...' PYTHONPATH=. python3 scripts/update_ai_taxonomy.py --apply
"""
import os
import sys
from datetime import datetime

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

from app import create_app
from app.models import db, Skill

APPLY = '--apply' in sys.argv

# ── Step 1: verify + fix category ────────────────────────────────────────────
# id -> category override (None = keep existing, set string to override)
VERIFY_IDS = {
    5024: 'technical',   # AI agents
    4906: 'technical',   # AI-assisted development
    4966: 'technical',   # MCP
    4710: 'technical',   # Claude
    4711: 'technical',   # Claude Code
    4712: 'technical',   # Gemini
    5117: 'domain',      # AI safety
    5076: 'domain',      # Responsible AI
    4929: 'technical',   # Embeddings
    4918: 'technical',   # LangGraph
    4965: 'technical',   # LLM APIs
    4722: 'technical',   # Transformer architectures
    4724: 'technical',   # LLMOps
    4714: 'technical',   # Amazon Bedrock
    5035: 'technical',   # LLM orchestration
    5049: 'technical',   # Microsoft Copilot
    5200: 'technical',   # Microsoft Copilot Studio
    5199: 'technical',   # Generative models
}

# ── Step 2: alias enrichment ─────────────────────────────────────────────────
# id -> list of aliases to append (duplicates skipped automatically)
ALIAS_ENRICHMENTS = {
    449: [  # Fine-tuning
        'LoRA', 'QLoRA', 'RLHF', 'instruction tuning', 'PEFT',
        'parameter-efficient fine-tuning', 'reinforcement learning from human feedback',
    ],
    185: [  # Prompt Engineering
        'chain-of-thought prompting', 'CoT prompting', 'few-shot prompting',
        'zero-shot prompting', 'system prompt design', 'system prompt',
    ],
    5024: [  # AI agents
        'AI agent development', 'autonomous agents', 'agentic systems',
        'agent framework', 'agent orchestration',
    ],
    5076: [  # Responsible AI
        'AI ethics', 'AI bias mitigation', 'algorithmic fairness',
        'ethical AI', 'AI governance',
    ],
    5049: [  # Microsoft Copilot
        'GitHub Copilot', 'M365 Copilot', 'Copilot Studio',
        'AI Copilot', 'copilot integration',
    ],
}

# Vector Databases looked up at runtime (name may vary in case)
VECTOR_DB_ALIASES = [
    'Pinecone', 'Weaviate', 'Chroma', 'Qdrant', 'Milvus',
    'vector store', 'vector search',
]

# ── Step 3: new skills ────────────────────────────────────────────────────────
NEW_SKILLS = [
    ('Agentic RAG',             'technical', ['Self-RAG', 'Graph RAG', 'GraphRAG', 'Adaptive RAG', 'agentic retrieval']),
    ('Context Window Management','technical', ['context management', 'context length', 'long context', 'context window']),
    ('Synthetic Data Generation','technical', ['synthetic data', 'data synthesis', 'synthetic dataset']),
    ('Function Calling',        'technical', ['tool use', 'tool calling', 'LLM tool use', 'function call API']),
    ('Human-in-the-Loop',       'domain',    ['HITL', 'human in the loop', 'human oversight', 'human-on-the-loop']),
    ('n8n',                     'technical', ['n8n automation', 'n8n workflow']),
    ('LLM Observability',       'technical', ['LLM monitoring', 'model observability', 'AI observability', 'AI monitoring']),
    ('Model Evaluation',        'technical', ['evals', 'LLM evals', 'model evals', 'eval framework', 'AI evaluation']),
    ('Hallucination Mitigation','technical', ['hallucination detection', 'LLM grounding', 'factual grounding', 'output validation']),
    ('Inference Optimization',  'technical', ['inference cost optimization', 'model inference optimization', 'LLM inference', 'token optimization']),
    ('Multimodal AI',           'technical', ['multimodal', 'multi-modal AI', 'vision-language model', 'VLM', 'multimodal models']),
    ('Speech AI',               'technical', ['audio AI', 'speech recognition', 'ASR', 'text-to-speech', 'TTS', 'speech synthesis']),
    ('Edge AI',                 'technical', ['edge AI deployment', 'on-device AI', 'edge inference', 'TinyML', 'edge ML']),
    ('Model Quantization',      'technical', ['model compression', 'quantization', 'INT8', 'model pruning', 'GGUF']),
    ('AI Security',             'technical', ['prompt injection', 'adversarial attacks', 'AI red teaming', 'LLM security', 'jailbreak prevention']),
    ('AI Compliance',           'domain',    ['EU AI Act', 'AI regulation', 'regulatory AI compliance', 'AI Act compliance']),
    ('AI Fluency',              'soft',      ['AI literacy', 'working with AI', 'AI adoption', 'AI-augmented work', 'AI-assisted analysis']),
]

# ── Step 4: deactivate duplicates ────────────────────────────────────────────
DEACTIVATE_IDS = [
    2472,  # PyTorch (Machine Learning Library)  → PyTorch
    2475,  # Scikit-learn (Machine Learning Library) → Scikit-learn
    2469,  # Keras (Neural Network Library) → Keras
    2447,  # Artificial Neural Networks → Neural Networks
    764,   # Word Embedding → Embeddings
    2437,  # AWS SageMaker → SageMaker (502)
]


def _add_aliases(skill, new_aliases):
    existing = {a.lower() for a in (skill.aliases or [])}
    added = []
    for a in new_aliases:
        if a.lower() not in existing:
            existing.add(a.lower())
            added.append(a)
    if added:
        skill.aliases = list(skill.aliases or []) + added
        skill.updated_at = datetime.utcnow()
    return added


def main():
    app = create_app()
    with app.app_context():
        now = datetime.utcnow()

        # ── Step 1 ──────────────────────────────────────────────────────────
        print('=== Step 1: Verify + fix category ===')
        step1_count = 0
        for skill_id, cat in VERIFY_IDS.items():
            s = Skill.query.get(skill_id)
            if not s:
                print(f'  MISSING id={skill_id}')
                continue
            changes = []
            if not s.is_verified:
                changes.append('is_verified=True')
            if s.category != cat:
                changes.append(f'category: {s.category!r} -> {cat!r}')
            if changes:
                print(f'  [{skill_id}] {s.name}: {", ".join(changes)}')
                if APPLY:
                    s.is_verified = True
                    s.category = cat
                    s.updated_at = now
                step1_count += 1
            else:
                print(f'  [{skill_id}] {s.name}: already ok')
        print(f'  → {step1_count} skills to update\n')

        # ── Step 2 ──────────────────────────────────────────────────────────
        print('=== Step 2: Alias enrichment ===')
        for skill_id, aliases in ALIAS_ENRICHMENTS.items():
            s = Skill.query.get(skill_id)
            if not s:
                print(f'  MISSING id={skill_id}')
                continue
            added = _add_aliases(s, aliases) if APPLY else [
                a for a in aliases if a.lower() not in {x.lower() for x in (s.aliases or [])}
            ]
            print(f'  [{skill_id}] {s.name}: +{len(added)} aliases {added}')

        # Vector Databases by name lookup
        vdb = Skill.query.filter(db.func.lower(Skill.name) == 'vector databases').first()
        if vdb:
            added = _add_aliases(vdb, VECTOR_DB_ALIASES) if APPLY else [
                a for a in VECTOR_DB_ALIASES if a.lower() not in {x.lower() for x in (vdb.aliases or [])}
            ]
            print(f'  [{vdb.id}] {vdb.name}: +{len(added)} aliases {added}')
        else:
            print('  Vector Databases skill not found by name')
        print()

        # ── Step 3 ──────────────────────────────────────────────────────────
        print('=== Step 3: New skills ===')
        inserted = 0
        skipped = 0
        new_ids = []
        for name, category, aliases in NEW_SKILLS:
            existing = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
            if existing:
                print(f'  SKIP (exists): {name} [id={existing.id}]')
                skipped += 1
                continue
            print(f'  INSERT: {name} ({category}) aliases={aliases}')
            if APPLY:
                s = Skill(
                    name=name,
                    category=category,
                    aliases=aliases,
                    is_verified=True,
                    total_job_count=0,
                    trending_score=0.0,
                )
                db.session.add(s)
                db.session.flush()
                new_ids.append(s.id)
            inserted += 1
        print(f'  → {inserted} to insert, {skipped} already exist\n')

        # ── Step 4 ──────────────────────────────────────────────────────────
        print('=== Step 4: Deactivate duplicates ===')
        for skill_id in DEACTIVATE_IDS:
            s = Skill.query.get(skill_id)
            if not s:
                print(f'  MISSING id={skill_id}')
                continue
            status = 'already unverified' if s.is_verified is False else 'will deactivate'
            print(f'  [{skill_id}] {s.name} ({s.total_job_count} jobs): {status}')
            if APPLY and s.is_verified is not False:
                s.is_verified = False
                s.updated_at = now
        print()

        # ── Commit ──────────────────────────────────────────────────────────
        if APPLY:
            db.session.commit()
            print('✓ All changes committed.')
            if new_ids:
                print(f'\nNew skill IDs: {new_ids}')
                print(f'Run backfill with: PYTHONPATH=. python scripts/backfill_skills.py --skill-ids {" ".join(str(i) for i in new_ids)}')
        else:
            print('Dry-run complete. Pass --apply to execute.')


if __name__ == '__main__':
    main()
