import logging

from bs4 import BeautifulSoup

from core.base import fetch_detail_soup, listing_page, resolve_url, short_delay
from core.extract import extract_contact, extract_job_type, extract_salary
from core.skills_keyword import extract_skills

log = logging.getLogger(__name__)


def scrape_linkedin(keyword="software engineer", max_jobs=25):
    base_url = "https://www.linkedin.com"
    url = f"{base_url}/jobs/search/?keywords={keyword}&location=Indonesia"

    with listing_page(url, "div.base-card", "LinkedIn") as loaded:
        if loaded is None:
            return []

        page, context = loaded
        soup = BeautifulSoup(page.content(), "html.parser")
        jobs = []

        for card in soup.select("div.base-card"):
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

                job_url = resolve_url(link_el.get("href", ""), base_url)
                location_text = location_el.text.strip() if location_el else ""

                description = ""
                salary = None
                job_type = "Full-time"
                contact_info = None

                try:
                    detail_soup = fetch_detail_soup(context, job_url, delay=short_delay)
                    if detail_soup:
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

    log.info("[LinkedIn] Keyword '%s' menghasilkan %d lowongan", keyword, len(jobs))
    return jobs