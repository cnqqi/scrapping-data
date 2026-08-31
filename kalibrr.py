import logging
import re

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

from base import goto_with_retry, human_delay, jitter_scroll, short_delay
from browser import get_browser
from extract import extract_contact, extract_job_type, extract_salary
from skills_keyword import extract_skills

log = logging.getLogger(__name__)

SALARY_NOISE = {"salary undisclosed", "salary negotiable", "-"}


def _parse_card_fields(container):
    """Ambil lokasi/gaji/tipe dari urutan span abu-abu pada kartu."""
    texts = []
    for el in container.select("span[class*='k-text-gray-500'], p[class*='k-text-gray-500']"):
        t = el.get_text(" ", strip=True)
        if t and t not in texts:
            texts.append(t)

    location_text = ""
    salary = None
    job_type = None

    for t in texts:
        lowered = t.lower()
        if not location_text and not re.match(r"^(salary|full|part|contract|intern|freelance|temporary)", lowered) \
                and "hiring" not in lowered and "apply before" not in lowered:
            location_text = t
        elif lowered.startswith(("rp", "idr", "$", "salary")) and lowered not in SALARY_NOISE \
                and not lowered.startswith("salary undisclosed"):
            salary = t
        elif re.search(r"\b(full|part)[- ]?time\b|\bcontract\b|\bintern\w*\b|\bfreelance\b|\btemporary\b", lowered) \
                and not job_type:
            job_type = t

    return location_text, salary, job_type


def _extract_description(detail_soup):
    heading = detail_soup.find(re.compile("^h[1-6]$"), string=re.compile(r"job description", re.I))
    if heading:
        container = heading.find_parent("div", class_="k-p-4")
        if not container:
            container = heading.parent
        text = container.get_text("\n", strip=True)
        if len(text) > len(heading.get_text(strip=True)) * 2:
            return text
        return ""

    main = detail_soup.find("main")
    scope = main or detail_soup.body or detail_soup
    candidates = [el for el in scope.find_all(["div", "section"])
                  if 400 < len(el.get_text(strip=True)) <= 20000]
    if candidates:
        best = min(candidates, key=lambda el: len(el.decode_contents()))
        return best.get_text("\n", strip=True)

    return ""


def scrape_kalibrr(keyword="software engineer", max_jobs=25):
    p, browser, context = get_browser()
    jobs = []

    try:
        page = context.new_page()

        base_url = "https://www.kalibrr.com"
        url = f"{base_url}/home/jobs?keywords={quote_plus(keyword)}"

        if not goto_with_retry(page, url):
            log.warning("[Kalibrr] Gagal memuat halaman pencarian: %s", url)
            return jobs

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector("a[href*='/c/'][href*='/jobs/']", timeout=30000)
        except Exception:
            log.warning("[Kalibrr] Kartu lowongan tidak muncul untuk keyword: %s", keyword)

        soup = BeautifulSoup(page.content(), "html.parser")

        anchors = []
        seen_href = set()
        for a in soup.select("a[href*='/c/']"):
            href = a.get("href", "")
            match = re.search(r"/c/[^/]+/jobs/(\d+)/", href)
            if not match or href in seen_href:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            seen_href.add(href)
            anchors.append((a, urljoin(base_url, href)))

        for anchor, job_url in anchors:
            if len(jobs) >= max_jobs:
                break

            try:
                title_text = anchor.get_text(strip=True)

                container = anchor.find_parent("div", class_="k-group")
                if container is None:
                    container = anchor.find_parent("div")

                company_text = ""
                company_link = container.select_one("a[href*='Company%20Name']")
                if company_link:
                    company_text = company_link.get_text(strip=True)
                if not company_text:
                    company_span = container.select_one("span[class*='k-inline-flex']")
                    if company_span:
                        company_text = company_span.get_text(strip=True)

                location_text, salary, job_type = _parse_card_fields(container)

                description = ""
                contact_info = None

                try:
                    detail_page = context.new_page()
                    detail_page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
                    human_delay(2, 4)
                    detail_soup = BeautifulSoup(detail_page.content(), "html.parser")

                    description = _extract_description(detail_soup)
                    page_text = detail_soup.get_text(" ", strip=True)

                    salary = salary or extract_salary(description or page_text)
                    job_type = job_type or extract_job_type(description or page_text)
                    contact_info = extract_contact(description or page_text)

                    if not location_text:
                        loc_el = detail_soup.select_one("[class*='location']")
                        if loc_el:
                            location_text = loc_el.text.strip()

                    detail_page.close()
                except Exception as e:
                    log.debug("[Kalibrr] Gagal ambil detail %s: %s", job_url, e)

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
                log.debug("[Kalibrr] Gagal proses kartu: %s", e)
                continue
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()

    log.info("[Kalibrr] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs
