import logging
import re

from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from core.base import fetch_detail_soup, listing_page, resolve_url, short_delay
from core.extract import extract_contact, extract_job_type, extract_salary
from core.skills_keyword import extract_skills

log = logging.getLogger(__name__)

TYPE_ID_MAP = {
    "penuh waktu": "Full-time",
    "full time": "Full-time",
    "paruh waktu": "Part-time",
    "part time": "Part-time",
    "kontrak": "Contract",
    "contract": "Contract",
    "magang": "Internship",
    "internship": "Internship",
    "freelance": "Contract",
}


def _map_type(text):
    if not text:
        return None
    return TYPE_ID_MAP.get(text.strip().lower())


def _extract_description(detail_soup):
    desc_el = detail_soup.select_one(
        "[class*='JobDescription'], "
        "[data-testid='job-description'], "
        "[class*='jobDescription'], "
        "[class*='job-description']"
    )
    if desc_el:
        return desc_el.get_text("\n", strip=True)

    heading = detail_soup.find(re.compile("^h[1-6]$"), string=re.compile(r"deskripsi|description", re.I))
    if heading:
        node = heading.find_parent("div")
        if node:
            return node.get_text("\n", strip=True)

    main = detail_soup.find("main") or detail_soup.body
    if main:
        candidates = [el for el in main.find_all("div") if len(el.get_text(strip=True)) > 400]
        if candidates:
            best = min(candidates, key=lambda el: len(el.decode_contents()))
            return best.get_text("\n", strip=True)

    return ""


def scrape_glints(keyword="software engineer", max_jobs=25):
    base_url = "https://glints.com"
    url = (f"{base_url}/id/opportunities/jobs/explore"
           f"?keyword={quote_plus(keyword)}&country=ID&locationName=All+Cities%2FProvinces&lowestLocationLevel=1")

    wait_selector = "a[href*='/opportunities/jobs/']"
    with listing_page(url, wait_selector, "Glints") as loaded:
        if loaded is None:
            return []

        page, context = loaded
        soup = BeautifulSoup(page.content(), "html.parser")
        jobs = []
        seen_url = set()

        for card in soup.select("div[class*='CompactJobCard']"):
            if len(jobs) >= max_jobs:
                break

            try:
                title_el = card.select_one("a[href*='/opportunities/jobs/']")
                if not title_el:
                    continue

                job_url = resolve_url(title_el.get("href", ""), base_url)
                if job_url in seen_url:
                    continue
                seen_url.add(job_url)

                title_text = title_el.get_text(strip=True)

                company_text = ""
                company_img = card.select_one("img[alt]")
                if company_img and company_img.get("alt"):
                    company_text = company_img["alt"].strip()
                if not company_text:
                    company_span = card.select_one("[class*='CompanyLinkContainer']")
                    if company_span:
                        company_text = company_span.get_text(strip=True).split(",")[0].strip()

                loc_spans = [s.get_text(" ", strip=True) for s in card.select("[class*='LocationSpan']")]
                location_text = " ".join(t for t in loc_spans if t and t != ",").replace(" , ", ", ").strip(", ")

                job_type = None
                for tag in card.select("[class*='TagContentStyle']"):
                    job_type = _map_type(tag.get_text(strip=True))
                    if job_type:
                        break

                description = ""
                salary = None
                contact_info = None

                try:
                    detail_soup = fetch_detail_soup(context, job_url, timeout=20000, delay=short_delay)
                    if detail_soup:
                        description = _extract_description(detail_soup)
                        page_text = detail_soup.get_text(" ", strip=True)

                        salary = salary or extract_salary(description or page_text)
                        job_type = job_type or extract_job_type(description or page_text)
                        contact_info = extract_contact(description or page_text)

                        if not location_text:
                            loc_el = detail_soup.select_one("[class*='ocation']")
                            if loc_el:
                                location_text = loc_el.text.strip()
                except Exception as e:
                    log.debug("[Glints] Gagal ambil detail %s: %s", job_url, e)

                if not location_text:
                    location_text = "Indonesia"

                jobs.append({
                    "title": title_text,
                    "company": company_text,
                    "location": location_text,
                    "type": job_type or "Full-time",
                    "salary": salary,
                    "url": job_url,
                    "description": description,
                    "skills": extract_skills(description),
                    "contact_info": contact_info,
                })
            except Exception as e:
                log.debug("[Glints] Gagal proses kartu: %s", e)
                continue

    log.info("[Glints] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs