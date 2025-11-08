create extension if not exists "uuid-ossp";


create table if not exists policy_flags (
  id int primary key default 1,
  trading_enabled boolean default true,
  max_daily_loss_bps int default 50
);


insert into policy_flags (id) values (1)
on conflict (id) do nothing;


create table if not exists trade_proposals (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz default now(),
  symbol text not null,
  side text check (side in ('buy','sell')) not null,
  size_bps_equity numeric not null,
  horizon_minutes int not null,
  thesis text not null,
  risk jsonb not null,
  evidence jsonb not null,
  confidence numeric not null,
  status text default 'proposed'
);


create table if not exists executions (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz default now(),
  proposal_id uuid references trade_proposals(id),
  venue text,
  order_id text,
  status text,
  fills jsonb,
  error text
);


