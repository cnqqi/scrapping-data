import argparse
import logging
import signal
import sys
import time

import schedule

from cleaner import clean_job
from glints import scrape_glints
from indeed import scrape_indeed
from jobstreet import scrape_jobstreet
from kalibrr import scrape_kalibrr
from linkedin import scrape_linkedin
from normalize import normalize
from remote import scrape_remoteok, scrape_remotive
from supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scraper")

KEYWORDS = [
    "software engineer",
    "backend developer",
    "frontend developer",
    "full stack developer",
    "data scientist",
    "data analyst",
    "devops engineer",
    "cloud engineer",
    "ui ux designer",
    "graphic designer",
    "multimedia designer",
    "video editor",
    "motion graphic designer",
    "animator",
    "3d artist",
    "content creator",
    "mobile developer",

    "react developer",
    "vue.js developer",
    "angular developer",
    "next.js developer",
    "node.js developer",
    "python developer",
    "java developer",
    "golang developer",
    "php developer",
    "laravel developer",
    "django developer",
    "spring boot developer",
    "flutter developer",
    "react native developer",
    "android developer",
    "ios developer",
    "kubernetes engineer",
    "database administrator",
    "machine learning engineer",
]


def push(jobs, source):
    batch = []
    seen = set()

    for job in jobs:
        job = clean_job(job)
        if not job:
            continue

        url = job["url"]
        if url in seen:
            continue
        seen.add(url)

        batch.append(normalize(job, source))

    if not batch:
        return 0

    try:
        supabase.table("jobs") \
            .upsert(batch, on_conflict="url") \
            .execute()
    except Exception as e:
        log.error("[Supabase] Upsert gagal (%s): %s", source, e)
        return 0

    return len(batch)


def scrape_source(scraper, source, keyword):
    try:
        jobs = scraper(keyword)
    except Exception as e:
        log.error("[%s] Scraping gagal (keyword=%s): %s", source, keyword, e)
        return

    inserted = push(jobs, source)
    log.info("[%s] %s: %d ditemukan, %d dimasukkan", source, keyword, len(jobs), inserted)


def main():
    for keyword in KEYWORDS:
        scrape_source(scrape_linkedin, "LinkedIn", keyword)
        scrape_source(scrape_jobstreet, "JobStreet", keyword)
        scrape_source(scrape_glints, "Glints", keyword)
        scrape_source(scrape_kalibrr, "Kalibrr", keyword)
        scrape_source(scrape_indeed, "Indeed", keyword)
        scrape_source(scrape_remoteok, "RemoteOK", keyword)
        scrape_source(scrape_remotive, "Remotive", keyword)


running = True


def shutdown(signum, frame):
    global running
    log.info("Ctrl+C ditekan. Menghentikan scraper...")
    running = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper LinkedIn, JobStreet, Glints, Kalibrr, Indeed, RemoteOK & Remotive")
    parser.add_argument("--once", action="store_true",
                        help="Jalankan sekali lalu keluar (untuk cron/CI)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    main()  # jalankan langsung saat pertama kali start

    if args.once:
        sys.exit(0)

    schedule.every(24).hours.do(main)
    log.info("Job scraper berjalan setiap 24 jam...")
    log.info("Tekan Ctrl+C untuk menghentikan.")

    while running:
        schedule.run_pending()
        time.sleep(60)

    log.info("Scraper dihentikan. Sampai jumpa!")
    sys.exit(0)