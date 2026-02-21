"""豆包 Seedream 图片生成器 — 通过火山引擎 Ark API 生成图片"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import httpx

from ..models import FilterResult, GeneratedImage
from ..prompts import ImageStyle


class DoubaoImageGenerator:
    """
    豆包 Seedream 图片生成：
      endpoint: {base_url}/images/generations
      认证: Authorization: Bearer {api_key}
      响应: data[i].url 或 data[i].b64_json
    """

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-seedream-4-5-251128",
        number_of_images: int = 3,
        image_size: str = "2048x2720",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._number_of_images = number_of_images
        self._image_size = image_size
        base = base_url.rstrip("/")
        if base.endswith("/images/generations"):
            self._url = base
        else:
            self._url = f"{base}/images/generations"

    async def _generate_single(self, prompt: str) -> bytes | None:
        """调用 Ark API 生成单张图片"""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "prompt": prompt,
            "size": self._image_size,
            "response_format": "b64_json",
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self._url, headers=headers, json=body)
            response.raise_for_status()

        data = response.json()
        images = data.get("data", [])
        if not images:
            return None

        # 优先 b64_json，其次 url
        b64 = images[0].get("b64_json")
        if b64:
            return base64.b64decode(b64)

        url = images[0].get("url")
        if url:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content

        return None

    async def generate(
        self,
        filter_result: FilterResult,
        output_dir: Path,
        style: ImageStyle,
    ) -> tuple[GeneratedImage, ...]:
        """生成小红书配图"""
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
