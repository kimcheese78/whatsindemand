"""
Second batch of manual industry overrides for remaining Other companies.
"""
import os, sys
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL must be set. Pass it as an env var — see CLAUDE.md.')
from app import create_app
from app.models import Company, db
from sqlalchemy import text

APPLY = '--apply' in sys.argv

OVERRIDES = {
    # ── Developer Tools ──────────────────────────────────────────────────────
    'Akuity': 'Developer Tools',
    'AOT Technologies': 'Developer Tools',
    'Arcotech': 'Developer Tools',
    'BrightSign': 'Developer Tools',
    'dbt Labs': 'Developer Tools',
    'DigitalBridge': 'Developer Tools',
    'Dots': 'Developer Tools',
    'Dubber': 'Developer Tools',
    'FlowFuse': 'Developer Tools',
    'Fluxon': 'Developer Tools',
    'Instabase': 'AI/ML',
    'InterSystems': 'Developer Tools',
    'Janea Systems': 'Developer Tools',
    'Kalles Group': 'Developer Tools',
    'Kicksaw': 'Developer Tools',
    'Kion': 'Developer Tools',
    'Konrad': 'Developer Tools',
    'Lazarus': 'Developer Tools',
    'Levio': 'Developer Tools',
    'Lightrun': 'Developer Tools',
    'Lob': 'Developer Tools',
    'Loka, Inc': 'Developer Tools',
    'Loka® Inc': 'Developer Tools',
    'Lyra Technology Group': 'Developer Tools',
    'Magic Hat Consulting': 'Developer Tools',
    'Magnolia': 'Developer Tools',
    'Meridian Partners': 'Developer Tools',
    'Metalab': 'Developer Tools',
    'Method, a GlobalLogic company': 'Developer Tools',
    'MetTel': 'Developer Tools',
    'PALO IT': 'Developer Tools',
    'Praxent': 'Developer Tools',
    'Prophecy': 'Developer Tools',
    'Proto': 'Developer Tools',
    'RADAR': 'Developer Tools',
    'Realm': 'Developer Tools',
    'Redapt': 'Developer Tools',
    'Santex': 'Developer Tools',
    'Samsungresearchamerica': 'Robotics & Hardware',
    'Teague': 'Developer Tools',
    'Telnyx': 'Developer Tools',
    'Tenon': 'Developer Tools',
    'Thoughtworks': 'Developer Tools',
    'Ting Internet': 'Developer Tools',
    'Valtech': 'Developer Tools',
    'Viam': 'Developer Tools',
    'Wavelo': 'Developer Tools',
    'WiZiX Technology Group, Inc': 'Developer Tools',
    'YLD': 'Developer Tools',

    # ── Fintech ──────────────────────────────────────────────────────────────
    'Alloy': 'Fintech',
    'Anders': 'Fintech',
    'Ariel Alternatives': 'Fintech',
    'Boku': 'Fintech',
    'Bridgewater Associates': 'Fintech',
    'Bridgewater Associates LP': 'Fintech',
    'EquityZen': 'Fintech',
    'Filecoin Foundation': 'Fintech',
    'Financial Times': 'Media & Entertainment',
    'Finyard': 'Fintech',
    'Found': 'Fintech',
    'Inyova': 'Fintech',
    'Jane Street Events': 'Fintech',
    'Kaiko Systems GmbH': 'Fintech',
    'Kiva.org': 'Fintech',
    'Kiva RTP': 'Fintech',
    'LTSE': 'Fintech',
    'Perpay - Career\'s Page': 'Fintech',
    'Pine': 'Fintech',
    'Prodigal': 'Fintech',
    'RA Capital Management, LLC': 'Fintech',
    'Radix Trading Experienced Job Board': 'Fintech',
    'Sagent': 'Fintech',
    'Seed': 'Fintech',
    'SSV Labs': 'Fintech',
    'The Riverside Company': 'Fintech',
    'TPG Careers Page': 'Fintech',
    'Ubiquity': 'Fintech',
    'WithumSmith+Brown': 'Fintech',
    'Wholesail': 'Fintech',
    'XION': 'Fintech',

    # ── Marketing Tech ───────────────────────────────────────────────────────
    '8am': 'Marketing Tech',
    'Appodeal': 'Marketing Tech',
    'Archrival': 'Marketing Tech',
    'Biolumina': 'Marketing Tech',
    'Deeplocal': 'Marketing Tech',
    'Flodesk': 'Marketing Tech',
    'Flowcode': 'Marketing Tech',
    'Fluency': 'Marketing Tech',
    'Inizio Engage XD': 'Marketing Tech',
    'Inizio Ignite': 'HealthTech',
    'Inizio Ignite | Vynamic': 'Marketing Tech',
    'Kargo': 'Marketing Tech',
    'Kargo': 'Marketing Tech',
    'Kayzen': 'Marketing Tech',
    'Landor': 'Marketing Tech',
    'Linqia': 'Marketing Tech',
    'Madano': 'Marketing Tech',
    'MATTE PROJECTS': 'Marketing Tech',
    'MERGE': 'Marketing Tech',
    'Phiture': 'Marketing Tech',
    'Placements.io': 'Marketing Tech',
    'Podium': 'Marketing Tech',
    'Postscript': 'Marketing Tech',
    'Rabin Martin': 'Marketing Tech',
    'Real Chemistry': 'Marketing Tech',
    'Recast': 'Marketing Tech',
    'Revenue.io': 'Marketing Tech',
    'Rewards Network': 'Marketing Tech',
    'Rival Technologies': 'Marketing Tech',
    'SALT XC': 'Marketing Tech',
    'TANK Worldwide': 'Marketing Tech',
    'TechnologyAdvice': 'Marketing Tech',
    'Tribal': 'Marketing Tech',
    'Tribal Worldwide Spain': 'Marketing Tech',
    'Vooban': 'AI/ML',
    'Voxie Inc': 'Marketing Tech',
    'We. Communications': 'Marketing Tech',
    'WITHIN': 'Marketing Tech',
    'Yalo Inc.': 'Marketing Tech',
    'Ylopo': 'Marketing Tech',

    # ── HealthTech ───────────────────────────────────────────────────────────
    'Axogen': 'HealthTech',
    'Bitfocus': 'HealthTech',
    'Careers at Eucalyptus': 'HealthTech',
    'Iowa Cannabis Company': 'HealthTech',
    'Lantern': 'HealthTech',
    'Mather Headquarters': 'HealthTech',
    'Mather Place': 'HealthTech',
    'Médecins Sans Frontières / Doctors Without Borders Canada': 'HealthTech',
    'MIND 24-7': 'HealthTech',
    'Pair Team': 'HealthTech',
    'Paytient': 'HealthTech',
    'Pearl': 'HealthTech',
    'Pelago': 'HealthTech',
    'Phamily': 'HealthTech',
    'PurposeMed': 'HealthTech',
    'Resolve To Save Lives': 'HealthTech',
    'Revero': 'HealthTech',
    'Rialtic, Inc.': 'HealthTech',
    'Rightway': 'HealthTech',
    'Splendido': 'HealthTech',
    'Terrabis': 'HealthTech',
    'Tetra': 'HealthTech',
    'The Perfect Workout': 'HealthTech',
    'The Ridge RTC': 'HealthTech',
    'The Specialty Alliance': 'HealthTech',
    'Urban Sports Club': 'HealthTech',
    'Wellist': 'HealthTech',
    'Willow Innovations': 'HealthTech',
    'WePractice (Psychotherapeut:in in Weiterbildung)': 'HealthTech',
    'WePractice (Psychotherapeutische Leitungsfunktionen)': 'HealthTech',
    'West Cancer Center': 'HealthTech',
    'WestCoast Children\'s Clinic': 'HealthTech',

    # ── B2B SaaS ─────────────────────────────────────────────────────────────
    'AlphaSights': 'B2B SaaS',
    'AMEND Consulting': 'B2B SaaS',
    'Atomicwork Inc': 'B2B SaaS',
    'Banyan Software': 'B2B SaaS',
    'Bevi': 'B2B SaaS',
    'Boulevard': 'B2B SaaS',
    'Box': 'B2B SaaS',
    'CueBox': 'B2B SaaS',
    'DMSI': 'B2B SaaS',
    'Fairmarkit': 'B2B SaaS',
    'Fundraise Up': 'B2B SaaS',
    'iRely Career Site': 'B2B SaaS',
    'Intradiem': 'B2B SaaS',
    'Kinetic': 'B2B SaaS',
    'Klaxoon': 'B2B SaaS',
    'Knack': 'B2B SaaS',
    'NISC': 'B2B SaaS',
    'Paperless Parts': 'B2B SaaS',
    'PerformLine': 'B2B SaaS',
    'Plume': 'B2B SaaS',
    'Poka EN': 'B2B SaaS',
    'Pushpay': 'B2B SaaS',
    'Quadbridge': 'B2B SaaS',
    'quip': 'B2B SaaS',
    'Relay Network': 'B2B SaaS',
    'Reliant': 'B2B SaaS',
    'Rockbot': 'B2B SaaS',
    'saas.group': 'B2B SaaS',
    'Sage': 'B2B SaaS',
    'Secretariat': 'B2B SaaS',
    'The Brattle Group': 'B2B SaaS',
    'The Weather Company': 'B2B SaaS',
    'TouchBistro': 'B2B SaaS',
    'Turnkey': 'B2B SaaS',
    'Unqork': 'B2B SaaS',
    'VIXXO': 'B2B SaaS',
    'Wizard': 'B2B SaaS',
    'WithMe, Inc.': 'B2B SaaS',

    # ── Security ─────────────────────────────────────────────────────────────
    'Fingerprint': 'Security',
    'Instnt': 'Security',
    'Microblink': 'Security',
    'Rubrik Job Board': 'Security',
    'Telesign': 'Security',
    'Tenable, Inc.': 'Security',
    'VerSprite - LinkedIn': 'Security',

    # ── E-commerce & Retail ───────────────────────────────────────────────────
    'Cuyana': 'E-commerce & Retail',
    'Fabric': 'E-commerce & Retail',
    'Flashfood': 'E-commerce & Retail',
    'Focal Systems': 'E-commerce & Retail',
    'IPSY': 'E-commerce & Retail',
    'Jungle Scout': 'E-commerce & Retail',
    'Kate McLeod': 'E-commerce & Retail',
    'Mammoth Brands': 'E-commerce & Retail',
    'Momentous': 'E-commerce & Retail',
    'Paperless Post': 'E-commerce & Retail',
    'Parachute Home': 'E-commerce & Retail',
    'Picnic': 'E-commerce & Retail',
    'Puffco': 'E-commerce & Retail',
    'The Quality Group': 'E-commerce & Retail',
    'The Quality Group GmbH': 'E-commerce & Retail',
    'Tomofun | Furbo Pet Camera': 'E-commerce & Retail',
    'Traeger Grills': 'E-commerce & Retail',
    'UMI Stone/Opustone': 'E-commerce & Retail',
    'unybrands': 'E-commerce & Retail',
    'Whop': 'E-commerce & Retail',

    # ── Data & Analytics ─────────────────────────────────────────────────────
    'Artefact': 'Data & Analytics',
    'BlueLabs, Inc.': 'Data & Analytics',
    'DataKind': 'Data & Analytics',
    'Landmark Information Group': 'Data & Analytics',
    'Landmark Information Group - Internal': 'Data & Analytics',
    'Precisely International Jobs': 'Data & Analytics',
    'Precisely US Jobs': 'Data & Analytics',
    'Quilt': 'AI/ML',
    'Reltio': 'Data & Analytics',
    'TigerGraph': 'Data & Analytics',
    'Tellius': 'Data & Analytics',

    # ── Climate & Energy ─────────────────────────────────────────────────────
    'Mill': 'Climate & Energy',
    'Picarro, Inc': 'Climate & Energy',
    'Resource Environmental Solutions LLC': 'Climate & Energy',
    'Revivn': 'Climate & Energy',
    'Runwise': 'Climate & Energy',
    'TerraClear': 'Robotics & Hardware',
    'Valar Atomics': 'Climate & Energy',
    'Watch Duty - Volunteers': 'GovTech & Defense',

    # ── GovTech & Defense ────────────────────────────────────────────────────
    'IronMountain Solutions': 'GovTech & Defense',
    'Jensen Hughes': 'GovTech & Defense',
    'Juvare': 'GovTech & Defense',
    'PUBLIC': 'GovTech & Defense',
    'Red Cell Partners': 'GovTech & Defense',
    'TrellisWare Technologies': 'GovTech & Defense',
    'Unlimited Technology': 'GovTech & Defense',
    'Woolpert': 'GovTech & Defense',

    # ── Gaming ───────────────────────────────────────────────────────────────
    'AppLovin': 'Gaming',
    'Bungie': 'Gaming',
    'The Pokémon Company International': 'Gaming',

    # ── HR Tech ───────────────────────────────────────────────────────────────
    'Level.works': 'HR Tech',
    'MindGym': 'HR Tech',
    'Select Management Group': 'HR Tech',
    'Tenstreet': 'HR Tech',
    'Upwork': 'HR Tech',
    'Vaco LLC': 'HR Tech',
    'Weploy': 'HR Tech',

    # ── PropTech ─────────────────────────────────────────────────────────────
    'Grupo QuintoAndar': 'PropTech',
    'Redpin': 'PropTech',
    'Resident': 'PropTech',
    'Transactly Connect': 'PropTech',
    'Updater': 'PropTech',
    'Venn': 'PropTech',
    'WIN Home Inspection': 'PropTech',

    # ── Automotive & Mobility ────────────────────────────────────────────────
    'Flash': 'Automotive & Mobility',
    'Kodiak Solutions': 'Automotive & Mobility',
    'LeasingMarkt.de': 'Automotive & Mobility',
    'Metropolis': 'Automotive & Mobility',
    'Vay': 'Automotive & Mobility',
    'Wheely': 'Automotive & Mobility',
    'Wing': 'Logistics & Supply Chain',
    'Wolt - English': 'Logistics & Supply Chain',
    'Wolt - Hebrew': 'Logistics & Supply Chain',

    # ── Robotics & Hardware ──────────────────────────────────────────────────
    'Fairchild Imaging, Inc.': 'Robotics & Hardware',
    'Kensington': 'Robotics & Hardware',
    'LG Electronics': 'Robotics & Hardware',
    'LI-COR': 'Robotics & Hardware',
    'Mendaera, Inc.': 'Robotics & Hardware',
    'Polygon US': 'Robotics & Hardware',
    'QphoX': 'Robotics & Hardware',
    'RAB Lighting': 'Robotics & Hardware',
    'Re:Build Manufacturing': 'Robotics & Hardware',
    'Samsung Next': 'Robotics & Hardware',
    'Senrasystems': 'Robotics & Hardware',
    'TerraClear': 'Robotics & Hardware',
    'Urschel Laboratories, Inc.': 'Robotics & Hardware',
    'VEGA Americas': 'Robotics & Hardware',
    'Velocity Electronics': 'Robotics & Hardware',

    # ── InsurTech ─────────────────────────────────────────────────────────────
    'Kettle': 'InsurTech',
    'Matic': 'InsurTech',

    # ── Legal Tech ───────────────────────────────────────────────────────────
    'Elite Technology': 'Legal Tech',
    'Jusbrasil': 'Legal Tech',
    'Proof': 'Legal Tech',
    'Scale LLP': 'Legal Tech',

    # ── Media & Entertainment ────────────────────────────────────────────────
    'Financial Times': 'Media & Entertainment',
    'Lightricks': 'Media & Entertainment',
    'Fussball Club Cincinnati LLC ("FC Cincinnati")': 'Media & Entertainment',
    'LA28': 'Media & Entertainment',
    'LA28 (Web)': 'Media & Entertainment',
    'The Knot Worldwide': 'Media & Entertainment',
    'VEED.IO': 'Media & Entertainment',

    # ── Consumer & Social ────────────────────────────────────────────────────
    'Waymark': 'AI/ML',

    # ── EdTech ───────────────────────────────────────────────────────────────
    'ECC': 'EdTech',
    'JFF': 'EdTech',
    'Logos': 'EdTech',
    'Pursuit': 'EdTech',
    'Teachable': 'EdTech',
    'Toastmasters International': 'EdTech',
    'Understood': 'EdTech',
    'Yousician': 'EdTech',

    # ── AI/ML ─────────────────────────────────────────────────────────────────
    'Thinking Machines Lab': 'AI/ML',
    'Suno': 'AI/ML',
    'Unframe': 'AI/ML',

    # ── SpaceTech ────────────────────────────────────────────────────────────
    'Interstellar Lab': 'SpaceTech',

    # ── Logistics & Supply Chain ─────────────────────────────────────────────
    'RigUp': 'Logistics & Supply Chain',
    'Saltbox': 'Logistics & Supply Chain',
}

app = create_app()
with app.app_context():
    updated = 0
    not_found = []
    for name, industry in OVERRIDES.items():
        n = db.session.execute(
            text('UPDATE companies SET industry=:ind WHERE name=:nm AND is_active=true AND (industry IS NULL OR industry=\'Other\')'),
            {'ind': industry, 'nm': name}
        ).rowcount
        if n == 0:
            # Try without the Other constraint in case it already has a canonical label worth keeping
            existing = db.session.execute(text('SELECT industry FROM companies WHERE name=:nm AND is_active=true'), {'nm': name}).fetchone()
            if not existing:
                not_found.append(name)
        else:
            print(f'  {name:<50} → {industry}')
            updated += n

    if APPLY:
        db.session.commit()
        print(f'\nApplied: {updated} companies')
    else:
        db.session.rollback()
        print(f'\nWould update: {updated} companies')

    if not_found:
        print(f'Not found ({len(not_found)}): {", ".join(not_found[:20])}')
    if not APPLY:
        print('Re-run with --apply to write.')
