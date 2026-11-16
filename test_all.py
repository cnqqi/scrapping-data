"""
Test suite manual (7 test) untuk memverifikasi semua komponen sebelum scraping penuh.
Jalankan: python test_all.py
"""

import sys
import traceback


def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def ok(msg):
    print(f"  [OK] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


# ─────────────────────────────────────────────
# TEST 1: cleaner
# ─────────────────────────────────────────────
section("TEST 1: cleaner.py")

try:
    from core.cleaner import clean_job

    # valid
    result = clean_job({"company": "  Google  ", "title": "  Software Engineer  ", "url": "  https://example.com  ", "location": "  Jakarta  ", "description": "  Need Python  ", "skills": ["python", "react"]})
    assert result is not None, "Harus lolos validasi"
    assert result["company"] == "Google", f"company harus di-strip, dapat: {result['company']}"
    assert result["title"] == "Software Engineer", f"title harus di-strip, dapat: {result['title']}"
    assert result["url"] == "https://example.com", f"url harus di-strip, dapat: {result['url']}"
    assert result["location"] == "Jakarta", f"location harus di-strip, dapat: {result['location']}"
    assert result["description"] == "Need Python", f"description harus di-strip, dapat: {result['description']}"
    assert result["skills"] == ["python", "react"], f"skills harus dipertahankan, dapat: {result['skills']}"
    ok("clean_job mengembalikan dict yang sudah di-strip dengan semua field")

    # valid tanpa location/description/skills — harus ada default
    result2 = clean_job({"company": "Google", "title": "Software Engineer", "url": "https://example.com"})
    assert result2["location"] == "Indonesia", f"location default Indonesia, dapat: {result2['location']}"
    assert result2["description"] == "", f"description default kosong, dapat: {result2['description']}"
    assert result2["skills"] == [], f"skills default [], dapat: {result2['skills']}"
    ok("clean_job memberikan default untuk location, description, skills")

    # company terlalu pendek
    assert clean_job({"company": "A", "title": "Software Engineer", "url": "https://x.com"}) is None
    ok("Menolak company < 2 karakter")

    # title terlalu pendek
    assert clean_job({"company": "Google", "title": "Dev", "url": "https://x.com"}) is None
    ok("Menolak title < 5 karakter")

    # URL tidak valid
    assert clean_job({"company": "Google", "title": "Software Engineer", "url": "/relative/path"}) is None
    ok("Menolak URL yang tidak diawali http")

    # field kosong
    assert clean_job({"company": "", "title": "Software Engineer", "url": "https://x.com"}) is None
    ok("Menolak company kosong")

    assert clean_job({"company": "Google", "title": "", "url": "https://x.com"}) is None
    ok("Menolak title kosong")

    assert clean_job({"company": "Google", "title": "Software Engineer", "url": ""}) is None
    ok("Menolak url kosong")

    # lokasi luar negeri — harus ditolak
    assert clean_job({"company": "Google", "title": "Software Engineer",
                      "url": "https://x.com", "location": "Singapore"}) is None
    assert clean_job({"company": "Google", "title": "Software Engineer",
                      "url": "https://x.com", "location": "Kuala Lumpur, Malaysia"}) is None
    assert clean_job({"company": "Google", "title": "Software Engineer",
                      "url": "https://x.com", "location": "Luar Negeri"}) is None
    ok("Menolak lokasi luar negeri / remote antarnegara")

except Exception as e:
    fail(f"cleaner.py error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 2: skills_keyword
# ─────────────────────────────────────────────
section("TEST 2: skills_keyword.py")

try:
    from core.skills_keyword import extract_skills

    desc = "We need a developer proficient in Python, JavaScript, React, and PostgreSQL. Experience with Docker and AWS is a plus."
    skills = extract_skills(desc)
    assert "python" in skills, f"Harus detect python, dapat: {skills}"
    assert "javascript" in skills, f"Harus detect javascript, dapat: {skills}"
    assert "react" in skills, f"Harus detect react, dapat: {skills}"
    assert "postgresql" in skills, f"Harus detect postgresql, dapat: {skills}"
    assert "docker" in skills, f"Harus detect docker, dapat: {skills}"
    assert "aws" in skills, f"Harus detect aws, dapat: {skills}"
    ok(f"extract_skills menemukan {len(skills)} skill: {skills}")

    # Empty text
    assert extract_skills("") == []
    ok("extract_skills mengembalikan [] untuk teks kosong")

    # No matching skills
    assert extract_skills("we need a fast learner") == []
    ok("extract_skills mengembalikan [] untuk teks tanpa skill")

except Exception as e:
    fail(f"skills_keyword.py error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 3: normalize
# ─────────────────────────────────────────────
section("TEST 3: normalize.py")

try:
    from core.normalize import normalize

    job = {"company": "Google", "title": "Software Engineer", "url": "https://example.com", "location": "Jakarta", "description": "Need Python and React skills", "skills": ["python", "react"]}
    row = normalize(job, "LinkedIn")

    assert row["company"] == "Google", f"Dapat: {row['company']}"
    assert row["title"] == "Software Engineer", f"Dapat: {row['title']}"
    assert row["url"] == "https://example.com", f"Dapat: {row['url']}"
    assert row["source"] == "LinkedIn", f"Dapat: {row['source']}"
    assert row["is_active"] is True, f"Dapat: {row['is_active']}"
    assert row["location"] == "Jakarta", f"Dapat: {row['location']}"
    assert row["priority"] == 1, f"Jakarta bukan prioritas, dapat: {row['priority']}"
    assert row["description"] == "Need Python and React skills", f"Dapat: {row['description']}"
    assert row["skills"] == ["python", "react"], f"Dapat: {row['skills']}"
    ok("normalize menghasilkan dict dengan semua kolom yang benar")

    # Fallback description when not provided
    job2 = {"company": "Google", "title": "Software Engineer", "url": "https://example.com"}
    row2 = normalize(job2, "JobStreet")
    assert row2["description"] == "Software Engineer", "Fallback ke title jika description kosong"
    ok("normalize fallback ke title saat description tidak ada")

    # Prioritas wilayah: Jateng / Solo Raya / DIY -> priority=0
    for loc in ["Semarang, Jawa Tengah", "Solo, Indonesia", "Surakarta (Solo)",
                "Klaten, Jawa Tengah", "Yogyakarta, Indonesia", "Sleman, DIY"]:
        row3 = normalize({"company": "X", "title": "Full Stack Developer", "url": "https://x.com", "location": loc}, "Indeed")
        assert row3["priority"] == 0, f"{loc} harus prioritas 0, dapat: {row3['priority']}"
    ok("Wilayah Jawa Tengah / Solo Raya / Yogyakarta diberi priority=0")

except Exception as e:
    fail(f"normalize.py error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 4: location.py
# ─────────────────────────────────────────────
section("TEST 4: location.py (filter luar negeri & prioritas)")

try:
    from core.location import is_foreign, priority_rank

    # Luar negeri
    assert is_foreign("Singapore"), "Singapore harus ditolak"
    assert is_foreign("Kuala Lumpur, Malaysia"), "Malaysia harus ditolak"
    assert is_foreign("Thailand"), "Thailand harus ditolak"
    assert is_foreign("Luar Negeri"), "Luar Negeri harus ditolak"
    assert is_foreign("Remote Worldwide"), "Remote antarnegara harus ditolak"
    # Indonesia
    assert not is_foreign("Jakarta"), "Jakarta bukan luar negeri"
    assert not is_foreign("Yogyakarta"), "Yogyakarta bukan luar negeri"
    assert not is_foreign(""), "Lokasi kosong/jatuh default Indonesia bukan luar negeri"
    ok("is_foreign membedakan luar negeri vs Indonesia dengan benar")

    # Prioritas
    assert priority_rank("Semarang, Jawa Tengah") == 0, "Semarang harus prioritas"
    assert priority_rank("Solo, Indonesia") == 0, "Solo harus prioritas"
    assert priority_rank("Surakarta") == 0, "Surakarta harus prioritas"
    assert priority_rank("Klaten, Jawa Tengah") == 0, "Klaten harus prioritas"
    assert priority_rank("Yogyakarta") == 0, "Yogyakarta harus prioritas"
    assert priority_rank("Sleman") == 0, "Sleman harus prioritas"
    assert priority_rank("Jakarta") == 1, "Jakarta tetap Indonesia tapi bukan prioritas"
    assert priority_rank("Surabaya") == 1, "Surabaya tetap masuk tapi bukan prioritas"
    assert priority_rank("Indonesia") == 1, "Default Indonesia bukan prioritas"
    ok("priority_rank menandai Jateng/Solo Raya/DIY = 0, lainnya Indonesia = 1")

except Exception as e:
    fail(f"location.py error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 5: supabase_client
# ─────────────────────────────────────────────
section("TEST 5: supabase_client.py (koneksi)")

try:
    from db.supabase_client import supabase

    # Coba query sederhana — hanya mengecek koneksi, bukan data
    result = supabase.table("jobs").select("id").limit(1).execute()
    ok(f"Koneksi Supabase berhasil. Baris tersedia: {len(result.data)}")

except Exception as e:
    fail(f"Koneksi Supabase gagal: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 6: push (pipeline lengkap tanpa scraping)
# ─────────────────────────────────────────────
section("TEST 6: push() pipeline (mock data)")

try:
    from run import push

    mock_jobs = [
        {"company": "Test Company", "title": "Backend Developer", "url": "https://test.example.com/job/1"},
        {"company": "  Spasi Inc  ", "title": "  Frontend Dev Test  ", "url": "  https://test.example.com/job/2  "},
        # data invalid — harus dibuang
        {"company": "X", "title": "Dev", "url": "/relative"},
        {"company": "", "title": "Backend Developer", "url": "https://test.example.com/job/3"},
        # duplikat URL
        {"company": "Test Company", "title": "Backend Developer", "url": "https://test.example.com/job/1"},
    ]

    inserted = push(mock_jobs, "TestSource")
    assert inserted == 2, f"Harus 2 yang valid & unik, dapat: {inserted}"
    ok(f"push() memasukkan {inserted} baris (duplikat & invalid dibuang dengan benar)")

except Exception as e:
    fail(f"push() error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 7: browser
# ─────────────────────────────────────────────
section("TEST 7: browser.py (Playwright launch)")

try:
    from core.browser import get_browser

    p, browser, context = get_browser()
    page = context.new_page()
    page.goto("about:blank")
    assert page.title() == ""
    browser.close()
    p.stop()
    ok("Browser Playwright berhasil diluncurkan dan ditutup")

except Exception as e:
    fail(f"browser.py error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# TEST 8: referensi loker (generic scraper + validasi db)
# ─────────────────────────────────────────────
section("TEST 8: referensi loker (generic scraper & db/sources.py)")

try:
    from bs4 import BeautifulSoup
    from werkzeug.datastructures import MultiDict

    from core.generic_scraper import _build_job, _pick, _text, build_url
    from db.sources import (
        _clean,
        _flag,
        _sanitize_source,
        SOURCE_BOOL_FIELDS,
        SOURCE_INT_FIELDS,
        SOURCE_TEXT_FIELDS,
    )

    # Template URL
    assert build_url("https://x.com/jobs?q={keyword}", "data analyst") == \
        "https://x.com/jobs?q=data+analyst", "keyword harus di-URL-encode"
    assert build_url("https://x.com/jobs?q={keyword_raw}", "data analyst") == \
        "https://x.com/jobs?q=data analyst", "keyword_raw harus apa adanya"
    assert build_url("https://x.com/jobs", "php") == "https://x.com/jobs", \
        "template tanpa placeholder tidak boleh diubah"
    ok("build_url mengganti {keyword} dan {keyword_raw} dengan benar")

    # Seleksi elemen lowongan
    html = """
    <div class="job-card">
      <h2><a href="/lowongan/backend">Backend Engineer</a></h2>
      <span class="company"><img alt="PT Kopi Nusantara"></span>
      <span class="city">Semarang, Jawa Tengah</span>
      <div class="desc">Full-time engineer dengan PHP Laravel. Gaji Rp 8 juta.</div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    card = soup.select_one("div.job-card")
    assert _text(_pick(card, "h2 a")) == "Backend Engineer", "title selector gagal"
    assert _pick(card, "attr:data-id") is None, "attr: harus None bila atribut tidak ada"
    ok("_pick memilih elemen lewat CSS selector maupun prefix attr:")

    source = {
        "name": "Uji", "item_selector": "div.job-card", "title_selector": "h2 a",
        "url_selector": "h2 a", "company_selector": ".company",
        "location_selector": "span.city", "desc_selector": "div.desc",
        "fetch_detail": False,
    }
    job = _build_job(card, source, "https://x.com", None)
    assert job["title"] == "Backend Engineer", job
    assert job["company"] == "PT Kopi Nusantara", f"company dari <img alt>, dapat: {job['company']}"
    assert job["location"] == "Semarang, Jawa Tengah", job
    assert job["url"] == "https://x.com/lowongan/backend", f"url harus absolut, dapat: {job['url']}"
    assert job["description"].startswith("Full-time engineer"), job["description"]
    assert "php" in job["skills"] and "laravel" in job["skills"], job["skills"]
    ok("_build_job menyusun dict lowongan lengkap dari selector")

    # Deskripsi jatuh ke teks kartu bila desc_selector kosong
    no_desc = dict(source, desc_selector=None)
    assert _build_job(card, no_desc, "https://x.com", None)["description"], \
        "harus jatuh ke teks kartu"
    ok("Deskripsi kosong diselector -> jatuh ke teks kartu")

    # Checkbox "hidden 0 + checkbox 1" harus dibaca sebagai aktif
    form = MultiDict([("enabled", "0"), ("enabled", "1")])
    assert _flag(form, "enabled") is True, "checkbox centang harus menang atas hidden 0"
    assert _flag(MultiDict([("fetch_detail", "0")]), "fetch_detail") is False
    assert _flag(MultiDict([]), "enabled") is None, "field absen harus None"
    ok("_flag membaca checkbox HTML dengan benar")

    # Validasi sumber
    base = {"scraper_key": "glints", "name": "Glints", "url_template": "https://g/{keyword}"}
    assert _sanitize_source(dict(base)), "sumber bawaan tak perlu selector"
    ok("Sumber scraper bawaan boleh tanpa selector")

    for field in ("item_selector", "title_selector", "url_selector"):
        try:
            _sanitize_source({"scraper_key": "custom", "name": "X", "url_template": "u"})
            raise AssertionError(f"{field} kosong seharusnya ditolak")
        except ValueError:
            pass
    ok("Sumber custom tanpa selector wajib ditolak")

    try:
        _sanitize_source({"scraper_key": "custom", "name": "X", "url_template": "u",
                          "item_selector": "a", "title_selector": "a", "url_selector": "a",
                          "max_jobs": 0})
        raise AssertionError("max_jobs=0 seharusnya ditolak")
    except ValueError:
        pass
    ok("max_jobs / max_pages minimal 1")

    # Nilai integer salah harus ditolak, bukan diam-diam 0
    try:
        _clean(MultiDict([("max_jobs", "abc")]), SOURCE_TEXT_FIELDS,
               SOURCE_INT_FIELDS, SOURCE_BOOL_FIELDS)
        raise AssertionError("max_jobs='abc' seharusnya ditolak")
    except ValueError:
        pass
    ok("Kolom angka tidak valid ditolak dengan pesan jelas")

except Exception as e:
    fail(f"referensi loker error: {e}")
    traceback.print_exc()


# ─────────────────────────────────────────────
# RINGKASAN
# ─────────────────────────────────────────────
section("SELESAI")
print("  Semua test selesai dijalankan.")
print("  Cek hasil [OK]/[FAIL] di atas.\n")
