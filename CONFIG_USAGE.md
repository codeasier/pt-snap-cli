# pt-snap 配置管理使用指南

## 功能概述

`pt-snap` 现在支持保存上下文状态，避免在分析时每次都指定数据库路径。

## 使用方法

### 1. 设置当前数据库

```bash
# 设置并验证数据库
pt-snap use /path/to/your/snapshot.db
```

设置成功后，数据库路径会自动保存到 `~/.config/pt-snap-analyzer/config.json`。

### 2. 查看当前配置

```bash
# 查看当前数据库
pt-snap use
```

### 3. 使用配置进行查询（无需指定 dbpath）

```bash
# 列出所有查询模板
pt-snap query --list

# 执行查询（自动使用配置的数据库）
pt-snap query --template-use memory_summary_v2

# 带参数查询
pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'

# 指定设备
pt-snap query --template-use active_blocks_v2 --device 0
```

### 4. 覆盖配置的数据库

即使配置了数据库，仍然可以在命令行中指定不同的数据库：

```bash
# 使用临时指定的数据库（不影响配置）
pt-snap query /path/to/other.db --template-use memory_summary_v2
```

### 5. 管理配置

```bash
# 查看完整配置
pt-snap config

# 查看配置文件路径
pt-snap config --path

# 清除所有配置
pt-snap config --clear
```

## 配置文件位置

配置文件保存在：`~/.config/pt-snap-analyzer/config.json`

配置内容示例：
```json
{
  "current_db_path": "/path/to/your/snapshot.db"
}
```

## 错误处理

### 未配置数据库时查询

```bash
pt-snap query --template-use memory_summary_v2
# Error: No database path specified and no database configured.
# Use 'pt-snap use <database_path>' to set a database, or provide db_path argument.
```

### 配置的数据库文件不存在

如果配置的数据库文件被删除或移动，系统会自动清除配置并提示：

```bash
pt-snap query --template-use memory_summary_v2
# Error: Configured database not found: /path/to/missing.db
# Use 'pt-snap use <new_database_path>' to set a new database.
```

## 完整工作流程示例

```bash
# 1. 初次使用，设置数据库
pt-snap use examples/snapshot_expandable.pkl.db

# 2. 之后可以直接查询，无需重复指定路径
pt-snap query --template-use memory_summary_v2
pt-snap query --template-use active_blocks_v2 --device 0
pt-snap query --template-use leak_detection_v2

# 3. 查看当前配置
pt-snap config

# 4. 如果需要切换到其他数据库
pt-snap use /path/to/new_snapshot.db

# 5. 清除配置
pt-snap config --clear
```

## 优势

1. **提高效率**：无需每次查询都输入完整的数据库路径
2. **减少错误**：避免因路径输入错误导致的查询失败
3. **灵活覆盖**：仍然支持在需要时指定不同的数据库路径
4. **自动清理**：当配置的数据库文件不存在时自动清除配置
5. **配置透明**：可以轻松查看和管理配置
