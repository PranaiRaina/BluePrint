"""A document search that finds nothing notifies the user and keeps going."""

from ManagerAgent.orchestrator import _continue_without_documents
from ManagerAgent.router_intelligence import IntentType
from RAG_PIPELINE.src.graph import NO_RESULTS_MESSAGE, reported_no_results


def test_recognises_the_miss_notice():
    assert reported_no_results(NO_RESULTS_MESSAGE)
    assert reported_no_results(f"\n{NO_RESULTS_MESSAGE}  ")


def test_does_not_mistake_an_answer_for_a_miss():
    assert not reported_no_results("Your April rent was $1,650.00.")
    assert not reported_no_results("")
    assert not reported_no_results(None)


def test_a_miss_adds_the_general_branch():
    intents = [IntentType.RAG]
    _continue_without_documents(NO_RESULTS_MESSAGE, intents)
    assert intents == [IntentType.RAG, IntentType.GENERAL]


def test_an_answer_leaves_the_intents_alone():
    intents = [IntentType.RAG]
    _continue_without_documents("Your April rent was $1,650.00.", intents)
    assert intents == [IntentType.RAG]


def test_general_is_not_added_twice():
    intents = [IntentType.RAG, IntentType.GENERAL]
    _continue_without_documents(NO_RESULTS_MESSAGE, intents)
    assert intents.count(IntentType.GENERAL) == 1


def test_other_branches_already_continue_the_turn():
    """STOCK is about to answer; a bolted-on GENERAL would just talk over it."""
    intents = [IntentType.RAG, IntentType.STOCK]
    _continue_without_documents(NO_RESULTS_MESSAGE, intents)
    assert intents == [IntentType.RAG, IntentType.STOCK]


def test_downstream_branches_are_told_not_to_repeat_the_notice():
    from ManagerAgent.orchestrator import enrich_query_with_context

    enriched = enrich_query_with_context(
        "what is AAPL trading at?",
        {"results": {"rag": NO_RESULTS_MESSAGE}},
    )
    assert "Do NOT repeat it" in enriched


def test_no_such_warning_when_the_documents_answered():
    from ManagerAgent.orchestrator import enrich_query_with_context

    enriched = enrich_query_with_context(
        "what is AAPL trading at?",
        {"results": {"rag": "Your April rent was $1,650.00."}},
    )
    assert "Do NOT repeat it" not in enriched


def test_appending_mid_iteration_is_picked_up():
    """The orchestrator appends while iterating; that has to actually run."""
    intents = [IntentType.RAG]
    visited = []
    for intent in intents:
        visited.append(intent)
        if intent == IntentType.RAG:
            _continue_without_documents(NO_RESULTS_MESSAGE, intents)

    assert visited == [IntentType.RAG, IntentType.GENERAL]


def test_general_agent_can_search_the_web():
    from CalcAgent.src.agent import general_agent

    assert general_agent.tools, "general agent has no tools"
    names = [getattr(t, "name", "") for t in general_agent.tools]
    assert any("tavily" in n for n in names), names
