# Tensil Format Specification (Draft v0.0.1)

## File Extension

`.tsl`

## File Encoding

UTF-8, always. No BOM.

## File Structure

A `.tsl` file has two parts: an optional schema block and a data body.

```
---
<schema>
---
<data>
```

If the schema block is omitted, the file is treated as plain CSV with a header row.

## Schema Block

Delimited by `---` on its own line. Written in YAML.

```yaml
---
sheet: fault_codes
key: code
columns:
  code: int
  severity: enum(WARNING, CAUTION, ALERT)
  threshold: int
  action: string
  message: string
---
```

### Schema Fields

|Field|Required|Description|
|---|---|---|
|`sheet`|Yes|Name of this sheet. Used in cross-sheet references.|
|`key`|No|Column name to use as the primary key. Enables stable row references and better diffs. Values must be unique.|
|`columns`|No|Map of column names to types. If omitted, all columns are untyped.|

### Types

|Type|Description|
|---|---|
|`string`|Any text value|
|`int`|Integer|
|`float`|Decimal number|
|`bool`|`true` or `false`|
|`date`|ISO 8601 date (`2026-04-09`)|
|`datetime`|ISO 8601 datetime (`2026-04-09T14:30:00Z`)|
|`enum(A, B, C)`|One of the listed values|

## Data Body

Standard CSV following RFC 4180, with a mandatory header row. Column names in the header must match the schema if one is provided.

```
code,severity,threshold,action,message
1001,WARNING,100,LOG,Sensor drift detected
1002,CAUTION,85,ALERT,Pressure below nominal
1003,ALERT,50,SHUTDOWN,Critical failure imminent
```

Values containing commas, newlines, or double quotes must be enclosed in double quotes per RFC 4180.

## Formulas

A cell value beginning with `=` is a formula.

```
code,severity,threshold,action,adjusted_threshold
1001,WARNING,100,LOG,=threshold * 0.9
1002,CAUTION,85,ALERT,=threshold * 0.9
```

Formulas are stored as text in the file. Renderers evaluate them; the raw file shows the expression.

### References

**Column (same row):**

```
=threshold * 2
```

Refers to the `threshold` value in the current row.

**Cell (specific row by primary key):**

```
=threshold[1002]
```

Refers to the `threshold` value in the row where the primary key equals `1002`.

**Cross-sheet:**

```
=subsystems.name[SYS-04]
```

Refers to the `name` column in the `subsystems` sheet, in the row where that sheet's primary key equals `SYS-04`.

### Supported Operators

Arithmetic: `+`, `-`, `*`, `/` Comparison: `=`, `!=`, `>`, `<`, `>=`, `<=` Parentheses for grouping.

### Built-in Functions

Keep this minimal. Initial set:

|Function|Description|
|---|---|
|`SUM(column)`|Sum all values in a column|
|`COUNT(column)`|Count non-empty values in a column|
|`MIN(column)`|Minimum value in a column|
|`MAX(column)`|Maximum value in a column|
|`AVG(column)`|Average of a column|
|`IF(condition, then, else)`|Conditional|
|`ROUND(value, decimals)`|Round a number|

More can be added as the spec evolves, but the bar for inclusion should be high.

## Workbook Convention

A workbook is a directory containing one or more `.tsl` files and a `workbook.yaml` manifest.

```
fault_system/
  workbook.yaml
  fault_codes.tsl
  subsystems.tsl
  severity_actions.tsl
```

### workbook.yaml

```yaml
name: Fault System Definition
sheets:
  - fault_codes.tsl
  - subsystems.tsl
  - severity_actions.tsl
```

Sheet order in the manifest defines display order in renderers. All `.tsl` files in the directory should be listed. Cross-sheet references use the `sheet` name defined in each file's schema, not the filename.

## Minimal Valid File

The simplest valid `.tsl` file is just CSV with a header row:

```
name,age,city
Alice,30,St. Louis
Bob,25,Chicago
```

No schema required. This is intentional — the format should be as easy to start with as CSV.

## Diff Behavior

Files should be committed with rows sorted by primary key (if declared). This ensures that row insertions and deletions produce minimal, meaningful diffs rather than shifting every subsequent line.

A well-formed diff looks like:

```diff
 1001,WARNING,100,LOG,Sensor drift detected
-1002,CAUTION,85,ALERT,Pressure below nominal
+1002,CAUTION,80,ALERT,Pressure below nominal
 1003,ALERT,50,SHUTDOWN,Critical failure imminent
```

One line changed, immediately clear what happened: threshold for code 1002 went from 85 to 80.
