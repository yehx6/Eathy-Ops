# CLAUDE.md

本文件为 Claude Code 提供项目上下文，帮助 AI 更好地理解和修改本项目。

## 项目概述

Eathy Ops 是一个全自动化的小红书内容生产与发布流水线。从 RSS/NewsAPI 采集资讯，经 AI 筛选、文案生成、配图生成后，自动发布到小红书。

## 技术栈

- Python 3.10+
- httpx（异步 HTTP）
- rich（终端 UI）
- PyYAML（配置）
- asyncio（并发）

## 项目结构

```
src/eathy/
├── pipeline.py          # 主流水线，串联采集→筛选→生成→发布
├── scheduler.py         # 定时调度器
├── prompts.py           # StyleManager，AI 风格决策
├── providers/           # AI Provider 层
│   ├── base.py          # AIProvider Protocol（generate 接口）
│   ├── minimax.py       # MiniMax（Anthropic 兼容接口）
│   ├── openai_compat.py # OpenAI 兼容 Provider（DeepSeek 等）
│   └── claude.py        # Claude Provider
├── collect/             # 数据采集（RSS、NewsAPI）
├── filter/              # 内容筛选
├── copywrite/           # 文案生成
├── image/               # 配图生成（Gemini）
└── publish/             # 小红书发布（MCP）
```

## 关键设计

### AI Provider 体系

所有 Provider 实现 `AIProvider` Protocol：

```python
class AIProvider(Protocol):
    async def generate(self, prompt: str, system: str = "") -> str: ...
```

- `MinimaxProvider`：Anthropic 兼容接口（`x-api-key` 认证，`/v1/messages`）
- `OpenAICompatProvider`：OpenAI 兼容接口（`Bearer` 认证，`/v1/chat/completions`）
- 通过 `config.yaml` 中 `minimax.api_type` 字段切换：`anthropic`（默认）| `openai`

### 配置

- `config.yaml`：主配置文件，API key 通过 `${ENV_VAR}` 引用环境变量
- `.env`：存放实际的 API key
- `prompts/`：提示词库，配置驱动，无需改代码即可新增风格

## 常用命令

```bash
# 安装
pip install -e .

# 单次运行
eathy run
eathy run --dry-run

# 启动调度器
eathy schedule

# 测试
pytest
```

## 开发约定

- 新增 AI Provider 时在 `src/eathy/providers/` 下新建文件，实现 `generate(prompt, system) -> str`，在 `__init__.py` 导出，在 `pipeline.py` 中按 `api_type` 分支创建。
- 所有 HTTP 调用使用 httpx 异步客户端。
- 配置中 API key 不硬编码，统一使用环境变量引用。
