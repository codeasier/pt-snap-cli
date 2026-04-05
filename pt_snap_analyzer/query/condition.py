"""Query condition classes for building SQL WHERE clauses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Condition(ABC):
    """Base class for query conditions."""

    @abstractmethod
    def to_sql(self) -> tuple[str, list[Any]]:
        """Convert condition to SQL string and parameters.

        Returns:
            Tuple of (SQL string, list of parameters).
        """
        pass

    @abstractmethod
    def __and__(self, other: Condition) -> Condition:
        """Combine conditions with AND."""
        pass

    @abstractmethod
    def __or__(self, other: Condition) -> Condition:
        """Combine conditions with OR."""
        pass


class Equal(Condition):
    """Equality condition: column = value."""

    def __init__(self, column: str, value: Any):
        self.column = column
        self.value = value

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} = ?", [self.value]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class NotEqual(Condition):
    """Inequality condition: column != value."""

    def __init__(self, column: str, value: Any):
        self.column = column
        self.value = value

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} != ?", [self.value]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class GreaterThan(Condition):
    """Greater than condition: column > value."""

    def __init__(self, column: str, value: Any):
        self.column = column
        self.value = value

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} > ?", [self.value]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class GreaterThanOrEqual(Condition):
    """Greater than or equal condition: column >= value."""

    def __init__(self, column: str, value: Any):
        self.column = column
        self.value = value

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} >= ?", [self.value]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class LessThan(Condition):
    """Less than condition: column < value."""

    def __init__(self, column: str, value: Any):
        self.column = column
        self.value = value

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} < ?", [self.value]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class LessThanOrEqual(Condition):
    """Less than or equal condition: column <= value."""

    def __init__(self, column: str, value: Any):
        self.column = column
        self.value = value

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} <= ?", [self.value]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class In(Condition):
    """IN condition: column IN (values)."""

    def __init__(self, column: str, values: list[Any]):
        self.column = column
        self.values = values

    def to_sql(self) -> tuple[str, list[Any]]:
        placeholders = ", ".join("?" * len(self.values))
        return f"{self.column} IN ({placeholders})", list(self.values)

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class Like(Condition):
    """LIKE condition: column LIKE pattern."""

    def __init__(self, column: str, pattern: str):
        self.column = column
        self.pattern = pattern

    def to_sql(self) -> tuple[str, list[Any]]:
        return f"{self.column} LIKE ?", [self.pattern]

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class And(Condition):
    """Composite AND condition: cond1 AND cond2 AND ..."""

    def __init__(self, conditions: list[Condition]):
        self.conditions = conditions

    def to_sql(self) -> tuple[str, list[Any]]:
        if not self.conditions:
            return "1=1", []
        parts = []
        params = []
        for cond in self.conditions:
            sql, p = cond.to_sql()
            parts.append(sql)
            params.extend(p)
        return " AND ".join(f"({part})" for part in parts), params

    def __and__(self, other: Condition) -> Condition:
        if isinstance(other, And):
            return And(self.conditions + other.conditions)
        return And(self.conditions + [other])

    def __or__(self, other: Condition) -> Condition:
        return Or([self, other])


class Or(Condition):
    """Composite OR condition: cond1 OR cond2 OR ..."""

    def __init__(self, conditions: list[Condition]):
        self.conditions = conditions

    def to_sql(self) -> tuple[str, list[Any]]:
        if not self.conditions:
            return "1=1", []
        parts = []
        params = []
        for cond in self.conditions:
            sql, p = cond.to_sql()
            parts.append(sql)
            params.extend(p)
        return " OR ".join(f"({part})" for part in parts), params

    def __and__(self, other: Condition) -> Condition:
        return And([self, other])

    def __or__(self, other: Condition) -> Condition:
        if isinstance(other, Or):
            return Or(self.conditions + other.conditions)
        return Or(self.conditions + [other])
