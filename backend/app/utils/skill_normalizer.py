import re

# Words that should NEVER be skills
SKILL_BLACKLIST = {
    # Common words that get falsely matched
    'here', 'there', 'where', 'what', 'when', 'which', 'this', 'that',
    'with', 'from', 'have', 'been', 'were', 'being', 'would', 'could',
    'should', 'will', 'just', 'also', 'very', 'much', 'many', 'some',
    'other', 'into', 'over', 'such', 'only', 'then', 'them', 'these',
    'more', 'most', 'made', 'make', 'well', 'back', 'even', 'want',
    'because', 'each', 'said', 'does', 'got', 'use', 'used', 'using',
    'work', 'worked', 'working', 'company', 'team', 'teams', 'role',
    'experience', 'experienced', 'responsible', 'responsibilities',
    'including', 'include', 'includes', 'various', 'ability', 'able',
    'strong', 'excellent', 'good', 'great', 'best', 'better',
    'help', 'helped', 'helping', 'support', 'supported', 'supporting',
    'manage', 'managed', 'management', 'manager',  # Too generic
    'develop', 'developed', 'developing',  # Too generic without context
    'create', 'created', 'creating',
    'build', 'built', 'building',
    'lead', 'led', 'leading',  # Too generic
    'year', 'years', 'month', 'months', 'day', 'days',
    'new', 'first', 'last', 'next', 'high', 'low',
    'part', 'full', 'time', 'based', 'level', 'senior', 'junior',
    # Add more as you discover them
}

# Minimum skill name length
MIN_SKILL_LENGTH = 2

# Maximum skill name length (catches garbage)
MAX_SKILL_LENGTH = 50


def normalize_skill_name(name: str) -> str | None:
    """
    Normalize a skill name and validate it.
    Returns None if the skill should be rejected.
    """
    if not name:
        return None
    
    # Strip whitespace and convert to lowercase for comparison
    normalized = name.strip()
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Check length
    if len(normalized) < MIN_SKILL_LENGTH or len(normalized) > MAX_SKILL_LENGTH:
        return None
    
    # Check blacklist (case-insensitive)
    if normalized.lower() in SKILL_BLACKLIST:
        return None
    
    # Check if it's just numbers or special characters
    if re.match(r'^[\d\s\W]+$', normalized):
        return None
    
    # Title case for consistency (but preserve acronyms)
    # "machine learning" -> "Machine Learning"
    # "AWS" stays "AWS"
    # "sql" -> "SQL"
    normalized = smart_title_case(normalized)
    
    return normalized


def smart_title_case(name: str) -> str:
    """
    Convert to title case while preserving common acronyms.
    """
    # Known acronyms that should stay uppercase
    acronyms = {
        'sql', 'aws', 'gcp', 'api', 'apis', 'html', 'css', 'js', 'ui', 'ux',
        'ci', 'cd', 'qa', 'ml', 'ai', 'nlp', 'etl', 'crm', 'erp', 'saas',
        'paas', 'iaas', 'sdk', 'ide', 'orm', 'mvc', 'rest', 'graphql',
        'json', 'xml', 'yaml', 'csv', 'http', 'https', 'ssh', 'ftp',
        'tcp', 'ip', 'dns', 'ssl', 'tls', 'jwt', 'oauth', 'sso',
        'kpi', 'okr', 'roi', 'b2b', 'b2c', 'seo', 'sem', 'ppc',
        'ios', 'macos', 'linux', 'unix', 'sql', 'nosql', 'mongodb',
        'postgresql', 'mysql', 'redis', 'kafka', 'rabbitmq',
        'docker', 'kubernetes', 'k8s', 'aws', 'ec2', 's3', 'rds',
        'lambda', 'ecs', 'eks', 'vpc', 'iam', 'sns', 'sqs',
    }
    
    words = name.split()
    result = []
    
    for word in words:
        lower = word.lower()
        if lower in acronyms:
            # Check for specific casing rules
            if lower == 'javascript':
                result.append('JavaScript')
            elif lower == 'typescript':
                result.append('TypeScript')
            elif lower == 'postgresql':
                result.append('PostgreSQL')
            elif lower == 'mongodb':
                result.append('MongoDB')
            elif lower == 'graphql':
                result.append('GraphQL')
            elif lower == 'nodejs':
                result.append('Node.js')
            elif lower == 'reactjs':
                result.append('React.js')
            elif lower == 'vuejs':
                result.append('Vue.js')
            else:
                result.append(word.upper())
        else:
            result.append(word.capitalize())
    
    return ' '.join(result)


def are_skills_equivalent(skill1: str, skill2: str) -> bool:
    """
    Check if two skill names refer to the same skill.
    """
    if not skill1 or not skill2:
        return False
    
    # Normalize both
    n1 = normalize_skill_name(skill1)
    n2 = normalize_skill_name(skill2)
    
    if not n1 or not n2:
        return False
    
    # Direct match after normalization
    if n1.lower() == n2.lower():
        return True
    
    # Check common equivalences
    equivalences = [
        {'javascript', 'js', 'ecmascript'},
        {'typescript', 'ts'},
        {'python', 'python3', 'python 3'},
        {'react', 'reactjs', 'react.js'},
        {'vue', 'vuejs', 'vue.js'},
        {'node', 'nodejs', 'node.js'},
        {'postgres', 'postgresql', 'psql'},
        {'mongo', 'mongodb'},
        {'k8s', 'kubernetes'},
        {'gcp', 'google cloud', 'google cloud platform'},
        {'aws', 'amazon web services'},
        {'ci/cd', 'ci cd', 'cicd'},
        {'ui/ux', 'ui ux', 'uiux'},
    ]
    
    s1_lower = n1.lower()
    s2_lower = n2.lower()
    
    for equiv_set in equivalences:
        if s1_lower in equiv_set and s2_lower in equiv_set:
            return True
    
    return False