"""Verify LangGraph is working with a minimal workflow."""
from langgraph.graph import StateGraph
from typing import TypedDict
from research_swarm.logger import logger

class State(TypedDict):
    message: str
    count: int

def node_a(state: State) -> State:
    logger.info(f"Node A: {state['message']}")
    return {"message": state["message"], "count": state["count"] + 1}

def node_b(state: State) -> State:
    logger.info(f"Node B: {state['message']}")
    return {"message": state["message"] + " (processed)", "count": state["count"] + 1}

def test_basic_workflow():
    """Test a simple 2-node workflow."""
    workflow = StateGraph(State)
    workflow.add_node("node_a", node_a)
    workflow.add_node("node_b", node_b)
    workflow.add_edge("node_a", "node_b")
    workflow.set_entry_point("node_a")
    workflow.set_finish_point("node_b")

    app = workflow.compile()

    result = app.invoke({"message": "Hello LangGraph", "count": 0})

    assert result["message"] == "Hello LangGraph (processed)"
    assert result["count"] == 2
    logger.success("✓ LangGraph workflow test passed!")

if __name__ == "__main__":
    test_basic_workflow()
