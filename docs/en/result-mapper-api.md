# ResultMapper API

[English](result-mapper-api.md) | [中文](../zh/result-mapper-api.md)

The `ResultMapper` provides type conversion and model mapping for query results. Use it when embedding or extending the query module programmatically.

## Basic Usage

```python
from pt_snap_cli.query.mapper import map_result, map_results

# Map a single row
mapped = map_result(row, schema)

# Map multiple rows
mapped_all = map_results(rows, schema)
```

## ResultMapper Class

```python
from pt_snap_cli.query.mapper import ResultMapper

mapper = ResultMapper()
```

### Type Conversion

Register custom type converters:

```python
mapper.register_type_converter("custom", lambda x: f"custom_{x}")
```

### Model Mapping

Register model factories:

```python
mapper.register_model_factory("MyModel", lambda d: MyModel(d))
```

Map to model objects:

```python
model = mapper.map_to_model(row, "MyModel")
models = mapper.map_all_to_model(rows, "MyModel")
```

### Direct Mapping

```python
row = {"id": "1", "size": "1024"}
schema = [
    {"column": "id", "type": "int"},
    {"column": "size", "type": "int"},
]
result = mapper.map(row, schema)
results = mapper.map_all(rows, schema)
```

## Supported Type Converters

| Type | Description |
|------|-------------|
| `int` | Integer |
| `float` | Float |
| `str` | String |
| `bool` | Boolean |
| `hex` | Hexadecimal (integer to hex string) |
| `datetime` | Datetime |
