"""MiniMax Provider — 通过 Anthropic 兼容接口调用 MiniMax（httpx 直接调用）"""

from __future__ import annotations

import httpx


class MinimaxProvider:
    """
    MiniMax Anthropic 兼容接口：
      endpoint: https://api.minimax.io/anthropic/v1/messages
      认证: x-api-key header
    """

    def __init__(
        self,
        api_key: str,
        model: str = "MiniMax-M2.5",
        base_url: str = "https://api.minimax.io/anthropic",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._url = f"{base_url.rstrip('/')}/v1/messages"

    async def generate(self, prompt: str, system: str = "") -> str:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": 2048,
            "system": system or "你是一个专业的小红书内容运营编辑。",
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        content = data.get("content", [])
        # 过滤掉 thinking 类型，只取 text
        for block in content:
            if block.get("type") == "text":
                return block["text"]
        raise ValueError(f"MiniMax 未返回 text 内容: {data}")
