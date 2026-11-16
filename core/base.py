import logging
import random
import time
from contextlib import contextmanager
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.browser import get_browser

log = logging.getLogger(__name__)


def human_delay(min_sec=2, max_sec=6):
    time.sleep(random.uniform(min_sec, max_sec))


def short_delay(min_sec=1, max_sec=2):
    time.sleep(random.uniform(min_sec, max_sec))


def jitter_scroll(page):
    page.evaluate("""
        window.scrollTo(0, document.body.scrollHeight / 2);
    """)


def goto_with_retry(page, url, timeout=45000, attempts=3):
    for i in range(attempts):
        try:
            page.goto(url, wait_until="commit", timeout=timeout)
            return True
        except Exception as e:
            if "ERR_NAME_NOT_RESOLVED" in str(e) or "ERR_CONNECTION" in str(e):
                time.sleep(2 * (i + 1))
                continue
            raise
    return False


def close_browser(p, browser):
    try:
        browser.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass


def resolve_url(href, base_url):
    """Ubah href menjadi URL absolut dan buang query yang tidak perlu."""
    if href.startswith("http"):
        return href.split("?")[0]
    return urljoin(base_url, href.split("?")[0])


@contextmanager
def listing_page(page_url, wait_selector, source, wait_timeout=30000):
    """Buka halaman daftar lowongan dengan siklus hidup browser standar.

    yield (page, context) saat berhasil, atau None bila gagal memuat.
    Browser selalu ditutup otomatis.
    """
    p, browser, context = get_browser()
    page = context.new_page()

    try:
        if not goto_with_retry(page, page_url):
            log.warning("[%s] Gagal memuat halaman pencarian: %s", source, page_url)
            yield None
            return

        human_delay()
        jitter_scroll(page)
        human_delay()

        try:
            page.wait_for_selector(wait_selector, timeout=wait_timeout)
        except Exception:
            log.warning("[%s] Kartu lowongan tidak muncul untuk halaman ini", source)

        yield (page, context)
    finally:
        close_browser(p, browser)


def fetch_detail_soup(context, url, timeout=15000, delay=None):
    """Buka halaman detail lowongan, kembali BeautifulSoup (atau None saat gagal)."""
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        if delay:
            delay()
        return BeautifulSoup(page.content(), "html.parser")
    except Exception:
        return None
    finally:
        try:
            page.close()
        except Exception:
            pass