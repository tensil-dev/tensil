"""
Type coercion for cell values based on column type definitions.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from tensil.schema import Column, ColumnType


def coerce(value: str, column: Optional[Column]) -> Any:
    """
    Coerce a raw CSV string value to the appropriate Python type
    based on the column definition. Returns the raw string if no
    column definition is provided.
    """
    if value == "":
        return None

    if column is None:
        return value

    # Formulas are kept as-is (strings starting with '=')
    if value.startswith("="):
        return value

    try:
        return _COERCERS[column.type](value, column)
    except (ValueError, TypeError) as e:
        # Return raw string if coercion fails — validation catches the error
        return value


def _coerce_string(value: str, col: Column) -> str:
    return value


def _coerce_int(value: str, col: Column) -> int:
    return int(value)


def _coerce_float(value: str, col: Column) -> float:
    return float(value)


def _coerce_bool(value: str, col: Column) -> bool:
    lower = value.lower()
    if lower in ("true", "1", "yes"):
        return True
    if lower in ("false", "0", "no"):
        return False
    raise ValueError(f"Cannot coerce {value!r} to bool")


def _coerce_date(value: str, col: Column) -> date:
    return date.fromisoformat(value)


def _coerce_datetime(value: str, col: Column) -> datetime:
    # Handle trailing Z for UTC
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _coerce_enum(value: str, col: Column) -> str:
    # Return as-is; validation checks membership
    return value


_COERCERS = {
    ColumnType.STRING: _coerce_string,
    ColumnType.INT: _coerce_int,
    ColumnType.FLOAT: _coerce_float,
    ColumnType.BOOL: _coerce_bool,
    ColumnType.DATE: _coerce_date,
    ColumnType.DATETIME: _coerce_datetime,
    ColumnType.ENUM: _coerce_enum,
}
