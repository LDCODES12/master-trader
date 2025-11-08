create table if not exists hypotheses (
  key text primary key,
  alpha numeric not null default 1,
  beta numeric not null default 1,
  promoted boolean not null default false,
  updated_at timestamptz not null default now()
);


