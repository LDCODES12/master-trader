create table if not exists trade_attribution (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz not null default now(),
  order_id text,
  symbol text,
  mechanism text,
  aslf numeric,
  execution_style text,
  impact_bps numeric,
  notes text
);


