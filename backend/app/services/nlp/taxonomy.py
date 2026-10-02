import re
from typing import TypedDict


class SkillMeta(TypedDict):
    canonical: str
    category: str


# Comprehensive Enterprise Skills Taxonomy
SKILLS_TAXONOMY: dict[str, SkillMeta] = {
    # ── Languages ─────────────────────────────────────────────────────────────
    "python": {"canonical": "Python", "category": "Programming Languages"},
    "javascript": {"canonical": "JavaScript", "category": "Programming Languages"},
    "typescript": {"canonical": "TypeScript", "category": "Programming Languages"},
    "golang": {"canonical": "Go", "category": "Programming Languages"},
    "go": {"canonical": "Go", "category": "Programming Languages"},
    "rust": {"canonical": "Rust", "category": "Programming Languages"},
    "java": {"canonical": "Java", "category": "Programming Languages"},
    "c++": {"canonical": "C++", "category": "Programming Languages"},
    "cpp": {"canonical": "C++", "category": "Programming Languages"},
    "c#": {"canonical": "C#", "category": "Programming Languages"},
    "csharp": {"canonical": "C#", "category": "Programming Languages"},
    "ruby": {"canonical": "Ruby", "category": "Programming Languages"},
    "php": {"canonical": "PHP", "category": "Programming Languages"},
    "scala": {"canonical": "Scala", "category": "Programming Languages"},
    "kotlin": {"canonical": "Kotlin", "category": "Programming Languages"},
    "swift": {"canonical": "Swift", "category": "Programming Languages"},
    "sql": {"canonical": "SQL", "category": "Programming Languages"},
    "bash": {"canonical": "Bash", "category": "Programming Languages"},
    "shell": {"canonical": "Shell Scripting", "category": "Programming Languages"},

    # ── Frameworks & Libraries ─────────────────────────────────────────────────
    "fastapi": {"canonical": "FastAPI", "category": "Frameworks"},
    "django": {"canonical": "Django", "category": "Frameworks"},
    "flask": {"canonical": "Flask", "category": "Frameworks"},
    "react": {"canonical": "React", "category": "Frameworks"},
    "react.js": {"canonical": "React", "category": "Frameworks"},
    "reactjs": {"canonical": "React", "category": "Frameworks"},
    "next.js": {"canonical": "Next.js", "category": "Frameworks"},
    "nextjs": {"canonical": "Next.js", "category": "Frameworks"},
    "vue": {"canonical": "Vue.js", "category": "Frameworks"},
    "vue.js": {"canonical": "Vue.js", "category": "Frameworks"},
    "angular": {"canonical": "Angular", "category": "Frameworks"},
    "angularjs": {"canonical": "Angular", "category": "Frameworks"},
    "node": {"canonical": "Node.js", "category": "Frameworks"},
    "node.js": {"canonical": "Node.js", "category": "Frameworks"},
    "nodejs": {"canonical": "Node.js", "category": "Frameworks"},
    "express": {"canonical": "Express.js", "category": "Frameworks"},
    "express.js": {"canonical": "Express.js", "category": "Frameworks"},
    "spring": {"canonical": "Spring Boot", "category": "Frameworks"},
    "spring boot": {"canonical": "Spring Boot", "category": "Frameworks"},
    ".net": {"canonical": ".NET", "category": "Frameworks"},
    "dotnet": {"canonical": ".NET", "category": "Frameworks"},
    "asp.net": {"canonical": ".NET", "category": "Frameworks"},

    # ── Databases & Caching ───────────────────────────────────────────────────
    "postgresql": {"canonical": "PostgreSQL", "category": "Databases"},
    "postgres": {"canonical": "PostgreSQL", "category": "Databases"},
    "psql": {"canonical": "PostgreSQL", "category": "Databases"},
    "mysql": {"canonical": "MySQL", "category": "Databases"},
    "redis": {"canonical": "Redis", "category": "Databases"},
    "mongodb": {"canonical": "MongoDB", "category": "Databases"},
    "mongo": {"canonical": "MongoDB", "category": "Databases"},
    "cassandra": {"canonical": "Cassandra", "category": "Databases"},
    "dynamodb": {"canonical": "DynamoDB", "category": "Databases"},
    "qdrant": {"canonical": "Qdrant", "category": "Databases"},
    "pinecone": {"canonical": "Pinecone", "category": "Databases"},
    "weaviate": {"canonical": "Weaviate", "category": "Databases"},
    "elasticsearch": {"canonical": "Elasticsearch", "category": "Databases"},
    "sqlite": {"canonical": "SQLite", "category": "Databases"},

    # ── Cloud, DevOps & Infrastructure ────────────────────────────────────────
    "aws": {"canonical": "AWS", "category": "Cloud & Infrastructure"},
    "amazon web services": {"canonical": "AWS", "category": "Cloud & Infrastructure"},
    "gcp": {"canonical": "GCP", "category": "Cloud & Infrastructure"},
    "google cloud": {"canonical": "GCP", "category": "Cloud & Infrastructure"},
    "azure": {"canonical": "Azure", "category": "Cloud & Infrastructure"},
    "docker": {"canonical": "Docker", "category": "Cloud & Infrastructure"},
    "kubernetes": {"canonical": "Kubernetes", "category": "Cloud & Infrastructure"},
    "k8s": {"canonical": "Kubernetes", "category": "Cloud & Infrastructure"},
    "terraform": {"canonical": "Terraform", "category": "Cloud & Infrastructure"},
    "ansible": {"canonical": "Ansible", "category": "Cloud & Infrastructure"},
    "linux": {"canonical": "Linux", "category": "Cloud & Infrastructure"},
    "ci/cd": {"canonical": "CI/CD", "category": "Cloud & Infrastructure"},
    "github actions": {"canonical": "GitHub Actions", "category": "Cloud & Infrastructure"},
    "jenkins": {"canonical": "Jenkins", "category": "Cloud & Infrastructure"},
    "git": {"canonical": "Git", "category": "Cloud & Infrastructure"},

    # ── AI, ML & Data ─────────────────────────────────────────────────────────
    "pytorch": {"canonical": "PyTorch", "category": "AI & Machine Learning"},
    "tensorflow": {"canonical": "TensorFlow", "category": "AI & Machine Learning"},
    "nlp": {"canonical": "NLP", "category": "AI & Machine Learning"},
    "natural language processing": {"canonical": "NLP", "category": "AI & Machine Learning"},
    "llm": {"canonical": "LLMs", "category": "AI & Machine Learning"},
    "large language models": {"canonical": "LLMs", "category": "AI & Machine Learning"},
    "langchain": {"canonical": "LangChain", "category": "AI & Machine Learning"},
    "huggingface": {"canonical": "Hugging Face", "category": "AI & Machine Learning"},
    "transformers": {"canonical": "Transformers", "category": "AI & Machine Learning"},
    "spacy": {"canonical": "spaCy", "category": "AI & Machine Learning"},
    "scikit-learn": {"canonical": "Scikit-Learn", "category": "AI & Machine Learning"},
    "sklearn": {"canonical": "Scikit-Learn", "category": "AI & Machine Learning"},
    "pandas": {"canonical": "Pandas", "category": "Data & Analytics"},
    "numpy": {"canonical": "NumPy", "category": "Data & Analytics"},
    "spark": {"canonical": "Apache Spark", "category": "Data & Analytics"},
    "kafka": {"canonical": "Apache Kafka", "category": "Data & Analytics"},
    "rabbitmq": {"canonical": "RabbitMQ", "category": "Data & Analytics"},
    "celery": {"canonical": "Celery", "category": "Architecture"},

    # ── Architecture & Practices ──────────────────────────────────────────────
    "microservices": {"canonical": "Microservices", "category": "Architecture"},
    "distributed systems": {"canonical": "Distributed Systems", "category": "Architecture"},
    "system design": {"canonical": "System Design", "category": "Architecture"},
    "rest": {"canonical": "REST API", "category": "Architecture"},
    "restful": {"canonical": "REST API", "category": "Architecture"},
    "rest api": {"canonical": "REST API", "category": "Architecture"},
    "graphql": {"canonical": "GraphQL", "category": "Architecture"},
    "grpc": {"canonical": "gRPC", "category": "Architecture"},
    "agile": {"canonical": "Agile", "category": "Methodologies"},
    "scrum": {"canonical": "Scrum", "category": "Methodologies"},
}


class SkillsExtractor:
    """High-throughput regex-based skills extractor with canonical taxonomy mapping."""

    def __init__(self, taxonomy: dict[str, SkillMeta] = SKILLS_TAXONOMY) -> None:
        self.taxonomy = taxonomy
        # Precompile patterns sorted by length descending so multi-word phrases match first
        self.compiled_patterns: list[tuple[re.Pattern, str, str]] = []
        sorted_keys = sorted(self.taxonomy.keys(), key=len, reverse=True)
        for term in sorted_keys:
            meta = self.taxonomy[term]
            # Use negative lookbehind/lookahead to prevent partial word matches
            escaped = re.escape(term)
            pattern = re.compile(
                r"(?<![a-zA-Z0-9])" + escaped + r"(?![a-zA-Z0-9])",
                re.IGNORECASE,
            )
            self.compiled_patterns.append((pattern, meta["canonical"], meta["category"]))

    def extract_skills(self, text: str) -> list[str]:
        """
        Extracts all canonical skills present in the text.
        Returns a sorted, deduplicated list of canonical skill names.
        """
        if not text:
            return []

        matched: set[str] = set()
        for pattern, canonical, _ in self.compiled_patterns:
            if pattern.search(text):
                matched.add(canonical)

        return sorted(list(matched))

    def extract_skills_with_categories(self, text: str) -> dict[str, list[str]]:
        """
        Extracts skills grouped by technical category.
        """
        if not text:
            return {}

        categorized: dict[str, set[str]] = {}
        for pattern, canonical, category in self.compiled_patterns:
            if pattern.search(text):
                categorized.setdefault(category, set()).add(canonical)

        return {cat: sorted(list(skills)) for cat, skills in categorized.items()}


skills_extractor = SkillsExtractor()
