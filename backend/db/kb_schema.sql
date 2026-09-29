-- Help-center knowledge base for RAG. Separate from schema.sql so re-seeding
-- the demo data never wipes the embeddings. Safe to re-run.

create extension if not exists vector;

create table if not exists kb_chunks (
  id        text primary key,                -- assigned by LangChain's index() (content hash)
  content   text not null,                   -- title header + chunk text
  metadata  jsonb not null default '{}',     -- source, url, title, language, audience, category, chunk
  embedding vector(1536) not null,           -- OpenAI text-embedding-3-small
  -- 'simple' config: no stemming, so Arabic and English tokens both index as-is
  fts       tsvector generated always as (to_tsvector('simple', content)) stored
);
create index if not exists kb_chunks_embedding_idx on kb_chunks using hnsw (embedding vector_cosine_ops);
create index if not exists kb_chunks_fts_idx on kb_chunks using gin (fts);
create index if not exists kb_chunks_metadata_idx on kb_chunks using gin (metadata);

-- Hybrid search: full-text ranking and vector ranking fused with Reciprocal
-- Rank Fusion. Keywords catch exact terms ("mada", "Tabby Card"); vectors catch
-- meaning and cross-language matches.
create or replace function kb_hybrid_search(
  query_text      text,
  query_embedding vector(1536),
  match_count     int     default 8,
  filter          jsonb   default '{}',
  rrf_k           int     default 60,
  full_text_weight float  default 1,
  semantic_weight  float  default 1
) returns table (id text, content text, metadata jsonb, similarity float, fts_rank int, vec_rank int, score float)
language sql stable as $$
  with q as (
    select to_tsquery('simple', nullif(array_to_string(tsvector_to_array(to_tsvector('simple', query_text)), ' | '), '')) as tq
  ),
  full_text as (
    select c.id, row_number() over (order by ts_rank_cd(c.fts, q.tq) desc) as rank_ix
    from kb_chunks c, q
    where q.tq is not null and c.fts @@ q.tq and c.metadata @> filter
    order by rank_ix
    limit match_count * 3
  ),
  semantic as (
    select c.id, row_number() over (order by c.embedding <=> query_embedding) as rank_ix
    from kb_chunks c
    where c.metadata @> filter
    order by rank_ix
    limit match_count * 3
  )
  select c.id, c.content, c.metadata,
         1 - (c.embedding <=> query_embedding) as similarity,
         f.rank_ix::int, s.rank_ix::int,
         coalesce(full_text_weight / (rrf_k + f.rank_ix), 0) + coalesce(semantic_weight / (rrf_k + s.rank_ix), 0) as score
  from full_text f
  full outer join semantic s on f.id = s.id
  join kb_chunks c on c.id = coalesce(f.id, s.id)
  order by score desc
  limit match_count;
$$;

alter table kb_chunks enable row level security;

-- Tables other libraries create (LangGraph checkpoints, LangChain record
-- manager) come without RLS; lock them to the service role like the rest.
do $$
declare t text;
begin
  foreach t in array array['checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'checkpoint_migrations', 'upsertion_record']
  loop
    if to_regclass('public.' || t) is not null then
      execute format('alter table public.%I enable row level security', t);
    end if;
  end loop;
end $$;

notify pgrst, 'reload schema';
