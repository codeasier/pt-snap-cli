# Models 模块

## 职责

定义 PyTorch 内存快照的数据模型，包括内存块和内存事件。

## 核心组件

### `Block` 类
内存块模型，表示一次内存分配。

**关键属性：**
- `address` - 内存地址
- `size` - 分配大小（字节）
- `device_id` - 设备 ID
- `stream_id` - 流 ID
- `start_ns` - 开始时间（纳秒）
- `call_stack` - 调用栈信息

### `Event` 类
内存事件模型，表示内存分配/释放事件。

**关键属性：**
- `external_id` - 外部 ID
- `block_info` - 关联的内存块
- `start_ns` - 事件时间戳

### `MemoryEventType` 枚举
事件类型定义：
- `UNKNOWN` - 未知类型
- `ALLOC` - 分配事件
- `FREE` - 释放事件

## 依赖关系

- **被依赖**：`query/` - 查询模块使用模型组织结果
- **依赖**：标准库和 PyTorch 相关类型

## 使用示例

```python
from pt_snap_analyzer.models import Block, Event, MemoryEventType

# 创建内存块
block = Block(
    address=0x7f8b4c000000,
    size=1024,
    device_id=0,
    stream_id=0,
    start_ns=1234567890,
    call_stack="main.py:10"
)

# 创建事件
event = Event(
    external_id=1,
    block_info=block,
    event_type=MemoryEventType.ALLOC,
    start_ns=1234567890
)
```

## 相关文件

- [models/__init__.py](../../pt_snap_analyzer/models/__init__.py) - 模块导出
- [models/block.py](../../pt_snap_analyzer/models/block.py) - Block 实现
- [models/event.py](../../pt_snap_analyzer/models/event.py) - Event 实现
- [models/_enums.py](../../pt_snap_analyzer/models/_enums.py) - 枚举定义
