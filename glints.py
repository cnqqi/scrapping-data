import logging

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

from base import goto_with_retry, human_delay, jitter_scroll, short_delay
from browser import get_browser
from extract import extract_contact, extract_job_type, extract_salary
from skills_keyword import extract_skills

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
    p, browser, context = get_browser()
    jobs = []

    try:
        page = context.new_page()

        base_url = "https://glints.com"
        url = (f"{base_url}/id/opportunities/jobs/explore"
               f"?keyword={quote_plus(keyword)}&country=ID&locationName=All+Cities%2FProvinces&lowestLocationLevel=1")

        if not goto_with_retry(page, url):
            log.warning("[Glints] Gagal memuat halaman pencarian: %s", url)
            return jobs

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector("a[href*='/opportunities/jobs/']", timeout=30000)
        except Exception:
            log.warning("[Glints] Kartu lowongan tidak muncul untuk keyword: %s", keyword)

        soup = BeautifulSoup(page.content(), "html.parser")

        seen_url = set()
        for card in soup.select("div[class*='CompactJobCard']"):
            if len(jobs) >= max_jobs:
                break

            try:
                title_el = card.select_one("a[href*='/opportunities/jobs/']")
                if not title_el:
                    continue

                href = title_el.get("href", "")
                job_url = urljoin(base_url, href.split("?")[0])
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

                location_text = ""
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
                    detail_page = context.new_page()
                    detail_page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                    short_delay()
                    detail_soup = BeautifulSoup(detail_page.content(), "html.parser")

                    description = _extract_description(detail_soup)
                    page_text = detail_soup.get_text(" ", strip=True)

                    salary = salary or extract_salary(description or page_text)
                    job_type = job_type or extract_job_type(description or page_text)
                    contact_info = extract_contact(description or page_text)

                    if not location_text:
                        loc_el = detail_soup.select_one("[class*='ocation']")
                        if loc_el:
                            location_text = loc_el.text.strip()

                    detail_page.close()
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
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()

    log.info("[Glints] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs
