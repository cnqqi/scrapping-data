# Job Scraper

Proyek ini adalah scraper lowongan kerja yang mengumpulkan data dari LinkedIn, JobStreet, Glints, Kalibrr, Indeed, RemoteOK, dan Remotive, membersihkannya, lalu menyimpannya ke database Supabase.

## Fitur

- Scraping lowongan dari **LinkedIn**, **JobStreet**, **Glints**, **Kalibrr**, dan **Indeed** (Playwright) serta **RemoteOK** & **Remotive** (API publik)
- Multi-keyword scraping (daftar di `run.py`)
- Automasi browser menggunakan Playwright
- Pembersihan dan normalisasi data sebelum disimpan
- Ekstraksi otomatis skill, tipe kerja, gaji, dan kontak dari deskripsi
- Penyimpanan data ke Supabase dengan mekanisme upsert
- Penjadwalan scraping setiap 24 jam, atau mode `--once` untuk cron/CI

## Setup

1. Clone repository ini
2. Buat virtual environment (Python 3.10+):

    python -m venv venv
    venv\Scripts\activate

3. Install dependensi:

    pip install -r requirements.txt

4. Instal browser untuk Playwright:

    playwright install chromium

5. Salin file `.env.example` menjadi `.env`, lalu isi kredensial Supabase:

    cp .env.example .env

    SUPABASE_URL=your_supabase_url
    SUPABASE_ANON_KEY=your_supabase_anon_key

6. Jalankan scraper (sekali jalan lalu keluar, cocok untuk cron/CI):

    python run.py --once

   Atau jalankan sebagai service berjalan terus (scrape tiap 24 jam):

    python run.py

## Struktur Modul

- `run.py` - Entry point, multi-keyword, menjadwalkan scraping dan menyimpan data
- `linkedin.py` - Scraping lowongan dari LinkedIn
- `jobstreet.py` - Scraping lowongan dari JobStreet
- `glints.py` - Scraping lowongan dari Glints
- `kalibrr.py` - Scraping lowongan dari Kalibrr
- `indeed.py` - Scraping lowongan dari Indeed
- `remote.py` - Lowongan remote dari API RemoteOK & Remotive
- `browser.py` - Konfigurasi Playwright (Chromium headless)
- `base.py` - Helper delay, scroll, dan retry navigasi
- `extract.py` - Ekstraksi gaji, tipe kerja, dan kontak dari deskripsi
- `normalize.py` - Normalisasi format data sebelum disimpan
- `cleaner.py` - Validasi dan pembersihan data yang tidak valid
- `supabase_client.py` - Koneksi ke Supabase
- `skills_keyword.py` - Daftar keyword untuk ekstraksi skill
- `schema.sql` - Skema tabel `jobs` di Supabase

## Database

Jalankan `schema.sql` di Supabase untuk membuat tabel `jobs`, atau pastikan sudah ada dengan skema berikut:

- `title`
- `company`
- `location`
- `type` (Full-time / Part-time / Contract / Internship)
- `salary`
- `description`
- `skills` (jsonb)
- `contact_info`
- `url`
- `source`
- `is_active`

Kolom `url` bersifat unik dan digunakan sebagai konflik untuk upsert.

## Deployment

### GitHub Actions (gratis, untuk demo skripsi)

Jalankan scraping setiap 24 jam lewat cron workflow, contoh `.github/workflows/scrape.yml`:

```yaml
name: scrape
on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m playwright install --with-deps chromium
      - run: python run.py --once
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
```

Atur `SUPABASE_URL` dan `SUPABASE_ANON_KEY` di *Settings → Secrets and variables → Actions*. Alternatif lain: Railway/Render (cron bawaan) atau VPS murah.
