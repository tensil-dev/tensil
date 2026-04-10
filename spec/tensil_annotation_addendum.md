# Tensil Format Specification — Addendum: Highlighting & Annotations

## Conditional Highlighting

Defined in the schema block under the `highlight` key. These are rules that apply to any row matching a condition. Renderers apply them visually; the data body is unaffected.

```yaml
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
  - where: threshold < 60
    color: orange
---
code,severity,threshold,action
1001,WARNING,100,LOG
1002,CAUTION,85,ALERT
1003,ALERT,50,SHUTDOWN
```

### Highlight Rule Fields

|Field|Required|Description|
|---|---|---|
|`where`|Yes|A condition using the same expression syntax as formulas.|
|`color`|Yes|A named color applied by the renderer.|

### Evaluation

- Conditions use column references, operators, and literals.
- Multiple rules can match the same row. Renderers apply them in order; later rules override earlier ones.
- Highlight rules are structural — they describe how the sheet should always look. They change when the sheet's logic changes.

### Named Colors

Initial set. Renderers map these to appropriate values for their context (light/dark themes, accessibility).

`red`, `orange`, `yellow`, `green`, `blue`, `purple`, `gray`

Custom hex values are not part of the initial spec. This keeps the schema readable and avoids bikeshedding over exact shades.

## Cell Annotations

Defined in a sidecar file named `<sheet>.tsl.annotations`. This file lives alongside the `.tsl` file and is entirely optional.

```
fault_system/
  workbook.yaml
  fault_codes.tsl
  fault_codes.tsl.annotations
  subsystems.tsl
```

### Format

YAML. A list of annotation entries.

```yaml
- cell: threshold[1002]
  color: red
  note: "Value seems too low — review with systems team"
  author: jsmith
  date: 2026-03-15

- cell: action[1003]
  color: green
  note: "Approved"
  author: mjones
  date: 2026-04-01

- row: 1001
  color: blue
  note: "Entire row under review pending sensor recalibration"
  author: jsmith
  date: 2026-04-05
```

### Annotation Fields

|Field|Required|Description|
|---|---|---|
|`cell`|Yes*|A cell reference: `column[key]`.|
|`row`|Yes*|A primary key value. Highlights the entire row.|
|`color`|No|A named color (same set as conditional highlighting).|
|`note`|No|Free text comment.|
|`author`|No|Who created the annotation.|
|`date`|No|ISO 8601 date.|

*Exactly one of `cell` or `row` must be present per entry.

### Design Rationale

- **The data file stays perfectly clean.** Annotations are metadata _about_ the data, not part of it.
- **Annotations diff independently from data.** A PR can show data changes in one file and review comments in another.
- **Annotations are disposable.** Deleting the sidecar file loses no data. The `.tsl` file is always the source of truth.
- **Permissions can differ.** In regulated environments, annotation changes may have different review requirements than data changes.

### Rendering Order

Renderers apply conditional highlighting rules from the schema first, then overlay cell annotations on top. Cell annotations take precedence where they conflict with conditional rules.