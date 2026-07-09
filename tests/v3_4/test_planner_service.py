from obsidian_rag.v3_4.planner.service import PlannerService, parse_plan_json
from obsidian_rag.v3_4.schemas import PlanRequest


class FakePlannerChatClient:
    def __init__(self, output: str):
        self.output = output
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return self.output


class FailingPlannerChatClient:
    def complete(self, messages):
        raise RuntimeError("connection failed")


def test_planner_parses_multi_search_plan_from_llm_json():
    chat = FakePlannerChatClient(
        """
        {
          "goal": "整理食品安全建议",
          "steps": [
            {"id": "s1", "kind": "search", "query": "生鸡肉 清洗 交叉污染", "reason": "查找生鸡肉处理建议"},
            {"id": "s2", "kind": "search", "query": "厨房 清洁 洗手 抹布", "reason": "查找厨房清洁建议"},
            {"id": "s3", "kind": "synthesize", "instruction": "综合检索结果形成分主题回答", "depends_on": ["s1", "s2"]}
          ]
        }
        """
    )
    service = PlannerService(chat_client=chat)

    response = service.plan(
        PlanRequest(question="帮我总结生鸡肉处理和厨房清洁建议", top_k=5, mode="hybrid", max_steps=4)
    )

    assert response.question == "帮我总结生鸡肉处理和厨房清洁建议"
    assert response.plan.goal == "整理食品安全建议"
    assert [step.kind for step in response.plan.steps] == ["search", "search", "synthesize"]
    assert response.plan.steps[0].query == "生鸡肉 清洗 交叉污染"
    assert response.graph_path == ["build_prompt", "call_planner", "parse_plan"]
    assert [step.node_name for step in response.trace] == response.graph_path
    assert response.trace[0].step_type == "planner_prompt"
    assert response.trace[1].step_type == "planner_output"
    assert chat.messages[0][0]["role"] == "system"


def test_planner_repairs_invalid_llm_output_to_clarify_plan():
    response = parse_plan_json("不是 JSON", question="这个呢")

    assert response.goal == "澄清用户问题"
    assert response.steps[0].kind == "clarify"
    assert response.steps[0].instruction == "请用户补充更明确的问题范围。"


def test_planner_without_llm_returns_clarify_plan():
    service = PlannerService(chat_client=None)

    response = service.plan(PlanRequest(question="这个呢"))

    assert response.plan.steps[0].kind == "clarify"
    assert response.graph_path == ["build_prompt", "call_planner", "parse_plan"]
    assert response.trace[0].step_type == "planner_error"
    assert "没有配置" in response.trace[0].reason


def test_planner_client_exception_returns_error_trace_instead_of_raising():
    service = PlannerService(chat_client=FailingPlannerChatClient())

    response = service.plan(PlanRequest(question="今天深圳天气怎么样"))

    assert response.plan.steps[0].kind == "clarify"
    assert response.graph_path == ["build_prompt", "call_planner", "parse_plan"]
    assert response.trace[0].step_type == "planner_error"
    assert "LLM Planner 调用失败" in response.trace[0].reason
