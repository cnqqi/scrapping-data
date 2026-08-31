import logging

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from base import goto_with_retry, human_delay, jitter_scroll, short_delay
from browser import get_browser
from extract import extract_contact, extract_job_type, extract_salary
from skills_keyword import extract_skills

log = logging.getLogger(__name__)


def scrape_linkedin(keyword="software engineer", max_jobs=25):
    p, browser, context = get_browser()
    jobs = []

    try:
        page = context.new_page()

        base_url = "https://www.linkedin.com"
        url = f"{base_url}/jobs/search/?keywords={keyword}&location=Indonesia"

        if not goto_with_retry(page, url):
            log.warning("[LinkedIn] Gagal memuat halaman pencarian: %s", url)
            return jobs

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector("div.base-card", timeout=30000)
        except Exception:
            log.warning("[LinkedIn] Kartu lowongan tidak muncul untuk keyword: %s", keyword)

        soup = BeautifulSoup(page.content(), "html.parser")

        cards = soup.select("div.base-card")

        for card in cards:
            if len(jobs) >= max_jobs:
                break

            try:
                title_el = card.select_one(
                    "h3.base-search-card__title, "
                    "span.screen-reader-text, "
                    "h3"
                )
                company_el = card.select_one(
                    "h4.base-search-card__subtitle, "
                    "a.hidden-nested-link, "
                    "h4"
                )
                location_el = card.select_one(
                    "span.job-search-card__location, "
                    "span[class*='location']"
                )
                link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")

                if not (title_el and company_el and link_el):
                    continue

                href = link_el.get("href", "")
                if href.startswith("http"):
                    job_url = href.split("?")[0]
                else:
                    job_url = urljoin(base_url, href.split("?")[0])

                location_text = location_el.text.strip() if location_el else ""

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
                        "div.description__text, "
                        "div[class*='description'], "
                        "section[class*='description']"
                    )
                    if desc_el:
                        description = desc_el.text.strip()

                    page_text = detail_soup.get_text(" ", strip=True)

                    salary = extract_salary(description or page_text)
                    job_type = extract_job_type(page_text)
                    contact_info = extract_contact(description or page_text)

                    if not location_text:
                        loc_el = detail_soup.select_one(
                            "div[class*='location'], "
                            "span[class*='location']"
                        )
                        if loc_el:
                            location_text = loc_el.text.strip()

                    detail_page.close()
                except Exception as e:
                    log.debug("[LinkedIn] Gagal ambil detail %s: %s", job_url, e)

                if not location_text:
                    location_text = "Indonesia"

                jobs.append({
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip(),
                    "location": location_text,
                    "type": job_type,
                    "salary": salary,
                    "url": job_url,
                    "description": description,
                    "skills": extract_skills(description),
                    "contact_info": contact_info,
                })
            except Exception as e:
                log.debug("[LinkedIn] Gagal proses kartu: %s", e)
                continue
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()

    log.info("[LinkedIn] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs