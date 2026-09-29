-- Tabby Assistant demo schema. Safe to re-run: drops and recreates everything.

drop view if exists product_cards;
drop function if exists search_products;
drop function if exists search_help;  -- replaced by kb_hybrid_search (kb_schema.sql)
drop table if exists chat_sessions, support_tickets, help_articles, payment_attempts, payment_methods, installments, orders, products, stores, categories, accounts cascade;

create table categories (
  id   text primary key,
  name text not null
);

create table stores (
  id           text primary key,
  name         text not null,
  categories   text[] not null default '{}',
  cashback_pct numeric not null default 0
);

create table products (
  id             text primary key,
  name           text not null,
  brand          text not null,
  category       text not null references categories(id),
  store_id       text not null references stores(id),
  price          numeric not null,
  original_price numeric,                      -- set when discounted
  rating         numeric,
  storage_gb     int generated always as ((specs->>'storage_gb')::int) stored,
  color          text generated always as (specs->>'color') stored,
  specs          jsonb not null default '{}'
);
create index on products (category, price);

create table accounts (
  id                     text primary key,
  name                   text not null,
  phone                  text,
  home_address           jsonb,
  profile_completion_pct int not null default 0,
  cashback_balance       numeric not null default 0,
  credit_limit           numeric not null,
  id_verified            boolean not null default true,
  language               text check (language in ('ar', 'en')),  -- null until the user picks
  referral               jsonb not null
);

create table orders (
  id         text primary key,
  account_id text not null references accounts(id),
  product    text not null,
  store      text not null,
  total      numeric not null,
  plan       text not null check (plan in ('split_in_4', 'pay_in_6', 'pay_in_12')),
  created_at timestamptz not null default now()
);

create table installments (
  id       text primary key,
  order_id text not null references orders(id) on delete cascade,
  seq      int not null,
  amount   numeric not null,
  due      date not null,
  status   text not null check (status in ('paid', 'upcoming')),
  paid_at  timestamptz
);

create table payment_methods (
  id         text primary key,
  account_id text not null references accounts(id),
  brand      text not null check (brand in ('visa', 'mastercard', 'mada', 'apple_pay')),
  last4      text not null,
  exp_month  int not null,
  exp_year   int not null,
  is_default boolean not null default false
);

-- Every charge Tabby tried, with the processor's reason when it failed.
create table payment_attempts (
  id             text primary key,
  account_id     text not null references accounts(id),
  method_id      text not null references payment_methods(id),
  installment_id text references installments(id),
  amount         numeric not null,
  status         text not null check (status in ('succeeded', 'failed')),
  failure_code   text,
  created_at     timestamptz not null default now()
);

create table support_tickets (
  id         text primary key,
  account_id text not null references accounts(id),
  category   text not null,
  summary    text not null,
  status     text not null default 'open',
  created_at timestamptz not null default now()
);

-- One row per assistant conversation. The full message history lives in the
-- LangGraph checkpoint tables (keyed by thread_id); this row holds only what
-- the user sees when they come back: a small memo of what they were doing.
create table chat_sessions (
  thread_id  text primary key,
  account_id text not null references accounts(id),
  language   text not null check (language in ('ar', 'en')),
  memo       jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on chat_sessions (account_id, updated_at desc);

-- Products joined with their store: what the app and the assistant display.
create view product_cards with (security_invoker = true) as
  select p.*, s.name as store_name, s.cashback_pct
  from products p join stores s on s.id = p.store_id;

-- Catalog search used by the assistant's search_products tool.
-- Every filter is optional; free text matches any word, ranked by how many match.
create function search_products(
  p_query          text    default null,
  p_category       text    default null,
  p_brands         text[]  default null,
  p_min_price      numeric default null,
  p_max_price      numeric default null,
  p_min_storage_gb int     default null,
  p_color          text    default null,
  p_store          text    default null,
  p_deals_only     boolean default false,
  p_sort           text    default 'relevance',
  p_limit          int     default 50
) returns jsonb language sql stable as $$
  with scored as (
    select c.*,
      case when coalesce(trim(p_query), '') = '' then 1 else (
        select count(*) from unnest(regexp_split_to_array(lower(trim(p_query)), '\s+')) w
        where lower(concat_ws(' ', c.name, c.brand, c.store_id, c.store_name, c.specs::text)) like '%' || w || '%'
      ) end as score
    from product_cards c
    where (p_category is null or c.category = p_category)
      and (p_brands is null or lower(c.brand) = any (select lower(b) from unnest(p_brands) b))
      and (p_min_price is null or c.price >= p_min_price)
      and (p_max_price is null or c.price <= p_max_price)
      and (p_min_storage_gb is null or c.storage_gb >= p_min_storage_gb)
      and (p_color is null or c.color ilike '%' || p_color || '%')
      and (p_store is null or c.store_id ilike '%' || p_store || '%' or c.store_name ilike '%' || p_store || '%')
      and (not p_deals_only or c.original_price is not null)
  ),
  matched as (select * from scored where score > 0),
  page as (
    select *, row_number() over (order by
        case when p_sort = 'price_asc'  then price end asc,
        case when p_sort = 'price_desc' then price end desc,
        case when p_sort = 'rating'     then rating end desc,
        case when p_sort = 'discount'   then coalesce(original_price, price) - price end desc,
        score desc, rating desc) as rn
    from matched
  )
  select jsonb_build_object(
    'total', (select count(*) from matched),
    'items', coalesce((select jsonb_agg(to_jsonb(page) - 'score' - 'rn' order by rn) from page where rn <= p_limit), '[]'::jsonb)
  );
$$;

-- The backend uses the service_role key. RLS on with no policies keeps the
-- anon key from reading or writing anything.
alter table categories   enable row level security;
alter table stores       enable row level security;
alter table products     enable row level security;
alter table accounts     enable row level security;
alter table orders       enable row level security;
alter table installments enable row level security;
alter table payment_methods  enable row level security;
alter table payment_attempts enable row level security;
alter table support_tickets  enable row level security;
alter table chat_sessions    enable row level security;

notify pgrst, 'reload schema';
