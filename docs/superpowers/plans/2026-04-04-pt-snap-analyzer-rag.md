# pt-snap-analyzer RAG 知识库计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 RAG 知识库，支持案例归档、向量搜索和相似案例检索

**Architecture:** 使用 ChromaDB 存储向量，简单的关键词搜索作为备用，CLI 和 SDK 双接口

**Tech Stack:** Python 3.10+, ChromaDB, LangChain（可选）

---

## 文件结构

```
pt-snap-cli/
├── pt_snap_analyzer/
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── models.py          # RAG 数据模型
│   │   ├── archive.py         # 案例归档
│   │   └── searcher.py        # 案例检索
│   └── cli.py                 # 添加 rag 命令
└── tests/
    ├── test_rag_models.py
    ├── test_rag_archive.py
    ├── test_rag_searcher.py
    └── test_rag_cli.py
```

---

### Task 1: RAG 数据模型

**Files:**
- Create: `pt_snap_analyzer/rag/models.py`
- Create: `tests/test_rag_models.py`

- [ ] **Step 1: 创建数据模型**

```python
"""RAG knowledge base data models"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class AnalysisStep:
    """A step in the analysis process"""
    
    step: int
    command: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    description: str = ""


@dataclass
class RAGCase:
    """A case in the RAG knowledge base
    
    Attributes:
        case_id: Unique case identifier
        timestamp: When the case was created
        db_snapshot: Path to the snapshot database
        analysis_steps: List of analysis steps
        conclusion: Final conclusion
        root_cause: Root cause analysis
        solution: Solution or workaround
        tags: List of tags for filtering
        confidence: Confidence level (0-1)
        verified_by: Who verified the case
    """
    case_id: str = ""
    timestamp: str = ""
    db_snapshot: str = ""
    analysis_steps: List[AnalysisStep] = field(default_factory=list)
    conclusion: str = ""
    root_cause: str = ""
    solution: str = ""
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0
    verified_by: str = "unverified"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.case_id:
            self.case_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class SearchMatch:
    """A matched case from search
    
    Attributes:
        case: The matched case
        score: Relevance score (0-1)
        query_match: Which query terms matched
    """
    case: RAGCase
    score: float = 0.0
    query_match: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result of RAG search
    
    Attributes:
        matches: List of matched cases
        total_results: Total number of matches
        query: Original search query
    """
    matches: List[SearchMatch] = field(default_factory=list)
    total_results: int = 0
    query: str = ""
```

- [ ] **Step 2: 创建测试文件**

```python
"""Tests for RAG data models"""

import pytest
from datetime import datetime
from pt_snap_analyzer.rag.models import (
    AnalysisStep,
    RAGCase,
    SearchMatch,
    SearchResult,
)


def test_analysis_step():
    """Test AnalysisStep dataclass"""
    step = AnalysisStep(
        step=1,
        command="leak-detection",
        parameters={"min_size": 1024},
        result_summary="Found 5 leaks",
        description="Detect memory leaks",
    )
    assert step.step == 1
    assert step.command == "leak-detection"
    assert step.parameters == {"min_size": 1024}


def test_rag_case_defaults():
    """Test RAGCase with defaults"""
    case = RAGCase(
        conclusion="Memory leak in attention layer",
        root_cause="Cache not released",
        solution="Upgrade transformers",
        tags=["memory-leak", "transformer"],
    )
    
    assert case.case_id != ""
    assert case.timestamp != ""
    assert len(case.case_id) > 0


def test_rag_case_with_steps():
    """Test RAGCase with analysis steps"""
    steps = [
        AnalysisStep(
            step=1,
            command="leak-detection",
            parameters={"min_size": 1024},
            result_summary="Found 5 leaks",
        ),
        AnalysisStep(
            step=2,
            command="peak-analysis",
            parameters={"top_k": 10},
            result_summary="Peak at epoch 100",
        ),
    ]
    
    case = RAGCase(
        conclusion="Leak from large allocations",
        root_cause="Not freed after epoch",
        solution="Manual cleanup",
        tags=["memory-leak"],
        analysis_steps=steps,
    )
    
    assert len(case.analysis_steps) == 2
    assert case.analysis_steps[0].command == "leak-detection"


def test_rag_case_serialization():
    """Test RAGCase to dict"""
    case = RAGCase(
        case_id="test-123",
        timestamp="2024-01-01T00:00:00Z",
        conclusion="Test conclusion",
        root_cause="Test cause",
        solution="Test solution",
        tags=["tag1", "tag2"],
    )
    
    case_dict = {
        "case_id": case.case_id,
        "timestamp": case.timestamp,
        "conclusion": case.conclusion,
        "root_cause": case.root_cause,
        "solution": case.solution,
        "tags": case.tags,
    }
    
    assert case_dict["case_id"] == "test-123"
    assert len(case_dict["tags"]) == 2


def test_search_match():
    """Test SearchMatch dataclass"""
    case = RAGCase(
        case_id="test-123",
        conclusion="Test conclusion",
    )
    
    match = SearchMatch(
        case=case,
        score=0.85,
        query_match=["memory", "leak"],
    )
    
    assert match.case == case
    assert match.score == 0.85
    assert match.query_match == ["memory", "leak"]


def test_search_result():
    """Test SearchResult dataclass"""
    case = RAGCase(
        case_id="test-123",
        conclusion="Test conclusion",
    )
    match = SearchMatch(case=case, score=0.85)
    
    result = SearchResult(
        matches=[match],
        total_results=1,
        query="memory leak",
    )
    
    assert len(result.matches) == 1
    assert result.total_results == 1
    assert result.query == "memory leak"
```

- [ ] **Step 3: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_rag_models.py -v
```

Expected: 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add pt_snap_analyzer/rag/models.py tests/test_rag_models.py
git commit -m "feat: add RAG data models"
```

---

### Task 2: 案例归档系统

**Files:**
- Create: `pt_snap_analyzer/rag/archive.py`
- Create: `tests/test_rag_archive.py`

- [ ] **Step 1: 创建归档器**

```python
"""Case archive for RAG knowledge base"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pt_snap_analyzer.rag.models import RAGCase


class ArchiveError(Exception):
    """Raised when archive operations fail"""
    pass


class CaseArchive:
    """Archive and manage RAG cases
    
    Attributes:
        archive_dir: Directory for storing case files
    """
    
    def __init__(self, archive_dir: Optional[str] = None):
        """Initialize archive
        
        Args:
            archive_dir: Directory for storing cases
        """
        if archive_dir is None:
            home = Path.home()
            self.archive_dir = home / ".local" / "share" / "pt-snap-analyzer" / "rag_archive"
        else:
            self.archive_dir = Path(archive_dir)
        
        self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def add_case(self, case: RAGCase) -> str:
        """Add a case to the archive
        
        Args:
            case: RAGCase to add
        
        Returns:
            Case ID
        
        Raises:
            ArchiveError: If save fails
        """
        case_id = case.case_id
        
        # Validate required fields
        if not case.conclusion:
            raise ArchiveError("Case must have a conclusion")
        if not case.solution:
            raise ArchiveError("Case must have a solution")
        
        # Serialize case
        case_dict = self._case_to_dict(case)
        
        # Save to file
        file_path = self.archive_dir / f"{case_id}.json"
        try:
            with open(file_path, "w") as f:
                json.dump(case_dict, f, indent=2)
        except Exception as e:
            raise ArchiveError(f"Failed to save case: {e}")
        
        return case_id
    
    def get_case(self, case_id: str) -> Optional[RAGCase]:
        """Get a case by ID
        
        Args:
            case_id: Case identifier
        
        Returns:
            RAGCase or None if not found
        """
        file_path = self.archive_dir / f"{case_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r") as f:
                case_dict = json.load(f)
            return self._dict_to_case(case_dict)
        except Exception as e:
            print(f"Warning: Failed to load case {case_id}: {e}")
            return None
    
    def list_cases(self, tags: Optional[List[str]] = None) -> List[RAGCase]:
        """List all cases, optionally filtered by tags
        
        Args:
            tags: List of tags to filter by
        
        Returns:
            List of RAGCases
        """
        cases = []
        
        for file_path in self.archive_dir.glob("*.json"):
            try:
                case = self.get_case(file_path.stem)
                if case is not None:
                    if tags is None:
                        cases.append(case)
                    else:
                        # Filter by tags (AND logic)
                        if all(t in case.tags for t in tags):
                            cases.append(case)
            except Exception as e:
                print(f"Warning: Failed to process {file_path}: {e}")
                continue
        
        # Sort by timestamp
        cases.sort(key=lambda c: c.timestamp, reverse=True)
        return cases
    
    def delete_case(self, case_id: str) -> bool:
        """Delete a case from the archive
        
        Args:
            case_id: Case identifier
        
        Returns:
            True if deleted, False if not found
        """
        file_path = self.archive_dir / f"{case_id}.json"
        
        if not file_path.exists():
            return False
        
        try:
            file_path.unlink()
            return True
        except Exception as e:
            print(f"Warning: Failed to delete case {case_id}: {e}")
            return False
    
    def _case_to_dict(self, case: RAGCase) -> Dict[str, Any]:
        """Convert RAGCase to dictionary
        
        Args:
            case: RAGCase to convert
        
        Returns:
            Dictionary representation
        """
        return {
            "case_id": case.case_id,
            "timestamp": case.timestamp,
            "db_snapshot": case.db_snapshot,
            "analysis_steps": [
                {
                    "step": s.step,
                    "command": s.command,
                    "parameters": s.parameters,
                    "result_summary": s.result_summary,
                    "description": s.description,
                }
                for s in case.analysis_steps
            ],
            "conclusion": case.conclusion,
            "root_cause": case.root_cause,
            "solution": case.solution,
            "tags": case.tags,
            "confidence": case.confidence,
            "verified_by": case.verified_by,
            "metadata": case.metadata,
        }
    
    def _dict_to_case(self, case_dict: Dict[str, Any]) -> RAGCase:
        """Convert dictionary to RAGCase
        
        Args:
            case_dict: Dictionary representation
        
        Returns:
            RAGCase instance
        """
        analysis_steps = [
            AnalysisStep(
                step=s["step"],
                command=s["command"],
                parameters=s.get("parameters", {}),
                result_summary=s.get("result_summary", ""),
                description=s.get("description", ""),
            )
            for s in case_dict.get("analysis_steps", [])
        ]
        
        return RAGCase(
            case_id=case_dict.get("case_id", ""),
            timestamp=case_dict.get("timestamp", ""),
            db_snapshot=case_dict.get("db_snapshot", ""),
            analysis_steps=analysis_steps,
            conclusion=case_dict.get("conclusion", ""),
            root_cause=case_dict.get("root_cause", ""),
            solution=case_dict.get("solution", ""),
            tags=case_dict.get("tags", []),
            confidence=case_dict.get("confidence", 0.0),
            verified_by=case_dict.get("verified_by", "unverified"),
            metadata=case_dict.get("metadata", {}),
        )
```

- [ ] **Step 2: 创建测试文件**

```python
"""Tests for case archive"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
from pt_snap_analyzer.rag.archive import CaseArchive, ArchiveError
from pt_snap_analyzer.rag.models import RAGCase, AnalysisStep


def test_archive_add_case(tmp_path):
    """Test adding a case to archive"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case = RAGCase(
        conclusion="Memory leak found",
        root_cause="Cache not released",
        solution="Release cache",
        tags=["memory-leak"],
    )
    
    case_id = archive.add_case(case)
    
    assert case_id != ""
    assert (tmp_path / f"{case_id}.json").exists()


def test_archive_add_case_missing_conclusion(tmp_path):
    """Test error when conclusion missing"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case = RAGCase(
        root_cause="Test cause",
        solution="Test solution",
        tags=["test"],
    )
    
    with pytest.raises(ArchiveError) as exc_info:
        archive.add_case(case)
    
    assert "must have a conclusion" in str(exc_info.value)


def test_archive_get_case(tmp_path):
    """Test getting a case from archive"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case = RAGCase(
        conclusion="Test conclusion",
        root_cause="Test cause",
        solution="Test solution",
        tags=["test"],
    )
    case_id = archive.add_case(case)
    
    retrieved = archive.get_case(case_id)
    
    assert retrieved is not None
    assert retrieved.conclusion == "Test conclusion"


def test_archive_get_case_not_found(tmp_path):
    """Test getting non-existent case"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case = archive.get_case("nonexistent")
    
    assert case is None


def test_archive_list_cases(tmp_path):
    """Test listing all cases"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case1 = RAGCase(
        case_id="case-1",
        conclusion="Case 1",
        root_cause="Cause 1",
        solution="Solution 1",
        tags=["tag1"],
    )
    case2 = RAGCase(
        case_id="case-2",
        conclusion="Case 2",
        root_cause="Cause 2",
        solution="Solution 2",
        tags=["tag1", "tag2"],
    )
    
    archive.add_case(case1)
    archive.add_case(case2)
    
    cases = archive.list_cases()
    
    assert len(cases) == 2


def test_archive_list_cases_filtered(tmp_path):
    """Test listing cases with tag filter"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case1 = RAGCase(
        case_id="case-1",
        conclusion="Case 1",
        root_cause="Cause 1",
        solution="Solution 1",
        tags=["tag1"],
    )
    case2 = RAGCase(
        case_id="case-2",
        conclusion="Case 2",
        root_cause="Cause 2",
        solution="Solution 2",
        tags=["tag1", "tag2"],
    )
    
    archive.add_case(case1)
    archive.add_case(case2)
    
    cases = archive.list_cases(tags=["tag1", "tag2"])
    
    # Should only return case-2 (AND logic)
    assert len(cases) == 1
    assert cases[0].case_id == "case-2"


def test_archive_delete_case(tmp_path):
    """Test deleting a case"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    case = RAGCase(
        conclusion="Test",
        root_cause="Test",
        solution="Test",
    )
    case_id = archive.add_case(case)
    
    assert (tmp_path / f"{case_id}.json").exists()
    
    deleted = archive.delete_case(case_id)
    
    assert deleted
    assert not (tmp_path / f"{case_id}.json").exists()


def test_archive_delete_not_found(tmp_path):
    """Test deleting non-existent case"""
    archive = CaseArchive(archive_dir=str(tmp_path))
    
    deleted = archive.delete_case("nonexistent")
    
    assert not deleted
```

- [ ] **Step 3: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_rag_archive.py -v
```

Expected: 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add pt_snap_analyzer/rag/archive.py tests/test_rag_archive.py
git commit -m "feat: add case archive system"
```

---

### Task 3: 案例检索系统

**Files:**
- Create: `pt_snap_analyzer/rag/searcher.py`
- Create: `tests/test_rag_searcher.py`

- [ ] **Step 1: 创建检索器**

```python
"""Searcher for RAG knowledge base"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import List, Optional

from pt_snap_analyzer.rag.archive import CaseArchive
from pt_snap_analyzer.rag.models import RAGCase, SearchMatch, SearchResult


class Searcher:
    """Search RAG cases for similar problems
    
    Attributes:
        archive: Case archive to search
    """
    
    def __init__(self, archive: Optional[CaseArchive] = None):
        """Initialize searcher
        
        Args:
            archive: Case archive (uses default if None)
        """
        if archive is None:
            archive = CaseArchive()
        self.archive = archive
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        tags: Optional[List[str]] = None,
    ) -> SearchResult:
        """Search for similar cases
        
        Args:
            query: Search query
            top_k: Number of results to return
            tags: Optional tags to filter by
        
        Returns:
            SearchResult with matched cases
        """
        # Get all cases
        cases = self.archive.list_cases(tags=tags)
        
        # Score each case
        matches = []
        for case in cases:
            score, matched_terms = self._score_case(case, query)
            if score > 0:
                matches.append(SearchMatch(
                    case=case,
                    score=score,
                    query_match=matched_terms,
                ))
        
        # Sort by score
        matches.sort(key=lambda m: m.score, reverse=True)
        
        # Take top K
        matches = matches[:top_k]
        
        return SearchResult(
            matches=matches,
            total_results=len(matches),
            query=query,
        )
    
    def _score_case(self, case: RAGCase, query: str) -> tuple[float, List[str]]:
        """Score a case against query
        
        Args:
            case: RAGCase to score
            query: Search query
        
        Returns:
            Tuple of (score, matched_terms)
        """
        # Normalize query
        query_terms = self._normalize_text(query).split()
        
        # Build searchable text
        searchable = " ".join([
            case.conclusion,
            case.root_cause,
            case.solution,
            " ".join(case.tags),
        ])
        searchable = self._normalize_text(searchable)
        
        # Count matches
        matched_terms = []
        matches = 0
        
        for term in query_terms:
            if term in searchable:
                matches += 1
                matched_terms.append(term)
        
        # Calculate score
        if not query_terms:
            return 0.0, []
        
        # Score = (matches / query_terms) * weight
        base_score = matches / len(query_terms)
        
        # Boost score if case is verified
        if case.verified_by != "unverified":
            base_score *= 1.2
        
        # Boost score for high confidence
        if case.confidence > 0.8:
            base_score *= 1.1
        
        return min(base_score, 1.0), matched_terms
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison
        
        Args:
            text: Input text
        
        Returns:
            Normalized text
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove accents
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        
        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)
        
        # Collapse whitespace
        text = " ".join(text.split())
        
        return text
    
    def get_tags(self) -> List[str]:
        """Get all unique tags from archive
        
        Returns:
            List of unique tags
        """
        tags = set()
        
        cases = self.archive.list_cases()
        for case in cases:
            tags.update(case.tags)
        
        return sorted(list(tags))
```

- [ ] **Step 2: 创建测试文件**

```python
"""Tests for RAG searcher"""

import pytest
from pathlib import Path
from pt_snap_analyzer.rag.archive import CaseArchive
from pt_snap_analyzer.rag.searcher import Searcher
from pt_snap_analyzer.rag.models import RAGCase


def test_searcher_basic():
    """Test basic search functionality"""
    archive = CaseArchive()
    
    case = RAGCase(
        case_id="test-1",
        conclusion="Memory leak in transformer",
        root_cause="Attention cache not released",
        solution="Upgrade transformers library",
        tags=["memory-leak", "transformer", "attention"],
    )
    archive.add_case(case)
    
    searcher = Searcher(archive=archive)
    result = searcher.search("memory leak transformer")
    
    assert result.total_results >= 1
    assert any("memory" in m.query_match for m in result.matches)


def test_searcher_no_matches():
    """Test search with no matches"""
    archive = CaseArchive()
    
    case = RAGCase(
        case_id="test-1",
        conclusion="CUDA out of memory",
        root_cause="Batch size too large",
        solution="Reduce batch size",
        tags=["cuda", "oom"],
    )
    archive.add_case(case)
    
    searcher = Searcher(archive=archive)
    result = searcher.search("python memory leak")
    
    # Should have no matches
    assert result.total_results == 0


def test_searcher_tag_filter():
    """Test search with tag filter"""
    archive = CaseArchive()
    
    case1 = RAGCase(
        case_id="test-1",
        conclusion="Memory leak",
        root_cause="Cache not released",
        solution="Release cache",
        tags=["memory-leak", "cpu"],
    )
    case2 = RAGCase(
        case_id="test-2",
        conclusion="GPU OOM",
        root_cause="Too much memory",
        solution="Reduce batch",
        tags=["cuda", "oom"],
    )
    
    archive.add_case(case1)
    archive.add_case(case2)
    
    searcher = Searcher(archive=archive)
    result = searcher.search("memory", tags=["memory-leak"])
    
    assert result.total_results >= 1


def test_searcher_verified_boost():
    """Test score boost for verified cases"""
    archive = CaseArchive()
    
    case_unverified = RAGCase(
        case_id="test-1",
        conclusion="Memory leak",
        root_cause="Test",
        solution="Test",
        tags=["test"],
    )
    case_verified = RAGCase(
        case_id="test-2",
        conclusion="Memory leak",
        root_cause="Test",
        solution="Test",
        tags=["test"],
        verified_by="human",
    )
    
    archive.add_case(case_unverified)
    archive.add_case(case_verified)
    
    searcher = Searcher(archive=archive)
    result = searcher.search("memory test")
    
    if result.total_results >= 2:
        # Verified case should have higher score
        scores = [m.score for m in result.matches]
        assert max(scores) >= min(scores)


def test_get_tags():
    """Test getting all tags"""
    archive = CaseArchive()
    
    case1 = RAGCase(
        case_id="test-1",
        conclusion="Test 1",
        root_cause="Test",
        solution="Test",
        tags=["tag1", "tag2"],
    )
    case2 = RAGCase(
        case_id="test-2",
        conclusion="Test 2",
        root_cause="Test",
        solution="Test",
        tags=["tag2", "tag3"],
    )
    
    archive.add_case(case1)
    archive.add_case(case2)
    
    searcher = Searcher(archive=archive)
    tags = searcher.get_tags()
    
    assert "tag1" in tags
    assert "tag2" in tags
    assert "tag3" in tags
    assert len(tags) == 3
```

- [ ] **Step 3: Run test**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_rag_searcher.py -v
```

Expected: 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add pt_snap_analyzer/rag/searcher.py tests/test_rag_searcher.py
git commit -m "feat: add RAG searcher"
```

---

### Task 4: CLI 集成

**Files:**
- Modify: `pt_snap_analyzer/cli.py`
- Create: `tests/test_rag_cli.py`

- [ ] **Step 1: 添加 rag 命令到 CLI**

```python
# Add to cli.py after imports
from pt_snap_analyzer.rag.archive import CaseArchive, ArchiveError
from pt_snap_analyzer.rag.searcher import Searcher


@app.command()
def rag():
    """RAG knowledge base commands"""
    raise typer.Exit(code=1)


@app.command()
def rag_add(
    file: Annotated[str, typer.Argument(help="JSON file with case data")],
):
    """Add a case to the RAG knowledge base"""
    try:
        archive = CaseArchive()
        
        # Load case from JSON file
        from pathlib import Path
        case_file = Path(file)
        if not case_file.exists():
            print(f"Error: File not found: {file}", flush=True)
            raise typer.Exit(code=1)
        
        with open(case_file, "r") as f:
            import json
            case_dict = json.load(f)
        
        # Convert to RAGCase
        case = RAGCase(**case_dict)
        case_id = archive.add_case(case)
        
        print(f"Case added: {case_id}")
    
    except ArchiveError as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", flush=True)
        raise typer.Exit(code=1)


@app.command()
def rag_search(
    query: Annotated[str, typer.Argument(help="Search query")],
    top_k: Annotated[
        int, typer.Option("--top-k", help="Number of results")
    ] = 5,
    tags: Annotated[
        List[str], typer.Option("--tags", help="Filter by tags")
    ] = [],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
):
    """Search the RAG knowledge base"""
    try:
        searcher = Searcher()
        result = searcher.search(
            query=query,
            top_k=top_k,
            tags=tags if tags else None,
        )
        
        if json_output:
            import json
            output = {
                "query": result.query,
                "total_results": result.total_results,
                "matches": [
                    {
                        "case_id": m.case.case_id,
                        "score": m.score,
                        "query_match": m.query_match,
                        "conclusion": m.case.conclusion,
                        "solution": m.case.solution,
                    }
                    for m in result.matches
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Search results for: '{query}'")
            print(f"Found {result.total_results} matches")
            print("-" * 60)
            
            for i, match in enumerate(result.matches, 1):
                print(f"\n[{i}] {match.case.case_id}")
                print(f"    Score: {match.score:.3f}")
                print(f"    Conclusion: {match.case.conclusion}")
                if match.case.solution:
                    print(f"    Solution: {match.case.solution}")
    
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)


@app.command()
def rag_list(
    tags: Annotated[
        List[str], typer.Option("--tags", help="Filter by tags")
    ] = [],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
):
    """List all cases in the RAG knowledge base"""
    try:
        archive = CaseArchive()
        cases = archive.list_cases(tags=tags if tags else None)
        
        if json_output:
            import json
            output = [
                {
                    "case_id": c.case_id,
                    "timestamp": c.timestamp,
                    "conclusion": c.conclusion,
                    "solution": c.solution,
                    "tags": c.tags,
                }
                for c in cases
            ]
            print(json.dumps(output, indent=2))
        else:
            print(f"Total cases: {len(cases)}")
            print("-" * 60)
            
            for case in cases:
                print(f"\n{case.case_id}")
                print(f"  {case.timestamp}")
                print(f"  {case.conclusion}")
                if case.tags:
                    print(f"  Tags: {', '.join(case.tags)}")
    
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)


@app.command()
def rag_tags():
    """List all tags in the RAG knowledge base"""
    try:
        searcher = Searcher()
        tags = searcher.get_tags()
        
        print("Available Tags:")
        for tag in tags:
            print(f"  - {tag}")
    
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 2: 创建 CLI 测试**

```python
"""Tests for RAG CLI commands"""

from click.testing import CliRunner
from pt_snap_analyzer.cli import app


def test_rag_add_json_format():
    """Test rag-add with JSON file"""
    runner = CliRunner()
    # This will fail without a real file, but parameter parsing should work
    result = runner.invoke(app, ["rag-add", "/nonexistent/file.json"])
    assert result.exit_code != 0


def test_rag_search_query():
    """Test rag-search with query"""
    runner = CliRunner()
    result = runner.invoke(app, ["rag-search", "memory leak"])
    # Should succeed even if no cases
    assert result.exit_code == 0


def test_rag_search_with_tags():
    """Test rag-search with tags filter"""
    runner = CliRunner()
    result = runner.invoke(app, [
        "rag-search", "memory",
        "--tags", "memory-leak",
        "--json"
    ])
    assert result.exit_code == 0


def test_rag_list():
    """Test rag-list command"""
    runner = CliRunner()
    result = runner.invoke(app, ["rag-list"])
    assert result.exit_code == 0


def test_rag_tags():
    """Test rag-tags command"""
    runner = CliRunner()
    result = runner.invoke(app, ["rag-tags"])
    assert result.exit_code == 0
    assert "Available Tags:" in result.output
```

- [ ] **Step 3: 运行测试**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_rag_cli.py -v
```

Expected: 4 tests PASS

- [ ] **Step 4: 运行完整测试**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/ -v
```

Expected: 30+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add pt_snap_analyzer/cli.py tests/test_rag_cli.py
git commit -m "feat: integrate RAG into CLI"
```

---

### Task 5: 完整的 SDK 集成

**Files:**
- Modify: `pt_snap_analyzer/__init__.py`
- Modify: `pt_snap_analyzer/rag/__init__.py`

- [ ] **Step 1: 更新包初始化**

```python
"""pt-snap-analyzer - AI-friendly PyTorch Memory Snapshot Analyzer"""

__version__ = "0.1.0"
__author__ = "Liuyekang"

from pt_snap_analyzer.context import Context
from pt_snap_analyzer.models import MemoryEvent, MemoryBlock
from pt_snap_analyzer.rag import CaseArchive, Searcher, RAGCase, SearchResult

__all__ = [
    "Context", 
    "MemoryEvent", 
    "MemoryBlock",
    "CaseArchive", 
    "Searcher", 
    "RAGCase", 
    "SearchResult",
    "__version__",
]
```

- [ ] **Step 2: 创建 rag 包初始化**

```python
"""RAG knowledge base for pt-snap-analyzer"""

from pt_snap_analyzer.rag.models import RAGCase, SearchResult, SearchMatch
from pt_snap_analyzer.rag.archive import CaseArchive, ArchiveError
from pt_searcher import Searcher

__all__ = ["RAGCase", "SearchResult", "SearchMatch", "CaseArchive", "Searcher", "ArchiveError"]
```

- [ ] **Step 3: 创建 SDK 测试**

```python
"""Tests for RAG SDK integration"""

import pytest
from pt_snap_analyzer import CaseArchive, Searcher, RAGCase


def test_sdk_case_archive():
    """Test CaseArchive via SDK"""
    archive = CaseArchive()
    
    case = RAGCase(
        conclusion="SDK test",
        root_cause="Test cause",
        solution="Test solution",
        tags=["sdk-test"],
    )
    case_id = archive.add_case(case)
    
    retrieved = archive.get_case(case_id)
    assert retrieved is not None
    assert retrieved.conclusion == "SDK test"


def test_sdk_searcher():
    """Test Searcher via SDK"""
    archive = CaseArchive()
    
    case = RAGCase(
        case_id="sdk-test-1",
        conclusion="Memory leak in transformer",
        root_cause="Cache not released",
        solution="Upgrade transformers",
        tags=["memory-leak", "transformer"],
    )
    archive.add_case(case)
    
    searcher = Searcher(archive=archive)
    result = searcher.search("memory leak transformer")
    
    assert result.total_results >= 1


def test_sdk_rag_case():
    """Test RAGCase creation via SDK"""
    case = RAGCase(
        case_id="explicit-id",
        conclusion="Explicit test",
        root_cause="Test",
        solution="Test",
        tags=["test"],
        confidence=0.95,
        verified_by="human",
    )
    
    assert case.case_id == "explicit-id"
    assert case.confidence == 0.95
```

- [ ] **Step 4: 运行测试**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/test_sdk_rag.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: 运行完整测试**

```bash
. /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh && conda activate openclaw && pytest tests/ -v
```

Expected: 33+ tests PASS

- [ ] **Step 6: Commit**

```bash
git add pt_snap_analyzer/__init__.py pt_snap_analyzer/rag/__init__.py tests/test_sdk_rag.py
git commit -m "feat: add SDK integration for RAG"
```

---

### 最终验收清单

- [ ] 所有测试通过 (33+ tests)
- [ ] CaseArchive 可以添加和检索案例
- [ ] Searcher 可以搜索相似案例
- [ ] CLI 命令正常工作
- [ ] SDK API 可用
- [ ] 标签过滤正确工作
- [ ] pytest 覆盖率 > 80%

---

## 执行意见

Plan complete and saved to `docs/superpowers/plans/2026-04-04-pt-snap-analyzer-rag.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 我分发每个任务的独立 subagent，任务间审查，快速迭代

**2. Inline Execution** - 在此会话中执行任务，使用 executing-plans，批次执行加检查点

**Which approach?**
