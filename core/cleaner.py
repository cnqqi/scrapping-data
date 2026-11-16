from core.location import is_foreign


def clean_job(job):
    cleaned, _ = clean_job_detail(job)
    return cleaned


def clean_job_detail(job):
    """Kembalikan (dict_bersih, reason) — reason terisi hanya saat ditolak."""
    company = job.get("company")
    title = job.get("title")
    url = job.get("url")
    location = (job.get("location") or "").strip() or "Indonesia"

    if not company:
        return None, "company kosong"
    if not title:
        return None, "title kosong"
    if not url:
        return None, "url kosong"

    company = company.strip()
    title = title.strip()
    url = url.strip()

    if len(company) < 2:
        return None, "company < 2 karakter"
    if len(title) < 5:
        return None, "title < 5 karakter"

    if not url.startswith("http"):
        return None, "url tidak diawali http"

    if is_foreign(location):
        return None, "lokasi luar negeri"

    return {
        "company": company,
        "title": title,
        "url": url,
        "location": location,
        "description": (job.get("description") or "").strip(),
        "skills": job.get("skills", []),
        "type": job.get("type", "Full-time"),
        "salary": (job.get("salary") or "").strip() or None,
        "contact_info": (job.get("contact_info") or "").strip() or None,
    }, None