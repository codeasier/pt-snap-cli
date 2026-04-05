# Tasks

- [ ] Task 1: test_condition.py - 基础条件类测试  
  - [ ] SubTask 1.1: Equal, NotEqual, GreaterThan, LessThan, GreaterThanOrEqual, LessThanOrEqual 测试
  - [ ] SubTask 1.2: In 条件测试（空列表、单值、多值）
  - [ ] SubTask 1.3: Like 条件测试

- [ ] Task 2: test_condition.py - 组合条件测试 
  - [ ] SubTask 2.1: And 组合测试（基础、多条件、空、链式）
  - [ ] SubTask 2.2: Or 组合测试（基础、多条件、空、链式）
  - [ ] SubTask 2.3: 混合组合测试（And+Or、嵌套、复杂组合）

- [ ] Task 3: test_registry.py - 注册表基础功能测试
  - [ ] SubTask 3.1: 单例模式测试（创建、重置）
  - [ ] SubTask 3.2: 注册和查询测试（基础、重复、不存在）
  - [ ] SubTask 3.3: 工厂函数测试（注册、缓存、覆盖）
  - [ ] SubTask 3.4: 列表查询测试（基础、详细信息、注销）

- [ ] Task 4: test_registry.py - 模块级函数和 YAML 加载测试
  - [ ] SubTask 4.1: 模块级便捷函数测试（register_query, get_query, list_queries）
  - [ ] SubTask 4.2: get_template_info 测试
  - [ ] SubTask 4.3: YAML 模板加载测试（目录不存在、正常加载、全部加载）

- [ ] Task 5: test_cli.py - 基础命令和 use 命令测试
  - [ ] SubTask 5.1: version 回调和主回调测试
  - [ ] SubTask 5.2: use 命令测试（无参数、无配置、数据库不存在）
  - [ ] SubTask 5.3: use 命令测试（成功场景、无设备、异常处理）

- [ ] Task 6: test_cli.py - query 命令测试
  - [ ] SubTask 6.1: list 和 template-info 选项测试
  - [ ] SubTask 6.2: query 命令错误处理（无 template-use、无数据库、数据库不存在）
  - [ ] SubTask 6.3: query 命令执行（带设备、不带设备、带参数、无效 JSON）
  - [ ] SubTask 6.4: query 命令异常处理（无设备、文件不存在、通用异常）

- [ ] Task 7: test_cli.py - config 命令测试
  - [ ] SubTask 7.1: config 显示测试（有配置、无配置）
  - [ ] SubTask 7.2: config 清空和路径显示测试

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 4] depends on [Task 3]
- [Task 6] depends on [Task 5]
- [Task 7] depends on [Task 5]
