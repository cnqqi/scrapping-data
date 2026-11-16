import logging
import re
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from core.base import (
    close_browser,
    fetch_detail_soup,
    goto_with_retry,
    human_delay,
    jitter_scroll,
    resolve_url,
    short_delay,
)
from core.browser import get_browser
from core.extract import extract_contact, extract_job_type, extract_salary
from core.skills_keyword import extract_skills

log = logging.getLogger(__name__)

# Durasi maksimum per halaman detail (detik) sebelum menyerah.
DETAIL_TIMEOUT_MS = 20000

# Teks yang menandai halaman sudah selesai memuat lowongan.
EMPTY_MARKERS = (
    "tidak ada lowongan",
    "no results",
    "no jobs",
    "belum ada lowongan",
    "0 lowongan",
)


def build_url(template, keyword):
    """Ganti placeholder pada template URL dengan keyword.

    {keyword}      -> keyword yang sudah di-URL-encode (paling umum)
    {keyword_raw}  -> keyword apa adanya
    """
    url = (template or "").strip()
    if "{keyword}" in url:
        url = url.replace("{keyword}", quote_plus(keyword or ""))
    if "{keyword_raw}" in url:
        url = url.replace("{keyword_raw}", keyword or "")
    return url


def _pick(card, selector):
    """Cari satu elemen di dalam kartu.

    Selector boleh berupa CSS biasa ("a[href]") atau "attr:nama-atribut"
    ("attr:data-url") untuk mengambil elemen yang punya atribut tersebut.
    """
    if not selector:
        return None
    sel = selector.strip()
    if sel.startswith("attr:"):
        name = sel[len("attr:"):].strip()
        if not name:
            return None
        if card.has_attr(name):
            return card
        return card.find(attrs={name: True})
    try:
        return card.select_one(sel)
    except Exception as e:
        log.debug("Selector tidak valid (%s): %s", sel, e)
        return None


def _text(node):
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _href_of(card, node):
    """Ambil URL lowongan dari elemen terpilih, atau dari kartu itu sendiri."""
    for candidate in (node, card):
        if candidate is None:
            continue
        if candidate.has_attr("href"):
            return candidate["href"]
    link = card.select_one("a[href]")
    return link["href"] if link else None


def _attribute_value(node, fallback_attr=None):
    """Teks dari elemen terpilih, atau atribut Alternatifnya.

    Banyak situs menaruh nama perusahaan di `alt` gambar logo, jadi bila teks
    elemen kosong, cari dulu atribut di dalam elemen itu sebelum menyerah.
    """
    if node is None:
        return ""
    if fallback_attr and node.has_attr(fallback_attr):
        return str(node[fallback_attr]).strip()
    for attr in ("content", "title", "alt"):
        if node.has_attr(attr):
            return str(node[attr]).strip()

    text = _text(node)
    if text:
        return text

    for attr in ("alt", "title", "content"):
        inner = node.select_one(f"[{attr}]")
        if inner is not None:
            value = str(inner[attr]).strip()
            if value:
                return value
    return ""


def _looks_empty(page):
    try:
        body = page.inner_text("body", timeout=5000).lower()
    except Exception:
        return False
    return any(marker in body for marker in EMPTY_MARKERS)


def _extract_detail_description(soup):
    """Ambil blok deskripsi terbesar sebagai fallback saat selector kosong."""
    if soup is None:
        return ""
    for sel in (
        "[class*='description' i]",
        "[class*='deskripsi' i]",
        "[id*='description' i]",
        "[data-testid*='description' i]",
    ):
        node = soup.select_one(sel)
        text = _text(node)
        if len(text) > 120:
            return text

    heading = soup.find(
        re.compile("^h[1-6]$"), string=re.compile(r"deskripsi|description", re.I)
    )
    if heading:
        block = heading.find_parent("div") or heading.parent
        text = _text(block)
        if len(text) > 120:
            return text

    main = soup.find("main") or soup.body
    if main:
        blocks = [_text(el) for el in main.find_all("div")]
        blocks = [b for b in blocks if len(b) > 400]
        if blocks:
            return max(blocks, key=len)
    return _text(main)


def _collect_cards(page, source_name):
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    item_selector = (source_name.get("item_selector") or "").strip()
    if not item_selector:
        cards = []
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            # Heuristik sederhana mencari link lowongan
            if any(k in href for k in ("job", "career", "lowongan", "vacancy", "detail", "opportunity", "role")):
                cards.append(a)
        if not cards:
            cards = soup.find_all("a", href=True)
        return cards[:50], soup

    try:
        cards = soup.select(item_selector)
    except Exception as e:
        log.warning("[%s] item_selector tidak valid (%s): %s",
                    source_name.get("name"), item_selector, e)
        cards = []
    return cards, soup


def _build_job(card, source, base_url, context):
    """Susun dict lowongan dari satu kartu. Return None bila tidak lengkap."""
    name = source.get("name") or "Sumber"

    title_node = _pick(card, source.get("title_selector"))
    title = _text(title_node)
    if not title:
        # Fallback heuristik: text dari elemen itu sendiri
        title = _text(card)
        if not title:
            return None

    url_node = _pick(card, source.get("url_selector")) or title_node
    if not url_node:
        url_node = card
    
    href = _href_of(card, url_node)
    if not href and card.name == "a":
        href = card.get("href")
    
    if not href:
        return None
    job_url = resolve_url(href.strip(), base_url)

    company_node = _pick(card, source.get("company_selector"))
    company = _attribute_value(company_node, "alt")

    location_node = _pick(card, source.get("location_selector"))
    location = _text(location_node) or "Indonesia"

    desc_node = _pick(card, source.get("desc_selector"))
    description = _text(desc_node)

    salary = None
    job_type = None
    contact_info = None
    card_text = _text(card)

    if source.get("fetch_detail", True) and not description:
        detail_soup = fetch_detail_soup(
            context, job_url, timeout=DETAIL_TIMEOUT_MS, delay=short_delay
        )
        if detail_soup:
            description = _extract_detail_description(detail_soup)
            haystack = description or _text(detail_soup)
            salary = extract_salary(haystack)
            job_type = extract_job_type(haystack)
            contact_info = extract_contact(haystack)

            if location == "Indonesia" and not location_node:
                loc_detail = detail_soup.select_one("[class*='ocation']")
                location = _text(loc_detail) or "Indonesia"

    # Detail gagal dimuat atau selector deskripsi kosong: pakai teks kartu.
    if not description:
        description = card_text
    if salary is None:
        salary = extract_salary(description or card_text)
    if job_type is None:
        job_type = extract_job_type(description or card_text)
    if contact_info is None:
        contact_info = extract_contact(description or card_text)

    return {
        "title": title,
        "company": company,
        "location": location,
        "type": job_type or "Full-time",
        "salary": salary,
        "url": job_url,
        "description": description,
        "skills": extract_skills(description),
        "contact_info": contact_info,
    }


def scrape_generic(source, keyword="software engineer", max_jobs=None, max_pages=None):
    """Scrape sumber lowongan berdasarkan konfigurasi selector di tabel job_sources.

    `source` adalah baris dari job_sources: minimal butuh name, url_template,
    item_selector, title_selector dan url_selector.
    """
    name = source.get("name") or "Sumber"
    limit = int(max_jobs or source.get("max_jobs") or 25)
    pages = int(max_pages or source.get("max_pages") or 1)

    start_url = build_url(source.get("url_template"), keyword)
    if not start_url:
        log.warning("[%s] url_template kosong, scraping dilewati", name)
        return []

    item_selector = (source.get("item_selector") or "").strip()
    wait_selector = item_selector or (source.get("url_selector") or "body")
    next_selector = (source.get("next_page_selector") or "").strip()

    jobs = []
    seen_urls = set()
    playwright = browser = None

    try:
        playwright, browser, context = get_browser()
        page = context.new_page()

        if not goto_with_retry(page, start_url):
            log.warning("[%s] Gagal memuat %s", name, start_url)
            return []

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector(wait_selector, timeout=20000)
        except Exception:
            log.warning("[%s] Selector '%s' tidak muncul di %s", name, wait_selector, start_url)

        if _looks_empty(page):
            log.info("[%s] Halaman '%s' tidak memuat lowongan apa pun", name, keyword)
            return []

        base_url = "{0.scheme}://{0.netloc}".format(urlparse(start_url))

        for page_no in range(1, pages + 1):
            if page_no > 1:
                try:
                    page.wait_for_selector(next_selector, timeout=15000)
                    page.click(next_selector)
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                    human_delay()
                    jitter_scroll(page)
                    human_delay()
                except Exception as e:
                    log.info("[%s] Halaman %d tidak dilanjutkan: %s", name, page_no, e)
                    break

            cards, _ = _collect_cards(page, source)
            log.info("[%s] Halaman %d: %d kartu ditemukan", name, page_no, len(cards))

            for card in cards:
                if len(jobs) >= limit:
                    break
                try:
                    job = _build_job(card, source, base_url, context)
                except Exception as e:
                    log.debug("[%s] Gagal proses kartu: %s", name, e)
                    continue
                if not job or job["url"] in seen_urls:
                    continue
                seen_urls.add(job["url"])
                jobs.append(job)

            if len(jobs) >= limit:
                break

            if not next_selector or page_no >= pages:
                break

    except Exception as e:
        log.error("[%s] Generic scraper gagal: %s", name, e)
    finally:
        close_browser(playwright, browser)

    log.info("[%s] Keyword '%s' menghasilkan %d lowongan", name, keyword, len(jobs))
    return jobs
