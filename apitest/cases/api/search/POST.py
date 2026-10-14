from apitest.common import json_body, request


def run(context):
    body = json_body(request(context, "POST", "/api/search", token=context["tokens"]["student_a"],
                            payload={"q": context["search_term"], "mode": "keyword"}))
    assert isinstance(body.get("hits"), list), "search response must contain hits list"
    return "Keyword search returned a result list for a synthetic or seeded term."
