create table if not exists public.jobs (
    id            uuid default gen_random_uuid() primary key,
    title         text        not null,
    company       text        not null,
    location      text        not null,
    type          text        not null default 'Full-time'
                    check (type in ('Full-time', 'Part-time', 'Contract', 'Internship')),
    salary        text,
    description   text        not null,
    skills        jsonb       default '[]'::jsonb,
    contact_info  text,
    url           text        not null unique,
    source        text        not null,
    is_active     boolean     not null default true,
    priority      integer     not null default 1,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- Migrasi untuk tabel jobs yang sudah ada (jalankan sekali saja):
-- alter table public.jobs
--     add column if not exists priority integer not null default 1;

create index if not exists idx_jobs_source    on public.jobs (source);
create index if not exists idx_jobs_is_active on public.jobs (is_active);
create index if not exists idx_jobs_priority  on public.jobs (priority);

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger trg_jobs_updated_at
    before update on public.jobs
    for each row execute procedure set_updated_at();

-- ── Sumber & Kata Kunci ──────────────────────────────────────────────────────
-- Daftar sumber + keyword yang dipakai scraper. Dikelola dari halaman
-- "Sumber & Kata Kunci" di dashboard, bukan lagi dari kode.
-- Jalankan ulang blok ini di Supabase SQL Editor sebelum memakai fiturnya.

create table if not exists public.job_sources (
    id                uuid default gen_random_uuid() primary key,
    scraper_key       text        not null,
    name              text        not null,
    url_template      text        not null,
    enabled           boolean     not null default true,
    sort_order        integer     not null default 100,
    max_jobs          integer     not null default 25,
    max_pages         integer     not null default 1,
    fetch_detail      boolean     not null default true,
    item_selector     text,
    title_selector    text,
    company_selector  text,
    location_selector text,
    url_selector      text,
    desc_selector     text,
    next_page_selector text,
    notes             text,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

-- Catatan: scraper_key sengaja tidak unik. Nilai 'custom' dipakai bersama
-- oleh semua sumber berbasis selector; hanya kunci bawaan (glints, indeed,
-- dll) yang punya arti khusus karena dipetakan ke modul scraper.

create index if not exists idx_job_sources_enabled on public.job_sources (enabled, sort_order);

create table if not exists public.job_keywords (
    id         uuid default gen_random_uuid() primary key,
    keyword    text        not null unique,
    enabled    boolean     not null default true,
    sort_order integer     not null default 100,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_job_keywords_enabled on public.job_keywords (enabled, sort_order);

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
