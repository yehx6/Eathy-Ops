"""提示词与风格管理模块"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Article
from .providers.base import AIProvider


@dataclass(frozen=True)
class CopywriteStyle:
    id: str
    name: str
    description: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class ImageStyle:
    id: str
    name: str
    description: str
    prompt: str


@dataclass(frozen=True)
class FilterPrompt:
    system_prompt: str
    user_prompt: str


class StyleManager:
    """管理提示词风格库，并提供 AI 智能选择功能"""

    def __init__(self, config_prompts: dict[str, str], provider: AIProvider) -> None:
        self._provider = provider
        self._prompts_cfg = config_prompts
        
        self._filter_prompt: FilterPrompt | None = None
        self._copywrite_styles: list[CopywriteStyle] = []
        self._image_styles: list[ImageStyle] = []
        
        self._load_prompts()

    def _load_prompts(self) -> None:
        """从 YAML 文件加载提示词"""
        # Filter
        filter_path = Path(self._prompts_cfg["filter"])
        if filter_path.exists():
            data = yaml.safe_load(filter_path.read_text(encoding="utf-8"))
            self._filter_prompt = FilterPrompt(
                system_prompt=data.get("system_prompt", ""),
                user_prompt=data.get("user_prompt", ""),
            )

        # Copywrite Styles
        copy_path = Path(self._prompts_cfg["copywrite"])
        if copy_path.exists():
            data = yaml.safe_load(copy_path.read_text(encoding="utf-8"))
            for style in data.get("styles", []):
                self._copywrite_styles.append(CopywriteStyle(**style))

        # Image Styles
        img_path = Path(self._prompts_cfg["image"])
        if img_path.exists():
            data = yaml.safe_load(img_path.read_text(encoding="utf-8"))
            for style in data.get("styles", []):
                self._image_styles.append(ImageStyle(**style))

    def get_filter_prompt(self) -> FilterPrompt:
        if not self._filter_prompt:
            raise RuntimeError("Filter prompt not loaded")
        return self._filter_prompt

    async def select_best_styles(self, article: Article) -> tuple[CopywriteStyle, ImageStyle]:
        """
        根据文章内容，智能选择最合适的文案风格和图片风格。
        """
        if not self._copywrite_styles or not self._image_styles:
            raise RuntimeError("Styles not loaded")

        # 构造选择 Prompt
        copy_options = "\n".join(
            f"- {s.id} ({s.name}): {s.description}" for s in self._copywrite_styles
        )
        img_options = "\n".join(
            f"- {s.id} ({s.name}): {s.description}" for s in self._image_styles
        )

        prompt = f"""
你是一个资深的内容主编。请根据以下文章摘要，为这篇小红书笔记选择最合适的文案风格和配图风格。

文章标题: {article.title}
文章摘要: {article.summary[:500]}

可选文案风格:
{copy_options}

可选配图风格:
{img_options}

请分析文章的调性（是严肃科普、情绪宣泄、还是生活方式推荐？），做出选择。
返回 JSON 格式：
{{
  "copywrite_style_id": "xxx",
  "image_style_id": "xxx",
  "reasoning": "选择理由..."
}}
"""
        response = await self._provider.generate(prompt)
        decision = self._extract_json(response)

        # 匹配结果
        c_id = decision.get("copywrite_style_id")
        i_id = decision.get("image_style_id")

        selected_copy = next(
            (s for s in self._copywrite_styles if s.id == c_id),
            self._copywrite_styles[0]
        )
        selected_img = next(
            (s for s in self._image_styles if s.id == i_id),
            self._image_styles[0]
        )
        
        return selected_copy, selected_img

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end != 0:
            return json.loads(cleaned[start:end])
        return {}
