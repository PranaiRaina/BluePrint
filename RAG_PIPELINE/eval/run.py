"""Retrieval-only eval. Run against a user who has the three fixture statements ingested.

    uv run python -m RAG_PIPELINE.eval.run <user_id>
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from RAG_PIPELINE.src.ingestion import perform_similarity_search  # noqa: E402

CASES_PATH = os.path.join(os.path.dirname(__file__), "questions.json")


def _rank_of(results, expect_source):
    """1-based rank of the first result whose source matches, or None."""
    for i, (doc, _score) in enumerate(results, start=1):
        if doc.metadata.get("source") == expect_source:
            return i
    return None


def run_eval(user_id: str, k: int = 10, threshold: float = 0.0) -> dict:
    with open(CASES_PATH) as f:
        cases = json.load(f)

    rows = []
    for case in cases:
        results = perform_similarity_search(
            query=case["question"], user_id=user_id, k=k, threshold=threshold
        )
        rank = _rank_of(results, case["expect_source"])
        top_text = results[0][0].page_content if results else ""
        found = [s for s in case["expect_contains"] if s in top_text]
        rows.append(
            {
                "question": case["question"],
                "expect_source": case["expect_source"],
                "rank": rank,
                "top_score": round(results[0][1], 4) if results else None,
                "value_in_top_chunk": len(found) == len(case["expect_contains"]),
                "passed": rank == 1,
            }
        )

    total = len(rows) or 1
    return {
        "cases": rows,
        # Right document retrieved first.
        "pass_rate": sum(1 for r in rows if r["passed"]) / total,
        # Right *chunk* retrieved first - the chunk actually holds the answer.
        # This is the metric that decides whether the bot can answer, and it is
        # the one within-document ranking moves.
        "answer_rate": sum(1 for r in rows if r["value_in_top_chunk"]) / total,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: python -m RAG_PIPELINE.eval.run <user_id>")
        raise SystemExit(1)

    report = run_eval(sys.argv[1])
    print(f"{'rank':>4}  {'score':>7}  {'val':>3}  question")
    print("-" * 78)
    for r in report["cases"]:
        rank = r["rank"] if r["rank"] is not None else "-"
        score = f"{r['top_score']:.4f}" if r["top_score"] is not None else "-"
        val = "y" if r["value_in_top_chunk"] else "n"
        print(f"{rank:>4}  {score:>7}  {val:>3}  {r['question']}")
    print("-" * 78)
    print(f"right document first : {report['pass_rate']:.0%}")
    print(f"answer in top chunk  : {report['answer_rate']:.0%}")


if __name__ == "__main__":
    main()
