"""Claude Provider — 用于信息筛选"""

from __future__ import annotations

from anthropic import AsyncAnthropic


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str, system: str = "") -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system or "你是一个专业的健康内容分析师。",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
