"""Migrate chunk metadata from a single `period_ym` to a start/end range.

    uv run python scripts/backfill_period_range.py --dry-run
    uv run python scripts/backfill_period_range.py

Sets period_start_ym = period_end_ym = period_ym and drops period_ym.

That is correct for every single-month document, which is most of them. It is
NOT correct for a document that always covered several months - a quarterly
brokerage statement backfills to "January..January" because January is the only
month the old field ever held. Those need re-ingesting to get a true range; this
script lists them at the end so you know which.
"""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from RAG_PIPELINE.src.ingestion import get_supabase_client  # noqa: E402

# Anything covering more than one month cannot be recovered from a single int.
MULTI_MONTH_TYPES = ("brokerage_statement", "tax_document")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    supabase = get_supabase_client()
    rows = supabase.table("documents").select("id,metadata").execute().data

    todo = [r for r in rows if "period_ym" in (r.get("metadata") or {})]
    print(f"{len(rows)} chunks, {len(todo)} still on the old field")
    if not todo:
        return

    suspect = set()
    for row in todo:
        meta = dict(row["metadata"])
        period = meta.pop("period_ym", None)
        meta["period_start_ym"] = period
        meta["period_end_ym"] = period

        if period is not None and meta.get("doc_type") in MULTI_MONTH_TYPES:
            suspect.add(meta.get("source", "?"))

        if not args.dry_run:
            supabase.table("documents").update({"metadata": meta}).eq(
                "id", row["id"]
            ).execute()

    verb = "would update" if args.dry_run else "updated"
    print(f"{verb} {len(todo)} chunks")

    if suspect:
        print(
            "\nRe-ingest these - they may cover more than one month, and a "
            "backfill cannot know the real end:"
        )
        for name in sorted(suspect):
            print(f"  {name}")


if __name__ == "__main__":
    sys.exit(main())
