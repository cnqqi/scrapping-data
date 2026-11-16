import re


SKILLS_DB = [
    # Programming Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "golang",
    "rust", "kotlin", "swift", "php", "ruby", "scala", "dart",
    "shell", "bash", "powershell",

    # Web Frontend
    "react", "react native", "vue", "vue.js", "angular", "next.js", "nextjs",
    "nuxt", "svelte", "html", "css", "scss", "sass", "tailwind",
    "bootstrap", "jquery",

    # Web Backend
    "node.js", "nodejs", "express", "django", "flask", "fastapi", "spring",
    "spring boot", "laravel", "rails", "asp.net", ".net", "gin", "echo",

    # Database
    "postgresql", "postgres", "mysql", "mariadb", "sqlite", "mongodb",
    "mongo", "redis", "elasticsearch", "cassandra", "dynamodb", "sql server",
    "oracle", "firebase", "supabase",

    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform",
    "jenkins", "gitlab ci", "github actions", "circleci", "ansible", "nginx",
    "linux", "ci/cd",

    # Tools & Platforms
    "git", "github", "gitlab", "bitbucket", "jira", "confluence", "slack",
    "figma", "postman",

    # Data & ML
    "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "matplotlib", "data analysis", "data science",
    "natural language processing", "nlp", "computer vision",

    # Mobile
    "flutter", "ios", "android",

    # Testing
    "selenium", "jest", "pytest", "mocha", "cypress", "unit testing",
    "integration testing",

    # Methodologies & Soft Skills
    "agile", "scrum", "kanban", "rest api", "graphql", "microservices",
    "oauth", "jwt", "design patterns", "oop", "mvc",

    # UI/UX
    "ui design", "ux design", "ui/ux", "wireframe", "prototype",
]


# Kata ambigu yang hanya dianggap skill jika muncul dengan konteks teknis.
# Pola kecocokan disimpan lowercase.
AMBIGUOUS = {
    "go": [
        r"\bgo\s+(language|lang|development|developer|programming)\b",
        r"\bwritten?\s+in\s+go\b",
        r"\bgo\s+golang\b",
    ],
    "r": [
        r"\br\s+(language|programming|studio)\b",
    ],
    "less": [
        r"\bless\s+(css|preprocessor)\b",
        r"\bscss\s*/\s*less\b",
        r"\bsass\s*/\s*less\b",
    ],
}


def _match_ambiguous(text):
    return [skill for skill, pattern in _AMBIGUOUS_PATTERNS if pattern.search(text)]


# Precompile semua pola sekali saat import supaya pencocokan lebih cepat.
_SKILL_PATTERNS = [
    (skill, re.compile(r"\b" + re.escape(skill.lower()) + r"\b"))
    for skill in SKILLS_DB
]
_AMBIGUOUS_PATTERNS = [
    (skill, re.compile(pattern, re.IGNORECASE))
    for skill, patterns in AMBIGUOUS.items()
    for pattern in patterns
]


def extract_skills(text):
    """Extract skills from job description text using keyword matching."""
    if not text:
        return []

    text_lower = text.lower()
    found = [skill for skill, pattern in _SKILL_PATTERNS if pattern.search(text_lower)]
    found += _match_ambiguous(text)

    return list(set(found))
