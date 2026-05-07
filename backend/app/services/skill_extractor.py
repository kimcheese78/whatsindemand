# backend/app/services/skill_extractor.py

import re
from typing import List, Dict, Tuple
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
    ],
    'preferred': [
        r"(?:preferred|desired)(?: skills| experience| qualifications)?",
        r"nice[- ]to[- ]have",
        r"bonus(?: points)?",
        r"it['']?s (?:great|nice|a plus) if",
        r"strong candidates",
        r"a\s+plus",
        r"extra credit",
        r"additional(?: desired)? (?:skills|qualifications)",
        r"even better if",
        r"bonus if you have",
        r"ideally you",
        r"these qualifications would be nice to have",
        r"what will make you stand out(?: \(.*?\))?",
        # Parenthetical preferred — e.g. "What will help you stand out (Nonessential Skills/Nice to Haves)"
        r".{5,60}\((?:preferred|desired|nice[- ]to[- ]haves?|nonessential|bonus)\)",
        # Figma-style
        r"(?:while )?not required,?.{0,30}(?:plus|bonus|added)",
        r"it['']?s an (?:added )?plus if",
        # Okta-style
        r"and extra credit if",
        # "Nice to Haves" (plural)
        r"nice[- ]to[- ]haves?",
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
    ],
    'about_company': [
        r"about (?:us|the company|the team|\w+(?:\s+\w+)?)",
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
    text = jd_text.strip()
    if not text:
        return [{'name': 'unknown', 'start': 0, 'end': 0, 'text': ''}]
    
    # Find all section headers
    headers = []
    for section_name, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            # Match section headers (with optional markdown/emoji/formatting prefix)
            full_pattern = r'(?:^|\n)\s*(?:[\U00002600-\U000027BF\U0001F300-\U0001FAFF]\s*)*(?:\*{1,2}|#{1,4})?\s*' + pattern + r'\s*(?:\*{1,2}|:)?\s*(?:\n|$)'
            for match in re.finditer(full_pattern, text, re.IGNORECASE | re.MULTILINE):
                headers.append({
                    'name': section_name,
                    'header_start': match.start(),
                    'content_start': match.end(),
                })
    
    if not headers:
        # No sections found - return entire text as 'unknown'
        return [{'name': 'unknown', 'start': 0, 'end': len(text), 'text': text}]
    
    # Sort by position
    headers.sort(key=lambda x: x['header_start'])
    
    # Remove overlapping headers (keep first)
    unique_headers = []
    last_end = -1
    for h in headers:
        if h['header_start'] >= last_end:
            unique_headers.append(h)
            last_end = h['content_start']
    
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
        NON_SKILL_SECTIONS = {'benefits', 'about_company'}
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
            
            # Compile patterns for efficient matching
            patterns = [re.compile(r'\b' + re.escape(s.name.lower()) + r'\b', re.IGNORECASE)]
            for alias in (s.aliases or []):
                alias_lower = alias.lower()
                if alias_lower not in SKILL_BLACKLIST and len(alias_lower) >= 2:
                    patterns.append(re.compile(r'\b' + re.escape(alias_lower) + r'\b', re.IGNORECASE))
            
            self._skill_patterns[s.id] = patterns
    
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
        
        # Reject skills that look like test data (contain numbers at end)
        if re.search(r'\d{3,}$', name):
            return False
        
        # Reject pure numbers
        if name.isdigit():
            return False
        
        return True
    
    def extract_skills(self, text: str, company_name: str = None) -> List[Dict]:
        """
        Extract skills from job description text.
        
        Only searches within requirements/preferred sections to avoid
        extracting skills from "About Us", responsibilities, benefits, etc.
        
        Args:
            text: Full job description text
            company_name: Optional company name (reduces confidence for matching skills)
            
        Returns:
            List of dicts with skill info and confidence scores
        """
        if not text:
            return []
        
        if self.skill_cache is None:
            self._load_skills()
        
        # === Extract only requirements/preferred sections ===
        search_text, extraction_meta = extract_requirements_text(text)
        
        company_name_lower = company_name.lower() if company_name else None
        found_skills = []
        seen_skill_ids = set()
        
        for skill in self.skill_cache:
            skill_name_lower = skill['name_lower']
            
            # Skip blacklisted skills
            if skill_name_lower in SKILL_BLACKLIST:
                continue
            
            # Skip invalid skills
            if not self.is_valid_skill(skill['name']):
                continue
            
            # Check for match
            matched = False
            
            # Handle strict-match skills (Go, R, Spring)
            if skill_name_lower in self.STRICT_MATCH_PATTERNS:
                for pattern in self.STRICT_MATCH_PATTERNS[skill_name_lower]:
                    if pattern.search(search_text):
                        matched = True
                        break
            else:
                # Standard matching with pre-compiled patterns
                for pattern in self._skill_patterns.get(skill['id'], []):
                    if pattern.search(search_text):
                        matched = True
                        break
            
            if not matched:
                continue
            
            # Dedupe by skill ID
            if skill['id'] in seen_skill_ids:
                continue
            seen_skill_ids.add(skill['id'])
            
            # Calculate confidence based on occurrence count
            patterns = self._skill_patterns.get(skill['id'], [])
            count = sum(len(p.findall(search_text)) for p in patterns)
            
            if count >= 3:
                confidence = 95
            elif count == 2:
                confidence = 85
            elif count == 1:
                confidence = 70
            else:
                confidence = 60
            
            # Reduce confidence if skill matches company name
            if (company_name_lower and
                skill_name_lower in self.COMPANY_PRODUCT_SKILLS and
                skill_name_lower == company_name_lower):
                confidence = max(30, confidence - 40)
            
            # Slight penalty if we had to use fallback (no sections detected)
            if extraction_meta.get('used_fallback'):
                confidence = max(50, confidence - 10)
            
            # Normalize the skill name for consistent display
            normalized_name = self.normalize_skill_name(skill['name'])
            
            found_skills.append({
                'skill_id': skill['id'],
                'name': normalized_name,
                'category': skill['category'],
                'confidence': confidence
            })
        
        # Sort by confidence
        found_skills.sort(key=lambda x: x['confidence'], reverse=True)
        
        return found_skills
    
    def categorize_skills(self, skills: list) -> dict:
        """Separate skills into technical, soft, and domain"""
        return {
            'technical': [s for s in skills if s.get('category') == 'technical'],
            'soft': [s for s in skills if s.get('category') == 'soft'],
            'domain': [s for s in skills if s.get('category') == 'domain'],
        }