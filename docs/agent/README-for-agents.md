# Agent 文档使用指南

## 📚 文档结构

```
docs/agents/
├── README-for-agents.md        # 本文件 - 导航索引
├── ARCHITECTURE.md             # 整体架构概览
├── 01-cli.md                   # CLI 模块详情
├── 02-context.md               # Context 模块详情
├── 03-models.md                # Models 模块详情
└── 04-query.md                 # Query 模块详情
```

## 🎯 阅读策略

### 新会话快速上手（推荐流程）

1. **第一步**：阅读 [ARCHITECTURE.md](ARCHITECTURE.md)
   - 了解项目定位和整体架构
   - 掌握模块依赖关系
   - 用时：2-3 分钟

2. **第二步**：根据任务需求选择阅读对应模块文档
   - CLI 相关 → [01-cli.md](01-cli.md)
   - 数据库相关 → [02-context.md](02-context.md)
   - 数据模型相关 → [03-models.md](03-models.md)
   - 查询功能相关 → [04-query.md](04-query.md)
   - 用时：每个模块 3-5 分钟

3. **第三步**：需要深入了解时再查阅源码

### 任务场景映射

| 任务类型 | 推荐文档 |
|---------|---------|
| 添加 CLI 命令 | ARCHITECTURE.md → 01-cli.md |
| 修改数据库操作 | ARCHITECTURE.md → 02-context.md |
| 新增数据模型 | ARCHITECTURE.md → 03-models.md |
| 开发查询功能 | ARCHITECTURE.md → 04-query.md |
| 修复 Bug | 根据错误定位选择对应模块文档 |
| 代码审查 | 全部模块文档快速浏览 |

## 💡 渐进式披露原则

```
ARCHITECTURE.md (5 分钟)
    ↓
模块文档 (3-5 分钟/个)
    ↓
源码细节 (按需深入)
```

**优势：**
- ✅ 新会话无需重新阅读全部源码
- ✅ 快速建立认知地图
- ✅ 按需深入，避免信息过载
- ✅ 文档维护成本低于源码注释

## 📝 文档维护

当代码发生变更时：
1. 同步更新对应的模块文档
2. 如有架构级变更，更新 ARCHITECTURE.md
3. 保持文档精简，只记录关键信息

## 🔗 与现有文档的关系

- `docs/agents/` - **Agent 快速参考**（本文档）
- `docs/superpowers/` - **设计文档**（PRDs、specs、plans）
- `README.md` - **用户使用指南**

## ✨ 最佳实践

```markdown
# 新会话开场
你好！我已阅读 [ARCHITECTURE.md](docs/agents/ARCHITECTURE.md)，
了解到 pt-snap-analyzer 是一个 PyTorch 内存快照分析工具。
请问需要我帮助你做什么？

# 执行任务时
根据任务需求，我会参考相关模块文档：
- 需要修改 CLI？→ 查看 01-cli.md
- 需要开发查询？→ 查看 04-query.md
```

---

**最后更新**: 2026-04-04
