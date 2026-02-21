"""OpenAI 兼容 Provider — 通过 OpenAI 兼容接口调用（httpx 直接调用）"""

from __future__ import annotations

import httpx


class OpenAICompatProvider:
    """
    OpenAI 兼容接口：
      endpoint: {base_url}/v1/chat/completions
      认证: Authorization: Bearer {api_key}
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        self._api_key = api_key
        self._model = model
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            self._url = base
        else:
            self._url = f"{base}/v1/chat/completions"

    async def generate(self, prompt: str, system: str = "") -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self._model,
            "messages": messages,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]
