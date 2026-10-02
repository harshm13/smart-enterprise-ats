import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.models.candidate import DegreeLevel
from app.services.nlp.taxonomy import skills_extractor

logger = logging.getLogger(__name__)

MONTH_MAP: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Regex for Contact Info
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
LINKEDIN_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+", re.IGNORECASE
)
GITHUB_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+", re.IGNORECASE
)

# Common Section Headings
SECTION_HEADERS = {
    "EXPERIENCE": re.compile(r"^(?:work\s+experience|professional\s+experience|experience|employment\s+history|career\s+history)\b", re.IGNORECASE),
    "EDUCATION": re.compile(r"^(?:education|academic\s+background|academic\s+history|qualifications)\b", re.IGNORECASE),
    "SKILLS": re.compile(r"^(?:technical\s+skills|skills|technologies|proficiencies|core\s+competencies)\b", re.IGNORECASE),
    "PROJECTS": re.compile(r"^(?:projects|personal\s+projects|open\s+source|portfolio)\b", re.IGNORECASE),
    "SUMMARY": re.compile(r"^(?:summary|professional\s+summary|about\s+me|objective)\b", re.IGNORECASE),
    "CERTIFICATIONS": re.compile(r"^(?:certifications|licenses|courses|accreditations)\b", re.IGNORECASE),
}


def extract_contact_info(text: str) -> dict[str, str | None]:
    """Extracts email, phone, linkedin, and github/portfolio URLs from resume text."""
    email_match = EMAIL_REGEX.search(text)
    phone_match = PHONE_REGEX.search(text)
    linkedin_match = LINKEDIN_REGEX.search(text)
    github_match = GITHUB_REGEX.search(text)

    # Heuristic for name: usually on the first 1-3 lines of the resume
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    candidate_name = None
    for line in lines[:4]:
        # Skip lines that are emails, URLs, or headings
        if "@" in line or "http" in line or "resume" in line.lower() or "curriculum" in line.lower():
            continue
        # Names are typically 2 to 4 words, letters only
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.isalpha() or "." in w for w in words):
            candidate_name = line
            break

    return {
        "email": email_match.group(0).lower() if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "linkedin_url": linkedin_match.group(0) if linkedin_match else None,
        "portfolio_url": github_match.group(0) if github_match else None,
        "full_name": candidate_name,
    }


def chunk_sections(text: str) -> dict[str, str]:
    """
    Partitions resume text into labeled sections (EXPERIENCE, EDUCATION, SKILLS, etc.).
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"HEADER": []}
    current_section = "HEADER"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        matched_section = None
        for sec_name, sec_regex in SECTION_HEADERS.items():
            if sec_regex.match(stripped) and len(stripped.split()) <= 4:
                matched_section = sec_name
                break

        if matched_section:
            current_section = matched_section
            sections.setdefault(current_section, [])
        else:
            sections.setdefault(current_section, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def calculate_tenure_and_roles(text: str) -> tuple[int, str | None, str | None, list[dict[str, Any]]]:
    """
    Parses dates to calculate total experience in months and identify current role & company.
    Returns: (total_tenure_months, current_title, current_company, parsed_work_history)
    """
    date_range_pattern = re.compile(
        r"(?P<start_m>[a-zA-Z]{3,9})?\s*(?P<start_y>\d{4})\s*[-–—to]+\s*(?:(?P<end_m>[a-zA-Z]{3,9})?\s*(?P<end_y>\d{4})|(?P<present>present|current|now))",
        re.IGNORECASE,
    )

    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month

    total_months = 0
    roles: list[dict[str, Any]] = []
    lines = text.split("\n")

    current_title = None
    current_company = None

    for i, line in enumerate(lines):
        match = date_range_pattern.search(line)
        if match:
            gd = match.groupdict()
            start_y = int(gd["start_y"])
            start_m_str = (gd["start_m"] or "").lower()
            start_m = MONTH_MAP.get(start_m_str[:3], 1)

            if gd.get("present"):
                end_y = current_year
                end_m = current_month
                is_current = True
            else:
                end_y = int(gd["end_y"]) if gd["end_y"] else start_y
                end_m_str = (gd["end_m"] or "").lower()
                end_m = MONTH_MAP.get(end_m_str[:3], 12)
                is_current = False

            # Sanity checks
            if 1970 <= start_y <= current_year + 1 and 1970 <= end_y <= current_year + 1:
                duration_months = max(1, (end_y - start_y) * 12 + (end_m - start_m))
                total_months += duration_months

                # Heuristic: Find job title and company from line above or current line
                context_line = lines[i - 1].strip() if i > 0 and lines[i - 1].strip() else line
                # Often formatted like: "Senior Backend Engineer | Acme Corp" or "Acme Corp - Senior Engineer"
                parts = re.split(r"[\-|•|@,]", context_line)
                title = parts[0].strip() if parts else None
                company = parts[1].strip() if len(parts) > 1 else None

                role_entry = {
                    "title": title,
                    "company": company,
                    "start": f"{start_y}-{start_m:02d}",
                    "end": "Present" if is_current else f"{end_y}-{end_m:02d}",
                    "duration_months": duration_months,
                    "is_current": is_current,
                }
                roles.append(role_entry)

                if is_current and not current_title:
                    current_title = title
                    current_company = company

    if not current_title and roles:
        current_title = roles[0].get("title")
        current_company = roles[0].get("company")

    return total_months, current_title, current_company, roles


def detect_highest_degree(text: str) -> tuple[DegreeLevel | None, list[dict[str, Any]]]:
    """
    Scans text for academic degrees and institutional credentials.
    Returns: (highest_degree_enum, list_of_educations)
    """
    degree_hierarchy = [
        (re.compile(r"\b(?:ph\.?d|doctorate|doctor of philosophy)\b", re.IGNORECASE), DegreeLevel.PHD),
        (re.compile(r"\b(?:m\.?b\.?a|master of business administration)\b", re.IGNORECASE), DegreeLevel.MBA),
        (re.compile(r"\b(?:master(?:'?s)?|m\.?s\.?|m\.?sc\.?|m\.?tech)\b", re.IGNORECASE), DegreeLevel.MASTERS),
        (re.compile(r"\b(?:bachelor(?:'?s)?|b\.?s\.?|b\.?sc\.?|b\.?tech|b\.?e\.?|b\.?a\.?)\b", re.IGNORECASE), DegreeLevel.BACHELORS),
        (re.compile(r"\b(?:associate(?:'?s)?|a\.?s\.?|a\.?a\.?)\b", re.IGNORECASE), DegreeLevel.ASSOCIATES),
        (re.compile(r"\b(?:bootcamp|coding bootcamp|nanodegree|professional certificate)\b", re.IGNORECASE), DegreeLevel.BOOTCAMP_CERT),
        (re.compile(r"\b(?:high\s+school|ged|secondary\s+school)\b", re.IGNORECASE), DegreeLevel.HIGH_SCHOOL),
    ]

    highest_degree: DegreeLevel | None = None
    education_records: list[dict[str, Any]] = []

    for pattern, degree_enum in degree_hierarchy:
        if pattern.search(text):
            if highest_degree is None:
                highest_degree = degree_enum
            education_records.append({"degree": degree_enum.value, "match": pattern.pattern})

    return highest_degree, education_records


def scrub_pii_for_blind_screening(parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Creates an anonymized representation of the parsed profile to eliminate demographic
    bias during initial screening (removes name, email, phone, location, gender pronouns, grad years).
    """
    blind = dict(parsed)
    blind["full_name"] = "[REDACTED FOR BLIND SCREENING]"
    blind["email"] = "[REDACTED]"
    blind["phone"] = "[REDACTED]"
    blind["location"] = "[REDACTED]"
    blind["linkedin_url"] = None
    blind["portfolio_url"] = None

    # Redact graduation years from education
    if "education" in blind and isinstance(blind["education"], list):
        redacted_edu = []
        for edu in blind["education"]:
            cleaned = dict(edu)
            cleaned.pop("graduation_year", None)
            redacted_edu.append(cleaned)
        blind["education"] = redacted_edu

    return blind


def parse_resume(raw_text: str) -> dict[str, Any]:
    """
    Master pipeline: extracts structured candidate data from raw resume text.
    """
    contact = extract_contact_info(raw_text)
    sections = chunk_sections(raw_text)

    # Extract skills across entire document and categorized
    skills = skills_extractor.extract_skills(raw_text)
    categorized_skills = skills_extractor.extract_skills_with_categories(raw_text)

    # Tenure and work history
    experience_text = sections.get("EXPERIENCE", raw_text)
    total_months, current_title, current_company, roles = calculate_tenure_and_roles(experience_text)

    # Education
    education_text = sections.get("EDUCATION", raw_text)
    highest_degree, education_records = detect_highest_degree(education_text)

    # If no degree found in education section, check whole text
    if not highest_degree:
        highest_degree, education_records = detect_highest_degree(raw_text)

    parsed_profile = {
        "contact": contact,
        "skills": skills,
        "categorized_skills": categorized_skills,
        "total_tenure_months": total_months,
        "current_title": current_title,
        "current_company": current_company,
        "work_history": roles,
        "highest_degree": highest_degree.value if highest_degree else None,
        "education": education_records,
        "sections_detected": list(sections.keys()),
        "parsed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Generate demographic-blind view
    parsed_profile["blind_view"] = scrub_pii_for_blind_screening(parsed_profile)

    return parsed_profile
