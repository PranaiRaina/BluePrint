"""Every branch must see what earlier branches already found.

The bug this pins: a query like "what was my credit card payment and what does
it mean" routes to [RAG, GENERAL]. RAG reads the amount out of the user's
uploaded statement; GENERAL then ran with only the raw query and replied "I do
not have access to your personal financial accounts... upload a bank statement".
Synthesis received one correct finding and one confident refusal, with no rule
saying which wins, so it picked non-deterministically.
"""

import inspect

from ManagerAgent import orchestrator
from ManagerAgent.orchestrator import enrich_query_with_context


# --- enrich_query_with_context is pure; test it directly -------------------

def test_rag_results_are_labelled_as_documents_not_holdings():
    out = enrich_query_with_context(
        "what was my payment", {"results": {"rag": "A payment of $900.00 was made."}}
    )
    assert "$900.00" in out
    # "USER'S CURRENT HOLDINGS" mislabels a bank statement as a portfolio.
    assert "HOLDINGS" not in out.upper()
    assert "DOCUMENT" in out.upper()


def test_every_branch_result_is_carried_not_just_rag_and_stock():
    out = enrich_query_with_context(
        "q",
        {"results": {"calculator": "FV = $1,234", "general": "some analysis"}},
    )
    assert "FV = $1,234" in out
    assert "some analysis" in out


def test_empty_results_are_skipped():
    # A branch that produced nothing must not contribute an empty labelled block.
    out = enrich_query_with_context("q", {"results": {"rag": "", "stock": "   "}})
    assert out == "q"


def test_no_context_returns_the_bare_query():
    assert enrich_query_with_context("q", {"results": {}}) == "q"
    assert enrich_query_with_context("q", {}) == "q"


def test_context_forbids_the_no_access_disclaimer():
    out = enrich_query_with_context("q", {"results": {"rag": "A payment of $900.00."}})
    lowered = out.lower()
    assert "do not tell the user you have no access" in lowered
    assert "upload" in lowered  # ...and don't ask for documents already present


# --- branch wiring ---------------------------------------------------------

def test_general_and_calculator_branches_receive_prior_findings():
    for fn in (orchestrator.orchestrate_stream, orchestrator.orchestrate):
        source = inspect.getsource(fn)
        # Split on the branch markers, not the bare enum names - those also
        # appear in the ORDER_PRIORITY dict at the top of each function.
        _, _, after_calc = source.partition("intent == IntentType.CALCULATOR")
        calc_branch, _, general_branch = after_calc.partition(
            "intent == IntentType.GENERAL"
        )

        assert "enrich_query_with_context" in calc_branch, (
            f"{fn.__name__}: CALCULATOR branch answers blind - it never sees what "
            "RAG or STOCK already found."
        )
        assert "enrich_query_with_context" in general_branch, (
            f"{fn.__name__}: GENERAL branch answers blind. This is what made the "
            "agent claim it had no access to a statement RAG had just read."
        )


# --- synthesis prompt ------------------------------------------------------

def test_synthesis_prompt_is_defined_once():
    for fn in (orchestrator.synthesize_response, orchestrator.synthesize_response_stream):
        source = inspect.getsource(fn)
        assert "_build_synthesis_prompt(" in source, (
            f"{fn.__name__} inlines its own copy of the prompt - the two copies drift."
        )
        assert "You are a Master Financial Orchestrator" not in source, (
            f"{fn.__name__} still carries an inline prompt body."
        )


def test_synthesis_prompt_makes_document_findings_authoritative():
    prompt = orchestrator.ORCHESTRATOR_SYNTHESIS_PROMPT.lower()
    # The old rule only covered "do I own" questions, so a payment question had
    # no precedence rule at all.
    assert '"do i own"' not in prompt
    assert "authoritative" in prompt
    assert "drop" in prompt  # drop the disclaimer when another agent has the data


def test_synthesis_prompt_citation_example_is_not_backticked():
    import re

    # `[label](url) renders as inline code, not a link - the model copies the
    # backticks verbatim.
    assert not re.search(r"`\[[^\]]*\]\(", orchestrator.ORCHESTRATOR_SYNTHESIS_PROMPT)
