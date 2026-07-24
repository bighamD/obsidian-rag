from obsidian_rag.core.skills.matcher import SkillMatcher
from obsidian_rag.core.skills.policy import need_llm_skill_router
from obsidian_rag.core.skills.schemas import SkillCandidate, SkillManifest


def test_exact_trigger_directly_selects_skill_without_llm_router():
    candidates = SkillMatcher().match(
        "生鸡肉需要清洗吗？",
        [
            SkillManifest(
                name="food-safety",
                description="处理食品安全和交叉污染问题。",
                triggers=["生鸡肉", "交叉污染"],
                path="food-safety/SKILL.md",
            ),
            SkillManifest(
                name="answer-quality",
                description="检查答案覆盖率。",
                triggers=["答案质检"],
                path="answer-quality/SKILL.md",
            ),
        ],
    )

    decision = need_llm_skill_router(candidates)

    assert decision.path == "direct"
    assert decision.selected_skill_names == ["food-safety"]


def test_close_candidates_require_llm_router():
    decision = need_llm_skill_router(
        [
            SkillCandidate(
                name="answer-quality",
                score=0.79,
                bm25_score=0.9,
                overlap_score=0.7,
                trigger_score=0,
            ),
            SkillCandidate(
                name="fact-checking",
                score=0.76,
                bm25_score=0.85,
                overlap_score=0.7,
                trigger_score=0,
            ),
        ]
    )

    assert decision.path == "llm_router"
    assert decision.score_margin == 0.03


def test_low_scores_do_not_call_llm_router():
    decision = need_llm_skill_router(
        [
            SkillCandidate(
                name="unrelated",
                score=0.12,
                bm25_score=0.2,
                overlap_score=0,
                trigger_score=0,
            )
        ]
    )

    assert decision.path == "no_skill"
