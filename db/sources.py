import logging

from db.supabase_client import supabase

log = logging.getLogger(__name__)

SOURCES_TABLE = "job_sources"
KEYWORDS_TABLE = "job_keywords"

BUILTIN_SCRAPERS = {
    "linkedin": "LinkedIn",
    "jobstreet": "JobStreet",
    "glints": "Glints",
    "kalibrr": "Kalibrr",
    "indeed": "Indeed",
}

SOURCE_TEXT_FIELDS = (
    "scraper_key",
    "name",
    "url_template",
    "item_selector",
    "title_selector",
    "company_selector",
    "location_selector",
    "url_selector",
    "desc_selector",
    "next_page_selector",
    "notes",
)

SOURCE_INT_FIELDS = ("sort_order", "max_jobs", "max_pages")
SOURCE_BOOL_FIELDS = ("enabled", "fetch_detail")

DEFAULT_SOURCES = [
    {
        "scraper_key": "linkedin",
        "name": "LinkedIn",
        "url_template": "https://www.linkedin.com/jobs/search/?keywords={keyword}&location=Indonesia",
        "sort_order": 1,
    },
    {
        "scraper_key": "jobstreet",
        "name": "JobStreet",
        "url_template": "https://www.jobstreet.co.id/找工作?keyword={keyword}",
        "sort_order": 2,
    },
    {
        "scraper_key": "glints",
        "name": "Glints",
        "url_template": (
            "https://glints.com/id/opportunities/jobs/explore"
            "?keyword={keyword}&country=ID&locationName=All+Cities%2FProvinces"
        ),
        "sort_order": 3,
    },
    {
        "scraper_key": "kalibrr",
        "name": "Kalibrr",
        "url_template": "https://kalibrr.id/lowongan?q={keyword}",
        "sort_order": 4,
    },
    {
        "scraper_key": "indeed",
        "name": "Indeed",
        "url_template": "https://id.indeed.com/jobs?q={keyword}&l=Indonesia",
        "sort_order": 5,
    },
]

DEFAULT_KEYWORDS = [
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


def _count(table):
    return len(supabase.table(table).select("id").execute().data or [])


def list_sources(only_enabled=False):
    query = supabase.table(SOURCES_TABLE).select("*")
    if only_enabled:
        query = query.eq("enabled", True)
    return query.order("sort_order").order("name").execute().data or []


def list_keywords(only_enabled=False):
    query = supabase.table(KEYWORDS_TABLE).select("*")
    if only_enabled:
        query = query.eq("enabled", True)
    return query.order("sort_order").order("keyword").execute().data or []


def get_source(source_id):
    rows = (supabase.table(SOURCES_TABLE).select("*")
            .eq("id", source_id).limit(1).execute().data or [])
    return rows[0] if rows else None


TRUTHY = ("1", "true", "on", "yes", "ya")


def _flag(payload, field):
    """Baca nilai boolean dari form, atau None bila field tidak dikirim.

    Checkbox HTML mengirim nilai '' saat tidak dicentang, dan pola
    "hidden 0 + checkbox 1" mengirim dua nilai. Selama salah satunya berbenar,
    field dianggap aktif. Field yang absen dibiarkan None supaya nilai lama
    di database tidak tertimpa diam-diam.
    """
    if field not in payload:
        return None
    values = (payload.getlist(field) if hasattr(payload, "getlist")
              else [payload.get(field)])
    return any(str(v).strip().lower() in TRUTHY for v in values)


def _clean(payload, text_fields, int_fields, bool_fields):
    data = {}

    for field in text_fields:
        if field in payload:
            value = payload.get(field)
            data[field] = value.strip() if isinstance(value, str) else value

    for field in int_fields:
        if field in payload:
            raw = payload.get(field)
            if raw in (None, ""):
                data[field] = None
                continue
            try:
                data[field] = int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"{field} harus berupa angka")

    for field in bool_fields:
        flag = _flag(payload, field)
        if flag is not None:
            data[field] = flag

    return data


def _sanitize_source(data):
    """Pastikan kolom wajib sumber terisi sebelum disimpan.

    Selector hanya wajib untuk sumber kustom; scraper bawaan (linkedin,
    glints, dll) memakai modul scraper-nya sendiri sehingga selector diabaikan.
    """
    data.setdefault("scraper_key", "").strip()
    for field in ("scraper_key", "name", "url_template"):
        if not data.get(field):
            raise ValueError(f"{field} wajib diisi")



    for field in ("max_jobs", "max_pages"):
        if data.get(field) is None:
            data[field] = 25 if field == "max_jobs" else 1
        if data[field] < 1:
            raise ValueError(f"{field} minimal 1")
    if data.get("sort_order") is None:
        data["sort_order"] = 100

    return data


def create_source(payload):
    data = _sanitize_source(_clean(
        payload, SOURCE_TEXT_FIELDS, SOURCE_INT_FIELDS, SOURCE_BOOL_FIELDS))
    rows = (supabase.table(SOURCES_TABLE).insert(data).execute().data or [])
    return rows[0] if rows else None


ALL_SOURCE_FIELDS = SOURCE_TEXT_FIELDS + SOURCE_INT_FIELDS + SOURCE_BOOL_FIELDS


def update_source(source_id, payload):
    """Gabung payload di atas baris yang ada, lalu validasi hasilnya.

    Ini membuat update parsial aman: aksi toggle cukup mengirim `enabled`
    tanpa harus mengirim ulang seluruh selector dan urutan.
    """
    current = get_source(source_id)
    if current is None:
        raise ValueError("sumber tidak ditemukan")

    merged = {field: current.get(field) for field in ALL_SOURCE_FIELDS}
    merged.update(_clean(payload, SOURCE_TEXT_FIELDS, SOURCE_INT_FIELDS, SOURCE_BOOL_FIELDS))
    data = _sanitize_source(merged)

    rows = (supabase.table(SOURCES_TABLE).update(data)
            .eq("id", source_id).execute().data or [])
    return rows[0] if rows else None


def delete_source(source_id):
    supabase.table(SOURCES_TABLE).delete().eq("id", source_id).execute()


def create_keyword(payload):
    keyword = (payload.get("keyword") or "").strip()
    if not keyword:
        raise ValueError("keyword wajib diisi")

    data = {"keyword": keyword}
    if "sort_order" in payload:
        try:
            data["sort_order"] = int(payload["sort_order"] or 0)
        except (TypeError, ValueError):
            raise ValueError("sort_order harus berupa angka")
    flag = _flag(payload, "enabled")
    if flag is not None:
        data["enabled"] = flag

    rows = (supabase.table(KEYWORDS_TABLE).insert(data).execute().data or [])
    return rows[0] if rows else None


def update_keyword(keyword_id, payload):
    data = {}
    if "keyword" in payload:
        keyword = (payload.get("keyword") or "").strip()
        if not keyword:
            raise ValueError("keyword wajib diisi")
        data["keyword"] = keyword
    if "sort_order" in payload:
        try:
            data["sort_order"] = int(payload["sort_order"] or 0)
        except (TypeError, ValueError):
            raise ValueError("sort_order harus berupa angka")
    flag = _flag(payload, "enabled")
    if flag is not None:
        data["enabled"] = flag

    if not data:
        return get_keyword(keyword_id)

    rows = (supabase.table(KEYWORDS_TABLE).update(data)
            .eq("id", keyword_id).execute().data or [])
    return rows[0] if rows else None


def get_keyword(keyword_id):
    rows = (supabase.table(KEYWORDS_TABLE).select("*")
            .eq("id", keyword_id).limit(1).execute().data or [])
    return rows[0] if rows else None


def delete_keyword(keyword_id):
    supabase.table(KEYWORDS_TABLE).delete().eq("id", keyword_id).execute()


def seed_defaults():
    """Isi tabel referensi dengan bawaan bila masih kosong (idempoten)."""
    created = {"sources": 0, "keywords": 0}

    if _count(SOURCES_TABLE) == 0:
        supabase.table(SOURCES_TABLE).insert(DEFAULT_SOURCES).execute()
        created["sources"] = len(DEFAULT_SOURCES)
        log.info("Seeding %d sumber default", created["sources"])

    if _count(KEYWORDS_TABLE) == 0:
        supabase.table(KEYWORDS_TABLE).insert(
            [{"keyword": kw, "sort_order": i + 1}
             for i, kw in enumerate(DEFAULT_KEYWORDS)]).execute()
        created["keywords"] = len(DEFAULT_KEYWORDS)
        log.info("Seeding %d keyword default", created["keywords"])

    return created


def ensure_seeded():
    """Isi referensi bila tabel kosong. Tidak melempar error.

    Kalau tabelnya belum dibuat di Supabase, scraper tetap jalan memakai
    daftar bawaan dari run.py.
    """
    try:
        return bool(seed_defaults())
    except Exception as e:
        log.warning("Tabel job_sources/job_keywords belum siap: %s", e)
        return False
