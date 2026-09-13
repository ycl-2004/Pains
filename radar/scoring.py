"""Scoring vocabulary: the only place score dimensions, classes and confidence levels are defined.

Everything else (LLM prompts, ledger, web export) reads from here so the rubric cannot drift.
"""

from typing import Literal

from pydantic import BaseModel

SolutionClass = Literal["A", "B", "C", "D"]
Level = Literal["high", "medium", "low"]

SOLUTION_CLASSES: dict[str, str] = {
    "A": "基本已解决：原生功能、成熟产品或简单替代办法够用，不优先",
    "B": "部分解决：有方案，但价格、复杂度、可靠性或集成仍有缺口",
    "C": "解决得很差：多人反复靠手工、脚本、表格硬扛",
    "D": "新兴问题：新工作方式或平台变化带来的问题，成熟方案还没出现，置信度偏低",
}

LEVELS: dict[str, str] = {
    "high": "多个社区独立出现，且有行为证据（自建脚本、付费、手工流程）",
    "medium": "有重复出现或行为证据，但样本少、缺口未实测",
    "low": "证据集中在单帖或旧帖，或缺口未证实",
}


class Scores(BaseModel):
    """1–10 per dimension. `overall` is a judgment made after the contrarian case, not a formula."""

    frequency: int
    severity: int
    urgency: int
    existing_solution_gap: int
    willingness_to_pay: int
    momentum: int
    ease_of_validation: int
    overall: float


DIMENSIONS: dict[str, str] = {
    "frequency": "频率：多少独立的人、多少次在不同地方遇到",
    "severity": "严重度：一次发生损失多少钱、时间或风险",
    "urgency": "紧迫性：现在是否必须处理（截止日、迁移窗口）",
    "existing_solution_gap": "方案缺口：现有方案没覆盖的部分有多大（越大分越高）",
    "willingness_to_pay": "付费意愿：预算、招聘、已付费工具等信号（表态和成交分开看）",
    "momentum": "动能：是否有新变化在推动（平台变动、法规、时间表）",
    "ease_of_validation": "验证容易度：能否很快接触到用户、拿到样本、测出结果",
    "overall": "综合机会分：写完反方论证后的判断，不是加权平均",
}

assert set(DIMENSIONS) == set(Scores.model_fields), "DIMENSIONS must describe exactly the Scores fields"

# A score change at or above this triggers a fresh existing-solution check.
SIGNIFICANT_OVERALL_CHANGE = 1.0
# A demoted cluster that new evidence lifts to at least this overall goes back to "watch".
REVIVE_OVERALL = 5.0


def render_rubric() -> str:
    """Rubric text injected into LLM prompts, generated from the definitions above."""
    lines = ["评分维度（1–10）："]
    lines += [f"- {name}：{text}" for name, text in DIMENSIONS.items()]
    lines.append("现有方案分类：")
    lines += [f"- {key}：{text}" for key, text in SOLUTION_CLASSES.items()]
    lines.append("置信度（痛点置信度 pain_confidence 与商业缺口置信度 gap_confidence 分开判断）：")
    lines += [f"- {key}：{text}" for key, text in LEVELS.items()]
    return "\n".join(lines)


def clamp_scores(scores: Scores) -> Scores:
    """Keep model output inside the 1–10 rubric instead of trusting it blindly."""
    data = {name: min(10, max(1, value)) for name, value in scores.model_dump().items()}
    data["overall"] = round(data["overall"] * 2) / 2
    return Scores(**data)


def is_significant_change(before: float | None, after: float) -> bool:
    return before is None or abs(after - before) >= SIGNIFICANT_OVERALL_CHANGE
