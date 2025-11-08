create table if not exists evidence_artifacts (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz default now(),
  url text not null,
  sha256 text not null,
  c2pa_status text not null,
  bytes_len int not null,
  proposal_id uuid
);


