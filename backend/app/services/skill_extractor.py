# backend/app/services/skill_extractor.py

import re
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup
from app.models import db, Skill

# ============================================
# SKILL BLACKLIST - Words that should never be skills
# ============================================
SKILL_BLACKLIST = {
    # Common words falsely matched
    'here', 'there', 'where', 'what', 'when', 'which', 'this', 'that',
    'with', 'from', 'have', 'been', 'were', 'being', 'would', 'could',
    'should', 'will', 'just', 'also', 'very', 'much', 'many', 'some',
    'other', 'into', 'over', 'such', 'only', 'then', 'them', 'these',
    'more', 'most', 'made', 'make', 'well', 'back', 'even', 'want',
    'because', 'each', 'said', 'does', 'got', 'about', 'after', 'before',
    
    # Generic resume words
    'use', 'used', 'using', 'work', 'worked', 'working',
    'company', 'team', 'teams', 'role', 'roles',
    'experience', 'experienced', 'experiences',
    'responsible', 'responsibilities', 'responsibility',
    'including', 'include', 'includes', 'included',
    'various', 'ability', 'able', 'abilities',
    'strong', 'excellent', 'good', 'great', 'best', 'better',
    'help', 'helped', 'helping', 'support', 'supported', 'supporting',
    'ensure', 'ensured', 'ensuring',
    'provide', 'provided', 'providing',
    'maintain', 'maintained', 'maintaining',
    
    # Too generic without context
    'manage', 'managed', 'management', 'manager', 'managing',
    'develop', 'developed', 'developing', 'development',
    'create', 'created', 'creating', 'creation',
    'build', 'built', 'building',
    'lead', 'led', 'leading', 'leader',
    
    # Time-related
    'year', 'years', 'month', 'months', 'day', 'days', 'week', 'weeks',
    'daily', 'weekly', 'monthly', 'yearly', 'annual', 'annually',
    
    # Generic adjectives
    'new', 'first', 'last', 'next', 'high', 'low', 'top', 'key',
    'part', 'full', 'time', 'based', 'level', 'senior', 'junior',
    'multiple', 'several', 'different', 'specific', 'current',
    
    # Common verbs
    'implement', 'implemented', 'implementing',
    'improve', 'improved', 'improving',
    'increase', 'increased', 'increasing',
    'reduce', 'reduced', 'reducing',
    'achieve', 'achieved', 'achieving',
    
    # Filler words
    'highly', 'effectively', 'efficiently', 'successfully',
    
    # Test/garbage data patterns
    'test_domain knowledge', 'test_soft skills', 
    'testdomainskill', 'brandnewskill999', 'newtestskill123',
    'there you go', 'here we go', 'and so on',
    'test', 'testing123', 'asdf', 'qwerty',
    'foo', 'bar', 'baz', 'lorem', 'ipsum',
}

# Known acronyms that should stay uppercase
SKILL_ACRONYMS = {
    # Programming & Data
    'sql', 'aws', 'gcp', 'api', 'apis', 'html', 'css', 'js', 'ui', 'ux',
    'php', 'xml', 'json', 'yaml', 'csv', 'npm', 'cdn', 'dom',
    
    # DevOps & Infrastructure  
    'ci', 'cd', 'qa', 'vpc', 'ec2', 's3', 'rds', 'eks', 'ecs', 'iam',
    'sns', 'sqs', 'ssl', 'tls', 'ssh', 'ftp', 'tcp', 'ip', 'dns', 'http', 'https',
    
    # AI/ML
    'ml', 'ai', 'nlp', 'llm', 'gpt', 'cv',
    
    # Business
    'etl', 'crm', 'erp', 'saas', 'paas', 'iaas', 'bi',
    'kpi', 'okr', 'roi', 'b2b', 'b2c', 'seo', 'sem', 'ppc',
    
    # Auth & Security
    'jwt', 'oauth', 'sso', 'sdk', 'ide', 'orm', 'mvc', 'mvp',
    
    # Other
    'ios', 'nosql', 'css3', 'html5', 'es6', 'rest', 'graphql',
    'ab',  # For A/B testing
}

# Special casing rules - exact replacements
SPECIAL_CASING = {
    # JavaScript ecosystem
    'javascript': 'JavaScript',
    'typescript': 'TypeScript',
    'nodejs': 'Node.js',
    'node.js': 'Node.js',
    'reactjs': 'React.js',
    'react.js': 'React.js',
    'react': 'React',
    'vuejs': 'Vue.js',
    'vue.js': 'Vue.js',
    'vue': 'Vue',
    'angular': 'Angular',
    'angularjs': 'AngularJS',
    'nextjs': 'Next.js',
    'next.js': 'Next.js',
    'expressjs': 'Express.js',
    'express.js': 'Express.js',
    'nuxtjs': 'Nuxt.js',
    'nuxt.js': 'Nuxt.js',
    
    # Databases
    'postgresql': 'PostgreSQL',
    'postgres': 'PostgreSQL',
    'mongodb': 'MongoDB',
    'mysql': 'MySQL',
    'sqlite': 'SQLite',
    'dynamodb': 'DynamoDB',
    'mariadb': 'MariaDB',
    'couchdb': 'CouchDB',
    'neo4j': 'Neo4j',
    'redis': 'Redis',
    
    # Cloud & DevOps
    'github': 'GitHub',
    'gitlab': 'GitLab',
    'bitbucket': 'Bitbucket',
    'devops': 'DevOps',
    'devsecops': 'DevSecOps',
    'jenkins': 'Jenkins',
    'kubernetes': 'Kubernetes',
    'docker': 'Docker',
    'dockerfile': 'Dockerfile',
    'terraform': 'Terraform',
    'ansible': 'Ansible',
    
    # AI/ML
    'tensorflow': 'TensorFlow',
    'pytorch': 'PyTorch',
    'scikit-learn': 'scikit-learn',
    'sklearn': 'scikit-learn',
    'opencv': 'OpenCV',
    'openai': 'OpenAI',
    'chatgpt': 'ChatGPT',
    'numpy': 'NumPy',
    'pandas': 'pandas',
    'scipy': 'SciPy',
    'matplotlib': 'Matplotlib',
    
    # Languages
    'python': 'Python',
    'java': 'Java',
    'golang': 'Go',
    'ruby': 'Ruby',
    'rust': 'Rust',
    'kotlin': 'Kotlin',
    'scala': 'Scala',
    'perl': 'Perl',
    'r': 'R',
    'c++': 'C++',
    'c#': 'C#',
    'csharp': 'C#',
    
    # Microsoft
    'powerpoint': 'PowerPoint',
    'powerbi': 'Power BI',
    'power bi': 'Power BI',
    'sharepoint': 'SharePoint',
    'linkedin': 'LinkedIn',
    'outlook': 'Outlook',
    'onenote': 'OneNote',
    'azure': 'Azure',
    'dotnet': '.NET',
    '.net': '.NET',
    
    # Apple
    'ios': 'iOS',
    'macos': 'macOS',
    'watchos': 'watchOS',
    'tvos': 'tvOS',
    'xcode': 'Xcode',
    'swift': 'Swift',
    'objective-c': 'Objective-C',
    
    # Testing & Methodology
    'a/b testing': 'A/B Testing',
    'ab testing': 'A/B Testing',
    'ci/cd': 'CI/CD',
    'cicd': 'CI/CD',
    'agile/scrum': 'Agile/Scrum',
    'agile': 'Agile',
    'scrum': 'Scrum',
    'kanban': 'Kanban',
    
    # Business terms
    'go-to-market': 'Go-to-Market',
    'gtm': 'GTM',
    
    # Other
    'graphql': 'GraphQL',
    'firebase': 'Firebase',
    'webpack': 'Webpack',
    'eslint': 'ESLint',
    'prettier': 'Prettier',
    'makefile': 'Makefile',
    'linux': 'Linux',
    'unix': 'Unix',
    'bash': 'Bash',
    'git': 'Git',
    'jira': 'Jira',
    'confluence': 'Confluence',
    'figma': 'Figma',
    'sketch': 'Sketch',
    'photoshop': 'Photoshop',
    'illustrator': 'Illustrator',
}

# Words that should stay lowercase in titles
LOWERCASE_WORDS = {
    'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 
    'to', 'from', 'by', 'with', 'in', 'of', 'as', 'is', 'vs',
}


def _title_case_word(word: str) -> str:
    """
    Title case a single word, preserving internal caps for camelCase.
    """
    if not word:
        return word
    
    if word.isupper():
        return word.capitalize()
    
    return word[0].upper() + word[1:]


# ============================================
# SECTION PARSING
# ============================================

SECTION_PATTERNS = {
    'requirements': [
        r"(?:basic |minimum )?(?:requirements|qualifications)",
        r"what you['']?ll need(?: to succeed)?",
        r"what we['']?re looking for",
        r"what you bring",
        r"you (?:should |must |will )?have",
        r"we['']?re looking for someone",
        r"required(?: skills| experience| qualifications)?",
        r"must[- ]have(?:s)?",
        r"key skills",
        r"who you are",
        r"about you",
        r"your background",
        r"experience(?: required)?",
        r"skills (?:and|&) (?:experience|qualifications)",
        r"what you need",
        r"(?:an )?ideal candidate(?:s)?(?:['']s)?(?: should| must| will)?(?: have)?",
        r"your profile",
        r"your qualifications",
        r"your expertise",
        r"(?:minimum|basic) qualifications",
        r"you['']?re a (?:great |strong |good )?fit",
        r"what you['']ll bring",
        r"the right candidate",
        r"what we look for",
        r"what we require(?:d)?",
        r"you (?:may |might )?(?:be a good fit|thrive in this role) if(?: you)?",
        r"you should apply if",
        r"what we['']?re looking for(?: \(.*?\))?",
        r"who you are(?: \(.*?\))?",
        # Parenthetical requirements — e.g. "What you'll need to thrive (Requirements)"
        r".{5,60}\((?:requirements?|qualifications?|must[- ]haves?)\)",
        # Figma-style
        r"we['']?d love to hear from you if",
        r"we['']?re looking for someone who",
        # Cloudflare-style — "Required Skills & Qualifications" / "Experiences might include"
        r"required skills(?: [&/] qualifications?)?",
        r"experiences? (?:might |may |could )?include",
        # On Running-style
        r"your story",
        # Okta-style
        r"what you['']?ll bring to the role",
        # Roku-style
        r"we['']?re excited if you have",
        # Notion-style
        r"skills? you['']?ll need to bring",
        # Whatnot-style — "As our next X you should have"
        r"as our next .{0,40} you should",
        # Healthcare / One Medical
        r"education(?:,? licenses?,?)?(?: and .+)? required",
        r"(?:licenses?|certifications?) required",
        r"an ideal candidate should have",
        r"what we are looking for",
        r"you (?:may |might )?(?:be a (?:great |strong |good )?fit|thrive)(?: if| in this role)?",
        r"technical skills",
        r"what success looks like",
        r"what you will need",
        r"what you love about",
        r"qualities that make (?:\w+ )?candidates?",
        r"you(?:['']ll| will) need to (?:have|bring)",
        r"job requirements?",
        r"position requirements?",
        r"what we expect from you",
        r"what we['']?re looking for(?: in you)?",
        r"what you['']?ll bring(?: to the (?:role|team|table))?",
        r"minimum requirements?",
        r"(?:required|necessary) (?:skills?|experience|qualifications?|background)",
        r"to be successful(?: in this role)?",
        r"to thrive in this role",
        r"we['']?re looking for someone with",
        r"the successful candidate",
        r"at a minimum(?:,)? you(?:['']?ll| will)? need",
        r"minimum(?:,)? you(?:['']?ll| will)? need",
        r"(?:core|key|required|essential|critical) competencies",
        r"essential criteria",
        r"must be able to",
        r"candidates? must have",
        r"you must have",
        # "Skills we're/you're looking for" variants
        r"skills we['']?re looking for",
        r"who we(?:['']?re| are) looking for",
        r"whom we(?:['']?re| are) looking for",
        r"what we(?:['']?re| are) looking for",
        r"what we need",
        r"we(?:['']?re| are| were) looking for",
        # "You bring" / "What you bring" variants
        r"what you will bring(?: to the (?:role|table|team))?",
        r"what you will bring",
        r"you(?:['']?ll)? bring these qualifications",
        r"the skillset you(?:['']?ll)? bring",
        r"the experience you(?:['']?ll)? bring",
        r"you bring",
        # Experience / background sections
        r"your experience",
        r"background (?:&|and) requirements?",
        r"education (?:and|&|and\/or|/) (?:experience|requirements?)",
        r"education\/experience",
        # Candidate profile variants
        r"our ideal candidate",
        r"the ideal candidate",
        r"candidate profile",
        r"ideal candidate profile",
        r"what skills do (?:i|you) need",
        r"what are we looking for",
        r"the basics you(?:['']?ll)? need",
        r"the experience you(?:['']?ll)? need",
        r"skills you(?:['']?ll| will)? need",
        r"you(?:['']?ll)? be set up for success if you have",
        r"(?:a )?perfect fit for you if",
        r"(?:this (?:role|position|opportunity) (?:is|could be) )?a perfect fit",
        r"this (?:role|position) (?:is|would be) (?:a )?(?:great|perfect) fit(?: for you)?",
        r"who we think will be a great fit",
        r"what makes you a (?:good|great) fit",
        r"you['']?(?:ll|d) be (?:a |an )?(?:great|good|strong|ideal|perfect) (?:addition|fit|candidate)",
        r"you['']?re (?:a |an )?(?:great|good|strong|ideal|perfect) fit if",
        # Portuguese/Spanish (common in multi-market JDs)
        r"requisitos",
        # Remaining patterns from fallback audit
        r"minimum(?: job)? qualifications?",
        r"minimum(?: required)? (?:knowledge,? skills?,? (?:and|&) abilities|requirements?)",
        r"education,? experience,? (?:and|&) skills?",
        r"education,? experience(?: &|/) skills?(?: requirements?)?",
        r"skills? you(?:['']?ll)? bring",
        r"what you should bring(?: with you)?",
        r"who are we looking for",
        r"what we(?:['']?ll| will) expect from you",
        r"ideal profile",
        r"the ideal profile",
        r"some things we(?:['']?re| are) looking for",
        r"skills?\s*\+\s*experience",
        r"you\s*\(?must[- ]haves?\)?",
        r"you need to have",
        r"core experience",
        r"the basics you bring",
        r"be a great fit if you bring",
        r"role requirements?(?: [-–] (?:skills?|experience|qualifications?))?",
        r"other experience (?:&|and) requirements?",
        r"skills? you must have",
        r"the ideal match",
        r"who we need",
        r"what do we need from you",
        r"you(?:(?:'re| are| might be| may be)) a (?:good|great) fit if you have",
        r"skill requirements?(?:\s*[-–]\s*essential)?",
        r"as part of (?:the journey|this role),? we(?:['']?d| would) expect you to",
        r"background$",
        r"minimum required(?: qualifications?)?",
        r"education and (?:general |minimum )?(?:experience|qualifications?)",
        r"key success criteria",
        r"what we expect(?! from)",
        r"what will you bring(?: to the (?:team|role|table))?",
        r"the experience you will bring",
        r"you could be (?:a |an )?(?:great|good|strong|ideal|perfect) fit if",
        # Additional patterns from full-scan fallback audit
        r"success in this role looks like",
        r"factors for success",
        r"your skills and experience",
        r"the required profile",
        r"minimum education(?: &|,? and|/) experience",
        r"what do you bring(?: to the table)?",
        r"to apply,? you(?:['']?ll| must)? (?:need to |must )?have",
        r"why you(?:['']?d|['']?ll| would| will) be a (?:great|good|strong) fit",
        r"skills you (?:will|would) need to be successful",
        r"you possess",
        r"(?:knowledge,? skills?,? (?:and|&) abilities)(?: for (?:the )?(?:role|position|success))?$",
        r"specific experience we(?:['']?re| are) seeking",
        r"what we think you(?:['']?ll| will) need",
        r"candidate requirements?",
        r"minimum$",
        r"who should apply",
        r"what you(?:['']?ve| have)(?: to offer)?",
        r"what you(?:['']?re| are) bringing",
    ],
    'preferred': [
        r"(?:preferred|desired)(?: skills?| experience| qualifications?| background)?",
        r"nice[- ]to[- ]have",
        r"bonus(?: points)?",
        r"it['']?s (?:great|nice|a plus) if",
        r"strong candidates",
        r"a\s+plus",
        r"extra credit",
        r"additional(?: desired)? (?:skills?|qualifications?)",
        r"even better if",
        r"bonus if you have",
        r"ideally you",
        r"these qualifications would be nice to have",
        r"what (?:will|would|makes?) (?:you )?(?:make you )?stand out",
        r"what sets you apart",
        r"what makes you a great fit",
        # Parenthetical preferred — e.g. "What will help you stand out (Nonessential Skills/Nice to Haves)"
        r".{5,60}\((?:preferred|desired|nice[- ]to[- ]haves?|nonessential|bonus)\)",
        # Figma-style
        r"(?:while )?not required,?.{0,30}(?:plus|bonus|added)",
        r"it['']?s an (?:added )?plus if",
        r"it['']?s a (?:big )?plus if",
        # Okta-style
        r"and extra credit if",
        # "Nice to Haves" (plural)
        r"nice[- ]to[- ]haves?",
        r"bonus points? for",
        r"would be (?:a plus|great|ideal) if",
        r"(?:preferred|desired) but not required",
        r"recommended qualifications?",
        r"preferred (?:skills?|experience|qualifications?|background)",
        r"preferred skills? and experience",
        r"strongly preferred",
        r"highly desired",
        r"great if you(?:['']?d)? (?:also )?have",
        r"we['']?d (?:love|prefer)(?: it)? if you(?:['']?d)? (?:also )?have",
        r"an? (?:added )?bonus if you(?:['']?d)? (?:also )?have",
        r"ideal candidate (?:profile|will possess|should also)",
        r"additional differentiators?",
        r"additional differentiators?",
        r"desired skills?(?: and| &| \+)? experience",
        r"desired skills? and experience",
        r"preferred experience",
        r"preferred experience and qualifications?",
        r"ideal skills? and experience",
        r"(?:examples of )?(?:desirable|desired) skills?,? knowledge,? (?:and|&) experience",
        r"advantageous",
        r"what (?:will|would) make you a (?:good|great) fit",
        # Portuguese/Spanish
        r"diferenciais",
        r"diferencial",
    ],
    'responsibilities': [
        r"(?:key )?responsibilities",
        r"what you['']?ll (?:do|be doing|work on|own|get to do)(?: \(.*?\))?",
        r"in this role,? you",
        r"your (?:day[- ]to[- ]day|impact)",
        r"you will(?:\.\.\.)?",
        r"the (?:opportunity|impact you will have)",
        r"areas of focus",
        r"about the role",
        r"role overview",
        r"job description",
        r"position overview",
        r"the impact you(?:'?ll| will) have",
        r"a day in the life",
        r"your mission",
        r"what you['']?ll achieve",
        # Parenthetical responsibilities
        r".{5,60}\(responsibilities\)",
        r"the role",
        r"about the job",
        r"how to be successful in this role",
        r"your responsibilities",
        r"(?:job|position|role) summary",
        r"the opportunity",
        r"what you will do",
        r"what you['']?ll be doing",
        r"job responsibilities",
        r"primary responsibilities",
        r"core responsibilities",
        r"essential (?:functions|duties|responsibilities)",
        r"duties (?:and|&) responsibilities",
    ],
    'about_company': [
        r"about (?:us|the company|the team|our company|our mission)",
        r"who we are",
        r"our (?:mission|vision|culture|values|story)",
        r"why (?:join|work)",
        r"the team",
        r"company overview",
        r"about this team",
    ],
    'benefits': [
        r"(?:benefits|perks|compensation|total rewards)",
        r"what we offer",
        r"why you'?ll love",
        r"we offer",
        r"our benefits",
        r"salary",
        r"pay range",
    ],
    'boilerplate': [
        # EEO / legal
        r"equal\s*opportunity\s*(?:employer|employment)",
        r"\beeo\b",
        r"\beeoc\b",
        r"affirmative\s*action",
        r"(?:diversity|inclusion)\s*(?:and|&|,)\s*(?:equity|inclusion|belonging)",
        r"our\s*commitment\s*to\s*(?:diversity|inclusion|equity)",
        r"we\s*(?:do\s*not|don['']t)\s*discriminate",
        r"(?:race|color|religion|sex|national\s*origin).*(?:disability|veteran)",
        # Physical / medical requirements
        r"physical\s*(?:requirements?|demands?|conditions?|capabilities)",
        r"(?:ability|must\s*be\s*able)\s*to\s*(?:lift|stand|sit|walk|bend|carry|push|pull)\b",
        r"work(?:ing)?\s*(?:environment|conditions?|hours?|schedule)",
        # Health / safety / COVID boilerplate
        r"(?:health|safety|wellness)\s*(?:requirements?|policy|policies|protocols?|standards?)",
        r"covid(?:\s*-?\s*19)?\s*(?:policy|requirements?|protocols?|vaccination|vaccine)",
        r"vaccination\s*(?:status|requirements?|policy)",
        r"(?:background|drug)\s*(?:check|screening|testing)\s*(?:required|policy|may\s*be)?",
        # Privacy notices
        r"(?:job\s*applicant|candidate|applicant)\s*privacy\s*(?:notice|policy|statement)",
        r"privacy\s*(?:notice|policy|statement|rights?)",
        r"for\s*(?:ca|california|colorado|new\s*york)\s*residents?",
        r"ccpa",
        # Tracking / ATS tags that appear as section headers
        r"#li-",
    ],
}

# Only extract skills from these sections
EXTRACTION_SECTIONS = {'requirements', 'preferred'}

# Scored signals for paragraph-level heuristic (used when no sections detected)
_PARA_POSITIVE = [
    (3.0, re.compile(r'\b\d+\+?\s*years?\s+of\s+experience\b', re.I)),
    (2.5, re.compile(r'\bexperience\s+(?:with|in)\b', re.I)),
    (2.5, re.compile(r'\bproficien(?:t|cy)\s+in\b', re.I)),
    (2.0, re.compile(r'\bknowledge\s+of\b', re.I)),
    (2.0, re.compile(r'\bfamili(?:ar|arity)\s+with\b', re.I)),
    (2.0, re.compile(r'\b(?:bachelor|master|phd|m\.s|b\.s|degree|certification)\b', re.I)),
    (1.5, re.compile(r'\b(?:must|required?)\b', re.I)),
    (1.5, re.compile(r'\bability\s+to\b', re.I)),
    (1.0, re.compile(r'\bunderstand(?:ing)?\s+of\b', re.I)),
    (1.0, re.compile(r'\btrack\s+record\b', re.I)),
    (1.0, re.compile(r'\bproven\b', re.I)),
]

_PARA_NEGATIVE = [
    (-4.0, re.compile(r'\b(?:salary|equity|vacation|pto|dental|vision|401k|parental\s+leave|health\s+insurance|stock\s+options)\b', re.I)),
    (-4.0, re.compile(r'\b(?:equal\s+opportunity|disability|accommodation|eeo|affirmative\s+action)\b', re.I)),
    (-3.0, re.compile(r'\b(?:we\s+are|our\s+mission|who\s+we\s+are|about\s+us|our\s+team|our\s+culture)\b', re.I)),
    (-2.0, re.compile(r'\b(?:founded|headquartered|series\s+[a-e]|venture|funding|investors?)\b', re.I)),
    (-1.5, re.compile(r'\b(?:join\s+us|come\s+work|we\s+offer|we\s+provide|we\s+believe)\b', re.I)),
]


def _score_paragraph(text: str) -> float:
    score = 0.0
    for weight, pattern in _PARA_POSITIVE:
        if pattern.search(text):
            score += weight
    for weight, pattern in _PARA_NEGATIVE:
        if pattern.search(text):
            score += weight  # weight is already negative

    # Bullet density bonus: short bullet-dense paragraphs strongly signal requirements
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        bullet_lines = sum(1 for l in lines if l and l[0] in '-•*·')
        avg_len = sum(len(l) for l in lines) / len(lines)
        bullet_ratio = bullet_lines / len(lines)
        if bullet_ratio > 0.5:
            score += bullet_ratio * 2.0
        # Short average line length = likely list items
        if avg_len < 80 and bullet_ratio > 0.3:
            score += 1.0

    return score


def parse_jd_sections(jd_text: str) -> List[Dict]:
    """
    Parse JD into labeled sections with character ranges.

    Returns: [
        {'name': 'unknown', 'start': 0, 'end': 500, 'text': '...'},
        {'name': 'requirements', 'start': 500, 'end': 1200, 'text': '...'},
        ...
    ]
    """
    if '<' in jd_text and '>' in jd_text:
        jd_text = BeautifulSoup(jd_text, 'html.parser').get_text(separator='\n', strip=True)
    jd_text = jd_text.replace('\xa0', ' ').replace('’', "'").replace('‘', "'")
    text = jd_text.strip()
    if not text:
        return [{'name': 'unknown', 'start': 0, 'end': 0, 'text': ''}]

    # Find all section headers
    headers = []
    for section_name, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            # Match section headers (with optional "Here’s" prefix, emoji, markdown; allow trailing text/emoji up to 60 chars)
            full_pattern = (
                "(?:^|\n)\\s*(?:\\:\\w+\\:\\s*)*(?:here\\x27?s\\s+)?"
                "(?:[\U00002600-\U000027BF\U0001F300-\U0001FAFF]\\s*)*"
                "(?:\\*{1,2}|#{1,4})?\\s*"
                + pattern +
                "[^\\n]{0,60}(?:\\n|$)"
            )
            for match in re.finditer(full_pattern, text, re.IGNORECASE | re.MULTILINE):
                headers.append({
                    'name': section_name,
                    'header_start': match.start(),
                    'content_start': match.end(),
                })
    
    if not headers:
        # No sections found - return entire text as 'unknown'
        return [{'name': 'unknown', 'start': 0, 'end': len(text), 'text': text}]
    
    # Sort by content_start so adjacent headers sharing a \n boundary are ordered correctly
    headers.sort(key=lambda x: x['content_start'])

    # Remove overlapping headers (keep first match per content position)
    # Use content_start for comparison: two headers sharing the same \n anchor
    # have different content_starts, so both are kept correctly.
    unique_headers = []
    last_content_end = -1
    for h in headers:
        if h['content_start'] > last_content_end:
            unique_headers.append(h)
            last_content_end = h['content_start']
    
    # Build sections with text content
    sections = []
    
    # Text before first header = 'unknown' section
    if unique_headers[0]['header_start'] > 0:
        sections.append({
            'name': 'unknown',
            'start': 0,
            'end': unique_headers[0]['header_start'],
            'text': text[0:unique_headers[0]['header_start']]
        })
    
    # Each detected section
    for i, header in enumerate(unique_headers):
        start = header['content_start']
        end = unique_headers[i + 1]['header_start'] if i + 1 < len(unique_headers) else len(text)
        sections.append({
            'name': header['name'],
            'start': start,
            'end': end,
            'text': text[start:end]
        })
    
    return sections


def extract_requirements_text(jd_text: str) -> Tuple[str, dict]:
    """
    Extract ONLY the requirements/preferred sections from a JD.

    Returns:
        (extracted_text, metadata)
    """
    if '<' in jd_text and '>' in jd_text:
        jd_text = BeautifulSoup(jd_text, 'html.parser').get_text(separator='\n', strip=True)
    jd_text = jd_text.replace('\xa0', ' ').replace(''', "'").replace(''', "'")
    sections = parse_jd_sections(jd_text)
    
    # Collect text from extraction sections only
    extracted_parts = []
    section_counts = {}
    
    for section in sections:
        section_counts[section['name']] = section_counts.get(section['name'], 0) + 1
        if section['name'] in EXTRACTION_SECTIONS:
            extracted_parts.append(section['text'])
    
    extracted_text = '\n'.join(extracted_parts)

    metadata = {
        'sections_found': section_counts,
        'extraction_sections_found': sum(1 for s in sections if s['name'] in EXTRACTION_SECTIONS),
        'used_fallback': False,
    }

    # Fallback: no requirements sections detected — use paragraph heuristic
    # to extract only requirement-likely paragraphs from the remaining text
    if not extracted_text.strip():
        NON_SKILL_SECTIONS = {'benefits', 'about_company', 'boilerplate'}
        candidate_text = '\n\n'.join(
            s['text'] for s in sections
            if s['name'] not in NON_SKILL_SECTIONS
        ) or jd_text

        # Score each paragraph; keep those above threshold
        SCORE_THRESHOLD = 2.0
        paragraphs = [p.strip() for p in candidate_text.split('\n\n') if p.strip()]
        scored = [(p, _score_paragraph(p)) for p in paragraphs]
        high_signal = [p for p, score in scored if score >= SCORE_THRESHOLD]

        # If heuristic is too aggressive (nothing passes), fall back to all candidate text
        extracted_text = '\n\n'.join(high_signal) if high_signal else candidate_text
        metadata['used_fallback'] = True
        metadata['para_heuristic'] = {
            'total_paras': len(paragraphs),
            'kept_paras': len(high_signal),
            'scores': [round(s, 1) for _, s in scored],
        }
    
    return extracted_text, metadata


# ============================================
# MAIN SKILL EXTRACTOR CLASS
# ============================================

class SkillExtractor:
    """Extract skills from text using keyword matching"""
    
    # Skills that need stricter matching patterns
    STRICT_MATCH_PATTERNS = {
        'go': [
            re.compile(p, re.IGNORECASE) for p in [
                r'\bgo\s*lang\b',
                r'\bgolang\b',
                r'\bgo\s+programming\b',
                r'\bwritten\s+in\s+go\b',
                r'\bgo\s+developer\b',
                r'\bgo\s*,\s*(?:python|java|rust|ruby|c\+\+)',
                r'(?:python|java|rust|ruby|c\+\+)\s*,\s*go\b',
            ]
        ],
        'spring': [
            re.compile(p, re.IGNORECASE) for p in [
                r'\bspring\s*(?:boot|framework|mvc|security|cloud|data|batch|integration)\b',
                r'\bspring\s*,\s*(?:java|hibernate|maven|gradle|kotlin|microservices)',
                r'(?:java|hibernate|maven|gradle|kotlin)\s*,\s*spring\b',
                r'\bjava\s+spring\b',
            ]
        ],
        'r': [
            re.compile(p, re.IGNORECASE) for p in [
                r'\br\s+programming\b',
                r'\br\s+language\b',
                r'\br(?:\s+|/)studio\b',
                r'\brstudio\b',
                r'\br\s*,\s*(?:python|sas|stata|spss)',
                r'(?:python|sas|stata|spss)\s*,\s*r\b',
            ]
        ],
    }
    
    # Known tool/product names that are also company names
    COMPANY_PRODUCT_SKILLS = {
        'figma', 'stripe', 'notion', 'linear', 'vercel', 'slack', 
        'salesforce', 'hubspot', 'asana', 'jira', 'confluence'
    }
    
    def __init__(self):
        self.skill_cache = None
        self._skill_patterns = None
        self._automaton = None       # Aho-Corasick automaton (fast path)
        self._term_to_skill = None   # term_lower → [skill_id, ...]

    def _load_skills(self):
        """Load verified skills from database and compile patterns."""
        skills = Skill.query.filter(Skill.is_verified == True).all()
        self.skill_cache = []
        self._skill_patterns = {}

        for s in skills:
            skill_data = {
                'id': s.id,
                'name': s.name,
                'name_lower': s.name.lower(),
                'category': s.category,
                'aliases': s.aliases or []
            }
            self.skill_cache.append(skill_data)

            # Compile regex patterns (used only for strict-match skills and fallback)
            patterns = [re.compile(r'\b' + re.escape(s.name.lower()) + r'\b', re.IGNORECASE)]
            for alias in (s.aliases or []):
                alias_lower = alias.lower()
                if alias_lower not in SKILL_BLACKLIST and len(alias_lower) >= 2:
                    patterns.append(re.compile(r'\b' + re.escape(alias_lower) + r'\b', re.IGNORECASE))

            self._skill_patterns[s.id] = patterns

        self._build_automaton()

    def _build_automaton(self):
        """Build Aho-Corasick automaton for O(text) multi-pattern matching."""
        try:
            import ahocorasick
        except ImportError:
            self._automaton = None
            return

        A = ahocorasick.Automaton()
        term_to_skills: Dict[str, List[int]] = {}  # term_lower → [skill_id, ...]

        for skill in self.skill_cache:
            sid = skill['id']
            # Skip strict-match skills — they need context patterns, not bare terms
            if skill['name_lower'] in self.STRICT_MATCH_PATTERNS:
                continue
            terms = [skill['name_lower']] + [
                a.lower() for a in skill['aliases']
                if a.lower() not in SKILL_BLACKLIST and len(a.strip()) >= 2
            ]
            for term in terms:
                if term not in term_to_skills:
                    term_to_skills[term] = []
                    A.add_word(term, term)
                if sid not in term_to_skills[term]:
                    term_to_skills[term].append(sid)

        if term_to_skills:
            A.make_automaton()
            self._automaton = A
            self._term_to_skill = term_to_skills
        else:
            self._automaton = None

    def _match_with_automaton(self, text: str) -> Dict[int, int]:
        """
        Single-pass skill detection using Aho-Corasick.
        Returns {skill_id: match_count} for skills found with word boundaries.
        """
        if not self._automaton:
            return {}

        text_lower = text.lower()
        counts: Dict[int, int] = {}

        for end_idx, term in self._automaton.iter(text_lower):
            start_idx = end_idx - len(term) + 1
            # Word-boundary check (no alphanumeric or _ adjacent)
            left_ok = start_idx == 0 or not (text_lower[start_idx - 1].isalnum() or text_lower[start_idx - 1] == '_')
            right_ok = end_idx + 1 >= len(text_lower) or not (text_lower[end_idx + 1].isalnum() or text_lower[end_idx + 1] == '_')
            if left_ok and right_ok:
                for sid in self._term_to_skill[term]:
                    counts[sid] = counts.get(sid, 0) + 1

        return counts
    
    @staticmethod
    def normalize_skill_name(name: str) -> str:
        """
        Normalize skill name for consistent casing.
        """
        if not name:
            return name
        
        name = name.strip()
        name = ' '.join(name.split())
        name_lower = name.lower()
        
        # Check special casing rules first (exact match)
        if name_lower in SPECIAL_CASING:
            return SPECIAL_CASING[name_lower]
        
        # Check if entire name is an acronym
        if name_lower in SKILL_ACRONYMS:
            return name.upper()
        
        # Handle skills with slashes (A/B Testing, CI/CD, Agile/Scrum)
        if '/' in name:
            parts = name.split('/')
            normalized_parts = []
            for part in parts:
                part = part.strip()
                part_lower = part.lower()
                
                if part_lower in SPECIAL_CASING:
                    normalized_parts.append(SPECIAL_CASING[part_lower])
                elif part_lower in SKILL_ACRONYMS:
                    normalized_parts.append(part.upper())
                else:
                    normalized_parts.append(_title_case_word(part))
            
            return '/'.join(normalized_parts)
        
        # Handle hyphenated skills (Go-to-Market, scikit-learn)
        if '-' in name and ' ' not in name:
            if name_lower in SPECIAL_CASING:
                return SPECIAL_CASING[name_lower]
            
            parts = name.split('-')
            normalized_parts = []
            for i, part in enumerate(parts):
                part_lower = part.lower()
                
                if part_lower in SKILL_ACRONYMS:
                    normalized_parts.append(part.upper())
                elif part_lower in LOWERCASE_WORDS and i > 0:
                    normalized_parts.append(part_lower)
                else:
                    normalized_parts.append(part.capitalize())
            
            return '-'.join(normalized_parts)
        
        # Handle multi-word skills
        words = name.split()
        normalized_words = []
        
        for i, word in enumerate(words):
            word_lower = word.lower()
            
            if word_lower in SPECIAL_CASING:
                normalized_words.append(SPECIAL_CASING[word_lower])
            elif word_lower in SKILL_ACRONYMS:
                normalized_words.append(word.upper())
            elif word_lower in LOWERCASE_WORDS and i > 0:
                normalized_words.append(word_lower)
            else:
                normalized_words.append(_title_case_word(word))
        
        return ' '.join(normalized_words)
    
    @staticmethod
    def is_valid_skill(name: str) -> bool:
        """
        Check if a skill name is valid (not blacklisted, proper format).
        """
        if not name:
            return False
        
        name = name.strip()
        name_lower = name.lower()
    
        # Whitelist: Single-character valid skills
        if name_lower in {'r', 'c'}:
            return True
        
        # Check length (too short or too long)
        if len(name) < 2 or len(name) > 100:
            return False
        
        # Check blacklist
        if name_lower in SKILL_BLACKLIST:
            return False
        
        # Must contain at least one letter
        if not any(c.isalpha() for c in name):
            return False
        
        # Reject skills with underscores (test data pattern)
        if '_' in name:
            return False
        
        # Reject pure numbers
        if name.isdigit():
            return False
        
        return True
    
    def extract_skills(self, text: str, company_name: str = None, is_resume: bool = False, requirements_text: str = None) -> List[Dict]:
        """
        Extract skills from text.

        For job descriptions (is_resume=False): only searches within
        requirements/preferred sections to avoid noise from About Us, benefits, etc.

        For resumes (is_resume=True): matches against the full text since resumes
        have Skills/Experience sections, not requirements sections.

        Args:
            text: Input text (JD or resume)
            company_name: Optional company name (reduces confidence for matching skills)
            is_resume: If True, skip JD section filtering and use full text

        Returns:
            List of dicts with skill info and confidence scores
        """
        if not text:
            return []

        if self.skill_cache is None:
            self._load_skills()

        if is_resume:
            search_text = re.sub(r'\s+', ' ', text).strip()
            extraction_meta = {'used_fallback': False}
        elif requirements_text:
            search_text = requirements_text
            extraction_meta = {'used_fallback': False}
        else:
            # === Extract only requirements/preferred sections ===
            search_text, extraction_meta = extract_requirements_text(text)
        
        company_name_lower = company_name.lower() if company_name else None
        found_skills = []
        seen_skill_ids = set()

        # ── Fast path: Aho-Corasick single-pass for all non-strict skills ──
        ac_counts: Dict[int, int] = {}
        if self._automaton:
            ac_counts = self._match_with_automaton(search_text)

        # ── Per-skill loop: strict-match skills + confidence scoring ──
        skill_lookup = {s['id']: s for s in self.skill_cache}

        # Union: AC hits + strict-match hits
        candidate_ids = set(ac_counts.keys())
        for skill in self.skill_cache:
            if skill['name_lower'] in self.STRICT_MATCH_PATTERNS:
                candidate_ids.add(skill['id'])

        for sid in candidate_ids:
            skill = skill_lookup.get(sid)
            if not skill:
                continue

            skill_name_lower = skill['name_lower']

            if skill_name_lower in SKILL_BLACKLIST:
                continue
            if not self.is_valid_skill(skill['name']):
                continue
            if sid in seen_skill_ids:
                continue

            # Determine match and count
            if skill_name_lower in self.STRICT_MATCH_PATTERNS:
                matched = any(
                    p.search(search_text)
                    for p in self.STRICT_MATCH_PATTERNS[skill_name_lower]
                )
                if not matched:
                    continue
                # Count via regex for confidence
                count = sum(
                    len(p.findall(search_text))
                    for p in self.STRICT_MATCH_PATTERNS[skill_name_lower]
                )
            else:
                count = ac_counts.get(sid, 0)
                if count == 0:
                    continue

            seen_skill_ids.add(sid)

            if count >= 3:
                confidence = 95
            elif count == 2:
                confidence = 85
            else:
                confidence = 70

            if (company_name_lower and
                    skill_name_lower in self.COMPANY_PRODUCT_SKILLS and
                    skill_name_lower == company_name_lower):
                confidence = max(30, confidence - 40)

            if extraction_meta.get('used_fallback'):
                confidence = max(50, confidence - 10)

            found_skills.append({
                'skill_id': sid,
                'name': self.normalize_skill_name(skill['name']),
                'category': skill['category'],
                'confidence': confidence,
            })

        found_skills.sort(key=lambda x: x['confidence'], reverse=True)
        return found_skills
    
    def categorize_skills(self, skills: list) -> dict:
        """Separate skills into technical, soft, and domain"""
        return {
            'technical': [s for s in skills if s.get('category') == 'technical'],
            'soft': [s for s in skills if s.get('category') == 'soft'],
            'domain': [s for s in skills if s.get('category') == 'domain'],
        }