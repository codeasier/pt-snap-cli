# pt-snap-analyzer 分析器模块计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现核心分析器模块：泄漏检测、峰值分析、趋势分析、调用栈分析

**Architecture:** 基于 AnalyzerBase 抽象基类，每个分析器实现独立的 analyze() 方法，返回结构化结果

**Tech Stack:** Python 3.10+, SQLite3, Pydantic

---

## 文件结构

```
pt-snap-cli/
├── pt_snap_analyzer/
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── base.py            # AnalyzerBase 抽象基类
│   │   ├── leak_detector.py   # 泄漏检测
│   │   ├── peak_analyzer.py   # 峰值分析
│   │   ├── trend_analyzer.py  # 趋势分析
│   │   └── stack_analyzer.py  # 调用栈分析
│   └── models/                # 新增结果模型
│       ├── __init__.py
│       ├── result.py          # AnalysisResult 基类
│       ├── leak.py            # LeakResult
│       ├── peak.py            # PeakResult
│       ├── trend.py           # TrendResult
│       └── stack.py           # StackResult
└── tests/
    ├── test_analyzers.py
    ├── test_leak_detector.py
    ├── test_peak_analyzer.py
    ├── test_trend_analyzer.py
    └── test_stack_analyzer.py
```

---

### Task 1: 分析器基类和结果模型

**Files:**
- Create: `pt_snap_analyzer/analyzers/base.py`
- Create: `pt_snap_analyzer/models/result.py`
- Modify: `pt_snap_analyzer/models/__init__.py`

- [ ] **Step 1: 创建分析器基类**

```python
"""Base class for analyzers"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pt_snap_analyzer.context import Context


class AnalysisResult:
    """Base class for analysis results"""
    
    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        raise NotImplementedError
    
    def to_json(self) -> str:
        """Convert result to JSON string"""
        import json
        return json.dumps(self.to_dict())


class AnalyzerBase(ABC):
    """Base class for all analyzers
    
    Attributes:
        context: Analysis context with database connection
        name: Analyzer name
        description: Analyzer description
    """
    
    name: str = ""
    description: str = ""
    
    def __init__(self, context: Context):
        self.context = context
    
    @abstractmethod
    def analyze(self, **kwargs) -> AnalysisResult:
        """Run analysis and return results
        
        Args:
            **kwargs: Analyzer-specific parameters
        
        Returns:
            AnalysisResult instance
        """
        raise NotImplementedError
```

- [ ] **Step 2: 创建结果模型基类**

```python
"""Base class for analysis results"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnalysisResult:
    """Base class for all analysis results
    
    Attributes:
        metadata: Analysis metadata (database path, timestamp, etc.)
    """
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {"metadata": self.metadata}
    
    def to_json(self) -> str:
        """Convert result to JSON string"""
        import json
        return json.dumps(self.to_dict())
```

- [ ] **Step 3: 修改 models 初始化文件**

```python
"""Data models for memory snapshot analysis"""

from pt_snap_analyzer.models._enums import EventType, BlockState
from pt_snap_analyzer.models.event import MemoryEvent
from pt_snap_analyzer.models.block import MemoryBlock
from pt_snap_analyzer.models.result import AnalysisResult

__all__ = [
    "EventType", 
    "BlockState", 
    "MemoryEvent", 
    "MemoryBlock",
    "AnalysisResult",
]
```

- [ ] **Step 4: 创建测试文件**

```python
"""Tests for analyzer base classes"""

import pytest
from pt_snap_analyzer.analyzers.base import AnalyzerBase, AnalysisResult
from pt_snap_analyzer.context import Context


def test_analysis_result_defaults():
    """Test AnalysisResult default values"""
    result = AnalysisResult()
    assert result.metadata == {}


def test_analysis_result_with_metadata():
    """Test AnalysisResult with metadata"""
    metadata = {"database": "test.db", "timestamp": "2024-01-01"}
    result = AnalysisResult(metadata=metadata)
    assert result.metadata == metadata


def test_analysis_result_to_dict():
    """Test AnalysisResult.to_dict()"""
    metadata = {"database": "test.db"}
    result = AnalysisResult(metadata=metadata)
    result_dict = result.to_dict()
    assert result_dict == {"metadata": metadata}


def test_analyzer_base_abstract():
    """Test AnalyzerBase is abstract"""
    with pytest.raises(TypeError):
        AnalyzerBase(context=None)  # Can't instantiate abstract class


def test_analyzer_base_subclass():
    """Test AnalyzerBase subclass implementation"""
    class TestAnalyzer(AnalyzerBase):
        name = "test"
        description = "Test analyzer"
        
        def analyze(self, **kwargs):
            return AnalysisResult()
    
    from unittest.mock import MagicMock
    mock_context = MagicMock(spec=Context)
    analyzer = TestAnalyzer(context=mock_context)
    assert analyzer.name == "test"
    assert analyzer.description == "Test analyzer"
    result = analyzer.analyze()
    assert isinstance(result, AnalysisResult)
```

- [ ] **Step 5: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_analyzers.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add pt_snap_analyzer/analyzers/base.py pt_snap_analyzer/models/result.py
git commit -m "feat: add AnalyzerBase and AnalysisResult base classes"
```

---

### Task 2: 泄漏检测分析器

**Files:**
- Create: `pt_snap_analyzer/analyzers/leak_detector.py`
- Create: `pt_snap_analyzer/models/leak.py`
- Modify: `tests/test_leak_detector.py`

- [ ] **Step 1: 创建泄漏数据模型**

```python
"""Leak detection result models"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pt_snap_analyzer.models.block import MemoryBlock
from pt_snap_analyzer.models.result import AnalysisResult


@dataclass
class LeakInfo:
    """Information about a memory leak
    
    Attributes:
        block: Memory block that was leaked
        callstack: Call stack where memory was allocated
        size: Size of leaked memory in bytes
    """
    block: MemoryBlock
    callstack: Optional[str]
    size: int


@dataclass
class LeakResult(AnalysisResult):
    """Result of memory leak detection
    
    Attributes:
        leaks: List of detected leaks
        total_leaked: Total leaked memory in bytes
        leak_count: Number of leaked blocks
        devices: List of device IDs analyzed
    """
    leaks: List[LeakInfo] = field(default_factory=list)
    total_leaked: int = 0
    leak_count: int = 0
    devices: List[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert result to dictionary"""
        return {
            "metadata": self.metadata,
            "leaks": [
                {
                    "block_id": leak.block.id,
                    "address": leak.block.address,
                    "size": leak.size,
                    "callstack": leak.callstack,
                }
                for leak in self.leaks
            ],
            "total_leaked": self.total_leaked,
            "leak_count": self.leak_count,
            "devices": self.devices,
        }
```

- [ ] **Step 2: 创建泄漏检测分析器**

```python
"""Memory leak detector analyzer"""

from __future__ import annotations

from typing import List, Optional

from pt_snap_analyzer.analyzers.base import AnalyzerBase, AnalysisResult
from pt_snap_analyzer.context import Context
from pt_snap_analyzer.models.block import MemoryBlock
from pt_snap_analyzer.models.leak import LeakInfo, LeakResult


class LeakDetector(AnalyzerBase):
    """Detects memory leaks by finding blocks that were never freed
    
    Attributes:
        name: Analyzer name
        description: Analyzer description
    """
    
    name = "leak_detector"
    description = "Detect memory leaks by finding unfreed blocks"
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
    
    def detect_leaks(
        self,
        min_size: int = 1024,
        device_ids: Optional[List[int]] = None,
    ) -> LeakResult:
        """Detect memory leaks
        
        Args:
            min_size: Minimum block size to consider (bytes)
            device_ids: List of device IDs to analyze (None = all)
        
        Returns:
            LeakResult with detected leaks
        """
        if device_ids is None:
            device_ids = self.context.device_ids
        
        leaks: List[LeakInfo] = []
        total_leaked = 0
        
        for device_id in device_ids:
            cursor = self.context.cursor()
            
            # Query unfreed blocks
            cursor.execute(f"""
                SELECT b.id, b.address, b.size, b.requestedSize, b.state,
                       b.allocEventId, b.freeEventId, t.callstack
                FROM block_{device_id} b
                LEFT JOIN trace_entry_{device_id} t ON b.allocEventId = t.id
                WHERE b.id >= 0 
                  AND (b.freeEventId IS NULL OR b.freeEventId = -1)
                  AND b.size >= ?
                ORDER BY b.size DESC
            """, (min_size,))
            
            for row in cursor.fetchall():
                block = MemoryBlock(
                    id=row[0],
                    address=row[1],
                    size=row[2],
                    requestedSize=row[3],
                    state=row[4],
                    allocEventId=row[5],
                    freeEventId=row[6],
                )
                callstack = row[7]
                
                leak = LeakInfo(
                    block=block,
                    callstack=callstack,
                    size=block.size,
                )
                leaks.append(leak)
                total_leaked += block.size
        
        result = LeakResult(
            metadata={
                "analyzer": self.name,
                "min_size": min_size,
                "devices": device_ids,
            },
            leaks=leaks,
            total_leaked=total_leaked,
            leak_count=len(leaks),
            devices=device_ids,
        )
        return result
    
    def analyze(self, **kwargs) -> AnalysisResult:
        """Run leak detection analysis"""
        return self.detect_leaks(**kwargs)
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for LeakDetector"""

import pytest
from unittest.mock import MagicMock
from pt_snap_analyzer.analyzers.leak_detector import LeakDetector, LeakInfo, LeakResult
from pt_snap_analyzer.models.block import MemoryBlock


def test_leak_detector_init():
    """Test LeakDetector initialization"""
    mock_context = MagicMock()
    detector = LeakDetector(mock_context)
    assert detector.name == "leak_detector"
    assert detector.description == "Detect memory leaks by finding unfreed blocks"


def test_leak_info_dataclass():
    """Test LeakInfo dataclass"""
    block = MemoryBlock(
        id=100, address=0x1000, size=4096, requestedSize=4096,
        state=1, allocEventId=50, freeEventId=None
    )
    leak = LeakInfo(
        block=block,
        callstack="test.py:10",
        size=4096
    )
    assert leak.block == block
    assert leak.callstack == "test.py:10"
    assert leak.size == 4096


def test_leak_result_dataclass():
    """Test LeakResult dataclass"""
    block = MemoryBlock(
        id=100, address=0x1000, size=4096, requestedSize=4096,
        state=1, allocEventId=50, freeEventId=None
    )
    leak = LeakInfo(block=block, callstack="test.py:10", size=4096)
    result = LeakResult(
        leaks=[leak],
        total_leaked=4096,
        leak_count=1,
        devices=[0]
    )
    assert len(result.leaks) == 1
    assert result.total_leaked == 4096
    assert result.leak_count == 1


def test_leak_result_to_dict():
    """Test LeakResult.to_dict()"""
    block = MemoryBlock(
        id=100, address=0x1000, size=4096, requestedSize=4096,
        state=1, allocEventId=50, freeEventId=None
    )
    leak = LeakInfo(block=block, callstack="test.py:10", size=4096)
    result = LeakResult(
        leaks=[leak],
        total_leaked=4096,
        leak_count=1,
        devices=[0]
    )
    result_dict = result.to_dict()
    assert "metadata" in result_dict
    assert "leaks" in result_dict
    assert result_dict["leak_count"] == 1
    assert result_dict["total_leaked"] == 4096


def test_analyze_method():
    """Test analyze() calls detect_leaks()"""
    mock_context = MagicMock()
    detector = LeakDetector(mock_context)
    
    mock_result = MagicMock(spec=LeakResult)
    detector.detect_leaks = MagicMock(return_value=mock_result)
    
    result = detector.analyze(min_size=1024)
    
    detector.detect_leaks.assert_called_once_with(min_size=1024)
    assert result == mock_result
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_leak_detector.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/analyzers/leak_detector.py pt_snap_analyzer/models/leak.py
git commit -m "feat: add LeakDetector for memory leak detection"
```

---

### Task 3: 峰值分析器

**Files:**
- Create: `pt_snap_analyzer/models/peak.py`
- Create: `pt_snap_analyzer/analyzers/peak_analyzer.py`
- Create: `tests/test_peak_analyzer.py`

- [ ] **Step 1: 创建峰值数据模型**

```python
"""Peak analysis result models"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pt_snap_analyzer.models.result import AnalysisResult


@dataclass
class PeakInfo:
    """Information about a memory peak
    
    Attributes:
        event_id: Event ID where peak occurred
        timestamp: Event timestamp
        size: Peak size in bytes
        allocated: Total allocated at peak
        active: Total active at peak
        reserved: Total reserved at peak
    """
    event_id: int
    timestamp: int
    size: int
    allocated: int
    active: int
    reserved: int


@dataclass
class PeakResult(AnalysisResult):
    """Result of memory peak analysis
    
    Attributes:
        peaks: List of detected peaks
        total_peaks: Number of peaks detected
        max_size: Maximum peak size in bytes
        avg_size: Average peak size in bytes
        devices: List of device IDs analyzed
    """
    peaks: List[PeakInfo] = field(default_factory=list)
    total_peaks: int = 0
    max_size: int = 0
    avg_size: float = 0.0
    devices: List[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert result to dictionary"""
        return {
            "metadata": self.metadata,
            "peaks": [
                {
                    "event_id": peak.event_id,
                    "timestamp": peak.timestamp,
                    "size": peak.size,
                    "allocated": peak.allocated,
                    "active": peak.active,
                    "reserved": peak.reserved,
                }
                for peak in self.peaks
            ],
            "total_peaks": self.total_peaks,
            "max_size": self.max_size,
            "avg_size": self.avg_size,
            "devices": self.devices,
        }
```

- [ ] **Step 2: 创建峰值分析器**

```python
"""Peak analyzer for memory allocation spikes"""

from __future__ import annotations

from typing import List, Optional

from pt_snap_analyzer.analyzers.base import AnalyzerBase, AnalysisResult
from pt_snap_analyzer.context import Context
from pt_snap_analyzer.models.peak import PeakInfo, PeakResult


class PeakAnalyzer(AnalyzerBase):
    """Analyzes memory peaks (allocation spikes)
    
    Attributes:
        name: Analyzer name
        description: Analyzer description
    """
    
    name = "peak_analyzer"
    description = "Analyze memory allocation peaks"
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
    
    def analyze_peaks(
        self,
        top_k: int = 10,
        device_ids: Optional[List[int]] = None,
    ) -> PeakResult:
        """Analyze memory peaks
        
        Args:
            top_k: Number of top peaks to return
            device_ids: List of device IDs to analyze (None = all)
        
        Returns:
            PeakResult with top K peaks
        """
        if device_ids is None:
            device_ids = self.context.device_ids
        
        all_peaks: List[PeakInfo] = []
        
        for device_id in device_ids:
            cursor = self.context.cursor()
            
            # Query top allocations by size
            cursor.execute(f"""
                SELECT id, address, size, allocated, active, reserved
                FROM trace_entry_{device_id}
                WHERE action = 4  -- ALLOC
                ORDER BY size DESC
                LIMIT ?
            """, (top_k,))
            
            for row in cursor.fetchall():
                peak = PeakInfo(
                    event_id=row[0],
                    timestamp=row[0],  # Use event_id as timestamp
                    size=row[2],
                    allocated=row[3],
                    active=row[4],
                    reserved=row[5],
                )
                all_peaks.append(peak)
        
        # Sort and take top K
        all_peaks.sort(key=lambda p: p.size, reverse=True)
        top_peaks = all_peaks[:top_k]
        
        total_size = sum(p.size for p in top_peaks)
        avg_size = total_size / len(top_peaks) if top_peaks else 0.0
        max_size = top_peaks[0].size if top_peaks else 0
        
        result = PeakResult(
            metadata={
                "analyzer": self.name,
                "top_k": top_k,
                "devices": device_ids,
            },
            peaks=top_peaks,
            total_peaks=len(top_peaks),
            max_size=max_size,
            avg_size=avg_size,
            devices=device_ids,
        )
        return result
    
    def analyze(self, **kwargs) -> AnalysisResult:
        """Run peak analysis"""
        return self.analyze_peaks(**kwargs)
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for PeakAnalyzer"""

import pytest
from unittest.mock import MagicMock
from pt_snap_analyzer.analyzers.peak_analyzer import PeakAnalyzer, PeakInfo, PeakResult


def test_peak_analyzer_init():
    """Test PeakAnalyzer initialization"""
    mock_context = MagicMock()
    analyzer = PeakAnalyzer(mock_context)
    assert analyzer.name == "peak_analyzer"


def test_peak_info_dataclass():
    """Test PeakInfo dataclass"""
    peak = PeakInfo(
        event_id=100,
        timestamp=100,
        size=4096,
        allocated=8192,
        active=8192,
        reserved=16384,
    )
    assert peak.event_id == 100
    assert peak.size == 4096
    assert peak.allocated == 8192


def test_peak_result_dataclass():
    """Test PeakResult dataclass"""
    peak = PeakInfo(
        event_id=100, timestamp=100, size=4096,
        allocated=8192, active=8192, reserved=16384,
    )
    result = PeakResult(
        peaks=[peak],
        total_peaks=1,
        max_size=4096,
        avg_size=4096.0,
        devices=[0],
    )
    assert len(result.peaks) == 1
    assert result.max_size == 4096


def test_peak_result_to_dict():
    """Test PeakResult.to_dict()"""
    peak = PeakInfo(
        event_id=100, timestamp=100, size=4096,
        allocated=8192, active=8192, reserved=16384,
    )
    result = PeakResult(
        peaks=[peak],
        total_peaks=1,
        max_size=4096,
        avg_size=4096.0,
        devices=[0],
    )
    result_dict = result.to_dict()
    assert "peaks" in result_dict
    assert result_dict["total_peaks"] == 1
    assert result_dict["max_size"] == 4096


def test_analyze_peaks_empty():
    """Test analyze_peaks with no data"""
    mock_context = MagicMock()
    mock_context.device_ids = []
    analyzer = PeakAnalyzer(mock_context)
    
    result = analyzer.analyze_peaks(top_k=10)
    assert result.total_peaks == 0
    assert result.max_size == 0
    assert result.avg_size == 0.0
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_peak_analyzer.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/models/peak.py pt_snap_analyzer/analyzers/peak_analyzer.py
git commit -m "feat: add PeakAnalyzer for memory peak detection"
```

---

### Task 4: 趋势分析器

**Files:**
- Create: `pt_snap_analyzer/models/trend.py`
- Create: `pt_snap_analyzer/analyzers/trend_analyzer.py`
- Create: `tests/test_trend_analyzer.py`

- [ ] **Step 1: 创建趋势数据模型**

```python
"""Memory trend analysis result models"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pt_snap_analyzer.models.result import AnalysisResult


@dataclass
class TrendPoint:
    """A single point in memory usage trend
    
    Attributes:
        timestamp: Event ID / timestamp
        allocated: Total allocated memory
        active: Total active memory
        reserved: Total reserved memory
    """
    timestamp: int
    allocated: int
    active: int
    reserved: int


@dataclass
class TrendResult(AnalysisResult):
    """Result of memory trend analysis
    
    Attributes:
        points: List of trend points
        total_points: Number of data points
        start_allocated: Starting allocated memory
        end_allocated: Ending allocated memory
        max_allocated: Maximum allocated memory
        min_allocated: Minimum allocated memory
        devices: List of device IDs analyzed
    """
    points: List[TrendPoint] = field(default_factory=list)
    total_points: int = 0
    start_allocated: int = 0
    end_allocated: int = 0
    max_allocated: int = 0
    min_allocated: int = 0
    devices: List[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert result to dictionary"""
        return {
            "metadata": self.metadata,
            "points": [
                {
                    "timestamp": p.timestamp,
                    "allocated": p.allocated,
                    "active": p.active,
                    "reserved": p.reserved,
                }
                for p in self.points
            ],
            "total_points": self.total_points,
            "start_allocated": self.start_allocated,
            "end_allocated": self.end_allocated,
            "max_allocated": self.max_allocated,
            "min_allocated": self.min_allocated,
            "devices": self.devices,
        }
```

- [ ] **Step 2: 创建趋势分析器**

```python
"""Trend analyzer for memory usage over time"""

from __future__ import annotations

from typing import List, Optional, Literal

from pt_snap_analyzer.analyzers.base import AnalyzerBase, AnalysisResult
from pt_snap_analyzer.context import Context
from pt_snap_analyzer.models.trend import TrendPoint, TrendResult


MetricType = Literal["allocated", "active", "reserved"]


class TrendAnalyzer(AnalyzerBase):
    """Analyzes memory usage trends over time
    
    Attributes:
        name: Analyzer name
        description: Analyzer description
    """
    
    name = "trend_analyzer"
    description = "Analyze memory usage trends over time"
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
    
    def analyze_trend(
        self,
        metrics: List[MetricType] = ["allocated", "active", "reserved"],
        device_ids: Optional[List[int]] = None,
    ) -> TrendResult:
        """Analyze memory usage trend
        
        Args:
            metrics: List of metrics to track
            device_ids: List of device IDs to analyze (None = all)
        
        Returns:
            TrendResult with time series data
        """
        if device_ids is None:
            device_ids = self.context.device_ids
        
        all_points: List[TrendPoint] = []
        
        for device_id in device_ids:
            cursor = self.context.cursor()
            
            # Query all events ordered by ID
            cursor.execute(f"""
                SELECT id, allocated, active, reserved
                FROM trace_entry_{device_id}
                ORDER BY id ASC
            """)
            
            for row in cursor.fetchall():
                point = TrendPoint(
                    timestamp=row[0],
                    allocated=row[1],
                    active=row[2],
                    reserved=row[3],
                )
                all_points.append(point)
        
        if not all_points:
            return TrendResult(
                metadata={
                    "analyzer": self.name,
                    "metrics": metrics,
                    "devices": device_ids,
                },
                devices=device_ids,
            )
        
        # Calculate statistics
        allocated_values = [p.allocated for p in all_points]
        start_allocated = allocated_values[0]
        end_allocated = allocated_values[-1]
        max_allocated = max(allocated_values)
        min_allocated = min(allocated_values)
        
        result = TrendResult(
            metadata={
                "analyzer": self.name,
                "metrics": metrics,
                "devices": device_ids,
            },
            points=all_points,
            total_points=len(all_points),
            start_allocated=start_allocated,
            end_allocated=end_allocated,
            max_allocated=max_allocated,
            min_allocated=min_allocated,
            devices=device_ids,
        )
        return result
    
    def analyze(self, **kwargs) -> AnalysisResult:
        """Run trend analysis"""
        return self.analyze_trend(**kwargs)
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for TrendAnalyzer"""

import pytest
from unittest.mock import MagicMock
from pt_snap_analyzer.analyzers.trend_analyzer import TrendAnalyzer, TrendPoint, TrendResult


def test_trend_analyzer_init():
    """Test TrendAnalyzer initialization"""
    mock_context = MagicMock()
    analyzer = TrendAnalyzer(mock_context)
    assert analyzer.name == "trend_analyzer"


def test_trend_point_dataclass():
    """Test TrendPoint dataclass"""
    point = TrendPoint(
        timestamp=100,
        allocated=8192,
        active=8192,
        reserved=16384,
    )
    assert point.timestamp == 100
    assert point.allocated == 8192


def test_trend_result_dataclass():
    """Test TrendResult dataclass"""
    point = TrendPoint(
        timestamp=100, allocated=8192, active=8192, reserved=16384,
    )
    result = TrendResult(
        points=[point],
        total_points=1,
        start_allocated=8192,
        end_allocated=8192,
        max_allocated=8192,
        min_allocated=8192,
        devices=[0],
    )
    assert len(result.points) == 1
    assert result.total_points == 1


def test_trend_result_statistics():
    """Test TrendResult statistics calculation"""
    points = [
        TrendPoint(timestamp=1, allocated=1000, active=1000, reserved=2000),
        TrendPoint(timestamp=2, allocated=2000, active=2000, reserved=4000),
        TrendPoint(timestamp=3, allocated=1500, active=1500, reserved=3000),
    ]
    result = TrendResult(
        points=points,
        total_points=3,
        start_allocated=1000,
        end_allocated=1500,
        max_allocated=2000,
        min_allocated=1000,
        devices=[0],
    )
    assert result.start_allocated == 1000
    assert result.end_allocated == 1500
    assert result.max_allocated == 2000
    assert result.min_allocated == 1000


def test_analyze_trend_empty():
    """Test analyze_trend with no data"""
    mock_context = MagicMock()
    mock_context.device_ids = []
    analyzer = TrendAnalyzer(mock_context)
    
    result = analyzer.analyze_trend()
    assert result.total_points == 0
    assert result.start_allocated == 0
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_trend_analyzer.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/models/trend.py pt_snap_analyzer/analyzers/trend_analyzer.py
git commit -m "feat: add TrendAnalyzer for memory usage trends"
```

---

### Task 5: 调用栈分析器

**Files:**
- Create: `pt_snap_analyzer/models/stack.py`
- Create: `pt_snap_analyzer/analyzers/stack_analyzer.py`
- Create: `tests/test_stack_analyzer.py`

- [ ] **Step 1: 创建调用栈数据模型**

```python
"""Call stack analysis result models"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pt_snap_analyzer.models.result import AnalysisResult


@dataclass
class StackInfo:
    """Information about a call stack pattern
    
    Attributes:
        callstack: The call stack string (multiline)
        count: Number of times this callstack appeared
        total_size: Total memory allocated by this callstack
        frames: Parsed call stack frames
    """
    callstack: str
    count: int = 0
    total_size: int = 0
    frames: List[str] = field(default_factory=list)
    
    @property
    def avg_size(self) -> float:
        """Average allocation size"""
        return self.total_size / self.count if self.count > 0 else 0.0


@dataclass
class StackResult(AnalysisResult):
    """Result of call stack analysis
    
    Attributes:
        stacks: List of call stack patterns
        total_stacks: Number of unique call stacks
        total_allocations: Total allocation count
        total_size: Total allocated memory
        devices: List of device IDs analyzed
    """
    stacks: List[StackInfo] = field(default_factory=list)
    total_stacks: int = 0
    total_allocations: int = 0
    total_size: int = 0
    devices: List[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert result to dictionary"""
        return {
            "metadata": self.metadata,
            "stacks": [
                {
                    "callstack": s.callstack,
                    "count": s.count,
                    "total_size": s.total_size,
                    "avg_size": s.avg_size,
                    "frames": s.frames,
                }
                for s in self.stacks
            ],
            "total_stacks": self.total_stacks,
            "total_allocations": self.total_allocations,
            "total_size": self.total_size,
            "devices": self.devices,
        }
```

- [ ] **Step 2: 创建调用栈分析器**

```python
"""Call stack analyzer for allocation patterns"""

from __future__ import annotations

from typing import List, Optional, Literal

from pt_snap_analyzer.analyzers.base import AnalyzerBase, AnalysisResult
from pt_snap_analyzer.context import Context
from pt_snap_analyzer.models.stack import StackInfo, StackResult


GroupByType = Literal["function", "file"]


class StackAnalyzer(AnalyzerBase):
    """Analyzes call stack patterns in memory allocations
    
    Attributes:
        name: Analyzer name
        description: Analyzer description
    """
    
    name = "stack_analyzer"
    description = "Analyze call stack patterns in memory allocations"
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
    
    def analyze_stack_trace(
        self,
        top_k: int = 10,
        group_by: GroupByType = "function",
        device_ids: Optional[List[int]] = None,
    ) -> StackResult:
        """Analyze call stack patterns
        
        Args:
            top_k: Number of top call stacks to return
            group_by: Group by 'function' or 'file'
            device_ids: List of device IDs to analyze (None = all)
        
        Returns:
            StackResult with top K call stacks
        """
        if device_ids is None:
            device_ids = self.context.device_ids
        
        stack_counts: dict[str, int] = {}
        stack_sizes: dict[str, int] = {}
        
        for device_id in device_ids:
            cursor = self.context.cursor()
            
            # Query events with callstacks
            cursor.execute(f"""
                SELECT id, size, callstack
                FROM trace_entry_{device_id}
                WHERE callstack IS NOT NULL
                  AND callstack != ''
                ORDER BY size DESC
                LIMIT 10000  -- Limit for performance
            """)
            
            for row in cursor.fetchall():
                callstack = row[2]
                size = row[1]
                
                if callstack not in stack_counts:
                    stack_counts[callstack] = 0
                    stack_sizes[callstack] = 0
                
                stack_counts[callstack] += 1
                stack_sizes[callstack] += size
        
        # Build StackInfo list
        stacks: List[StackInfo] = []
        for callstack, count in stack_counts.items():
            stack = StackInfo(
                callstack=callstack,
                count=count,
                total_size=stack_sizes[callstack],
                frames=self._parse_frames(callstack, group_by),
            )
            stacks.append(stack)
        
        # Sort by count and take top K
        stacks.sort(key=lambda s: s.count, reverse=True)
        top_stacks = stacks[:top_k]
        
        total_allocations = sum(s.count for s in top_stacks)
        total_size = sum(s.total_size for s in top_stacks)
        
        result = StackResult(
            metadata={
                "analyzer": self.name,
                "top_k": top_k,
                "group_by": group_by,
                "devices": device_ids,
            },
            stacks=top_stacks,
            total_stacks=len(top_stacks),
            total_allocations=total_allocations,
            total_size=total_size,
            devices=device_ids,
        )
        return result
    
    def _parse_frames(self, callstack: str, group_by: GroupByType) -> List[str]:
        """Parse call stack into frames
        
        Args:
            callstack: Multi-line call stack string
            group_by: Group by function or file
        
        Returns:
            List of frame identifiers
        """
        frames = []
        for line in callstack.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            
            if group_by == "function":
                # Extract function name (last part after last space)
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    frames.append(parts[1])
                else:
                    frames.append(line)
            else:  # group_by == "file"
                # Extract file path and line number
                if ":" in line:
                    parts = line.rsplit(":", 1)
                    frames.append(f"{parts[0]}:{parts[1]}")
                else:
                    frames.append(line)
        
        return frames
    
    def analyze(self, **kwargs) -> AnalysisResult:
        """Run stack analysis"""
        return self.analyze_stack_trace(**kwargs)
```

- [ ] **Step 3: 创建测试文件**

```python
"""Tests for StackAnalyzer"""

import pytest
from unittest.mock import MagicMock
from pt_snap_analyzer.analyzers.stack_analyzer import StackAnalyzer, StackInfo, StackResult


def test_stack_analyzer_init():
    """Test StackAnalyzer initialization"""
    mock_context = MagicMock()
    analyzer = StackAnalyzer(mock_context)
    assert analyzer.name == "stack_analyzer"


def test_stack_info_dataclass():
    """Test StackInfo dataclass"""
    info = StackInfo(
        callstack="file.py:10 function",
        count=5,
        total_size=20480,
    )
    assert info.callstack == "file.py:10 function"
    assert info.count == 5
    assert info.total_size == 20480
    assert info.avg_size == 4096.0


def test_stack_result_dataclass():
    """Test StackResult dataclass"""
    info = StackInfo(
        callstack="file.py:10 function",
        count=5,
        total_size=20480,
    )
    result = StackResult(
        stacks=[info],
        total_stacks=1,
        total_allocations=5,
        total_size=20480,
        devices=[0],
    )
    assert len(result.stacks) == 1
    assert result.total_allocations == 5


def test_analyze_stack_trace_empty():
    """Test analyze_stack_trace with no data"""
    mock_context = MagicMock()
    mock_context.device_ids = []
    analyzer = StackAnalyzer(mock_context)
    
    result = analyzer.analyze_stack_trace()
    assert result.total_stacks == 0
    assert result.total_allocations == 0


def test_parse_frames():
    """Test _parse_frames method"""
    mock_context = MagicMock()
    analyzer = StackAnalyzer(mock_context)
    
    callstack = "test.py:10 main\\n  test.py:5 train\\n  test.py:3 step"
    
    frames_func = analyzer._parse_frames(callstack, "function")
    frames_file = analyzer._parse_frames(callstack, "file")
    
    assert len(frames_func) == 3
    assert len(frames_file) == 3
```

- [ ] **Step 4: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_stack_analyzer.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/models/stack.py pt_snap_analyzer/analyzers/stack_analyzer.py
git commit -m "feat: add StackAnalyzer for call stack pattern analysis"
```

---

### Task 6: CLI 集成和测试

**Files:**
- Modify: `pt_snap_analyzer/cli.py`
- Create: `tests/test_cli_analyze.py`

- [ ] **Step 1: 添加 analyze 命令到 CLI**

```python
# Add to cli.py after imports

from pt_snap_analyzer.analyzers.leak_detector import LeakDetector
from pt_snap_analyzer.analyzers.peak_analyzer import PeakAnalyzer
from pt_snap_analyzer.analyzers.trend_analyzer import TrendAnalyzer
from pt_snap_analyzer.analyzers.stack_analyzer import StackAnalyzer
from pt_snap_analyzer.context import Context, DatabaseNotFoundError


@app.command()
def analyze():
    """Memory analysis commands"""
    raise typer.Exit(code=1)


@app.command()
def analyze_leak(
    min_size: Annotated[
        int, typer.Option(help="Minimum leak size in bytes")
    ] = 1024,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
):
    """Detect memory leaks"""
    # Get current database
    db_path = _get_current_db()
    if db_path is None:
        print("Error: No database selected. Use 'pt-snap use <db>' first.", flush=True)
        raise typer.Exit(code=1)
    
    try:
        with Context(db_path) as ctx:
            detector = LeakDetector(ctx)
            result = detector.detect_leaks(min_size=min_size)
            
            if json_output:
                print(result.to_json())
            else:
                _print_leak_result(result)
    except DatabaseNotFoundError as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)


@app.command()
def analyze_peak(
    top_k: Annotated[
        int, typer.Option(help="Number of top peaks to show")
    ] = 10,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
):
    """Analyze memory peaks"""
    db_path = _get_current_db()
    if db_path is None:
        print("Error: No database selected. Use 'pt-snap use <db>' first.", flush=True)
        raise typer.Exit(code=1)
    
    try:
        with Context(db_path) as ctx:
            analyzer = PeakAnalyzer(ctx)
            result = analyzer.analyze_peaks(top_k=top_k)
            
            if json_output:
                print(result.to_json())
            else:
                _print_peak_result(result)
    except DatabaseNotFoundError as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)


def _get_current_db() -> Optional[str]:
    """Get current database path"""
    import os
    config_dir = Path.home() / ".config" / "pt-snap-analyzer"
    config_file = config_dir / "current_db"
    
    if config_file.exists():
        return config_file.read_text().strip()
    return None
```

- [ ] **Step 2: 创建 CLI 分析测试**

```python
"""Tests for CLI analyze commands"""

from click.testing import CliRunner
from pt_snap_analyzer.cli import app


def test_analyze_leak_json():
    """Test analyze-leak with JSON output"""
    runner = CliRunner()
    result = runner.invoke(app, ["analyze-leak", "--json"])
    # Expected to fail because no database selected
    assert result.exit_code != 0


def test_analyze_peak_json():
    """Test analyze-peak with JSON output"""
    runner = CliRunner()
    result = runner.invoke(app, ["analyze-peak", "--json"])
    # Expected to fail because no database selected
    assert result.exit_code != 0


def test_help_text():
    """Test help text includes analyze commands"""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Memory analysis commands" in result.output
```

- [ ] **Step 3: 运行所有 analyze 测试**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_cli_analyze.py -v
```

Expected: 3 tests PASS

- [ ] **Step 4: 运行完整测试套件**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/ -v
```

Expected: 20+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/cli.py tests/test_cli_analyze.py
git commit -m "feat: integrate analyzers into CLI"
```

---

### 最终验收清单

- [ ] 所有测试通过 (20+ tests)
- [ ] LeakDetector 正确检测泄漏
- [ ] PeakAnalyzer 正确识别峰值
- [ ] TrendAnalyzer 正确生成趋势数据
- [ ] StackAnalyzer 正确分析调用栈
- [ ] CLI 命令正常工作
- [ ] JSON 输出格式正确
- [ ] pytest 覆盖率 > 80%

---

## 执行意见

Plan complete and saved to `docs/superpowers/plans/2026-04-04-pt-snap-analyzer-analyzers.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 我分发每个任务的独立 subagent，任务间审查，快速迭代

**2. Inline Execution** - 在此会话中执行任务，使用 executing-plans，批次执行加检查点

**Which approach?**
