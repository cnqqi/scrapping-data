-- ============================================================================
--  SUMBER & KATA KUNCI — salin SELURUH isi file ini ke Supabase SQL Editor
--  Supabase -> SQL Editor -> New query -> (paste) -> Run
--
--  Aman dijalankan berulang kali (idempoten).
--  Setelah selesai, buka http://localhost:5000/references lalu klik
--  "Isi Data Bawaan".
-- ============================================================================

-- ── 1. Tabel sumber lowongan ────────────────────────────────────────────────
create table if not exists public.job_sources (
    id                 uuid default gen_random_uuid() primary key,
    scraper_key        text        not null,
    name               text        not null,
    url_template       text        not null,
    enabled            boolean     not null default true,
    sort_order         integer     not null default 100,
    max_jobs           integer     not null default 25,
    max_pages          integer     not null default 1,
    fetch_detail       boolean     not null default true,
    item_selector      text,
    title_selector     text,
    company_selector   text,
    location_selector  text,
    url_selector       text,
    desc_selector      text,
    next_page_selector text,
    notes              text,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

-- scraper_key sengaja tidak unik: nilai 'custom' dipakai bersama oleh semua
-- sumber berbasis selector. Hanya kunci bawaan (glints, indeed, dll) yang
-- punya arti khusus karena dipetakan ke modul scraper.

create index if not exists idx_job_sources_enabled
    on public.job_sources (enabled, sort_order);

-- ── 2. Tabel kata kunci pencarian ───────────────────────────────────────────
create table if not exists public.job_keywords (
    id         uuid default gen_random_uuid() primary key,
    keyword    text        not null unique,
    enabled    boolean     not null default true,
    sort_order integer     not null default 100,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_job_keywords_enabled
    on public.job_keywords (enabled, sort_order);

-- ── 3. Trigger updated_at ───────────────────────────────────────────────────
-- Function set_updated_at() sudah dibuat oleh blok pertama schema.sql.
-- Kalau tabel jobs belum pernah dibuat, jalankan blok ini dulu:
--
--   create or replace function set_updated_at()
--   returns trigger language plpgsql as $$
--   begin
--       new.updated_at = now();
--       return new;
--   end;
--   $$;

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'trg_job_sources_updated_at') then
        create trigger trg_job_sources_updated_at
            before update on public.job_sources
            for each row execute procedure set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_job_keywords_updated_at') then
        create trigger trg_job_keywords_updated_at
            before update on public.job_keywords
            for each row execute procedure set_updated_at();
    end if;
end $$;
