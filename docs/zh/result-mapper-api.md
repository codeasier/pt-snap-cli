# ResultMapper API

[English](../en/result-mapper-api.md) | 中文

`ResultMapper` 提供查询结果的类型转换和模型映射功能。在编程式嵌入或扩展查询模块时使用。

## 基本用法

```python
from pt_snap_cli.query.mapper import map_result, map_results

# 映射单行结果
mapped = map_result(row, schema)

# 映射多行结果
mapped_all = map_results(rows, schema)
```

## ResultMapper 类

```python
from pt_snap_cli.query.mapper import ResultMapper

mapper = ResultMapper()
```

### 类型转换

注册自定义类型转换器：

```python
mapper.register_type_converter("custom", lambda x: f"custom_{x}")
```

### 模型映射

注册模型工厂：

```python
mapper.register_model_factory("MyModel", lambda d: MyModel(d))
```

映射到模型对象：

```python
model = mapper.map_to_model(row, "MyModel")
models = mapper.map_all_to_model(rows, "MyModel")
```

### 直接映射

```python
row = {"id": "1", "size": "1024"}
schema = [
    {"column": "id", "type": "int"},
    {"column": "size", "type": "int"},
]
result = mapper.map(row, schema)
results = mapper.map_all(rows, schema)
```

## 支持的类型转换器

| 类型 | 说明 |
|------|------|
| `int` | 整数 |
| `float` | 浮点数 |
| `str` | 字符串 |
| `bool` | 布尔值 |
| `hex` | 十六进制（整数转 hex 字符串） |
| `datetime` | 日期时间 |
