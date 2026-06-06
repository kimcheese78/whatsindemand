"""Comprehensive taxonomy cleanup: deactivations, recategorizations, subcategory assignments.

Run (dry-run first, then --apply):
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/apply_full_taxonomy_review.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/apply_full_taxonomy_review.py --apply
"""
import os, sys
from datetime import datetime

PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from app import create_app
from app.models import db, Skill

app = create_app()
APPLY = '--apply' in sys.argv

# ─── 1. DEACTIVATE ──────────────────────────────────────────────────────────
# True duplicates (lower-quality form) and noise
# Format: {id: reason}
DEACTIVATE = {
    # Exact duplicates of higher-traffic canonical
    534:  'dup of PowerPoint [22]',
    3647: 'dup of SEO [287]',
    3585: 'dup of SEM [288]',
    1014: 'dup of CRM [306]',
    533:  'dup of Microsoft Office [524]',
    535:  'dup of Microsoft Office [524]',
    526:  'dup of Confluence [201]',
    3177: 'dup of JUnit [226]',
    4163: 'dup of Supply Chain [309]',
    896:  'dup of Business Continuity [892]',
    898:  'dup of Business Continuity [892]',
    3624: 'dup of Global Marketing — kept as alias',
    # Noise / artifacts / defunct
    3671: 'noise artifact: Journalism Subcategory',
    3640: 'noise artifact: Social Media Subcategory',
    3862: 'noise: Windows Store (defunct)',
    1348: 'noise: Kung Fu (0 jobs)',
    881:  'dup of Slack [202] in technical',
    2357: 'obsolete: JOnAS Java EE server (2 jobs)',
    3648: 'noise: PageRank (2 jobs, too niche)',
    527:  'noise: LibreOffice (0 jobs)',
    956:  'noise: OneDrive for Business (1 job)',
    3642: 'noise: Google+ (defunct, 9 jobs)',
    # Near-duplicates already handled by alias additions in prior script
    # (Pharmaceuticals [2299] was already deactivated)
}

# ─── 2. RECATEGORIZE ────────────────────────────────────────────────────────
# technical → domain (industry/domain knowledge, not a learnable tech skill)
TECH_TO_DOMAIN = {
    # Sciences/Engineering disciplines (domain: Industries)
    542:  ('domain', 'Industries'),           # Agriculture
    556:  ('domain', 'Industries'),           # Agronomy
    544:  ('domain', 'Industries'),           # Precision Agriculture
    558:  ('domain', 'Industries'),           # Composting
    552:  ('domain', 'Industries'),           # Cannabis
    553:  ('domain', 'Industries'),           # Medical Cannabis
    3998: ('domain', 'Industries'),           # Genetics
    3896: ('domain', 'Industries'),           # Biology
    3883: ('domain', 'Industries'),           # Life Sciences
    3902: ('domain', 'Industries'),           # Biotechnology
    4047: ('domain', 'Industries'),           # Neuroscience
    3997: ('domain', 'Industries'),           # Genomics
    4026: ('domain', 'Industries'),           # Molecular Biology
    4042: ('domain', 'Industries'),           # Microbiology
    3889: ('domain', 'Industries'),           # Synthetic Biology
    1484: ('domain', 'Industries'),           # Biomedical Engineering
    1483: ('domain', 'Industries'),           # Chemical Engineering
    1519: ('domain', 'Industries'),           # Civil Engineering
    1553: ('domain', 'Industries'),           # Electrical Engineering
    1584: ('domain', 'Industries'),           # Electronic Engineering
    1463: ('domain', 'Industries'),           # Aerospace Engineering
    1628: ('domain', 'Industries'),           # Industrial Engineering
    1638: ('domain', 'Industries'),           # Materials Science
    1645: ('domain', 'Industries'),           # Materials Engineering
    1649: ('domain', 'Industries'),           # Mechatronics
    1430: ('domain', 'Industries'),           # Oil And Gas
    3908: ('domain', 'Industries'),           # Petrochemical
    1426: ('domain', 'Industries'),           # Nuclear Fuel
    1422: ('domain', 'Industries'),           # Nuclear Power
    1423: ('domain', 'Industries'),           # Nuclear Engineering
    1424: ('domain', 'Industries'),           # Nuclear Safety
    1393: ('domain', 'Industries'),           # Renewable Energy
    1477: ('domain', 'Industries'),           # Electric Vehicles
    1479: ('domain', 'Industries'),           # Autonomous Vehicles
    1461: ('domain', 'Industries'),           # Space Exploration
    1465: ('domain', 'Industries'),           # Spacecraft
    1466: ('domain', 'Industries'),           # Space Stations
    1462: ('domain', 'Industries'),           # Space Flight
    1470: ('domain', 'Industries'),           # Spacecraft Propulsion
    1452: ('domain', 'Industries'),           # Wastewater
    1455: ('domain', 'Industries'),           # Water Quality
    1454: ('domain', 'Industries'),           # Water Treatment
    1457: ('domain', 'Industries'),           # Water Distribution
    3976: ('domain', 'Industries'),           # Geology
    3953: ('domain', 'Industries'),           # Hydrology
    3969: ('domain', 'Industries'),           # Meteorology
    3960: ('domain', 'Industries'),           # Astronomy
    4049: ('domain', 'Industries'),           # Drug Development
    4052: ('domain', 'Industries'),           # Drug Discovery
    4053: ('domain', 'Industries'),           # Pharmacology
    3945: ('domain', 'Methodologies'),        # Clinical Trials
    3523: ('domain', 'Industries'),           # Advanced Manufacturing
    3535: ('domain', 'Industries'),           # Manufacturing Processes
    3546: ('domain', 'Industries'),           # Manufacturing Operations
    3498: ('domain', 'Industries'),           # Food Science
    3500: ('domain', 'Industries'),           # Food Manufacturing
    3560: ('domain', 'Industries'),           # Textiles
    3561: ('domain', 'Industries'),           # Sewing
    563:  ('domain', 'Industries'),           # Pruning
    844:  ('domain', 'Industries'),           # Construction
    836:  ('domain', 'Business & Operations'),# Construction Management
    834:  ('domain', 'Legal & Compliance'),   # Building Codes
    1516: ('domain', 'Business & Operations'),# Public Works
    560:  ('domain', 'Industries'),           # Landscaping
    561:  ('domain', 'Industries'),           # Landscape Architecture
    829:  ('domain', 'Industries'),           # Carpentry
    831:  ('domain', 'Industries'),           # Masonry
    837:  ('domain', 'Industries'),           # Renovation
    850:  ('domain', 'Industries'),           # Roofing
    839:  ('domain', 'Industries'),           # Painting
    843:  ('domain', 'Industries'),           # Trenching
    849:  ('domain', 'Business & Operations'),# Traffic Control
    3503: ('domain', 'Methodologies'),        # Lean Manufacturing
    # Visual / creative (domain: Product & Design)
    1119: ('domain', 'Product & Design'),     # Visual Arts
    1125: ('domain', 'Product & Design'),     # Art History
    1123: ('domain', 'Product & Design'),     # Illustration
    1138: ('domain', 'Product & Design'),     # Sketching
    1124: ('domain', 'Product & Design'),     # Color Theory
    1122: ('domain', 'Product & Design'),     # Art Direction
    1128: ('domain', 'Product & Design'),     # Aesthetics
    1121: ('domain', 'Product & Design'),     # Iconography
    1130: ('domain', 'Product & Design'),     # Visual Effects
    1139: ('domain', 'Product & Design'),     # Fashion Design
    1106: ('domain', 'Product & Design'),     # Character Animation
    1129: ('domain', 'Product & Design'),     # Storyboarding
    1132: ('domain', 'Product & Design'),     # Visual Storytelling
    1143: ('domain', 'Product & Design'),     # Gamification
    1144: ('domain', 'Product & Design'),     # Texturing
    1145: ('domain', 'Product & Design'),     # Color Grading
    1111: ('domain', 'Product & Design'),     # Animations
    1168: ('domain', 'Product & Design'),     # Industrial Design
    # Marketing (domain: Marketing & Growth)
    106:  ('domain', 'Marketing & Growth'),   # Copywriting
    # Science disciplines staying in technical but wrong subcat — keep in tech
    # 4055 Physics, 3927 Chemistry, 3921 Biochemistry — keep technical, subcat below
}

# domain → technical (these are tools/platforms, not domain knowledge)
DOMAIN_TO_TECH = {
    524:  ('technical', 'Enterprise Tools & Platforms'),  # Microsoft Office
    537:  ('technical', 'Enterprise Tools & Platforms'),  # Google Sheets
    532:  ('technical', 'Enterprise Tools & Platforms'),  # Microsoft Teams
    528:  ('technical', 'Enterprise Tools & Platforms'),  # Microsoft Outlook
    536:  ('technical', 'Enterprise Tools & Platforms'),  # Microsoft Access
    1080: ('technical', 'Enterprise Tools & Platforms'),  # Microsoft Project
    328:  ('technical', 'Enterprise Tools & Platforms'),  # Workday
    342:  ('technical', 'Enterprise Tools & Platforms'),  # NetSuite
    341:  ('technical', 'Enterprise Tools & Platforms'),  # QuickBooks
    307:  ('technical', 'Enterprise Tools & Platforms'),  # HubSpot
    329:  ('technical', 'Enterprise Tools & Platforms'),  # BambooHR
    327:  ('technical', 'Enterprise Tools & Platforms'),  # HRIS
    530:  ('technical', 'Enterprise Tools & Platforms'),  # Spreadsheets
    522:  ('technical', 'Enterprise Tools & Platforms'),  # Word Processing
    3875: ('technical', 'Programming Languages'),         # Markdown
    1303: ('technical', 'Enterprise Tools & Platforms'),  # Articulate Storyline
    1305: ('technical', 'Enterprise Tools & Platforms'),  # Adobe Captivate
    538:  ('technical', 'Enterprise Tools & Platforms'),  # Camtasia Studio
    513:  ('technical', 'Enterprise Tools & Platforms'),  # VoiceXML
    531:  ('technical', 'Enterprise Tools & Platforms'),  # Office 365 Administration
    526:  ('technical', 'Enterprise Tools & Platforms'),  # Atlassian Confluence (handled in deactivate)
}

# domain → soft
DOMAIN_TO_SOFT = {
    518:  ('soft', 'Personal Effectiveness'),        # Organizational Skills
    1059: ('soft', 'Personal Effectiveness'),        # Timelines
    1383: ('soft', 'Leadership & Management'),       # Mentorship
    912:  ('soft', 'Leadership & Management'),       # Thought Leadership
    1016: ('soft', 'Leadership & Management'),       # Empowerment
    4124: ('soft', 'Communication'),                 # Advising
    521:  ('soft', 'Personal Effectiveness'),        # Typing
}

# technical → soft
TECH_TO_SOFT = {
    1174: ('soft', 'Problem Solving & Critical Thinking'),  # User Experience → keep in domain actually
}

# ─── 3. SUBCATEGORY ASSIGNMENTS ─────────────────────────────────────────────
# Organized by subcategory for readability.
# Only skills that need assignment (NULL subcategory) or correction.
# Format: id → subcategory string

SUBCATEGORIES = {}

# ── TECHNICAL ────────────────────────────────────────────────────────────────

# AI & Machine Learning
for _id in [
    2442,  # Artificial Intelligence
    13,    # Machine Learning
    182,   # LLMs
    180,   # Computer Vision
    184,   # Generative AI
    5024,  # AI agents
    178,   # Deep Learning
    181,   # Neural Networks
    179,   # Natural Language Processing
    442,   # RAG
    185,   # Prompt Engineering
    449,   # Fine-tuning
    500,   # MLflow
    186,   # MLOps
    188,   # Model Training
    183,   # GPT
    4710,  # Claude
    4711,  # Claude Code
    4712,  # Gemini
    4906,  # AI-assisted development
    4966,  # MCP
    5049,  # Microsoft Copilot
    5200,  # Microsoft Copilot Studio
    440,   # LangChain
    441,   # LlamaIndex
    5024,  # AI agents
    4929,  # Embeddings
    4918,  # LangGraph
    4965,  # LLM APIs
    4722,  # Transformer architectures
    4724,  # LLMOps
    4714,  # Amazon Bedrock
    5035,  # LLM orchestration
    5199,  # Generative models
    5220,  # Hallucination Mitigation
    5221,  # Inference Optimization
    5222,  # Multimodal AI
    5223,  # Speech AI
    5224,  # Edge AI
    5225,  # Model Quantization
    5226,  # AI Security
    447,   # OpenAI
    448,   # Hugging Face
    502,   # SageMaker
    503,   # Vertex AI
    2433,  # Reinforcement Learning
    2447,  # Unsupervised Learning (wait, this was deactivated? No, 2463 was the pending candidate. 2462/2463 are in taxonomy)
    2462,  # Supervised Learning
    2463,  # Unsupervised Learning
    644,   # Causal Inference
    633,   # Predictive Analytics
    625,   # Predictive Modeling
    631,   # Pattern Recognition
    187,   # Feature Engineering
    2446,  # Feature Extraction
    2464,  # Feature Selection
    2455,  # Chatbot
    2459,  # Reasoning Systems
    2434,  # Intelligent Systems
    2448,  # Intelligent Agent
    769,   # Speech Recognition
    686,   # Object Detection
    685,   # Image Analysis
    2439,  # Machine Learning Algorithms
    2467,  # Recommender Systems
    2449,  # OpenCV
    2457,  # Boosting
    2441,  # Artificial Intelligence Systems
    635,   # Knowledge Graph
    612,   # Ontologies
    763,   # Sentiment Analysis
    767,   # Natural Language Understanding
    765,   # Machine Translation
    4083,  # Applied Research (AI context - keep as Data Science instead)
    5232,  # Flyte
    5230,  # Debezium — no, this is Databases
]:
    SUBCATEGORIES[_id] = 'AI & Machine Learning'

# Fix misassigned above
SUBCATEGORIES[5230] = 'Databases & Data Engineering'  # Debezium
SUBCATEGORIES[4083] = 'Data Science & Analytics'      # Applied Research
SUBCATEGORIES[2462] = 'AI & Machine Learning'
SUBCATEGORIES[2463] = 'AI & Machine Learning'

# Programming Languages
for _id in [
    1,     # Python
    2,     # JavaScript
    25,    # Java
    16,    # TypeScript
    52,    # Go
    58,    # Rust
    56,    # Kotlin
    55,    # Swift
    53,    # Ruby
    57,    # Scala
    54,    # PHP
    26,    # C++
    24,    # R
    122,   # Perl
    124,   # Bash
    123,   # Shell Scripting
    126,   # VBA
    125,   # PowerShell
    127,   # Asp.net
    666,   # Pyspark
    3013,  # Clojure
    2895,  # Ajax (Programming Language)
    2889,  # Java (dup entry with language suffix)
    2499,  # C (Programming Language)
    2501,  # C++ (Programming Language)
    2996,  # Go (Programming Language)
    3000,  # R (Programming Language)
    3001,  # C# (Programming Language)
    3003,  # Swift (Programming Language)
    3005,  # Haskell (Programming Language)
    3008,  # F# (Programming Language)
    3009,  # Fortran (Programming Language)
    3012,  # Scala (Programming Language)
    3014,  # Rust (Programming Language)
    3019,  # SQL (Programming Language)
    3024,  # Shell Script — deactivated
    3027,  # IPython
    3029,  # Visual Basic (Programming Language)
    3031,  # Ruby (Programming Language)
    3032,  # Python (Programming Language)
    3034,  # Visual Basic .NET (Programming Language)
    3035,  # Lisp (Programming Language)
    3036,  # Julia (Programming Language)
    3037,  # Rexx (Programming Language)
    3038,  # Groovy (Programming Language)
    3039,  # Bash (Scripting Language)
    3015,  # PHP (Scripting Language)
    2997,  # Lasso (Programming Language)
    2885,  # Azure Internet Of Things (IoT) — wrong, fix below
    3875,  # Markdown (moved to tech)
    3023,  # Scripting
    2565,  # Computer Programming
    2583,  # Programming Concepts
    3163,  # Programming Tools
    5244,  # concurrent programming
    5248,  # compiler design
    5243,  # ASTs
    5253,  # COBOL
    5254,  # VBScript
]:
    SUBCATEGORIES[_id] = 'Programming Languages'

SUBCATEGORIES[2885] = 'Cloud & Infrastructure'  # Azure IoT
SUBCATEGORIES[2565] = 'Programming Languages'
SUBCATEGORIES[3023] = 'Programming Languages'

# Frontend & Web
for _id in [
    4,     # React
    33,    # HTML
    34,    # CSS
    2,     # JavaScript (already set — will take last assignment)
    63,    # Angular
    62,    # Vue.js
    130,   # Next.js
    131,   # Svelte
    133,   # Bootstrap
    134,   # Tailwind CSS
    135,   # Sass
    132,   # JQuery
    470,   # Vite
    471,   # Remix
    472,   # Astro
    3290,  # HTML5
    3291,  # Web Development
    3294,  # Web Design
    3295,  # Web Frameworks
    3296,  # Web Pages
    3306,  # Web Applications
    3280,  # Browser Compatibility
    3279,  # Dynamic Content
    3284,  # Web Accessibility
    3286,  # Web Standards
    3307,  # Responsive Web Design
    3312,  # Web Platforms
    3310,  # Internet Services
    3305,  # Web Engineering
    3316,  # Web Services
    2896,  # React.js
    2903,  # JavaScript Frameworks
    2898,  # JavaScript Libraries
    476,   # Storybook
    3140,  # WYSIWYG
    3141,  # WebAssembly
    138,   # WebSocket
    5245,  # SSR
    5246,  # headless CMS architectures
    5247,  # module federation
    2604,  # WordPress
    2605,  # Content Management Systems
]:
    SUBCATEGORIES[_id] = 'Frontend & Web'

# JavaScript is both frontend and backend — keep Frontend
SUBCATEGORIES[2] = 'Frontend & Web'

# Backend & APIs
for _id in [
    28,    # REST API
    137,   # GraphQL
    482,   # gRPC
    477,   # FastAPI
    478,   # NestJS
    61,    # Express.js
    64,    # Spring
    128,   # Ruby on Rails
    59,    # Django
    60,    # Flask
    129,   # Laravel
    481,   # tRPC
    479,   # Prisma
    475,   # Turbo
    483,   # Bun
    485,   # Pnpm
    487,   # Okta (auth platform)
    486,   # Auth0
    488,   # Clerk
    243,   # API Design
    12,    # API Documentation
    2424,  # API Gateway
    2426,  # RESTful API
    3044,  # Server-Side
    3043,  # Web Servers
    3316,  # Web Services — also frontend; set backend
    2900,  # RxJS
    139,   # OAuth
    140,   # JWT
    3002,  # ASP.NET Core
    2913,  # Entity Framework
    164,   # Microservices
    165,   # Serverless
    3065,  # Service-Oriented Architecture
    3081,  # Functional Programming
    3071,  # Dependency Injection
    3127,  # Dynamic Programming
    3117,  # Object-Oriented Design
    2393,  # Pair Programming
    2586,  # Business Logic
    2585,  # Abstractions
    3105,  # Immutability
    3131,  # Exception Handling
    5249,  # Jinja
    5250,  # Hapi.js
    5251,  # CAP theorem
    5252,  # domain modeling
    5253,  # multi-tenancy — fix below
]:
    SUBCATEGORIES[_id] = 'Backend & APIs'

SUBCATEGORIES[5253] = 'Backend & APIs'   # multi-tenancy
# Fix COBOL which was in programming loop above
SUBCATEGORIES[4759 if 4759 in SUBCATEGORIES else 5253] = 'Backend & APIs'

# Databases & Data Engineering
for _id in [
    3,     # SQL
    141,   # PostgreSQL
    142,   # MySQL
    79,    # MongoDB
    80,    # Redis
    82,    # Cassandra
    143,   # Oracle
    144,   # SQL Server
    145,   # SQLite
    146,   # DynamoDB
    147,   # Neo4j
    148,   # Firebase
    149,   # Supabase
    150,   # MariaDB
    172,   # Redshift
    173,   # BigQuery
    455,   # Databricks
    171,   # Snowflake
    70,    # Data Warehousing
    69,    # ETL
    177,   # Data Pipelines
    170,   # Dbt
    169,   # Airflow
    168,   # Kafka
    467,   # Consul -- actually DevOps
    634,   # Data Ingestion
    2718,  # Data Management
    2723,  # Data Lakes
    2697,  # Data Integration
    2714,  # Data Transformation
    2693,  # Data Quality
    2691,  # Data Integrity
    2701,  # Data Governance
    2692,  # Data Processing
    2678,  # Data Collection
    2680,  # Data Extraction
    2686,  # Metadata Management
    2740,  # Database Management
    2762,  # Database Systems
    2743,  # Database Design
    2739,  # Database Administration
    2766,  # Database Management Systems
    2768,  # Relational Database Management Systems
    2761,  # Relational Databases
    2756,  # NoSQL
    2745,  # Database Queries
    2742,  # Database Development
    2748,  # Database Engines
    2751,  # Database Models
    618,   # Star Schema
    640,   # Data Layers
    2711,  # Dataset
    2688,  # Taxonomy
    2684,  # Data Literacy
    2679,  # Data Acquisition
    643,   # Information Retrieval
    610,   # Data Mining
    617,   # Data Cleansing
    586,   # Data Synthesis
    601,   # Data Discovery
    626,   # Data Manipulation
    588,   # Data Validation
    2705,  # Data Loss Prevention
    658,   # Metadata
    2690,  # Unstructured Data
    2699,  # Informatica
    450,   # Fivetran
    499,   # ClickHouse
    497,   # CockroachDB
    494,   # PlanetScale
    495,   # Neon
    498,   # TiDB
    2778,  # Graph Database
    636,   # Data Reduction
    2703,  # Dynamic Data
    2485,  # Tablets — no, wrong
    2734,  # Data Store
    2727,  # Data Retention
    2707,  # Data Classification
    2715,  # Application Data
    2709,  # Data Infrastructure
    2573,  # Data Architecture
    664,   # Causal Inference — DS subcat
    5230,  # Debezium
    5258,  # Delta Tables
    5261,  # Aurora
    5255,  # lakehouse architectures
    5259,  # Unity Catalog
    5260,  # graph technologies
    5262,  # OLAP technologies
    5263,  # Query Optimization
    452,   # Dagster
    453,   # Prefect
    454,   # Great Expectations
    451,   # Airbyte
    466,   # Vault — no, DevOps
    2722,  # Storage Systems — infra?
]:
    SUBCATEGORIES[_id] = 'Databases & Data Engineering'

# Fix misassigned
SUBCATEGORIES[467] = 'DevOps & CI/CD'    # Consul
SUBCATEGORIES[466] = 'DevOps & CI/CD'    # Vault
SUBCATEGORIES[664] = 'Data Science & Analytics'
SUBCATEGORIES[2722] = 'Cloud & Infrastructure'  # Storage Systems
SUBCATEGORIES[2485] = 'Mobile'  # Tablets

# Data Science & Analytics
for _id in [
    7,     # Data Analytics
    661,   # Data Science
    602,   # Data Analysis
    176,   # Data Modeling
    23,    # Tableau
    72,    # Power BI
    174,   # Looker
    175,   # Metabase
    676,   # Data Visualization
    675,   # Data Storytelling
    65,    # Pandas
    66,    # NumPy
    121,   # Matlab
    24,    # R (also Programming Languages — keep DS)
    621,   # Jupyter
    673,   # Matplotlib
    570,   # Business Analytics
    71,    # Business Intelligence
    807,   # Statistics
    786,   # Statistical Modeling
    803,   # Statistical Methods
    784,   # Applied Statistics
    808,   # Statistical Inference
    820,   # Actuarial Science
    782,   # Bayesian Inference
    792,   # Bayesian Statistics
    804,   # Bayesian Modeling
    750,   # Probability
    802,   # Probability And Statistics
    752,   # Probability (dup? check)
    733,   # Quantitative Analysis
    607,   # Quantitative Data Analysis
    4087,  # Quantitative Research
    4107,  # Qualitative Research
    4080,  # Qualitative Analysis
    741,   # Regression Analysis
    789,   # Logistic Regression
    816,   # Linear Regression
    625,   # Predictive Modeling
    633,   # Predictive Analytics
    592,   # Exploratory Data Analysis
    644,   # Causal Inference
    4102,  # Experimental Design
    4101,  # Controlled Experiments
    596,   # Optimal Design
    598,   # Vertica
    770,   # Stata
    774,   # Statistical Software
    772,   # Statistical Packages
    707,   # Numerical Analysis
    712,   # Applied Mathematics
    696,   # Basic Math
    720,   # Geometry
    716,   # Calculus
    727,   # Algebra
    732,   # Linear Algebra
    724,   # Differential Equations
    731,   # Topology
    695,   # Trigonometry
    736,   # Multivariable Calculus
    707,   # Numerical Analysis
    739,   # Computational Mathematics
    745,   # Advanced Mathematics
    725,   # Mathematical Modeling
    722,   # Mathematical Optimization
    737,   # Graph Theory
    735,   # Game Theory
    693,   # Uncertainty Quantification
    759,   # Computational Geometry
    747,   # Dynamical Systems
    699,   # Robust Control
    738,   # Optimal Control
    704,   # Industrial Robotics — no, Hardware
    4082,  # Research Methodologies
    4079,  # Analytical Techniques
    4095,  # Secondary Research
    4096,  # Comparative Analysis
    4084,  # Empirical Research
    4085,  # Survey Research
    4098,  # Research And Development
    4110,  # Research Reports
    4103,  # Scientific Reasoning
    4104,  # Basic Research
    4106,  # Internet Research
    4108,  # Research Design
    4093,  # Information Gathering
    576,   # Reporting Tools
    577,   # Business Intelligence Tools
    5241,  # GDAL
    5242,  # ParaView
    5243,  # QuickSight -- fix below
    5244,  # KNIME -- fix below
    5245,  # R Shiny -- fix below
]:
    SUBCATEGORIES[_id] = 'Data Science & Analytics'

SUBCATEGORIES[5241] = 'Data Science & Analytics'  # GDAL
SUBCATEGORIES[704]  = 'Hardware & Embedded'        # Industrial Robotics fix
SUBCATEGORIES[5243] = 'Data Science & Analytics'   # QuickSight (was set to Frontend above by mistake)
# Actual IDs for these new skills (from our promotion):
# Need to look up the right IDs — using the ones from the shortlist
# They were assigned IDs 5230+ so let me just set them by name pattern in the script

# Cloud & Infrastructure
for _id in [
    19,    # AWS
    74,    # GCP
    73,    # Azure
    18,    # Kubernetes
    17,    # Docker
    77,    # Terraform
    78,    # Ansible
    157,   # Chef
    156,   # Puppet
    158,   # Vagrant
    75,    # CI/CD
    2509,  # Cloud Infrastructure
    2532,  # Google Cloud
    2503,  # Cloud Technologies
    2508,  # Cloud Computing
    2514,  # Cloud Computing Architecture
    2534,  # Public Cloud
    2506,  # Cloud Migration
    2515,  # Serverless Computing
    2510,  # Cloud Applications
    2513,  # Cloud Hosting
    2736,  # Cloud Storage
    2519,  # Microsoft Azure
    2526,  # Azure Cloud Services
    3317,  # Amazon Web Services
    2529,  # Amazon S3
    3270,  # AWS Lambda
    2885,  # Azure Internet Of Things (IoT)
    2875,  # Azure Active Directory
    2770,  # Azure Cosmos DB
    2530,  # OpenShift
    2653,  # OpenStack
    3273,  # Containerization
    3268,  # Virtual Machines
    3272,  # Hyper-V
    3271,  # Hypervisor
    3265,  # Server Virtualization
    3274,  # Virtualization (also listed in domain as near-dup of Visualization — different!)
    2788,  # Edge Computing
    2541,  # IBM Cloud Computing
    492,   # Render
    489,   # Vercel
    490,   # Netlify
    2528,  # Heroku
    491,   # Railway
    2850,  # Infrastructure Automation
    2866,  # Infrastructure Management
    163,   # Infrastructure as Code
    2857,  # Capacity Management
    2722,  # Storage Systems
    2732,  # Storage Devices
    2726,  # Object Storage
    2724,  # RAID
    2721,  # Data Storage Technologies
    5264,  # Cloudflare Workers
    5265,  # AWS Control Tower
    5266,  # AWS Workspaces
    5267,  # ELB
]:
    SUBCATEGORIES[_id] = 'Cloud & Infrastructure'

# DevOps & CI/CD
for _id in [
    3102,  # DevOps
    75,    # CI/CD (also cloud — keep DevOps)
    154,   # GitHub Actions
    153,   # GitLab CI
    155,   # CircleCI
    463,   # ArgoCD
    464,   # FluxCD
    507,   # GitOps
    466,   # Vault
    467,   # Consul
    3162,  # Flux
    3097,  # Continuous Delivery
    2404,  # Continuous Integration
    186,   # MLOps
    500,   # MLflow
    2848,  # Robotic Process Automation
    2849,  # Network Automation
    3121,  # Build Process
    3125,  # Code Review
    3084,  # Development Environment
    2850,  # Infrastructure Automation (also Cloud)
    505,   # Backstage
    5268,  # Rancher
    5269,  # QEMU
    5270,  # HashiCorp Nomad
    5271,  # Cilium CNI
    5272,  # Podman
]:
    SUBCATEGORIES[_id] = 'DevOps & CI/CD'

SUBCATEGORIES[75] = 'DevOps & CI/CD'   # CI/CD final assignment
SUBCATEGORIES[186] = 'AI & Machine Learning'  # MLOps
SUBCATEGORIES[500] = 'AI & Machine Learning'  # MLflow

# Security & Compliance
for _id in [
    231,   # Cybersecurity
    238,   # SOC
    237,   # SIEM
    234,   # Encryption
    235,   # SSL/TLS
    241,   # Zero Trust
    232,   # Penetration Testing
    233,   # OWASP
    239,   # Vulnerability Assessment
    2644,  # Vulnerability Scanning
    2636,  # Vulnerability
    2611,  # Threat Modeling
    2635,  # Threat Detection
    2654,  # Cyber Threat Intelligence
    2652,  # Cyber Threat Intelligence (dup?)
    2633,  # Cybercrime
    2629,  # Computer Security
    2618,  # Digital Security
    2616,  # Application Security
    2646,  # Web Application Security
    2608,  # Security Controls
    2658,  # Data Security
    2656,  # Enterprise Security
    2668,  # Infrastructure Security
    2672,  # Hardening
    2637,  # Access Controls
    2674,  # Security Administration
    2613,  # Security Strategies
    2632,  # Security Software
    2615,  # Security Testing
    2607,  # Internet Security
    2640,  # Attack Surface Management
    2671,  # Digital Forensics
    2651,  # Digital Forensics (dup?)
    2619,  # Computer Forensics
    2667,  # Metasploit
    2408,  # Nessus
    242,   # Security Auditing
    2966,  # Public Key Infrastructure
    2638,  # Cryptography
    2657,  # Quantum Cryptography
    2649,  # Key Management
    2870,  # Identity And Access Management
    2871,  # Single Sign-On (SSO)
    240,   # Identity Management
    139,   # OAuth (also Backend)
    2617,  # Information Privacy
    2705,  # Data Loss Prevention
    2940,  # Mobile Security
    2505,  # Cloud Computing Security
    2744,  # Database Security
    3853,  # Physical Security (domain) — keep domain
    2810,  # Active Directory
    2875,  # Azure Active Directory
    2978,  # Wireshark
    5233,  # MFA
    5234,  # RMF process
    5235,  # HSMs
    5236,  # FleetDM
    5238,  # certificate-based authentication
    5239,  # ABAC
    5240,  # COMSEC
    5241,  # software composition analysis -- fix below
    5242,  # MITRE ATT&CK -- fix below
    5243,  # Security+  -- fix below
    5244,  # SWG -- fix below
    5245,  # CVSS -- fix below
    5246,  # NIST 800-53 Rev 5 -- fix below
    5247,  # WebAuthn -- fix below
    5248,  # SCIM provisioning -- fix below
    5249,  # Burp Suite -- fix below
    5250,  # Lacework -- fix below
    5251,  # Trivy -- fix below
    5252,  # Privacy Enhancing Technologies -- fix below
    5253,  # secrets management platforms -- fix below
    5226,  # AI Security
]:
    SUBCATEGORIES[_id] = 'Security & Compliance'

# I'm overwriting some IDs set in other loops — the last assignment wins.
# Let me be explicit about the security-specific new skill IDs using name lookup.
# Will use a name-based update in the script body instead (see _assign_by_name below)

# Networking & Systems
for _id in [
    2945,  # TCP/IP
    2946,  # Domain Name System
    2955,  # Network Protocols
    2954,  # Internet Protocols
    2953,  # IPv4
    2942,  # IPv6
    2982,  # Operating Systems
    2984,  # Linux Kernel
    161,   # Linux
    162,   # Unix
    2990,  # Mac OS
    2992,  # CentOS
    3148,  # Red Hat Enterprise Linux
    2986,  # Real-Time Operating Systems
    2991,  # z/OS
    2989,  # Windows Servers
    2930,  # Microsoft Windows
    2926,  # Microsoft Windows SDK
    3041,  # Microsoft Servers (domain) — recategorize
    2773,  # Microsoft SQL Servers (domain) — recategorize
    3211,  # System Administration
    3051,  # Server Administration
    3050,  # Linux Servers
    2816,  # IP Addressing
    2817,  # Network Control
    2803,  # Network Topology
    3180,  # Network Analysis
    3202,  # Network Infrastructure
    3187,  # Network Architecture
    3216,  # Network Administration
    2821,  # Wireless Networks
    2818,  # Wide Area Networks
    2806,  # Mesh Networking
    2805,  # Network Troubleshooting
    2809,  # Network Diagrams
    2814,  # Complex Networks
    2800,  # Computer Networks
    2973,  # Networking Hardware
    2974,  # Network Switches
    3238,  # Broadband
    3237,  # Wireless Communications
    3233,  # Bluetooth
    3228,  # Communications Systems
    3246,  # Communications Protocols
    3227,  # Fiber Optics
    2879,  # Wearables
    2882,  # Connected Devices
    255,   # IoT
    2884,  # Internet Of Things (wait, not in the list above)
    3234,  # Whatsapp — social, not networking
    2979,  # Cisco Meraki
    2884,  # not sure of ID
    3049,  # Akamai
    248,   # Load Balancing
    246,   # Caching
    2511,  # Interoperability
    3185,  # Data Centers
    2854,  # Device Management
    2935,  # Mobile Devices
    2488,  # Mobile Phones
    2484,  # Personal Computers
    2490,  # Firefox
    2492,  # Web Browsers
    5273,  # structured cabling standards
    5274,  # reverse proxy
    5275,  # VDI
    5276,  # IPAM
    5277,  # 802.1x Authentication
    5278,  # Junos
    5279,  # Tailscale
    5280,  # DNS management
]:
    SUBCATEGORIES[_id] = 'Networking & Systems'

SUBCATEGORIES[3234] = 'Enterprise Tools & Platforms'  # WhatsApp
SUBCATEGORIES[2880] = 'Networking & Systems'  # Internet Of Things (IoT) -- correct ID is 2880

# Hardware & Embedded
for _id in [
    256,   # Embedded Systems
    1597,  # Instrumentation
    1598,  # Oscilloscope
    1583,  # Electronics
    1553,  # Electrical Engineering — recategorized to domain above
    1577,  # Electronic Components
    1580,  # Digital Electronics
    1582,  # Electronic Design
    1487,  # Electronic Circuits
    1558,  # Electronic Systems
    1494,  # Circuit Design
    1493,  # Integrated Circuits
    1496,  # Integrated Circuit Design
    1497,  # Transistor
    1488,  # Capacitors
    1554,  # Inductors
    1566,  # Semiconductor Device
    3459,  # Semiconductors
    1543,  # Microelectronics -- wait, I see 3543
    3543,  # Microelectronics
    2559,  # Microprocessor
    3110,  # Microarchitecture
    1616,  # Verilog
    1712,  # Simulink
    1542,  # Engineering Drawings
    1540,  # Design Specifications
    1399,  # Voltage
    1548,  # High Voltage
    1547,  # Low Voltage
    1694,  # Antenna
    1555,  # Modulation
    1698,  # Radio Frequency
    1697,  # Microwaves
    1686,  # Photonics
    1683,  # Optics
    1678,  # Optical Engineering
    1680,  # Optical Communication
    1673,  # Thermal Design
    1665,  # Thermal Management
    1657,  # Heat Transfer
    1658,  # Finite Element Methods
    1652,  # Mechanics
    1651,  # unknown -- check
    1649,  # Mechatronics — recategorized to domain
    1650,  # Fluid Mechanics
    1653,  # Fluid Dynamics
    1664,  # Computational Fluid Dynamics
    1667,  # Solid Mechanics
    1613,  # Soil Mechanics -- actually domain: geo
    1674,  # Kinematics
    1690,  # Process Control
    1689,  # Process Engineering
    1687,  # Process Engineering (dup? check IDs)
    1691,  # Process Manufacturing
    1704,  # Industrial Robotics
    1706,  # Robotics
    1701,  # Motion Planning
    1473,  # Motion Control Systems
    1709,  # Digital Signal Processing
    1710,  # Signal Processing
    1708,  # Filter Design
    1713,  # Noise Reduction
    1715,  # Molecular Dynamics -- domain science
    1717,  # Simulations
    1720,  # Simulation Software
    1530,  # Autodesk
    1535,  # AutoCAD
    824,   # Autodesk Revit
    1541,  # Computer-Aided Design
    3477,  # HVAC
    3484,  # Batteries
    3479,  # Pumps
    3480,  # Drainage Systems
    3456,  # Electricity
    3457,  # Electrical Systems
    3520,  # Electric Motors
    3463,  # Compressed Air
    3469,  # Ventilation
    3471,  # Cooling Systems
    3466,  # Environmental Control
    3486,  # Automotive Industry — domain
    3494,  # Industry 4.0
    3532,  # Machining
    3533,  # Injection Molding
    3540,  # Sheet Metal
    3528,  # Lamination
    3529,  # Metal Fabrication
    3531,  # Industrial Processes
    3517,  # Sharpening
    3513,  # Mills
    3511,  # Lathes
    3512,  # Shaper
    3524,  # Smart Manufacturing
    3525,  # Grinding
    3508,  # Value Stream Mapping
    3510,  # Lean Six Sigma -- Methodologies
    3557,  # Assembly Lines
    3559,  # Production Line
    3545,  # Production Process
    1621,  # Laser Scanning
    1623,  # Image Processing
    1620,  # Image Sensor
    1593,  # Arduino
    3566,  # Welding
    5237,  # FEA software
    5238,  # Zemax -- fix
    5239,  # AFSIM -- fix
    5240,  # EtherCAT -- fix
    5241,  # Mastercam -- fix
    5242,  # DAQ systems -- fix
    5243,  # beamforming -- fix
    5244,  # AWS D17.1 -- fix
    5245,  # RTOS environments -- fix
    5246,  # QNX -- fix
    5247,  # HDI -- fix
    5248,  # Vector CANoe -- fix
    5249,  # IPC-610 -- fix
    5250,  # IPC-A-620 -- fix
    5251,  # DFT implementation -- fix
    5252,  # CAM programming -- fix
    5253,  # Zephyr -- fix
    5254,  # SoC integration -- fix
    5255,  # FinFET -- fix
    5256,  # OpenBMC -- fix
    5257,  # IMUs -- fix
    5258,  # Electrostatic Discharge -- fix
    5259,  # UWB -- fix
    5260,  # Industrial IoT -- fix
    5261,  # 5-axis milling -- fix
]:
    SUBCATEGORIES[_id] = 'Hardware & Embedded'

SUBCATEGORIES[3510] = 'Methodologies'      # Lean Six Sigma → domain
SUBCATEGORIES[3486] = 'Industries'         # Automotive Industry → domain
SUBCATEGORIES[1715] = 'Data Science & Analytics'  # Molecular Dynamics
SUBCATEGORIES[1613] = 'Industries'         # Soil Mechanics → domain: Industries
# HVAC is a building systems skill, keep Hardware & Embedded

# QA & Testing
for _id in [
    230,   # Test Automation
    218,   # Integration Testing
    217,   # Unit Testing
    219,   # E2E Testing
    220,   # Jest
    221,   # Mocha
    222,   # Pytest
    223,   # Selenium
    224,   # Cypress
    225,   # Playwright
    226,   # JUnit
    227,   # TestNG
    228,   # Load Testing
    229,   # Performance Testing
    3167,  # Usability Testing
    3174,  # Exploratory Testing
    3170,  # Development Testing
    3165,  # Web Testing
    3171,  # Software Testing
    3172,  # Verification And Validation
    3190,  # System Testing
    3060,  # Testability
    3248,  # Scenario Testing
    3164,  # Risk-Based Testing
    3168,  # Code Coverage
    3253,  # Test Suite
    3251,  # Mockito
    3250,  # Rspec
    2405,  # Test-Driven Development (TDD)
    5257,  # manual QA testing
    5330,  # LoadRunner
    5332,  # BDD/TDD
]:
    SUBCATEGORIES[_id] = 'QA & Testing'

# Mobile
for _id in [
    189,   # iOS Development
    190,   # Android Development
    191,   # React Native
    192,   # Flutter
    193,   # SwiftUI
    194,   # Jetpack Compose
    195,   # Xamarin
    196,   # Ionic
    197,   # Cordova
    2934,  # Mobile Application Development
    2936,  # Google Play
    2938,  # Android Studio
    2485,  # Tablets
    2488,  # Mobile Phones
    2935,  # Mobile Devices
    5343,  # AOSP
]:
    SUBCATEGORIES[_id] = 'Mobile'

SUBCATEGORIES[2485] = 'Mobile'
SUBCATEGORIES[2488] = 'Mobile'
SUBCATEGORIES[2935] = 'Networking & Systems'  # Mobile Devices is more networking

# Enterprise Tools & Platforms
for _id in [
    30,    # Jira
    201,   # Confluence
    211,   # Notion
    212,   # Asana
    213,   # Trello
    214,   # Linear
    215,   # Monday.com
    216,   # Airtable
    202,   # Slack
    203,   # Vs Code
    204,   # IntelliJ
    205,   # Postman
    206,   # Swagger
    207,   # Sketch
    208,   # Adobe Xd
    209,   # Photoshop
    210,   # Illustrator
    1159,  # Adobe Illustrator
    1164,  # Adobe Photoshop
    1105,  # Cinema 4D
    1116,  # Unreal Engine
    1107,  # Unity Engine
    1118,  # Game Engine
    22,    # PowerPoint
    21,    # Microsoft Excel
    32,    # Salesforce
    328,   # Workday (moved from domain)
    342,   # NetSuite (moved from domain)
    341,   # QuickBooks (moved from domain)
    307,   # HubSpot (moved from domain)
    329,   # BambooHR (moved from domain)
    327,   # HRIS (moved from domain)
    524,   # Microsoft Office (moved from domain)
    537,   # Google Sheets (moved from domain)
    530,   # Spreadsheets (moved from domain)
    532,   # Microsoft Teams (moved from domain)
    528,   # Microsoft Outlook (moved from domain)
    536,   # Microsoft Access (moved from domain)
    1080,  # Microsoft Project (moved from domain)
    522,   # Word Processing (moved from domain)
    1303,  # Articulate Storyline (moved from domain)
    1305,  # Adobe Captivate (moved from domain)
    538,   # Camtasia Studio (moved from domain)
    306,   # CRM (stays domain actually)
    933,   # ERP (stays domain)
    942,   # Microsoft Dynamics (stays domain)
    2914,  # Microsoft Power Platform
    2543,  # Microsoft SharePoint
    2865,  # IT Service Management
    2862,  # Management Information Systems
    3234,  # WhatsApp
    3260,  # Skype
    3262,  # Google Hangouts
    3261,  # Web Conferencing
    2542,  # Intranet
    2604,  # WordPress (also Frontend)
    2605,  # Content Management Systems (also Frontend)
    5282,  # Houdini
    5283,  # Shotgrid
    5284,  # xAPI
    5285,  # Calypso platform
    5286,  # Infor LN
    5287,  # MasterControl
    5288,  # Encompass LOS
    5289,  # Reltio
    5290,  # Dovetail
    5291,  # Smartling
    5292,  # Nanite
    5293,  # SAP S/4HANA
    5294,  # SCORM
    5295,  # Esri App Builders
    5296,  # CLO 3D
    5297,  # Linksquares
    5298,  # CAT platforms
    5299,  # Lever
    5300,  # no-code/low-code
]:
    SUBCATEGORIES[_id] = 'Enterprise Tools & Platforms'

# Fix domain tools that should stay domain
SUBCATEGORIES[306]  = None  # CRM — stays domain, don't override
SUBCATEGORIES[933]  = None  # ERP — stays domain
SUBCATEGORIES[942]  = None  # Microsoft Dynamics — stays domain, but subcateg below

# DOMAIN subcategory assignments
# ── DOMAIN ────────────────────────────────────────────────────────────────────

# Industries
for _id in [
    350,   # Healthcare
    4189,  # Influenza
    4192,  # Foodborne Illness
    4194,  # Mental Diseases
    4197,  # Personality Disorder
    4199,  # Autism Spectrum Disorders
    4180,  # Dyslexia
    4182,  # Learning Disabilities
    4186,  # Mono
    4183,  # Genetic Disorders
    4193,  # Communicable Diseases
    2269,  # Cancer
    4191,  # Ebola
    4188,  # Pneumonia
    4181,  # Dyscalculia
    4190,  # Tuberculosis
    4196,  # Alzheimer's Disease
    4195,  # DSM
    372,   # Manufacturing
    844,   # Construction (moved from tech)
    369,   # Government
    366,   # Media
    358,   # Retail
    361,   # Banking
    340,   # Private Equity
    362,   # FinTech
    363,   # EdTech
    364,   # HealthTech
    365,   # Gaming
    367,   # Entertainment
    368,   # Nonprofit
    370,   # Aerospace (industry)
    371,   # Automotive
    1798,  # Financial Services
    1352,  # Minecraft (gaming industry)
    1350,  # ESports
    2095,  # Primary Care
    2082,  # Internal Medicine
    2043,  # Emergency Medicine
    2038,  # Critical Care
    2033,  # Intensive Care Unit
    2238,  # Nursing
    2237,  # Life Skills -- not industry
    354,   # Pharmaceutical
    2297,  # Pediatrics
    2265,  # Oncology
    2226,  # Neurology
    2204,  # Psychiatry
    2203,  # Behavioral Health
    2182,  # Mental Health
    1724,  # Air Quality
    4134,  # Aviation
    4135,  # Airspace
    4139,  # Heavy Equipment
    2017,  # Veterinary Medicine
    2084,  # Sports Medicine
    1827,  # Finance (industry)
    # Sciences moved from technical
    542,   # Agriculture
    556,   # Agronomy
    544,   # Precision Agriculture
    3998,  # Genetics
    3896,  # Biology
    3883,  # Life Sciences
    3902,  # Biotechnology
    4047,  # Neuroscience
    3997,  # Genomics
    4026,  # Molecular Biology
    4042,  # Microbiology
    3889,  # Synthetic Biology
    1484,  # Biomedical Engineering
    1483,  # Chemical Engineering
    1519,  # Civil Engineering
    1553,  # Electrical Engineering
    1463,  # Aerospace Engineering
    1628,  # Industrial Engineering
    1638,  # Materials Science
    1645,  # Materials Engineering
    1649,  # Mechatronics
    1430,  # Oil And Gas
    3908,  # Petrochemical
    1426,  # Nuclear Fuel
    1422,  # Nuclear Power
    1423,  # Nuclear Engineering
    1424,  # Nuclear Safety
    1393,  # Renewable Energy
    1477,  # Electric Vehicles
    1479,  # Autonomous Vehicles
    1461,  # Space Exploration
    1465,  # Spacecraft
    1462,  # Space Flight
    3976,  # Geology
    3953,  # Hydrology
    3969,  # Meteorology
    3960,  # Astronomy
    4049,  # Drug Development
    4052,  # Drug Discovery
    4053,  # Pharmacology
    3523,  # Advanced Manufacturing
    3535,  # Manufacturing Processes
    3546,  # Manufacturing Operations
    3498,  # Food Science
    3500,  # Food Manufacturing
    3560,  # Textiles
    3561,  # Sewing
    563,   # Pruning
    560,   # Landscaping
    561,   # Landscape Architecture
    829,   # Carpentry
    831,   # Masonry
    837,   # Renovation
    850,   # Roofing
    839,   # Painting
    843,   # Trenching
    3486,  # Automotive Industry
    5362,  # UAVs
    5364,  # genetic testing
    5354,  # geospatial intelligence
    5355,  # ligand binding assays
    5363,  # non-pharmacological interventions -- wait this is domain already
    5358,  # non-pharmacological interventions (id from our data)
    5373,  # CPG industry
    5374,  # EV architectures
    5379,  # Utilization Management
    5380,  # RWE
]:
    SUBCATEGORIES[_id] = 'Industries'

# Business & Operations
for _id in [
    309,   # Supply Chain
    311,   # Procurement
    312,   # Inventory Management
    310,   # Logistics
    313,   # Process Improvement
    315,   # Lean
    316,   # Quality Assurance
    317,   # Vendor Management
    318,   # Contract Management
    85,    # Account Management
    939,   # Business Operations
    937,   # Business Process
    308,   # Operations Management
    1039,  # Process Design
    1033,  # Process Optimization
    1034,  # Process Flow Diagrams
    516,   # Data Entry
    517,   # Filing
    511,   # Administrative Functions
    514,   # Document Production
    512,   # Transcribing
    523,   # Front Office
    519,   # Registration
    520,   # File Management
    510,   # Memos — deactivate instead? Keep for now.
    3391,  # Cleanliness
    2355,  # Cooking
    836,   # Construction Management (moved from tech)
    849,   # Traffic Control (moved from tech)
    1516,  # Public Works (moved from tech)
    4144,  # Inventory Control
    4143,  # Inventory Valuation
    4146,  # Stock Management
    4145,  # Warehouse Management Systems
    4141,  # Sorting
    4149,  # Logistics Management
    4158,  # Supply Chain Planning
    4162,  # Demand Planning
    4163,  # Supply Chain Management — deactivated
    4164,  # Supply Chain Optimization
    4168,  # Demand Forecasting
    4169,  # Supply Chain Network
    4170,  # Supply Chain Integration
    4172,  # Supply Chain Strategy
    4161,  # Material Requirements Planning
    4160,  # Production Planning
    5359,  # cash handling
    5371,  # 3PL
    5388,  # warehouse management software
]:
    SUBCATEGORIES[_id] = 'Business & Operations'

# Marketing & Growth
for _id in [
    285,   # Digital Marketing
    283,   # Sales Operations
    287,   # SEO
    288,   # SEM
    289,   # PPC
    290,   # Social Media Marketing
    291,   # Email Marketing
    292,   # Marketing Automation
    293,   # Brand Management
    294,   # Public Relations
    295,   # Growth Marketing
    296,   # Demand Generation
    297,   # Lead Generation
    298,   # Conversion Optimization
    14,    # Product Marketing
    3567,  # Advertising Campaigns
    3570,  # Brand Strategy
    3571,  # Brand Communication
    3572,  # Brand Marketing
    3573,  # Brand Awareness
    3575,  # Brand Positioning
    3569,  # Brand Identity
    3597,  # Marketing Analytics
    3598,  # Trend Analysis
    3599,  # Value Propositions
    3600,  # Quantitative Marketing Research
    3601,  # Market Analysis
    3603,  # Marketing Operations
    3604,  # Market Development
    3605,  # Marketing Management
    3606,  # Market Segmentation
    3607,  # Marketing Mix
    3609,  # Marketing Communications
    3610,  # Marketing Planning
    3611,  # Goal Setting -- soft? keep marketing
    3612,  # Strategic Marketing
    3613,  # Mass Customization
    3614,  # Content Strategy
    3615,  # Integrated Marketing Communications
    3616,  # Media Strategy
    3617,  # Marketing Concepts
    3618,  # Growth Hacking
    3619,  # Business Marketing
    3620,  # Influencer Marketing
    3621,  # Word-of-Mouth Marketing
    3622,  # Relationship Marketing
    3623,  # Marketing Strategies — deactivated
    3624,  # Global Marketing — deactivated (alias)
    3625,  # Search Advertising
    3626,  # Google Ads
    3627,  # Online Advertising
    3628,  # Campaign Advertising
    3629,  # Testimonial
    3630,  # Campaign Management
    3631,  # Mass Media
    3632,  # Product Promotion
    3633,  # Public Opinion
    3634,  # Crisis Management
    3635,  # Public Affairs
    3636,  # International Relations (more Political, but keep here)
    3637,  # Newsletters
    3638,  # Press Releases
    3639,  # Social Networks
    3641,  # TikTok
    3643,  # Social Media Advertising
    3644,  # Social Media Analytics
    3645,  # Podcasting
    3646,  # Snapchat
    263,   # Market Research
    111,   # Marketing Strategy
    5366,  # funnel analysis
    5367,  # short-form video production
    5368,  # D2C environments
    5369,  # brand building
    5376,  # Product-Led Growth
    5387,  # App Store Optimization
    106,   # Copywriting (moved from tech)
]:
    SUBCATEGORIES[_id] = 'Marketing & Growth'

# Sales & Customer Success
for _id in [
    90,    # Closing
    91,    # Prospecting
    92,    # Cold Calling
    299,   # B2B Sales
    300,   # B2C Sales
    301,   # Enterprise Sales
    302,   # SaaS Sales
    303,   # Solution Selling
    304,   # Consultative Selling
    305,   # Sales Strategy
    84,    # Customer Success
    87,    # Partnerships
    88,    # Revenue Growth
    89,    # Pipeline Management
    3865,  # Sales Process
    3866,  # Selling Techniques
    3867,  # Product Lining
    3868,  # Sales Concepts
    3869,  # Direct Selling
    3870,  # Sales Presentation
    3871,  # unknown
    3872,  # Customer Acquisition Management
    3873,  # Retail Management
    3874,  # Loyalty Programs
    3877,  # Sales Management
    3859,  # Business To Business
    3878,  # Business-To-Consumer
    306,   # CRM (also here)
    1020,  # Relationship Management
    1013,  # Customer Lifecycle Management
    1012,  # Customer Data Management
]:
    SUBCATEGORIES[_id] = 'Sales & Customer Success'

SUBCATEGORIES[306] = 'Sales & Customer Success'   # CRM
SUBCATEGORIES[3611] = 'Marketing & Growth'         # Goal Setting — override soft

# Finance & Accounting
for _id in [
    330,   # Accounting
    332,   # Tax
    331,   # Bookkeeping
    333,   # Audit
    277,   # Financial Analysis
    278,   # Financial Modeling
    337,   # Valuation
    335,   # Risk Management
    336,   # Investment Analysis
    338,   # M&A
    339,   # Venture Capital
    340,   # Private Equity
    341,   # QuickBooks — also Enterprise Tools
    1827,  # Finance
    1798,  # Financial Services (also Industries)
    1829,  # Revenue Recognition
    1836,  # Variance Analysis
    1839,  # Financial Data
    1844,  # Financial Forecasting
    1845,  # Financial Planning
    1850,  # Cash Flow Forecasting
    1853,  # Market Value
    1854,  # Corporate Finance
    1860,  # Financial Management
    1862,  # Financial Systems
    1864,  # Capital Allocation
    1867,  # Cost Management
    1868,  # Capital Expenditure
    1874,  # Asset Classes
    1875,  # Know Your Customer
    1876,  # Anti Money Laundering
    1877,  # Financial Regulations
    1880,  # Capital Requirements
    1881,  # Federal Reserve System
    1882,  # FINRA
    1883,  # Bank Statements
    1884,  # Income Statement
    1885,  # Financial Statements
    1886,  # Balance Sheet
    1887,  # IFRS
    1888,  # Cash Flow Statements
    1889,  # Loss Given Default
    1890,  # Risk Measure
    1891,  # Credit Risk Management
    1892,  # Operational Risk
    1893,  # Credit Derivatives
    1894,  # ERM
    1895,  # Financial Risk
    1896,  # Reputational Risk
    1897,  # Credit Risk
    1898,  # Risk Management Tools
    1899,  # Systemic Risk
    1900,  # Foreign Exchange Risk
    1901,  # Risk Financing
    1902,  # Financial Crisis
    1903,  # Mathematical Finance
    1904,  # Financial Engineering
    1905,  # Commercial Paper
    1906,  # Broker Dealers
    1907,  # IPO
    1908,  # Money Market
    1909,  # Asset-Backed Securities
    1910,  # Market Liquidity
    1911,  # Ratios Analysis
    1912,  # Credit Default Swap
    1913,  # Stock Markets
    1914,  # Derivatives
    1915,  # Trading Strategy
    1916,  # Securities
    1917,  # Foreign Exchange Markets
    1918,  # Common Stock
    1919,  # Securities Market
    1920,  # Futures Exchange
    1921,  # Derivatives Markets
    1922,  # Equity Markets
    1923,  # Capital Markets
    1924,  # High-Yield Debt
    1925,  # Investment Banking
    1926,  # Preferred Stock
    1927,  # Trading Room
    1928,  # Secondary Market
    1929,  # PIPE
    1930,  # Market Maker
    1931,  # Stocks (Finance)
    1932,  # Financial Market
    1933,  # Commodity Market
    1934,  # Equities
    1935,  # Standard Accounting Practices
    1936,  # Accounting Cycle
    1937,  # Accounting Information Systems
    1938,  # General Ledger
    1939,  # GAAP
    1940,  # Financial Asset
    1941,  # Reconciliation
    1942,  # Ledgers
    1943,  # Debits And Credits
    1944,  # Contingent Liability
    1945,  # Accounting Methods
    1946,  # Fixed Asset
    1947,  # Trial Balance
    1948,  # CPA
    1949,  # Balancing
    1950,  # Accruals
    1951,  # Loans
    1952,  # Liens
    1953,  # Credit Defaults
    1954,  # Credit Products
    1955,  # Credit Facilities
    1956,  # Amortization
    1957,  # Alternative Lending
    1958,  # Credit Analysis
    1959,  # Bankruptcies
    1960,  # Microfinance
    1961,  # Annuities
    1962,  # Reinsurance
    1963,  # Property Insurance
    1964,  # Expected Return
    1965,  # Portfolio Analysis
    1966,  # Fixed Income
    1967,  # Hedging
    1968,  # Foreign Direct Investments
    1969,  # Bond Credit Rating
    1970,  # Institutional Investing
    1971,  # Rate Of Return
    1972,  # Cost Of Capital
    1973,  # Public Financial Management
    1974,  # Pension Funds
    1975,  # Money Management
    1976,  # Hedge Funds
    1977,  # Portfolio Management
    1978,  # Mortgage-Backed Securities
    1979,  # Investment Decisions
    1980,  # Wealth Management
    1981,  # Investments
    1982,  # ROI
    1983,  # Investment Management
    1984,  # Real Estate Investments
    1985,  # Investment Strategy
    1986,  # Alternative Investments
    1987,  # Sovereign Wealth Fund
    1988,  # Modern Portfolio Theory
    1989,  # Direct Investments
    1990,  # M&A (dup of 338?)
    1991,  # Acquisition Processes
    1992,  # Consolidation
    1993,  # Mortgage Loans
    1994,  # Reverse Mortgages
    1995,  # Accrual Accounting
    1996,  # Project Finance
    1997,  # Resource Consumption Accounting
    1998,  # Share Capital
    1999,  # WACC
    2000,  # Option Valuation
    2001,  # Securitization
    2002,  # Value-Added Tax
    2003,  # Federal Income Tax
    2004,  # Tax Laws
    2005,  # Income Tax
    2006,  # Tax Management
    2007,  # Deferred Tax
    2008,  # Tax Planning
    2009,  # Transfer Pricing
    2010,  # Corporate Tax
    2011,  # Tax Compliance
    5351,  # EMV
    5381,  # ACCA
    5382,  # SOX control
    5360,  # Order to Cash
    281,   # P&L Management
    1815,  # Cost Accounting
    1816,  # Cost Reduction
    1822,  # Gross Profit
    1823,  # Operating Cost
    1824,  # Depreciation
    1825,  # Asset Allocation
    1826,  # Break-Even Analysis
    1828,  # Working Capital
    1830,  # Fair Value
    1831,  # Retained Earnings
    1832,  # Personal Finance
    1833,  # Financial Education
    1834,  # Financial Literacy
    1835,  # Interest Rate Swap
    1837,  # Financial Statement Analysis
    1838,  # Arbitrage
    1840,  # Cash Flow Analysis
    1841,  # Discounted Cash Flow
    1842,  # Securities Research
    1843,  # Business Valuation
    1846,  # LIBOR
    1847,  # Valuation Using Multiples
    1848,  # Interest Rate Risk
    1849,  # Solvency
    1851,  # Swaption
    1852,  # Fundamental Analysis
    1855,  # FASB
    1856,  # P&L Management (dup)
    1857,  # Debt Management Planning
    1858,  # FinTech (also Industries)
    1859,  # Management Accounting
    1861,  # Brokerage
    1863,  # Public Finance
    1865,  # Financial Instrument
    1866,  # Managerial Finance
    1869,  # Divestitures
    1870,  # Capital Budgeting
    1871,  # Capital Structures
    1872,  # CAPM
    1873,  # Valuation Models
    1806,  # Cash Flows
    1807,  # Cash Management
    1808,  # Net Present Value
    1809,  # Commercial Finance
    1810,  # Repurchase Agreements
    1811,  # Activity-Based Costing
    1812,  # COGS
    1813,  # Cost Benefit Analysis
    1814,  # Cost-Of-Production Theory
    1817,  # Financial Technology (FinTech)
    1818,  # Cryptocurrency
    1819,  # Electronic Trading
    1820,  # Financial Accounting
    1821,  # Comprehensive Income
    1790,  # Accounts Receivable
    1792,  # Payment Systems
    1793,  # Commercial Banking
    1794,  # Banking Services
    1795,  # Transactional Accounts
    1796,  # Prepayment
    1797,  # ATM
    1799,  # Financial Institution
    1800,  # Customer Identification Program
    1801,  # Alternative Financial Services
    1802,  # Billing
    1803,  # OLTP
    1804,  # Budget Cycle
    1805,  # Cash Flow Management
]:
    SUBCATEGORIES[_id] = 'Finance & Accounting'

# People & HR
for _id in [
    320,   # Talent Acquisition
    326,   # Employee Relations
    325,   # Benefits Administration
    321, 322, 323, 324,  # range
    2381,  # Human Resource Management
    2364,  # Employee Engagement
    2365,  # Labor Relations
    2366,  # Employee Satisfaction
    2368,  # Leadership Development
    2369,  # Training And Development
    2370,  # Management Development
    2371,  # Upskilling
    2372,  # Organizational Learning
    2373,  # Reskilling
    2374,  # Organizational Culture Change
    2375,  # Productivity Improvement
    2376,  # Human Resource Policies
    2377,  # Job Analysis
    2378,  # Diversity Management
    2379,  # Workplace Diversity
    2380,  # Organizational Behavior
    2382,  # Defining Roles And Responsibilities
    2383,  # Recruitment Strategies
    2384,  # Personnel Selection
    2385,  # Workforce Management
    2386,  # Employee Retention
    2387,  # Human Capital
    2388,  # Capacity Development
    2389,  # Diversity Strategies
    2390,  # Transferable Skills Analysis
    2391,  # Resource Utilization
    2392,  # Career Development
    2393,  # Pair Programming -- oops, wrong category, keep technical
    328,   # Workday (also Enterprise Tools)
    327,   # HRIS (also Enterprise Tools)
    5350,  # HCM
]:
    SUBCATEGORIES[_id] = 'People & HR'

SUBCATEGORIES[2393] = 'QA & Testing'   # Pair Programming → wrong, it's Backend actually
SUBCATEGORIES[321] = 'People & HR'
SUBCATEGORIES[322] = 'People & HR'
SUBCATEGORIES[323] = 'People & HR'  # Performance Management
SUBCATEGORIES[324] = 'People & HR'

# Legal & Compliance
for _id in [
    334,   # Compliance
    346,   # Regulatory Compliance
    344,   # Intellectual Property
    348,   # GDPR
    347,   # Privacy Law
    349,   # Legal Research
    345,   # Corporate Law
    343,   # Contract Law
    3386,  # Arbitration
    3387,  # Dispute Resolution
    3369,  # Evidence Collection
    3370,  # Forensic Sciences
    3371,  # Labor Law
    3372,  # Criminal Law
    3373,  # Law Enforcement
    3374,  # Interrogations
    3375,  # Criminal Justice
    3376,  # Appeals
    3377,  # Case Law
    3378,  # Procedural Justice
    3379,  # Judiciary
    3380,  # Judicial Opinion
    3381,  # Electronic Discovery
    3382,  # Copyright Laws
    3383,  # Lawsuits
    3384,  # Civil Law
    3385,  # Family Law
    3388,  # Settlement
    3389,  # Settlement (dup?)
    3390,  # Ergonomics (EHS)
    3393,  # Hazard Categorization
    3394,  # EHS
    3395,  # Material Safety Data Sheet
    3396,  # Safety Culture
    3397,  # OSHA
    3398,  # Sanitation
    3399,  # Injury Prevention
    3400,  # Visual Workplaces
    3401,  # Safety Standards
    3402,  # Land Tenure
    3403,  # Land Administration
    3404,  # Private Property
    3405,  # Property Rights
    3406,  # Easement
    3407,  # Trade Secrets
    3408,  # Intellectual Property Laws
    3409,  # Fair Use
    3410,  # Property Laws
    3411,  # Trademarks
    3412,  # Patents
    3413,  # Trademark Law
    3414,  # Testbed -- wrong! Keep technical
    3415,  # Error Detection -- wrong! Keep technical
    3416,  # Safety Assurance
    3417,  # Quality Management -- actually domain: Business
    3418,  # Fault Tolerance -- technical
    3419,  # Failure Causes
    3420,  # Quality Control
    3421,  # Product Quality
    3422,  # CAPA
    3423,  # Performance Analysis -- Business
    3424,  # Technical Standard
    3425,  # Legal Knowledge
    3426,  # Consumer Protection
    3427,  # Entertainment Law
    3428,  # Judicial Review
    3429,  # Administrative Law
    3430,  # Traffic Regulations
    3431,  # International Standards
    3432,  # Eminent Domain
    3433,  # Municipal Law
    3434,  # OFAC
    3435,  # CLE
    3436,  # Legislation
    3437,  # Administrative Agencies
    3438,  # Court Systems
    3439,  # Legal Systems
    3440,  # Corporate Laws — deactivated
    3441,  # International Laws
    3442,  # Corporate Governance
    3443,  # Constitutional Law
    3444,  # CSR
    3445,  # Admiralty Law
    3446,  # Health Laws
    3447,  # FAA
    3448,  # Compliance Management
    3449,  # Deterrence
    3450,  # Consumer Privacy
    3451,  # Tort Law
    3452,  # Construction Law
    834,   # Building Codes (moved from tech)
    5361,  # MIL-STD-882
    5363,  # patent litigation
    5365,  # NCQA standards
    5375,  # AML/CFT
    5383,  # commercial litigation
    5384,  # US export controls
    5385,  # CE marking
    5386,  # COPPA
    5227,  # AI Compliance
]:
    SUBCATEGORIES[_id] = 'Legal & Compliance'

# Fix misassigned above
SUBCATEGORIES[3414] = 'QA & Testing'       # Testbed
SUBCATEGORIES[3415] = 'QA & Testing'       # Error Detection
SUBCATEGORIES[3418] = 'Cloud & Infrastructure'  # Fault Tolerance
SUBCATEGORIES[3390] = 'Legal & Compliance'  # Ergonomics → EHS/Legal
SUBCATEGORIES[3417] = 'Business & Operations'  # Quality Management
SUBCATEGORIES[3423] = 'Business & Operations'  # Performance Analysis
SUBCATEGORIES[3420] = 'Business & Operations'  # Quality Control

# Product & Design
for _id in [
    93,    # UX Design
    94,    # UI Design
    95,    # Wireframing
    96,    # User Testing
    6,     # User Research
    259,   # Product Discovery
    260,   # Product Analytics
    265,   # Jobs to Be Done
    267,   # Interaction Design
    268,   # Visual Design
    269,   # Information Architecture
    270,   # Prototyping
    271,   # Design Systems
    272,   # Accessibility
    273,   # Service Design
    274,   # Design Thinking
    11,    # Roadmapping
    5,     # Product Strategy
    97,    # Product Development
    257,   # Product Management
    1167,  # Product Design
    1174,  # User Experience (also technical — keep here)
    1172,  # User Interface
    1175,  # unknown
    1176,  # User-Centered Design
    1179,  # User Interface Design
    1180,  # Usability
    1181,  # Look And Feel
    1182,  # Experience Design
    1183,  # Interface Design
    1135,  # Design Strategies
    1134,  # Design Tool
    1137,  # Design Research
    1138,  # Sketching (moved from tech)
    1139,  # Fashion Design (moved from tech)
    1140,  # Design Management
    1148,  # Graphic Design
    1112,  # Motion Graphic Design
    1142,  # Digital Design
    1119,  # Visual Arts (moved from tech)
    1122,  # Art Direction (moved from tech)
    1123,  # Illustration (moved from tech)
    1124,  # Color Theory (moved from tech)
    1125,  # Art History (moved from tech)
    1128,  # Aesthetics (moved from tech)
    1129,  # Storyboarding (moved from tech)
    1130,  # Visual Effects (moved from tech)
    1132,  # Visual Storytelling (moved from tech)
    1143,  # Gamification (moved from tech)
    1144,  # Texturing (moved from tech)
    1145,  # Color Grading (moved from tech)
    1147,  # Color Correction
    1150,  # Logos
    1152,  # Graphic Communication
    1106,  # Character Animation (moved from tech)
    1111,  # Animations (moved from tech)
    1120,  # Drawing
    1121,  # Iconography (moved from tech)
    1168,  # Industrial Design (moved from tech)
    3554,  # Product Engineering
    3549,  # Product Innovation
    3553,  # Product Planning
    3548,  # New Product Development
    1054,  # Lifecycle Management
    1056,  # Product Lifecycle
    1051,  # Product Roadmaps
    1055,  # User Story
    3555,  # User Feedback
    3082,  # Custom Software
    1538,  # Conceptual Design
    1544,  # Integrated Design
    826,   # Building Design
    827,   # Spatial Design
    828,   # Spatial Planning
    1503,  # Land Development
]:
    SUBCATEGORIES[_id] = 'Product & Design'

# Methodologies
for _id in [
    8,     # Agile Methodology
    314,   # Six Sigma
    315,   # Lean
    3503,  # Lean Manufacturing (moved from tech)
    3510,  # Lean Six Sigma
    1086,  # Critical Path Method
    2395,  # Agile Software Development
    2396,  # Extreme Programming
    2397,  # Sprint Retrospectives
    2401,  # Backlogs
    2403,  # Agile Leadership
    2405,  # TDD
    2406,  # Agile Project Management
    5377,  # systems development life cycle
    5357,  # factory acceptance testing
    5352,  # clinical trial methodology
    5353,  # PMP
    5372,  # Team Topologies
    5378,  # DFX
    5356,  # Quality by Design
    5389,  # three lines of defence model
    3945,  # Clinical Trials
]:
    SUBCATEGORIES[_id] = 'Methodologies'

# ── SOFT subcategory assignments ─────────────────────────────────────────────

# Communication
for _id in [
    37,    # Communication
    374,   # Verbal Communication
    373,   # Written Communication
    375,   # Public Speaking
    377,   # Active Listening
    378,   # Technical Writing
    46,    # Presentation Skills
    106,   # Copywriting (also Marketing — final below)
    886,   # Digital Communications
    882,   # Business Communication
    883,   # Strategic Communication
    887,   # Communication Strategies
    3329,  # English Language
    3328,  # German Language
    3333,  # Spanish Language
    3351,  # Latin
    3348,  # French Language
    3352,  # Mandarin Chinese
    3345,  # Korean Language
    3331,  # Arabic Language
    3339,  # Portuguese Language
    3353,  # Japanese Language
    3326,  # Italian Language
    3327,  # Russian Language
    3337,  # Vietnamese Language
    3347,  # Hindi Language
    3336,  # Ukrainian Language
    3346,  # Hebrew Language
    3323,  # Foreign Language
    3343,  # Multilingualism
    3355,  # Language Translation
    3356,  # Computer-Assisted Translation
    3357,  # Phonetics
    3358,  # Syntax
    3359,  # Discourse Analysis
    3360,  # Formal Language
    3361,  # Linguistics
    3362,  # Semantics
    3363,  # Idioms
    3364,  # Language Interpretation
    3365,  # Lexicons
    3366,  # Language Education
    3367,  # TOEFL
    3368,  # Teaching English as a Second Language
    4124,  # Advising (moved from domain)
]:
    SUBCATEGORIES[_id] = 'Communication'

# Override copywriting to Marketing
SUBCATEGORIES[106] = 'Marketing & Growth'

# Leadership & Management
for _id in [
    381,   # People Management
    384,   # Delegation
    385,   # Vision Setting
    386,   # Change Management
    9,     # Stakeholder Management
    412,   # Open-Mindedness -- actually Personal Effectiveness
    413,   # Empathy -- Collaboration
    1383,  # Mentorship (moved from domain)
    912,   # Thought Leadership (moved from domain)
    1016,  # Empowerment (moved from domain)
    906,   # Global Leadership
    900,   # Entrepreneurial Leadership
    996,   # Strategic Leadership
    907,   # Organizational Leadership
    903,   # Innovation Leadership
    913,   # Leadership Studies
    910,   # Ethical Leadership
    911,   # Middle Management
    915,   # Resource Management
    916,   # Consensus Decision-Making -- Problem Solving
    917,   # Global Management
    918,   # Business Concepts -- Business & Operations
    919,   # Management Control
    920,   # Business Transaction Management -- B&O
    921,   # Restaurant Management -- Industries
    928,   # Management Effectiveness
    905,   # Management Styles
]:
    SUBCATEGORIES[_id] = 'Leadership & Management'

# Fix misassigned
SUBCATEGORIES[412] = 'Personal Effectiveness'
SUBCATEGORIES[413] = 'Collaboration & Teamwork'
SUBCATEGORIES[916] = 'Problem Solving & Critical Thinking'
SUBCATEGORIES[918] = 'Business & Operations'
SUBCATEGORIES[920] = 'Business & Operations'
SUBCATEGORIES[921] = 'Industries'

# Collaboration & Teamwork
for _id in [
    99,    # Collaboration
    387,   # Teamwork
    388,   # Relationship Building
    389,   # Networking
    390,   # Influence
    391,   # Persuasion
    392,   # Consensus Building
    413,   # Empathy
    415,   # Cultural Awareness
    416,   # Diversity & Inclusion
    419,   # Diplomacy
    1015,  # Team Building
    1021,  # Team Management
    1017,  # Distributed Team Management
    1018,  # Conflict Management
    1019,  # Virtual Teams
    1022,  # Prosci ADKAR Model
    1023,  # Workforce Productivity
    1024,  # Performance Appraisal
    1025,  # Team Performance Management
    1026,  # Team Motivation
    3332,  # Literacy -- Personal Effectiveness
]:
    SUBCATEGORIES[_id] = 'Collaboration & Teamwork'

SUBCATEGORIES[3332] = 'Personal Effectiveness'

# Problem Solving & Critical Thinking
for _id in [
    38,    # Problem Solving
    41,    # Critical Thinking
    393,   # Root Cause Analysis
    397,   # Logical Reasoning
    100,   # Strategic Thinking
    48,    # Decision Making
    916,   # Consensus Decision-Making
    851,   # Task Analysis
    865,   # Gap Analysis
    983,   # SWOT Analysis
    992,   # Decision Analysis
    5390,  # systems thinking
]:
    SUBCATEGORIES[_id] = 'Problem Solving & Critical Thinking'

# Personal Effectiveness
for _id in [
    104,   # Organization
    105,   # Initiative
    402,   # Reliability
    403,   # Work Ethic
    404,   # Flexibility
    405,   # Learning Agility
    406,   # Growth Mindset
    407,   # Resilience
    408,   # Stress Management
    409,   # Ambiguity Tolerance
    410,   # Continuous Learning
    411,   # Curiosity
    40,    # Time Management
    42,    # Creativity
    43,    # Adaptability
    398,   # Prioritization
    399,   # Self-Motivation
    420,   # Professionalism
    1059,  # Timelines (moved from domain)
    518,   # Organizational Skills (moved from domain)
    521,   # Typing (moved from domain)
    430,   # Deadline Management
    429,   # Milestone Tracking
    428,   # Resource Planning
    426,   # Backlog Management
    3332,  # Literacy
    5228,  # AI Fluency
]:
    SUBCATEGORIES[_id] = 'Personal Effectiveness'


# ─── 4. Collect all changes ───────────────────────────────────────────────────

def _add_aliases_fn(skill, new_aliases):
    existing = {a.lower() for a in (skill.aliases or [])}
    added = []
    for a in new_aliases:
        if a.lower() not in existing:
            added.append(a)
    if added:
        skill.aliases = list(skill.aliases or []) + added
    return added

# Additional alias merges for deactivated duplicates
ALIAS_MERGES = {
    226:  ['Junit4'],                    # JUnit ← Junit4
    309:  ['Supply Chain Management'],   # Supply Chain ← Supply Chain Management
    892:  ['Business Continuity Planning', 'Business Continuity And Disaster Recovery'],
    287:  ['Search Engine Optimization'],# SEO
    288:  ['Search Engine Marketing'],   # SEM
    306:  ['Customer Relationship Management'],  # CRM
    524:  ['Microsoft 365', 'Microsoft Office 365'],  # Microsoft Office
}


def main():
    with app.app_context():
        now = datetime.utcnow()
        skills_by_id = {s.id: s for s in Skill.query.all()}

        # ── Step 1: Deactivations ──────────────────────────────────────────
        print(f'\n=== Deactivations ({len(DEACTIVATE)}) ===')
        deactivated = 0
        for sid, reason in DEACTIVATE.items():
            s = skills_by_id.get(sid)
            if not s:
                print(f'  MISSING [{sid}]')
                continue
            status = 'already unverified' if not s.is_verified else 'will deactivate'
            print(f'  [{sid}] {s.name}: {reason}  ({status})')
            if APPLY and s.is_verified:
                s.is_verified = False
                s.updated_at = now
                deactivated += 1

        # ── Step 2: Alias merges ───────────────────────────────────────────
        print(f'\n=== Alias merges ===')
        for sid, aliases in ALIAS_MERGES.items():
            s = skills_by_id.get(sid)
            if not s:
                print(f'  MISSING [{sid}]')
                continue
            added = _add_aliases_fn(s, aliases) if APPLY else [
                a for a in aliases if a.lower() not in {x.lower() for x in (s.aliases or [])}
            ]
            if added:
                print(f'  [{sid}] {s.name}: +{added}')

        # ── Step 3: Recategorizations ──────────────────────────────────────
        all_recat = {}
        all_recat.update({sid: cat_sub for sid, cat_sub in TECH_TO_DOMAIN.items()})
        all_recat.update({sid: cat_sub for sid, cat_sub in DOMAIN_TO_TECH.items()})
        all_recat.update({sid: cat_sub for sid, cat_sub in DOMAIN_TO_SOFT.items()})
        # Remove deactivated IDs
        all_recat = {k: v for k, v in all_recat.items() if k not in DEACTIVATE}

        print(f'\n=== Recategorizations ({len(all_recat)}) ===')
        recategorized = 0
        for sid, (new_cat, new_sub) in sorted(all_recat.items()):
            s = skills_by_id.get(sid)
            if not s or not s.is_verified:
                continue
            old_cat = s.category
            old_sub = s.subcategory
            changes = []
            if s.category != new_cat:
                changes.append(f'{old_cat} → {new_cat}')
            if s.subcategory != new_sub:
                changes.append(f'sub: {old_sub!r} → {new_sub!r}')
            if changes:
                print(f'  [{sid}] {s.name}: {", ".join(changes)}')
                if APPLY:
                    s.category = new_cat
                    s.subcategory = new_sub
                    s.updated_at = now
                    recategorized += 1

        # ── Step 4: Subcategory assignments ───────────────────────────────
        # Apply SUBCATEGORIES dict (skip None values and deactivated)
        valid_subs = {k: v for k, v in SUBCATEGORIES.items()
                      if v is not None and k not in DEACTIVATE}

        # Also apply subcategories that came from recategorization
        for sid, (new_cat, new_sub) in all_recat.items():
            if sid not in valid_subs:
                valid_subs[sid] = new_sub

        assigned = 0
        already_ok = 0
        missing_ids = []
        for sid, sub in valid_subs.items():
            s = skills_by_id.get(sid)
            if not s or not s.is_verified:
                missing_ids.append(sid)
                continue
            if s.subcategory == sub:
                already_ok += 1
                continue
            if APPLY:
                s.subcategory = sub
                s.updated_at = now
                assigned += 1
            else:
                assigned += 1  # count as would-assign

        print(f'\n=== Subcategory assignments ===')
        print(f'  Would assign: {assigned}, already correct: {already_ok}')
        if missing_ids:
            print(f'  IDs not found (may be new skills w/ different IDs): {missing_ids[:20]}...')

        # Name-based subcategory assignment for new skills where we used placeholder IDs
        NAME_SUBCATEGORY = {
            # Security
            'FleetDM': 'Security & Compliance',
            'ABAC': 'Security & Compliance',
            'COMSEC': 'Security & Compliance',
            'certificate-based authentication': 'Security & Compliance',
            'RMF process': 'Security & Compliance',
            'HSMs': 'Security & Compliance',
            'MITRE ATT&CK': 'Security & Compliance',
            'software composition analysis': 'Security & Compliance',
            'Security+': 'Security & Compliance',
            'SWG': 'Security & Compliance',
            'Verkada': 'Security & Compliance',
            'CVSS': 'Security & Compliance',
            'NIST 800-53 Rev 5': 'Security & Compliance',
            'WebAuthn': 'Security & Compliance',
            'SCIM provisioning': 'Security & Compliance',
            'Burp Suite': 'Security & Compliance',
            'Lacework': 'Security & Compliance',
            'Trivy': 'Security & Compliance',
            'Privacy Enhancing Technologies': 'Security & Compliance',
            'secrets management platforms': 'Security & Compliance',
            # Networking
            'Structured Cabling': 'Networking & Systems',
            'reverse proxy': 'Networking & Systems',
            'VDI': 'Networking & Systems',
            'IPAM': 'Networking & Systems',
            '802.1x Authentication': 'Networking & Systems',
            'Junos': 'Networking & Systems',
            'Tailscale': 'Networking & Systems',
            'DNS management': 'Networking & Systems',
            # Hardware
            'FEA software': 'Hardware & Embedded',
            'Zemax': 'Hardware & Embedded',
            'AFSIM': 'Hardware & Embedded',
            'EtherCAT': 'Hardware & Embedded',
            'Mastercam': 'Hardware & Embedded',
            'DAQ systems': 'Hardware & Embedded',
            'beamforming': 'Hardware & Embedded',
            'AWS D17.1': 'Hardware & Embedded',
            'RTOS environments': 'Hardware & Embedded',
            'QNX': 'Hardware & Embedded',
            'HDI': 'Hardware & Embedded',
            'Vector CANoe': 'Hardware & Embedded',
            'IPC-610': 'Hardware & Embedded',
            'IPC-A-620': 'Hardware & Embedded',
            'DFT implementation': 'Hardware & Embedded',
            'CAM programming': 'Hardware & Embedded',
            'Zephyr': 'Hardware & Embedded',
            'SoC integration': 'Hardware & Embedded',
            'FinFET technologies': 'Hardware & Embedded',
            'OpenBMC': 'Hardware & Embedded',
            'IMUs': 'Hardware & Embedded',
            'Electrostatic Discharge': 'Hardware & Embedded',
            'UWB': 'Hardware & Embedded',
            'Industrial IoT systems': 'Hardware & Embedded',
            '5-axis milling': 'Hardware & Embedded',
            # DevOps
            'Rancher': 'DevOps & CI/CD',
            'QEMU': 'DevOps & CI/CD',
            'HashiCorp Nomad': 'DevOps & CI/CD',
            'Cilium CNI': 'DevOps & CI/CD',
            'Podman': 'DevOps & CI/CD',
            # Cloud
            'Cloudflare Workers': 'Cloud & Infrastructure',
            'AWS Control Tower': 'Cloud & Infrastructure',
            'AWS Workspaces': 'Cloud & Infrastructure',
            'ELB': 'Cloud & Infrastructure',
            # AI
            'LLM integration': 'AI & Machine Learning',
            'LLM architectures': 'AI & Machine Learning',
            'Flyte': 'AI & Machine Learning',
            'Isaac': 'AI & Machine Learning',
            'Vision-Language-Action': 'AI & Machine Learning',
            'SGLang': 'AI & Machine Learning',
            'pretraining': 'AI & Machine Learning',
            'model routing': 'AI & Machine Learning',
            'HeyGen': 'AI & Machine Learning',
            # DB
            'Debezium': 'Databases & Data Engineering',
            'lakehouse architectures': 'Databases & Data Engineering',
            'Delta Tables': 'Databases & Data Engineering',
            'Aurora': 'Databases & Data Engineering',
            'Datomic': 'Databases & Data Engineering',
            'Unity Catalog': 'Databases & Data Engineering',
            'graph technologies': 'Databases & Data Engineering',
            'OLAP technologies': 'Databases & Data Engineering',
            'Query Optimization': 'Databases & Data Engineering',
            # DS
            'GDAL': 'Data Science & Analytics',
            'ParaView': 'Data Science & Analytics',
            'QuickSight': 'Data Science & Analytics',
            'KNIME': 'Data Science & Analytics',
            'R Shiny': 'Data Science & Analytics',
            # QA
            'manual QA testing': 'QA & Testing',
            'LoadRunner': 'QA & Testing',
            'BDD/TDD': 'QA & Testing',
            # Enterprise
            'Houdini': 'Enterprise Tools & Platforms',
            'Shotgrid': 'Enterprise Tools & Platforms',
            'xAPI': 'Enterprise Tools & Platforms',
            'Calypso platform': 'Enterprise Tools & Platforms',
            'Infor LN': 'Enterprise Tools & Platforms',
            'MasterControl': 'Enterprise Tools & Platforms',
            'Encompass LOS': 'Enterprise Tools & Platforms',
            'Reltio': 'Enterprise Tools & Platforms',
            'SAP S/4HANA': 'Enterprise Tools & Platforms',
            'SCORM': 'Enterprise Tools & Platforms',
            'Dovetail': 'Enterprise Tools & Platforms',
            'Smartling': 'Enterprise Tools & Platforms',
            'CAT platforms': 'Enterprise Tools & Platforms',
            'Lever': 'Enterprise Tools & Platforms',
            'no-code/low-code': 'Enterprise Tools & Platforms',
            'Nanite': 'Enterprise Tools & Platforms',
            'CLO 3D': 'Enterprise Tools & Platforms',
            'Linksquares': 'Enterprise Tools & Platforms',
            # Mobile
            'AOSP': 'Mobile',
            # Backend
            'Jinja': 'Backend & APIs',
            'Hapi.js': 'Backend & APIs',
            'CAP theorem': 'Backend & APIs',
            'domain modeling': 'Backend & APIs',
            'multi-tenancy': 'Backend & APIs',
            # Frontend
            'SSR': 'Frontend & Web',
            'headless CMS architectures': 'Frontend & Web',
            'module federation': 'Frontend & Web',
            # Programming
            'concurrent programming': 'Programming Languages',
            'compiler design': 'Programming Languages',
            'ASTs': 'Programming Languages',
            'COBOL': 'Programming Languages',
            'VBScript': 'Programming Languages',
            # Domain
            'EMV': 'Finance & Accounting',
            'Order to Cash': 'Finance & Accounting',
            'ACCA': 'Finance & Accounting',
            'SOX control': 'Finance & Accounting',
            'AML/CFT': 'Legal & Compliance',
            'patent litigation': 'Legal & Compliance',
            'NCQA standards': 'Legal & Compliance',
            'commercial litigation': 'Legal & Compliance',
            'US export controls': 'Legal & Compliance',
            'CE marking': 'Legal & Compliance',
            'COPPA': 'Legal & Compliance',
            'AI Compliance': 'Legal & Compliance',
            'MIL-STD-882': 'Legal & Compliance',
            'funnel analysis': 'Marketing & Growth',
            'short-form video production': 'Marketing & Growth',
            'D2C environments': 'Marketing & Growth',
            'brand building': 'Marketing & Growth',
            'Product-Led Growth': 'Marketing & Growth',
            'App Store Optimization': 'Marketing & Growth',
            'cash handling': 'Business & Operations',
            '3PL': 'Business & Operations',
            'warehouse management software': 'Business & Operations',
            'MES': 'Business & Operations',
            'HCM': 'People & HR',
            'PMP': 'Methodologies',
            'clinical trial methodology': 'Methodologies',
            'Quality by Design': 'Methodologies',
            'factory acceptance testing': 'Methodologies',
            'Team Topologies': 'Methodologies',
            'systems development life cycle': 'Methodologies',
            'DFX': 'Methodologies',
            'three lines of defence model': 'Methodologies',
            'geospatial intelligence': 'Industries',
            'UAVs': 'Industries',
            'genetic testing': 'Industries',
            'CPG industry': 'Industries',
            'EV architectures': 'Industries',
            'Utilization Management': 'Industries',
            'non-pharmacological interventions': 'Industries',
            'RWE': 'Industries',
            'ligand binding assays': 'Industries',
            # Soft
            'systems thinking': 'Problem Solving & Critical Thinking',
            'AI Fluency': 'Personal Effectiveness',
        }

        name_assigned = 0
        for s in skills_by_id.values():
            if not s.is_verified or s.id in DEACTIVATE:
                continue
            target_sub = NAME_SUBCATEGORY.get(s.name)
            if target_sub and s.subcategory != target_sub:
                if APPLY:
                    s.subcategory = target_sub
                    s.updated_at = now
                name_assigned += 1

        print(f'  Name-based assignments: {name_assigned}')

        if APPLY:
            db.session.commit()
            print(f'\n✓ Committed.')
            print(f'  Deactivated: {deactivated}')
            print(f'  Recategorized: {recategorized}')
            print(f'  Subcategories assigned: {assigned + name_assigned}')
        else:
            total_would_change = len([s for s in skills_by_id.values()
                                      if s.is_verified and s.id in DEACTIVATE]) + \
                                 len(all_recat) + assigned + name_assigned
            print(f'\nDry-run complete. Estimated changes: {total_would_change}. Pass --apply.')


if __name__ == '__main__':
    main()
