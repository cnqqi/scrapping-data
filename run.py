import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import partial

import schedule

from core.cleaner import clean_job_detail
from core.generic_scraper import scrape_generic
from core.normalize import normalize
from core.pipeline_view import fail, hr, ok, stage, step, sub, summary, title, warn
from db.cleanup import purge_old_jobs
from db.sources import ensure_seeded, list_keywords, list_sources, seed_defaults
from db.supabase_client import supabase
from scrapers.glints import scrape_glints
from scrapers.indeed import scrape_indeed
from scrapers.jobstreet import scrape_jobstreet
from scrapers.kalibrr import scrape_kalibrr
from scrapers.linkedin import scrape_linkedin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
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


SOURCES = [
    (scrape_linkedin, "LinkedIn"),
    (scrape_jobstreet, "JobStreet"),
    (scrape_glints, "Glints"),
    (scrape_kalibrr, "Kalibrr"),
    (scrape_indeed, "Indeed"),
]

# Pemetaan scraper_key -> fungsi scraper bawaan. Sumber dengan kunci di luar
# peta ini memakai core/generic_scraper.py (URL template + CSS selector).
SCRAPER_REGISTRY = {
    "linkedin": scrape_linkedin,
    "jobstreet": scrape_jobstreet,
    "glints": scrape_glints,
    "kalibrr": scrape_kalibrr,
    "indeed": scrape_indeed,
}

# Loker yang berumur lebih dari ini (hari) dihapus permanen dari Supabase.
PURGE_MAX_AGE_DAYS = 90  # 3 bulan

# URL yang sudah diproses pada siklus run ini — mencegah loker yang sama
# (muncul berulang karena keyword berebeda) discraping/disimpan dua kali.
DONE_URLS: set[str] = set()


def load_keywords():
    """Keyword aktif dari tabel job_keywords; jatuh ke KEYWORDS bila tabel kosong."""
    try:
        rows = list_keywords(only_enabled=True)
    except Exception as e:
        log.warning("Gagal baca job_keywords, pakai daftar bawaan: %s", e)
        return list(KEYWORDS)

    keywords = [(r.get("keyword") or "").strip() for r in rows]
    keywords = [k for k in keywords if k]
    return keywords or list(KEYWORDS)


def load_sources():
    """Sumber aktif dari tabel job_sources sebagai list (scraper, nama).

    Bentuknya sama dengan SOURCES bawaan supaya main() tidak berubah struktur.
    Sumber kustom dibungkus scraper_generic yang dikonfigurasi per baris.
    """
    try:
        rows = list_sources(only_enabled=True)
    except Exception as e:
        log.warning("Gagal baca job_sources, pakai daftar bawaan: %s", e)
        return list(SOURCES)

    pairs = []
    for row in rows:
        key = (row.get("scraper_key") or "").strip()
        name = (row.get("name") or key).strip()
        if not key and not name:
            continue
        builtin = SCRAPER_REGISTRY.get(key)
        pairs.append((builtin, name) if builtin
                     else (partial(scrape_generic, row), name))
    return pairs or list(SOURCES)


def push(jobs, source):
    text = f"Sumber: {source} | {len(jobs)} lowongan mentah"
    stage("3", "BERSIHKAN & NORMALISASI", text)

    batch = []
    invalid = 0
    dup = 0
    seen_before = 0
    reasons = {}

    for job in jobs:
        cleaned, reason = clean_job_detail(job)
        if not cleaned:
            invalid += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            continue

        url = cleaned["url"]
        if url in DONE_URLS:
            seen_before += 1
            continue
        DONE_URLS.add(url)

        batch.append(normalize(cleaned, source))

    # Wilayah prioritas (Jawa Tengah / Solo Raya / Yogyakarta) diurutkan lebih dulu.
    batch.sort(key=lambda r: r.get("priority", 1))
    priority_cnt = sum(1 for r in batch if r.get("priority") == 0)

    kept = len(batch)

    # ── validasi ──
    line = f"clean_job (cleaner.py): {len(jobs)} mentah -> {len(jobs) - invalid} valid ({invalid} dibuang)"
    step(line)
    if reasons:
        step("Alasan dibuang oleh clean_job:")
        for reason, cnt in sorted(reasons.items(), key=lambda item: -item[1]):
            sub(f"{reason} : {cnt} baris")
    line = f"dedupe URL dalam batch: {len(jobs) - invalid} -> {kept} unik ({dup} duplikat dibuang)"
    step(line)
    line = f"duplikat lintas batch (sudah diproses di run ini, dilewati): {seen_before} baris"
    step(line)

    # ── hasil normalisasi tiap baris ──
    step("Normalisasi per baris (normalize.py):")
    row_limit = 10
    for i, row in enumerate(batch[:row_limit], 1):
        title_s = (row["title"] or "")[:32]
        company_s = (row["company"] or "")[:18]
        loc_s = (row["location"] or "")[:12]
        skills_s = ", ".join(row["skills"][:4]) if row["skills"] else "-"
        sub(f"[{i:>3}] {title_s:<32} | {company_s:<18} | {loc_s:<12} | skill: {skills_s[:24]}")
    if len(batch) > row_limit:
        sub(f"... +{len(batch) - row_limit} baris lainnya tidak ditampilkan")

    # ── statistik normalisasi ──
    default_loc = sum(1 for r in batch if r["location"] == "Indonesia")
    default_type = sum(1 for r in batch if r["type"] == "Full-time")
    total_skills = sum(len(r.get("skills") or []) for r in batch)
    step("Statistik hasil normalisasi:")
    sub(f"lokasi jatuh ke default 'Indonesia' : {default_loc} baris")
    sub(f"prioritas Jateng/Solo Raya/DIY       : {priority_cnt} baris (diurutkan lebih dulu)")
    sub(f"tipe jatuh ke default 'Full-time'    : {default_type} baris")
    sub(f"total skill terdeteksi               : {total_skills}")

    ok(f"{kept} lowongan valid dinormalisasi")

    stage("4", "SIMPAN KE SUPABASE",
          f"Tabel: jobs | Konflik: url | Batch: {kept} baris")

    if not batch:
        warn("Tidak ada data untuk disimpan, upsert dilewati")
        return 0

    try:
        step("Mengirim upsert ke Supabase...")
        supabase.table("jobs") \
            .upsert(batch, on_conflict="url") \
            .execute()
    except Exception as e:
        fail(f"Upsert gagal ({source}): {e}")
        log.error("[Supabase] Upsert gagal (%s): %s", source, e)
        return 0

    ok(f"{kept} baris berhasil dimasukkan/diperbarui di tabel jobs")
    return kept


def scrape_source(scraper, source, keyword, note=""):
    detail = f"Sumber: {source} | Keyword: '{keyword}'"
    if note:
        detail += f" | {note}"

    stage("2", "SCRAPING", detail)
    step("Membuka browser Playwright dan menjalankan scraper...")

    try:
        jobs = scraper(keyword)
    except Exception as e:
        fail(f"Scraping gagal ({source}): {e}")
        log.error("[%s] Scraping gagal (keyword=%s): %s", source, keyword, e)
        return 0, 0

    ok(f"{len(jobs)} lowongan mentah terkumpul dari {source}")

    inserted = push(jobs, source)
    log.info("[%s] %s: %d ditemukan, %d dimasukkan", source, keyword, len(jobs), inserted)
    return len(jobs), inserted


def main():
    title("JOB SCRAPER  |  PENGUMPULAN DATA LOWONGAN KERJA")

    DONE_URLS.clear()
    ensure_seeded()

    keywords = load_keywords()
    sources = load_sources()

    total_combos = len(keywords) * len(sources)
    stage("1", "PERSIAPAN PENGUMPULAN DATA",
          f"{len(keywords)} keyword | {len(sources)} sumber | {total_combos} pencarian")
    step(f"Keyword : {len(keywords)}, contoh pertama: {', '.join(keywords[:5])}, ...")
    step(f"Sumber  : {', '.join(src for _, src in sources)}")
    step(f"Total   : {len(keywords)} keyword x {len(sources)} sumber = {total_combos} pencarian")
    step("Referensi diambil dari tabel job_sources & job_keywords (Supabase)")
    step("Database: tabel 'jobs' di Supabase (upsert berdasarkan kolom url)")
    step("Browser : Playwright (Chromium)")
    step("Cara menghentikan: tekan Ctrl+C di terminal ini kapan saja.")
    ok("Persiapan selesai, mulai pengumpulan data...")

    totals = {"found": 0, "inserted": 0}
    per_source = {}
    combo = 0

    for keyword in keywords:
        for scraper, source in sources:
            combo += 1
            found, inserted = scrape_source(
                scraper, source, keyword, note=f"{combo}/{total_combos}")
            totals["found"] += found
            totals["inserted"] += inserted

            src = per_source.setdefault(source, {"found": 0, "inserted": 0})
            src["found"] += found
            src["inserted"] += inserted

    hr()
    summary([(src, d["found"], d["inserted"]) for src, d in per_source.items()])

    cleanup_old_jobs(PURGE_MAX_AGE_DAYS)


def cleanup_old_jobs(max_age_days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stage("5", "PEMBERSIHAN LOKER LAMA (HARD DELETE)",
          f"Supabase: jobs | umur > {max_age_days} hari | cutoff {cutoff:%Y-%m-%d}")
    step(f"Menghapus permanen baris dengan created_at < {cutoff:%Y-%m-%d}...")
    removed = purge_old_jobs(max_age_days)
    if removed:
        ok(f"{removed} loker lama berhasil dihapus permanen.")
    else:
        ok(f"Tidak ada loker yang berumur lebih dari {max_age_days} hari.")


running = True


def shutdown(signum, frame):
    global running
    log.info("Ctrl+C ditekan. Menghentikan scraper...")
    running = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper LinkedIn, JobStreet, Glints, Kalibrr & Indeed")
    parser.add_argument("--once", action="store_true",
                        help="Jalankan sekali lalu keluar (untuk cron/CI)")
    parser.add_argument("--seed", action="store_true",
                        help="Isi tabel job_sources & job_keywords dengan data bawaan lalu keluar")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.seed:
        try:
            created = seed_defaults()
        except Exception as e:
            fail(f"Tabel job_sources/job_keywords belum dibuat di Supabase: {e}")
            sys.exit(1)
        if created["sources"] or created["keywords"]:
            ok(f"Data bawaan ditambahkan: {created['sources']} sumber, "
               f"{created['keywords']} keyword.")
        else:
            ok("Tabel referensi sudah berisi data, tidak ada yang ditambahkan.")
        sys.exit(0)

    main()  # jalankan langsung saat pertama kali start

    if args.once:
        sys.exit(0)

    schedule.every(24).hours.do(main)
    print()
    step("Scraper berjalan terus! Pengumpulan data diulang setiap 24 jam.")
    step("Cara menghentikan: tekan Ctrl+C di terminal ini.")
    log.info("Job scraper berjalan setiap 24 jam; tekan Ctrl+C untuk menghentikan.")

    while running:
        schedule.run_pending()
        time.sleep(60)

    print()
    ok("Scraper dihentikan. Sampai jumpa!")
    sys.exit(0)