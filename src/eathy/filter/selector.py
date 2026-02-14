"""AI 筛选器 — 用 Claude 从候选文章中选出最适合 Eathy 账号的 1 条"""

from __future__ import annotations

import json
import re

from ..models import Article, AccountProfile, ContentCategory, FilterResult
from ..providers.base import AIProvider


_SYSTEM = """你是 Eathy App 的内容运营专家，负责为小红书账号筛选最适合的健康资讯。
根据历史数据，品牌拆解类内容（如快餐品牌热量分析）表现最好，应优先考虑。
你的输出必须是合法的 JSON，不要加任何额外说明。"""

_PROMPT = """## Eathy 账号人设
- 领域: {domain}
- 人设: {persona}
- 目标受众: {target_audience}
- 偏好角度: {preferred_angles}
- 禁止话题: {forbidden_topics}

## 候选资讯（共 {count} 条）

{articles_text}

## 任务
从以上 {count} 条资讯中，选出 1 条最适合 Eathy 小红书账号发布的资讯。

评估维度：
1. 涉及知名品牌（快餐/奶茶/零食品牌）的资讯优先（权重最高）
   — 历史数据：品牌拆解类平均 227 赞，纯科普仅 3 赞
2. 与"成分分析/配料表解读"的相关性
3. 小红书用户的关注度和互动潜力
4. 能否自然关联到 Eathy App 的"扫配料表"功能
5. 时效性和话题热度
6. 不涉及禁止话题
7. 内容必须与中国用户相关（避免纯海外 FDA 召回等低共鸣内容）

输出 JSON（严格遵守）：
{{
  "selected_index": 0,
  "category": "品牌拆解",
  "relevance_score": 0.85,
  "key_points": ["关键要点1", "关键要点2", "关键要点3"],
  "image_subject": "English description for image generation, specific visual subject",
  "reasoning": "选择这条资讯的理由"
}}

category 只能是以下五个值之一：成分分析、食品避雷、健康替代、热点话题、品牌拆解"""


_CATEGORY_MAP = {
    "成分分析": ContentCategory.INGREDIENT_ANALYSIS,
    "食品避雷": ContentCategory.FOOD_WARNING,
    "健康替代": ContentCategory.HEALTHY_ALTERNATIVE,
    "热点话题": ContentCategory.TRENDING_TOPIC,
    "品牌拆解": ContentCategory.BRAND_TEARDOWN,
}


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON，兼容 markdown 代码块包裹"""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"LLM 输出中找不到 JSON: {text[:300]}")
    return json.loads(cleaned[start:end])


def _format_articles(articles: tuple[Article, ...]) -> str:
    lines = []
    for i, a in enumerate(articles):
        lines.append(f"[{i}] 标题: {a.title}")
        lines.append(f"    来源: {a.source_name} ({a.language})")
        lines.append(f"    摘要: {a.summary[:200]}")
        lines.append("")
    return "\n".join(lines)


from ..prompts import FilterPrompt

class ArticleSelector:
    def __init__(self, provider: AIProvider, prompt_config: FilterPrompt) -> None:
        self._provider = provider
        self._prompt_config = prompt_config

    async def select(
        self,
        articles: tuple[Article, ...],
        profile: AccountProfile,
    ) -> FilterResult:
        """从候选文章中用 Claude 筛选出最佳 1 条"""
        if not articles:
            raise ValueError("候选文章列表为空，无法筛选")

        prompt = self._prompt_config.user_prompt.format(
            domain=profile.domain,
            persona=profile.persona,
            target_audience=profile.target_audience,
            preferred_angles="、".join(profile.preferred_angles) or "成分揭秘、避雷指南",
            forbidden_topics="、".join(profile.forbidden_topics) or "无",
            count=len(articles),
            articles_text=_format_articles(articles),
        )

        raw = await self._provider.generate(prompt, system=self._prompt_config.system_prompt)
        data = _extract_json(raw)

        selected_index = int(data.get("selected_index", 0))
        if selected_index >= len(articles):
            selected_index = 0

        category_str = data.get("category", "成分分析")
        category = _CATEGORY_MAP.get(category_str, ContentCategory.INGREDIENT_ANALYSIS)

        return FilterResult(
            selected_article=articles[selected_index],
            category=category,
            relevance_score=float(data.get("relevance_score", 0.0)),
            key_points=tuple(data.get("key_points", [])),
            image_subject=data.get("image_subject", "healthy food ingredient analysis"),
            reasoning=data.get("reasoning", ""),
        )
