-- 0001_init — Legal Drafting Copilot schema, RLS, and profile trigger.
-- Manual rollbacks live outside this directory so `db push` never applies them.

create extension if not exists "pgcrypto";

-- profiles: mirrors auth.users
create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text,
    org text,
    plan text not null default 'free',
    created_at timestamptz not null default now()
);

-- tasks: one legal task/brief (top-level resource)
create table if not exists public.tasks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    task_type text not null default 'ma_first_draft',
    title text not null,
    brief text not null,
    eval_doc_count int not null default 5,
    status text not null default 'planning',
    plan_md text,
    created_at timestamptz not null default now()
);
create index if not exists tasks_user_status_idx on public.tasks (user_id, status);

-- documents: lawyer-uploaded source material
create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),
    task_id uuid not null references public.tasks (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    filename text not null,
    s3_key text not null,
    mime text,
    status text not null default 'uploaded',
    created_at timestamptz not null default now()
);
create index if not exists documents_task_idx on public.documents (task_id);

-- candidates: the unified evidence pool (web + cellar + uploads)
create table if not exists public.candidates (
    id uuid primary key default gen_random_uuid(),
    task_id uuid not null references public.tasks (id) on delete cascade,
    origin text not null,                       -- web | cellar | upload
    title text,
    url text,
    snippet text,
    source_document_id uuid references public.documents (id) on delete set null,
    agent_run_id uuid,
    rank int,                                   -- set by reranker
    relevance_score double precision,
    evaluated boolean not null default false,
    eval_relevance double precision,
    eval_risk double precision,
    eval_uncertainty double precision,
    eval_notes text,
    use_in_synthesis boolean not null default false,
    created_at timestamptz not null default now()
);
create index if not exists candidates_task_rank_idx on public.candidates (task_id, rank);
create index if not exists candidates_task_eval_idx on public.candidates (task_id, evaluated);

-- agent_runs: one row per agent stage (the unit Celery executes)
create table if not exists public.agent_runs (
    id uuid primary key default gen_random_uuid(),
    task_id uuid not null references public.tasks (id) on delete cascade,
    agent text not null,                        -- planner|coordinator|web|doc|reranker|evaluator|synthesiser
    status text not null default 'queued',
    provider text,
    input jsonb,
    output jsonb,
    tokens int,
    cost double precision,
    attempts int not null default 0,
    idempotency_key text,
    error text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists agent_runs_task_agent_idx on public.agent_runs (task_id, agent);

-- outputs: the synthesised argument
create table if not exists public.outputs (
    id uuid primary key default gen_random_uuid(),
    task_id uuid not null references public.tasks (id) on delete cascade,
    version int not null default 1,
    content_md text not null,
    s3_key text,
    created_at timestamptz not null default now()
);
create index if not exists outputs_task_version_idx on public.outputs (task_id, version desc);

-- ---- Row Level Security ----
alter table public.profiles enable row level security;
alter table public.tasks enable row level security;
alter table public.documents enable row level security;
alter table public.candidates enable row level security;
alter table public.agent_runs enable row level security;
alter table public.outputs enable row level security;

-- Profiles: owner can read/update own row.
create policy "profiles_self" on public.profiles
    for all using (auth.uid() = id) with check (auth.uid() = id);

-- Tasks: owner-only.
create policy "tasks_owner" on public.tasks
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Documents: owner-only.
create policy "documents_owner" on public.documents
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Child tables (candidates/agent_runs/outputs): readable if the parent task is owned.
-- Writes happen via the service-role API, which bypasses RLS; clients only read.
create policy "candidates_via_task" on public.candidates
    for select using (
        exists (select 1 from public.tasks t where t.id = task_id and t.user_id = auth.uid())
    );
create policy "agent_runs_via_task" on public.agent_runs
    for select using (
        exists (select 1 from public.tasks t where t.id = task_id and t.user_id = auth.uid())
    );
create policy "outputs_via_task" on public.outputs
    for select using (
        exists (select 1 from public.tasks t where t.id = task_id and t.user_id = auth.uid())
    );

-- ---- Auto-provision a profile on signup ----
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, email)
    values (new.id, new.email)
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();
