import random
import time


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