from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
import sqlite3
from datetime import date, timedelta

from langchain_core.messages import AIMessage

from backend import config

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from backend.agent.nodes.call import (
    after_agent, after_tools, agent_node, client_turn_node, tools_node,
)
from backend.agent.nodes.scan import scan_node
from backend.agent.state import CollectionState
from backend.agent.tools import check_policy

def plan_node(state: CollectionState) -> dict:
    overdue = state.get("overdue", [])
    target = state.get("target_invoice_id")
    if target:
        overdue = [i for i in overdue if i["id"] == target]
    if not overdue:
        return {"current": None}
    invoice = overdue[0]
    d = invoice["days_overdue"]
    tone = "friendly" if d < 15 else "firm" if d < 30 else "urgent"
    return {"current": invoice, "tone": tone}


def policy_node(state: CollectionState) -> dict:
    return {
        "needs_approval": state.get("outcome") == "needs_approval"
        and not state.get("followup_sent")
    }


def approval_node(state: CollectionState) -> dict:
    decision = interrupt(
        {
            "type": "approval",
            "invoice_id": state["current"]["id"],
            "request": state.get("pending_request") or {"type": "unspecified", "value": None},
            "message": "Client asked for something outside policy. Approve?",
        }
    )
    return {"approved": bool(decision)}


def post_call_node(state: CollectionState) -> dict:
    inv = state["current"]
    name = (inv["client_name"] or "there").split()[0]
    update = {"call_done": False, "awaiting_reply": False}
    approved = state.get("approved")

    if (
        state.get("outcome") == "needs_approval"
        and approved is not None
        and not state.get("followup_sent")
    ):
        req = state.get("pending_request") or {}
        days = int(req.get("value") or 0)
        if approved and req.get("type") == "extension_days" and days:
            new_date = date.today() + timedelta(days=days)
            text = (f"Hi {name}, good news, the freelancer approved your request. "
                    f"Can you confirm you'll pay invoice {inv['number']} by "
                    f"{new_date.strftime('%B %d')}?")
        elif approved:
            text = f"Hi {name}, good news, the freelancer approved your request."
        else:
            limit = config.POLICY["max_extension_days"]
            text = (f"Hi {name}, the freelancer couldn't approve that. "
                    f"They can offer up to {limit} days instead. Would that work for you?")
        update.update(
            messages=[AIMessage(content=text)],
            awaiting_reply=True,
            followup_sent=True,
        )

    print(f"[post_call] {inv['number']} outcome={state.get('outcome')} approved={approved}")
    return update

def build_graph(checkpointer):
    b = StateGraph(CollectionState)
    b.add_node("scan", scan_node)
    b.add_node("plan", plan_node)
    b.add_node("agent", agent_node)
    b.add_node("tools", tools_node)
    b.add_node("client_turn", client_turn_node)
    b.add_node("policy_check", policy_node)
    b.add_node("approval", approval_node)
    b.add_node("post_call", post_call_node)


    b.add_edge(START, "scan")
    b.add_edge("scan", "plan")
    b.add_conditional_edges(
        "plan", lambda s: "agent" if s.get("current") else END,
        {"agent": "agent", END: END},
    )
    b.add_conditional_edges(
        "agent", after_agent, {"tools": "tools", "client_turn": "client_turn"}
    )
    b.add_edge("client_turn", "agent")
    b.add_conditional_edges(
        "tools", after_tools, {"agent": "agent", "policy_check": "policy_check"}
    )
    b.add_conditional_edges(
        "policy_check",
        lambda s: "approval" if s.get("needs_approval") else "post_call",
        {"approval": "approval", "post_call": "post_call"},
    )
    b.add_edge("approval", "post_call")
    b.add_conditional_edges(
        "post_call",
        lambda s: "client_turn" if s.get("awaiting_reply") else END,
        {"client_turn": "client_turn", END: END},
    )    
    return b.compile(checkpointer=checkpointer)

def get_graph():
    conn = sqlite3.connect("calls.db", check_same_thread=False)
    return build_graph(SqliteSaver(conn))

graph = build_graph(MemorySaver())

if __name__ == "__main__":
    cfg = {"configurable": {"thread_id": "demo-1"}}
    result = graph.invoke({}, cfg)
    while result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        if payload.get("type") == "client_turn":
            print(f"\nAgent: {payload['agent_says']}")
            resume = input("Client: ")
        else:
            print(f"\nOWNER APPROVAL NEEDED: {payload['request']}")
            resume = input("Approve? (y/n): ").lower().startswith("y")
        result = graph.invoke(Command(resume=resume), cfg)
    print("\nDone. outcome:", result.get("outcome"), "| promise:", result.get("promise_date"))