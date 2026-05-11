"""
Import curated skill candidates from data/skill_candidates_curated.csv into the skills table.
Assigns a category (technical / soft / domain) and populates aliases for common variations.

Usage:
    PYTHONPATH=. venv/bin/python scripts/import_skill_candidates.py [--dry-run] [--csv PATH]

Options:
    --dry-run    Print what would be inserted without touching the DB
    --csv PATH   Path to curated CSV (default: data/skill_candidates_curated.csv)
"""
import argparse
import csv
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Aliases  (canonical skill name → list of alternate names / abbreviations)
# Checked case-insensitively on import; also used when updating existing skills.
# ---------------------------------------------------------------------------
ALIASES: dict[str, list[str]] = {
    # ── Cloud platforms ───────────────────────────────────────────────────
    "AWS":                       ["Amazon Web Services", "Amazon AWS"],
    "Azure":                     ["Microsoft Azure", "MS Azure"],
    "GCP":                       ["Google Cloud Platform", "Google Cloud", "Google Cloud Services"],
    "Google Workspace":          ["G Suite", "GSuite", "Google Suite", "Google Apps"],
    "Kubernetes":                ["K8s", "k8s"],
    "Terraform":                 ["TF", "terraform IaC"],
    "Ansible":                   ["Ansible automation"],
    "OpenShift":                 ["Red Hat OpenShift"],

    # ── Languages / runtimes ─────────────────────────────────────────────
    "JavaScript":                ["JS", "ECMAScript", "ES6", "ES2015"],
    "TypeScript":                ["TS"],
    "Python":                    ["Python 3", "Python programming"],
    "Golang":                    ["Go", "Go programming", "Go lang"],
    "Rust":                      ["Rust lang", "Rust programming"],
    "Kotlin":                    ["Kotlin programming"],
    "Swift":                     ["Swift programming", "SwiftUI"],
    "C#":                        ["CSharp", "C Sharp", ".NET C#"],
    "C++":                       ["CPP", "C plus plus"],
    "Scala":                     ["Scala programming"],
    "Ruby":                      ["Ruby programming"],
    "PHP":                       ["PHP programming"],

    # ── Web / mobile frameworks ──────────────────────────────────────────
    "React":                     ["ReactJS", "React.js", "React Native"],
    "Angular":                   ["AngularJS", "Angular.js"],
    "Vue.js":                    ["Vue", "VueJS", "Vue.JS"],
    "Node.js":                   ["NodeJS", "Node", "Node JS"],
    "Next.js":                   ["NextJS", "Next"],
    "FastAPI":                   ["Fast API"],
    "Spring Boot":               ["Spring", "Spring Framework", "Spring MVC"],
    "Django":                    ["Django REST framework", "Django framework"],
    "Flask":                     ["Flask Python"],
    ".NET":                      ["dotnet", "dot net", "Microsoft .NET"],
    "SwiftUI":                   ["Swift UI"],
    "Jetpack Compose":           ["Compose", "Android Compose"],

    # ── Data & ML ────────────────────────────────────────────────────────
    "PostgreSQL":                ["Postgres", "PostgresDB"],
    "MongoDB":                   ["Mongo", "MongoDB Atlas"],
    "Elasticsearch":             ["Elastic", "OpenSearch"],
    "Apache Spark":              ["Spark", "PySpark"],
    "Apache Kafka":              ["Kafka"],
    "Apache Airflow":            ["Airflow"],
    "dbt":                       ["data build tool", "DBT"],
    "Snowflake":                 ["Snowflake Data Cloud"],
    "Databricks":                ["Databricks platform"],
    "BigQuery":                  ["Google BigQuery"],
    "Redshift":                  ["Amazon Redshift", "AWS Redshift"],
    "Power BI":                  ["PowerBI", "Microsoft Power BI"],
    "Tableau":                   ["Tableau Desktop", "Tableau Server"],
    "Looker":                    ["Looker Studio", "Google Looker"],
    "PyTorch":                   ["Pytorch", "torch"],
    "TensorFlow":                ["Tensorflow", "TF"],
    "scikit-learn":              ["sklearn", "scikit learn"],
    "LLM orchestration":         ["LLM systems", "LLM integration", "LLM-based systems",
                                  "large language model orchestration", "LLM architectures"],
    "agentic AI":                ["AI agent", "AI agents", "AI agent development",
                                  "autonomous AI agents", "LLM agents"],
    "model serving":             ["model deployment", "model inference",
                                  "ML serving", "model hosting"],
    "AI-assisted development":   ["AI coding assistants", "GitHub Copilot", "Copilot",
                                  "AI code generation", "AI-assisted coding"],
    "RLHF":                      ["reinforcement learning from human feedback",
                                  "RLAIF", "human feedback fine-tuning"],
    "CUDA":                      ["GPU programming", "GPU computing", "CUDA programming"],
    "RAG":                       ["retrieval-augmented generation", "retrieval augmented generation"],
    "vector databases":          ["vector DB", "vector store", "vector search"],
    "feature engineering":       ["feature extraction", "feature selection"],

    # ── DevOps / platform ────────────────────────────────────────────────
    "CI/CD":                     ["continuous integration", "continuous deployment",
                                  "continuous delivery", "CI CD", "CICD"],
    "DevOps":                    ["dev ops"],
    "GitOps":                    ["git ops"],
    "Docker":                    ["Docker containers", "Docker Hub"],
    "Helm":                      ["Helm charts"],
    "ArgoCD":                    ["Argo CD"],
    "Datadog":                   ["DD", "Datadog monitoring"],
    "Prometheus":                ["Prometheus monitoring"],
    "Grafana":                   ["Grafana dashboards"],
    "Splunk":                    ["Splunk SIEM"],
    "New Relic":                 ["NewRelic"],
    "OpenTelemetry":             ["OTel", "open telemetry"],

    # ── APIs / integration ───────────────────────────────────────────────
    "REST APIs":                 ["RESTful APIs", "REST API", "RESTful API",
                                  "REST", "RESTful services"],
    "GraphQL":                   ["Graph QL"],
    "gRPC":                      ["GRPC", "g RPC"],
    "API development":           ["API design", "API engineering", "REST API development"],
    "enterprise integration":    ["EAI", "enterprise application integration",
                                  "system integration", "enterprise integration patterns"],
    "microservices":             ["micro services", "microservice architecture"],
    "event-driven architecture": ["EDA", "event driven architecture", "event-driven"],
    "message queues":            ["message queue", "message broker", "MQ"],
    "webhooks":                  ["web hooks", "webhook integrations"],

    # ── Security ─────────────────────────────────────────────────────────
    "OAuth":                     ["OAuth 2.0", "OAuth2"],
    "SAML":                      ["SAML 2.0"],
    "SSO":                       ["single sign-on", "single sign on"],
    "zero trust":                ["zero-trust", "zero trust security", "Zero Trust Architecture"],
    "SIEM":                      ["Security Information and Event Management"],
    "IAM":                       ["Identity and Access Management", "access management"],
    "CSPM":                      ["cloud security posture management"],
    "DAST":                      ["dynamic application security testing"],
    "SAST":                      ["static application security testing", "static analysis"],
    "security scanning":         ["vulnerability scanning", "code scanning",
                                  "SCA", "security scan"],
    "penetration testing":       ["pen testing", "pentest", "ethical hacking"],
    "SOC 2":                     ["SOC2", "SOC II", "SOC 2 compliance"],
    "PCI-DSS":                   ["PCI DSS", "PCI", "Payment Card Industry"],
    "HIPAA":                     ["HIPAA compliance"],
    "SOX":                       ["Sarbanes-Oxley", "Sarbanes Oxley", "SOX controls",
                                  "SOX 404", "SOX compliance"],

    # ── Networking / infra ───────────────────────────────────────────────
    "network engineering":       ["networking", "network design", "network architecture",
                                  "network infrastructure"],
    "TCP/IP":                    ["TCP IP", "TCP/IP networking"],
    "DNS":                       ["Domain Name System"],
    "VPN":                       ["virtual private network"],
    "SD-WAN":                    ["software-defined WAN", "SD WAN"],

    # ── Hardware / embedded ──────────────────────────────────────────────
    "hardware design":           ["HW design", "hardware engineering design",
                                  "circuit design", "electronic design"],
    "hardware testing":          ["HW testing", "hardware validation",
                                  "hardware verification", "hardware QA"],
    "embedded systems":          ["embedded software", "embedded development",
                                  "embedded programming"],
    "FPGA development":          ["FPGAs", "FPGA", "field programmable gate array",
                                  "FPGA programming", "FPGA design"],
    "PCB design":                ["printed circuit board design", "PCB layout", "PCB"],
    "Schematic Capture":         ["ECAD", "electronic CAD", "schematic design"],
    "fraud prevention":          ["fraud detection", "anti-fraud", "fraud management"],
    "Jamf Pro":                  ["Jamf", "Jamf MDM"],
    "IT General Controls":       ["ITGCs", "IT general controls", "ITGC"],
    "CAD":                       ["CAD software", "3D CAD", "computer-aided design"],

    # ── Methodologies ────────────────────────────────────────────────────
    "Agile":                     ["agile methodology", "agile development", "agile software"],
    "Scrum":                     ["scrum methodology", "scrum framework"],
    "Kanban":                    ["kanban board", "kanban methodology"],
    "Six Sigma":                 ["6 Sigma", "Six-Sigma", "6-Sigma"],
    "Lean":                      ["lean methodology", "lean manufacturing", "lean principles"],
    "TDD":                       ["test-driven development", "test driven development"],
    "BDD":                       ["behavior-driven development", "behaviour-driven development"],
    "SAFe":                      ["scaled agile framework", "scaled agile"],

    # ── Cloud-native ─────────────────────────────────────────────────────
    "cloud-native development":  ["cloud native development", "cloud native",
                                  "cloud-native", "cloud native apps",
                                  "cloud native architecture"],
    "serverless":                ["serverless computing", "serverless architecture",
                                  "FaaS", "function as a service"],
    "infrastructure as code":    ["IaC", "Infrastructure as Code"],
    "container orchestration":   ["container management", "containers orchestration"],

    # ── Data engineering / querying ──────────────────────────────────────
    "data querying":             ["data query", "database querying", "querying databases"],
    "ETL":                       ["extract transform load", "extract, transform, load",
                                  "data pipelines", "data pipeline"],
    "data warehousing":          ["data warehouse", "DWH"],
    "data modeling":             ["data modelling", "dimensional modeling"],

    # ── Business / CRM ───────────────────────────────────────────────────
    "Salesforce":                ["SFDC", "Salesforce CRM", "Salesforce platform"],
    "HubSpot":                   ["Hubspot", "Hub Spot"],
    "Jira":                      ["JIRA", "Atlassian Jira"],
    "Confluence":                ["Atlassian Confluence"],
    "ServiceNow":                ["Service Now"],
    "Zendesk":                   ["Zendesk support"],
    "Workday":                   ["Workday HCM", "Workday HRIS"],
    "SAP":                       ["SAP ERP", "SAP S/4HANA"],
    "NetSuite":                  ["Oracle NetSuite", "Netsuite ERP"],
    "QuickBooks":                ["Quickbooks", "QuickBooks Online"],
    "Marketo":                   ["Marketo Engage", "Adobe Marketo"],
    "Pardot":                    ["Salesforce Pardot", "Marketing Cloud Account Engagement"],

    # ── Finance / accounting ─────────────────────────────────────────────
    "US GAAP":                   ["GAAP", "U.S. GAAP", "Generally Accepted Accounting Principles"],
    "IFRS":                      ["International Financial Reporting Standards"],
    "financial modeling":        ["financial modelling", "financial model building"],
    "DCF":                       ["discounted cash flow", "discounted cashflow"],
    "MEDDPICC":                  ["MEDDIC", "MEDDCC", "MEDDICC", "MEDDPIC"],

    # ── Product / design ─────────────────────────────────────────────────
    "product-led growth":        ["PLG", "product led growth"],
    "A/B testing":               ["AB testing", "A/B test", "split testing",
                                  "multivariate testing"],
    "Figma":                     ["Figma design"],
    "Sketch":                    ["Sketch app"],

    # ── HR / ops ─────────────────────────────────────────────────────────
    "HRIS":                      ["human resources information system",
                                  "HR information system", "HR systems"],
    "ATS":                       ["applicant tracking system", "recruiting software"],
}


# ---------------------------------------------------------------------------
# Category classifier
# ---------------------------------------------------------------------------

_TECHNICAL_SIGNALS = {
    "python", "java", "javascript", "typescript", "golang", "go", "rust",
    "c++", "c#", "ruby", "scala", "kotlin", "swift", "php",
    "aws", "azure", "gcp", "kubernetes", "docker", "terraform", "ansible",
    "linux", "unix", "windows server", "vmware", "openshift",
    "sql", "nosql", "spark", "hadoop", "kafka", "airflow", "dbt",
    "pytorch", "tensorflow", "scikit", "pandas", "numpy", "snowflake",
    "databricks", "bigquery", "redshift", "postgres", "mysql", "mongodb",
    "elasticsearch", "redis", "cassandra",
    "git", "ci/cd", "devops", "devsecops", "mlops", "api", "rest",
    "graphql", "grpc", "microservices", "agile", "scrum", "kanban",
    "tdd", "test-driven", "unit test", "integration test",
    "penetration", "siem", "soc", "firewall", "vpn", "tcp/ip",
    "zero trust", "iam", "oauth", "saml", "ldap", "sso",
    "sdk", "cli", "llm", "nlp", "ml", "ai", "neural", "computer vision",
    "deep learning", "machine learning", "data pipeline", "etl",
    "cloud", "serverless", "container", "orchestrat", "embed",
    "firmware", "fpga", "verilog", "hdl", "pcb", "cad", "autocad",
    "solidworks", "matlab", "labview", "plc",
    "tableau", "power bi", "looker", "qlik", "excel", "spreadsheet",
    "domo", "metabase", "mode analytics",
    "salesforce", "hubspot", "marketo", "pardot", "zendesk", "servicenow",
    "jira", "confluence", "notion", "asana", "monday",
    "bloomberg", "hyperion", "workday", "sap", "oracle", "netsuite",
    "quickbooks", "xero",
    "network engineer", "hardware design", "hardware test",
    "cloud-native", "cloud native", "enterprise integrat",
    "security scanning", "api development", "data quer",
}

_SOFT_SIGNALS = {
    "communication", "leadership", "collaboration", "teamwork",
    "problem.solving", "critical thinking", "emotional intelligence",
    "time management", "adaptability", "conflict resolution",
    "public speaking", "negotiation", "mentoring", "coaching",
    "storytelling", "executive presence", "cross.functional",
    "stakeholder", "relationship", "influencing",
}

_DOMAIN_SIGNALS = {
    "gaap", "ifrs", "sox", "pci", "hipaa", "gdpr", "ccpa", "iso",
    "sec reporting", "financial model", "valuation", "m&a",
    "supply chain", "logistics", "procurement", "inventory",
    "clinical", "regulatory", "fda", "gmp", "quality management",
    "lean", "six sigma", "operations research",
    "product strategy", "go-to-market", "product-led",
    "account-based", "demand generation", "revenue operations",
    "customer success", "customer experience",
}


def classify(name: str) -> str:
    n = name.lower()
    for sig in _TECHNICAL_SIGNALS:
        if sig in n:
            return "Technical"
    for sig in _SOFT_SIGNALS:
        if sig in n:
            return "Soft"
    for sig in _DOMAIN_SIGNALS:
        if sig in n:
            return "Domain"
    tech_suffixes = ("js", ".js", ".io", "db", "ml", "ai", "ops", "sql",
                     "sdk", "api", "os", "net", "lang")
    if any(n.endswith(s) for s in tech_suffixes):
        return "Technical"
    return "Domain"


def get_aliases(name: str) -> list[str]:
    """Case-insensitive lookup into ALIASES dict."""
    n_lower = name.lower()
    for canonical, alts in ALIASES.items():
        if canonical.lower() == n_lower:
            return alts
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv", default="data/skill_candidates_curated.csv")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}")

    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    print(f"Loaded {len(rows)} candidates from {csv_path}")

    if args.dry_run:
        cats = {"technical": 0, "soft": 0, "domain": 0}
        aliased = 0
        for row in rows:
            name = row["candidate"]
            c = classify(name)
            cats[c] += 1
            alts = get_aliases(name)
            if alts:
                aliased += 1
            alias_str = f"  → {alts}" if alts else ""
            print(f"  [{c:9s}]  {name}{alias_str}")
        print(f"\nCategory breakdown : {cats}")
        print(f"Skills with aliases: {aliased} / {len(rows)}")
        print("Dry run — nothing written.")
        return

    sys.path.insert(0, os.getcwd())
    from app import create_app, db
    from app.models import Skill

    app = create_app()
    with app.app_context():
        inserted = 0
        skipped = 0
        updated = 0

        for row in rows:
            name = row["candidate"].strip()
            job_count = int(row.get("job_count", 0) or 0)
            category = classify(name)
            aliases = get_aliases(name)

            existing = Skill.query.filter(
                db.func.lower(Skill.name) == name.lower()
            ).first()

            if existing:
                changed = False
                if job_count > (existing.total_job_count or 0):
                    existing.total_job_count = job_count
                    changed = True
                # Backfill aliases if none set yet
                if not existing.aliases and aliases:
                    existing.aliases = aliases
                    changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1
                continue

            skill = Skill(
                name=name,
                category=category,
                is_verified=True,
                total_job_count=job_count,
                trending_score=0.0,
                aliases=aliases,
            )
            db.session.add(skill)
            inserted += 1

        db.session.commit()
        print(f"\nDone.")
        print(f"  Inserted : {inserted}")
        print(f"  Updated  : {updated}  (job_count or aliases backfilled)")
        print(f"  Skipped  : {skipped}  (already in DB, no changes)")
        print(f"  Total    : {inserted + updated + skipped}")


if __name__ == "__main__":
    main()
