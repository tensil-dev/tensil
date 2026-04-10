"""
Tensil formula evaluator — evaluates expressions in cells.

Supports:
  - Arithmetic: +, -, *, /
  - Comparisons: =, !=, >, <, >=, <=
  - Column references (same row): =threshold * 2
  - Cell references (by key): =threshold[1002]
  - Cross-sheet references: =subsystems.name[SYS-04]
  - Built-in functions: SUM, COUNT, MIN, MAX, AVG, IF, ROUND
  - Parentheses for grouping
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from tensil.schema import Sheet, Row, Workbook


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(sheet: Sheet, workbook: Optional[Workbook] = None) -> Sheet:
    """
    Evaluate all formulas in a sheet, returning a new Sheet with
    computed values replacing formula strings.

    If formulas contain cross-sheet references, pass the parent Workbook.
    """
    context = EvalContext(sheet=sheet, workbook=workbook)

    for i, row in enumerate(sheet.rows):
        for col_name in sheet.column_names:
            val = row.get(col_name)
            if isinstance(val, str) and val.startswith("="):
                expr = val[1:]  # strip leading =
                try:
                    row[col_name] = context.eval_expr(expr, row)
                except Exception:
                    # Leave the formula string if evaluation fails
                    pass

    # Rebuild key index since values may have changed
    if sheet.key:
        sheet._rebuild_key_index()

    return sheet


# ---------------------------------------------------------------------------
# Evaluation context
# ---------------------------------------------------------------------------

# Matches function calls like SUM(column), IF(cond, a, b)
_FUNC_RE = re.compile(r"([A-Z]+)\((.+)\)$")

# Matches cell references like threshold[1002] or subsystems.name[SYS-04]
_CELL_REF_RE = re.compile(r"((?:[\w]+\.)?[\w]+)\[([^\]]+)\]")

# Matches bare column names (word characters only, not starting with a digit)
_COL_REF_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")

# Comparison operators (must check multi-char before single-char)
_COMPARISONS = ["!=", ">=", "<=", "=", ">", "<"]


class EvalContext:
    """Holds the environment for evaluating formulas."""

    def __init__(self, sheet: Sheet, workbook: Optional[Workbook] = None):
        self.sheet = sheet
        self.workbook = workbook

    def eval_expr(self, expr: str, current_row: Row) -> Any:
        """Evaluate an expression string in the context of a row."""

        expr = expr.strip()

        # Handle built-in functions
        func_match = _FUNC_RE.match(expr)
        if func_match:
            func_name = func_match.group(1).upper()
            args_str = func_match.group(2)
            return self._eval_function(func_name, args_str, current_row)

        # Handle comparisons
        for op in _COMPARISONS:
            # Simple split — doesn't handle nested expressions with comparisons
            if op in expr:
                parts = expr.split(op, 1)
                if len(parts) == 2:
                    left = self.eval_expr(parts[0], current_row)
                    right = self.eval_expr(parts[1], current_row)
                    return _compare(left, right, op)

        # Resolve all references and evaluate as arithmetic
        resolved = self._resolve_references(expr, current_row)
        try:
            # Safe evaluation of arithmetic expressions
            return _safe_eval(resolved)
        except Exception:
            return resolved

    def _resolve_references(self, expr: str, current_row: Row) -> str:
        """Replace cell and column references with their values."""

        # First resolve cell references like threshold[1002] or sheet.col[key]
        def replace_cell_ref(m):
            ref_path = m.group(1)
            key_val = m.group(2)
            val = self._resolve_cell_ref(ref_path, key_val)
            return _val_to_str(val)

        expr = _CELL_REF_RE.sub(replace_cell_ref, expr)

        # Then resolve bare column references (same row)
        def replace_col_ref(m):
            name = m.group(1)
            # Don't replace if it's a number or a known function name
            if name.upper() in _BUILTIN_FUNCS or name.replace(".", "").isdigit():
                return name
            if name in current_row:
                return _val_to_str(current_row[name])
            return name

        expr = _COL_REF_RE.sub(replace_col_ref, expr)

        return expr

    def _resolve_cell_ref(self, ref_path: str, key_str: str) -> Any:
        """Resolve a cell reference like 'threshold[1002]' or 'subsystems.name[SYS-04]'."""

        # Cross-sheet reference
        if "." in ref_path:
            sheet_name, col_name = ref_path.split(".", 1)
            if self.workbook and sheet_name in self.workbook.sheets:
                target_sheet = self.workbook.sheets[sheet_name]
                return target_sheet[col_name, _try_numeric(key_str)]
            raise ValueError(f"Sheet '{sheet_name}' not found in workbook")

        # Same-sheet reference
        return self.sheet[ref_path, _try_numeric(key_str)]

    def _eval_function(self, name: str, args_str: str, current_row: Row) -> Any:
        """Evaluate a built-in function."""

        if name == "IF":
            # Split on commas carefully (doesn't handle nested commas)
            args = _split_args(args_str)
            if len(args) != 3:
                raise ValueError("IF requires exactly 3 arguments: IF(condition, then, else)")
            cond = self.eval_expr(args[0], current_row)
            if cond:
                return self.eval_expr(args[1], current_row)
            else:
                return self.eval_expr(args[2], current_row)

        if name == "ROUND":
            args = _split_args(args_str)
            val = self.eval_expr(args[0], current_row)
            decimals = int(self.eval_expr(args[1], current_row)) if len(args) > 1 else 0
            return round(float(val), decimals)

        # Aggregate functions operate on a whole column
        col_name = args_str.strip()
        values = [
            v for v in self.sheet[col_name]
            if v is not None and not (isinstance(v, str) and v.startswith("="))
        ]
        numeric = [float(v) for v in values if _is_numeric(v)]

        if name == "SUM":
            return sum(numeric)
        if name == "COUNT":
            return len(values)
        if name == "MIN":
            return min(numeric) if numeric else None
        if name == "MAX":
            return max(numeric) if numeric else None
        if name == "AVG":
            return sum(numeric) / len(numeric) if numeric else None

        raise ValueError(f"Unknown function: {name}")


_BUILTIN_FUNCS = {"SUM", "COUNT", "MIN", "MAX", "AVG", "IF", "ROUND"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val_to_str(val: Any) -> str:
    """Convert a value to a string suitable for embedding in an expression."""
    if val is None:
        return "0"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    # Try to return as a number if it looks like one
    try:
        float(val)
        return str(val)
    except (ValueError, TypeError):
        return f"'{val}'"


def _try_numeric(s: str):
    """Try to convert a string to int or float, return as-is if not numeric."""
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def _is_numeric(v) -> bool:
    """Check if a value can be treated as a number."""
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def _safe_eval(expr: str) -> Any:
    """
    Safely evaluate an arithmetic expression.
    Only allows numbers, +, -, *, /, parentheses, and whitespace.
    """
    cleaned = expr.strip()
    if not cleaned:
        return 0

    # Verify expression only contains safe characters
    if not re.match(r"^[\d\s\+\-\*/\.\(\)]+$", cleaned):
        return cleaned

    try:
        return eval(cleaned, {"__builtins__": {}}, {})  # noqa: S307
    except Exception:
        return cleaned


def _compare(left: Any, right: Any, op: str) -> bool:
    """Perform a comparison."""
    # Coerce to float for numeric comparisons
    try:
        left = float(left)
        right = float(right)
    except (ValueError, TypeError):
        left = str(left) if left is not None else ""
        right = str(right) if right is not None else ""

    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    return False


def _split_args(args_str: str) -> List[str]:
    """Split function arguments on commas, respecting parentheses depth."""
    args: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in args_str:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current).strip())
    return args
