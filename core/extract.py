import re


def extract_salary(text):
    if not text:
        return None

    patterns = [
        r"Rp\s?[\d.,]+\s?(rb|ribu|juta|jt|miliar|m)?",
        r"\$\s?[\d.,]+\s?(k|m)?",
        r"IDR\s?[\d.,]+",
        r"[\d.,]+\s?(juta|jt|rb|ribu|miliar)\s?(per|/)?\s?(bulan|tahun|month|year)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_job_type(text):
    if not text:
        return "Full-time"

    lowered = text.lower()
    if re.search(r"\bintern(ship)?\b", lowered):
        return "Internship"
    if re.search(r"\bpart[- ]?time\b", lowered):
        return "Part-time"
    if re.search(r"\bcontract\b|\bfreelance\b", lowered):
        return "Contract"
    return "Full-time"


def extract_contact(text):
    if not text:
        return None

    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if email:
        return email.group(0)

    phone = re.search(r"(?:\+62|0)\s?8[\d\s-]{8,12}", text)
    if phone:
        return phone.group(0).strip()

    return None