create table if not exists equity_stats (
  ts timestamptz default now(),
  equity numeric not null,
  high_water_mark numeric not null,
  max_drawdown numeric not null,
  romad numeric,
  dsr numeric,
  regime text,
  notes text
);


