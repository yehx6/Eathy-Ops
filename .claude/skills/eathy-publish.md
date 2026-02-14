# Eathy 发布模块

## 发布器路径
`src/eathy/publish/xhs.py` — `XhsPublisher`

## 依赖
xiaohongshu-mcp 服务需提前启动（Go + Playwright）：
```bash
# 下载 binary
# 首次登录
./xiaohongshu-mcp login

# 启动服务
./xiaohongshu-mcp serve
# 默认监听 http://localhost:18060
```

## MCP 调用方式
通过 HTTP JSON-RPC 调用 `publish_note` 工具：
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "publish_note",
    "arguments": {
      "title": "标题（<=20字）",
      "content": "正文 + #话题标签",
      "images": ["/path/to/img1.png", "/path/to/img2.png"],
      "tags": ["健康饮食", "成分分析"]
    }
  }
}
```

## 检查登录状态
```bash
eathy status
```

## Dry Run 模式
```bash
eathy run --dry-run
```
不实际发布，只打印文案和图片路径

## 常见问题
- **未登录**：运行 `xiaohongshu-mcp login`，扫码登录
- **Cookie 过期**：重新运行 login 命令
- **发布失败**：检查 `output/{run_id}/publish_result.json` 中的 error_message
- **MCP 服务未启动**：`eathy status` 会提示
