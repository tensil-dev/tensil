"""
Tensil parser — reads and writes .tsl files.
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from tensil.schema import (
    Column,
    ColumnType,
    HighlightRule,
    Row,
    Sheet,
    Workbook,
)
from tensil.types import coerce


# ---------------------------------------------------------------------------
# Schema parsing helpers
# ---------------------------------------------------------------------------

_ENUM_RE = re.compile(r"^enum\((.+)\)$", re.IGNORECASE)


def _parse_column_type(name: str, raw_type: str) -> Column:
    """Parse a type string like 'int', 'enum(A, B, C)' into a Column."""
    raw_type = raw_type.strip()
    m = _ENUM_RE.match(raw_type)
    if m:
        values = [v.strip() for v in m.group(1).split(",")]
        return Column(name=name, type=ColumnType.ENUM, enum_values=values)

    try:
        ct = ColumnType(raw_type.lower())
    except ValueError:
        ct = ColumnType.STRING
    return Column(name=name, type=ct)


def _parse_schema(raw: str) -> dict:
    """Parse YAML schema text into a dict."""
    return yaml.safe_load(raw) or {}


def _build_columns(schema: dict) -> Dict[str, Column]:
    """Build Column objects from the 'columns' key of the schema."""
    columns: Dict[str, Column] = {}
    raw_cols = schema.get("columns")
    if not raw_cols or not isinstance(raw_cols, dict):
        return columns
    for col_name, col_type in raw_cols.items():
        columns[str(col_name)] = _parse_column_type(str(col_name), str(col_type))
    return columns


def _build_highlights(schema: dict) -> List[HighlightRule]:
    """Build HighlightRule objects from the 'highlight' key of the schema."""
    rules: List[HighlightRule] = []
    raw = schema.get("highlight")
    if not raw or not isinstance(raw, list):
        return rules
    for entry in raw:
        if isinstance(entry, dict) and "where" in entry and "color" in entry:
            rules.append(HighlightRule(where=str(entry["where"]), color=str(entry["color"])))
    return rules


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _split_schema_and_body(text: str):
    """
    Split a .tsl file into its schema YAML and CSV body.
    Returns (schema_text | None, body_text).
    """
    # Check for --- delimited schema block
    if not text.startswith("---"):
        return None, text

    # Find the closing ---
    end = text.find("\n---", 3)
    if end == -1:
        return None, text

    schema_text = text[3:end].strip()
    body_text = text[end + 4:].strip()
    return schema_text, body_text


def read(source: Union[str, Path, io.IOBase]) -> Sheet:
    """
    Read a .tsl file and return a Sheet.

    source can be:
      - a file path (str or Path)
      - a file-like object
      - a raw string containing .tsl content (if it contains newlines)
    """
    if isinstance(source, (str, Path)):
        # If it contains newlines, treat as raw content
        if isinstance(source, str) and "\n" in source:
            text = source
        else:
            path = Path(source)
            if path.exists():
                text = path.read_text(encoding="utf-8")
            else:
                raise FileNotFoundError(f"File not found: {source}")
    elif hasattr(source, "read"):
        text = source.read()
    else:
        text = str(source)

    return _parse_text(text)


def _parse_text(text: str) -> Sheet:
    """Parse raw .tsl text into a Sheet."""
    schema_text, body_text = _split_schema_and_body(text)

    sheet = Sheet()

    # Parse schema if present
    if schema_text:
        schema = _parse_schema(schema_text)
        sheet.name = schema.get("sheet")
        sheet.key = schema.get("key")
        if sheet.key:
            sheet.key = str(sheet.key)
        sheet.columns = _build_columns(schema)
        sheet.highlight = _build_highlights(schema)

    # Parse CSV body
    if not body_text:
        return sheet

    reader = csv.reader(io.StringIO(body_text))

    # First row is column headers
    try:
        headers = next(reader)
    except StopIteration:
        return sheet

    headers = [h.strip() for h in headers]
    sheet.column_names = headers

    # If no schema columns were defined, create untyped columns from headers
    if not sheet.columns:
        for h in headers:
            sheet.columns[h] = Column(name=h)

    # Parse data rows
    for raw_row in reader:
        if not any(raw_row):
            continue  # skip blank lines

        row = Row()
        for i, header in enumerate(headers):
            raw_val = raw_row[i].strip() if i < len(raw_row) else ""
            col = sheet.columns.get(header)
            row[header] = coerce(raw_val, col)
        sheet.rows.append(row)

    # Build key index
    if sheet.key:
        sheet._rebuild_key_index()

    return sheet


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write(sheet: Sheet, dest: Union[str, Path, io.IOBase]) -> Optional[str]:
    """
    Write a Sheet to a .tsl file.

    dest can be:
      - a file path (str or Path) — writes to file, returns None
      - a file-like object — writes to it, returns None
      - None — returns the .tsl content as a string
    """
    text = _render_text(sheet)

    if dest is None:
        return text

    if isinstance(dest, (str, Path)):
        Path(dest).write_text(text, encoding="utf-8")
        return None

    if hasattr(dest, "write"):
        dest.write(text)
        return None

    return text


def _render_text(sheet: Sheet) -> str:
    """Render a Sheet to .tsl text."""
    parts: List[str] = []

    # Schema block
    schema = _build_schema_dict(sheet)
    if schema:
        parts.append("---")
        parts.append(yaml.dump(schema, default_flow_style=False, sort_keys=False).strip())
        parts.append("---")

    # Column headers
    col_names = sheet.column_names or list(sheet.columns.keys())
    if not col_names:
        return "\n".join(parts) + "\n" if parts else ""

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(col_names)

    # Data rows
    for row in sheet.rows:
        csv_row = []
        for col in col_names:
            val = row.get(col)
            if val is None:
                csv_row.append("")
            elif isinstance(val, bool):
                csv_row.append("true" if val else "false")
            else:
                csv_row.append(str(val))
        writer.writerow(csv_row)

    parts.append(out.getvalue().strip())
    return "\n".join(parts) + "\n"


def _build_schema_dict(sheet: Sheet) -> dict:
    """Build a schema dict for YAML output."""
    schema: dict = {}

    if sheet.name:
        schema["sheet"] = sheet.name
    if sheet.key:
        schema["key"] = sheet.key

    # Only include columns if any have non-default types
    typed_cols = {}
    for name, col in sheet.columns.items():
        if col.type == ColumnType.ENUM and col.enum_values:
            typed_cols[name] = f"enum({', '.join(col.enum_values)})"
        elif col.type != ColumnType.STRING:
            typed_cols[name] = col.type.value
        else:
            typed_cols[name] = col.type.value

    if typed_cols:
        schema["columns"] = typed_cols

    if sheet.highlight:
        schema["highlight"] = [
            {"where": rule.where, "color": rule.color}
            for rule in sheet.highlight
        ]

    return schema


# ---------------------------------------------------------------------------
# Workbook read/write
# ---------------------------------------------------------------------------

def read_workbook(path: Union[str, Path]) -> Workbook:
    """
    Read a workbook directory containing .tsl files and a workbook.yaml manifest.
    """
    path = Path(path)
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    workbook = Workbook()

    manifest_path = path / "workbook.yaml"
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        workbook.name = manifest.get("name")
        sheet_files = manifest.get("sheets", [])
    else:
        # No manifest — just read all .tsl files alphabetically
        sheet_files = sorted(f.name for f in path.glob("*.tsl"))

    workbook.sheet_order = []
    for filename in sheet_files:
        filepath = path / filename
        if filepath.exists():
            sheet = read(filepath)
            # Use the sheet's declared name, or fall back to the filename stem
            sheet_name = sheet.name or filepath.stem
            sheet.name = sheet_name
            workbook.sheets[sheet_name] = sheet
            workbook.sheet_order.append(sheet_name)

    return workbook


def write_workbook(workbook: Workbook, path: Union[str, Path]) -> None:
    """
    Write a Workbook to a directory with .tsl files and a workbook.yaml manifest.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    sheet_files = []
    for sheet_name in (workbook.sheet_order or list(workbook.sheets.keys())):
        sheet = workbook.sheets[sheet_name]
        filename = f"{sheet_name}.tsl"
        write(sheet, path / filename)
        sheet_files.append(filename)

    manifest = {}
    if workbook.name:
        manifest["name"] = workbook.name
    manifest["sheets"] = sheet_files

    (path / "workbook.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
