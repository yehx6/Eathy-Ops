"""Gemini 图片生成器 — 通过 Gemini (12ai) 原生接口生成图片"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import httpx

from ..models import ContentCategory, FilterResult, GeneratedImage
from ..prompts import ImageStyle

# 默认配置
_DEFAULT_MODEL = "gemini-3-pro-image-preview"
_DEFAULT_BASE_URL = "https://new.12ai.org"


class ImagenGenerator:
    """
    使用 Gemini gemini-3-pro-image-preview 模型生成图片。
    
    使用 Gemini 原生 API 格式:
    POST /v1beta/models/{model}:generateContent?key={api_key}
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        number_of_images: int = 3,
        image_size: str = "3:4",
        num_inference_steps: int = 20, # 保留参数兼容性，但 Gemini API 不需要
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._number_of_images = number_of_images
        self._aspect_ratio = image_size if ":" in image_size else "3:4"
        self._base_url = base_url.rstrip("/")

    async def _generate_single(
        self,
        prompt: str,
    ) -> bytes | None:
        """调用 Gemini 原生 API 生成单张图片"""
        
        # 构造请求 URL
        url = f"{self._base_url}/v1beta/models/{self._model}:generateContent"
        
        # 构造请求体
        body = {
            "contents": [{
                "parts": [{"text": f"Generate an image: {prompt}"}]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": self._aspect_ratio
                }
            }
        }

        # 通过 URL 参数传递 API Key
        params = {"key": self._api_key}
        
        headers = {
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=body
            )
            response.raise_for_status()
            
        data = response.json()
        
        # 解析响应: candidates[0].content.parts[0].inlineData.data
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return None
            
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None
                
            # 查找 inlineData
            for part in parts:
                inline_data = part.get("inlineData", {})
                b64_data = inline_data.get("data")
                if b64_data:
                    return base64.b64decode(b64_data)
                    
        except Exception as e:
            print(f"[Warning] 解析 Gemini 响应失败: {e}")
            
        return None

    async def generate(
        self,
        filter_result: FilterResult,
        output_dir: Path,
        style: ImageStyle,
    ) -> tuple[GeneratedImage, ...]:
        """
        生成小红书配图。

        Args:
            filter_result: AI 筛选结果（提供 image_subject 和 category）
            output_dir: 图片保存目录
            style: 图片生成风格

        Returns:
            tuple[GeneratedImage, ...] 生成的图片列表
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt = style.prompt.replace("{subject}", filter_result.image_subject).strip()

        images: list[GeneratedImage] = []

        for i in range(self._number_of_images):
            try:
                img_bytes = await self._generate_single(prompt)
                
                if img_bytes is None:
                    print(f"[Warning] 第{i+1}张图片生成无数据")
                    continue

                filename = f"image_{i:02d}_{uuid.uuid4().hex[:8]}.png"
                image_path = output_dir / filename
                image_path.write_bytes(img_bytes)

                images.append(
                    GeneratedImage(
                        path=image_path,
                        prompt_used=prompt,
                        template_name=style.name,
                    )
                )
            except httpx.HTTPStatusError as exc:
                print(
                    f"[Warning] 第{i+1}张图片生成失败 HTTP {exc.response.status_code}: "
                    f"{exc.response.text[:200]}"
                )
            except Exception as exc:
                print(f"[Warning] 第{i+1}张图片生成失败: {exc}")

        if not images:
            raise RuntimeError("图片生成失败：未获得任何可用图片")

        return tuple(images)
