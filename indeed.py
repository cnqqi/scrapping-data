import logging

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus, parse_qs, urlparse

from base import goto_with_retry, human_delay, jitter_scroll
from browser import get_browser
from extract import extract_job_type
from skills_keyword import extract_skills

log = logging.getLogger(__name__)


def _canonical_url(href):
    """/rc/clk?jk=... berisi token unik; pakai viewjob?jk= agar URL stabil untuk dedup."""
    qs = parse_qs(urlparse(href).query)
    jk = qs.get("jk", [None])[0]
    if jk:
        return f"https://id.indeed.com/viewjob?jk={jk}"
    return None


def scrape_indeed(keyword="software engineer", max_jobs=25):
    p, browser, context = get_browser()
    jobs = []

    try:
        page = context.new_page()

        base_url = "https://id.indeed.com"
        url = f"{base_url}/jobs?q={quote_plus(keyword)}&l=Indonesia"

        if not goto_with_retry(page, url):
            log.warning("[Indeed] Gagal memuat halaman pencarian: %s", url)
            return jobs

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector("div.job_seen_beacon", timeout=30000)
        except Exception:
            log.warning("[Indeed] Kartu lowongan tidak muncul untuk keyword: %s", keyword)

        soup = BeautifulSoup(page.content(), "html.parser")

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

                href = title_el.get("href", "")
                if href.startswith("http"):
                    raw = href.split("?")[0]
                else:
                    raw = urljoin(base_url, href)

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
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()

    log.info("[Indeed] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs
