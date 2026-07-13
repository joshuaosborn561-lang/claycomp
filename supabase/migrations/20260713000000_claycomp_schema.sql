-- Claycomp persistence schema (run once in Supabase SQL Editor)

create table if not exists public.claycomp_tables (
  id text primary key,
  name text not null default 'My Leads',
  row_count integer not null default 0,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.claycomp_settings (
  id text primary key default 'api_keys',
  keys jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists claycomp_tables_updated_at_idx
  on public.claycomp_tables (updated_at desc);

alter table public.claycomp_tables enable row level security;
alter table public.claycomp_settings enable row level security;

-- Server uses the service role key (bypasses RLS). These policies allow anon access if needed.
create policy "claycomp_tables_all" on public.claycomp_tables
  for all using (true) with check (true);

create policy "claycomp_settings_all" on public.claycomp_settings
  for all using (true) with check (true);
