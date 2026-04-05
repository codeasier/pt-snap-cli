# Context 模块

## 职责

管理 SQLite 数据库连接，提供只读访问模式和设备发现功能。

## 核心组件

### `Context` 类

**属性：**
- `db_path` - 数据库文件路径
- `device_ids` - 可用的设备 ID 列表

**方法：**
- `__init__(db_path, devices)` - 初始化并验证 schema
- `connect()` - 上下文管理器，以只读模式打开连接
- `close()` - 关闭连接
- `cursor()` - 获取数据库游标
- `_validate_schema()` - 验证数据库 schema
- `_discover_device_ids()` - 从表名发现设备 ID

### 异常类

- `DatabaseNotFoundError` - 数据库文件不存在
- `SchemaVersionError` - Schema 无效或不兼容

## 依赖关系

- **依赖**：`sqlite3` - SQLite 连接
- **被依赖**：`cli.py` - CLI 命令使用
- **被依赖**：`query/executor.py` - 查询执行使用

## 设计特点

1. **只读模式**：使用 `file:...?mode=ro` URI 防止数据修改
2. **延迟连接**：首次访问时才建立连接
3. **设备缓存**：`device_ids` 缓存避免重复查询
4. **Schema 验证**：启动时验证 `dictionary` 表存在

## 使用示例

```python
from pt_snap_analyzer.context import Context

# 初始化并验证
ctx = Context("snapshot.pkl.db")

# 获取设备列表
devices = ctx.device_ids  # [0, 1, 2]

# 使用上下文管理器
with ctx.connect() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trace_entry_0")

# 自动关闭
```

## 相关文件

- [context.py](../../pt_snap_analyzer/context.py) - 完整实现
- [cli.py](../../pt_snap_analyzer/cli.py) - 使用 Context 的 CLI 命令
