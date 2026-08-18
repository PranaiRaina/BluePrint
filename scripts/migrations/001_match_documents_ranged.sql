-- Date-scoped variant of match_documents.
--
-- Added alongside the original rather than replacing it: when a query names no
-- period there must be NO date predicate at all, and the caller routes to the
-- original for that. Keeping both also means a bad deploy cannot take the
-- existing search path down.
--
-- The NULL rule is the whole point of the OR. A document with no period is not
-- out of range, it is timeless - credit card terms, a KYC record, an IRA
-- disclosure answer a question asked about any month. `->>` returns SQL NULL
-- both when the key is absent (chunks ingested before metadata existed) and
-- when it holds JSON null (prose), so one test covers both.
--
-- Matching is OVERLAP, not containment: a Jan-Mar quarterly statement must
-- match a question about March even though it is not contained by March.

create or replace function public.match_documents_ranged(
  query_embedding vector,
  match_threshold double precision,
  match_count integer,
  filter jsonb default '{}'::jsonb,
  period_from integer default null,
  period_to integer default null
)
returns table(id uuid, content text, metadata jsonb, similarity double precision)
language plpgsql
stable
as $function$
begin
  return query(
    select
      documents.id,
      documents.content,
      documents.metadata,
      1 - (documents.embedding <=> query_embedding) as similarity
    from documents
    where 1 - (documents.embedding <=> query_embedding) > match_threshold
      and documents.metadata @> filter
      and (
        -- undated documents are always eligible
        (documents.metadata->>'period_start_ym') is null
        or (documents.metadata->>'period_end_ym') is null
        -- or the document's span overlaps the requested span
        or (
          (documents.metadata->>'period_start_ym')::integer
              <= coalesce(period_to, 999912)
          and (documents.metadata->>'period_end_ym')::integer
              >= coalesce(period_from, 1)
        )
      )
    order by documents.embedding <=> query_embedding
    limit match_count
  );
end;
$function$;
