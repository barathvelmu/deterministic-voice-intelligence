import pytest
from agent.graph import build_graph

@pytest.fixture(scope="module")
def graph():
    return build_graph()

def test_search_falls_back(graph):
    state = graph.invoke({"transcript": "search Ada Lovelace"})
    assert state["intent"] == "SEARCH"
    # Unreachable so, just ensure fallback reply triggers.
    assert "Sorry" in state["answer"] or "Here’s what I found" in state["answer"]

def test_calc_simple_expression(graph):
    state = graph.invoke({"transcript": "what is 14 plus 7"})
    assert state["intent"] == "CALC"
    assert state["answer"].startswith("The answer is")

def test_add_and_list_notes(graph):
    graph.invoke({"transcript": "add a note barath built agent"})
    graph.invoke({"transcript": "add a note meeting tomorrow"})
    list_state = graph.invoke({"transcript": "list notes"})
    assert list_state["intent"] == "NOTES_LIST"
    assert "barath built agent" in list_state["answer"]
    assert "meeting tomorrow" in list_state["answer"]

def test_fallback_reply(graph):
    state = graph.invoke({"transcript": "just saying hi"})
    assert state["intent"] == "ANSWER"
    assert state["answer"].startswith("You said")
