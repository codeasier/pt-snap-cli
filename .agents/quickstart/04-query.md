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

- **Basic**: `allocation`, `block`, `event`
- **Statistical**: `active_blocks_at_event`, `allocator_gap`, `callstack_analysis`, `memory_peak`
- **Business**: `active_memory_callstack_at_event`, `leak_detection`

## 使用示例

```bash
pt-snap query snapshot.pkl.db --template-use leak_detection \
  --params '{"min_size": 1024}' --device 0
pt-snap query --list
pt-snap query --template-info leak_detection
```

## 相关文件

- [query/__init__.py](../../src/pt_snap_cli/query/__init__.py) - 模块导出
- [query/executor.py](../../src/pt_snap_cli/query/executor.py) - 执行器
- [query/builder.py](../../src/pt_snap_cli/query/builder.py) - 构建器
- [query/condition.py](../../src/pt_snap_cli/query/condition.py) - 条件
- [query/mapper.py](../../src/pt_snap_cli/query/mapper.py) - 映射器
- [query/registry.py](../../src/pt_snap_cli/query/registry.py) - 注册表
- [query/templates/](../../src/pt_snap_cli/query/templates/) - 查询模板
