# Eathy XHS 项目架构模式

## 项目路径
`/Users/zeke/agent dome/eathy-xhs/`

## 架构原则
- **frozen dataclass** 保证不可变（`@dataclass(frozen=True)`）
- **Provider Protocol** 实现 AI API 抽象（claude.py / minimax.py）
- **异步管道** (async/await) 处理 I/O 密集操作
- **环境变量** 管理所有 API 密钥（通过 `${ENV_VAR}` 语法）
- **每次运行独立 output 目录**（`output/{run_id}/`）

## 目录结构
```
eathy-xhs/
├── src/eathy/
│   ├── models.py          # 核心数据模型（frozen dataclass）
│   ├── config.py          # 配置加载（${ENV_VAR} 解析）
│   ├── pipeline.py        # 管道编排（5个阶段串联）
│   ├── cli.py             # CLI 入口
│   ├── collect/           # 信息采集（RSS + NewsAPI）
│   ├── filter/            # AI 筛选（Claude Haiku）
│   ├── image/             # 图片生成（Google Imagen 3）
│   ├── copywrite/         # 文案生成（MiniMax）
│   ├── publish/           # 发布（xiaohongshu-mcp）
│   └── providers/         # AI Provider 抽象层
├── config.yaml            # 主配置（引用 ${ENV_VAR}）
├── account-profile.yaml   # Eathy 账号人设
├── prompt-templates.yaml  # 图片提示词模板
└── .env                   # 实际 API 密钥（gitignore）
```

## 核心数据流
```
Article → FilterResult → GeneratedImage[] + XhsCopywrite → PublishResult → PipelineResult
```

## 关键模型
- `Article`: 采集到的资讯（不可变）
- `FilterResult`: AI 筛选结果（含 selected_article + key_points + image_subject）
- `XhsCopywrite`: 小红书文案（title ≤20字 + body ≤1000字 + hashtags）
- `GeneratedImage`: 生成的图片（含 path + prompt_used）
- `PublishResult`: 发布结果（status: published/failed/dry_run）

## JSON 提取模式
```python
def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    return json.loads(cleaned[start:end])
```

## 环境变量
```
ANTHROPIC_API_KEY   # Claude（筛选）
MINIMAX_API_KEY     # MiniMax（文案）
MINIMAX_GROUP_ID    # MiniMax group
GCP_PROJECT_ID      # Google Cloud（Imagen 3）
NEWS_API_KEY        # NewsAPI（信息采集）
```
