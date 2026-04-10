# Tensil

**The markdown of spreadsheets.**

Tensil is a plain text tabular data format designed to be human-readable, git-diffable, and renderable into rich spreadsheet-like views.

```
---
sheet: fault_codes
key: code
columns:
  code: int
  severity: enum(WARNING, CAUTION, ALERT)
  threshold: int
  action: string
---
code,severity,threshold,action
1001,WARNING,100,LOG
1002,CAUTION,85,ALERT
1003,ALERT,50,SHUTDOWN
```

That's a `.tsl` file. The schema is YAML. The data is CSV. Git diff just works:

```diff
 code,severity,threshold,action
 1001,WARNING,100,LOG
-1002,CAUTION,85,ALERT
+1002,CAUTION,80,ALERT
 1003,ALERT,50,SHUTDOWN
+1004,WARNING,90,LOG
```

## Why

CSV has survived for 50 years because it got the hard part right — the data is just there, readable, diffable. What it's missing is small: column types, metadata, validation, formulas. Tensil adds a thin layer on top without losing what makes CSV work.

Excel files are binary blobs. You can't diff them, merge them, or review them in a PR. Every team that puts a spreadsheet in Git is working around this. Tensil is the fix.

## Status

Early. The format spec and a Python reference parser exist. Everything is subject to change.

## Install

```bash
pip install .
```

## Quick start

```python
import tensil

sheet = tensil.read("fault_codes.tsl")
print(sheet["threshold", 1002])  # 85

errors = tensil.validate("fault_codes.tsl")
```

## License

MIT
