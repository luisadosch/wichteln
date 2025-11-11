-- SQL setup for the Wichtel-Zuteiler app
-- Run these statements once in the Supabase SQL editor (or via CLI) using a service role key.

create table if not exists public.sessions (
    id bigserial primary key,
    user_password text not null,
    user_password_hash text not null unique,
    admin_code_hash text unique,
    assignments_json text not null,
    pairs_json text,
    created_at timestamptz not null
);

create unique index if not exists idx_sessions_admin_code_hash
    on public.sessions (admin_code_hash);
