import logging

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from base import goto_with_retry, human_delay, jitter_scroll, short_delay
from browser import get_browser
from extract import extract_contact, extract_job_type, extract_salary
from skills_keyword import extract_skills

log = logging.getLogger(__name__)


def scrape_jobstreet(keyword="developer", max_jobs=25):
    p, browser, context = get_browser()
    jobs = []

    try:
        page = context.new_page()

        base_url = "https://id.jobstreet.com"
        slug = keyword.strip().lower().replace(" ", "-")
        url = f"{base_url}/id/{slug}-jobs"

        if not goto_with_retry(page, url):
            log.warning("[JobStreet] Gagal memuat halaman pencarian: %s", url)
            return jobs

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector(
                "article[data-testid='job-card'], article[data-automation='job-card']",
                timeout=30000,
            )
        except Exception:
            log.warning("[JobStreet] Kartu lowongan tidak muncul untuk keyword: %s", keyword)

        soup = BeautifulSoup(page.content(), "html.parser")

        cards = soup.select("article[data-testid='job-card'], article[data-automation='job-card'], article")

        for card in cards:
            if len(jobs) >= max_jobs:
                break

            try:
                title_el = card.select_one(
                    "a[data-automation='jobTitle'], "
                    "h1[data-automation='job-detail-title'], "
                    "a[data-testid='job-title'], "
                    "h3 a, h2 a, a[href*='/job/']"
                )
                company_el = card.select_one(
                    "span[data-automation='jobCompany'], "
                    "a[data-automation='jobCompany'], "
                    "[data-testid='company-name'], "
                    "span[class*='company'], "
                    "a[class*='company']"
                )
                location_el = card.select_one(
                    "span[data-automation='jobLocation'], "
                    "span[class*='location'], "
                    "[data-testid='job-location']"
                )

                if not title_el:
                    continue

                title_text = title_el.text.strip()
                company_text = company_el.text.strip() if company_el else ""
                location_text = location_el.text.strip() if location_el else ""

                href = title_el.get("href", "")
                if not href:
                    continue

                if href.startswith("http"):
                    job_url = href.split("?")[0]
                else:
                    job_url = urljoin(base_url, href.split("?")[0])

                description = ""
                salary = None
                job_type = "Full-time"
                contact_info = None

                try:
                    detail_page = context.new_page()
                    detail_page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
                    short_delay()
                    detail_soup = BeautifulSoup(detail_page.content(), "html.parser")

                    desc_el = detail_soup.select_one(
                        "div[data-automation='jobAdDetails'], "
                        "div[class*='description'], "
                        "section[class*='description'], "
                        "article"
                    )
                    if desc_el:
                        description = desc_el.text.strip()

                    salary_el = detail_soup.select_one(
                        "span[data-automation='jobSalary'], "
                        "span[class*='salary']"
                    )
                    if salary_el:
                        salary = salary_el.text.strip() or None
                    if not salary:
                        page_text = detail_soup.get_text(" ", strip=True)
                        salary = extract_salary(description or page_text)

                    page_text = detail_soup.get_text(" ", strip=True)
                    job_type = extract_job_type(page_text)
                    contact_info = extract_contact(description or page_text)

                    if not location_text:
                        loc_el = detail_soup.select_one(
                            "span[data-automation='jobLocation'], "
                            "span[class*='location']"
                        )
                        if loc_el:
                            location_text = loc_el.text.strip()

                    detail_page.close()
                except Exception as e:
                    log.debug("[JobStreet] Gagal ambil detail %s: %s", job_url, e)

                if not location_text:
                    location_text = "Indonesia"

                jobs.append({
                    "title": title_text,
                    "company": company_text,
                    "location": location_text,
                    "type": job_type,
                    "salary": salary,
                    "url": job_url,
                    "description": description,
                    "skills": extract_skills(description),
                    "contact_info": contact_info,
                })
            except Exception as e:
                log.debug("[JobStreet] Gagal proses kartu: %s", e)
                continue
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()

    log.info("[JobStreet] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs