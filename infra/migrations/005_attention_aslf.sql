create table if not exists attention_aslf (
  ts timestamptz default now(),
  symbol text,
  aas numeric,
  lmf numeric,
  aslf numeric,
  decision text,
  notes text
);


