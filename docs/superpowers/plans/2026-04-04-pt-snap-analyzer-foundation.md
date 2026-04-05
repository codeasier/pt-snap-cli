# pt-snap-analyzer 基础架构计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 CLI 框架、数据模型和核心 Context，提供基础 API 支撑

**Architecture:** 基于 Typer 构建 CLI 框架，Pydantic 定义数据模型，SQLite 管理数据库连接

**Tech Stack:** Python 3.10+, Typer, Pydantic, SQLite3

---

## 文件结构

```
pt-snap-cli/
├── pt_snap_analyzer/
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口
│   ├── context.py             # Context 类
│   ├── models/
│   │   ├── __init__.py
│   │   ├── event.py           # MemoryEvent
│   │   └── block.py           # MemoryBlock
│   └── version.py             # 版本信息
├── tests/
│   ├── test_context.py
│   ├── test_models.py
│   └── test_cli.py
├── examples/
│   └── snapshot_expandable.pkl.db
└── pyproject.toml
```

---

### Task 1: 项目初始化和配置

**Files:**
- Create: `pt_snap_analyzer/__init__.py`
- Create: `pt_snap_analyzer/version.py`
- Create: `pyproject.toml`
- Create: `examples/snapshot_expandable.pkl.db` (symlink to test database)

- [ ] **Step 1: 创建包初始化文件**

```python
"""pt-snap-analyzer - AI-friendly PyTorch Memory Snapshot Analyzer"""

__version__ = "0.1.0"
__author__ = "Liuyekang"

from pt_snap_analyzer.context import Context
from pt_snap_analyzer.models import MemoryEvent, MemoryBlock

__all__ = ["Context", "MemoryEvent", "MemoryBlock", "__version__"]
```

- [ ] **Step 2: 创建版本信息文件**

```python
"""Package version"""

__version__ = "0.1.0"
```

- [ ] **Step 3: 创建 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "pt-snap-analyzer"
version = "0.1.0"
description = "AI-friendly PyTorch Memory Snapshot Analyzer"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Liuyekang", email = "liuyekang@example.com"}
]
dependencies = [
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "chromadb>=0.4.0",
    "langchain>=0.1.0",
]

[project.scripts]
pt-snap = "pt_snap_analyzer.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.0.280",
]

[tool.black]
line-length = 100
target-version = ['py310']

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["pt_snap_analyzer"]
```

- [ ] **Step 4: 创建示例数据库符号链接**

```bash
mkdir -p examples
ln -sf /path/to/snapshot_expandable.pkl.db examples/snapshot_expandable.pkl.db
```

- [ ] **Step 5: 运行安装测试**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pip install -e .[dev] -v
```

Expected: 安装成功，无错误

- [ ] **Step 6: Commit**

```bash
git add pt_snap_analyzer/__init__.py pt_snap_analyzer/version.py pyproject.toml
git commit -m "chore: project initialization and configuration"
```

---

### Task 2: 数据模型 - 枚举类型和基类

**Files:**
- Create: `pt_snap_analyzer/models/__init__.py`
- Create: `pt_snap_analyzer/models/_enums.py`

- [ ] **Step 1: 创建枚举模块**

```python
"""Data models for memory snapshot analysis"""

from enum import IntEnum


class EventType(IntEnum):
    """Memory event action types"""
    SEGMENT_MAP = 0
    SEGMENT_UNMAP = 1
    SEGMENT_ALLOC = 2
    SEGMENT_FREE = 3
    ALLOC = 4
    FREE_REQUESTED = 5
    FREE_COMPLETED = 6
    WORKSPACE_SNAPSHOT = 7


class BlockState(IntEnum):
    """Memory block states"""
    INACTIVE = -1
    ACTIVE_PENDING_FREE = 0
    ACTIVE_ALLOCATED = 1
    UNKNOWN = 99
```

- [ ] **Step 2: 创建 models 初始化文件**

```python
"""Data models for memory snapshot analysis"""

from pt_snap_analyzer.models._enums import EventType, BlockState
from pt_snap_analyzer.models.event import MemoryEvent
from pt_snap_analyzer.models.block import MemoryBlock

__all__ = ["EventType", "BlockState", "MemoryEvent", "MemoryBlock"]
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for data models"""

import pytest
from pt_snap_analyzer.models import EventType, BlockState


def test_event_type_enum():
    """Test EventType enum values"""
    assert EventType.SEGMENT_MAP == 0
    assert EventType.ALLOC == 4
    assert EventType.FREE_COMPLETED == 6


def test_block_state_enum():
    """Test BlockState enum values"""
    assert BlockState.INACTIVE == -1
    assert BlockState.ACTIVE_ALLOCATED == 1
    assert BlockState.UNKNOWN == 99


def test_event_type_is_intenum():
    """Test EventType is IntEnum subclass"""
    assert issubclass(EventType, int)
    assert issubclass(EventType, IntEnum)


def test_block_state_is_intenum():
    """Test BlockState is IntEnum subclass"""
    assert issubclass(BlockState, int)
    assert issubclass(BlockState, IntEnum)
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_models.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/models/ tests/test_models.py
git commit -m "feat: add data models - EventType and BlockState enums"
```

---

### Task 3: 数据模型 - MemoryEvent 和 MemoryBlock

**Files:**
- Create: `pt_snap_analyzer/models/event.py`
- Create: `pt_snap_analyzer/models/block.py`

- [ ] **Step 1: 创建 MemoryEvent 模型**

```python
"""MemoryEvent data model"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pt_snap_analyzer.models._enums import EventType


@dataclass
class MemoryEvent:
    """Represents a memory allocation/free event
    
    Attributes:
        id: Event ID (negative for synthetic events)
        action: Type of memory action
        address: Memory address
        size: Allocation size in bytes
        stream: CUDA/CANN stream ID
        allocated: Total allocated memory
        active: Total active memory
        reserved: Total reserved memory
        callstack: Call stack information (multi-line string)
    """
    id: int
    action: EventType
    address: int
    size: int
    stream: int
    allocated: int
    active: int
    reserved: int
    callstack: Optional[str]

    @property
    def is_virtual_event(self) -> bool:
        """Check if event is system-generated (virtual)"""
        return self.id < 0

    @property
    def is_runtime_event(self) -> bool:
        """Check if event is from runtime code"""
        return self.id >= 0

    @classmethod
    def from_row(cls, row: tuple) -> MemoryEvent:
        """Create MemoryEvent from database row
        
        Args:
            row: Tuple from SQLite query (id, action, address, size, 
                 stream, allocated, active, reserved, callstack)
        
        Returns:
            MemoryEvent instance
        """
        return cls(
            id=row[0],
            action=EventType(row[1]),
            address=row[2],
            size=row[3],
            stream=row[4],
            allocated=row[5],
            active=row[6],
            reserved=row[7],
            callstack=row[8],
        )
```

- [ ] **Step 2: 创建 MemoryBlock 模型**

```python
"""MemoryBlock data model"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pt_snap_analyzer.models._enums import BlockState


@dataclass
class MemoryBlock:
    """Represents a memory block with its lifecycle state
    
    Attributes:
        id: Block ID (negative for historical blocks)
        address: Memory address
        size: Actual allocation size in bytes
        requestedSize: User-requested size
        state: Block state
        allocEventId: ID of allocation event
        freeEventId: ID of free event
    """
    id: int
    address: int
    size: int
    requestedSize: int
    state: int
    allocEventId: Optional[int]
    freeEventId: Optional[int]

    @property
    def is_historical_block(self) -> bool:
        """Check if block is from historical snapshot"""
        return self.id < 0

    @property
    def is_active(self) -> bool:
        """Check if block is currently allocated"""
        if self.is_historical_block:
            return self.state == BlockState.ACTIVE_ALLOCATED
        return self.freeEventId is None or self.freeEventId == -1

    @property
    def block_state(self) -> BlockState:
        """Get block state as BlockState enum"""
        return BlockState(self.state) if self.state != 99 else BlockState.UNKNOWN

    @classmethod
    def from_row(cls, row: tuple) -> MemoryBlock:
        """Create MemoryBlock from database row
        
        Args:
            row: Tuple from SQLite query (id, address, size, requestedSize,
                 state, allocEventId, freeEventId)
        
        Returns:
            MemoryBlock instance
        """
        return cls(
            id=row[0],
            address=row[1],
            size=row[2],
            requestedSize=row[3],
            state=row[4],
            allocEventId=row[5],
            freeEventId=row[6],
        )
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for MemoryEvent and MemoryBlock models"""

import pytest
from pt_snap_analyzer.models import MemoryEvent, MemoryBlock, EventType, BlockState


def test_memory_event_properties():
    """Test MemoryEvent properties"""
    event = MemoryEvent(
        id=1, action=EventType.ALLOC, address=0x1000, size=1024,
        stream=0, allocated=2048, active=2048, reserved=4096,
        callstack="test.py:10"
    )
    assert not event.is_virtual_event
    assert event.is_runtime_event


def test_memory_event_virtual():
    """Test virtual event detection"""
    event = MemoryEvent(
        id=-100, action=EventType.ALLOC, address=0x1000, size=1024,
        stream=0, allocated=2048, active=2048, reserved=4096,
        callstack=None
    )
    assert event.is_virtual_event
    assert not event.is_runtime_event


def test_memory_event_from_row():
    """Test MemoryEvent.from_row()"""
    row = (1, 4, 0x1000, 1024, 0, 2048, 2048, 4096, "test.py:10")
    event = MemoryEvent.from_row(row)
    assert event.id == 1
    assert event.action == EventType.ALLOC
    assert event.size == 1024
    assert event.callstack == "test.py:10"


def test_memory_block_properties():
    """Test MemoryBlock properties"""
    block = MemoryBlock(
        id=-320, address=0x2000, size=4096, requestedSize=4096,
        state=1, allocEventId=-1, freeEventId=-1
    )
    assert block.is_historical_block
    assert block.is_active
    assert block.block_state == BlockState.ACTIVE_ALLOCATED


def test_memory_block_active_state():
    """Test active block detection"""
    block = MemoryBlock(
        id=100, address=0x3000, size=2048, requestedSize=2048,
        state=0, allocEventId=50, freeEventId=None
    )
    assert not block.is_historical_block
    assert block.is_active


def test_memory_block_inactive():
    """Test inactive block detection"""
    block = MemoryBlock(
        id=101, address=0x4000, size=2048, requestedSize=2048,
        state=0, allocEventId=51, freeEventId=60
    )
    assert not block.is_active


def test_memory_block_from_row():
    """Test MemoryBlock.from_row()"""
    row = (-320, 0x2000, 4096, 4096, 1, -1, -1)
    block = MemoryBlock.from_row(row)
    assert block.id == -320
    assert block.address == 0x2000
    assert block.is_historical_block
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_models.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/models/event.py pt_snap_analyzer/models/block.py
git commit -m "feat: add MemoryEvent and MemoryBlock data models"
```

---

### Task 4: Context 类 - 数据库连接管理

**Files:**
- Create: `pt_snap_analyzer/context.py`
- Modify: `tests/test_models.py` → add context tests

- [ ] **Step 1: 创建 Context 类**

```python
"""Context management for snapshot analysis"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional

from pt_snap_analyzer.version import __version__


class DatabaseNotFoundError(FileNotFoundError):
    """Raised when database file not found"""
    def __init__(self, path: str):
        super().__init__(f"Database not found: {path}")
        self.path = path


class SchemaVersionError(Exception):
    """Raised when database schema version mismatch"""
    def __init__(self, expected: str, actual: Optional[str]):
        super().__init__(f"Schema version mismatch: expected {expected}, got {actual}")
        self.expected = expected
        self.actual = actual


@dataclass
class Context:
    """Analysis context managing database connection and configuration
    
    Attributes:
        db_path: Path to SQLite database
        devices: List of device IDs to analyze (None = all)
        db_version: Database schema version
       _AnNOTE__: Database connection (internal)
    """
    db_path: str
    devices: Optional[list[int]] = None
    _conn: Optional[sqlite3.Connection] = field(default=None, repr=False)
    
    def __post_init__(self):
        """Validate and open database"""
        self._validate_db_path()
        self._conn = self._open_database()
        self._validate_schema()
    
    def _validate_db_path(self) -> None:
        """Validate database file exists"""
        path = Path(self.db_path)
        if not path.exists():
            raise DatabaseNotFoundError(self.db_path)
        if not path.is_file():
            raise DatabaseNotFoundError(f"Not a file: {self.db_path}")
    
    def _open_database(self) -> sqlite3.Connection:
        """Open database in read-only mode"""
        path = Path(self.db_path).resolve()
        uri = f"file:{path}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    
    def _validate_schema(self) -> None:
        """Validate database schema version"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'")
        if cursor.fetchone() is None:
            raise SchemaVersionError("v1.0", "no dictionary table")
    
    @property
    def device_ids(self) -> list[int]:
        """Get list of device IDs in database"""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'block_%'"
        )
        tables = cursor.fetchall()
        devices = []
        for (table,) in tables:
            try:
                device_id = int(table.split("_")[-1])
                devices.append(device_id)
            except (ValueError, IndexError):
                continue
        if self.devices is not None:
            devices = [d for d in devices if d in self.devices]
        return devices
    
    def cursor(self) -> sqlite3.Cursor:
        """Get database cursor"""
        if self._conn is None:
            raise RuntimeError("Database not connected")
        return self._conn.cursor()
    
    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connection
        
        Yields:
            Database connection
        """
        if self._conn is None:
            raise RuntimeError("Database not connected")
        try:
            yield self._conn
        finally:
            pass
    
    def close(self) -> None:
        """Close database connection"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
    
    def __enter__(self) -> Context:
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()
    
    def __del__(self) -> None:
        """Destructor to close connection"""
        self.close()
```

- [ ] **Step 2: 创建测试文件**

```python
"""Tests for Context class"""

import pytest
import sqlite3
from pathlib import Path
from pt_snap_analyzer.context import Context, DatabaseNotFoundError, SchemaVersionError


def test_context_open_database(tmp_path):
    """Test opening valid database"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE dictionary (
            table TEXT, column TEXT, key TEXT, value TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    with Context(str(db_path)) as ctx:
        assert ctx.db_path == str(db_path)
        assert ctx.devices is None
        assert ctx.device_ids == []


def test_context_database_not_found():
    """Test error when database not found"""
    with pytest.raises(DatabaseNotFoundError):
        Context("/nonexistent/path/db.db")


def test_context_invalid_file(tmp_path):
    """Test error when path is not a file"""
    dir_path = tmp_path / "not_a_file"
    dir_path.mkdir()
    with pytest.raises(DatabaseNotFoundError):
        Context(str(dir_path))


def test_context_schema_validation(tmp_path):
    """Test schema validation"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER)")
    conn.commit()
    conn.close()
    
    with pytest.raises(SchemaVersionError):
        Context(str(db_path))


def test_context_device_filtering(tmp_path):
    """Test device ID filtering"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE dictionary (
            table TEXT, column TEXT, key TEXT, value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE block_0 (id INTEGER PRIMARY KEY)
    """)
    cursor.execute("""
        CREATE TABLE block_1 (id INTEGER PRIMARY KEY)
    """)
    cursor.execute("""
        CREATE TABLE block_2 (id INTEGER PRIMARY KEY)
    """)
    conn.commit()
    conn.close()
    
    ctx = Context(str(db_path), devices=[0, 2])
    assert ctx.device_ids == [0, 2]


def test_context_connect_context_manager(tmp_path):
    """Test connect() context manager"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE dictionary (
            table TEXT, column TEXT, key TEXT, value TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    with Context(str(db_path)) as ctx:
        with ctx.connect() as connection:
            assert isinstance(connection, sqlite3.Connection)
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            assert len(tables) >= 1
```

- [ ] **Step 3: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_context.py -v
```

Expected: 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add pt_snap_analyzer/context.py tests/test_context.py
git commit -m "feat: add Context class for database management"
```

---

### Task 5: CLI 框架 - 命令结构

**Files:**
- Create: `pt_snap_analyzer/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 创建 CLI 入口**

```python
"""CLI entry point for pt-snap-analyzer"""

import typer
from typing_extensions import Annotated

app = typer.Typer(
    name="pt-snap",
    help="AI-friendly PyTorch Memory Snapshot Analyzer",
    no_args_is_help=True,
)


@app.command()
def use(
    db_path: Annotated[
        str, typer.Argument(help="Path to SQLite database")
    ],
):
    """Set current database for analysis"""
    from pt_snap_analyzer.context import Context, DatabaseNotFoundError
    
    try:
        ctx = Context(db_path)
        print(f"Using database: {db_path}")
        ctx.close()
    except DatabaseNotFoundError as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)


@app.command()
def config(
    device: Annotated[
        list[int], typer.Option(help="Device IDs to analyze (repeat for multiple)")
    ] = [],
):
    """Configure analysis settings"""
    print(f"Device filter: {device if device else 'all'}")


@app.command()
def version():
    """Show version information"""
    from pt_snap_analyzer.version import __version__
    print(f"pt-snap-analyzer v{__version__}")


@app.command()
def analyze():
    """Memory analysis commands"""
    raise typer.Exit(code=1)


@app.command()
def query():
    """Query management commands"""
    raise typer.Exit(code=1)


@app.command()
def rag():
    """RAG knowledge base commands"""
    raise typer.Exit(code=1)


@app.command()
def compare():
    """Compare two databases"""
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: 创建 CLI 测试文件**

```python
"""Tests for CLI commands"""

from click.testing import CliRunner
from pt_snap_analyzer.cli import app


def test_version():
    """Test version command"""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "pt-snap-analyzer v" in result.output


def test_use_command():
    """Test use command with valid database"""
    runner = CliRunner()
    result = runner.invoke(app, ["use", "examples/snapshot_expandable.pkl.db"])
    assert result.exit_code == 0
    assert "Using database:" in result.output


def test_use_command_invalid():
    """Test use command with invalid database"""
    runner = CliRunner()
    result = runner.invoke(app, ["use", "/nonexistent/path.db"])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_config_command():
    """Test config command"""
    runner = CliRunner()
    result = runner.invoke(app, ["config", "--device", "0", "--device", "1"])
    assert result.exit_code == 0
    assert "Device filter:" in result.output


def test_analyze_command():
    """Test analyze command (no subcommand)"""
    runner = CliRunner()
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 1


def test_help():
    """Test help output"""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AI-friendly PyTorch Memory Snapshot Analyzer" in result.output
```

- [ ] **Step 3: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_cli.py -v
```

Expected: 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add pt_snap_analyzer/cli.py tests/test_cli.py
git commit -m "feat: add CLI framework with subcommands"
```

---

### Task 6: 安装和验收测试

**Files:**
- Modify: `pyproject.toml` → add entry point
- Create: `tests/test_integration.py`

- [ ] **Step 1: 验证 entry point**

确保 `pyproject.toml` 包含:
```toml
[project.scripts]
pt-snap = "pt_snap_analyzer.cli:app"
```

- [ ] **Step 2: 创建集成测试**

```python
"""Integration tests for pt-snap-analyzer"""

import subprocess
import tempfile
import sqlite3
from pathlib import Path


def test_cli_command():
    """Test CLI command installation"""
    result = subprocess.run(
        ["pt-snap", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "AI-friendly PyTorch Memory Snapshot Analyzer" in result.stdout


def test_version_command():
    """Test version command"""
    result = subprocess.run(
        ["pt-snap", "version"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "v0.1.0" in result.output


def test_use_command_integration():
    """Test use command with real database"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE dictionary (
                table TEXT, column TEXT, key TEXT, value TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        result = subprocess.run(
            ["pt-snap", "use", str(db_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Using database:" in result.stdout


def test_sdk_import():
    """Test SDK can be imported"""
    from pt_snap_analyzer import Context, MemoryEvent, MemoryBlock, __version__
    assert __version__ == "0.1.0"
    assert Context is not None
    assert MemoryEvent is not None
    assert MemoryBlock is not None
```

- [ ] **Step 3: Run all tests**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/ -v
```

Expected: All tests PASS (15+ tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for CLI and SDK"
```

---

### 最终验收清单

- [ ] 所有测试通过 (15+ tests)
- [ ] CLI 命令 `pt-snap --help` 正常工作
- [ ] `pt-snap version` 输出正确版本
- [ ] `pt-snap use <db>` 可以打开数据库
- [ ] SDK 可以正常导入: `from pt_snap_analyzer import Context, MemoryEvent, MemoryBlock`
- [ ] 数据模型包含所有字段和属性
- [ ] Context 正确管理数据库连接
- [ ] pytest 覆盖率 > 80%

---

## 执行意见

Plan complete and saved to `docs/superpowers/plans/2026-04-04-pt-snap-analyzer-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 我分发每个任务的独立 subagent，任务间审查，快速迭代

**2. Inline Execution** - 在此会话中执行任务，使用 executing-plans，批次执行加检查点

**Which approach?**
