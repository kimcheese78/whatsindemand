# backend/app/services/role_normalizer.py

import re
from typing import Optional, Tuple

# ============================================================================
# SKIP PATTERNS - Junk entries that shouldn't create roles
# ============================================================================
SKIP_PATTERNS = [
    r'$template$|default template',
    r'can\'?t find a role',
    r'don\'?t see the perfect fit',
    r'submit.*general application',
    r'join our talent community',
    r'future opportunities',
    r'your chance to join',
    r'talent community!?$',
    r'talent density program',
    r'^talent network$',
    r'^unknown$',
    r'^operations$',  # Too generic on its own
    r'^policy$',
    r'^consultant$',
    r'^researcher$',
    r'supervisor template',
]

# ============================================================================
# TITLE CLEANING PATTERNS - Strip these from titles
# ============================================================================

# Location patterns to strip (order matters - more specific first)
LOCATION_STRIP_PATTERNS = [
    # Pipe-separated: "| Germany | Remote", "| Usa | Remote"
    r'\s*\|[^|]*\|\s*remote\s*$',
    r'\s*\|[^|]*$',
    
    # Dash-separated regions
    r'\s*[-–]\s*(?:APAC|EMEA|AUNZ|LATAM|AMER|APJ|ANZ|JAPAC|SEMEA|SEUR|Pacnw)(?:\s|$).*$',
    
    # Dash-separated countries/cities
    r'\s*[-–]\s*(?:US|UK|EU|USA|Remote|Hybrid|India|Japan|Korea|China|Taiwan|Singapore|Australia|Canada|Mexico|Brazil|Spain|France|Germany|Italy|Netherlands|Poland|Ireland|Israel)(?:\s|,|$).*$',
    
    # US regions
    r'\s*[-–]\s*(?:Bay Area|Great Lakes|Midwest|Northeast|Southeast|Southwest|Northwest|Pacific Northwest|Southern California|East Coast|West Coast|Central|East|West|North|South|Tola|Heartland|French Markets)(?:\s|$).*$',
    
    # Specific cities with state: "- Nashville, Tn", "- Philadelphia, Pa"
    r'\s*[-–]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s*[A-Z]{2}\s*$',
    
    # Just city names after dash
    r'\s*[-–]\s*(?:NYC|SF|LA|Boston|Seattle|Austin|Denver|Chicago|Atlanta|Dallas|Miami|Phoenix|Portland|Philadelphia|Nashville|Tokyo|London|Berlin|Paris|Dublin|Sydney|Melbourne|Toronto|Vancouver|Mumbai|Bangalore|Bengaluru|Hyderabad|Cardiff|Bellevue|Mexico City|Hanoi|Short Hills|Tysons Corner|Alderwood Mall|Las Vegas|Cheadle)(?:\s|$).*$',
    
    # Remote/Hybrid at end
    r'\s*[-–]\s*(?:Remote|Hybrid|On-?site).*$',
    r',\s*(?:Remote|Hybrid)$',
]

# Temporal/contract patterns to strip
TEMPORAL_STRIP_PATTERNS = [
    # Year cohorts: "(Summer 2026)", "(2026)", "(2026 Start)"
    r'\s*$(?:Summer|Fall|Winter|Spring)?\s*202[4-9](?:\s*Start)?$',
    r'\s*$202[4-9]$',
    
    # Fixed term contracts
    r'\s*$12[- ]?Month[- ]?(?:Fixed[- ]?Term|Contract|Ftc)?$',
    r'\s*$(?:Fixed[- ]?Term|Ftc|Contract)$',
    r'\s*$Contractor$',
    r'\s*$Contract\s*(?:Basis)?$',
    r'\s*$Contingent(?:,?\s*Part[- ]?Time)?$',
    
    # Part-time markers
    r'\s*$(?:Full[- ]?Time|Part[- ]?Time)$',
]

# Language patterns to strip
LANGUAGE_STRIP_PATTERNS = [
    r'\s*$[^)]*(?:Speaking|Speaker|Fluent)[^)]*$',
    r'\s*$(?:Danish|Dutch|Swedish|French|German|Spanish|Portuguese|Italian|Japanese|Korean|Chinese|Mandarin|Cantonese|Hebrew|Arabic|Hindi|Turkish|Polish|Russian|Vietnamese|Thai|Indonesian|Malay)(?:\s*(?:&|and)\s*(?:English|Spanish|Portuguese))?\s*(?:Speaking|Speaker)?$',
]

# Other noise to strip
OTHER_STRIP_PATTERNS = [
    # Skillbridge/military programs
    r'\s*[-–]\s*Skillbridge.*$',
    r'\s*$Skillbridge$',
    
    # Affirmative action notes
    r'\s*$[^)]*Affirmative Action[^)]*$',
    r'\s*$[^)]*Exclusiv[ao][^)]*$',  # Portuguese exclusivity notes
    
    # Team/product suffixes we don't need
    r'\s*[-–]\s*(?:Team\s+)?(?:Web|Mobile|Platform|Core|Growth|Enterprise)$',
    
    # Roman numerals at end (but keep "II" if it's the only thing)
    r'\s+(?:II|III|IV|V|VI)$',
    
    # Generic parenthetical noise
    r'\s*$[^)]*(?:United Kingdom|United States|Bengaluru|Singapore|Poland|Germany|Sweden)$',
]

# ============================================================================
# SENIORITY PATTERNS
# ============================================================================
SENIORITY_PATTERNS = [
    (r'\bprincipal\b', 'principal'),
    (r'\bdistinguished\b', 'distinguished'),
    (r'\b(senior|sr\.?)\s+staff\b', 'senior-staff'),
    (r'\bstaff\b', 'staff'),
    (r'\bsenior\b', 'senior'),
    (r'\bsr\.\s*', 'senior'),
    (r'\bsr\s+', 'senior'),
    (r'\blead\b', 'lead'),
    (r'\b(junior|jr\.?|entry[- ]level)\b', 'junior'),
    (r'\b(mid[- ]?level)\b', 'mid'),
    (r'\b(intern|internship)\b', 'intern'),
    (r'\bassociate\b(?!\s*,)', 'associate'),  # "Associate Engineer" but not "Associate, X"
]

# ============================================================================
# ACRONYM FIXES - Applied at the end
# ============================================================================
ACRONYM_FIXES = {
    ' Ai ': ' AI ',
    ' Ai': ' AI',
    'Ai ': 'AI ',
    ' Ml ': ' ML ',
    ' It ': ' IT ',
    ' Ui ': ' UI ',
    ' Ux ': ' UX ',
    ' Api ': ' API ',
    ' Sdk ': ' SDK ',
    ' Qa ': ' QA ',
    ' Sql ': ' SQL ',
    ' Aws ': ' AWS ',
    ' Gcp ': ' GCP ',
    ' Sre ': ' SRE ',
    ' Swe ': ' SWE ',
    ' Pm ': ' PM ',
    ' Vp ': ' VP ',
    ' Svp ': ' SVP ',
    ' Evp ': ' EVP ',
    ' Ceo': ' CEO',
    ' Cto': ' CTO',
    ' Cfo': ' CFO',
    ' Coo': ' COO',
    ' Cmo': ' CMO',
    ' Cpo': ' CPO',
    ' Cro': ' CRO',
    ' Ciso': ' CISO',
    'Ceo': 'CEO',
    'Cto': 'CTO',
    'Cfo': 'CFO',
    'Coo': 'COO',
    ' Gtm ': ' GTM ',
    ' Gtm': ' GTM',
    'Gtm ': 'GTM ',
    ' Emea': ' EMEA',
    ' Apac': ' APAC',
    ' Anz': ' ANZ',
    ' Latam': ' LATAM',
    ' Aml ': ' AML ',
    ' Kyc ': ' KYC ',
    ' Hris ': ' HRIS ',
    ' Hcm ': ' HCM ',
    ' Erp ': ' ERP ',
    ' Crm ': ' CRM ',
    ' Fpga ': ' FPGA ',
    ' Gpu ': ' GPU ',
    ' Cpu ': ' CPU ',
    ' Tpu ': ' TPU ',
    ' Nlp ': ' NLP ',
    ' Llm ': ' LLM ',
    ' Genai': ' GenAI',
    'Genai ': 'GenAI ',
    ' Devsecops ': ' DevSecOps ',
    ' Devops ': ' DevOps ',
    ' Ios ': ' iOS ',
    ' Saas ': ' SaaS ',
    ' B2B ': ' B2B ',
    ' B2C ': ' B2C ',
    ' B2G ': ' B2G ',
    ' Pmo ': ' PMO ',
    ' Sox ': ' SOX ',
    ' Dba ': ' DBA ',
    ' Etl ': ' ETL ',
    ' Ci/Cd ': ' CI/CD ',
    ' Iam ': ' IAM ',
    ' Grc ': ' GRC ',
    ' Abm ': ' ABM ',
    ' Seo ': ' SEO ',
    ' Cpq ': ' CPQ ',
    ' Fpanda ': ' FP&A ',
    "Fp&A": "FP&A",
}


def clean_title(raw_title: str) -> str:
    """Clean up a raw job title by removing location, temporal, and noise patterns."""
    if not raw_title:
        return ''
    
    title = raw_title.strip()
    
    # Apply all strip patterns
    for pattern in LOCATION_STRIP_PATTERNS:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    
    for pattern in TEMPORAL_STRIP_PATTERNS:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    
    for pattern in LANGUAGE_STRIP_PATTERNS:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    
    for pattern in OTHER_STRIP_PATTERNS:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    
    # Clean up any remaining parentheses with just location-like content
    title = re.sub(r'\s*$[^)]{0,30}$$', '', title)  # Short parenthetical at end
    
    # Remove trailing punctuation and whitespace
    title = re.sub(r'\s*[-–,]\s*$', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title


def should_skip(title: str) -> bool:
    """Check if this title should be skipped entirely."""
    title_lower = title.lower().strip()
    
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    
    # Skip non-English titles (French, Portuguese, Japanese, etc.)
    # These have special characters or patterns
    if re.search(r'[àâäéèêëïîôùûüçœæ]', title_lower):  # French
        return True
    if re.search(r'[ãõáéíóúâêôç]', title_lower):  # Portuguese
        return True
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]', title):  # Japanese/Chinese
        return True
    
    # Skip if title is too short or just noise
    if len(title_lower) < 3:
        return True
    
    return False


def extract_seniority(title: str) -> Tuple[Optional[str], str]:
    """Extract seniority level from title and return cleaned title."""
    title_lower = title.lower()
    
    for pattern, level in SENIORITY_PATTERNS:
        if re.search(pattern, title_lower):
            # Don't remove "staff" from "staff engineer" - it's part of the role
            if level in ('staff', 'senior-staff') and re.search(r'staff\s+engineer', title_lower):
                return level, title_lower
            
            # Don't remove "lead" if it's "Team Lead" or similar
            if level == 'lead' and re.search(r'(team|tech|engineering)\s+lead', title_lower):
                return level, title_lower
            
            # Remove the seniority prefix
            cleaned = re.sub(pattern, '', title_lower, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r'^[\s,.\-]+|[\s,.\-]+$', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return level, cleaned
    
    return None, title_lower


def fix_acronyms(title: str) -> str:
    """Fix common acronym casing."""
    for wrong, right in ACRONYM_FIXES.items():
        title = title.replace(wrong, right)
    return title

# ============================================================================
# JOB FAMILY PATTERNS
# Pattern -> (normalized_title, category, job_family)
# ORDER MATTERS - more specific patterns first!
# ============================================================================

JOB_FAMILY_PATTERNS = [
    
    # ========================================================================
    # ENGINEERING - AI/ML (Most specific first)
    # ========================================================================
    (r'applied ai engineer', 'Applied AI Engineer', 'Engineering', 'AI/ML'),
    (r'applied ai scientist', 'Applied AI Scientist', 'Engineering', 'AI/ML'),
    (r'applied (ml|machine learning) engineer', 'Applied ML Engineer', 'Engineering', 'AI/ML'),
    (r'genai.*engineer|gen\s*ai.*engineer', 'GenAI Engineer', 'Engineering', 'AI/ML'),
    (r'generative ai.*engineer', 'GenAI Engineer', 'Engineering', 'AI/ML'),
    (r'ai platform engineer', 'AI Platform Engineer', 'Engineering', 'AI/ML'),
    (r'ai infrastructure engineer', 'AI Infrastructure Engineer', 'Engineering', 'AI/ML'),
    (r'ai safety engineer', 'AI Safety Engineer', 'Engineering', 'AI/ML'),
    (r'ai architect', 'AI Architect', 'Engineering', 'AI/ML'),
    (r'ai automation lead', 'AI Automation Lead', 'Engineering', 'AI/ML'),
    (r'ai deployment specialist', 'AI Deployment Specialist', 'Engineering', 'AI/ML'),
    (r'ai specialist', 'AI Specialist', 'Engineering', 'AI/ML'),
    (r'ai engineer', 'AI Engineer', 'Engineering', 'AI/ML'),
    (r'ml platform engineer', 'ML Platform Engineer', 'Engineering', 'AI/ML'),
    (r'ml infrastructure engineer', 'ML Infrastructure Engineer', 'Engineering', 'AI/ML'),
    (r'mlops engineer', 'MLOps Engineer', 'Engineering', 'AI/ML'),
    (r'ml ops engineer', 'MLOps Engineer', 'Engineering', 'AI/ML'),
    (r'machine learning engineer', 'Machine Learning Engineer', 'Engineering', 'AI/ML'),
    (r'ml engineer', 'Machine Learning Engineer', 'Engineering', 'AI/ML'),
    (r'deep learning engineer', 'Deep Learning Engineer', 'Engineering', 'AI/ML'),
    (r'nlp engineer', 'NLP Engineer', 'Engineering', 'AI/ML'),
    (r'computer vision engineer', 'Computer Vision Engineer', 'Engineering', 'AI/ML'),
    (r'research engineer', 'Research Engineer', 'Engineering', 'Research'),
    (r'research scientist', 'Research Scientist', 'Engineering', 'Research'),
    (r'applied scientist', 'Applied Scientist', 'Engineering', 'Research'),
    (r'algorithm scientist', 'Algorithm Scientist', 'Engineering', 'Research'),
    
    # ========================================================================
    # ENGINEERING - Specific Language/Framework Engineers
    # ========================================================================
    (r'golang\s*(developer|engineer)', 'Go Engineer', 'Engineering', 'Software Engineering'),
    (r'\bgo\b\s*(developer|engineer)', 'Go Engineer', 'Engineering', 'Software Engineering'),
    (r'rust\s*(developer|engineer)', 'Rust Engineer', 'Engineering', 'Software Engineering'),
    (r'python\s*(developer|engineer)', 'Python Engineer', 'Engineering', 'Software Engineering'),
    (r'java\s*(developer|engineer)', 'Java Engineer', 'Engineering', 'Software Engineering'),
    (r'kotlin\s*(developer|engineer)', 'Kotlin Engineer', 'Engineering', 'Software Engineering'),
    (r'kotlin engineer', 'Kotlin Engineer', 'Engineering', 'Software Engineering'),
    (r'swift\s*(developer|engineer)', 'Swift Engineer', 'Engineering', 'Software Engineering'),
    (r'ruby\s*(developer|engineer)', 'Ruby Engineer', 'Engineering', 'Software Engineering'),
    (r'node\.?js\s*(developer|engineer)', 'Node.js Engineer', 'Engineering', 'Software Engineering'),
    (r'react\s*(developer|engineer)', 'React Engineer', 'Engineering', 'Software Engineering'),
    (r'angular\s*(developer|engineer)', 'Angular Engineer', 'Engineering', 'Software Engineering'),
    (r'vue\s*(developer|engineer)', 'Vue Engineer', 'Engineering', 'Software Engineering'),
    (r'typescript\s*(developer|engineer)', 'TypeScript Engineer', 'Engineering', 'Software Engineering'),
    (r'scala\s*(developer|engineer)', 'Scala Engineer', 'Engineering', 'Software Engineering'),
    (r'elixir\s*(developer|engineer)', 'Elixir Engineer', 'Engineering', 'Software Engineering'),
    (r'c\+\+\s*(developer|engineer)', 'C++ Engineer', 'Engineering', 'Software Engineering'),
    (r'\.net\s*(developer|engineer)', '.NET Engineer', 'Engineering', 'Software Engineering'),
    (r'php\s*(developer|engineer)', 'PHP Engineer', 'Engineering', 'Software Engineering'),
    
    # ========================================================================
    # ENGINEERING - Web Development
    # ========================================================================
    (r'web developer', 'Web Developer', 'Engineering', 'Software Engineering'),
    (r'web engineer', 'Web Engineer', 'Engineering', 'Software Engineering'),
    (r'frontend|front[- ]end', 'Frontend Engineer', 'Engineering', 'Software Engineering'),
    (r'backend|back[- ]end', 'Backend Engineer', 'Engineering', 'Software Engineering'),
    (r'full[- ]?stack', 'Fullstack Engineer', 'Engineering', 'Software Engineering'),
    
    # ========================================================================
    # ENGINEERING - Mobile
    # ========================================================================
    (r'ios\s*(developer|engineer)', 'iOS Engineer', 'Engineering', 'Mobile'),
    (r'android\s*(developer|engineer)', 'Android Engineer', 'Engineering', 'Mobile'),
    (r'mobile\s*(developer|engineer)', 'Mobile Engineer', 'Engineering', 'Mobile'),
    (r'react native\s*(developer|engineer)', 'React Native Engineer', 'Engineering', 'Mobile'),
    (r'flutter\s*(developer|engineer)', 'Flutter Engineer', 'Engineering', 'Mobile'),
    (r'\bios\b', 'iOS Engineer', 'Engineering', 'Mobile'),
    (r'\bandroid\b', 'Android Engineer', 'Engineering', 'Mobile'),
    (r'macos developer', 'macOS Developer', 'Engineering', 'Software Engineering'),
    
    # ========================================================================
    # ENGINEERING - Data Engineering
    # ========================================================================
    (r'analytics engineer', 'Analytics Engineer', 'Engineering', 'Data Engineering'),
    (r'data platform engineer', 'Data Platform Engineer', 'Engineering', 'Data Engineering'),
    (r'data infrastructure engineer', 'Data Infrastructure Engineer', 'Engineering', 'Data Engineering'),
    (r'business intelligence engineer|bi engineer', 'Business Intelligence Engineer', 'Engineering', 'Data Engineering'),
    (r'data engineer', 'Data Engineer', 'Engineering', 'Data Engineering'),
    (r'database reliability engineer|dbre', 'Database Reliability Engineer', 'Engineering', 'Infrastructure'),
    (r'database engineer', 'Database Engineer', 'Engineering', 'Data Engineering'),
    (r'database administrator|dba\b', 'Database Administrator', 'Engineering', 'Data Engineering'),
    (r'etl engineer', 'ETL Engineer', 'Engineering', 'Data Engineering'),
    (r'data operations engineer', 'Data Operations Engineer', 'Engineering', 'Data Engineering'),
    
    # ========================================================================
    # ENGINEERING - Infrastructure/DevOps/SRE
    # ========================================================================
    (r'devsecops', 'DevSecOps Engineer', 'Engineering', 'Infrastructure'),
    (r'devops', 'DevOps Engineer', 'Engineering', 'Infrastructure'),
    (r'site reliability|sre\b', 'Site Reliability Engineer', 'Engineering', 'Infrastructure'),
    (r'platform engineer', 'Platform Engineer', 'Engineering', 'Infrastructure'),
    (r'infrastructure engineer', 'Infrastructure Engineer', 'Engineering', 'Infrastructure'),
    (r'cloud engineer', 'Cloud Engineer', 'Engineering', 'Infrastructure'),
    (r'systems engineer', 'Systems Engineer', 'Engineering', 'Infrastructure'),
    (r'system engineer', 'Systems Engineer', 'Engineering', 'Infrastructure'),
    (r'network engineer', 'Network Engineer', 'Engineering', 'Infrastructure'),
    (r'network deployment engineer', 'Network Deployment Engineer', 'Engineering', 'Infrastructure'),
    (r'monitoring engineer', 'Monitoring Engineer', 'Engineering', 'Infrastructure'),
    (r'observability.*architect', 'Observability Architect', 'Engineering', 'Infrastructure'),
    (r'reliability engineer', 'Reliability Engineer', 'Engineering', 'Infrastructure'),
    (r'capacity engineer', 'Capacity Engineer', 'Engineering', 'Infrastructure'),
    (r'ci/cd engineer', 'CI/CD Engineer', 'Engineering', 'Infrastructure'),
    (r'build engineer', 'Build Engineer', 'Engineering', 'Infrastructure'),
    (r'release engineer', 'Release Engineer', 'Engineering', 'Infrastructure'),
    (r'it engineer', 'IT Engineer', 'Engineering', 'IT'),
    (r'it automation engineer', 'IT Automation Engineer', 'Engineering', 'IT'),
    (r'it operations engineer', 'IT Operations Engineer', 'Engineering', 'IT'),
    (r'it systems engineer', 'IT Systems Engineer', 'Engineering', 'IT'),
    (r'data center.*engineer', 'Data Center Engineer', 'Engineering', 'Infrastructure'),
    
    # ========================================================================
    # ENGINEERING - Security
    # ========================================================================
    (r'application security.*engineer', 'Application Security Engineer', 'Engineering', 'Security'),
    (r'product security.*engineer', 'Product Security Engineer', 'Engineering', 'Security'),
    (r'cloud security engineer', 'Cloud Security Engineer', 'Engineering', 'Security'),
    (r'security.*engineer', 'Security Engineer', 'Engineering', 'Security'),
    (r'detection engineer', 'Detection Engineer', 'Engineering', 'Security'),
    (r'privacy engineer', 'Privacy Engineer', 'Engineering', 'Security'),
    (r'threat.*engineer', 'Threat Engineer', 'Engineering', 'Security'),
    (r'offensive security', 'Offensive Security Engineer', 'Engineering', 'Security'),
    (r'penetration tester|pen\s*test', 'Penetration Tester', 'Engineering', 'Security'),
    (r'security researcher', 'Security Researcher', 'Engineering', 'Security'),
    (r'threat researcher', 'Threat Researcher', 'Engineering', 'Security'),
    (r'threat detection researcher', 'Threat Detection Researcher', 'Engineering', 'Security'),
    (r'threat intelligence researcher', 'Threat Intelligence Researcher', 'Engineering', 'Security'),
    (r'malware.*engineer', 'Malware Engineer', 'Engineering', 'Security'),
    (r'cryptography engineer', 'Cryptography Engineer', 'Engineering', 'Security'),
    (r'iam engineer', 'IAM Engineer', 'Engineering', 'Security'),
    (r'identity.*access.*engineer', 'IAM Engineer', 'Engineering', 'Security'),
    (r'grc engineer', 'GRC Engineer', 'Engineering', 'Security'),
    
    # ========================================================================
    # ENGINEERING - Specialized
    # ========================================================================
    (r'staff engineer', 'Staff Engineer', 'Engineering', 'Software Engineering'),
    (r'principal engineer', 'Principal Engineer', 'Engineering', 'Software Engineering'),
    (r'distinguished engineer', 'Distinguished Engineer', 'Engineering', 'Software Engineering'),
    (r'product engineer', 'Product Engineer', 'Engineering', 'Product Engineering'),
    (r'growth engineer', 'Growth Engineer', 'Engineering', 'Growth'),
    (r'integration engineer', 'Integration Engineer', 'Engineering', 'Integration'),
    (r'systems integration engineer', 'Systems Integration Engineer', 'Engineering', 'Integration'),
    (r'forward deploy(ment|ed)?\s*engineer', 'Forward Deployed Engineer', 'Engineering', 'Solutions Engineering'),
    (r'developer experience engineer', 'Developer Experience Engineer', 'Engineering', 'Developer Experience'),
    (r'developer success engineer', 'Developer Success Engineer', 'Engineering', 'Developer Experience'),
    (r'demo engineer', 'Demo Engineer', 'Engineering', 'Solutions Engineering'),
    (r'application engineer', 'Application Engineer', 'Engineering', 'Software Engineering'),
    (r'applications developer', 'Applications Developer', 'Engineering', 'Software Engineering'),
    (r'qa\s*engineer|quality assurance engineer|test engineer|sdet', 'QA Engineer', 'Engineering', 'Quality'),
    (r'automation engineer', 'Automation Engineer', 'Engineering', 'Quality'),
    (r'performance engineer', 'Performance Engineer', 'Engineering', 'Performance'),
    (r'embedded\s*(engineer|developer)', 'Embedded Engineer', 'Engineering', 'Hardware'),
    (r'hardware engineer', 'Hardware Engineer', 'Engineering', 'Hardware'),
    (r'firmware engineer', 'Firmware Engineer', 'Engineering', 'Hardware'),
    (r'electrical engineer', 'Electrical Engineer', 'Engineering', 'Hardware'),
    (r'mechanical engineer', 'Mechanical Engineer', 'Engineering', 'Hardware'),
    (r'smart contract engineer', 'Smart Contract Engineer', 'Engineering', 'Blockchain'),
    (r'blockchain engineer', 'Blockchain Engineer', 'Engineering', 'Blockchain'),
    (r'protocol engineer', 'Protocol Engineer', 'Engineering', 'Blockchain'),
    (r'solana.*engineer', 'Solana Engineer', 'Engineering', 'Blockchain'),
    (r'fleet engineer', 'Fleet Engineer', 'Engineering', 'IT'),
    (r'saas engineer', 'SaaS Engineer', 'Engineering', 'Infrastructure'),
    (r'support engineer', 'Support Engineer', 'Engineering', 'Support Engineering'),
    (r'escalation engineer', 'Escalation Engineer', 'Engineering', 'Support Engineering'),
    (r'field engineer', 'Field Engineer', 'Engineering', 'Field Engineering'),
    (r'solutions engineer', 'Solutions Engineer', 'Engineering', 'Solutions Engineering'),
    (r'solution engineer', 'Solutions Engineer', 'Engineering', 'Solutions Engineering'),
    (r'sales engineer', 'Sales Engineer', 'Engineering', 'Sales Engineering'),
    (r'pre[- ]?sales engineer', 'Pre-Sales Engineer', 'Engineering', 'Sales Engineering'),
    (r'customer engineer', 'Customer Engineer', 'Engineering', 'Customer Engineering'),
    (r'professional services engineer', 'Professional Services Engineer', 'Engineering', 'Professional Services'),
    (r'implementation engineer', 'Implementation Engineer', 'Engineering', 'Implementation'),
    (r'onboarding engineer', 'Onboarding Engineer', 'Engineering', 'Implementation'),
    (r'broadcast engineer', 'Broadcast Engineer', 'Engineering', 'Media'),
    (r'av engineer|a/v engineer', 'AV Engineer', 'Engineering', 'Media'),
    (r'video engineer', 'Video Engineer', 'Engineering', 'Media'),
    (r'streaming engineer', 'Streaming Engineer', 'Engineering', 'Media'),
    (r'content engineer', 'Content Engineer', 'Engineering', 'Content'),
    (r'prototype engineer', 'Prototype Engineer', 'Engineering', 'R&D'),
    (r'sustaining engineer', 'Sustaining Engineer', 'Engineering', 'Support Engineering'),
    (r'change engineer', 'Change Engineer', 'Engineering', 'IT'),
    (r'ux engineer', 'UX Engineer', 'Engineering', 'Design Engineering'),
    (r'design technologist', 'Design Technologist', 'Engineering', 'Design Engineering'),
    (r'creative technologist', 'Creative Technologist', 'Engineering', 'Design Engineering'),
    
    # ========================================================================
    # ENGINEERING - Business Systems / Enterprise Apps
    # ========================================================================
    (r'salesforce\s*(developer|engineer)', 'Salesforce Developer', 'Engineering', 'Business Systems'),
    (r'salesforce architect', 'Salesforce Architect', 'Engineering', 'Business Systems'),
    (r'servicenow\s*(developer|engineer)', 'ServiceNow Developer', 'Engineering', 'Business Systems'),
    (r'servicenow.*architect', 'ServiceNow Architect', 'Engineering', 'Business Systems'),
    (r'netsuite\s*(developer|engineer)', 'NetSuite Developer', 'Engineering', 'Business Systems'),
    (r'workday\s*(developer|engineer)', 'Workday Developer', 'Engineering', 'Business Systems'),
    (r'oracle.*developer', 'Oracle Developer', 'Engineering', 'Business Systems'),
    (r'sap\s*(developer|engineer)', 'SAP Developer', 'Engineering', 'Business Systems'),
    (r'anaplan\s*(engineer|model builder)', 'Anaplan Engineer', 'Engineering', 'Business Systems'),
    (r'airtable.*architect', 'Airtable Architect', 'Engineering', 'Business Systems'),
    (r'ciam engineer', 'CIAM Engineer', 'Engineering', 'Identity'),
    
    # ========================================================================
    # ENGINEERING - Management & Leadership
    # ========================================================================
    (r'engineering manager', 'Engineering Manager', 'Engineering', 'Engineering Management'),
    (r'manager.*engineering', 'Engineering Manager', 'Engineering', 'Engineering Management'),
    (r'engineering director', 'Engineering Director', 'Engineering', 'Engineering Leadership'),
    (r'director.*engineering', 'Director of Engineering', 'Engineering', 'Engineering Leadership'),
    (r'vp.*engineering', 'VP of Engineering', 'Engineering', 'Engineering Leadership'),
    (r'head of engineering', 'Head of Engineering', 'Engineering', 'Engineering Leadership'),

    # Risk/Compliance Team Leads - BEFORE generic "team lead"
    (r'credit risk.*team lead', 'Credit Risk Team Lead', 'Risk', 'Credit Risk'),
    (r'credit risk.*lead', 'Credit Risk Lead', 'Risk', 'Credit Risk'),
    (r'credit.*team lead', 'Credit Team Lead', 'Risk', 'Credit'),
    (r'fraud.*team lead', 'Fraud Team Lead', 'Risk', 'Fraud'),
    (r'risk.*team lead', 'Risk Team Lead', 'Risk', 'Risk'),
    (r'aml.*team lead', 'AML Team Lead', 'Risk', 'AML'),
    (r'kyc.*team lead', 'KYC Team Lead', 'Risk', 'KYC'),
    (r'compliance.*team lead', 'Compliance Team Lead', 'Legal', 'Compliance'),
    (r'operations.*team lead', 'Operations Team Lead', 'Operations', 'Operations'),
    (r'sales.*team lead', 'Sales Team Lead', 'Sales', 'Sales'),
    (r'support.*team lead', 'Support Team Lead', 'Customer Success', 'Support'),

    # Generic Team Lead - AFTER specific ones
    (r'team lead', 'Team Lead', 'Engineering', 'Engineering Leadership'),
    (r'tech lead', 'Tech Lead', 'Engineering', 'Engineering Leadership'),
    (r'engineering lead', 'Engineering Lead', 'Engineering', 'Engineering Leadership'),
    
    # ========================================================================
    # ENGINEERING - DevRel
    # ========================================================================
    (r'developer advocate', 'Developer Advocate', 'Engineering', 'Developer Relations'),
    (r'developer relations', 'Developer Relations', 'Engineering', 'Developer Relations'),
    (r'devrel', 'Developer Relations', 'Engineering', 'Developer Relations'),
    (r'developer educator', 'Developer Educator', 'Engineering', 'Developer Relations'),
    (r'developer evangelist', 'Developer Evangelist', 'Engineering', 'Developer Relations'),
    (r'community engineer', 'Community Engineer', 'Engineering', 'Developer Relations'),
    
    # ========================================================================
    # ENGINEERING - Generic (LAST in engineering section)
    # ========================================================================
    (r'software\s*(engineer|developer)', 'Software Engineer', 'Engineering', 'Software Engineering'),
    (r'engineer.*software', 'Software Engineer', 'Engineering', 'Software Engineering'),
    (r'swe\b', 'Software Engineer', 'Engineering', 'Software Engineering'),
    (r'\bdeveloper\b', 'Software Developer', 'Engineering', 'Software Engineering'),
    
    # ========================================================================
    # DATA SCIENCE & ANALYTICS
    # ========================================================================
    (r'data science manager', 'Data Science Manager', 'Data', 'Data Science'),
    (r'data scientist', 'Data Scientist', 'Data', 'Data Science'),
    (r'data science lead', 'Data Science Lead', 'Data', 'Data Science'),
    (r'data science$', 'Data Scientist', 'Data', 'Data Science'),
    (r'decision scientist', 'Decision Scientist', 'Data', 'Data Science'),
    (r'quantitative analyst', 'Quantitative Analyst', 'Data', 'Quantitative'),
    (r'quantitative researcher', 'Quantitative Researcher', 'Data', 'Quantitative'),
    (r'quantitative analytics', 'Quantitative Analyst', 'Data', 'Quantitative'),
    (r'data analyst', 'Data Analyst', 'Data', 'Data Analytics'),
    (r'data analytics', 'Data Analyst', 'Data', 'Data Analytics'),
    (r'analytics manager', 'Analytics Manager', 'Data', 'Analytics'),
    (r'analytics lead', 'Analytics Lead', 'Data', 'Analytics'),
    (r'advanced analytics', 'Advanced Analytics', 'Data', 'Analytics'),
    (r'business intelligence analyst|bi analyst', 'Business Intelligence Analyst', 'Data', 'Business Intelligence'),
    (r'business intelligence developer', 'Business Intelligence Developer', 'Data', 'Business Intelligence'),
    (r'insights analyst', 'Insights Analyst', 'Data', 'Analytics'),
    (r'market.*insights', 'Market Insights Analyst', 'Data', 'Analytics'),
    (r'consumer insights', 'Consumer Insights Analyst', 'Data', 'Analytics'),
    (r'pricing analyst', 'Pricing Analyst', 'Data', 'Analytics'),
    (r'pricing strategy', 'Pricing Strategy Manager', 'Data', 'Analytics'),
    (r'credit analyst', 'Credit Analyst', 'Data', 'Credit'),
    (r'fraud analyst', 'Fraud Analyst', 'Data', 'Fraud'),
    (r'fraud model', 'Fraud Model Developer', 'Data', 'Fraud'),
    (r'data governance', 'Data Governance Lead', 'Data', 'Data Governance'),
    (r'data manager', 'Data Manager', 'Data', 'Data Management'),
    (r'data researcher', 'Data Researcher', 'Data', 'Research'),
    (r'data strategy', 'Data Strategy Manager', 'Data', 'Strategy'),
    (r'business analyst', 'Business Analyst', 'Data', 'Business Analysis'),
    (r'business systems analyst', 'Business Systems Analyst', 'Data', 'Business Analysis'),
    (r'systems analyst', 'Systems Analyst', 'Data', 'Business Analysis'),

    # ========================================================================
    # ENGINEERING - Sales/Support/Solutions Engineers 
    # ========================================================================
    (r'sales engineer', 'Sales Engineer', 'Engineering', 'Sales Engineering'),
    (r'pre[- ]?sales engineer', 'Pre-Sales Engineer', 'Engineering', 'Sales Engineering'),
    (r'post[- ]?sales engineer', 'Post-Sales Engineer', 'Engineering', 'Sales Engineering'),
    (r'support engineer', 'Support Engineer', 'Engineering', 'Support Engineering'),
    (r'customer engineer', 'Customer Engineer', 'Engineering', 'Customer Engineering'),
    (r'customer support engineer', 'Customer Support Engineer', 'Engineering', 'Support Engineering'),
    (r'technical support engineer', 'Technical Support Engineer', 'Engineering', 'Support Engineering'),
    (r'solutions engineer', 'Solutions Engineer', 'Engineering', 'Solutions Engineering'),
    (r'solution engineer', 'Solutions Engineer', 'Engineering', 'Solutions Engineering'),
    (r'field engineer', 'Field Engineer', 'Engineering', 'Field Engineering'),
    (r'implementation engineer', 'Implementation Engineer', 'Engineering', 'Implementation'),
    (r'services engineer', 'Services Engineer', 'Engineering', 'Professional Services'),
    (r'professional services engineer', 'Professional Services Engineer', 'Engineering', 'Professional Services'),
    (r'success engineer', 'Success Engineer', 'Engineering', 'Customer Success'),

    # ========================================================================
    # SOLUTIONS & ARCHITECTURE
    # ========================================================================
    (r'specialist solutions architect', 'Specialist Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'billing solutions architect', 'Billing Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'solutions architect.*manager|manager.*solutions architect', 'Solutions Architecture Manager', 'Solutions', 'Solutions Architecture'),
    (r'solutions architect', 'Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'solution architect', 'Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'partner solutions architect', 'Partner Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'resident solution architect', 'Resident Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'global solution architect', 'Global Solutions Architect', 'Solutions', 'Solutions Architecture'),
    (r'solutions consultant', 'Solutions Consultant', 'Solutions', 'Consulting'),
    (r'solutions specialist', 'Solutions Specialist', 'Solutions', 'Solutions'),
    (r'solutions consulting', 'Solutions Consultant', 'Solutions', 'Consulting'),
    (r'ai solutions consultant', 'AI Solutions Consultant', 'Solutions', 'AI Consulting'),
    (r'business systems architect', 'Business Systems Architect', 'Solutions', 'Systems Architecture'),
    (r'finance systems.*architect', 'Finance Systems Architect', 'Solutions', 'Systems Architecture'),
    (r'gtm architect', 'GTM Architect', 'Solutions', 'GTM Architecture'),
    (r'technical architect', 'Technical Architect', 'Solutions', 'Architecture'),
    (r'enterprise architect', 'Enterprise Architect', 'Solutions', 'Architecture'),
    (r'platform architect', 'Platform Architect', 'Solutions', 'Architecture'),
    (r'software architect', 'Software Architect', 'Solutions', 'Architecture'),
    (r'data architect', 'Data Architect', 'Solutions', 'Architecture'),
    (r'cloud architect', 'Cloud Architect', 'Solutions', 'Architecture'),
    (r'security architect', 'Security Architect', 'Solutions', 'Architecture'),
    (r'product security architect', 'Product Security Architect', 'Solutions', 'Architecture'),
    (r'infrastructure architect', 'Infrastructure Architect', 'Solutions', 'Architecture'),
    (r'network architect', 'Network Architect', 'Solutions', 'Architecture'),
    (r'big data architect', 'Big Data Architect', 'Solutions', 'Architecture'),
    (r'transformation architect', 'Transformation Architect', 'Solutions', 'Architecture'),
    (r'adoption architect', 'Adoption Architect', 'Solutions', 'Architecture'),
    (r'delivery architect', 'Delivery Architect', 'Solutions', 'Architecture'),
    
    # ========================================================================
    # PRODUCT
    # ========================================================================
    (r'chief product officer|cpo\b', 'Chief Product Officer', 'Product', 'Executive'),
    (r'vp.*product', 'VP of Product', 'Product', 'Product Leadership'),
    (r'head of product', 'Head of Product', 'Product', 'Product Leadership'),
    (r'director.*product', 'Director of Product', 'Product', 'Product Leadership'),
    (r'product director', 'Product Director', 'Product', 'Product Leadership'),
    (r'group product manager', 'Group Product Manager', 'Product', 'Product Management'),
    (r'product management.*manager', 'Product Management Manager', 'Product', 'Product Management'),
    (r'product manager', 'Product Manager', 'Product', 'Product Management'),
    (r'product lead', 'Product Lead', 'Product', 'Product Management'),
    (r'product owner', 'Product Owner', 'Product', 'Product Management'),
    (r'product management$', 'Product Manager', 'Product', 'Product Management'),
    (r'product analyst', 'Product Analyst', 'Product', 'Product Analytics'),
    (r'product analytics', 'Product Analyst', 'Product', 'Product Analytics'),
    (r'product operations', 'Product Operations Manager', 'Product', 'Product Operations'),
    (r'product counsel', 'Product Counsel', 'Legal', 'Product Legal'),
    (r'product communications', 'Product Communications Manager', 'Marketing', 'Product Marketing'),
    (r'product risk strategist', 'Product Risk Strategist', 'Risk', 'Risk Strategy'),
    (r'product support', 'Product Support Specialist', 'Operations', 'Support'),
    (r'product specialist', 'Product Specialist', 'Product', 'Product'),
    (r'product researcher', 'Product Researcher', 'Product', 'Research'),
    (r'product design$', 'Product Designer', 'Design', 'Product Design'),
    (r'technical program manager|tpm\b', 'Technical Program Manager', 'Product', 'Program Management'),
    (r'program manager', 'Program Manager', 'Product', 'Program Management'),
    (r'program director', 'Program Director', 'Product', 'Program Management'),
    (r'program lead', 'Program Lead', 'Product', 'Program Management'),
    (r'project manager', 'Project Manager', 'Product', 'Project Management'),
    (r'project lead', 'Project Lead', 'Product', 'Project Management'),
    (r'platform manager', 'Platform Manager', 'Product', 'Platform'),
    (r'release manager', 'Release Manager', 'Product', 'Release Management'),
    (r'launch manager', 'Launch Manager', 'Product', 'Launch'),
    
    # ========================================================================
    # DESIGN
    # ========================================================================
    (r'chief design officer', 'Chief Design Officer', 'Design', 'Executive'),
    (r'vp.*design', 'VP of Design', 'Design', 'Design Leadership'),
    (r'head of design', 'Head of Design', 'Design', 'Design Leadership'),
    (r'director.*design', 'Director of Design', 'Design', 'Design Leadership'),
    (r'design director', 'Design Director', 'Design', 'Design Leadership'),
    (r'director of learning design', 'Director of Learning Design', 'Design', 'Learning Design'),
    (r'creative director', 'Creative Director', 'Design', 'Creative'),
    (r'art director', 'Art Director', 'Design', 'Creative'),
    (r'design manager', 'Design Manager', 'Design', 'Design Management'),
    (r'design systems', 'Design Systems Designer', 'Design', 'Design Systems'),
    (r'product design manager', 'Product Design Manager', 'Design', 'Design Management'),
    (r'product design lead', 'Product Design Lead', 'Design', 'Product Design'),
    (r'product designer', 'Product Designer', 'Design', 'Product Design'),
    (r'experience designer', 'Experience Designer', 'Design', 'Experience Design'),
    (r'growth designer', 'Growth Designer', 'Design', 'Growth Design'),
    (r'designer advocate', 'Designer Advocate', 'Design', 'Design Advocacy'),
    (r'instructional designer', 'Instructional Designer', 'Design', 'Learning Design'),
    (r'learning designer', 'Learning Designer', 'Design', 'Learning Design'),
    (r'visual designer', 'Visual Designer', 'Design', 'Visual Design'),
    (r'interaction designer', 'Interaction Designer', 'Design', 'Interaction Design'),
    (r'service designer', 'Service Designer', 'Design', 'Service Design'),
    (r'systems designer', 'Systems Designer', 'Design', 'Systems Design'),
    (r'content designer', 'Content Designer', 'Design', 'Content Design'),
    (r'motion designer', 'Motion Designer', 'Design', 'Motion Design'),
    (r'ux designer|user experience designer', 'UX Designer', 'Design', 'UX Design'),
    (r'ui designer', 'UI Designer', 'Design', 'UI Design'),
    (r'ui/ux designer', 'UI/UX Designer', 'Design', 'UI/UX Design'),
    (r'ux researcher|user experience researcher', 'UX Researcher', 'Design', 'UX Research'),
    (r'user researcher', 'User Researcher', 'Design', 'UX Research'),
    (r'ux research', 'UX Researcher', 'Design', 'UX Research'),
    (r'design researcher', 'Design Researcher', 'Design', 'UX Research'),
    (r'experience researcher', 'Experience Researcher', 'Design', 'UX Research'),
    (r'graphic designer', 'Graphic Designer', 'Design', 'Graphic Design'),
    (r'brand designer', 'Brand Designer', 'Design', 'Brand Design'),
    (r'web designer', 'Web Designer', 'Design', 'Web Design'),
    (r'web producer', 'Web Producer', 'Design', 'Web Production'),
    (r'illustrator', 'Illustrator', 'Design', 'Illustration'),
    (r'animator', 'Animator', 'Design', 'Animation'),
    (r'video producer', 'Video Producer', 'Design', 'Video'),
    (r'video lead', 'Video Lead', 'Design', 'Video'),
    # Generic designer LAST
    (r'designer\b', 'Designer', 'Design', 'Design'),
    
    # ========================================================================
    # SALES - Account Development/SDR/BDR (Specific first)
    # ========================================================================
    (r'account development representative', 'Account Development Representative', 'Sales', 'Sales Development'),
    (r'account development executive', 'Account Development Executive', 'Sales', 'Sales Development'),
    (r'account development specialist', 'Account Development Specialist', 'Sales', 'Sales Development'),
    (r'account development', 'Account Development Representative', 'Sales', 'Sales Development'),
    (r'business development representative|bdr\b', 'Business Development Representative', 'Sales', 'Sales Development'),
    (r'sales development representative|sdr\b', 'Sales Development Representative', 'Sales', 'Sales Development'),
    (r'development representative', 'Development Representative', 'Sales', 'Sales Development'),
    (r'market development representative', 'Market Development Representative', 'Sales', 'Sales Development'),
    (r'partner development representative', 'Partner Development Representative', 'Sales', 'Partner Development'),
    (r'cloud partner development', 'Cloud Partner Development Representative', 'Sales', 'Partner Development'),
    
    # ========================================================================
    # SALES - Account Executive / Account Manager
    # ========================================================================
    (r'strategic account executive', 'Strategic Account Executive', 'Sales', 'Strategic Sales'),
    (r'enterprise account executive', 'Enterprise Account Executive', 'Sales', 'Enterprise Sales'),
    (r'commercial account executive', 'Commercial Account Executive', 'Sales', 'Commercial Sales'),
    (r'mid[- ]?market account executive', 'Mid-Market Account Executive', 'Sales', 'Mid-Market Sales'),
    (r'smb account executive', 'SMB Account Executive', 'Sales', 'SMB Sales'),
    (r'startup account executive', 'Startup Account Executive', 'Sales', 'Startup Sales'),
    (r'named account executive', 'Named Account Executive', 'Sales', 'Named Accounts'),
    (r'account executive', 'Account Executive', 'Sales', 'Sales'),
    (r'\bae\b,', 'Account Executive', 'Sales', 'Sales'),  # "AE, Commercial"
    (r'strategic account manager', 'Strategic Account Manager', 'Sales', 'Strategic Accounts'),
    (r'enterprise account manager', 'Enterprise Account Manager', 'Sales', 'Enterprise Sales'),
    (r'key account manager', 'Key Account Manager', 'Sales', 'Key Accounts'),
    (r'account manager', 'Account Manager', 'Sales', 'Account Management'),
    (r'technical account manager', 'Technical Account Manager', 'Sales', 'Technical Account Management'),
    (r'customer account manager', 'Customer Account Manager', 'Sales', 'Account Management'),
    
    # ========================================================================
    # SALES - Account Director / Sales Director
    # ========================================================================
    (r'strategic account director', 'Strategic Account Director', 'Sales', 'Strategic Accounts'),
    (r'enterprise account director', 'Enterprise Account Director', 'Sales', 'Enterprise Sales'),
    (r'account director.*enterprise', 'Enterprise Account Director', 'Sales', 'Enterprise Sales'),
    (r'account director', 'Account Director', 'Sales', 'Sales Leadership'),
    (r'key account director', 'Key Account Director', 'Sales', 'Key Accounts'),
    (r'director of sales', 'Director of Sales', 'Sales', 'Sales Leadership'),
    (r'sales director', 'Sales Director', 'Sales', 'Sales Leadership'),
    (r'director.*sales', 'Director of Sales', 'Sales', 'Sales Leadership'),
    (r'regional sales director', 'Regional Sales Director', 'Sales', 'Regional Sales'),
    (r'area sales director', 'Area Sales Director', 'Sales', 'Regional Sales'),
    (r'enterprise sales director', 'Enterprise Sales Director', 'Sales', 'Enterprise Sales'),
    (r'global director of sales', 'Global Director of Sales', 'Sales', 'Sales Leadership'),
    (r'director of account management', 'Director of Account Management', 'Sales', 'Account Management'),
    
    # ========================================================================
    # SALES - Sales Manager / Leadership
    # ========================================================================
    (r'vp.*sales', 'VP of Sales', 'Sales', 'Sales Leadership'),
    (r'head of sales', 'Head of Sales', 'Sales', 'Sales Leadership'),
    (r'chief revenue officer|cro\b', 'Chief Revenue Officer', 'Sales', 'Executive'),
    (r'enterprise sales manager', 'Enterprise Sales Manager', 'Sales', 'Enterprise Sales'),
    (r'commercial sales manager', 'Commercial Sales Manager', 'Sales', 'Commercial Sales'),
    (r'mid[- ]?market sales manager', 'Mid-Market Sales Manager', 'Sales', 'Mid-Market Sales'),
    (r'startup sales manager', 'Startup Sales Manager', 'Sales', 'Startup Sales'),
    (r'digital native sales manager', 'Digital Native Sales Manager', 'Sales', 'Digital Native'),
    (r'growth sales manager', 'Growth Sales Manager', 'Sales', 'Growth Sales'),
    (r'strategic sales manager', 'Strategic Sales Manager', 'Sales', 'Strategic Sales'),
    (r'regional sales manager', 'Regional Sales Manager', 'Sales', 'Regional Sales'),
    (r'territory sales manager', 'Territory Sales Manager', 'Sales', 'Territory Sales'),
    (r'inside sales manager', 'Inside Sales Manager', 'Sales', 'Inside Sales'),
    (r'field sales manager', 'Field Sales Manager', 'Sales', 'Field Sales'),
    (r'sales manager', 'Sales Manager', 'Sales', 'Sales Management'),
    (r'sales lead', 'Sales Lead', 'Sales', 'Sales'),
    (r'sales leader', 'Sales Leader', 'Sales', 'Sales Leadership'),
    (r'sales supervisor', 'Sales Supervisor', 'Sales', 'Sales Management'),
    
    # ========================================================================
    # SALES - Regional VP / RVP
    # ========================================================================
    (r'rvp.*enterprise', 'RVP Enterprise Sales', 'Sales', 'Sales Leadership'),
    (r'rvp.*sales', 'RVP Sales', 'Sales', 'Sales Leadership'),
    (r'rvp\b', 'Regional VP', 'Sales', 'Sales Leadership'),
    (r'regional vice president', 'Regional VP', 'Sales', 'Sales Leadership'),
    (r'area vice president', 'Area VP', 'Sales', 'Sales Leadership'),
    (r'avp.*sales', 'AVP Sales', 'Sales', 'Sales Leadership'),
    
    # ========================================================================
    # SALES - Sales Operations / Enablement
    # ========================================================================
    (r'sales operations manager', 'Sales Operations Manager', 'Sales', 'Sales Operations'),
    (r'sales operations lead', 'Sales Operations Lead', 'Sales', 'Sales Operations'),
    (r'sales operations analyst', 'Sales Operations Analyst', 'Sales', 'Sales Operations'),
    (r'sales operations', 'Sales Operations', 'Sales', 'Sales Operations'),
    (r'revenue operations', 'Revenue Operations', 'Sales', 'Revenue Operations'),
    (r'revops', 'Revenue Operations', 'Sales', 'Revenue Operations'),
    (r'sales enablement manager', 'Sales Enablement Manager', 'Sales', 'Sales Enablement'),
    (r'sales enablement', 'Sales Enablement Specialist', 'Sales', 'Sales Enablement'),
    (r'field enablement', 'Field Enablement Manager', 'Sales', 'Sales Enablement'),
    (r'enablement manager', 'Enablement Manager', 'Sales', 'Enablement'),
    (r'sales training', 'Sales Training Manager', 'Sales', 'Sales Enablement'),
    (r'sales programs', 'Sales Programs Manager', 'Sales', 'Sales Programs'),
    (r'sales strategy', 'Sales Strategy Manager', 'Sales', 'Sales Strategy'),
    (r'sales analytics', 'Sales Analytics Manager', 'Sales', 'Sales Analytics'),
    (r'deal desk', 'Deal Desk Analyst', 'Sales', 'Deal Desk'),
    (r'deal pricing', 'Deal Pricing Lead', 'Sales', 'Deal Desk'),
    (r'proposal manager', 'Proposal Manager', 'Sales', 'Sales Operations'),
    (r'rfx|rfp.*manager', 'RFP Manager', 'Sales', 'Sales Operations'),
    
    # ========================================================================
    # SALES - Renewals / Expansion
    # ========================================================================
    (r'renewals manager', 'Renewals Manager', 'Sales', 'Renewals'),
    (r'renewals specialist', 'Renewals Specialist', 'Sales', 'Renewals'),
    (r'renewals', 'Renewals Specialist', 'Sales', 'Renewals'),
    (r'expansion.*manager', 'Expansion Manager', 'Sales', 'Expansion'),
    (r'retention.*manager', 'Retention Manager', 'Sales', 'Retention'),
    
    # ========================================================================
    # SALES - Industry/Vertical Sales
    # ========================================================================
    (r'industry.*sales', 'Industry Sales', 'Sales', 'Industry Sales'),
    (r'vertical.*sales', 'Vertical Sales', 'Sales', 'Vertical Sales'),
    (r'healthcare.*sales', 'Healthcare Sales', 'Sales', 'Healthcare'),
    (r'financial services.*sales', 'Financial Services Sales', 'Sales', 'Financial Services'),
    (r'public sector.*sales', 'Public Sector Sales', 'Sales', 'Public Sector'),
    (r'federal.*sales', 'Federal Sales', 'Sales', 'Federal'),
    (r'government.*sales', 'Government Sales', 'Sales', 'Government'),
    
    # ========================================================================
    # SALES - Other Sales Roles
    # ========================================================================
    (r'field sales representative', 'Field Sales Representative', 'Sales', 'Field Sales'),
    (r'inside sales representative', 'Inside Sales Representative', 'Sales', 'Inside Sales'),
    (r'sales representative', 'Sales Representative', 'Sales', 'Sales'),
    (r'sales associate', 'Sales Associate', 'Sales', 'Sales'),
    (r'sales specialist', 'Sales Specialist', 'Sales', 'Sales'),
    (r'sales consultant', 'Sales Consultant', 'Sales', 'Sales'),
    (r'sales executive', 'Sales Executive', 'Sales', 'Sales'),
    (r'services sales', 'Services Sales Executive', 'Sales', 'Services Sales'),
    (r'business development manager', 'Business Development Manager', 'Sales', 'Business Development'),
    (r'business development lead', 'Business Development Lead', 'Sales', 'Business Development'),
    (r'business development$', 'Business Development Manager', 'Sales', 'Business Development'),
    (r'enterprise services manager', 'Enterprise Services Manager', 'Sales', 'Enterprise Services'),
    (r'client partner', 'Client Partner', 'Sales', 'Client Management'),
    (r'relationship manager', 'Relationship Manager', 'Sales', 'Relationship Management'),
    (r'market manager', 'Market Manager', 'Sales', 'Market Management'),
    (r'regional director', 'Regional Director', 'Sales', 'Regional Sales'),
    (r'territory manager', 'Territory Manager', 'Sales', 'Territory Sales'),
    (r'channel sales', 'Channel Sales Manager', 'Sales', 'Channel Sales'),
    (r'partner sales', 'Partner Sales Manager', 'Sales', 'Partner Sales'),
    (r'alliances manager', 'Alliances Manager', 'Sales', 'Alliances'),
    (r'strategic alliances', 'Strategic Alliances Lead', 'Sales', 'Strategic Alliances'),
    (r'genai sales', 'GenAI Sales Lead', 'Sales', 'AI Sales'),
    (r'institutional sales', 'Institutional Sales', 'Sales', 'Institutional Sales'),
    (r'ad sales|ads sales|advertising sales', 'Advertising Sales', 'Sales', 'Advertising'),
    (r'programmatic.*sales', 'Programmatic Sales', 'Sales', 'Advertising'),
    (r'media sales', 'Media Sales', 'Sales', 'Media'),
    (r'insurance.*sales', 'Insurance Sales', 'Sales', 'Insurance'),
    
    # ========================================================================
    # SALES - Salesforce Admin (often miscategorized)
    # ========================================================================
    (r'salesforce administrator', 'Salesforce Administrator', 'Sales', 'Sales Systems'),
    (r'salesforce admin', 'Salesforce Administrator', 'Sales', 'Sales Systems'),
    (r'crm administrator', 'CRM Administrator', 'Sales', 'Sales Systems'),
    (r'sales systems', 'Sales Systems Analyst', 'Sales', 'Sales Systems'),


    # ========================================================================
    # MARKETING - Leadership
    # ========================================================================
    (r'chief marketing officer|cmo\b', 'Chief Marketing Officer', 'Marketing', 'Executive'),
    (r'vp.*marketing', 'VP of Marketing', 'Marketing', 'Marketing Leadership'),
    (r'head of marketing', 'Head of Marketing', 'Marketing', 'Marketing Leadership'),
    (r'director.*marketing', 'Director of Marketing', 'Marketing', 'Marketing Leadership'),
    (r'marketing director', 'Marketing Director', 'Marketing', 'Marketing Leadership'),
    (r'global marketing director', 'Global Marketing Director', 'Marketing', 'Marketing Leadership'),
    
    # ========================================================================
    # MARKETING - Product Marketing
    # ========================================================================
    (r'product marketing manager', 'Product Marketing Manager', 'Marketing', 'Product Marketing'),
    (r'product marketing lead', 'Product Marketing Lead', 'Marketing', 'Product Marketing'),
    (r'product marketing', 'Product Marketing Manager', 'Marketing', 'Product Marketing'),
    (r'technical marketing', 'Technical Marketing Manager', 'Marketing', 'Technical Marketing'),
    (r'solutions marketing', 'Solutions Marketing Manager', 'Marketing', 'Solutions Marketing'),
    (r'portfolio marketing', 'Portfolio Marketing Manager', 'Marketing', 'Portfolio Marketing'),
    
    # ========================================================================
    # MARKETING - Growth / Demand Gen
    # ========================================================================
    (r'growth marketing manager', 'Growth Marketing Manager', 'Marketing', 'Growth'),
    (r'growth marketing', 'Growth Marketing Manager', 'Marketing', 'Growth'),
    (r'growth manager', 'Growth Manager', 'Marketing', 'Growth'),
    (r'demand generation manager', 'Demand Generation Manager', 'Marketing', 'Demand Gen'),
    (r'demand gen', 'Demand Generation Manager', 'Marketing', 'Demand Gen'),
    (r'lead generation', 'Lead Generation Manager', 'Marketing', 'Lead Gen'),
    (r'lifecycle marketing', 'Lifecycle Marketing Manager', 'Marketing', 'Lifecycle'),
    (r'retention marketing', 'Retention Marketing Manager', 'Marketing', 'Retention'),
    (r'acquisition marketing', 'Acquisition Marketing Manager', 'Marketing', 'Acquisition'),
    (r'user acquisition', 'User Acquisition Manager', 'Marketing', 'User Acquisition'),
    (r'performance marketing', 'Performance Marketing Manager', 'Marketing', 'Performance'),
    (r'paid marketing', 'Paid Marketing Manager', 'Marketing', 'Paid Media'),
    (r'paid media', 'Paid Media Manager', 'Marketing', 'Paid Media'),
    (r'paid social', 'Paid Social Manager', 'Marketing', 'Paid Media'),
    (r'paid search', 'Paid Search Manager', 'Marketing', 'Paid Media'),
    
    # ========================================================================
    # MARKETING - Content / Brand
    # ========================================================================
    (r'head of content', 'Head of Content', 'Marketing', 'Content Leadership'),
    (r'director of content', 'Director of Content', 'Marketing', 'Content Leadership'),
    (r'content marketing manager', 'Content Marketing Manager', 'Marketing', 'Content Marketing'),
    (r'content marketing lead', 'Content Marketing Lead', 'Marketing', 'Content Marketing'),
    (r'content marketing', 'Content Marketing Manager', 'Marketing', 'Content Marketing'),
    (r'content manager', 'Content Manager', 'Marketing', 'Content'),
    (r'content strategist', 'Content Strategist', 'Marketing', 'Content'),
    (r'content specialist', 'Content Specialist', 'Marketing', 'Content'),
    (r'content lead', 'Content Lead', 'Marketing', 'Content'),
    (r'content writer', 'Content Writer', 'Marketing', 'Content'),
    (r'copywriter', 'Copywriter', 'Marketing', 'Content'),
    (r'editor', 'Editor', 'Marketing', 'Content'),
    (r'editorial', 'Editorial Manager', 'Marketing', 'Content'),
    (r'brand manager', 'Brand Manager', 'Marketing', 'Brand'),
    (r'brand marketing', 'Brand Marketing Manager', 'Marketing', 'Brand'),
    (r'brand strategist', 'Brand Strategist', 'Marketing', 'Brand'),
    (r'head of brand', 'Head of Brand', 'Marketing', 'Brand Leadership'),
    (r'creative marketing', 'Creative Marketing Manager', 'Marketing', 'Creative'),
    (r'creative studio', 'Creative Studio Manager', 'Marketing', 'Creative'),
    (r'creator marketing', 'Creator Marketing Manager', 'Marketing', 'Creator'),
    (r'influencer marketing', 'Influencer Marketing Manager', 'Marketing', 'Influencer'),
    (r'influencer manager', 'Influencer Manager', 'Marketing', 'Influencer'),
    
    # ========================================================================
    # MARKETING - Communications / PR
    # ========================================================================
    (r'head of communications', 'Head of Communications', 'Marketing', 'Communications Leadership'),
    (r'director of communications', 'Director of Communications', 'Marketing', 'Communications Leadership'),
    (r'communications manager', 'Communications Manager', 'Marketing', 'Communications'),
    (r'communications specialist', 'Communications Specialist', 'Marketing', 'Communications'),
    (r'communications lead', 'Communications Lead', 'Marketing', 'Communications'),
    (r'internal communications', 'Internal Communications Manager', 'Marketing', 'Internal Communications'),
    (r'corporate communications', 'Corporate Communications Manager', 'Marketing', 'Corporate Communications'),
    (r'strategic communications', 'Strategic Communications Manager', 'Marketing', 'Communications'),
    (r'public relations|pr manager', 'Public Relations Manager', 'Marketing', 'PR'),
    (r'media relations', 'Media Relations Manager', 'Marketing', 'PR'),
    (r'analyst relations', 'Analyst Relations Manager', 'Marketing', 'Analyst Relations'),
    
    # ========================================================================
    # MARKETING - Events
    # ========================================================================
    (r'events manager', 'Events Manager', 'Marketing', 'Events'),
    (r'event marketing', 'Event Marketing Manager', 'Marketing', 'Events'),
    (r'field marketing manager', 'Field Marketing Manager', 'Marketing', 'Field Marketing'),
    (r'field marketing lead', 'Field Marketing Lead', 'Marketing', 'Field Marketing'),
    (r'field marketing specialist', 'Field Marketing Specialist', 'Marketing', 'Field Marketing'),
    (r'field marketing', 'Field Marketing Manager', 'Marketing', 'Field Marketing'),
    (r'global event', 'Global Events Manager', 'Marketing', 'Events'),
    (r'internal events', 'Internal Events Manager', 'Marketing', 'Events'),
    
    # ========================================================================
    # MARKETING - Campaigns / ABM
    # ========================================================================
    (r'campaign manager', 'Campaign Manager', 'Marketing', 'Campaigns'),
    (r'campaigns manager', 'Campaign Manager', 'Marketing', 'Campaigns'),
    (r'integrated campaigns', 'Integrated Campaigns Manager', 'Marketing', 'Campaigns'),
    (r'integrated marketing', 'Integrated Marketing Manager', 'Marketing', 'Integrated'),
    (r'abm.*manager|account.based.marketing', 'ABM Manager', 'Marketing', 'ABM'),
    (r'global abm', 'Global ABM Manager', 'Marketing', 'ABM'),
    (r'marketing campaigns', 'Marketing Campaigns Manager', 'Marketing', 'Campaigns'),
    (r'campaign operations', 'Campaign Operations Manager', 'Marketing', 'Campaigns'),
    (r'campaign strategist', 'Campaign Strategist', 'Marketing', 'Campaigns'),
    
    # ========================================================================
    # MARKETING - Digital / SEO / Social
    # ========================================================================
    (r'digital marketing manager', 'Digital Marketing Manager', 'Marketing', 'Digital'),
    (r'digital marketing', 'Digital Marketing Manager', 'Marketing', 'Digital'),
    (r'seo manager', 'SEO Manager', 'Marketing', 'SEO'),
    (r'seo specialist', 'SEO Specialist', 'Marketing', 'SEO'),
    (r'seo strategist', 'SEO Strategist', 'Marketing', 'SEO'),
    (r'seo.*generative', 'SEO & Generative Search Strategist', 'Marketing', 'SEO'),
    (r'social media manager', 'Social Media Manager', 'Marketing', 'Social Media'),
    (r'social media', 'Social Media Manager', 'Marketing', 'Social Media'),
    (r'social.*community', 'Social & Community Manager', 'Marketing', 'Social Media'),
    (r'community manager', 'Community Manager', 'Marketing', 'Community'),
    (r'community specialist', 'Community Specialist', 'Marketing', 'Community'),
    (r'community lead', 'Community Lead', 'Marketing', 'Community'),
    
    # ========================================================================
    # MARKETING - Marketing Ops / Analytics
    # ========================================================================
    (r'marketing operations manager', 'Marketing Operations Manager', 'Marketing', 'Marketing Operations'),
    (r'marketing ops', 'Marketing Operations Manager', 'Marketing', 'Marketing Operations'),
    (r'marketing automation', 'Marketing Automation Manager', 'Marketing', 'Marketing Operations'),
    (r'marketing analytics manager', 'Marketing Analytics Manager', 'Marketing', 'Marketing Analytics'),
    (r'marketing analytics', 'Marketing Analytics Manager', 'Marketing', 'Marketing Analytics'),
    (r'marketing analyst', 'Marketing Analyst', 'Marketing', 'Marketing Analytics'),
    (r'marketing science', 'Marketing Science Manager', 'Marketing', 'Marketing Science'),
    (r'martech', 'Martech Manager', 'Marketing', 'Marketing Technology'),
    (r'marketing technology', 'Marketing Technology Manager', 'Marketing', 'Marketing Technology'),
    
    # ========================================================================
    # MARKETING - Other
    # ========================================================================
    (r'consumer marketing', 'Consumer Marketing Manager', 'Marketing', 'Consumer Marketing'),
    (r'enterprise marketing', 'Enterprise Marketing Manager', 'Marketing', 'Enterprise Marketing'),
    (r'partner marketing', 'Partner Marketing Manager', 'Marketing', 'Partner Marketing'),
    (r'channel marketing', 'Channel Marketing Manager', 'Marketing', 'Channel Marketing'),
    (r'developer marketing', 'Developer Marketing Manager', 'Marketing', 'Developer Marketing'),
    (r'b2b marketing', 'B2B Marketing Manager', 'Marketing', 'B2B Marketing'),
    (r'retail marketing', 'Retail Marketing Manager', 'Marketing', 'Retail Marketing'),
    (r'regional marketing', 'Regional Marketing Manager', 'Marketing', 'Regional Marketing'),
    (r'localization manager', 'Localization Manager', 'Marketing', 'Localization'),
    (r'localization specialist', 'Localization Specialist', 'Marketing', 'Localization'),
    (r'marketing manager', 'Marketing Manager', 'Marketing', 'Marketing'),
    (r'marketing specialist', 'Marketing Specialist', 'Marketing', 'Marketing'),
    (r'marketing lead', 'Marketing Lead', 'Marketing', 'Marketing'),
    (r'marketing coordinator', 'Marketing Coordinator', 'Marketing', 'Marketing'),
    (r'marketing associate', 'Marketing Associate', 'Marketing', 'Marketing'),
    
    # ========================================================================
    # GTM (Go-To-Market)
    # ========================================================================
    (r'gtm.*industry', 'GTM Industry Lead', 'GTM', 'Industry GTM'),
    (r'gtm.*sales|sales.*gtm', 'GTM Sales Lead', 'GTM', 'Sales GTM'),
    (r'gtm strategy', 'GTM Strategy Manager', 'GTM', 'GTM Strategy'),
    (r'gtm operations', 'GTM Operations Manager', 'GTM', 'GTM Operations'),
    (r'gtm finance', 'GTM Finance Manager', 'GTM', 'GTM Finance'),
    (r'gtm enablement', 'GTM Enablement Manager', 'GTM', 'GTM Enablement'),
    (r'gtm manager', 'GTM Manager', 'GTM', 'Go-To-Market'),
    (r'gtm lead', 'GTM Lead', 'GTM', 'Go-To-Market'),
    (r'head of gtm', 'Head of GTM', 'GTM', 'GTM Leadership'),
    (r'gtm\b', 'GTM Lead', 'GTM', 'Go-To-Market'),
    
    # ========================================================================
    # PARTNERSHIPS
    # ========================================================================
    (r'head of partnerships', 'Head of Partnerships', 'Partnerships', 'Partnerships Leadership'),
    (r'director.*partnerships', 'Director of Partnerships', 'Partnerships', 'Partnerships Leadership'),
    (r'vp.*partnerships', 'VP of Partnerships', 'Partnerships', 'Partnerships Leadership'),
    (r'partnerships director', 'Partnerships Director', 'Partnerships', 'Partnerships Leadership'),
    (r'partner development manager', 'Partner Development Manager', 'Partnerships', 'Partner Development'),
    (r'partner solutions architect', 'Partner Solutions Architect', 'Partnerships', 'Partner Solutions'),
    (r'partner engineer', 'Partner Engineer', 'Partnerships', 'Partner Engineering'),
    (r'partner success manager', 'Partner Success Manager', 'Partnerships', 'Partner Success'),
    (r'partner manager', 'Partner Manager', 'Partnerships', 'Partnerships'),
    (r'partner lead', 'Partner Lead', 'Partnerships', 'Partnerships'),
    (r'strategic partnerships manager', 'Strategic Partnerships Manager', 'Partnerships', 'Strategic Partnerships'),
    (r'strategic partnerships', 'Strategic Partnerships Manager', 'Partnerships', 'Strategic Partnerships'),
    (r'technology partnerships', 'Technology Partnerships Manager', 'Partnerships', 'Technology Partnerships'),
    (r'channel partnerships', 'Channel Partnerships Manager', 'Partnerships', 'Channel Partnerships'),
    (r'channel program', 'Channel Program Manager', 'Partnerships', 'Channel Programs'),
    (r'channel manager', 'Channel Manager', 'Partnerships', 'Channel'),
    (r'alliance manager', 'Alliance Manager', 'Partnerships', 'Alliances'),
    (r'regional alliance', 'Regional Alliance Manager', 'Partnerships', 'Alliances'),
    (r'global partner', 'Global Partner Lead', 'Partnerships', 'Global Partnerships'),
    (r'risk partnerships', 'Risk Partnerships Manager', 'Partnerships', 'Risk Partnerships'),
    (r'investor partnerships', 'Investor Partnerships Lead', 'Partnerships', 'Investor Relations'),
    (r'payments partnership', 'Payments Partnerships Manager', 'Partnerships', 'Payments Partnerships'),
    (r'financial partnerships', 'Financial Partnerships Manager', 'Partnerships', 'Financial Partnerships'),
    (r'commercial partnerships', 'Commercial Partnerships Manager', 'Partnerships', 'Commercial Partnerships'),
    (r'ecosystem.*manager', 'Ecosystem Manager', 'Partnerships', 'Ecosystem'),
    (r'ecosystem.*lead', 'Ecosystem Lead', 'Partnerships', 'Ecosystem'),
    (r'partnerships manager', 'Partnerships Manager', 'Partnerships', 'Partnerships'),
    (r'partnerships specialist', 'Partnerships Specialist', 'Partnerships', 'Partnerships'),
    (r'partnerships lead', 'Partnerships Lead', 'Partnerships', 'Partnerships'),
    
    # ========================================================================
    # PEOPLE - Partner roles
    # ========================================================================
    (r'compensation partner', 'Compensation Partner', 'People', 'Compensation'),
    (r'benefits partner', 'Benefits Partner', 'People', 'Benefits'),
    (r'talent partner', 'Talent Partner', 'People', 'Recruiting'),
    (r'people partner', 'People Partner', 'People', 'People Partners'),
    (r'hr partner', 'HR Partner', 'People', 'HR'),
    (r'recruiting partner', 'Recruiting Partner', 'People', 'Recruiting'),
    (r'hrbp|hr business partner', 'HR Business Partner', 'People', 'HR Business Partners'),
    (r'people business partner', 'People Business Partner', 'People', 'HR Business Partners'),

    # ========================================================================
    # PEOPLE / HR - Leadership
    # ========================================================================
    (r'chief people officer', 'Chief People Officer', 'People', 'Executive'),
    (r'chief human resources|chro', 'Chief Human Resources Officer', 'People', 'Executive'),
    (r'vp.*people', 'VP of People', 'People', 'People Leadership'),
    (r'vp.*human resources|vp.*hr', 'VP of HR', 'People', 'People Leadership'),
    (r'head of people', 'Head of People', 'People', 'People Leadership'),
    (r'head of hr|head of human resources', 'Head of HR', 'People', 'People Leadership'),
    (r'director.*people', 'Director of People', 'People', 'People Leadership'),
    (r'director.*hr|director.*human resources', 'Director of HR', 'People', 'People Leadership'),
    (r'people director', 'People Director', 'People', 'People Leadership'),
    
    # ========================================================================
    # PEOPLE / HR - Business Partners
    # ========================================================================
    (r'people business partner|hr business partner|hrbp', 'People Business Partner', 'People', 'HR Business Partners'),
    (r'people partner', 'People Partner', 'People', 'People Partners'),
    (r'people consultant', 'People Consultant', 'People', 'People Partners'),
    (r'hr generalist', 'HR Generalist', 'People', 'HR'),
    (r'people generalist', 'People Generalist', 'People', 'HR'),
    (r'people team', 'People Team Partner', 'People', 'People Partners'),
    
    # ========================================================================
    # PEOPLE / HR - Recruiting / Talent Acquisition
    # ========================================================================
    (r'head of talent acquisition', 'Head of Talent Acquisition', 'People', 'Recruiting Leadership'),
    (r'director.*talent acquisition', 'Director of Talent Acquisition', 'People', 'Recruiting Leadership'),
    (r'director.*recruiting', 'Director of Recruiting', 'People', 'Recruiting Leadership'),
    (r'talent acquisition manager', 'Talent Acquisition Manager', 'People', 'Recruiting'),
    (r'talent acquisition', 'Talent Acquisition', 'People', 'Recruiting'),
    (r'recruiting manager', 'Recruiting Manager', 'People', 'Recruiting'),
    (r'recruiting lead', 'Recruiting Lead', 'People', 'Recruiting'),
    (r'recruiter', 'Recruiter', 'People', 'Recruiting'),
    (r'recruiting coordinator', 'Recruiting Coordinator', 'People', 'Recruiting'),
    (r'recruiting operations', 'Recruiting Operations Manager', 'People', 'Recruiting Operations'),
    (r'recruitment', 'Recruiter', 'People', 'Recruiting'),
    (r'sourcer|sourcing specialist', 'Sourcer', 'People', 'Recruiting'),
    (r'talent sourcing', 'Talent Sourcer', 'People', 'Recruiting'),
    (r'talent partner', 'Talent Partner', 'People', 'Recruiting'),
    (r'technical recruiter', 'Technical Recruiter', 'People', 'Recruiting'),
    (r'university recruiter', 'University Recruiter', 'People', 'Recruiting'),
    (r'executive recruiter', 'Executive Recruiter', 'People', 'Recruiting'),
    
    # ========================================================================
    # PEOPLE / HR - Compensation & Benefits
    # ========================================================================
    (r'director.*compensation', 'Director of Compensation', 'People', 'Compensation'),
    (r'head of.*compensation', 'Head of Compensation', 'People', 'Compensation'),
    (r'compensation manager', 'Compensation Manager', 'People', 'Compensation'),
    (r'compensation analyst', 'Compensation Analyst', 'People', 'Compensation'),
    (r'compensation specialist', 'Compensation Specialist', 'People', 'Compensation'),
    (r'total rewards', 'Total Rewards Manager', 'People', 'Total Rewards'),
    (r'benefits manager', 'Benefits Manager', 'People', 'Benefits'),
    (r'benefits specialist', 'Benefits Specialist', 'People', 'Benefits'),
    (r'benefits analyst', 'Benefits Analyst', 'People', 'Benefits'),
    (r'payroll manager', 'Payroll Manager', 'People', 'Payroll'),
    (r'payroll specialist', 'Payroll Specialist', 'People', 'Payroll'),
    (r'payroll analyst', 'Payroll Analyst', 'People', 'Payroll'),
    (r'payroll', 'Payroll Specialist', 'People', 'Payroll'),
    (r'equity administration', 'Equity Administration Manager', 'People', 'Equity'),
    (r'stock.*admin', 'Stock Administrator', 'People', 'Equity'),
    
    # ========================================================================
    # PEOPLE / HR - People Ops / HRIS
    # ========================================================================
    (r'people ops manager|people operations manager', 'People Operations Manager', 'People', 'People Ops'),
    (r'people ops|people operations', 'People Operations Specialist', 'People', 'People Ops'),
    (r'people services', 'People Services Specialist', 'People', 'People Ops'),
    (r'hr operations', 'HR Operations Specialist', 'People', 'People Ops'),
    (r'hris manager', 'HRIS Manager', 'People', 'HRIS'),
    (r'hris analyst', 'HRIS Analyst', 'People', 'HRIS'),
    (r'hris', 'HRIS Analyst', 'People', 'HRIS'),
    (r'people systems manager', 'People Systems Manager', 'People', 'HRIS'),
    (r'people systems analyst', 'People Systems Analyst', 'People', 'HRIS'),
    (r'people systems', 'People Systems Analyst', 'People', 'HRIS'),
    (r'workday.*analyst', 'Workday Analyst', 'People', 'HRIS'),
    (r'workday.*specialist', 'Workday Specialist', 'People', 'HRIS'),
    (r'workday.*admin', 'Workday Administrator', 'People', 'HRIS'),
    
    # ========================================================================
    # PEOPLE / HR - L&D / Talent Management
    # ========================================================================
    (r'learning.*development manager|l&d manager', 'Learning & Development Manager', 'People', 'L&D'),
    (r'learning.*development|l&d', 'Learning & Development', 'People', 'L&D'),
    (r'talent development', 'Talent Development Manager', 'People', 'Talent Development'),
    (r'talent management', 'Talent Management Manager', 'People', 'Talent Management'),
    (r'global talent management', 'Global Talent Management Manager', 'People', 'Talent Management'),
    (r'leadership development', 'Leadership Development Manager', 'People', 'L&D'),
    (r'training manager', 'Training Manager', 'People', 'Training'),
    (r'training specialist', 'Training Specialist', 'People', 'Training'),
    (r'learning manager', 'Learning Manager', 'People', 'L&D'),
    (r'learning specialist', 'Learning Specialist', 'People', 'L&D'),
    
    # ========================================================================
    # PEOPLE / HR - Employee Relations / Other
    # ========================================================================
    (r'employee relations', 'Employee Relations Specialist', 'People', 'Employee Relations'),
    (r'team member relations', 'Team Member Relations Manager', 'People', 'Employee Relations'),
    (r'employee engagement', 'Employee Engagement Manager', 'People', 'Employee Engagement'),
    (r'culture specialist', 'Culture Specialist', 'People', 'Culture'),
    (r'dei|diversity.*inclusion', 'DEI Manager', 'People', 'DEI'),
    (r'immigration.*mobility', 'Immigration & Mobility Manager', 'People', 'Immigration'),
    (r'workplace experience', 'Workplace Experience Manager', 'People', 'Workplace'),
    (r'people analytics', 'People Analytics Manager', 'People', 'People Analytics'),
    (r'people scientist', 'People Scientist', 'People', 'People Analytics'),
    (r'hr specialist', 'HR Specialist', 'People', 'HR'),
    (r'human resources', 'HR Specialist', 'People', 'HR'),
    (r'\bhr\b', 'HR Specialist', 'People', 'HR'),
    
    # ========================================================================
    # FINANCE - Leadership
    # ========================================================================
    (r'chief financial officer|cfo\b', 'Chief Financial Officer', 'Finance', 'Executive'),
    (r'vp.*finance', 'VP of Finance', 'Finance', 'Finance Leadership'),
    (r'head of finance', 'Head of Finance', 'Finance', 'Finance Leadership'),
    (r'director.*finance', 'Director of Finance', 'Finance', 'Finance Leadership'),
    (r'finance director', 'Finance Director', 'Finance', 'Finance Leadership'),
    (r'controller', 'Controller', 'Finance', 'Controllership'),
    (r'financial controller', 'Financial Controller', 'Finance', 'Controllership'),
    (r'legal entity controller', 'Legal Entity Controller', 'Finance', 'Controllership'),
    
    # ========================================================================
    # FINANCE - FP&A
    # ========================================================================
    (r'fp&a manager', 'FP&A Manager', 'Finance', 'FP&A'),
    (r'fp&a analyst', 'FP&A Analyst', 'Finance', 'FP&A'),
    (r'fp&a lead', 'FP&A Lead', 'Finance', 'FP&A'),
    (r'fp&a', 'FP&A Analyst', 'Finance', 'FP&A'),
    (r'financial planning.*analysis', 'FP&A Analyst', 'Finance', 'FP&A'),
    (r'financial planning', 'Financial Planning Manager', 'Finance', 'FP&A'),
    (r'strategic finance', 'Strategic Finance', 'Finance', 'Strategic Finance'),
    
    # ========================================================================
    # FINANCE - Accounting
    # ========================================================================
    (r'head of.*accounting', 'Head of Accounting', 'Finance', 'Accounting Leadership'),
    (r'director.*accounting', 'Director of Accounting', 'Finance', 'Accounting Leadership'),
    (r'accounting manager', 'Accounting Manager', 'Finance', 'Accounting'),
    (r'accountant', 'Accountant', 'Finance', 'Accounting'),
    (r'accounting', 'Accountant', 'Finance', 'Accounting'),
    (r'accounts payable', 'Accounts Payable Specialist', 'Finance', 'Accounting'),
    (r'accounts receivable', 'Accounts Receivable Specialist', 'Finance', 'Accounting'),
    (r'general ledger', 'General Ledger Accountant', 'Finance', 'Accounting'),
    (r'revenue accounting', 'Revenue Accounting Manager', 'Finance', 'Revenue Accounting'),
    (r'revenue recognition', 'Revenue Recognition Manager', 'Finance', 'Revenue Accounting'),
    (r'technical accounting', 'Technical Accounting Manager', 'Finance', 'Technical Accounting'),
    (r'financial reporting', 'Financial Reporting Manager', 'Finance', 'Financial Reporting'),
    (r'sec reporting', 'SEC Reporting Manager', 'Finance', 'SEC Reporting'),
    (r'external reporting', 'External Reporting Manager', 'Finance', 'Financial Reporting'),
    (r'regulatory reporting', 'Regulatory Reporting Analyst', 'Finance', 'Regulatory Reporting'),
    (r'bookkeeper', 'Bookkeeper', 'Finance', 'Accounting'),
    
    # ========================================================================
    # FINANCE - Tax & Treasury
    # ========================================================================
    (r'tax manager', 'Tax Manager', 'Finance', 'Tax'),
    (r'tax analyst', 'Tax Analyst', 'Finance', 'Tax'),
    (r'tax specialist', 'Tax Specialist', 'Finance', 'Tax'),
    (r'tax director', 'Tax Director', 'Finance', 'Tax'),
    (r'international tax', 'International Tax Manager', 'Finance', 'Tax'),
    (r'tax controversy', 'Tax Controversy Manager', 'Finance', 'Tax'),
    (r'treasury manager', 'Treasury Manager', 'Finance', 'Treasury'),
    (r'treasury analyst', 'Treasury Analyst', 'Finance', 'Treasury'),
    (r'treasury', 'Treasury Specialist', 'Finance', 'Treasury'),
    (r'capital markets manager', 'Capital Markets Manager', 'Finance', 'Capital Markets'),
    (r'capital markets', 'Capital Markets Analyst', 'Finance', 'Capital Markets'),
    
    # ========================================================================
    # FINANCE - Billing & Revenue Ops
    # ========================================================================
    (r'billing manager', 'Billing Manager', 'Finance', 'Billing'),
    (r'billing operations', 'Billing Operations Manager', 'Finance', 'Billing'),
    (r'billing specialist', 'Billing Specialist', 'Finance', 'Billing'),
    (r'billing analyst', 'Billing Analyst', 'Finance', 'Billing'),
    (r'billing systems', 'Billing Systems Analyst', 'Finance', 'Billing'),
    (r'revenue operations', 'Revenue Operations', 'Finance', 'Revenue Operations'),
    (r'order management', 'Order Management Specialist', 'Finance', 'Order Management'),
    (r'commission analyst', 'Commission Analyst', 'Finance', 'Commissions'),
    (r'commissions', 'Commissions Analyst', 'Finance', 'Commissions'),
    
    # ========================================================================
    # FINANCE - Other
    # ========================================================================
    (r'finance manager', 'Finance Manager', 'Finance', 'Finance'),
    (r'finance lead', 'Finance Lead', 'Finance', 'Finance'),
    (r'finance analyst', 'Finance Analyst', 'Finance', 'Finance'),
    (r'finance business partner', 'Finance Business Partner', 'Finance', 'Finance'),
    (r'finance systems', 'Finance Systems Manager', 'Finance', 'Finance Systems'),
    (r'finance transformation', 'Finance Transformation Manager', 'Finance', 'Finance Transformation'),
    (r'financial analyst', 'Financial Analyst', 'Finance', 'Financial Analysis'),
    (r'financial representative', 'Financial Representative', 'Finance', 'Finance'),
    (r'investor relations', 'Investor Relations Manager', 'Finance', 'Investor Relations'),
    (r'internal audit', 'Internal Auditor', 'Finance', 'Audit'),
    (r'auditor', 'Auditor', 'Finance', 'Audit'),
    (r'sox', 'SOX Analyst', 'Finance', 'SOX'),
    (r'procurement manager', 'Procurement Manager', 'Finance', 'Procurement'),
    (r'procurement analyst', 'Procurement Analyst', 'Finance', 'Procurement'),
    (r'procurement specialist', 'Procurement Specialist', 'Finance', 'Procurement'),
    (r'procurement', 'Procurement Specialist', 'Finance', 'Procurement'),
    (r'sourcing manager', 'Sourcing Manager', 'Finance', 'Sourcing'),
    (r'strategic sourcing', 'Strategic Sourcing Manager', 'Finance', 'Sourcing'),
    
    # ========================================================================
    # RISK - Credit roles
    # ========================================================================
    (r'credit risk strategy.*analyst', 'Credit Risk Strategy Analyst', 'Risk', 'Credit Risk'),
    (r'credit risk strategy.*manager', 'Credit Risk Strategy Manager', 'Risk', 'Credit Risk'),
    (r'credit risk strategy', 'Credit Risk Strategy Analyst', 'Risk', 'Credit Risk'),
    (r'credit strategy.*analyst', 'Credit Strategy Analyst', 'Risk', 'Credit'),
    (r'credit strategy', 'Credit Strategy Analyst', 'Risk', 'Credit'),
    
    # Credit Risk Operations
    (r'credit risk.*operations.*manager', 'Credit Risk Operations Manager', 'Risk', 'Credit Risk'),
    (r'credit risk.*operations', 'Credit Risk Operations Specialist', 'Risk', 'Credit Risk'),
    
    # Credit Risk general
    (r'credit risk.*manager', 'Credit Risk Manager', 'Risk', 'Credit Risk'),
    (r'credit risk.*analyst', 'Credit Risk Analyst', 'Risk', 'Credit Risk'),
    (r'credit risk.*lead', 'Credit Risk Lead', 'Risk', 'Credit Risk'),
    (r'credit risk', 'Credit Risk Specialist', 'Risk', 'Credit Risk'),
    
    # Credit Operations (without "risk")
    (r'credit operations.*manager', 'Credit Operations Manager', 'Risk', 'Credit Operations'),
    (r'credit operations.*analyst', 'Credit Operations Analyst', 'Risk', 'Credit Operations'),
    (r'credit operations', 'Credit Operations Specialist', 'Risk', 'Credit Operations'),
    
    # Credit general
    (r'credit analyst', 'Credit Analyst', 'Risk', 'Credit'),
    (r'credit manager', 'Credit Manager', 'Risk', 'Credit'),

    # ========================================================================
    # RISK & COMPLIANCE
    # ========================================================================
    (r'head of risk', 'Head of Risk', 'Risk', 'Risk Leadership'),
    (r'chief risk officer', 'Chief Risk Officer', 'Risk', 'Executive'),
    (r'director.*risk', 'Director of Risk', 'Risk', 'Risk Leadership'),
    (r'risk manager', 'Risk Manager', 'Risk', 'Risk Management'),
    (r'risk analyst', 'Risk Analyst', 'Risk', 'Risk'),
    (r'risk specialist', 'Risk Specialist', 'Risk', 'Risk'),
    (r'risk operations manager', 'Risk Operations Manager', 'Risk', 'Risk Operations'),
    (r'risk operations analyst', 'Risk Operations Analyst', 'Risk', 'Risk Operations'),
    (r'risk operations', 'Risk Operations Specialist', 'Risk', 'Risk Operations'),
    (r'operational risk', 'Operational Risk Manager', 'Risk', 'Operational Risk'),
    (r'credit risk', 'Credit Risk Analyst', 'Risk', 'Credit Risk'),
    (r'market risk', 'Market Risk Analyst', 'Risk', 'Market Risk'),
    (r'model risk', 'Model Risk Specialist', 'Risk', 'Model Risk'),
    (r'liquidity risk', 'Liquidity Risk Analyst', 'Risk', 'Liquidity Risk'),
    (r'enterprise risk', 'Enterprise Risk Manager', 'Risk', 'Enterprise Risk'),
    (r'product risk', 'Product Risk Strategist', 'Risk', 'Product Risk'),
    (r'user risk', 'User Risk Strategist', 'Risk', 'User Risk'),
    (r'fraud.*manager', 'Fraud Manager', 'Risk', 'Fraud'),
    (r'fraud.*analyst', 'Fraud Analyst', 'Risk', 'Fraud'),
    (r'fraud.*specialist', 'Fraud Specialist', 'Risk', 'Fraud'),
    (r'fraud.*investigat', 'Fraud Investigator', 'Risk', 'Fraud'),
    (r'fraud.*strateg', 'Fraud Strategist', 'Risk', 'Fraud'),
    (r'fraud.*prevention', 'Fraud Prevention Specialist', 'Risk', 'Fraud'),
    (r'fraud', 'Fraud Specialist', 'Risk', 'Fraud'),
    (r'financial crimes', 'Financial Crimes Specialist', 'Risk', 'Financial Crimes'),
    (r'aml.*manager', 'AML Manager', 'Risk', 'AML'),
    (r'aml.*analyst', 'AML Analyst', 'Risk', 'AML'),
    (r'aml|anti.?money.?laundering', 'AML Specialist', 'Risk', 'AML'),
    (r'kyc.*manager', 'KYC Manager', 'Risk', 'KYC'),
    (r'kyc.*analyst', 'KYC Analyst', 'Risk', 'KYC'),
    (r'kyc|know your customer', 'KYC Specialist', 'Risk', 'KYC'),
    (r'cdd.*analyst', 'CDD Analyst', 'Risk', 'KYC'),
    (r'sanctions', 'Sanctions Specialist', 'Risk', 'Sanctions'),
    (r'stress testing', 'Stress Testing Manager', 'Risk', 'Risk Analytics'),
    (r'risk analytics', 'Risk Analytics Manager', 'Risk', 'Risk Analytics'),
    (r'risk.*analyst', 'Risk Analyst', 'Data', 'Risk'),
    (r'risk reporting', 'Risk Reporting Manager', 'Risk', 'Risk Reporting'),
    
    # ========================================================================
    # LEGAL
    # ========================================================================
    (r'general counsel', 'General Counsel', 'Legal', 'Legal Leadership'),
    (r'chief legal officer|clo\b', 'Chief Legal Officer', 'Legal', 'Executive'),
    (r'vp.*legal', 'VP of Legal', 'Legal', 'Legal Leadership'),
    (r'head of legal', 'Head of Legal', 'Legal', 'Legal Leadership'),
    (r'director.*legal', 'Director of Legal', 'Legal', 'Legal Leadership'),
    (r'legal director', 'Legal Director', 'Legal', 'Legal Leadership'),
    (r'deputy general counsel', 'Deputy General Counsel', 'Legal', 'Legal Leadership'),
    (r'associate general counsel', 'Associate General Counsel', 'Legal', 'Legal'),
    (r'commercial counsel', 'Commercial Counsel', 'Legal', 'Commercial Legal'),
    (r'corporate counsel', 'Corporate Counsel', 'Legal', 'Corporate Legal'),
    (r'employment counsel', 'Employment Counsel', 'Legal', 'Employment Law'),
    (r'product counsel', 'Product Counsel', 'Legal', 'Product Legal'),
    (r'privacy counsel', 'Privacy Counsel', 'Legal', 'Privacy'),
    (r'regulatory counsel', 'Regulatory Counsel', 'Legal', 'Regulatory'),
    (r'litigation counsel', 'Litigation Counsel', 'Legal', 'Litigation'),
    (r'ip counsel|intellectual property counsel', 'IP Counsel', 'Legal', 'IP'),
    (r'legal counsel', 'Legal Counsel', 'Legal', 'Legal'),
    (r'attorney', 'Attorney', 'Legal', 'Legal'),
    (r'lawyer', 'Lawyer', 'Legal', 'Legal'),
    (r'counsel', 'Counsel', 'Legal', 'Legal'),
    (r'paralegal', 'Paralegal', 'Legal', 'Legal'),
    (r'legal operations', 'Legal Operations Manager', 'Legal', 'Legal Operations'),
    (r'legal ops', 'Legal Operations Manager', 'Legal', 'Legal Operations'),
    (r'contracts manager', 'Contracts Manager', 'Legal', 'Contracts'),
    (r'contracts negotiator', 'Contracts Negotiator', 'Legal', 'Contracts'),
    (r'contract manager', 'Contract Manager', 'Legal', 'Contracts'),
    (r'contract admin', 'Contract Administrator', 'Legal', 'Contracts'),
    (r'legal specialist', 'Legal Specialist', 'Legal', 'Legal'),
    (r'legal analyst', 'Legal Analyst', 'Legal', 'Legal'),
    (r'compliance manager', 'Compliance Manager', 'Legal', 'Compliance'),
    (r'compliance analyst', 'Compliance Analyst', 'Legal', 'Compliance'),
    (r'compliance specialist', 'Compliance Specialist', 'Legal', 'Compliance'),
    (r'compliance officer', 'Compliance Officer', 'Legal', 'Compliance'),
    (r'compliance', 'Compliance Specialist', 'Legal', 'Compliance'),
    (r'regulatory.*manager', 'Regulatory Manager', 'Legal', 'Regulatory'),
    (r'regulatory.*analyst', 'Regulatory Analyst', 'Legal', 'Regulatory'),
    (r'regulatory.*specialist', 'Regulatory Specialist', 'Legal', 'Regulatory'),
    (r'regulatory', 'Regulatory Specialist', 'Legal', 'Regulatory'),
    (r'privacy manager', 'Privacy Manager', 'Legal', 'Privacy'),
    (r'privacy.*compliance', 'Privacy Compliance Manager', 'Legal', 'Privacy'),
    (r'data protection', 'Data Protection Officer', 'Legal', 'Privacy'),
    (r'governance.*risk.*compliance|grc', 'GRC Manager', 'Legal', 'GRC'),

    # ========================================================================
    # OPERATIONS - Leadership
    # ========================================================================
    (r'chief operating officer|coo\b', 'Chief Operating Officer', 'Operations', 'Executive'),
    (r'vp.*operations', 'VP of Operations', 'Operations', 'Operations Leadership'),
    (r'head of operations', 'Head of Operations', 'Operations', 'Operations Leadership'),
    (r'director.*operations', 'Director of Operations', 'Operations', 'Operations Leadership'),
    (r'operations director', 'Operations Director', 'Operations', 'Operations Leadership'),
    
    # ========================================================================
    # OPERATIONS - Business Operations
    # ========================================================================
    (r'business operations manager', 'Business Operations Manager', 'Operations', 'Business Ops'),
    (r'business operations', 'Business Operations', 'Operations', 'Business Ops'),
    (r'biz ops', 'Business Operations Manager', 'Operations', 'Business Ops'),
    (r'operations manager', 'Operations Manager', 'Operations', 'Operations'),
    (r'operations lead', 'Operations Lead', 'Operations', 'Operations'),
    (r'operations analyst', 'Operations Analyst', 'Operations', 'Operations'),
    (r'operations associate', 'Operations Associate', 'Operations', 'Operations'),
    (r'operations specialist', 'Operations Specialist', 'Operations', 'Operations'),
    (r'operations coordinator', 'Operations Coordinator', 'Operations', 'Operations'),
    (r'strategy.*operations|operations.*strategy', 'Strategy & Operations', 'Operations', 'Strategy & Ops'),
    
    # ========================================================================
    # OPERATIONS - Technical Operations
    # ========================================================================
    (r'technical operations manager', 'Technical Operations Manager', 'Operations', 'Technical Ops'),
    (r'technical operations', 'Technical Operations Specialist', 'Operations', 'Technical Ops'),
    (r'it operations', 'IT Operations Manager', 'Operations', 'IT Ops'),
    (r'it support manager', 'IT Support Manager', 'Operations', 'IT Support'),
    (r'it support', 'IT Support Specialist', 'Operations', 'IT Support'),
    (r'executive it support', 'Executive IT Support', 'Operations', 'IT Support'),
    (r'service desk', 'Service Desk Manager', 'Operations', 'IT Support'),
    (r'help desk', 'Help Desk Specialist', 'Operations', 'IT Support'),
    
    # ========================================================================
    # OPERATIONS - Implementation / Professional Services
    # ========================================================================
    (r'implementation manager', 'Implementation Manager', 'Operations', 'Implementation'),
    (r'implementation consultant', 'Implementation Consultant', 'Operations', 'Implementation'),
    (r'implementation specialist', 'Implementation Specialist', 'Operations', 'Implementation'),
    (r'professional services manager', 'Professional Services Manager', 'Operations', 'Professional Services'),
    (r'professional services consultant', 'Professional Services Consultant', 'Operations', 'Professional Services'),
    (r'professional services', 'Professional Services', 'Operations', 'Professional Services'),
    (r'services consultant', 'Services Consultant', 'Operations', 'Consulting'),
    (r'delivery manager', 'Delivery Manager', 'Operations', 'Delivery'),
    (r'delivery consultant', 'Delivery Consultant', 'Operations', 'Delivery'),
    (r'engagement manager', 'Engagement Manager', 'Operations', 'Engagement'),
    (r'client services', 'Client Services Manager', 'Operations', 'Client Services'),
    
    # ========================================================================
    # OPERATIONS - Trust & Safety
    # ========================================================================
    (r'head of trust.*safety', 'Head of Trust & Safety', 'Operations', 'Trust & Safety Leadership'),
    (r'director.*trust.*safety', 'Director of Trust & Safety', 'Operations', 'Trust & Safety Leadership'),
    (r'trust.*safety.*manager', 'Trust & Safety Manager', 'Operations', 'Trust & Safety'),
    (r'trust.*safety.*specialist', 'Trust & Safety Specialist', 'Operations', 'Trust & Safety'),
    (r'trust.*safety.*analyst', 'Trust & Safety Analyst', 'Operations', 'Trust & Safety'),
    (r'trust.*safety', 'Trust & Safety Specialist', 'Operations', 'Trust & Safety'),
    (r'safety specialist', 'Safety Specialist', 'Operations', 'Safety'),
    (r'content moderation', 'Content Moderator', 'Operations', 'Trust & Safety'),
    (r'policy.*specialist', 'Policy Specialist', 'Operations', 'Policy'),
    (r'policy.*manager', 'Policy Manager', 'Operations', 'Policy'),
    
    # ========================================================================
    # OPERATIONS - Vendor / Procurement
    # ========================================================================
    (r'vendor manager', 'Vendor Manager', 'Operations', 'Vendor Management'),
    (r'vendor operations', 'Vendor Operations Manager', 'Operations', 'Vendor Management'),
    (r'vendor performance', 'Vendor Performance Manager', 'Operations', 'Vendor Management'),
    (r'vendor strategist', 'Vendor Strategist', 'Operations', 'Vendor Management'),
    (r'supplier.*manager', 'Supplier Manager', 'Operations', 'Vendor Management'),
    (r'third party.*manager', 'Third Party Manager', 'Operations', 'Vendor Management'),
    
    # ========================================================================
    # OPERATIONS - Facilities / Workplace
    # ========================================================================
    (r'facilities manager', 'Facilities Manager', 'Operations', 'Facilities'),
    (r'facilities', 'Facilities Specialist', 'Operations', 'Facilities'),
    (r'workplace manager', 'Workplace Manager', 'Operations', 'Workplace'),
    (r'workplace.*coordinator', 'Workplace Coordinator', 'Operations', 'Workplace'),
    (r'workplace.*specialist', 'Workplace Specialist', 'Operations', 'Workplace'),
    (r'office manager', 'Office Manager', 'Operations', 'Office Management'),
    (r'office coordinator', 'Office Coordinator', 'Operations', 'Office Management'),
    (r'space.*community manager', 'Space & Community Manager', 'Operations', 'Workplace'),
    (r'real estate', 'Real Estate Manager', 'Operations', 'Real Estate'),
    
    # ========================================================================
    # OPERATIONS - Administrative
    # ========================================================================
    (r'executive assistant', 'Executive Assistant', 'Operations', 'Executive Support'),
    (r'administrative assistant', 'Administrative Assistant', 'Operations', 'Administration'),
    (r'administrative manager', 'Administrative Manager', 'Operations', 'Administration'),
    (r'administrative business partner', 'Administrative Business Partner', 'Operations', 'Administration'),
    (r'chief of staff', 'Chief of Staff', 'Operations', 'Executive Support'),
    (r'business partner analyst', 'Business Partner Analyst', 'Operations', 'Business Analytics'),
    
    # ========================================================================
    # OPERATIONS - Security (Physical)
    # ========================================================================
    (r'physical security', 'Physical Security Manager', 'Operations', 'Security'),
    (r'security operations coordinator', 'Security Operations Coordinator', 'Operations', 'Security'),
    (r'facility security', 'Facility Security Officer', 'Operations', 'Security'),
    (r'protective intelligence', 'Protective Intelligence Analyst', 'Operations', 'Security'),
    (r'investigations.*manager', 'Investigations Manager', 'Operations', 'Investigations'),
    (r'investigator', 'Investigator', 'Operations', 'Investigations'),
    
    # ========================================================================
    # OPERATIONS - Other
    # ========================================================================
    (r'program coordinator', 'Program Coordinator', 'Operations', 'Program Management'),
    (r'project coordinator', 'Project Coordinator', 'Operations', 'Project Management'),
    (r'logistics', 'Logistics Specialist', 'Operations', 'Logistics'),
    (r'supply chain', 'Supply Chain Manager', 'Operations', 'Supply Chain'),
    (r'warehouse', 'Warehouse Manager', 'Operations', 'Warehouse'),
    (r'fulfillment', 'Fulfillment Manager', 'Operations', 'Fulfillment'),
    (r'fleet', 'Fleet Manager', 'Operations', 'Fleet'),
    (r'transportation', 'Transportation Manager', 'Operations', 'Transportation'),
    (r'customs', 'Customs Specialist', 'Operations', 'Customs'),
    (r'trade advisory', 'Trade Advisory Lead', 'Operations', 'Trade'),
    (r'air freight', 'Air Freight Manager', 'Operations', 'Freight'),
    (r'ocean freight', 'Ocean Freight Manager', 'Operations', 'Freight'),
    (r'parcel ops', 'Parcel Operations Manager', 'Operations', 'Logistics'),
    
    # ========================================================================
    # CUSTOMER SUCCESS
    # ========================================================================
    (r'head of customer success', 'Head of Customer Success', 'Customer Success', 'CS Leadership'),
    (r'director.*customer success', 'Director of Customer Success', 'Customer Success', 'CS Leadership'),
    (r'vp.*customer success', 'VP of Customer Success', 'Customer Success', 'CS Leadership'),
    (r'customer success manager', 'Customer Success Manager', 'Customer Success', 'Customer Success'),
    (r'customer success lead', 'Customer Success Lead', 'Customer Success', 'Customer Success'),
    (r'customer success', 'Customer Success Manager', 'Customer Success', 'Customer Success'),
    (r'client success manager', 'Client Success Manager', 'Customer Success', 'Customer Success'),
    (r'client success lead', 'Client Success Lead', 'Customer Success', 'Customer Success'),
    (r'client success', 'Client Success Manager', 'Customer Success', 'Customer Success'),
    (r'customer experience manager', 'Customer Experience Manager', 'Customer Success', 'Customer Experience'),
    (r'customer experience', 'Customer Experience Specialist', 'Customer Success', 'Customer Experience'),
    (r'cx manager', 'CX Manager', 'Customer Success', 'Customer Experience'),
    (r'cx operations', 'CX Operations Manager', 'Customer Success', 'CX Operations'),
    (r'cx analyst', 'CX Analyst', 'Customer Success', 'Customer Experience'),
    (r'cx\b', 'CX Specialist', 'Customer Success', 'Customer Experience'),
    (r'customer onboarding', 'Customer Onboarding Manager', 'Customer Success', 'Onboarding'),
    (r'customer activation', 'Customer Activation Manager', 'Customer Success', 'Activation'),
    (r'customer advocacy', 'Customer Advocacy Manager', 'Customer Success', 'Advocacy'),
    (r'customer education', 'Customer Education Manager', 'Customer Success', 'Education'),
    (r'customer learning', 'Customer Learning Consultant', 'Customer Success', 'Education'),
    
    # ========================================================================
    # CUSTOMER SUPPORT
    # ========================================================================
    (r'head of.*support', 'Head of Support', 'Customer Success', 'Support Leadership'),
    (r'director.*support', 'Director of Support', 'Customer Success', 'Support Leadership'),
    (r'customer support manager', 'Customer Support Manager', 'Customer Success', 'Support'),
    (r'customer support', 'Customer Support Specialist', 'Customer Success', 'Support'),
    (r'customer service manager', 'Customer Service Manager', 'Customer Success', 'Support'),
    (r'customer service', 'Customer Service Specialist', 'Customer Success', 'Support'),
    (r'customer care', 'Customer Care Specialist', 'Customer Success', 'Support'),
    (r'technical support manager', 'Technical Support Manager', 'Customer Success', 'Technical Support'),
    (r'technical support', 'Technical Support Specialist', 'Customer Success', 'Technical Support'),
    (r'support specialist', 'Support Specialist', 'Customer Success', 'Support'),
    (r'support manager', 'Support Manager', 'Customer Success', 'Support'),
    (r'support engineer', 'Support Engineer', 'Customer Success', 'Technical Support'),
    (r'support lead', 'Support Lead', 'Customer Success', 'Support'),
    (r'technical success manager', 'Technical Success Manager', 'Customer Success', 'Technical Success'),
    (r'technical account specialist', 'Technical Account Specialist', 'Customer Success', 'Technical Success'),
    (r'user escalations', 'User Escalations Specialist', 'Customer Success', 'Escalations'),
    (r'escalations', 'Escalations Specialist', 'Customer Success', 'Escalations'),
    (r'knowledge manager', 'Knowledge Manager', 'Customer Success', 'Knowledge'),
    (r'knowledge base', 'Knowledge Base Specialist', 'Customer Success', 'Knowledge'),
    
    # ========================================================================
    # PAYMENTS
    # ========================================================================
    (r'head of payments', 'Head of Payments', 'Payments', 'Payments Leadership'),
    (r'director.*payments', 'Director of Payments', 'Payments', 'Payments Leadership'),
    (r'payments.*manager', 'Payments Manager', 'Payments', 'Payments'),
    (r'payments.*lead', 'Payments Lead', 'Payments', 'Payments'),
    (r'payments.*analyst', 'Payments Analyst', 'Payments', 'Payments'),
    (r'payments.*specialist', 'Payments Specialist', 'Payments', 'Payments'),
    (r'payments.*strategist', 'Payments Strategist', 'Payments', 'Payments Strategy'),
    (r'payments.*engineer', 'Payments Engineer', 'Engineering', 'Payments'),
    (r'payments.*operations', 'Payments Operations Manager', 'Payments', 'Payments Operations'),
    (r'payments.*optimization', 'Payments Optimization Manager', 'Payments', 'Payments'),
    (r'payments.*partnership', 'Payments Partnerships Manager', 'Payments', 'Payments Partnerships'),
    (r'payments.*performance', 'Payments Performance Specialist', 'Payments', 'Payments'),
    (r'payments.*risk', 'Payments Risk Manager', 'Payments', 'Payments Risk'),
    (r'payment partner', 'Payment Partner Lead', 'Payments', 'Payments Partnerships'),
    (r'payment advisor', 'Payment Advisor', 'Payments', 'Payments'),
    
    # ========================================================================
    # STRATEGY
    # ========================================================================
    (r'chief strategy officer|cso\b', 'Chief Strategy Officer', 'Strategy', 'Executive'),
    (r'vp.*strategy', 'VP of Strategy', 'Strategy', 'Strategy Leadership'),
    (r'head of strategy', 'Head of Strategy', 'Strategy', 'Strategy Leadership'),
    (r'director.*strategy', 'Director of Strategy', 'Strategy', 'Strategy Leadership'),
    (r'strategy director', 'Strategy Director', 'Strategy', 'Strategy Leadership'),
    (r'strategy.*operations', 'Strategy & Operations', 'Strategy', 'Strategy & Ops'),
    (r'corporate strategy', 'Corporate Strategy', 'Strategy', 'Corporate Strategy'),
    (r'business strategy', 'Business Strategy Manager', 'Strategy', 'Business Strategy'),
    (r'commercial strategy', 'Commercial Strategy Manager', 'Strategy', 'Commercial Strategy'),
    (r'strategy manager', 'Strategy Manager', 'Strategy', 'Strategy'),
    (r'strategy lead', 'Strategy Lead', 'Strategy', 'Strategy'),
    (r'strategy analyst', 'Strategy Analyst', 'Strategy', 'Strategy'),
    (r'strategist', 'Strategist', 'Strategy', 'Strategy'),
    (r'strategic programs', 'Strategic Programs Lead', 'Strategy', 'Strategic Programs'),
    (r'strategic initiatives', 'Strategic Initiatives Lead', 'Strategy', 'Strategic Initiatives'),
    (r'strategic projects', 'Strategic Projects Lead', 'Strategy', 'Strategic Projects'),
    (r'strategic planning', 'Strategic Planning Manager', 'Strategy', 'Strategic Planning'),
    (r'strategic operations', 'Strategic Operations Lead', 'Strategy', 'Strategic Operations'),
    (r'core strategy', 'Core Strategy Lead', 'Strategy', 'Core Strategy'),
    (r'corporate development', 'Corporate Development Manager', 'Strategy', 'Corporate Development'),
    (r'm&a', 'M&A Manager', 'Strategy', 'M&A'),
    
    # ========================================================================
    # EXECUTIVE - C-Suite (catch remaining)
    # ========================================================================
    (r'\bceo\b|chief executive officer', 'CEO', 'Executive', 'Leadership'),
    (r'\bcto\b|chief technology officer', 'CTO', 'Executive', 'Leadership'),
    (r'\bcfo\b|chief financial officer', 'CFO', 'Executive', 'Leadership'),
    (r'\bcoo\b|chief operating officer', 'COO', 'Executive', 'Leadership'),
    (r'\bcmo\b|chief marketing officer', 'CMO', 'Executive', 'Leadership'),
    (r'\bcpo\b|chief product officer', 'CPO', 'Executive', 'Leadership'),
    (r'\bcro\b|chief revenue officer', 'CRO', 'Executive', 'Leadership'),
    (r'\bciso\b|chief information security', 'CISO', 'Executive', 'Leadership'),
    (r'\bcio\b|chief information officer', 'CIO', 'Executive', 'Leadership'),
    (r'chief.*officer', 'Chief Officer', 'Executive', 'Leadership'),
    
    # ========================================================================
    # EXECUTIVE - VP / SVP / EVP
    # ========================================================================
    (r'executive vice president|evp\b', 'Executive Vice President', 'Executive', 'Leadership'),
    (r'senior vice president|svp\b', 'Senior Vice President', 'Executive', 'Leadership'),
    (r'\bvp\b|vice president', 'Vice President', 'Executive', 'Leadership'),
    
    # ========================================================================
    # LEADERSHIP - Director (generic catch-all)
    # ========================================================================
    (r'director', 'Director', 'Leadership', 'Leadership'),
    
    # ========================================================================
    # LEADERSHIP - Head of (generic catch-all)
    # ========================================================================
    (r'head of', 'Head', 'Leadership', 'Leadership'),
    
    # ========================================================================
    # NICHE / INDUSTRY-SPECIFIC
    # ========================================================================
    # Crypto / Web3
    (r'trader|trading', 'Trader', 'Finance', 'Trading'),
    (r'custody.*operations', 'Custody Operations', 'Operations', 'Custody'),
    (r'staking', 'Staking Specialist', 'Operations', 'Crypto'),
    (r'protocol', 'Protocol Specialist', 'Engineering', 'Blockchain'),
    
    # Real Estate / Mortgage
    (r'mortgage.*originator', 'Mortgage Loan Originator', 'Finance', 'Mortgage'),
    (r'mortgage.*processor', 'Mortgage Processor', 'Finance', 'Mortgage'),
    (r'mortgage.*underwriter', 'Mortgage Underwriter', 'Finance', 'Mortgage'),
    (r'home.*loan', 'Home Loan Specialist', 'Finance', 'Mortgage'),
    (r'home.*equity', 'Home Equity Specialist', 'Finance', 'Mortgage'),
    (r'underwriter', 'Underwriter', 'Finance', 'Underwriting'),
    (r'underwriting', 'Underwriter', 'Finance', 'Underwriting'),
    (r'loan.*originator', 'Loan Originator', 'Finance', 'Lending'),
    (r'loan.*processor', 'Loan Processor', 'Finance', 'Lending'),
    (r'lending', 'Lending Specialist', 'Finance', 'Lending'),
    
    # Insurance
    (r'actuary', 'Actuary', 'Finance', 'Actuarial'),
    (r'claims', 'Claims Specialist', 'Operations', 'Claims'),
    (r'insurance.*agent', 'Insurance Agent', 'Sales', 'Insurance'),
    
    # Authentication / Security Products
    (r'authenticat.*specialist', 'Authentication Specialist', 'Operations', 'Authentication'),
    (r'authenticat.*admin', 'Authentication Admin', 'Operations', 'Authentication'),
    
    # Government Affairs
    (r'government affairs', 'Government Affairs Manager', 'Legal', 'Government Affairs'),
    (r'federal affairs', 'Federal Affairs Manager', 'Legal', 'Government Affairs'),
    (r'public policy', 'Public Policy Manager', 'Legal', 'Public Policy'),
    (r'policy manager', 'Policy Manager', 'Legal', 'Policy'),
    
    # Miscellaneous
    (r'collections', 'Collections Specialist', 'Finance', 'Collections'),
    (r'disputes', 'Disputes Specialist', 'Operations', 'Disputes'),
    (r'member service', 'Member Service Representative', 'Customer Success', 'Support'),
    (r'enrollment', 'Enrollment Representative', 'Operations', 'Enrollment'),
]


# ============================================================================
# SPECIAL PATTERN HANDLERS
# ============================================================================

# "Manager, X" pattern mappings
MANAGER_DOMAIN_PATTERNS = [
    # Compound terms FIRST (before their components)
    (r'mid-market sales', 'Mid-Market Sales Manager', 'Sales', 'Mid-Market Sales'),
    (r'mid market sales', 'Mid-Market Sales Manager', 'Sales', 'Mid-Market Sales'),
    (r'midmarket sales', 'Mid-Market Sales Manager', 'Sales', 'Mid-Market Sales'),
    (r'enterprise sales', 'Enterprise Sales Manager', 'Sales', 'Enterprise Sales'),
    (r'sales development', 'Sales Development Manager', 'Sales', 'Sales Development'),
    (r'billing sales', 'Billing Sales Manager', 'Sales', 'Sales'),
    (r'partner sales', 'Partner Sales Manager', 'Sales', 'Partner Sales'),
    (r'channel sales', 'Channel Sales Manager', 'Sales', 'Channel Sales'),
    (r'inside sales', 'Inside Sales Manager', 'Sales', 'Inside Sales'),
    (r'field sales', 'Field Sales Manager', 'Sales', 'Field Sales'),
    (r'enterprise.*new business', 'Enterprise New Business Manager', 'Sales', 'Enterprise Sales'),
    (r'enterprise.*existing business', 'Enterprise Account Manager', 'Sales', 'Enterprise Sales'),
    
    # Product compound terms
    (r'product design', 'Product Design Manager', 'Design', 'Design Management'),
    (r'product marketing', 'Product Marketing Manager', 'Marketing', 'Product Marketing'),
    (r'product management', 'Product Management Manager', 'Product', 'Product Management'),
    (r'product operations', 'Product Operations Manager', 'Product', 'Product Operations'),
    (r'product analytics', 'Product Analytics Manager', 'Product', 'Product Analytics'),
    
    # Engineering compound terms
    (r'software engineering', 'Engineering Manager', 'Engineering', 'Engineering Management'),
    (r'engineering', 'Engineering Manager', 'Engineering', 'Engineering Management'),
    (r'data science', 'Data Science Manager', 'Data', 'Data Science'),
    (r'data engineering', 'Data Engineering Manager', 'Engineering', 'Data Engineering'),
    (r'machine learning', 'ML Manager', 'Engineering', 'ML'),
    
    # Design compound terms
    (r'design systems', 'Design Systems Manager', 'Design', 'Design Systems'),
    (r'ux design', 'UX Design Manager', 'Design', 'UX Design'),
    (r'design', 'Design Manager', 'Design', 'Design Management'),
    
    # Solutions
    (r'solutions consulting', 'Solutions Consulting Manager', 'Solutions', 'Consulting'),
    (r'solutions engineering', 'Solutions Engineering Manager', 'Solutions', 'Solutions Engineering'),
    (r'solutions', 'Solutions Manager', 'Solutions', 'Solutions'),
    
    # Operations compound terms
    (r'risk operations', 'Risk Operations Manager', 'Risk', 'Risk Operations'),
    (r'credit operations', 'Credit Operations Manager', 'Risk', 'Credit Operations'),
    (r'sales operations', 'Sales Operations Manager', 'Sales', 'Sales Operations'),
    (r'marketing operations', 'Marketing Operations Manager', 'Marketing', 'Marketing Operations'),
    (r'revenue operations', 'Revenue Operations Manager', 'Sales', 'Revenue Operations'),
    (r'business operations', 'Business Operations Manager', 'Operations', 'Business Ops'),
    (r'partner support', 'Partner Support Manager', 'Operations', 'Partner Support'),
    (r'customer operations', 'Customer Operations Manager', 'Operations', 'Customer Operations'),
    (r'technical operations', 'Technical Operations Manager', 'Operations', 'Technical Ops'),
    
    # Finance compound terms
    (r'financial planning', 'Financial Planning Manager', 'Finance', 'FP&A'),
    (r'gtm finance', 'GTM Finance Manager', 'GTM', 'GTM Finance'),
    (r'finance', 'Finance Manager', 'Finance', 'Finance'),
    
    # People compound terms
    (r'talent acquisition', 'Talent Acquisition Manager', 'People', 'Recruiting'),
    (r'recruiting', 'Recruiting Manager', 'People', 'Recruiting'),
    (r'people operations', 'People Operations Manager', 'People', 'People Ops'),
    (r'people', 'People Manager', 'People', 'People'),
    (r'hr', 'HR Manager', 'People', 'HR'),
    
    # Marketing compound terms
    (r'field marketing', 'Field Marketing Manager', 'Marketing', 'Field Marketing'),
    (r'content marketing', 'Content Marketing Manager', 'Marketing', 'Content Marketing'),
    (r'growth marketing', 'Growth Marketing Manager', 'Marketing', 'Growth'),
    (r'demand gen', 'Demand Generation Manager', 'Marketing', 'Demand Gen'),
    (r'marketing', 'Marketing Manager', 'Marketing', 'Marketing'),
    
    # Account patterns
    (r'account executives?', 'Account Executives Manager', 'Sales', 'Sales Management'),
    (r'account management', 'Account Management Manager', 'Sales', 'Account Management'),
    (r'relationship managers?', 'Relationship Managers Manager', 'Sales', 'Relationship Management'),
    
    # Customer Success
    (r'customer success', 'Customer Success Manager', 'Customer Success', 'Customer Success'),
    (r'customer experience', 'Customer Experience Manager', 'Customer Success', 'Customer Experience'),
    (r'technical success', 'Technical Success Manager', 'Customer Success', 'Technical Success'),
    
    # Strategy
    (r'strategic sales', 'Strategic Sales Manager', 'Sales', 'Strategic Sales'),
    (r'strategy', 'Strategy Manager', 'Strategy', 'Strategy'),
    
    # Analytics
    (r'analytics', 'Analytics Manager', 'Data', 'Analytics'),
    
    # Legal
    (r'legal', 'Legal Manager', 'Legal', 'Legal'),
    (r'compliance', 'Compliance Manager', 'Legal', 'Compliance'),
    
    # Generic (LAST)
    (r'operations', 'Operations Manager', 'Operations', 'Operations'),
    (r'administrative', 'Administrative Manager', 'Operations', 'Administration'),
    (r'product', 'Product Manager', 'Product', 'Product Management'),
    (r'sales', 'Sales Manager', 'Sales', 'Sales Management'),
]

# "Head of X" pattern mappings
HEAD_OF_PATTERNS = [
    (r'sales', 'Head of Sales', 'Sales', 'Sales Leadership'),
    (r'marketing', 'Head of Marketing', 'Marketing', 'Marketing Leadership'),
    (r'engineering', 'Head of Engineering', 'Engineering', 'Engineering Leadership'),
    (r'product', 'Head of Product', 'Product', 'Product Leadership'),
    (r'design', 'Head of Design', 'Design', 'Design Leadership'),
    (r'content', 'Head of Content', 'Marketing', 'Content Leadership'),
    (r'gtm', 'Head of GTM', 'GTM', 'GTM Leadership'),
    (r'payments', 'Head of Payments', 'Payments', 'Payments Leadership'),
    (r'solutions', 'Head of Solutions', 'Solutions', 'Solutions Leadership'),
    (r'finance', 'Head of Finance', 'Finance', 'Finance Leadership'),
    (r'people|hr', 'Head of People', 'People', 'People Leadership'),
    (r'risk', 'Head of Risk', 'Risk', 'Risk Leadership'),
    (r'operations', 'Head of Operations', 'Operations', 'Operations Leadership'),
    (r'legal', 'Head of Legal', 'Legal', 'Legal Leadership'),
    (r'data', 'Head of Data', 'Data', 'Data Leadership'),
    (r'security', 'Head of Security', 'Engineering', 'Security Leadership'),
    (r'growth', 'Head of Growth', 'Marketing', 'Growth Leadership'),
    (r'partnerships', 'Head of Partnerships', 'Partnerships', 'Partnerships Leadership'),
    (r'customer success', 'Head of Customer Success', 'Customer Success', 'CS Leadership'),
    (r'support', 'Head of Support', 'Customer Success', 'Support Leadership'),
    (r'compliance', 'Head of Compliance', 'Legal', 'Compliance Leadership'),
    (r'talent', 'Head of Talent', 'People', 'Talent Leadership'),
    (r'recruiting', 'Head of Recruiting', 'People', 'Recruiting Leadership'),
    (r'brand', 'Head of Brand', 'Marketing', 'Brand Leadership'),
    (r'communications', 'Head of Communications', 'Marketing', 'Communications Leadership'),
    (r'strategy', 'Head of Strategy', 'Strategy', 'Strategy Leadership'),
    (r'revenue', 'Head of Revenue', 'Sales', 'Revenue Leadership'),
    (r'business development', 'Head of Business Development', 'Sales', 'BD Leadership'),
    (r'enablement', 'Head of Enablement', 'Sales', 'Enablement Leadership'),
    (r'professional services', 'Head of Professional Services', 'Operations', 'PS Leadership'),
    (r'ai', 'Head of AI', 'Engineering', 'AI Leadership'),
    (r'applied ai', 'Head of Applied AI', 'Engineering', 'AI Leadership'),
    (r'infrastructure', 'Head of Infrastructure', 'Engineering', 'Infrastructure Leadership'),
    (r'platform', 'Head of Platform', 'Engineering', 'Platform Leadership'),
]

# "Director of X" / "Director, X" pattern mappings
DIRECTOR_DOMAIN_PATTERNS = [
    # Legal/Counsel patterns - VERY SPECIFIC FIRST
    (r'product counsel', 'Director of Product Counsel', 'Legal', 'Product Legal'),
    (r'commercial counsel', 'Director of Commercial Counsel', 'Legal', 'Commercial Legal'),
    (r'employment counsel', 'Director of Employment Counsel', 'Legal', 'Employment Law'),
    (r'privacy counsel', 'Director of Privacy Counsel', 'Legal', 'Privacy'),
    (r'counsel', 'Director of Legal', 'Legal', 'Legal'),
    
    # Operations with prefix
    (r'payroll operations', 'Director of Payroll Operations', 'Finance', 'Payroll'),
    (r'sales operations', 'Director of Sales Operations', 'Sales', 'Sales Operations'),
    (r'revenue operations', 'Director of Revenue Operations', 'Sales', 'Revenue Operations'),
    (r'marketing operations', 'Director of Marketing Operations', 'Marketing', 'Marketing Operations'),
    (r'billing operations', 'Director of Billing Operations', 'Finance', 'Billing'),
    (r'credit operations', 'Director of Credit Operations', 'Risk', 'Credit Operations'),
    (r'risk operations', 'Director of Risk Operations', 'Risk', 'Risk Operations'),
    (r'business operations', 'Director of Business Operations', 'Operations', 'Business Ops'),
    
    # Engineering specifics
    (r'software engineering', 'Director of Engineering', 'Engineering', 'Engineering Leadership'),
    (r'engineering', 'Director of Engineering', 'Engineering', 'Engineering Leadership'),
    (r'data science', 'Director of Data Science', 'Data', 'Data Leadership'),
    (r'data engineering', 'Director of Data Engineering', 'Engineering', 'Data Engineering'),
    (r'machine learning|ml\b', 'Director of Machine Learning', 'Engineering', 'ML Leadership'),
    (r'platform', 'Director of Platform', 'Engineering', 'Platform'),
    (r'infrastructure', 'Director of Infrastructure', 'Engineering', 'Infrastructure'),
    (r'security', 'Director of Security', 'Engineering', 'Security'),
    (r'mobile', 'Director of Mobile', 'Engineering', 'Mobile'),
    (r'web', 'Director of Web', 'Engineering', 'Web'),
    (r'ai\b', 'Director of AI', 'Engineering', 'AI'),
    
    # Design specifics
    (r'learning design', 'Director of Learning Design', 'Design', 'Learning Design'),
    (r'product design', 'Director of Product Design', 'Design', 'Product Design'),
    (r'ux design', 'Director of UX Design', 'Design', 'UX Design'),
    (r'design', 'Director of Design', 'Design', 'Design Leadership'),
    
    # Product
    (r'product management', 'Director of Product Management', 'Product', 'Product Leadership'),
    (r'product', 'Director of Product', 'Product', 'Product Leadership'),
    
    # Sales specifics
    (r'enterprise sales', 'Director of Enterprise Sales', 'Sales', 'Enterprise Sales'),
    (r'commercial sales', 'Director of Commercial Sales', 'Sales', 'Commercial Sales'),
    (r'account management', 'Director of Account Management', 'Sales', 'Account Management'),
    (r'sales', 'Director of Sales', 'Sales', 'Sales Leadership'),
    
    # Marketing specifics
    (r'content', 'Director of Content', 'Marketing', 'Content'),
    (r'communications', 'Director of Communications', 'Marketing', 'Communications'),
    (r'demand gen', 'Director of Demand Generation', 'Marketing', 'Demand Gen'),
    (r'growth', 'Director of Growth', 'Marketing', 'Growth'),
    (r'brand', 'Director of Brand', 'Marketing', 'Brand'),
    (r'marketing', 'Director of Marketing', 'Marketing', 'Marketing Leadership'),
    
    # People/HR
    (r'talent acquisition', 'Director of Talent Acquisition', 'People', 'Recruiting Leadership'),
    (r'recruiting', 'Director of Recruiting', 'People', 'Recruiting Leadership'),
    (r'compensation', 'Director of Compensation', 'People', 'Compensation'),
    (r'talent', 'Director of Talent', 'People', 'Talent Leadership'),
    (r'people|hr|human resources', 'Director of People', 'People', 'People Leadership'),
    
    # Finance
    (r'finance', 'Director of Finance', 'Finance', 'Finance Leadership'),
    (r'tax', 'Director of Tax', 'Finance', 'Tax'),
    (r'accounting', 'Director of Accounting', 'Finance', 'Accounting'),
    
    # Other
    (r'professional services', 'Director of Professional Services', 'Operations', 'Professional Services'),
    (r'customer success', 'Director of Customer Success', 'Customer Success', 'CS Leadership'),
    (r'customer experience', 'Director of Customer Experience', 'Customer Success', 'CX Leadership'),
    (r'support', 'Director of Support', 'Customer Success', 'Support Leadership'),
    (r'trust.*safety', 'Director of Trust & Safety', 'Operations', 'Trust & Safety'),
    (r'partnerships', 'Director of Partnerships', 'Partnerships', 'Partnerships'),
    (r'strategy', 'Director of Strategy', 'Strategy', 'Strategy'),
    (r'operations', 'Director of Operations', 'Operations', 'Operations Leadership'),
    (r'legal', 'Director of Legal', 'Legal', 'Legal Leadership'),
    (r'risk', 'Director of Risk', 'Risk', 'Risk Leadership'),
    (r'compliance', 'Director of Compliance', 'Legal', 'Compliance'),
]


def handle_manager_comma_pattern(title: str) -> Optional[dict]:
    """Handle titles like 'Manager, Sales Development' -> 'Sales Development Manager'"""
    match = re.match(r'^manager\s*,\s*(.+)$', title, re.IGNORECASE)
    if not match:
        return None
    
    domain = match.group(1).strip()
    
    for pattern, normalized, category, job_family in MANAGER_DOMAIN_PATTERNS:
        if re.search(pattern, domain, re.IGNORECASE):
            return {
                'normalized_title': normalized,
                'category': category,
                'seniority_level': None,
                'job_family': job_family
            }
    
    # If no specific match, create "X Manager"
    domain_clean = re.sub(r'\s*$[^)]*$', '', domain)
    domain_clean = re.sub(r'\s+', ' ', domain_clean).strip()
    domain_clean = domain_clean.title()
    
    return {
        'normalized_title': f"{domain_clean} Manager",
        'category': 'Management',
        'seniority_level': None,
        'job_family': 'Management'
    }


def handle_head_of_pattern(title: str) -> Optional[dict]:
    """Handle titles like 'Head of Sales, AMER' -> 'Head of Sales'"""
    match = re.search(r'(?:global\s+)?head of\s+(.+)', title, re.IGNORECASE)
    if not match:
        return None
    
    domain = match.group(1).strip()
    # Remove suffixes after comma
    domain = re.split(r',\s*', domain)[0].strip()
    
    for pattern, normalized, category, job_family in HEAD_OF_PATTERNS:
        if re.search(pattern, domain, re.IGNORECASE):
            return {
                'normalized_title': normalized,
                'category': category,
                'seniority_level': 'lead',
                'job_family': job_family
            }
    
    # Generic "Head of X"
    domain_clean = domain.title()
    return {
        'normalized_title': f"Head of {domain_clean}",
        'category': 'Executive',
        'seniority_level': 'lead',
        'job_family': 'Leadership'
    }


def handle_director_pattern(title: str, seniority: str = None) -> Optional[dict]:
    """Handle titles like 'Director, Engineering' or 'Director of Engineering'"""
    # Match "Director, X" or "Director of X"
    match = re.match(r'^(?:senior\s+)?director\s*[,of]+\s*(.+)$', title, re.IGNORECASE)
    if not match:
        return None
    
    domain = match.group(1).strip()
    
    # Clean domain - remove location/team suffixes
    domain = re.sub(r'\s*[-–].*$', '', domain)
    domain = re.sub(r'\s*$.*$$', '', domain)
    
    for pattern, normalized, category, job_family in DIRECTOR_DOMAIN_PATTERNS:
        if re.search(pattern, domain, re.IGNORECASE):
            return {
                'normalized_title': normalized,
                'category': category,
                'seniority_level': seniority or 'lead',
                'job_family': job_family
            }
    
    # Generic fallback - keep the domain
    domain_clean = domain.strip().title()
    
    return {
        'normalized_title': f"Director of {domain_clean}",
        'category': 'Leadership',
        'seniority_level': seniority or 'lead',
        'job_family': 'Leadership'
    }


def handle_associate_pattern(title: str) -> Optional[dict]:
    """Handle titles like 'Associate, Services Consulting' -> 'Services Consultant'"""
    match = re.match(r'^associate\s*,\s*(.+)$', title, re.IGNORECASE)
    if not match:
        return None
    
    domain = match.group(1).strip()
    
    if re.search(r'consult', domain, re.IGNORECASE):
        return {
            'normalized_title': 'Services Consultant',
            'category': 'Operations',
            'seniority_level': 'junior',
            'job_family': 'Consulting'
        }
    
    if re.search(r'product analytics', domain, re.IGNORECASE):
        return {
            'normalized_title': 'Product Analytics Associate',
            'category': 'Product',
            'seniority_level': 'junior',
            'job_family': 'Product Analytics'
        }
    
    if re.search(r'strateg', domain, re.IGNORECASE):
        return {
            'normalized_title': 'Strategy Associate',
            'category': 'Strategy',
            'seniority_level': 'junior',
            'job_family': 'Strategy'
        }
    
    if re.search(r'operations', domain, re.IGNORECASE):
        return {
            'normalized_title': 'Operations Associate',
            'category': 'Operations',
            'seniority_level': 'junior',
            'job_family': 'Operations'
        }
    
    domain_clean = domain.title()
    return {
        'normalized_title': f"{domain_clean} Associate",
        'category': 'Operations',
        'seniority_level': 'junior',
        'job_family': 'Operations'
    }


# ============================================================================
# MAIN NORMALIZE FUNCTION
# ============================================================================

def normalize_title(raw_title: str) -> dict:
    """
    Normalize a job title into structured components.
    
    Returns:
        dict with keys:
            - normalized_title: str
            - category: str
            - seniority_level: str or None
            - job_family: str
    """
    if not raw_title:
        return {
            'normalized_title': 'Unknown',
            'category': 'Skip',
            'seniority_level': None,
            'job_family': 'Skip'
        }
    
    # Clean the title first
    title = clean_title(raw_title)
    
    # Check if should skip
    if should_skip(title):
        return {
            'normalized_title': 'Unknown',
            'category': 'Skip',
            'seniority_level': None,
            'job_family': 'Skip'
        }
    
    # Extract seniority
    seniority, title_without_seniority = extract_seniority(title)
    
    # ================================================================
    # Check special patterns first
    # ================================================================
    
    # "Manager, X" pattern
    manager_result = handle_manager_comma_pattern(title_without_seniority)
    if manager_result:
        manager_result['seniority_level'] = seniority
        manager_result['normalized_title'] = fix_acronyms(manager_result['normalized_title'])
        return manager_result
    
    # "Head of X" pattern
    head_result = handle_head_of_pattern(title_without_seniority)
    if head_result:
        if seniority:
            head_result['seniority_level'] = seniority
        head_result['normalized_title'] = fix_acronyms(head_result['normalized_title'])
        return head_result
    
    # "Director, X" or "Director of X" pattern
    director_result = handle_director_pattern(title_without_seniority, seniority)
    if director_result:
        director_result['normalized_title'] = fix_acronyms(director_result['normalized_title'])
        return director_result
    
    # "Associate, X" pattern
    associate_result = handle_associate_pattern(title_without_seniority)
    if associate_result:
        associate_result['normalized_title'] = fix_acronyms(associate_result['normalized_title'])
        return associate_result
    
    # ================================================================
    # Match against main job family patterns
    # ================================================================
    
    # Remove team/product suffixes for matching (but keep for context)
    title_for_matching = re.split(r',\s*(?![^()]*\))', title_without_seniority)[0].strip()
    
    # Try matching against patterns
    for pattern, normalized, category, job_family in JOB_FAMILY_PATTERNS:
        if re.search(pattern, title_for_matching, re.IGNORECASE):
            return {
                'normalized_title': fix_acronyms(normalized),
                'category': category,
                'seniority_level': seniority,
                'job_family': job_family
            }
    
    # Try again with full title
    for pattern, normalized, category, job_family in JOB_FAMILY_PATTERNS:
        if re.search(pattern, title_without_seniority, re.IGNORECASE):
            return {
                'normalized_title': fix_acronyms(normalized),
                'category': category,
                'seniority_level': seniority,
                'job_family': job_family
            }
    
    # ================================================================
    # FALLBACK LOGIC
    # ================================================================
    
    fallback_title = title_for_matching.strip()
    
    # If too generic, use more context
    GENERIC_TERMS = {
        'engineer', 'designer', 'director', 'manager', 'lead', 'analyst',
        'associate', 'specialist', 'coordinator', 'consultant', 'architect',
        'strategist', 'partner', 'executive', 'representative', 'agent'
    }
    
    if fallback_title.lower() in GENERIC_TERMS:
        fallback_title = title_without_seniority.strip()
    
    # Title case and clean up
    fallback_title = fallback_title.title()
    fallback_title = re.sub(r'\s+', ' ', fallback_title).strip()
    fallback_title = fix_acronyms(fallback_title)
    
    # Determine category from keywords - ORDER MATTERS!
    category = 'Other'
    job_family = 'Other'
    
    fl = fallback_title.lower()
    
    # Check most specific patterns first
    
    # People/HR - check BEFORE "partner" catches it
    if any(w in fl for w in ['recruit', 'people', 'hr ', 'human resources', 'talent acquisition', 
                              'compensation', 'benefits', 'payroll', 'hris', 'hrbp']):
        category = 'People'
        job_family = 'People'
    # Risk - check BEFORE "analyst" catches it  
    elif any(w in fl for w in ['risk', 'fraud', 'aml', 'kyc', 'credit risk', 'financial crime']):
        category = 'Risk'
        job_family = 'Risk'
    # Engineering - specific terms
    elif any(w in fl for w in ['engineer', 'developer', 'swe', 'sre', 'devops', 'software', 
                                'backend', 'frontend', 'fullstack', 'infrastructure', 'platform']):
        category = 'Engineering'
        job_family = 'Engineering'
    # Sales - check before generic "partner"
    elif any(w in fl for w in ['sales', 'account executive', 'account manager', ' ae ', 'sdr', 'bdr', 
                                'business development', 'quota', 'revenue']):
        category = 'Sales'
        job_family = 'Sales'
    # Customer Success
    elif any(w in fl for w in ['customer success', 'customer experience', 'csm', 'client success']):
        category = 'Customer Success'
        job_family = 'Customer Success'
    # Design
    elif any(w in fl for w in ['designer', 'design', 'ux', 'ui', 'creative', 'illustrat', 'visual']):
        category = 'Design'
        job_family = 'Design'
    # Product
    elif any(w in fl for w in ['product manager', 'product lead', 'program manager', 'project manager', 
                                'product owner', 'tpm', 'technical program']):
        category = 'Product'
        job_family = 'Product Management'
    # Marketing
    elif any(w in fl for w in ['marketing', 'growth', 'content', 'brand', 'communications', 'pr ', 
                                'public relations', 'social media', 'seo', 'demand gen']):
        category = 'Marketing'
        job_family = 'Marketing'
    # Data
    elif any(w in fl for w in ['data scientist', 'data analyst', 'analytics', 'bi ', 'business intelligence']):
        category = 'Data'
        job_family = 'Data & Analytics'
    # Finance
    elif any(w in fl for w in ['finance', 'accounting', 'controller', 'accountant', 'tax', 'treasury', 
                                'fp&a', 'financial', 'billing', 'revenue accounting']):
        category = 'Finance'
        job_family = 'Finance'
    # Legal
    elif any(w in fl for w in ['legal', 'counsel', 'attorney', 'lawyer', 'compliance', 'paralegal', 
                                'regulatory', 'contract']):
        category = 'Legal'
        job_family = 'Legal'
    # Operations
    elif any(w in fl for w in ['operations', 'ops', 'support', 'implementation', 'admin', 'facilities',
                                'workplace', 'logistics', 'supply chain']):
        category = 'Operations'
        job_family = 'Operations'
    # Partnerships - check AFTER People (to not catch "People Partner")
    elif any(w in fl for w in ['partnership', 'alliance', 'channel manager', 'partner manager']):
        category = 'Partnerships'
        job_family = 'Partnerships'
    # Leadership/Executive - generic catch
    elif any(w in fl for w in ['director', 'head of', 'vp ', 'chief', 'president']):
        category = 'Leadership'
        job_family = 'Leadership'
    
    return {
        'normalized_title': fallback_title,
        'category': category,
        'seniority_level': seniority,
        'job_family': job_family
    }


# ============================================================================
# TEST
# ============================================================================

if __name__ == '__main__':
    test_titles = [
        # From the report - should NOT be "Other"
        'AI Architect',
        'AI Automation Lead I',
        'AI Deployment Specialist',
        'Golang Developer',
        'Rust Developer',
        'Web Developer',
        'Account Development Representative (Danish Speaking)',
        'Account Director Enterprise Sales - Bay Area',
        'Database Administrator',
        'Salesforce Developer',
        
        # Weird categorizations to fix
        'Mortgage Loan Originator, Home Equity',
        'Regional Sales Director, Acquisition | Boston | Remote',
        'Threat Detection Researcher (Windows/Linux)',
        
        # Location stripping
        '(Talent Community) Peloton Expert - Nashville, Tn',
        'Observability Architect | Germany | Remote',
        'Enterprise Sales, Latam (Spanish-Speaking)',
        
        # Temporal stripping
        'Data Science (Summer 2026)',
        'Product Management (2026) - Amsterdam',
        'Market Associate (12 Month Fixed-Term Contract)',
        
        # Skip patterns
        "Can't Find A Role For You? Submit A General Application.",
        "Don't See The Perfect Fit?",
        'Your Chance To Join Our Talent Community!',
        
        # Manager patterns
        'Manager, Sales Development',
        'Account Executives (Commercial) Manager',
        
        # Head of patterns
        'Head of Applied AI',
        'Head of Content',
        'Head of Sec Reporting',
        
        # Director patterns
        'Director of Engineering',
        'Director of Learning Design, Immersive Language Learning',
        'Director, Trust & Safety',
        
        # Normal ones that should work
        'Senior Software Engineer',
        'Staff Product Designer',
        'Principal Data Scientist',
        'Solutions Architect',
        'Customer Success Manager',
    ]
    
    print("=" * 120)
    print("ROLE NORMALIZER TEST")
    print("=" * 120)
    print(f"{'Original':<55} {'Normalized':<35} {'Category':<15} {'Seniority'}")
    print("-" * 120)
    
    for title in test_titles:
        result = normalize_title(title)
        seniority = result['seniority_level'] or '-'
        orig = title[:53] + '..' if len(title) > 55 else title
        norm = result['normalized_title'][:33] + '..' if len(result['normalized_title']) > 35 else result['normalized_title']
        print(f"{orig:<55} {norm:<35} {result['category']:<15} {seniority}")