import logging

from bs4 import BeautifulSoup
from urllib.parse import parse_qs, quote_plus, urlparse

from core.base import listing_page, resolve_url
from core.extract import extract_job_type
from core.skills_keyword import extract_skills

log = logging.getLogger(__name__)


def _canonical_url(href):
    """/rc/clk?jk=... berisi token unik; pakai viewjob?jk= agar URL stabil untuk dedup."""
    qs = parse_qs(urlparse(href).query)
    jk = qs.get("jk", [None])[0]
    if jk:
        return f"https://id.indeed.com/viewjob?jk={jk}"
    return None


def scrape_indeed(keyword="software engineer", max_jobs=25):
    base_url = "https://id.indeed.com"
    url = f"{base_url}/jobs?q={quote_plus(keyword)}&l=Indonesia"

    with listing_page(url, "div.job_seen_beacon", "Indeed") as loaded:
        if loaded is None:
            return []

        page, _context = loaded
        soup = BeautifulSoup(page.content(), "html.parser")
        jobs = []

        for card in soup.select("div.job_seen_beacon"):
            if len(jobs) >= max_jobs:
                break

            try:
                title_el = card.select_one("h2 a[href], a.jcs-JobTitle")
                company_el = card.select_one("span[data-testid='company-name'], [data-testid='company-name']")
                location_el = card.select_one("div[data-testid='text-location'], [data-testid='text-location']")
                salary_el = card.select_one(
                    "[data-testid*='salary-snippet'], "
                    "[class*='salaryText'], "
                    "div[class*='metadata'] li:first-child"
                )

                if not title_el:
                    continue

                raw = resolve_url(title_el.get("href", ""), base_url)
                job_url = _canonical_url(raw) or raw
                if not job_url.startswith("http"):
                    continue

                title_text = title_el.text.strip()
                company_text = company_el.text.strip() if company_el else ""
                location_text = location_el.text.strip() if location_el else ""
                salary = salary_el.text.strip() if salary_el else None

                # Halaman detail (viewjob) memerlukan login sejak 2025,
                # jadi deskripsi tidak diambil; fallback ke judul di normalize().
                page_text = f"{title_text} {salary or ''}"

                jobs.append({
                    "title": title_text,
                    "company": company_text,
                    "location": location_text,
                    "type": extract_job_type(page_text),
                    "salary": salary,
                    "url": job_url,
                    "description": "",
                    "skills": extract_skills(page_text),
                    "contact_info": None,
                })
            except Exception as e:
                log.debug("[Indeed] Gagal proses kartu: %s", e)
                continue

    log.info("[Indeed] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs