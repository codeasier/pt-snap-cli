# pt-snap-analyzer 查询系统计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现查询配置系统，支持 YAML 配置的 SQL 模板和查询执行器

**Architecture:** YAML 配置存储 SQL 模板，查询执行器渲染模板并执行查询，支持参数替换和设备适配

**Tech Stack:** Python 3.10+, SQLite3, PyYAML, Jinja2

---

## 文件结构

```
pt-snap-cli/
├── pt_snap_analyzer/
│   ├── query/
│   │   ├── __init__.py
│   │   ├── executor.py        # 查询执行器
│   │   ├── config.py          # YAML 配置管理
│   │   └── templates/         # 预定义 SQL 模板
│   │       ├── leak_detection_v2.yaml
│   │       ├── memory_timeline_v2.yaml
│   │       └── callstack_analysis_v2.yaml
│   └── cli.py                 # 添加查询命令
└── tests/
    ├── test_query_config.py
    ├── test_query_executor.py
    └── test_query_cli.py
```

---

### Task 1: 查询配置系统

**Files:**
- Create: `pt_snap_analyzer/query/config.py`
- Create: `tests/test_query_config.py`

- [ ] **Step 1: 创建配置数据模型**

```python
"""Query configuration management"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class QueryParameter:
    """Query parameter definition"""
    
    name: str
    default: Any = None
    type: str = "str"  # 'str', 'int', 'float', 'bool'
    description: str = ""
    required: bool = False
    
    @property
    def python_type(self) -> type:
        """Get Python type from type string"""
        type_map = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
        }
        return type_map.get(self.type, str)


@dataclass
class QueryTemplate:
    """SQL query template"""
    
    name: str
    description: str
    devices: List[str]  # ['all', '0', '1', ...]
    parameters: Dict[str, QueryParameter]
    query: str
    output_schema: List[Dict[str, str]]


@dataclass
class QueryConfig:
    """Query configuration"""
    
    version: str = "1.0"
    queries: Dict[str, QueryTemplate] = None
    
    def __post_init__(self):
        if self.queries is None:
            self.queries = {}
```

- [ ] **Step 2: 创建配置加载器**

```python
"""Query configuration management"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

from pt_snap_analyzer.query.config import (
    QueryConfig,
    QueryTemplate,
    QueryParameter,
)


class QueryConfigError(Exception):
    """Raised when query configuration error occurs"""
    pass


class QueryConfigLoader:
    """Load and validate query configurations"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize loader
        
        Args:
            config_dir: Directory containing query YAML files
        """
        if config_dir is None:
            home = Path.home()
            self.config_dir = home / ".config" / "pt-snap-analyzer" / "queries"
        else:
            self.config_dir = Path(config_dir)
        
        self.queries: Dict[str, QueryTemplate] = {}
    
    def load_query(self, file_path: str) -> QueryTemplate:
        """Load a single query from YAML file
        
        Args:
            file_path: Path to YAML file
        
        Returns:
            QueryTemplate instance
        
        Raises:
            QueryConfigError: If validation fails
        """
        path = Path(file_path)
        if not path.exists():
            raise QueryConfigError(f"File not found: {file_path}")
        
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise QueryConfigError(f"Invalid YAML in {file_path}: {e}")
        
        return self._validate_query(data, file_path)
    
    def _validate_query(self, data: dict, source: str) -> QueryTemplate:
        """Validate query data
        
        Args:
            data: Parsed YAML data
            source: Source file path
        
        Returns:
            Validated QueryTemplate
        
        Raises:
            QueryConfigError: If validation fails
        """
        required_fields = ["name", "description", "devices", "query"]
        for field in required_fields:
            if field not in data:
                raise QueryConfigError(
                    f"Missing required field '{field}' in {source}"
                )
        
        # Parse parameters
        parameters = {}
        params_data = data.get("parameters", {})
        for name, param_data in params_data.items():
            parameters[name] = QueryParameter(
                name=name,
                default=param_data.get("default"),
                type=param_data.get("type", "str"),
                description=param_data.get("description", ""),
                required=param_data.get("required", False),
            )
        
        # Parse output schema
        output_schema = []
        schema_data = data.get("output_schema", [])
        for item in schema_data:
            if isinstance(item, str):
                output_schema.append({"name": item, "type": "any"})
            elif isinstance(item, dict):
                output_schema.append(item)
        
        return QueryTemplate(
            name=data["name"],
            description=data["description"],
            devices=data["devices"],
            parameters=parameters,
            query=data["query"],
            output_schema=output_schema,
        )
    
    def load_all(self) -> Dict[str, QueryTemplate]:
        """Load all queries from config directory
        
        Returns:
            Dictionary of query name to QueryTemplate
        """
        self.queries = {}
        
        if not self.config_dir.exists():
            return self.queries
        
        yaml_files = list(self.config_dir.glob("*.yaml"))
        yaml_files.extend(self.config_dir.glob("*.yml"))
        
        for file_path in yaml_files:
            try:
                template = self.load_query(str(file_path))
                self.queries[template.name] = template
            except QueryConfigError as e:
                print(f"Warning: Failed to load {file_path}: {e}")
        
        return self.queries
    
    def get_query(self, name: str) -> Optional[QueryTemplate]:
        """Get query template by name
        
        Args:
            name: Query name
        
        Returns:
            QueryTemplate or None if not found
        """
        return self.queries.get(name)
    
    def list_queries(self) -> List[str]:
        """List all query names
        
        Returns:
            List of query names
        """
        return list(self.queries.keys())
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for query configuration system"""

import pytest
import tempfile
import yaml
from pathlib import Path
from pt_snap_analyzer.query.config import (
    QueryConfigLoader,
    QueryConfigError,
    QueryParameter,
    QueryTemplate,
)


def test_query_parameter():
    """Test QueryParameter dataclass"""
    param = QueryParameter(
        name="min_size",
        default=1024,
        type="int",
        description="Minimum size in bytes",
    )
    assert param.name == "min_size"
    assert param.default == 1024
    assert param.python_type == int


def test_query_template():
    """Test QueryTemplate dataclass"""
    template = QueryTemplate(
        name="leak_detection",
        description="Detect memory leaks",
        devices=["0", "1"],
        parameters={},
        query="SELECT * FROM block_0 WHERE freeEventId IS NULL",
        output_schema=[{"name": "id", "type": "int"}],
    )
    assert template.name == "leak_detection"
    assert len(template.devices) == 2


def test_loader_load_single_query(tmp_path):
    """Test loading a single query"""
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("""
name: test_query
description: Test query
devices: ["0"]
parameters:
  limit:
    type: int
    default: 10
query: |
  SELECT * FROM block_0
  LIMIT {{ limit }}
output_schema:
  - name: id
    type: int
  - name: address
    type: int
""")
    
    loader = QueryConfigLoader(config_dir=str(tmp_path))
    template = loader.load_query(str(yaml_file))
    
    assert template.name == "test_query"
    assert template.description == "Test query"
    assert template.devices == ["0"]
    assert "limit" in template.parameters
    assert template.parameters["limit"].default == 10


def test_loader_missing_field(tmp_path):
    """Test error on missing required field"""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("""
name: test_query
# Missing description, devices, and query
""")
    
    loader = QueryConfigLoader(config_dir=str(tmp_path))
    with pytest.raises(QueryConfigError) as exc_info:
        loader.load_query(str(yaml_file))
    
    assert "Missing required field" in str(exc_info.value)


def test_loader_invalid_yaml(tmp_path):
    """Test error on invalid YAML"""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("""
name: test_query
invalid: yaml: syntax: [
""")
    
    loader = QueryConfigLoader(config_dir=str(tmp_path))
    with pytest.raises(QueryConfigError) as exc_info:
        loader.load_query(str(yaml_file))
    
    assert "Invalid YAML" in str(exc_info.value)


def test_loader_load_all(tmp_path):
    """Test loading all queries from directory"""
    yaml_file1 = tmp_path / "query1.yaml"
    yaml_file1.write_text("""
name: leak_detection
description: Detect leaks
devices: ["0"]
query: SELECT * FROM block_0 WHERE freeEventId IS NULL
output_schema: []
""")
    
    yaml_file2 = tmp_path / "query2.yaml"
    yaml_file2.write_text("""
name: peak_analysis
description: Analyze peaks
devices: ["0"]
query: SELECT * FROM trace_entry_0 ORDER BY size DESC
output_schema: []
""")
    
    loader = QueryConfigLoader(config_dir=str(tmp_path))
    queries = loader.load_all()
    
    assert len(queries) == 2
    assert "leak_detection" in queries
    assert "peak_analysis" in queries


def test_loader_nonexistent_file():
    """Test error on nonexistent file"""
    loader = QueryConfigLoader()
    with pytest.raises(QueryConfigError) as exc_info:
        loader.load_query("/nonexistent/path.yaml")
    
    assert "File not found" in str(exc_info.value)
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_query_config.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/query/config.py tests/test_query_config.py
git commit -m "feat: add query configuration loader"
```

---

### Task 2: 查询执行器

**Files:**
- Create: `pt_snap_analyzer/query/executor.py`
- Create: `tests/test_query_executor.py`

- [ ] **Step 1: 创建执行器**

```python
"""Query executor for rendered templates"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Template

from pt_snap_analyzer.context import Context
from pt_snap_analyzer.query.config import QueryTemplate


class QueryExecutionError(Exception):
    """Raised when query execution fails"""
    pass


class QueryExecutor:
    """Execute rendered query templates"""
    
    def __init__(self, context: Context):
        """Initialize executor
        
        Args:
            context: Analysis context with database connection
        """
        self.context = context
    
    def execute_template(
        self,
        template: QueryTemplate,
        parameters: Optional[Dict[str, Any]] = None,
        device_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a query template
        
        Args:
            template: QueryTemplate to execute
            parameters: Parameter values for rendering
            device_id: Device ID to use (None = first device)
        
        Returns:
            List of result rows as dictionaries
        
        Raises:
            QueryExecutionError: If execution fails
        """
        if parameters is None:
            parameters = {}
        
        # Build device-specific query
        try:
            rendered_query = self._render_template(template, parameters, device_id)
        except Exception as e:
            raise QueryExecutionError(f"Failed to render template: {e}")
        
        # Execute query
        try:
            cursor = self.context.cursor()
            cursor.execute(rendered_query)
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            columns = [desc[0] for desc in cursor.description or []]
            results = [dict(zip(columns, row)) for row in rows]
            
            return results
        except Exception as e:
            raise QueryExecutionError(f"Query execution failed: {e}")
    
    def _render_template(
        self,
        template: QueryTemplate,
        parameters: Dict[str, Any],
        device_id: Optional[int] = None,
    ) -> str:
        """Render template with parameters and device
        
        Args:
            template: QueryTemplate to render
            parameters: Parameter values
            device_id: Device ID to substitute
        
        Returns:
            Rendered SQL query
        """
        # Set default parameter values
        for name, param in template.parameters.items():
            if name not in parameters:
                if param.required:
                    raise ValueError(f"Required parameter '{name}' not provided")
                parameters[name] = param.default
        
        # Render Jinja2 template
        template_obj = Template(template.query)
        rendered = template_obj.render(**parameters)
        
        # Substitute device placeholder
        if device_id is not None:
            rendered = self._substitute_device(rendered, device_id)
        elif template.devices and template.devices != ["all"]:
            # Use first device if not specified
            rendered = self._substitute_device(rendered, int(template.devices[0]))
        
        return rendered
    
    def _substitute_device(self, query: str, device_id: int) -> str:
        """Substitute device placeholders in query
        
        Args:
            query: Rendered query
            device_id: Device ID to substitute
        
        Returns:
            Query with device placeholders replaced
        """
        # Replace {device} with actual device ID
        query = query.replace("{device}", str(device_id))
        query = query.replace("{deviceId}", str(device_id))
        query = query.replace("{device_id}", str(device_id))
        
        # Handle table placeholders like {table}_device
        pattern = r"(\w+)_\{device\}"
        matches = re.findall(pattern, query)
        for base_table in matches:
            query = query.replace(f"{base_table}_{{device}}", f"{base_table}_{device_id}")
        
        return query
    
    def execute_name(
        self,
        name: str,
        parameters: Optional[Dict[str, Any]] = None,
        device_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Execute query by name
        
        Args:
            name: Query template name
            parameters: Parameter values
            device_id: Device ID
        
        Returns:
            Query results
        """
        from pt_snap_analyzer.query.config import QueryConfigLoader
        
        loader = QueryConfigLoader()
        loader.load_all()
        
        template = loader.get_query(name)
        if template is None:
            raise QueryExecutionError(f"Query not found: {name}")
        
        return self.execute_template(template, parameters, device_id)
```

- [ ] **Step 2: 创建测试文件**

```python
"""Tests for query executor"""

import pytest
from unittest.mock import MagicMock
from pt_snap_analyzer.query.executor import QueryExecutor, QueryExecutionError


def test_executor_execute_template(mock_context):
    """Test executing query template"""
    from pt_snap_analyzer.query.config import QueryTemplate
    
    template = QueryTemplate(
        name="test_query",
        description="Test query",
        devices=["0"],
        parameters={},
        query="SELECT * FROM block_0",
        output_schema=[],
    )
    
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1, 0x1000), (2, 0x2000)]
    mock_cursor.description = [("id",), ("address",)]
    mock_context.cursor.return_value = mock_cursor
    
    executor = QueryExecutor(context=mock_context)
    results = executor.execute_template(template)
    
    assert len(results) == 2
    assert results[0]["id"] == 1
    assert results[0]["address"] == 0x1000


def test_executor_execute_template_with_params(mock_context):
    """Test executing query with parameters"""
    from pt_snap_analyzer.query.config import QueryTemplate
    
    template = QueryTemplate(
        name="test_query",
        description="Test query",
        devices=["0"],
        parameters={
            "limit": type("Param", (), {"default": 10, "required": False})()
        },
        query="SELECT * FROM block_0 LIMIT {{ limit }}",
        output_schema=[],
    )
    
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1, 0x1000)]
    mock_cursor.description = [("id",), ("address",)]
    mock_context.cursor.return_value = mock_cursor
    
    executor = QueryExecutor(context=mock_context)
    results = executor.execute_template(template, parameters={"limit": 5})
    
    mock_cursor.execute.assert_called_once_with("SELECT * FROM block_0 LIMIT 5")
    assert len(results) == 1


def test_executor_execute_template_missing_param(mock_context):
    """Test error on missing required parameter"""
    from pt_snap_analyzer.query.config import QueryTemplate
    
    template = QueryTemplate(
        name="test_query",
        description="Test query",
        devices=["0"],
        parameters={
            "min_size": type("Param", (), {"default": None, "required": True})()
        },
        query="SELECT * FROM block_0 WHERE size >= {{ min_size }}",
        output_schema=[],
    )
    
    mock_cursor = MagicMock()
    mock_context.cursor.return_value = mock_cursor
    
    executor = QueryExecutor(context=mock_context)
    
    with pytest.raises(ValueError) as exc_info:
        executor.execute_template(template)
    
    assert "Required parameter" in str(exc_info.value)


def test_executor_execute_name(mock_context):
    """Test executing query by name"""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1, 0x1000)]
    mock_cursor.description = [("id",), ("address",)]
    mock_context.cursor.return_value = mock_cursor
    
    executor = QueryExecutor(context=mock_context)
    
    # Mock QueryConfigLoader
    from unittest.mock import patch
    mock_loader = MagicMock()
    mock_loader.get_query.return_value = None
    mock_loader.load_all.return_value = {}
    
    with patch("pt_snap_analyzer.query.executor.QueryConfigLoader", return_value=mock_loader):
        with pytest.raises(QueryExecutionError) as exc_info:
            executor.execute_name("nonexistent_query")
        
        assert "Query not found" in str(exc_info.value)
```

- [ ] **Step 3: 创建测试辅助函数**

在 `tests/conftest.py` (create if not exists):

```python
"""Test fixtures and utilities"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_context():
    """Mock Context for testing"""
    context = MagicMock()
    context.device_ids = [0]
    return context


@pytest.fixture
def example_query_config(tmp_path):
    """Create example query configuration"""
    queries_dir = tmp_path / "queries"
    queries_dir.mkdir()
    
    (queries_dir / "leak_detection.yaml").write_text("""
name: leak_detection_v2
description: Memory leak detection v2
devices: ["all"]
parameters:
  min_size:
    type: int
    default: 1024
    description: Minimum leak size in bytes
query: |
  SELECT b.id, b.address, b.size, t.callstack
  FROM block_{device} b
  LEFT JOIN trace_entry_{device} t ON b.allocEventId = t.id
  WHERE b.id >= 0 AND b.freeEventId IS NULL
  ORDER BY b.size DESC
output_schema:
  - block_id: int
  - address: int
  - size: int
  - callstack: str
""")
    
    return queries_dir
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_query_executor.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/query/executor.py tests/test_query_executor.py tests/conftest.py
git commit -m "feat: add query executor"
```

---

### Task 3: 预定义 SQL 模板

**Files:**
- Create: `pt_snap_analyzer/query/templates/`
- Create: `tests/test_predefined_queries.py`

- [ ] **Step 1: 创建 leak_detection_v2.yaml**

```yaml
name: leak_detection_v2
description: 内存泄漏检测 v2 - 找出未释放的内存块
devices: ["all"]
parameters:
  min_size:
    type: int
    default: 1024
    description: 最小泄漏块大小（字节）
query: |
  SELECT 
    b.id as block_id,
    b.address,
    b.size,
    b.requestedSize,
    t.callstack
  FROM block_{device} b
  LEFT JOIN trace_entry_{device} t ON b.allocEventId = t.id
  WHERE 
    b.id >= 0 
    AND (b.freeEventId IS NULL OR b.freeEventId = -1)
    AND b.size >= {{ min_size }}
  ORDER BY b.size DESC
output_schema:
  - name: block_id
    type: int
  - name: address
    type: int
  - name: size
    type: int
  - name: requestedSize
    type: int
  - name: callstack
    type: str
```

- [ ] **Step 2: 创建 memory_timeline_v2.yaml**

```yaml
name: memory_timeline_v2
description: 内存使用时间线 - 按时间顺序查看内存使用情况
devices: ["all"]
parameters:
  start_id:
    type: int
    default: 0
    description: 起始事件 ID
  end_id:
    type: int
    default: -1
    description: 结束事件 ID (-1 表示最后)
  interval:
    type: int
    default: 1000
    description: 采样间隔（事件数）
query: |
  SELECT 
    id,
    allocated,
    active,
    reserved
  FROM trace_entry_{device}
  WHERE 
    id >= {{ start_id }}
    AND ({{ end_id }} = -1 OR id <= {{ end_id }})
    AND (id - {{ start_id }}) % {{ interval }} = 0
  ORDER BY id ASC
output_schema:
  - name: id
    type: int
  - name: allocated
    type: int
  - name: active
    type: int
  - name: reserved
    type: int
```

- [ ] **Step 3: 创建 callstack_analysis_v2.yaml**

```yaml
name: callstack_analysis_v2
description: 调用栈分析 - 统计调用栈模式
devices: ["all"]
parameters:
  top_k:
    type: int
    default: 10
    description: 返回 Top-K 调用栈
  min_count:
    type: int
    default: 1
    description: 最少出现次数
query: |
  WITH callstack_stats AS (
    SELECT 
      callstack,
      COUNT(*) as count,
      SUM(size) as total_size
    FROM trace_entry_{device}
    WHERE callstack IS NOT NULL AND callstack != ''
    GROUP BY callstack
    HAVING COUNT(*) >= {{ min_count }}
  )
  SELECT 
    callstack,
    count,
    total_size,
    ROUND(CAST(total_size AS REAL) / count, 2) as avg_size
  FROM callstack_stats
  ORDER BY count DESC
  LIMIT {{ top_k }}
output_schema:
  - name: callstack
    type: str
  - name: count
    type: int
  - name: total_size
    type: int
  - name: avg_size
    type: float
```

- [ ] **Step 4: 创建测试文件**

```python
"""Tests for predefined query templates"""

import pytest
from pathlib import Path
from pt_snap_analyzer.query.config import QueryConfigLoader


def test_load_leak_detection():
    """Test loading leak_detection_v2.yaml"""
    loader = QueryConfigLoader()
    
    queries_dir = Path(__file__).parent.parent / "pt_snap_analyzer" / "query" / "templates"
    
    yaml_files = list(queries_dir.glob("*.yaml"))
    assert len(yaml_files) > 0, "No YAML files found in templates directory"
    
    # Check leak_detection_v2.yaml exists
    leak_file = queries_dir / "leak_detection_v2.yaml"
    assert leak_file.exists(), "leak_detection_v2.yaml not found"
    
    template = loader.load_query(str(leak_file))
    assert template.name == "leak_detection_v2"
    assert "memory leak" in template.description.lower()


def test_load_memory_timeline():
    """Test loading memory_timeline_v2.yaml"""
    loader = QueryConfigLoader()
    
    queries_dir = Path(__file__).parent.parent / "pt_snap_analyzer" / "query" / "templates"
    timeline_file = queries_dir / "memory_timeline_v2.yaml"
    
    assert timeline_file.exists(), "memory_timeline_v2.yaml not found"
    
    template = loader.load_query(str(timeline_file))
    assert template.name == "memory_timeline_v2"
    assert "timeline" in template.description.lower()


def test_load_callstack_analysis():
    """Test loading callstack_analysis_v2.yaml"""
    loader = QueryConfigLoader()
    
    queries_dir = Path(__file__).parent.parent / "pt_snap_analyzer" / "query" / "templates"
    stack_file = queries_dir / "callstack_analysis_v2.yaml"
    
    assert stack_file.exists(), "callstack_analysis_v2.yaml not found"
    
    template = loader.load_query(str(stack_file))
    assert template.name == "callstack_analysis_v2"
    assert "callstack" in template.description.lower()


def test_template_parameters():
    """Test template parameters are correctly parsed"""
    loader = QueryConfigLoader()
    
    queries_dir = Path(__file__).parent.parent / "pt_snap_analyzer" / "query" / "templates"
    
    # Test leak_detection
    leak_file = queries_dir / "leak_detection_v2.yaml"
    template = loader.load_query(str(leak_file))
    
    assert "min_size" in template.parameters
    assert template.parameters["min_size"].default == 1024
    assert template.parameters["min_size"].type == "int"
    
    # Test memory_timeline
    timeline_file = queries_dir / "memory_timeline_v2.yaml"
    template = loader.load_query(str(timeline_file))
    
    assert "start_id" in template.parameters
    assert template.parameters["start_id"].default == 0
    
    # Test callstack_analysis
    stack_file = queries_dir / "callstack_analysis_v2.yaml"
    template = loader.load_query(str(stack_file))
    
    assert "top_k" in template.parameters
    assert template.parameters["top_k"].default == 10
```

- [ ] **Step 5: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_predefined_queries.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pt_snap_analyzer/query/templates/
git commit -m "feat: add predefined SQL query templates"
```

---

### Task 4: CLI 集成

**Files:**
- Modify: `pt_snap_analyzer/cli.py`
- Create: `tests/test_query_cli.py`

- [ ] **Step 1: 添加 query 命令到 CLI**

```python
# Add after imports at top of cli.py
from pt_snap_analyzer.query.config import QueryConfigLoader, QueryConfigError
from pt_snap_analyzer.query.executor import QueryExecutor, QueryExecutionError


@app.command()
def query():
    """Query management commands"""
    raise typer.Exit(code=1)


@app.command()
def query_list(
    format: Annotated[
        str, typer.Option("--format", help="Output format: json | table")
    ] = "table",
):
    """List available query templates"""
    loader = QueryConfigLoader()
    loader.load_all()
    
    queries = loader.list_queries()
    
    if format == "json":
        import json
        result = {"queries": [{"name": q} for q in queries]}
        print(json.dumps(result, indent=2))
    else:  # table
        print("Available Queries:")
        print("-" * 40)
        for name in queries:
            template = loader.get_query(name)
            if template:
                print(f"  {name}")
                print(f"    {template.description}")


@app.command()
def query_exec(
    name: Annotated[str, typer.Argument(help="Query name")],
    param: Annotated[
        List[str], typer.Option("--param", help="Parameter key=value")
    ] = [],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
):
    """Execute a predefined query"""
    db_path = _get_current_db()
    if db_path is None:
        print("Error: No database selected. Use 'pt-snap use <db>' first.", flush=True)
        raise typer.Exit(code=1)
    
    try:
        with Context(db_path) as ctx:
            # Parse parameters
            parameters = {}
            for p in param:
                if "=" not in p:
                    print(f"Error: Invalid parameter format: {p} (expected key=value)", flush=True)
                    raise typer.Exit(code=1)
                key, value = p.split("=", 1)
                try:
                    # Try to convert to int
                    parameters[key] = int(value)
                except ValueError:
                    parameters[key] = value
            
            # Execute query
            executor = QueryExecutor(ctx)
            results = executor.execute_name(name, parameters)
            
            if json_output:
                import json
                print(json.dumps(results, indent=2, default=str))
            else:
                # Print as table
                if results:
                    # Print headers
                    headers = list(results[0].keys())
                    print(" | ".join(headers))
                    print("-" * (sum(len(h) for h in headers) + len(headers) * 3))
                    
                    # Print rows
                    for row in results:
                        values = [str(row[h]) for h in headers]
                        print(" | ".join(values))
                else:
                    print("No results")
    
    except QueryExecutionError as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 2: 创建 CLI 测试**

```python
"""Tests for query CLI commands"""

from click.testing import CliRunner
from pt_snap_analyzer.cli import app


def test_query_list():
    """Test query-list command"""
    runner = CliRunner()
    result = runner.invoke(app, ["query-list"])
    # Should succeed even without database
    assert result.exit_code == 0


def test_query_exec_without_db():
    """Test query-exec without database"""
    runner = CliRunner()
    result = runner.invoke(app, ["query-exec", "leak_detection_v2"])
    # Should fail because no database
    assert result.exit_code != 0


def test_query_exec_with_param():
    """Test query-exec with parameters"""
    runner = CliRunner()
    result = runner.invoke(app, [
        "query-exec", "leak_detection_v2",
        "--param", "min_size=4096",
        "--json"
    ])
    # Should fail because no database, but parameter parsing should work
    assert result.exit_code != 0


def test_help_includes_query():
    """Test help includes query commands"""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "query" in result.output.lower()
```

- [ ] **Step 3: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_query_cli.py -v
```

Expected: 4 tests PASS

- [ ] **Step 4: Run full test suite**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/ -v
```

Expected: 25+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/cli.py tests/test_query_cli.py
git commit -m "feat: integrate queries into CLI"
```

---

### 最终验收清单

- [ ] 所有测试通过 (25+ tests)
- [ ] QueryConfigLoader 可以加载 YAML 配置
- [ ] QueryExecutor 可以渲染和执行查询
- [ ] 参数替换正确工作
- [ ] 设备 ID 替换正确工作
- [ ] CLI 命令正常工作
- [ ] JSON 和表格输出都正常
- [ ] pytest 覆盖率 > 80%

---

## 执行意见

Plan complete and saved to `docs/superpowers/plans/2026-04-04-pt-snap-analyzer-query.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 我分发每个任务的独立 subagent，任务间审查，快速迭代

**2. Inline Execution** - 在此会话中执行任务，使用 executing-plans，批次执行加检查点

**Which approach?**
