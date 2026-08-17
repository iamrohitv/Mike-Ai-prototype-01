def make_plan(request, tools):
    plan = ["understand", "retrieve context"]
    plan.append("reason about the request")

    for tool in tools:
        if tool.matches(request):
            plan.append(f"use tool: {tool.name}")
            break

    plan.append("verify the result")
    plan.append("remember the outcome")
    plan.append("report")
    return plan