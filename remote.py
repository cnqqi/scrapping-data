import logging
import time

import httpx
from bs4 import BeautifulSoup

from extract import extract_contact, extract_job_type, extract_salary
from skills_keyword import extract_skills

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

JOB_TYPE_MAP = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "contractor": "Contract",
    "contract": "Contract",
    "internship": "Internship",
    "temporary": "Contract",
    "other": "Full-time",
}

_remoteok_cache = {"data": None, "ts": 0}
REMOTEOK_CACHE_TTL = 3600


def _strip_html(html):
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def _match_keyword(job_text, keyword):
    tokens = [t for t in keyword.lower().split() if t]
    return all(t in job_text for t in tokens)


def _fetch_remoteok():
    now = time.time()
    if _remoteok_cache["data"] is not None and now - _remoteok_cache["ts"] < REMOTEOK_CACHE_TTL:
        return _remoteok_cache["data"]

    resp = httpx.get(
        "https://remoteok.com/api",
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    data = [item for item in resp.json() if isinstance(item, dict) and item.get("position")]

    _remoteok_cache["data"] = data
    _remoteok_cache["ts"] = now
    return data


def scrape_remoteok(keyword="software engineer", max_jobs=25):
    jobs = []

    try:
        listings = _fetch_remoteok()
    except Exception as e:
        log.error("[RemoteOK] Gagal memuat API: %s", e)
        return jobs

    for item in listings:
        if len(jobs) >= max_jobs:
            break

        title = (item.get("position") or "").strip()
        company = (item.get("company") or "").strip()
        url = (item.get("url") or item.get("apply_url") or "").split("?")[0].strip()

        description_html = item.get("description") or ""
        description = _strip_html(description_html)

        haystack = f"{title} {' '.join(item.get('tags') or [])} {company} {description[:600]}".lower()
        if not _match_keyword(haystack, keyword):
            continue

        salary = None
        salary_min = item.get("salary_min") or 0
        salary_max = item.get("salary_max") or 0
        if salary_min and salary_max:
            salary = f"${salary_min:,} - ${salary_max:,}"
        else:
            salary = extract_salary(description)

        location = (item.get("location") or "").strip() or "Remote"

        page_text = f"{title} {description}"
        job_type = extract_job_type(page_text)
        contact_info = extract_contact(description)

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "type": job_type,
            "salary": salary,
            "url": url,
            "description": description,
            "skills": extract_skills(description),
            "contact_info": contact_info,
        })

    log.info("[RemoteOK] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs


def scrape_remotive(keyword="software engineer", max_jobs=25):
    jobs = []

    try:
        resp = httpx.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": keyword, "limit": max_jobs * 3},
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        listings = resp.json().get("jobs", [])
    except Exception as e:
        log.error("[Remotive] Gagal memuat API: %s", e)
        return jobs

    for item in listings:
        if len(jobs) >= max_jobs:
            break

        title = (item.get("title") or "").strip()
        company = (item.get("company_name") or "").strip()
        url = (item.get("url") or "").split("?")[0].strip()

        description_html = item.get("description") or ""
        description = _strip_html(description_html)

        salary = (item.get("salary") or "").strip() or None
        if not salary:
            salary = extract_salary(description)

        location = (item.get("candidate_required_location") or "").strip() or "Remote"

        raw_type = (item.get("job_type") or "").lower()
        job_type = JOB_TYPE_MAP.get(raw_type) or extract_job_type(f"{title} {description}")

        tags = " ".join(item.get("tags") or [])
        skills = list(set(extract_skills(description) + extract_skills(tags)))
        contact_info = extract_contact(description)

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "type": job_type,
            "salary": salary,
            "url": url,
            "description": description,
            "skills": skills,
            "contact_info": contact_info,
        })

    log.info("[Remotive] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs
