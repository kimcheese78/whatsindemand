"""Bulk-process unmatched_titles: map to canonical roles, create new roles, or reject.

Key design: EXPLICIT_MAPS uses canonical role TITLES (not IDs). IDs are
resolved at runtime from the DB, so this survives migrations and backfills.

Strategy:
  1. Auto-reject non-English, noise, seasonal, intern, volunteer titles
  2. Hard-coded explicit patterns (substring match, case-insensitive)
  3. Exact normalized match against canonical role titles
  4. Candidate starts with a canonical title (prefix match)
  5. Canonical title is contained in the candidate (contains match)
  6. New-role patterns for meaningful clusters without an existing canonical

Writes backend/data/role_mapping_decisions.json.
Apply with:  python scripts/apply_role_mappings_v2.py [--apply]

Usage:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/map_role_candidates.py
"""
import json, os, re, sys
from collections import defaultdict

# Pass DATABASE_URL as an env var — see CLAUDE.md for the prod DSN.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import create_app
from app.models import db

app = create_app()
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

# ─── Suffixes to strip before fuzzy matching ────────────────────────────────
_STRIP_SUFFIXES = re.compile(
    r'\s*[-–(,|]\s*'
    r'(?:remote|hybrid|onsite|on.?site|part.?time|full.?time|bilingual|'
    r'contract|temp|temporary|seasonal|part time|ft|pt|'
    r'prn\b|per diem\b|'
    r'i+v?|ii|iii|senior|sr\.?|jr\.?|associate|staff|lead|principal|'
    r'sign.?on bonus.*|\$[\d,k]+.*|with.*bonus.*|'
    r'[a-z]{2,}\s+region.*|'
    r'[a-z\s]+\d{4}.*'
    r').*$',
    re.IGNORECASE
)
_PARENS = re.compile(r'\s*\([^)]*\)\s*')
# Strip embedded salary/rate expressions like "$20.00" "$1.5k" "OTE $5k" from anywhere
_SALARY_INLINE = re.compile(r'\s*[-–|,]?\s*(?:OTE\s*)?\$[\d,.]+[k+]?.*$', re.IGNORECASE)

# ─── Auto-reject keywords ────────────────────────────────────────────────────
_REJECT_KEYWORDS = [
    ' intern ', 'intern,', 'intern-', 'internship',
    'volunteer', 'frivillig',
    'conference', 'networking night',
    'submit your application', 'future consideration',
    'werkstudent', 'praktikum', 'alternance', 'stagiaire', 'assessoria',
    'repartidor', 'teamleiter', 'psychologe', 'logistik', 'aufgaben',
    'elektroniker', 'industriemechaniker', 'locatiemanager',
    'requerimiento', 'medio tiempo', 'bono garantizado', 'tiempo completo',
    'descrizione', 'mansioni', 'requisiti', 'offerta', 'diseñador',
    'ambassador program',
    'seasonal property',
    'summer networking',
    'casting call', 'audition',
    'ea test', 'most questions',
    'event coordinator volunteer',
    'become a ', 'biochef',   # "Become a BioChef" etc.
    'graduate program',       # graduate rotational programs
    'future leaders',
    'founding partner',       # VC founding partner postings
    'entrepreneur in residence',
    'tour conductor',         # travel guide postings
]

# ─── Explicit pattern → canonical role title mappings ─────────────────────────
# Format: (canonical_role_title, [patterns])
# Patterns are case-insensitive substring matches.
# IMPORTANT: Use the exact normalized_title from the roles table.
# Role IDs are resolved at runtime — no hardcoded IDs here.
EXPLICIT_MAPS: list[tuple[str, list[str]]] = [

    # ── Healthcare: Behavioral Health ─────────────────────────────────────────
    ('Mental Health Therapist', [
        'psychotherapist', 'psychotherapists',
        'lcsw', 'lmft', 'licensed marriage and family',
        'licensed clinical social worker',
        'licensed professional counselor', 'lpc,', 'lpc-', ' lpc ',
        'mental health counselor', 'behavioral health counselor',
        'substance abuse counselor', 'addiction counselor',
        'clinical counselor', 'grief counselor',
        'trauma therapist', 'play therapist', 'art therapist',
        'teletherapist', 'telehealth therapist',
        'outpatient therapist', 'clinical therapist',
        'mental health clinician', 'per diem therapist',
        'school-based therapist', 'school based therapist',
        'behavioral health therapist',
        'child and adolescent therapist',
        'mental health clinician',
        'licensed school-based mental health',
    ]),
    ('Clinical Psychologist', [
        'licensed psychologist', 'clinical psychologist',
        'school psychologist', 'forensic psychologist', 'health psychologist',
        'psychologist',  # standalone "Psychologist" title
    ]),
    ('Testing Psychologist', [
        'testing psychologist', 'neuropsychologist', 'psychometrician',
    ]),
    ('Psychiatrist', [
        'psychiatrist', 'child psychiatrist', 'forensic psychiatrist',
        'geriatric psychiatrist',
    ]),
    ('Behavioral Specialist', [
        'behavioral specialist', 'behavior technician', 'behavior analyst',
        'aba therapist', 'rbt,', 'rbt ', 'bcba,', 'bcba ',
        'applied behavior', 'behavioral intervention',
        'behavioral health specialist',
    ]),
    ('Direct Support Professional', [
        'direct support professional', ' dsp ', 'direct care',
        'residential support', 'developmental disability', 'group home staff',
        'community support worker', 'behavioral support specialist',
        'residential rehabilitation educator', 'rehab educator',
        'rehabilitation educator',
    ]),

    # ── Healthcare: Nursing ──────────────────────────────────────────────────
    ('Registered Nurse', [
        'registered nurse', ' rn ', 'rn,', 'rn-',
        'staff nurse', 'charge nurse',
        'travel nurse', 'per diem nurse', 'float nurse', 'icu nurse',
        'er nurse', 'ed nurse', 'med surg nurse', 'telemetry nurse',
        'oncology nurse', 'labor and delivery nurse', 'postpartum nurse',
        'nicu nurse', 'picu nurse', 'pacu nurse', 'or nurse',
        'pre-op nurse', 'home health rn', 'hospice rn',
        'clinic nurse', 'infusion nurse', 'float pool rn',
        'float pool certified nursing assistant',  # catch-all for float pool
        'senior living',  # "Registered Nurse - Senior Living"
    ]),
    ('Licensed Practical Nurse', [
        'licensed practical nurse', ' lpn ', 'lpn ', 'lpn,', 'lpn-',
        'licensed vocational nurse', ' lvn ', 'lvn,', 'lvn-',
    ]),
    ('Certified Nursing Assistant', [
        'certified nursing assistant', ' cna ', 'cna,', 'cna-',
        'nursing assistant', 'patient care technician',
        'patient care assistant', 'pct,', 'pct ', 'care aide', 'nurse aide',
    ]),
    ('Nurse Midwife', [
        'nurse midwife', 'certified nurse midwife', 'cnm ',
    ]),

    # ── Healthcare: Clinical ─────────────────────────────────────────────────
    ('Medical Assistant', [
        'medical assistant', 'clinical assistant', 'healthcare assistant',
        'patient services assistant', 'ophthalmic assistant',
    ]),
    ('Medical Scribe', [
        'medical scribe', 'clinical scribe', 'physician scribe', 'er scribe',
    ]),
    ('Phlebotomist', [
        'phlebotomist', 'phlebotomy technician', 'blood draw',
    ]),
    ('Radiologic Technologist', [
        'radiologic technologist', 'radiology tech', 'x-ray tech',
        'ct technologist', 'mri technologist', 'ultrasound tech',
        'sonographer', 'mammography tech', 'nuclear medicine tech',
    ]),
    ('Surgical Technologist', [
        'surgical tech', 'surgical first assist',
        'operating room tech', 'scrub tech',
        'surgical preservationist', 'surgical assist',
    ]),

    # ── Healthcare: Rehabilitation ───────────────────────────────────────────
    ('Physical Therapist', [
        'physical therapist', 'physiotherapist',
    ]),
    ('Occupational Therapist', [
        'occupational therapist', 'certified occupational therapy assistant',
        'cota ', 'ota ',
    ]),
    ('Speech-Language Pathologist', [
        'speech-language pathologist', 'speech therapist', 'slp,', ' slp ',
        'speech language', 'language pathologist',
    ]),

    # ── Healthcare: Dental ───────────────────────────────────────────────────
    ('Dental Hygienist', [
        'dental hygienist', 'registered dental hygienist', 'rdh ',
    ]),
    ('Dental Assistant', [
        'dental assistant', 'chairside assistant', 'orthodontic assistant',
    ]),
    ('Dentist', [
        'dentist', 'general dentist', 'associate dentist',
    ]),

    # ── Healthcare: Pharmacy ─────────────────────────────────────────────────
    ('Pharmacist', [
        'pharmacist', 'clinical pharmacist', 'retail pharmacist',
        'hospital pharmacist', 'staff pharmacist',
    ]),
    ('Pharmacy Technician', [
        'pharmacy technician', 'pharmacy tech', 'pharm tech',
    ]),

    # ── Healthcare: Specialty ────────────────────────────────────────────────
    ('Dermatologist', [
        'dermatologist', 'mohs surgeon', 'cosmetic dermatologist',
    ]),
    ('Obstetrician/Gynecologist', [
        'obstetrician', 'gynecologist', 'ob/gyn', 'obstetrics',
    ]),
    ('Pediatrician', [
        'pediatrician', 'child health physician',
    ]),
    ('Podiatrist', [
        'podiatrist', 'foot and ankle', 'dpm,', 'dpm ',
    ]),
    ('Optometrist', [
        'optometrist', 'doctor of optometry', ' od,', ' od ',
    ]),
    ('Respiratory Therapist', [
        'respiratory therapist', 'respiratory care practitioner', 'rrt ', 'crt ',
    ]),
    ('Veterinarian', [
        'veterinarian', 'veterinary doctor', 'dvm,', 'dvm ',
        'associate veterinarian', 'emergency veterinarian',
        'relief veterinarian', 'veterinary internist',
        'veterinary specialist', 'veterinary surgeon',
    ]),
    ('Veterinary Technician', [
        'veterinary technician', 'vet tech', 'veterinary assistant',
        'vet assistant', 'animal technician', 'veterinary nurse',
    ]),

    # ── Healthcare: Home & Social Services ───────────────────────────────────
    ('Caregiver', [
        'caregiver', 'personal care', 'home care aide', 'companion care',
        'senior care', 'elder care', 'in-home care', 'assisted living aide',
    ]),
    ('Home Health Aide', [
        'home health aide', 'hhc,', 'hhc ', 'home care specialist',
    ]),
    ('Hospice Aide', [
        'hospice aide', 'hospice caregiver', 'end of life care aide', 'prn hospice',
    ]),
    ('Social Worker', [
        'social worker', 'case manager', 'case worker', 'care coordinator',
        'care manager', 'patient navigator', 'health navigator',
        'community health worker', 'community outreach worker',
        'community guide', 'health coach', 'wellness coach',
        'life skills coach', 'life skills specialist',
        'rehab counselor', 'vocational counselor', 'disability specialist',
        'relief counselor', 'juvenile justice', 'juvenile counselor',
        'patient advocate',
    ]),

    # ── Healthcare: Administrative ───────────────────────────────────────────
    ('Medical Coder', [
        'medical coder', 'medical billing', 'health information coder',
    ]),
    ('Nurse Care Manager', [
        'nurse care manager', 'care management nurse', 'utilization management nurse',
    ]),

    # ── Food Service ─────────────────────────────────────────────────────────
    ('Server', [
        'food server', 'banquet server', 'fine dining server',
        'restaurant server', 'table server', 'cocktail server',
        'bus person', 'busser', 'bus boy', 'busgirl', 'busperson',
    ]),
    ('Line Cook', [
        'line cook', 'deli cook', 'prep cook', 'short order cook',
        'grill cook', 'fry cook', 'saute cook', 'breakfast cook',
        'line chef', 'grill chef', 'station cook', 'prep chef',
        'kitchen prep', 'food prep cook',
    ]),
    ('Chef', [
        'executive chef', 'sous chef', 'head chef', 'pastry chef',
        'catering chef', 'banquet chef', 'private chef',
    ]),
    ('Dishwasher', [
        'dishwasher', 'dish washer', 'kitchen utility', 'dish room',
    ]),
    ('Host', [
        'hostess', 'restaurant host', 'dining host',
        'host/hostess',
    ]),
    ('Barista', [
        'barista', 'coffee specialist', 'espresso bar',
    ]),
    ('Bartender', [
        'bartender', 'bar back', 'barback', 'mixologist',
    ]),
    ('Restaurant Manager', [
        'restaurant manager', 'food service manager', 'dining manager',
        'kitchen manager', 'bar manager', 'general manager, food',
        'f&b manager', 'food and beverage manager',
    ]),

    # ── Retail / Hospitality ─────────────────────────────────────────────────
    ('Store Associate', [
        'store associate', 'retail associate', 'floor associate',
        'merchandising associate', 'stock associate',
        'floor staff', 'floor team', 'retail team member', 'retail staff',
        'store team member', 'grocery merchandiser', 'merchandiser',
        'grocery clerk', 'retail clerk', 'stock clerk', 'shelf stocker',
        'inventory associate', 'produce associate',
        'bilingual grocery',
    ]),
    ('Retail Store Manager', [
        'store manager', 'retail manager', 'shop manager', 'boutique manager',
        'district manager', 'area retail manager', 'general manager, retail',
    ]),
    ('Cashier', [
        'cashier', 'checkout associate', 'front end associate',
        'register operator',
    ]),
    ('Brand Ambassador', [
        'brand ambassador', 'product demonstrator', 'brand rep',
        'brand specialist', 'event ambassador',
        'promo ambassador', 'part-time ambassador', 'part time ambassador',
    ]),
    ('Housekeeper', [
        'housekeeper', 'housekeeping', 'room attendant', 'laundry attendant',
    ]),
    ('Porter', [
        'bellhop', 'bellman', 'bell attendant', 'valet attendant',
    ]),
    ('Cosmetologist', [
        'cosmetologist', 'hair stylist', 'hairstylist', 'colorist',
        'esthetician', 'nail technician', 'nail tech', 'waxing specialist',
        'skin care specialist', 'lash tech', 'lash artist', 'massage therapist',
    ]),
    ('Store Advisor', [
        'store advisor', 'retail advisor', 'beauty advisor',
    ]),
    ('Shift Supervisor', [
        'shift supervisor', 'shift lead', 'shift manager', 'team lead,',
        'floor supervisor', 'key holder', 'key-holder',
    ]),

    # ── Operations & Trades ──────────────────────────────────────────────────
    ('Delivery Driver', [
        'delivery driver', 'delivery associate', 'courier', 'food delivery',
        'package delivery', 'last mile delivery', 'route driver',
    ]),
    ('Truck Driver', [
        'truck driver', 'cdl driver', 'class a driver', 'class b driver',
        'semi driver', 'flatbed driver', 'otr driver', 'cdl-a',
    ]),
    ('Flight Attendant', [
        'flight attendant', 'cabin crew', 'cabin attendant',
    ]),
    ('Warehouse Associate', [
        'warehouse associate', 'warehouse worker', 'warehouse operator',
        'distribution associate', 'dc associate',
        'forklift operator', 'picker packer', 'order picker',
        'order fulfillment', 'distribution operations',
        'parts assistant', 'parts associate', 'parts clerk',
        'general laborer', 'general helper', 'laborer/helper',
    ]),
    ('Manufacturing Technician', [
        'manufacturing technician', 'production technician',
        'assembly technician', 'production operator', 'machine operator',
        'cnc operator',
    ]),
    ('Maintenance Technician', [
        'maintenance technician', 'maintenance tech', 'facilities technician',
        'facilities tech', 'building technician', 'maintenance worker',
        'maintenance specialist', 'janitor', 'custodian',
        'facilities specialist', 'pool attendant', 'pool technician',
        'property caretaker', 'property maintenance', 'estate caretaker',
    ]),
    ('Field Service Technician', [
        'field service technician', 'field technician', 'service technician',
        'field tech', 'installation technician', 'hvac technician',
        'elevator technician', 'elevator mechanic',
        'refrigeration technician', 'telematics', 'fleet installer',
        'gps installer', 'installation specialist', 'field installer',
        'low voltage technician', 'av technician', 'audio visual tech',
        'fire protection', 'sprinkler fitter', 'general contractor - home',
    ]),
    ('Machinist', [
        'machinist', 'cnc machinist', 'mill operator', 'lathe operator',
        'tool and die maker', 'precision machinist',
    ]),
    ('Electrician', [
        'electrician', 'electrical technician', 'journeyman electrician',
        'master electrician', 'electrical helper',
    ]),
    ('Field Service Technician', [  # duplicate intentional: plumber also field service
        'plumber', 'pipefitter',
    ]),
    ('Landscape Technician', [
        'landscape technician', 'landscaper', 'groundskeeper', 'groundsman',
        'lawn care', 'arborist', 'tree trimmer', 'irrigation technician',
    ]),
    ('Dispatcher', [
        'dispatcher', 'fleet dispatcher', 'transportation coordinator',
        'freight coordinator',
    ]),
    ('Estimator', [
        'estimator', 'cost estimator', 'construction estimator',
        'bid estimator', 'takeoff specialist',
    ]),
    ('Superintendent', [
        'construction superintendent', 'site superintendent',
        'project superintendent', 'foreman', 'job site supervisor',
        'general contractor', 'grade setter', 'construction manager',
        'site manager',
    ]),
    ('Inspector', [
        'quality inspector', 'building inspector',
        'home inspector', 'code inspector',
    ]),
    ('Surveyor', [
        'surveyor', 'land surveyor', 'survey technician', 'geomatics',
    ]),
    ('Diesel Mechanic', [
        'diesel mechanic', 'heavy equipment mechanic', 'equipment mechanic',
        'truck mechanic', 'automotive mechanic', 'auto mechanic',
    ]),

    # ── Engineering ──────────────────────────────────────────────────────────
    ('Software Engineer', [
        'software engineer', 'software developer', 'swe,', 'swe ',
        'backend engineer', 'frontend engineer', 'full.?stack engineer',
        'fullstack engineer', 'full stack engineer', 'web developer',
        'web engineer', 'application developer', 'application engineer',
    ]),
    ('Machine Learning Engineer', [
        'machine learning engineer', 'ml engineer', 'mle,', 'mle ',
        'ai/ml engineer', 'nlp engineer', 'computer vision engineer',
    ]),
    ('AI Engineer', [
        'ai engineer', 'ai developer', 'ai software engineer',
        'generative ai engineer', 'llm engineer', 'genai engineer',
    ]),
    ('Security Engineer', [
        'security engineer', 'cybersecurity engineer',
        'appsec engineer', 'network security engineer',
    ]),
    ('QA Engineer', [
        'sdet', 'software development engineer in test',
        'software engineer in test', 'quality engineer',
        'automation engineer', 'qa automation engineer',
        'director of quality',
    ]),
    ('Solutions Architect', [
        'principal solution architect', 'principal solutions architect',
        'enterprise architect', 'cloud architect',
        'staff solutions architect', 'distinguished engineer',
    ]),

    # ── Sales ─────────────────────────────────────────────────────────────────
    ('Account Executive', [
        'account executive', 'ae,', ' ae ', 'quota-carrying',
        'closing rep', 'sales closer', 'inbound sales closer',
        'remote closer', 'high ticket closer', 'client executive',
        'commercial insurance executive', 'insurance executive',
        'benefits executive', 'insurance sales executive',
        'commercial account executive', 'ownership advisor',
    ]),
    ('Business Development Manager', [
        'business development director', 'director of client relations',
        'director of business development', 'client relations director',
        'director of partnerships', 'head of business development',
        'vp of business development', 'head of bd',
    ]),
    ('Business Development Representative', [
        'business development rep', 'bdr,', ' bdr ', 'outbound bdr',
        'inbound bdr', 'allbound bdr', 'allbound sdr',
    ]),
    ('Sales Development Representative', [
        ' sdr ', 'sdr,',
    ]),
    ('Sales Manager', [
        'director of field sales', 'vp of sales', 'vp sales',
        'director of sales', 'head of sales', 'sales director',
        'regional sales manager', 'area sales manager',
        'enterprise sales leader',
    ]),

    # ── Marketing ────────────────────────────────────────────────────────────
    ('Marketing Manager', [
        'director of demand generation', 'demand gen director',
        'director of marketing', 'head of marketing',
        'vp of marketing', 'vp marketing',
        'director of pricing', 'director of growth',
    ]),
    ('Demand Generation Manager', [
        'director of demand generation', 'demand generation manager',
        'demand gen manager',
    ]),
    ('Content Marketing Manager', [
        'senior content strategist',
    ]),
    ('Field Marketing Manager', [
        'field market development', 'field marketing', 'regional marketing',
        'territory marketing', 'market development manager',
    ]),
    ('Journalist', [
        'anchor', 'news anchor', 'tv anchor', 'broadcast journalist',
        'reporter', 'correspondent', 'photojournalist',
        'copy editor', 'news editor', 'msj ',
    ]),

    # ── Operations Management ─────────────────────────────────────────────────
    ('Operations Manager', [
        'operations manager', 'ops manager', 'operations lead',
        'operational manager', 'line manager', 'operations director',
        'distribution operations', 'general operations',
    ]),
    ('Area Manager', [
        'regional manager, affordable housing', 'regional manager,',
        'area manager',
    ]),
    ('Project Manager', [
        'project manager', ' pm,', 'project lead', 'project coordinator',
        'project management professional', 'project scheduler',
        'scheduling manager', 'planning manager', 'project planner',
        'construction scheduler',
    ]),
    ('Program Manager', [
        'program manager', 'pgm,', 'pgm ', 'technical program coordinator',
        'delivery excellence manager',
    ]),
    ('Leasing Consultant', [
        'leasing consultant', 'leasing agent', 'property leasing',
        'apartment leasing', 'rental agent', 'leasing specialist',
    ]),
    ('Maintenance Technician', [  # duplicate: property management also maintenance
        'property manager', 'facilities manager',
    ]),

    # ── Finance ──────────────────────────────────────────────────────────────
    ('Trader', [
        'quantitative trader', 'quant trader', 'algorithmic trader',
        'equity trader', 'fixed income trader', 'derivatives trader',
        'options trader', 'prop trader', 'market maker',
        'experienced quant', 'quantitative researcher',
    ]),

    # ── Legal ────────────────────────────────────────────────────────────────
    ('Attorney', [
        'immigration attorney', 'immigration lawyer', 'criminal attorney',
        'family attorney', 'employment attorney', 'real estate attorney',
        'corporate attorney', 'litigation attorney', 'tax attorney',
        'patent attorney', 'intellectual property attorney',
        'defense attorney', 'prosecuting attorney', 'public defender',
    ]),
    ('Paralegal', [
        'paralegal', 'legal assistant', 'legal associate',
        'legal coordinator', 'legal secretary',
    ]),

    # ── People / HR ───────────────────────────────────────────────────────────
    ('Director of People', [
        'director of human resources', 'director of people',
        'vp of people', 'vp people', 'chief people officer',
        'cpo,', 'cpo ', 'head of people', 'head of hr',
        'vp hr', 'vp of hr',
    ]),
    ('Recruiter', [
        'recruiter', 'talent acquisition partner', 'talent partner',
        'sourcing specialist', 'recruiting coordinator', 'hr recruiter',
    ]),
    ('Talent Acquisition Specialist', [
        'talent acquisition specialist', 'talent specialist',
        'recruitment specialist', 'staffing specialist',
        'staffing coordinator',
    ]),
    ('HR Generalist', [
        'hr generalist', 'human resources generalist', 'people generalist',
        'hr coordinator', 'hr specialist', 'hr advisor',
    ]),
    ('People Operations Specialist', [
        'member of people operations', 'training facilitator, trust',
    ]),

    # ── IT & Admin ────────────────────────────────────────────────────────────
    ('IT Support Engineer', [
        'it support', 'helpdesk', 'help desk', 'desktop support',
        'it technician', 'it specialist', 'technical support specialist',
        'tier 1 support', 'tier 2 support', 'service desk analyst',
        'it services team lead',
    ]),
    ('Business Systems Analyst', [
        'business applications', 'business systems',
        'erp analyst', 'crm analyst', 'business application',
        'enterprise systems analyst',
    ]),

    # ── Design ───────────────────────────────────────────────────────────────
    ('Motion Designer', [
        'vfx artist', 'visual effects artist', 'motion graphics artist',
        'animator', '3d artist', 'cg artist',
    ]),

    # ── Education ────────────────────────────────────────────────────────────
    ('Teacher', [
        'classroom teacher', 'substitute teacher',
        'adjunct instructor', 'adjunct professor',
        'assistant professor', 'associate professor', 'professor ',
        'faculty member', 'lecturer', 'school tutor',
        'k-12 instructor', 'academic instructor', 'school educator',
        'electrical instructor',  # technical trade instructor
        'aircraft maintenance instructor', 'amt instructor',
        'a&p mechanic instructor',
    ]),

    # ── Partnerships ─────────────────────────────────────────────────────────
    ('Partner Manager', [
        'venture scout', 'investment scout', 'vc scout', 'startup scout',
        'partner - client',
    ]),

    # ── Compliance ───────────────────────────────────────────────────────────
    ('Compliance Specialist', [
        'compliance specialist', 'compliance analyst', 'compliance officer',
        'regulatory specialist', 'compliance coordinator',
    ]),

    # ── Support ───────────────────────────────────────────────────────────────
    ('Support Specialist', [
        'customer solutions', 'customer support advocate',
    ]),

    # ── Data / Analytics ─────────────────────────────────────────────────────
    ('Data Analyst', [
        'data management and bi', 'bi senior', 'bi analyst',
    ]),

    # ── Marketing / Content (executive titles with clear function) ────────────
    ('Content Marketing Manager', [
        'executive content planning', 'content executive', 'content planning',
    ]),

    # ── Operations (generic "executive" titles with planning/ops function) ─────
    ('Operations Manager', [
        'executive, planning', 'executive - planning', 'executive planning',
        'executive - cross channel', 'executive - digital',
        'senior executive, media planning', 'senior executive, media',
    ]),

    # ── Consulting / Strategy ──────────────────────────────────────────────────
    ('Solutions Consultant', [
        'senior consulting director', 'consulting commercial leader',
        'senior consultant, strategy',
        'implementation & activation executive',
    ]),

    # ── Finance — Actuary ─────────────────────────────────────────────────────
    ('Actuary', [
        'actuar',  # matches actuary, actuarial, actuary manager, etc.
    ]),

    # ── Engineering — Security ────────────────────────────────────────────────
    ('Information Security Engineer', [
        'director of information security', 'head of information security',
        'vp of information security', 'ciso',
        'information security officer',
    ]),
    ('Security Engineer', [
        'director of security engineering', 'head of security engineering',
    ]),

    # ── IT ────────────────────────────────────────────────────────────────────
    ('Salesforce Administrator', [
        'salesforce admin', 'junior salesforce',
    ]),
    ('Systems Administrator', [
        'director of information technology', 'director of it',
        'head of it', 'vp of it', 'senior director of information technology',
    ]),

    # ── Engineering — Software ────────────────────────────────────────────────
    ('Software Engineer', [
        'engine programmer', 'gameplay programmer', 'graphics programmer',
        'game programmer',
    ]),

    # ── Veterinary specialty → Veterinarian ──────────────────────────────────
    ('Veterinarian', [
        'veterinary criticalist', 'veterinary cardiologist',
        'veterinary neurologist', 'veterinary oncologist',
        'veterinary radiologist', 'veterinary dermatologist',
    ]),
]

# ─── New canonical roles for meaningful clusters ────────────────────────���─────
NEW_ROLES = [
    {
        'normalized_title': 'Aviation Mechanic',
        'category': 'Operations',
        'job_family': 'Trades',
        'seniority_level': None,
        'patterns': ["a&p mechanic", 'amt instructor', 'aircraft mechanic',
                     'aviation mechanic', 'airframe mechanic', 'powerplant mechanic',
                     'avionics technician'],
        'reason': '~200 jobs across A&P / AMT / avionics cluster',
    },
    {
        'normalized_title': 'Budtender',
        'category': 'Retail / Hospitality',
        'job_family': 'Retail Floor',
        'seniority_level': None,
        'patterns': ['budtender', 'cannabis retail', 'dispensary associate',
                     'cannabis associate', 'cannabis consultant'],
        'reason': '~100 jobs, cannabis-specific retail role',
    },
    {
        'normalized_title': 'Stylist',
        'category': 'Retail / Hospitality',
        'job_family': 'Beauty & Wellness',
        'seniority_level': None,
        'patterns': ['retail stylist', 'wardrobe stylist', 'fashion stylist',
                     'personal stylist', 'stylist (retail)', 'stylist, retail'],
        'reason': '~100 jobs, distinct from Cosmetologist',
    },
    {
        'normalized_title': 'Meteorologist',
        'category': 'Engineering',
        'job_family': 'Sciences',
        'seniority_level': None,
        'patterns': ['meteorologist', 'atmospheric scientist', 'weather forecaster',
                     'climatologist'],
        'reason': '~80 jobs, scientific role with no canonical',
    },
    {
        'normalized_title': 'Intelligence Analyst',
        'category': 'Engineering',
        'job_family': 'Defense & Intelligence',
        'seniority_level': None,
        'patterns': ['intelligence analyst', 'intelligence officer',
                     'intelligence operations', 'geospatial analyst',
                     'signals analyst', 'imagery analyst', 'all-source analyst',
                     'collection manager', 'intelligence operations integrator'],
        'reason': 'Defense/government intelligence cluster, ~50 jobs',
    },
    {
        'normalized_title': 'Security Officer',
        'category': 'Operations',
        'job_family': 'Security',
        'seniority_level': None,
        'patterns': ['security officer', 'security guard', 'loss prevention officer',
                     'loss prevention associate', 'security associate',
                     'part time security'],
        'reason': 'Physical security / guard roles, distinct from Security Engineer',
    },
    {
        'normalized_title': 'Logistics Coordinator',
        'category': 'Operations',
        'job_family': 'Logistics',
        'seniority_level': None,
        'patterns': ['logistics coordinator', 'logistics specialist',
                     'logistics manager', 'supply chain coordinator',
                     'international freight', 'freight forwarding',
                     'import coordinator', 'export coordinator'],
        'reason': 'Logistics coordinator cluster — not field dispatch (Dispatcher)',
    },
    {
        'normalized_title': 'Fitness Instructor',
        'category': 'Retail / Hospitality',
        'job_family': 'Health & Wellness',
        'seniority_level': None,
        'patterns': ['fitness instructor', 'personal trainer', 'group fitness',
                     'pilates instructor', 'yoga instructor', 'spin instructor',
                     'cycling instructor', 'strength coach', 'athletic trainer',
                     'sports trainer'],
        'reason': '~40 jobs, fitness/wellness instructors distinct from cosmetologist',
    },
    {
        'normalized_title': 'Registered Dietitian',
        'category': 'Healthcare',
        'job_family': 'Clinical Nutrition',
        'seniority_level': None,
        'patterns': ['registered dietitian', 'dietitian', 'dietician',
                     'clinical nutritionist', 'nutrition counselor'],
        'reason': 'Licensed clinical nutrition role with no canonical',
    },
]


def _is_english(title: str) -> bool:
    ascii_ratio = sum(1 for c in title if ord(c) < 128) / max(len(title), 1)
    return ascii_ratio >= 0.85


def _normalize(title: str) -> str:
    t = _SALARY_INLINE.sub('', title)
    t = _PARENS.sub(' ', t)
    t = _STRIP_SUFFIXES.sub('', t)
    return t.strip().lower()


def _should_reject(title: str) -> str | None:
    if not _is_english(title):
        return 'non-english'
    tl = title.lower()
    # Word-boundary intern check catches "Design Intern", "Sales Intern", etc.
    if re.search(r'\bintern\b', tl):
        return 'intern'
    for kw in _REJECT_KEYWORDS:
        if kw in tl:
            return f'noise: {kw.strip()}'
    if len(title.strip()) < 4:
        return 'too short'
    # Reject obvious non-job postings
    if re.search(r'\bfrivillig\b|\bstagiaire\b|\bpraktikum\b|\bwerkstudent\b', tl):
        return 'non-english/intern'
    return None


def build_explicit_lookup(roles_by_title: dict[str, int]) -> dict[str, int]:
    """Build pattern → role_id lookup. Resolves role IDs by title at runtime."""
    lookup: dict[str, int] = {}
    missing: list[str] = []
    for role_title, patterns in EXPLICIT_MAPS:
        role_id = roles_by_title.get(role_title.lower())
        if role_id is None:
            if role_title not in missing:
                missing.append(role_title)
            continue
        for pat in patterns:
            pat_l = pat.lower()
            if pat_l not in lookup:
                lookup[pat_l] = role_id
    if missing:
        print(f'  Warning: {len(missing)} canonical titles not found in DB:')
        for t in missing:
            print(f'    - {t!r}')
    return lookup


def match_candidate(title: str, roles_norm: dict, explicit_lookup: dict) -> int | None:
    title_l = title.lower()
    title_n = _normalize(title)

    # 1. Explicit substring patterns (highest priority)
    for pat, role_id in explicit_lookup.items():
        if pat in title_l:
            return role_id

    # 2. Exact normalized match
    if title_n in roles_norm:
        return roles_norm[title_n]

    # 3. Candidate starts with a canonical title (min 8 chars)
    for role_title_n, role_id in roles_norm.items():
        if len(role_title_n) >= 8 and title_n.startswith(role_title_n):
            return role_id

    # 4. Canonical title is a substring of the candidate (min 10 chars)
    for role_title_n, role_id in roles_norm.items():
        if len(role_title_n) >= 10 and role_title_n in title_n:
            return role_id

    return None


def run():
    with app.app_context():
        roles = db.session.execute(db.text(
            'SELECT id, normalized_title FROM roles ORDER BY total_active_jobs DESC'
        )).fetchall()
        roles_by_id = {r.id: r.normalized_title for r in roles}
        roles_by_title = {r.normalized_title.lower(): r.id for r in roles}
        roles_norm = {_normalize(r.normalized_title): r.id for r in roles}

        candidates = db.session.execute(db.text(
            "SELECT id, raw_title, job_count FROM unmatched_titles "
            "WHERE status='pending' ORDER BY job_count DESC"
        )).fetchall()

    explicit_lookup = build_explicit_lookup(roles_by_title)

    # New-role pattern lookup
    new_role_lookup: dict[str, str] = {}
    for nr in NEW_ROLES:
        for pat in nr['patterns']:
            if pat.lower() not in new_role_lookup:
                new_role_lookup[pat.lower()] = nr['normalized_title']

    decisions: dict[str, list] = {'map': [], 'new_role': [], 'reject': [], 'skip': []}

    for cand in candidates:
        cid, title, jobs = cand.id, cand.raw_title, cand.job_count

        reject_reason = _should_reject(title)
        if reject_reason:
            decisions['reject'].append({'candidate_id': cid, 'title': title,
                                        'jobs': jobs, 'reason': reject_reason})
            continue

        title_l = title.lower()

        # Check new-role patterns before explicit (more specific wins)
        matched_new_role = next(
            (nr_title for pat, nr_title in new_role_lookup.items() if pat in title_l),
            None
        )
        if matched_new_role:
            decisions['new_role'].append({'candidate_id': cid, 'title': title,
                                          'jobs': jobs, 'new_role_title': matched_new_role})
            continue

        role_id = match_candidate(title, roles_norm, explicit_lookup)
        if role_id:
            decisions['map'].append({'candidate_id': cid, 'title': title,
                                     'jobs': jobs, 'role_id': role_id,
                                     'role_title': roles_by_id[role_id]})
            continue

        decisions['skip'].append({'candidate_id': cid, 'title': title, 'jobs': jobs})

    total = len(candidates)
    print(f'Processed {total:,} candidates:')
    print(f'  map:      {len(decisions["map"]):,}')
    print(f'  new_role: {len(decisions["new_role"]):,}')
    print(f'  reject:   {len(decisions["reject"]):,}')
    print(f'  skip:     {len(decisions["skip"]):,}')

    print(f'\nTop skipped (by job count):')
    for s in sorted(decisions['skip'], key=lambda x: -x['jobs'])[:50]:
        print(f'  {s["jobs"]:5d}  {s["title"]}')

    print(f'\nSample mappings (top 30):')
    for m in sorted(decisions['map'], key=lambda x: -x['jobs'])[:30]:
        print(f'  {m["jobs"]:5d}  {m["title"]!r}  →  {m["role_title"]!r}')

    print(f'\nNew roles:')
    by_new: dict[str, list] = defaultdict(list)
    for n in decisions['new_role']:
        by_new[n['new_role_title']].append(n)
    for rt, items in sorted(by_new.items(), key=lambda x: -sum(i['jobs'] for i in x[1])):
        print(f'  {sum(i["jobs"] for i in items):5d} total  "{rt}"  ({len(items)} candidates)')

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, 'role_mapping_decisions.json')
    with open(out_path, 'w') as f:
        json.dump({
            'meta': {'total': total, 'map': len(decisions['map']),
                     'new_role': len(decisions['new_role']),
                     'reject': len(decisions['reject']),
                     'skip': len(decisions['skip'])},
            'new_role_definitions': NEW_ROLES,
            **decisions,
        }, f, indent=2)
    print(f'\nWrote {out_path}')


if __name__ == '__main__':
    run()
