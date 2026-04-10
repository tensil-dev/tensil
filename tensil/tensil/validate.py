"""
Tensil validation — checks .tsl data against its schema.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import List, Union

from tensil.schema import (
    Column,
    ColumnType,
    Sheet,
    ValidationError,
    Workbook,
)
from tensil.parser import read, read_workbook


def validate(source: Union[str, Path, Sheet]) -> List[ValidationError]:
    """
    Validate a .tsl file or Sheet against its schema.
    Returns a list of ValidationError objects. Empty list means valid.
    """
    if isinstance(source, Sheet):
        sheet = source
    else:
        sheet = read(source)

    errors: List[ValidationError] = []

    # Schema-level checks
    errors.extend(_validate_schema(sheet))

    # Row-level checks
    for i, row in enumerate(sheet.rows, start=1):
        errors.extend(_validate_row(sheet, row, i))

    # Primary key uniqueness
    errors.extend(_validate_key_uniqueness(sheet))

    return errors


def validate_workbook(source: Union[str, Path, Workbook]) -> List[ValidationError]:
    """Validate all sheets in a workbook."""
    if isinstance(source, Workbook):
        workbook = source
    else:
        workbook = read_workbook(source)

    errors: List[ValidationError] = []
    for sheet_name, sheet in workbook.sheets.items():
        sheet_errors = validate(sheet)
        for e in sheet_errors:
            e.message = f"[{sheet_name}] {e.message}"
        errors.extend(sheet_errors)

    return errors


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------

def _validate_schema(sheet: Sheet) -> List[ValidationError]:
    """Validate schema-level consistency."""
    errors: List[ValidationError] = []

    # Key column must exist in columns
    if sheet.key and sheet.key not in sheet.columns:
        errors.append(ValidationError(
            row=None,
            column=sheet.key,
            message=f"Primary key column '{sheet.key}' is not defined in columns.",
        ))

    # Column names in data header should match schema
    if sheet.column_names and sheet.columns:
        schema_names = set(sheet.columns.keys())
        header_names = set(sheet.column_names)
        for name in header_names - schema_names:
            errors.append(ValidationError(
                row=None,
                column=name,
                message=f"Column '{name}' appears in data header but is not defined in schema.",
            ))
        for name in schema_names - header_names:
            errors.append(ValidationError(
                row=None,
                column=name,
                message=f"Column '{name}' is defined in schema but missing from data header.",
            ))

    return errors


def _validate_row(sheet: Sheet, row: dict, row_num: int) -> List[ValidationError]:
    """Validate a single data row against column type definitions."""
    errors: List[ValidationError] = []

    for col_name, col in sheet.columns.items():
        value = row.get(col_name)

        # Skip None (empty cells) and formulas
        if value is None:
            continue
        if isinstance(value, str) and value.startswith("="):
            continue

        error = _validate_cell(col, value, row_num)
        if error:
            errors.append(error)

    return errors


def _validate_cell(col: Column, value, row_num: int) -> ValidationError | None:
    """Validate a single cell value against its column type."""

    if col.type == ColumnType.INT:
        if not isinstance(value, int):
            return ValidationError(
                row=row_num,
                column=col.name,
                message=f"Expected int, got {value!r}.",
                value=value,
            )

    elif col.type == ColumnType.FLOAT:
        if not isinstance(value, (int, float)):
            return ValidationError(
                row=row_num,
                column=col.name,
                message=f"Expected float, got {value!r}.",
                value=value,
            )

    elif col.type == ColumnType.BOOL:
        if not isinstance(value, bool):
            return ValidationError(
                row=row_num,
                column=col.name,
                message=f"Expected bool, got {value!r}.",
                value=value,
            )

    elif col.type == ColumnType.DATE:
        if not isinstance(value, date) or isinstance(value, datetime):
            return ValidationError(
                row=row_num,
                column=col.name,
                message=f"Expected date (YYYY-MM-DD), got {value!r}.",
                value=value,
            )

    elif col.type == ColumnType.DATETIME:
        if not isinstance(value, datetime):
            return ValidationError(
                row=row_num,
                column=col.name,
                message=f"Expected datetime (ISO 8601), got {value!r}.",
                value=value,
            )

    elif col.type == ColumnType.ENUM:
        if col.enum_values and value not in col.enum_values:
            allowed = ", ".join(col.enum_values)
            return ValidationError(
                row=row_num,
                column=col.name,
                message=f"'{value}' is not a valid value. Expected one of: {allowed}.",
                value=value,
            )

    return None


def _validate_key_uniqueness(sheet: Sheet) -> List[ValidationError]:
    """Check that primary key values are unique."""
    errors: List[ValidationError] = []
    if not sheet.key:
        return errors

    seen: dict = {}
    for i, row in enumerate(sheet.rows, start=1):
        kv = row.get(sheet.key)
        if kv is None:
            errors.append(ValidationError(
                row=i,
                column=sheet.key,
                message=f"Primary key column '{sheet.key}' is empty.",
            ))
            continue
        if kv in seen:
            errors.append(ValidationError(
                row=i,
                column=sheet.key,
                message=f"Duplicate primary key value {kv!r} (first seen at row {seen[kv]}).",
                value=kv,
            ))
        else:
            seen[kv] = i

    return errors
