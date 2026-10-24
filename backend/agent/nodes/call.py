import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import interrupt

from backend import config
from backend.agent.mock_llm import mock_reply
from backend.agent.prompts import system_prompt
from backend.agent.tools import call_tools

TOOLS = call_tools()
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

llm = None
if not config.MOCK_LLM:
    llm = ChatGoogleGenerativeAI(
        model=config.LLM_MODEL, api_key=config.GOOGLE_API_KEY
    ).bind_tools(TOOLS)

GOODBYES = {
    "needs_approval": "I'll check with the freelancer and get back to you. Thanks for your time.",
    "promised": "Thank you, I've noted that. Have a great day.",
    "paid_now": "Thank you for the payment. Have a great day.",
    "refused": "Understood, I'll pass this on to the freelancer. Take care.",
    "no_answer": "I'll try again later. Goodbye.",
}


def as_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        p.get("text", "") if isinstance(p, dict) else str(p) for p in content
    )


def agent_node(state: dict) -> dict:
    messages = list(state.get("messages", []))
    new = []
    if not messages:
        opener = HumanMessage(content="(The client picked up the phone.)")
        messages.append(opener)
        new.append(opener)
    if config.MOCK_LLM:
        reply = mock_reply(state, messages)
    else:
        system = SystemMessage(content=system_prompt(state["current"], state["tone"]))
        reply = llm.invoke([system, *messages])
    return {"messages": [*new, reply]}


def tools_node(state: dict) -> dict:
    last = state["messages"][-1]
    results, update = [], {}
    for call in last.tool_calls:
        name, args = call["name"], call["args"]
        try:
            output = TOOLS_BY_NAME[name].invoke(args)
        except Exception as e:
            output = f"Tool error: {e}"

        if name == "check_policy" and isinstance(output, dict) and not output.get("allowed"):
            update["pending_request"] = {
                "type": args.get("request_type"),
                "value": args.get("value"),
            }
        if name == "record_promise" and str(output).startswith("Recorded"):
            update["promise_date"] = args.get("promise_date")
            update["pending_request"] = None
        if name == "end_call":
            update["call_done"] = True
            update["outcome"] = args.get("outcome", "")
            if args.get("outcome") == "needs_approval" and args.get("request_type"):
                update["pending_request"] = {
                    "type": args["request_type"],
                    "value": args.get("request_value"),
                }

        results.append(
            ToolMessage(
                content=json.dumps(output, default=str),
                tool_call_id=call["id"],
                name=name,
            )
        )

    end = next((c for c in last.tool_calls if c["name"] == "end_call"), None)
    if end and not as_text(last.content).strip():
        outcome = end["args"].get("outcome", "")
        results.append(
            AIMessage(content=GOODBYES.get(outcome, "Thanks for your time. Goodbye."))
        )
    update["messages"] = results
    return update


def client_turn_node(state: dict) -> dict:
    agent_said = as_text(state["messages"][-1].content)
    reply = interrupt({"type": "client_turn", "agent_says": agent_said})
    return {"messages": [HumanMessage(content=reply)]}


def after_agent(state: dict) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else "client_turn"


def after_tools(state: dict) -> str:
    return "policy_check" if state.get("call_done") else "agent"