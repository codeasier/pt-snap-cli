# Models 模块

## 职责

定义 PyTorch 内存快照的数据模型，包括内存块和内存事件。

## 核心组件

### `MemoryBlock` 类
内存块模型，表示一次内存分配。

**关键属性：**
- `address` - 内存地址
- `size` - 分配大小（字节）
- `requested_size` - 用户请求的大小
- `state` - 内存块状态
- `alloc_event_id` / `free_event_id` - 生命周期事件 ID

### `MemoryEvent` 类
内存事件模型，表示内存分配/释放事件。

**关键属性：**
- `id` - 事件 ID
- `action` - 事件类型
- `allocated` / `active` / `reserved` - 事件后的内存统计

### `EventType` 枚举
事件类型定义：
- `UNKNOWN` - 未知类型
- `ALLOC` - 分配事件
- `FREE` - 释放事件

## 依赖关系

- **被依赖**：`query/` - 查询模块使用模型组织结果
- **依赖**：标准库和 PyTorch 相关类型

## 使用示例

```python
from pt_snap_cli.models import BlockState, EventType, MemoryBlock, MemoryEvent

# 创建内存块
block = MemoryBlock(
    id=1,
    address=0x7f8b4c000000,
    size=1024,
    requested_size=1000,
    state=BlockState.ACTIVE_ALLOCATED,
    alloc_event_id=1,
)

# 创建事件
event = MemoryEvent(
    id=1,
    action=EventType.ALLOC,
    address=block.address,
    size=block.size,
    stream=0,
    allocated=1024,
    active=1024,
    reserved=2048,
)
```

## 相关文件

- [models/__init__.py](../../src/pt_snap_cli/models/__init__.py) - 模块导出
- [models/block.py](../../src/pt_snap_cli/models/block.py) - MemoryBlock 实现
- [models/event.py](../../src/pt_snap_cli/models/event.py) - MemoryEvent 实现
- [models/_enums.py](../../src/pt_snap_cli/models/_enums.py) - 枚举定义
