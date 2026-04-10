"""
Tests for the Tensil parser library.
"""

import os
import tempfile
from pathlib import Path

import tensil
from tensil.schema import ColumnType, ValidationError
from tensil.annotations import Annotation


# ---------------------------------------------------------------------------
# Sample .tsl content
# ---------------------------------------------------------------------------

FAULT_CODES_TSL = """\
---
sheet: fault_codes
key: code
columns:
  code: int
  severity: enum(WARNING, CAUTION, ALERT)
  threshold: int
  action: string
highlight:
  - where: severity = ALERT
    color: red
  - where: severity = CAUTION
    color: yellow
---
code,severity,threshold,action
1001,WARNING,100,LOG
1002,CAUTION,85,ALERT
1003,ALERT,50,SHUTDOWN
"""

BARE_CSV_TSL = """\
name,age,city
Alice,30,St. Louis
Bob,25,Chicago
"""

FORMULA_TSL = """\
---
sheet: pricing
key: item
columns:
  item: string
  price: float
  tax_rate: float
  total: string
---
item,price,tax_rate,total
Widget,10.00,0.08,=price * (1 + tax_rate)
Gadget,25.00,0.10,=price * (1 + tax_rate)
"""


# ---------------------------------------------------------------------------
# Test: read a full .tsl file
# ---------------------------------------------------------------------------

def test_read_full():
    sheet = tensil.read(FAULT_CODES_TSL)

    assert sheet.name == "fault_codes"
    assert sheet.key == "code"
    assert len(sheet.columns) == 4
    assert sheet.columns["severity"].type == ColumnType.ENUM
    assert sheet.columns["severity"].enum_values == ["WARNING", "CAUTION", "ALERT"]
    assert sheet.columns["code"].type == ColumnType.INT
    assert len(sheet.rows) == 3
    assert sheet.rows[0]["code"] == 1001
    assert sheet.rows[1]["severity"] == "CAUTION"
    assert sheet.rows[2]["action"] == "SHUTDOWN"
    print("PASS: test_read_full")


# ---------------------------------------------------------------------------
# Test: read bare CSV (no schema)
# ---------------------------------------------------------------------------

def test_read_bare_csv():
    sheet = tensil.read(BARE_CSV_TSL)

    assert sheet.name is None
    assert sheet.key is None
    assert len(sheet.rows) == 2
    assert sheet.rows[0]["name"] == "Alice"
    assert sheet.rows[1]["city"] == "Chicago"
    # All columns should be untyped (default STRING)
    assert sheet.columns["age"].type == ColumnType.STRING
    print("PASS: test_read_bare_csv")


# ---------------------------------------------------------------------------
# Test: cell access by primary key
# ---------------------------------------------------------------------------

def test_cell_access():
    sheet = tensil.read(FAULT_CODES_TSL)

    assert sheet["threshold", 1002] == 85
    assert sheet["action", 1003] == "SHUTDOWN"
    assert sheet["severity", 1001] == "WARNING"
    print("PASS: test_cell_access")


# ---------------------------------------------------------------------------
# Test: column access
# ---------------------------------------------------------------------------

def test_column_access():
    sheet = tensil.read(FAULT_CODES_TSL)

    codes = sheet["code"]
    assert codes == [1001, 1002, 1003]
    print("PASS: test_column_access")


# ---------------------------------------------------------------------------
# Test: highlight rules
# ---------------------------------------------------------------------------

def test_highlight_rules():
    sheet = tensil.read(FAULT_CODES_TSL)

    assert len(sheet.highlight) == 2
    assert sheet.highlight[0].where == "severity = ALERT"
    assert sheet.highlight[0].color == "red"
    assert sheet.highlight[1].where == "severity = CAUTION"
    assert sheet.highlight[1].color == "yellow"
    print("PASS: test_highlight_rules")


# ---------------------------------------------------------------------------
# Test: write and round-trip
# ---------------------------------------------------------------------------

def test_write_roundtrip():
    sheet = tensil.read(FAULT_CODES_TSL)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".tsl", delete=False) as f:
        tmp_path = f.name

    try:
        tensil.write(sheet, tmp_path)
        sheet2 = tensil.read(tmp_path)

        assert sheet2.name == sheet.name
        assert sheet2.key == sheet.key
        assert len(sheet2.rows) == len(sheet.rows)
        assert sheet2.rows[0]["code"] == 1001
        assert sheet2["threshold", 1002] == 85
        print("PASS: test_write_roundtrip")
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Test: validation — valid file
# ---------------------------------------------------------------------------

def test_validate_valid():
    errors = tensil.validate(FAULT_CODES_TSL)
    assert errors == [], f"Expected no errors, got: {errors}"
    print("PASS: test_validate_valid")


# ---------------------------------------------------------------------------
# Test: validation — type error
# ---------------------------------------------------------------------------

def test_validate_type_error():
    bad_tsl = """\
---
sheet: test
columns:
  id: int
  value: int
---
id,value
1,100
2,not_a_number
"""
    errors = tensil.validate(bad_tsl)
    assert len(errors) > 0
    assert any("int" in str(e).lower() or "not_a_number" in str(e) for e in errors)
    print("PASS: test_validate_type_error")


# ---------------------------------------------------------------------------
# Test: validation — enum violation
# ---------------------------------------------------------------------------

def test_validate_enum_error():
    bad_tsl = """\
---
sheet: test
columns:
  status: enum(OPEN, CLOSED)
---
status
OPEN
INVALID
CLOSED
"""
    errors = tensil.validate(bad_tsl)
    assert len(errors) == 1
    assert "INVALID" in str(errors[0])
    print("PASS: test_validate_enum_error")


# ---------------------------------------------------------------------------
# Test: validation — duplicate primary key
# ---------------------------------------------------------------------------

def test_validate_duplicate_key():
    bad_tsl = """\
---
sheet: test
key: id
columns:
  id: int
  name: string
---
id,name
1,Alice
2,Bob
1,Charlie
"""
    errors = tensil.validate(bad_tsl)
    assert any("Duplicate" in str(e) or "duplicate" in str(e) for e in errors)
    print("PASS: test_validate_duplicate_key")


# ---------------------------------------------------------------------------
# Test: formula evaluation
# ---------------------------------------------------------------------------

def test_evaluate_formulas():
    sheet = tensil.read(FORMULA_TSL)
    tensil.evaluate(sheet)

    # Widget: 10.00 * (1 + 0.08) = 10.80
    assert abs(sheet.rows[0]["total"] - 10.80) < 0.001
    # Gadget: 25.00 * (1 + 0.10) = 27.50
    assert abs(sheet.rows[1]["total"] - 27.50) < 0.001
    print("PASS: test_evaluate_formulas")


# ---------------------------------------------------------------------------
# Test: workbook read/write
# ---------------------------------------------------------------------------

def test_workbook_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a workbook manually
        wb = tensil.Workbook(name="Test Workbook")

        s1 = tensil.read(FAULT_CODES_TSL)
        s2 = tensil.read(BARE_CSV_TSL)
        s2.name = "people"

        wb.sheets["fault_codes"] = s1
        wb.sheets["people"] = s2
        wb.sheet_order = ["fault_codes", "people"]

        # Write it
        tensil.write_workbook(wb, tmpdir)

        # Read it back
        wb2 = tensil.read_workbook(tmpdir)

        assert wb2.name == "Test Workbook"
        assert len(wb2.sheets) == 2
        assert "fault_codes" in wb2.sheets
        assert "people" in wb2.sheets
        assert wb2["fault_codes"].rows[0]["code"] == 1001
        assert wb2["people"].rows[0]["name"] == "Alice"
        print("PASS: test_workbook_roundtrip")


# ---------------------------------------------------------------------------
# Test: annotations read/write
# ---------------------------------------------------------------------------

def test_annotations_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsl_path = Path(tmpdir) / "test.tsl"

        annotations = [
            Annotation(cell="threshold[1002]", color="red", note="Too low", author="jsmith", date="2026-03-15"),
            Annotation(row="1001", color="blue", note="Under review"),
        ]

        tensil.write_annotations(annotations, tsl_path)

        loaded = tensil.read_annotations(tsl_path)
        assert len(loaded) == 2
        assert loaded[0].cell == "threshold[1002]"
        assert loaded[0].color == "red"
        assert loaded[0].note == "Too low"
        assert loaded[0].author == "jsmith"
        assert loaded[1].row == "1001"
        assert loaded[1].color == "blue"
        print("PASS: test_annotations_roundtrip")


# ---------------------------------------------------------------------------
# Test: get_row helper
# ---------------------------------------------------------------------------

def test_get_row():
    sheet = tensil.read(FAULT_CODES_TSL)

    row = sheet.get_row(1002)
    assert row is not None
    assert row["severity"] == "CAUTION"
    assert row["threshold"] == 85

    assert sheet.get_row(9999) is None
    print("PASS: test_get_row")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_read_full()
    test_read_bare_csv()
    test_cell_access()
    test_column_access()
    test_highlight_rules()
    test_write_roundtrip()
    test_validate_valid()
    test_validate_type_error()
    test_validate_enum_error()
    test_validate_duplicate_key()
    test_evaluate_formulas()
    test_workbook_roundtrip()
    test_annotations_roundtrip()
    test_get_row()
    print("\n--- ALL TESTS PASSED ---")
