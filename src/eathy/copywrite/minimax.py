"""MiniMax 文案生成器 — 生成小红书标题、正文和话题标签"""

from __future__ import annotations

import re
import json

from ..models import AccountProfile, ContentCategory, FilterResult, XhsCopywrite
from ..providers.base import AIProvider


_SYSTEM = """你是 Eathy App 的小红书运营编辑，擅长写爆款健康饮食内容。
历史爆款数据：品牌拆解标题平均 227 赞，纯科普仅 3 赞。你的标题必须让人忍不住点进来。
你输出的 JSON 格式必须严格符合要求，不要加任何额外说明。"""

_PROMPT = """## 账号人设
- 名称: {name}
- 领域: {domain}
- 人设: {persona}
- 目标受众: {target_audience}
- 语气风格: {tone}
- App 引导语: {app_download_cta}
- 结尾 CTA: {call_to_action}

## 资讯素材
- 标题: {article_title}
- 分类: {category}
- 关键要点:
{key_points_text}

## 创作要求
1. **标题**：不超过 {title_max} 字，使用以下爆款公式之一：
   - "@品牌名 + 反常识发现"（如「@肯德基"解剖"报告：别光看热量！」）
   - "具体数字 + 惊叹"（如「这货才450卡？」）
   - "情绪钩子 + 实用信息"（如「别再吃草了❗️」）
   标题中尽量包含具体品牌名或产品名，增加搜索流量
2. **正文**：不超过 {body_max} 字，小红书风格：
   - 开头直接抓眼球，前 3 行是关键
   - 短段落（每段 2-3 行），适当空行
   - 适当使用 emoji（不要过度）
   - 核心信息清晰突出
   - 如果是品牌拆解类：重点拆解具体数据（热量/成分/价格），用对比突出反差
   - 避免纯知识科普，要有观点和态度
   - 自然提及"用 Eathy App 扫一扫配料表"（1次即可）
   - 结尾用 CTA 引导收藏/关注
3. **话题标签**：{hashtag_count} 个，组合：领域词 + 内容词 + 人群词 + 热门词

输出 JSON（严格遵守）：
{{
  "title": "标题（<= {title_max} 字）",
  "body": "正文内容（<= {body_max} 字）",
  "hashtags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}}"""


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"MiniMax 输出中找不到 JSON: {text[:300]}")
    return json.loads(cleaned[start:end])


from ..prompts import CopywriteStyle

class CopywriteGenerator:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        filter_result: FilterResult,
        profile: AccountProfile,
        style: CopywriteStyle,
    ) -> XhsCopywrite:
        """
        生成小红书文案。

        Args:
            filter_result: AI 筛选结果
            profile: 账号人设
            style: 文案风格
        """
        key_points_text = "\n".join(f"  - {p}" for p in filter_result.key_points)

        prompt = style.user_prompt.format(
            name=profile.name,
            domain=profile.domain,
            persona=profile.persona,
            target_audience=profile.target_audience,
            tone=profile.tone,
            app_download_cta=profile.app_download_cta,
            call_to_action=profile.call_to_action,
            article_title=filter_result.selected_article.title,
            category=filter_result.category.value,
            key_points_text=key_points_text,
            title_max=profile.title_max_length,
            body_max=profile.body_max_length,
            hashtag_count=profile.hashtag_count,
        )

        raw = await self._provider.generate(prompt, system=style.system_prompt)
        data = _extract_json(raw)

        title = data.get("title", "").strip()
        body = data.get("body", "").strip()
        hashtags = data.get("hashtags", [])

        # 强制截断（兜底保护）
        if len(title) > profile.title_max_length:
            title = title[:profile.title_max_length]
        if len(body) > profile.body_max_length:
            body = body[:profile.body_max_length]

        return XhsCopywrite(
            title=title,
            body=body,
            hashtags=tuple(hashtags[:profile.hashtag_count]),
            category=filter_result.category,
            source_article_id=filter_result.selected_article.id,
        )
