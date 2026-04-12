# Query 模块

## 职责

提供内存快照的查询引擎，支持模板化查询和 Fluent API 构建自定义查询。

## 核心组件

### `QueryExecutor`
查询执行器，负责执行模板查询。

**方法：**
- `execute_template(template_name, params, device_id)` - 执行模板查询
- `_load_template(template_name)` - 加载 YAML 模板
- `_render_template(template, params)` - 渲染模板参数

### `QueryBuilder`
Fluent API 构建 SQL 查询。

**链式方法：**
- `from_table(table)` - 指定表
- `columns(*cols)` - 选择列
- `where(condition)` - 添加条件
- `order_by(*cols, descending)` - 排序
- `group_by(*cols)` - 分组
- `limit(n)` / `offset(n)` - 分页
- `build()` - 生成 SQL 字符串

### `Condition`
条件表达式构建器。

**方法：**
- `eq(value)` / `ne(value)` - 等于/不等于
- `gt(value)` / `gte(value)` - 大于
- `lt(value)` / `lte(value)` - 小于
- `in_list(values)` - IN 查询
- `like(pattern)` - LIKE 查询
- `and_(other)` / `or_(other)` - 逻辑组合

### `QueryMapper`
将查询结果映射为 Python 对象。

### `Registry`
查询模板注册表，管理可用模板。

**函数：**
- `list_queries()` - 列出所有注册模板

## 依赖关系

- **依赖**：`Context` - 数据库连接
- **依赖**：`Models` - 结果映射
- **依赖**：`yaml` / `jinja2` - 模板渲染
- **被依赖**：`cli.py` - CLI 调用

## 预定义模板

位于 `query/templates/` 目录，按分类组织：

- **Basic**: `active_blocks.yaml`, `blocks_by_size.yaml`, `events_by_action.yaml`, `memory_timeline.yaml`
- **Statistical**: `memory_summary.yaml`, `callstack_analysis.yaml`
- **Business**: `leak_detection.yaml`

## 使用示例

```python
from pt_snap_analyzer.query import QueryExecutor
from pt_snap_analyzer.context import Context
from pathlib import Path

# 初始化
ctx = Context("snapshot.pkl.db")
executor = QueryExecutor(ctx, template_dir=Path("query/templates"))

# 执行模板查询
results = executor.execute_template(
    "leak_detection",
    params={"min_size": 1024},
    device_id=0
)

# 使用 QueryBuilder
from pt_snap_analyzer.query import QueryBuilder, Condition

builder = QueryBuilder()
sql = (builder
    .from_table("trace_entry_0")
    .columns("address", "size", "start_ns")
    .where(Condition("size").gt(1024))
    .order_by("start_ns")
    .limit(100)
    .build())
```

## 相关文件

- [query/__init__.py](../../pt_snap_analyzer/query/__init__.py) - 模块导出
- [query/executor.py](../../pt_snap_analyzer/query/executor.py) - 执行器
- [query/builder.py](../../pt_snap_analyzer/query/builder.py) - 构建器
- [query/condition.py](../../pt_snap_analyzer/query/condition.py) - 条件
- [query/mapper.py](../../pt_snap_analyzer/query/mapper.py) - 映射器
- [query/registry.py](../../pt_snap_analyzer/query/registry.py) - 注册表
- [query/templates/](../../pt_snap_analyzer/query/templates/) - 查询模板
