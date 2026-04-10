"""
Tensil schema types — the data model for parsed .tsl files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Column type definitions
# ---------------------------------------------------------------------------

class ColumnType(PyEnum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"


@dataclass
class Column:
    """Describes a single column in a sheet."""
    name: str
    type: ColumnType = ColumnType.STRING
    enum_values: Optional[List[str]] = None

    def __repr__(self) -> str:
        if self.type == ColumnType.ENUM and self.enum_values:
            vals = ", ".join(self.enum_values)
            return f"Column({self.name!r}, enum({vals}))"
        return f"Column({self.name!r}, {self.type.value})"


# ---------------------------------------------------------------------------
# Highlight rules
# ---------------------------------------------------------------------------

@dataclass
class HighlightRule:
    """A conditional highlighting rule from the schema."""
    where: str
    color: str


# ---------------------------------------------------------------------------
# Row
# ---------------------------------------------------------------------------

class Row(dict):
    """
    A single data row. Acts as a dict mapping column names to values.
    Preserves insertion order.
    """
    pass


# ---------------------------------------------------------------------------
# Sheet
# ---------------------------------------------------------------------------

@dataclass
class Sheet:
    """A parsed .tsl sheet."""
    name: Optional[str] = None
    key: Optional[str] = None
    columns: Dict[str, Column] = field(default_factory=dict)
    column_names: List[str] = field(default_factory=list)
    highlight: List[HighlightRule] = field(default_factory=list)
    rows: List[Row] = field(default_factory=list)
    _key_index: Dict[Any, int] = field(default_factory=dict, repr=False)

    # ----- convenience accessors -----------------------------------------

    def __getitem__(self, ref: Union[str, Tuple[str, Any]]) -> Any:
        """
        sheet["column_name"]        -> list of all values in that column
        sheet["column_name", key]   -> single cell value by primary key
        """
        if isinstance(ref, tuple):
            col, key_val = ref
            return self._get_cell(col, key_val)
        return [row.get(ref) for row in self.rows]

    def _get_cell(self, column: str, key_val: Any) -> Any:
        if not self.key:
            raise KeyError("Sheet has no primary key defined; cannot look up by key.")
        if not self._key_index:
            self._rebuild_key_index()
        idx = self._key_index.get(key_val)
        if idx is None:
            raise KeyError(f"No row with {self.key}={key_val!r}")
        return self.rows[idx].get(column)

    def _rebuild_key_index(self) -> None:
        self._key_index = {}
        for i, row in enumerate(self.rows):
            kv = row.get(self.key)
            if kv is not None:
                self._key_index[kv] = i

    def get_row(self, key_val: Any) -> Optional[Row]:
        """Return the Row with the given primary key value, or None."""
        if not self._key_index:
            self._rebuild_key_index()
        idx = self._key_index.get(key_val)
        return self.rows[idx] if idx is not None else None


# ---------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------

@dataclass
class Workbook:
    """A collection of sheets loaded from a workbook directory."""
    name: Optional[str] = None
    sheets: Dict[str, Sheet] = field(default_factory=dict)
    sheet_order: List[str] = field(default_factory=list)

    def __getitem__(self, sheet_name: str) -> Sheet:
        return self.sheets[sheet_name]


# ---------------------------------------------------------------------------
# Validation error
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    """A single validation error."""
    row: Optional[int]  # 1-based row number in the data body, or None for schema-level errors
    column: Optional[str]
    message: str
    value: Any = None

    def __str__(self) -> str:
        parts = []
        if self.row is not None:
            parts.append(f"Row {self.row}")
        if self.column is not None:
            parts.append(f"column '{self.column}'")
        location = ", ".join(parts)
        if location:
            return f"{location}: {self.message}"
        return self.message
