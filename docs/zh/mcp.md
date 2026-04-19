# MCP 服务器

[English](../en/mcp.md) | 中文

`pt-snap-cli` 提供了 MCP（Model Context Protocol）服务器，使 AI Agent 能够以编程方式与 PyTorch 内存快照交互。

## 安装

```bash
pip install -e .
```

MCP 服务器作为核心包的一部分自动安装。

## 启动服务器

```bash
pt-snap-mcp
```

这将启动一个 FastMCP 服务器，暴露用于分析 PyTorch 内存快照的工具。

## 可用工具

| 工具 | 说明 |
|------|------|
| `get_focus` | 获取当前分析焦点（数据库路径、设备 ID、来源） |
| `set_focus` | 设置焦点到指定数据库和可选设备。运行查询前使用。 |
| `list_templates` | 列出可用的查询模板，可按类别筛选 |
| `get_template_info` | 获取模板详情，包括参数信息 |
| `execute_query` | 对焦点数据库执行查询模板 |

## 可用资源

| 资源 | 说明 |
|------|------|
| `focus://current` | 当前分析焦点状态 |

## 可用提示词

| 提示词 | 说明 |
|--------|------|
| `analyze_memory_leaks` | 生成用于分析内存泄漏的提示词模板 |

## 典型工作流

1. 调用 `set_focus` 并传入 `db_path` 指向快照文件
2. 调用 `list_templates` 发现可用查询
3. 调用 `get_template_info` 查看模板参数
4. 调用 `execute_query` 执行查询

## 使用示例

```python
# 设置焦点到快照文件
set_focus(db_path="/path/to/snapshot.db", device_id=0)

# 列出模板
list_templates()
# 返回: [{"name": "leak_detection", "description": "...", ...}, ...]

# 获取模板详情
get_template_info("leak_detection")
# 返回: {"name": "leak_detection", "parameters": [...], ...}

# 运行查询
execute_query("leak_detection", params={"min_size": 1024})
# 返回: {"total": 5, "returned": 5, "rows": [...]}
```

## CLI 命令

MCP 入口点在 `pyproject.toml` 中声明：

```toml
[project.scripts]
pt-snap-mcp = "pt_snap_cli.mcp.server:main"
```
