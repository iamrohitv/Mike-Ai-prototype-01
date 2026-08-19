def make_plan(request, tools):
    return {
        "request": request,
        "steps": [
            {"step": "understand", "action": "parse the request"},
            {"step": "retrieve_context", "action": "pull relevant memory"},
            {"step": "reason", "action": "reason about the request"},
            {"step": "execute", "action": _tool_step(request, tools)},
            {"step": "verify", "action": "verify the result"},
            {"step": "remember", "action": "remember the outcome"},
            {"step": "report", "action": "report what happened"},
        ],
    }


def _tool_step(request, tools):
    for tool in tools:
        if tool.matches(request):
            return f"use tool: {tool.name}"
    return "no tool needed; respond directly"


def format_plan(plan):
    lines = [f"Plan for: {plan['request']}"]
    for i, step in enumerate(plan["steps"], start=1):
        lines.append(f"  {i}. {step['step']} - {step['action']}")
    return "\n".join(lines)