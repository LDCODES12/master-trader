alter table if exists trade_attribution
  add column if not exists status text default 'unknown';


