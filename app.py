import inspect
import logging
import os
import threading
import time
from collections import Counter
from datetime import datetime
from functools import partial

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from core.generic_scraper import scrape_generic
from db import sources as refdb
from db.sources import BUILTIN_SCRAPERS
from db.supabase_client import supabase
from run import (
    DONE_URLS,
    SCRAPER_REGISTRY,
    load_keywords,
    load_sources,
    push,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "job-scraper-admin"

LOG_ENTRIES = []
LOG_ID = 0
LOCK = threading.Lock()

# Sinyal kontrol scraping yang berjalan di background thread.
# PAUSE_SIGNAL aktif  -> jeda, tunggu sebelum pekerjaan berikutnya.
# STOP_SIGNAL aktif   -> berhenti, jangan mulai pekerjaan berikutnya.
PAUSE_SIGNAL = threading.Event()
STOP_SIGNAL = threading.Event()

STATE = {
    "running": False,
    "paused": False,
    "stop_requested": False,
    "started_at": None,
    "finished_at": None,
    "total_combos": 0,
    "done_combos": 0,
    "jobs_found": 0,
    "jobs_inserted": 0,
}

JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]

# Pesan error tabel referensi yang belum dibuat di Supabase.
REF_TABLES_MISSING = (
    "Tabel job_sources/job_keywords belum ada di Supabase. "
    "Jalankan blok Sumber & Kata Kunci di schema.sql melalui Supabase SQL Editor."
)


def emit(level, text):
    global LOG_ID
    with LOCK:
        LOG_ID += 1
        LOG_ENTRIES.append({
            "id": LOG_ID,
            "ts": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "text": text,
        })
        if len(LOG_ENTRIES) > 5000:
            del LOG_ENTRIES[: len(LOG_ENTRIES) - 5000]


class EmitLogHandler(logging.Handler):
    def emit(self, record):
        level = "step"
        if record.levelno >= logging.ERROR:
            level = "fail"
        elif record.levelno >= logging.WARNING:
            level = "warn"
        emit(level, self.format(record))

def arm_run_state():
    """Siapkan STATE sebelum thread scraper benar-benar jalan.

    Menyiapkan referensi (seed + baca keyword/sumber) butuh beberapa
    panggilan network ke Supabase. Kalau `running` baru diset setelah itu,
    poll UI pertama bisa melihat `running=False` lalu berhenti diam-diam,
    sehingga tidak ada catatan yang pernah tampil di halaman pipeline.
    """
    PAUSE_SIGNAL.clear()
    STOP_SIGNAL.clear()
    STATE["running"] = True
    STATE["paused"] = False
    STATE["stop_requested"] = False
    STATE["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATE["finished_at"] = None
    STATE["done_combos"] = 0
    STATE["jobs_found"] = 0
    STATE["jobs_inserted"] = 0
    DONE_URLS.clear()


def run_scraper_in_background():
    try:
        from core.pipeline_view import set_emit_callback
        set_emit_callback(emit)

        # Tambahkan handler log untuk UI
        ui_handler = EmitLogHandler()
        ui_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(ui_handler)

        emit("stage", "Menyiapkan sumber dan kata kunci...")

        refdb.ensure_seeded()
        keywords = load_keywords()
        sources = load_sources()
        combos = len(keywords) * len(sources)

        STATE["total_combos"] = combos

        emit("stage", f"Total {len(keywords)} keyword x {len(sources)} sumber "
                      f"= {combos} pencarian")

        stopped = False
        for keyword in keywords:
            for scraper, source in sources:
                if not wait_if_needed():
                    stopped = True
                    break

                STATE["done_combos"] += 1
                emit("stage",
                     f"MENGAMBIL DATA [{STATE['done_combos']}/{combos}] "
                     f"{source} - kata kunci '{keyword}'")
                try:
                    jobs = scraper(keyword)
                except Exception as e:
                    emit("fail", f"Gagal mengambil data dari {source}: {e}")
                    continue
                STATE["jobs_found"] += len(jobs)
                emit("ok", f"{len(jobs)} lowongan dari {source} (kata kunci '{keyword}')")
                try:
                    STATE["jobs_inserted"] += push(jobs, source)
                except Exception as e:
                    emit("fail", f"Gagal menyimpan data dari {source}: {e}")
            if stopped:
                break

        emit("hr", "")
        if stopped:
            emit("warn", f"DIHENTIKAN operator - baru selesai "
                         f"{STATE['done_combos']} dari {combos} pencarian.")
        else:
            emit("ok", "SELESAI - semua sumber dan kata kunci sudah dijalankan.")
    except Exception as e:
        emit("fail", f"Terjadi kesalahan umum: {e}")
    finally:
        try:
            root_logger.removeHandler(ui_handler)
            set_emit_callback(None)
        except:
            pass
        STATE["running"] = False
        STATE["paused"] = False
        STATE["stop_requested"] = False
        PAUSE_SIGNAL.clear()
        STOP_SIGNAL.clear()
        STATE["finished_at"] = datetime.now().strftime("%H:%M:%S")


def wait_if_needed():
    """Tahan thread di sini selama scraping dijeda.

    Kembalikan False kalau operator meminta berhenti. Periksa berhenti
    duluan supaya jeda tidak membuat "Hentikan" menggantung.
    """
    if STOP_SIGNAL.is_set():
        return False
    while PAUSE_SIGNAL.is_set():
        if STOP_SIGNAL.is_set():
            return False
        time.sleep(0.25)
    return True


def _apply_filters(query):
    q = (request.args.get("q") or "").strip()
    source = request.args.get("source") or ""
    jtype = request.args.get("type") or ""
    priority = request.args.get("priority") or ""
    if q:
        query = query.ilike("title", f"%{q}%")
    if source and source != "all":
        query = query.eq("source", source)
    if jtype and jtype != "all":
        query = query.eq("type", jtype)
    if priority in ("0", "1"):
        query = query.eq("priority", int(priority))
    return query


def _safe_page(raw):
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def _source_names():
    """Nama sumber aktif dari referensi DB; fallback ke daftar bawaan."""
    return [name for _, name in load_sources()]


def _references_payload():
    """Data untuk halaman Sumber & Kata Kunci + penanda bila tabel belum ada."""
    try:
        sources_rows = refdb.list_sources()
        keyword_rows = refdb.list_keywords()
        ready = True
        error = None
    except Exception as e:
        sources_rows = []
        keyword_rows = []
        ready = False
        error = f"{REF_TABLES_MISSING} ({e})"

    return sources_rows, keyword_rows, ready, error


def _source_action(action, source_id):
    """Aksi satu sumber: update, toggle, hapus, atau seed ulang."""
    try:
        if action == "delete":
            refdb.delete_source(source_id)
            flash("Sumber dihapus.", "ok")
            return redirect(url_for("references"))

        source = refdb.get_source(source_id)
        if source is None:
            flash("Sumber tidak ditemukan.", "error")
            return redirect(url_for("references"))

        if action == "toggle":
            refdb.update_source(source_id, {"enabled": not source.get("enabled", False)})
            flash(f"{source['name']} {'diaktifkan' if not source.get('enabled') else 'dinonaktifkan'}.", "ok")
        elif action == "update":
            refdb.update_source(source_id, request.form)
            flash(f"{source['name']} diperbarui.", "ok")
        else:
            flash("Aksi tidak dikenal.", "error")
    except Exception as e:
        flash(f"Gagal menyimpan sumber: {e}", "error")
    return redirect(url_for("references"))


def _keyword_action(action, keyword_id):
    try:
        if action == "delete":
            refdb.delete_keyword(keyword_id)
            flash("Keyword dihapus.", "ok")
            return redirect(url_for("references"))

        keyword = refdb.get_keyword(keyword_id)
        if keyword is None:
            flash("Keyword tidak ditemukan.", "error")
            return redirect(url_for("references"))

        if action == "toggle":
            refdb.update_keyword(keyword_id, {"enabled": not keyword.get("enabled", False)})
            flash(f"{keyword['keyword']} {'diaktifkan' if not keyword.get('enabled') else 'dinonaktifkan'}.", "ok")
        elif action == "update":
            refdb.update_keyword(keyword_id, request.form)
            flash(f"Keyword '{keyword['keyword']}' diperbarui.", "ok")
        else:
            flash("Aksi tidak dikenal.", "error")
    except Exception as e:
        flash(f"Gagal menyimpan keyword: {e}", "error")
    return redirect(url_for("references"))


@app.route("/")
def dashboard():
    per_page = 25
    page = _safe_page(request.args.get("page"))

    all_rows = supabase.table("jobs").select("source,priority").execute().data
    total_all = len(all_rows)
    per_source = Counter(r["source"] for r in all_rows)
    priority_cnt = sum(1 for r in all_rows if r.get("priority") == 0)

    filtered = _apply_filters(supabase.table("jobs").select("id")).execute().data
    total_filtered = len(filtered)

    rows = _apply_filters(supabase.table("jobs").select("*")) \
        .order("created_at", desc=True) \
        .range((page - 1) * per_page, page * per_page - 1) \
        .execute().data

    sources = _source_names()
    return render_template(
        "dashboard.html",
        rows=rows,
        total_all=total_all,
        per_source=per_source,
        per_source_sorted=sorted(per_source.items(), key=lambda x: -x[1]),
        priority_cnt=priority_cnt,
        total_filtered=total_filtered,
        sources=sources,
        types=JOB_TYPES,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total_filtered + per_page - 1) // per_page),
        q=(request.args.get("q") or "").strip(),
        source=request.args.get("source") or "",
        jtype=request.args.get("type") or "",
        priority=request.args.get("priority") or "",
    )


@app.route("/pipeline")
def pipeline():
    sources = _source_names()
    keywords = load_keywords()
    return render_template(
        "pipeline.html",
        source_count=len(sources),
        keyword_count=len(keywords),
        sources=sources,
        keywords_preview=keywords[:8],
        combos=len(sources) * len(keywords),
    )


@app.route("/references")
def references():
    sources_rows, keyword_rows, ready, error = _references_payload()
    return render_template(
        "references.html",
        sources=sources_rows,
        keywords=keyword_rows,
        ready=ready,
        error=error,
        builtin_scrapers=BUILTIN_SCRAPERS,
        source_names=_source_names(),
    )


@app.route("/references/seed", methods=["POST"])
def references_seed():
    try:
        created = refdb.seed_defaults()
        if created["sources"] or created["keywords"]:
            flash(f"Data bawaan ditambahkan: {created['sources']} sumber, "
                  f"{created['keywords']} keyword.", "ok")
        else:
            flash("Tabel referensi sudah berisi data.", "ok")
    except Exception as e:
        flash(f"Gagal mengisi data bawaan: {e}", "error")
    return redirect(url_for("references"))


@app.route("/references/sources", methods=["POST"])
def sources_create():
    try:
        created = refdb.create_source(request.form)
        flash(f"Sumber '{created['name']}' ditambahkan.", "ok")
    except Exception as e:
        flash(f"Gagal menambah sumber: {e}", "error")
    return redirect(url_for("references"))


@app.route("/references/sources/<source_id>", methods=["POST"])
def sources_update(source_id):
    return _source_action(request.form.get("action", "update"), source_id)


@app.route("/references/keywords", methods=["POST"])
def keywords_create():
    keyword = (request.form.get("keyword") or "").strip()
    if not keyword:
        flash("Keyword tidak boleh kosong.", "error")
        return redirect(url_for("references"))
    try:
        refdb.create_keyword(request.form)
        flash(f"Keyword '{keyword}' ditambahkan.", "ok")
    except Exception as e:
        flash(f"Gagal menambah keyword: {e}", "error")
    return redirect(url_for("references"))


@app.route("/references/keywords/<keyword_id>", methods=["POST"])
def keywords_update(keyword_id):
    return _keyword_action(request.form.get("action", "update"), keyword_id)


@app.route("/references/sources/<source_id>/test", methods=["POST"])
def sources_test(source_id):
    """Uji satu sumber dengan satu keyword: mengembalikan lowongan yang ketemu."""
    source = refdb.get_source(source_id)
    if source is None:
        return jsonify({"ok": False, "error": "Sumber tidak ditemukan"}), 404

    keyword = (request.form.get("keyword") or "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "Keyword tes wajib diisi"}), 400

    key = (source.get("scraper_key") or "").strip()
    scraper = SCRAPER_REGISTRY.get(key)
    if scraper is None:
        if not source.get("item_selector") or not source.get("title_selector") \
                or not source.get("url_selector"):
            return jsonify({"ok": False,
                            "error": "Sumber kustom wajib mengisi item_selector, "
                                     "title_selector dan url_selector"}), 400
        runner = partial(scrape_generic, source)
    else:
        runner = scraper

    limit = source.get("max_jobs") or 25
    try:
        if "max_jobs" in inspect.signature(runner).parameters:
            jobs = runner(keyword, max_jobs=min(int(limit), 5))
        else:
            jobs = runner(keyword)
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    preview = [{
        "title": j.get("title"),
        "company": j.get("company"),
        "location": j.get("location"),
        "url": j.get("url"),
    } for j in jobs[:5]]

    return jsonify({
        "ok": True,
        "source": source.get("name"),
        "keyword": keyword,
        "found": len(jobs),
        "preview": preview,
    })


@app.route("/api/state")
def api_state():
    since = 0
    try:
        since = max(0, int(request.args.get("since") or 0))
    except (TypeError, ValueError):
        since = 0
    with LOCK:
        events = [e for e in LOG_ENTRIES if e["id"] > since]
        last_id = LOG_ENTRIES[-1]["id"] if LOG_ENTRIES else 0
        running = STATE["running"]
    if not running and not STATE["total_combos"]:
        STATE["total_combos"] = len(load_keywords()) * len(load_sources())
    return jsonify({"state": dict(STATE), "events": events, "last_id": last_id})


@app.route("/api/scrape/start", methods=["POST"])
def scrape_start():
    if STATE["running"]:
        return jsonify({"ok": False, "error": "Pengambilan data sedang berjalan"}), 409
    # Tandai jalan sebelum thread dibuat supaya poll UI pertama tidak berhenti.
    arm_run_state()
    threading.Thread(target=run_scraper_in_background, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/scrape/pause", methods=["POST"])
def scrape_pause():
    """Jeda / lanjutkan scraping. Tombol yang sama untuk dua aksi."""
    if not STATE["running"]:
        return jsonify({"ok": False, "error": "Tidak ada pengambilan data yang berjalan"}), 409

    if PAUSE_SIGNAL.is_set():
        PAUSE_SIGNAL.clear()
        STATE["paused"] = False
        emit("warn", "Dijadwalkan untuk LANJUT setelah lowongan yang sedang diproses selesai.")
        return jsonify({"ok": True, "paused": False})

    PAUSE_SIGNAL.set()
    STATE["paused"] = True
    emit("warn", "DIJEDA - lowongan yang sedang diproses akan selesai, lalu scraping berhenti sejenak.")
    return jsonify({"ok": True, "paused": True})


@app.route("/api/scrape/stop", methods=["POST"])
def scrape_stop():
    """Minta scraping berhenti. Lowongan yang sedang diproses tetap disimpan."""
    if not STATE["running"]:
        return jsonify({"ok": False, "error": "Tidak ada pengambilan data yang berjalan"}), 409

    STOP_SIGNAL.set()
    PAUSE_SIGNAL.clear()
    STATE["paused"] = False
    STATE["stop_requested"] = True
    emit("warn", "Permintaan BERHENTI diterima - menyimpan lowongan yang sedang diproses, lalu berhenti.")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)