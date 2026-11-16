import logging
from datetime import datetime, timedelta, timezone

from db.supabase_client import supabase

log = logging.getLogger(__name__)

DEFAULT_MAX_AGE_DAYS = 90  # 3 bulan


def purge_old_jobs(max_age_days=DEFAULT_MAX_AGE_DAYS):
    """Hapus permanen loker yang sudah lebih dari max_age_days.

    Basis umur: kolom `created_at` (saat baris pertama kali dimasukkan ke DB).
    Mengembalikan jumlah baris yang dihapus.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff_iso = cutoff.isoformat()

    log.info("[Cleanup] Cari loker dengan created_at < %s ...", cutoff.date().isoformat())

    try:
        res = supabase.table("jobs") \
            .select("id") \
            .lt("created_at", cutoff_iso) \
            .execute()
    except Exception as e:
        log.error("[Cleanup] Gagal membaca loker lama: %s", e)
        return 0

    data = getattr(res, "data", None)
    if data is None and isinstance(res, dict):
        data = res.get("data")
    ids = [row["id"] for row in (data or []) if row.get("id")]

    if not ids:
        log.info("[Cleanup] Tidak ada loker yang berumur > %d hari", max_age_days)
        return 0

    try:
        supabase.table("jobs") \
            .delete() \
            .in_("id", ids) \
            .execute()
    except Exception as e:
        log.error("[Cleanup] Gagal menghapus %d loker lama: %s", len(ids), e)
        return 0

    log.info("[Cleanup] %d loker lama dihapus permanen", len(ids))
    return len(ids)