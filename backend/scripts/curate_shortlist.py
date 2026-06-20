"""Build skill_shortlist.json from a hand-curated keep-list.

Used in place of the LLM triage pass (scripts/triage_skill_candidates.py) while
the ANTHROPIC_API_KEY has no credit balance. CURATED maps an exact pending
candidate name -> (category, subcategory, [aliases]). This script re-queries
prod for the candidate id/counts so IDs are never transcribed by hand, then
writes backend/data/skill_shortlist.json grouped by category for review +
promotion (scripts/promote_shortlist.py).

Run:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/curate_shortlist.py
"""
import json
import os
import sys
from collections import defaultdict

if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db

app = create_app()

# name (exact, as stored) -> (category, subcategory, aliases)
CURATED = {
    # ── AI & Machine Learning ────────────────────────────────────────────────
    'LLM integration':        ('technical', 'AI & Machine Learning', ['LLM integrations']),
    'LLM architectures':      ('technical', 'AI & Machine Learning', []),
    'Flyte':                  ('technical', 'AI & Machine Learning', ['Flyte orchestration']),
    'SGLang':                 ('technical', 'AI & Machine Learning', []),
    'Isaac':                  ('technical', 'AI & Machine Learning', ['NVIDIA Isaac', 'Isaac Sim']),
    'Vision-Language-Action': ('technical', 'AI & Machine Learning', ['VLA', 'VLA models']),
    'pretraining':            ('technical', 'AI & Machine Learning', ['pre-training']),
    'model routing':          ('technical', 'AI & Machine Learning', ['LLM routing']),
    'HeyGen':                 ('technical', 'AI & Machine Learning', []),

    # ── Databases & Data Engineering ─────────────────────────────────────────
    'Debezium':               ('technical', 'Databases & Data Engineering', ['CDC', 'Change Data Capture']),
    'lakehouse architectures':('technical', 'Databases & Data Engineering', ['data lakehouse', 'lakehouse']),
    'Delta Tables':           ('technical', 'Databases & Data Engineering', ['Delta Lake']),
    'Aurora':                 ('technical', 'Databases & Data Engineering', ['Amazon Aurora', 'AWS Aurora']),
    'Datomic':                ('technical', 'Databases & Data Engineering', []),
    'Unity Catalog':          ('technical', 'Databases & Data Engineering', []),
    'graph technologies':     ('technical', 'Databases & Data Engineering', ['graph databases']),
    'OLAP technologies':      ('technical', 'Databases & Data Engineering', ['OLAP']),
    'optimizing complex queries for performance': ('technical', 'Databases & Data Engineering', ['query optimization', 'SQL tuning']),

    # ── Data Science & Analytics ─────────────────────────────────────────────
    'GDAL':                   ('technical', 'Data Science & Analytics', []),
    'ParaView':               ('technical', 'Data Science & Analytics', []),
    'QuickSight':             ('technical', 'Data Science & Analytics', ['Amazon QuickSight']),
    'KNIME':                  ('technical', 'Data Science & Analytics', []),
    'R/R Shiny advantageous': ('technical', 'Data Science & Analytics', ['R Shiny', 'Shiny']),

    # ── Programming Languages ────────────────────────────────────────────────
    'concurrent programming': ('technical', 'Programming Languages', ['concurrency', 'multithreading', 'parallel programming']),
    'compiler design':        ('technical', 'Programming Languages', []),
    'ASTs':                   ('technical', 'Programming Languages', ['Abstract Syntax Tree']),
    'COBOL':                  ('technical', 'Programming Languages', []),
    'VBScript':               ('technical', 'Programming Languages', []),

    # ── Frontend & Web ───────────────────────────────────────────────────────
    'SSR':                    ('technical', 'Frontend & Web', ['Server-Side Rendering']),
    'headless CMS architectures': ('technical', 'Frontend & Web', ['headless CMS']),
    'module federation':      ('technical', 'Frontend & Web', []),

    # ── Backend & APIs ───────────────────────────────────────────────────────
    'Jinja':                  ('technical', 'Backend & APIs', ['Jinja2']),
    'Hapi.js':                ('technical', 'Backend & APIs', ['hapi']),
    'CAP theorem':            ('technical', 'Backend & APIs', []),
    'domain modeling':        ('technical', 'Backend & APIs', ['domain-driven design']),
    'multi-tenancy':          ('technical', 'Backend & APIs', ['multi-tenant architecture']),

    # ── Cloud & Infrastructure ───────────────────────────────────────────────
    'Cloudflare Workers':     ('technical', 'Cloud & Infrastructure', []),
    'AWS Control Tower':      ('technical', 'Cloud & Infrastructure', []),
    'AWS Workspaces':         ('technical', 'Cloud & Infrastructure', []),
    'ELB':                    ('technical', 'Cloud & Infrastructure', ['Elastic Load Balancing']),

    # ── DevOps & CI/CD ───────────────────────────────────────────────────────
    'Rancher':                ('technical', 'DevOps & CI/CD', []),
    'QEMU':                   ('technical', 'DevOps & CI/CD', []),
    'HashiCorp Nomad':        ('technical', 'DevOps & CI/CD', ['Nomad']),
    'Cilium CNI':             ('technical', 'DevOps & CI/CD', ['Cilium']),
    'Podman':                 ('technical', 'DevOps & CI/CD', []),

    # ── Networking & Systems ─────────────────────────────────────────────────
    'structured cabling standards': ('technical', 'Networking & Systems', ['structured cabling']),
    'reverse proxy':          ('technical', 'Networking & Systems', []),
    'VDI':                    ('technical', 'Networking & Systems', ['Virtual Desktop Infrastructure']),
    'IPAM':                   ('technical', 'Networking & Systems', ['IP Address Management']),
    'Junos':                  ('technical', 'Networking & Systems', ['Juniper Junos']),
    'Tailscale':              ('technical', 'Networking & Systems', []),
    'DNS management':         ('technical', 'Networking & Systems', ['DNS']),
    '802.1x Authentication':  ('technical', 'Networking & Systems', ['802.1X']),

    # ── Security & Compliance ────────────────────────────────────────────────
    'MFA':                    ('technical', 'Security & Compliance', ['Multi-Factor Authentication', '2FA']),
    'RMF process':            ('technical', 'Security & Compliance', ['Risk Management Framework', 'NIST RMF']),
    'HSMs':                   ('technical', 'Security & Compliance', ['Hardware Security Module']),
    'certificate-based authentication': ('technical', 'Security & Compliance', []),
    'ABAC':                   ('technical', 'Security & Compliance', ['Attribute-Based Access Control']),
    'COMSEC requirements':    ('technical', 'Security & Compliance', ['COMSEC']),
    'software composition analysis': ('technical', 'Security & Compliance', ['SCA']),
    'MITRE':                  ('technical', 'Security & Compliance', ['MITRE ATT&CK', 'ATT&CK']),
    'CyberArk':               ('technical', 'Security & Compliance', []),
    'threat actor TTPs':      ('technical', 'Security & Compliance', ['TTPs']),
    'Security+':              ('technical', 'Security & Compliance', ['CompTIA Security+']),
    'SWG':                    ('technical', 'Security & Compliance', ['Secure Web Gateway']),
    'CVSS':                   ('technical', 'Security & Compliance', ['Common Vulnerability Scoring System']),
    'NIST 800-53 Rev 5':      ('technical', 'Security & Compliance', ['NIST 800-53', 'NIST SP 800-53']),
    'WebAuthn':               ('technical', 'Security & Compliance', []),
    'SCIM provisioning':      ('technical', 'Security & Compliance', ['SCIM']),
    'tools like Burp Suite':  ('technical', 'Security & Compliance', ['Burp Suite']),
    'Verkada':                ('technical', 'Security & Compliance', []),
    'FleetDM':                ('technical', 'Security & Compliance', ['Fleet']),
    'Lacework':               ('technical', 'Security & Compliance', []),
    'Trivy':                  ('technical', 'Security & Compliance', []),
    'Privacy Enhancing Technologies': ('technical', 'Security & Compliance', ['PETs']),
    'secrets management platforms': ('technical', 'Security & Compliance', ['secrets management']),

    # ── Hardware & Embedded ──────────────────────────────────────────────────
    'IPC-610':                ('technical', 'Hardware & Embedded', ['IPC-A-610']),
    'accordance with IPC-A-620 standards': ('technical', 'Hardware & Embedded', ['IPC-A-620', 'IPC-620']),
    'FEA software':           ('technical', 'Hardware & Embedded', ['Finite Element Analysis', 'FEA']),
    'Zemax':                  ('technical', 'Hardware & Embedded', []),
    'AFSIM':                  ('technical', 'Hardware & Embedded', ['Advanced Framework for Simulation, Integration and Modeling']),
    'EtherCAT':               ('technical', 'Hardware & Embedded', []),
    'Mastercam':              ('technical', 'Hardware & Embedded', []),
    'DAQ systems':            ('technical', 'Hardware & Embedded', ['Data Acquisition', 'DAQ']),
    'beamforming':            ('technical', 'Hardware & Embedded', []),
    'AWS D17.1':              ('technical', 'Hardware & Embedded', ['aerospace welding standard']),
    'QNX':                    ('technical', 'Hardware & Embedded', []),
    'RTOS environments':      ('technical', 'Hardware & Embedded', ['Real-Time Operating System', 'RTOS']),
    'Vector CANoe':           ('technical', 'Hardware & Embedded', ['CANoe']),
    'HDI':                    ('technical', 'Hardware & Embedded', ['High Density Interconnect']),
    'SoC integration':        ('technical', 'Hardware & Embedded', ['System-on-Chip', 'SoC']),
    'DFT implementation':     ('technical', 'Hardware & Embedded', ['Design for Test', 'DFT']),
    'FinFET technologies':    ('technical', 'Hardware & Embedded', ['FinFET']),
    'OpenBMC':                ('technical', 'Hardware & Embedded', []),
    'IMUs':                   ('technical', 'Hardware & Embedded', ['Inertial Measurement Unit']),
    'Electrostatic Discharge':('technical', 'Hardware & Embedded', ['ESD']),
    'UWB':                    ('technical', 'Hardware & Embedded', ['Ultra-Wideband']),
    'Industrial IoT systems': ('technical', 'Hardware & Embedded', ['IIoT', 'Industrial IoT']),
    '5-axis milling':         ('technical', 'Hardware & Embedded', []),
    'CAM programming':        ('technical', 'Hardware & Embedded', ['Computer-Aided Manufacturing']),
    'Zephyr':                 ('technical', 'Hardware & Embedded', ['Zephyr RTOS']),

    # ── QA & Testing ─────────────────────────────────────────────────────────
    'manual QA testing':      ('technical', 'QA & Testing', ['manual testing', 'manual QA']),
    'LoadRunner':             ('technical', 'QA & Testing', []),
    'BDD/TDD testing approaches': ('technical', 'QA & Testing', ['Behavior-Driven Development', 'BDD', 'Test-Driven Development', 'TDD']),

    # ── Enterprise Tools & Platforms ─────────────────────────────────────────
    'Houdini':                ('technical', 'Enterprise Tools & Platforms', ['SideFX Houdini']),
    'Shotgrid':               ('technical', 'Enterprise Tools & Platforms', ['ShotGrid']),
    'xAPI':                   ('technical', 'Enterprise Tools & Platforms', ['Experience API', 'Tin Can API']),
    'Calypso platform':       ('technical', 'Enterprise Tools & Platforms', ['Calypso']),
    'Infor LN':               ('technical', 'Enterprise Tools & Platforms', ['Infor']),
    'MasterControl':          ('technical', 'Enterprise Tools & Platforms', []),
    'Reltio':                 ('technical', 'Enterprise Tools & Platforms', []),
    'SAP/S4 Hana':            ('technical', 'Enterprise Tools & Platforms', ['SAP S/4HANA', 'S/4HANA']),
    'SCORM':                  ('technical', 'Enterprise Tools & Platforms', []),
    'Esri App Builders':      ('technical', 'Enterprise Tools & Platforms', ['Esri', 'ArcGIS']),
    'CLO 3D':                 ('technical', 'Enterprise Tools & Platforms', []),
    'Linksquares':            ('technical', 'Enterprise Tools & Platforms', []),
    'Dovetail':               ('technical', 'Enterprise Tools & Platforms', []),
    'Smartling':              ('technical', 'Enterprise Tools & Platforms', []),
    'CAT platforms':          ('technical', 'Enterprise Tools & Platforms', ['Computer-Assisted Translation', 'CAT tools']),
    'Encompass LOS':          ('technical', 'Enterprise Tools & Platforms', ['Encompass']),
    'Lever':                  ('technical', 'Enterprise Tools & Platforms', []),
    'no-code/low-code':       ('technical', 'Enterprise Tools & Platforms', ['low-code', 'no-code']),
    'Nanite':                 ('technical', 'Enterprise Tools & Platforms', ['Unreal Nanite']),

    # ── Mobile ───────────────────────────────────────────────────────────────
    'AOSP':                   ('technical', 'Mobile', ['Android Open Source Project']),

    # ── Domain: Industries ───────────────────────────────────────────────────
    'non-pharmacological interventions': ('domain', 'Industries', []),
    'geospatial intelligence':('domain', 'Industries', ['GEOINT']),
    'UAVs':                   ('domain', 'Industries', ['drones', 'unmanned aerial vehicles']),
    'genetic testing':        ('domain', 'Industries', []),
    'CPG industry':           ('domain', 'Industries', ['Consumer Packaged Goods', 'CPG']),
    'EV architectures':       ('domain', 'Industries', ['electric vehicle architectures']),
    'ligand binding assays':  ('domain', 'Industries', []),
    'Utilization Management': ('domain', 'Industries', []),
    'using EMR systems':      ('domain', 'Industries', ['EMR', 'Electronic Medical Records', 'EHR']),
    'RWE':                    ('domain', 'Industries', ['Real-World Evidence']),

    # ── Domain: Finance & Accounting ─────────────────────────────────────────
    'EMV':                    ('domain', 'Finance & Accounting', ['EMV chip', 'chip and PIN']),
    'Order to Cash':          ('domain', 'Finance & Accounting', ['O2C']),
    'ACCA':                   ('domain', 'Finance & Accounting', []),
    'SOX control':            ('domain', 'Finance & Accounting', ['SOX', 'Sarbanes-Oxley']),

    # ── Domain: Legal & Compliance ───────────────────────────────────────────
    'AML/CFT risks':          ('domain', 'Legal & Compliance', ['AML', 'CFT', 'Anti-Money Laundering', 'AML/BSA', 'BSA', 'Bank Secrecy Act']),
    'patent litigation':      ('domain', 'Legal & Compliance', []),
    'commercial litigation':  ('domain', 'Legal & Compliance', []),
    'MIL-STD-882':            ('domain', 'Legal & Compliance', []),
    'US export controls':     ('domain', 'Legal & Compliance', ['ITAR', 'EAR', 'export controls']),
    'CE marking':             ('domain', 'Legal & Compliance', ['CE mark']),
    'COPPA':                  ('domain', 'Legal & Compliance', []),
    'NCQA standards':         ('domain', 'Legal & Compliance', ['NCQA']),

    # ── Domain: Marketing & Growth ───────────────────────────────────────────
    'funnel analysis':        ('domain', 'Marketing & Growth', []),
    'short-form video production': ('domain', 'Marketing & Growth', []),
    'D2C environments':       ('domain', 'Marketing & Growth', ['DTC', 'Direct-to-Consumer']),
    'brand building':         ('domain', 'Marketing & Growth', []),
    'both Product-Led Growth':('domain', 'Marketing & Growth', ['Product-Led Growth', 'PLG']),
    'App Store Optimization': ('domain', 'Marketing & Growth', ['ASO']),

    # ── Domain: Business & Operations ────────────────────────────────────────
    'cash handling':          ('domain', 'Business & Operations', []),
    '3PL':                    ('domain', 'Business & Operations', ['Third-Party Logistics']),
    'warehouse management software': ('domain', 'Business & Operations', ['WMS']),
    'MES/ERP software':       ('domain', 'Business & Operations', ['MES', 'Manufacturing Execution System']),

    # ── Domain: People & HR ──────────────────────────────────────────────────
    'Core HCM':               ('domain', 'People & HR', ['HCM']),

    # ── Domain: Methodologies ────────────────────────────────────────────────
    'PMP':                    ('domain', 'Methodologies', ['Project Management Professional']),
    'clinical trial methodology': ('domain', 'Methodologies', []),
    'Quality by Design':      ('domain', 'Methodologies', ['QbD']),
    'factory acceptance testing': ('domain', 'Methodologies', ['FAT']),
    'Team Topologies':        ('domain', 'Methodologies', []),
    'systems development life cycle': ('domain', 'Methodologies', ['SDLC']),
    'three lines of defence model': ('domain', 'Methodologies', ['three lines of defense']),
    'DFX':                    ('domain', 'Methodologies', ['Design for Excellence']),

    # ── Soft ─────────────────────────────────────────────────────────────────
    'systems thinking':       ('soft', 'Problem Solving & Critical Thinking', []),
}


def main():
    with app.app_context():
        rows = db.session.execute(db.text(
            "SELECT id, name, job_count, company_count, example_contexts "
            "FROM skill_candidates WHERE status='pending'"
        )).fetchall()
        by_name = {r[1]: r for r in rows}

    grouped = defaultdict(list)
    missing = []
    for name, (cat, sub, aliases) in CURATED.items():
        r = by_name.get(name)
        if not r:
            missing.append(name)
            continue
        grouped[cat].append({
            'candidate_id': r[0],
            'name': name,
            'category': cat,
            'subcategory': sub,
            'aliases': aliases,
            'company_count': r[3],
            'job_count': r[2],
            'example_contexts': list(r[4] or [])[:3],
        })

    for cat in grouped:
        grouped[cat].sort(key=lambda x: (-x['company_count'], -x['job_count']))

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'skill_shortlist.json')
    payload = {
        'meta': {
            'source': 'hand-curated (LLM key out of credits)',
            'kept': sum(len(v) for v in grouped.values()),
            'missing_from_pending': missing,
        },
        'skills_by_category': grouped,
    }
    with open(out_path, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f'Wrote {payload["meta"]["kept"]} curated skills to {out_path}')
    for cat in ('technical', 'domain', 'soft'):
        print(f'  {cat}: {len(grouped.get(cat, []))}')
    if missing:
        print(f'\n  WARNING: {len(missing)} curated names not found in pending candidates:')
        for m in missing:
            print(f'    - {m!r}')


if __name__ == '__main__':
    main()
