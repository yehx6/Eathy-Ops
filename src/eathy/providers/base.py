"""Provider Protocol 定义"""

from typing import Protocol


class AIProvider(Protocol):
    async def generate(self, prompt: str, system: str = "") -> str: ...
