# Tensil

**The markdown of spreadsheets.** A plain text tabular data format designed to be human-readable, git-diffable, and renderable into rich spreadsheet-like views.

**Domain:** tensil.dev **File extension:** `.tsl`

---

## The Problem

Safety-critical industries (aerospace, automotive, medical devices, defense) rely heavily on spreadsheets as engineering artifacts — fault code tables, FMEA matrices, parameter tables, requirements traceability. These are not throwaway analysis; they are formal, auditable documents embedded in certification workflows.

Excel files are binary blobs. Git can't diff them, can't merge them, can't blame them. No tool exists that solves this properly. Everything available is either a workaround (extract to CSV, regenerate Excel), a partial solution (xltrail only diffs VBA, not cell data), or a paradigm shift (Dolt requires migrating to a database).

Microsoft could solve this trivially — they own the format, GitHub, VS Code, and Azure DevOps — but they have no incentive because these industries are already locked in and coping.

## The Insight

What engineers actually need is not Excel. It's a **tabular data editor with native version control**. They don't need pivot tables, macros, or chart wizards. They need structured rows and columns of data that are diffable, mergeable, and auditable.

CSV is 90% of the answer. It's survived 50 years because the data is just there — readable and diffable. What it's missing is small: column types, metadata, formulas, validation rules. That's a thin layer on top, not a reinvention.

## The Format

The key design principle: **readable raw, renderable rich.** Just like markdown.

A `.tsl` file looks like this:

```
---
sheet: fault_codes
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

- YAML header for metadata (column types, enums, constraints, sheet name)
- CSV body for data
- The header rarely changes, so it stays out of your diffs
- The body is plain CSV — git diff shows exactly what changed

### Multi-sheet / Workbook Convention

- One `.tsl` file per sheet
- A directory acts as the workbook
- A `workbook.yaml` manifest links sheets together

### Design Priorities

- **Human readability of the raw file is the highest priority** — this is what makes it diffable
- Declare a primary key column so diffs match rows by identity, not position
- Keep rows sorted by primary key so insertions don't look like every row changed
- Minimal, meaningful diffs for real-world changes

## The Layered Architecture

The format is layered to preserve simplicity at the base while allowing rigor when needed:

1. **Base layer:** CSV with a sheet name header. No schema, no types. Anyone can write it by hand. Always valid. This is the "markdown" layer.
2. **Schema layer (optional):** Column types, enums, constraints, required fields. Add this and you get validation. Leave it off and the file still works.
3. **Formula layer (optional):** Expressions that compute values from other values. No control flow, no user-defined functions. The renderer evaluates them; the file stores them as text.

Each layer adds power and complexity, but the base remains dead simple. A file with no header at all is just CSV and still valid.

## It's Not...

- **Excel** — no pivot tables, macros, VBA, chart wizards, rich formatting, or 500 formula functions
- **SQL** — no server, no runtime, no query language. The file _is_ the data. You open it in a text editor and read it.
- **SQLite** — that solved "no server" but it's still a binary file, not diffable
- **A programming language** — no control flow, no loops, no user-defined functions
- **Markdown** — markdown is simpler because it has no schema or types

It's a **data definition language with an expression layer**. Closest analogies: CSV + JSON Schema + a lightweight formula syntax. Or: what you'd get if CSV and SQL had a baby, raised by Git.

## Why It Needs a Language Server

Because it has a schema layer with types and constraints, users need real-time feedback when authoring:

- Type mismatches (column is `int`, you entered "foo")
- Enum violations (severity must be WARNING/CAUTION/ALERT, you typed WARN)
- Required field violations
- Formula errors (referencing a column that doesn't exist)
- Cross-file consistency (fault code references a subsystem ID from another sheet)

Build the language server using LSP so it works in VS Code, Neovim, Emacs, and any LSP-compatible editor for free. The VS Code extension becomes thin — just a table renderer plus an LSP client.

The language server lights up progressively: no schema means no validation, add a schema and you get type checking, add formulas and you get expression evaluation.

## Build Order

### Phase 1 (~3-4 months, 1-2 people)

- Formal spec document
- Reference parser library (Python first)
- Language server (LSP)
- VS Code extension with table rendering + LSP validation
- **Goal:** Usable end-to-end in a real Git workflow. Get it in front of 50 aerospace/automotive engineers and iterate.

### Phase 2

- GitHub/GitLab renderer so table diffs look good in PRs
- Build community, open-source everything

### Phase 3

- Commercial desktop editor (the paid product)
- Visual diff display (consumes Git's diff output, renders as highlighted table)
- Excel import/export wizard
- Formula evaluation
- Spreadsheet-like grid editing experience

### Phase 4

- Enterprise platform (only when paying editor customers ask for it)
- Review/approval workflows
- Electronic signatures and audit trails (FDA 21 CFR Part 11, DO-178C compliance)
- Role-based access
- PLM/DOORS/Jira integration connectors

## Business Model

**Open core.** The format wins by being everywhere. The product wins by serving people who need more.

### Free (drives adoption)

- Format spec
- Reference parser libraries
- Language server
- VS Code extension
- CLI tools
- GitHub/GitLab renderers

### Paid: Commercial Editor

- Desktop app, cross-platform
- Spreadsheet-like editing experience for non-developers
- Visual three-way diff with cell-level highlighting
- Merge conflict resolution UI
- Excel import/export
- Target buyers: aerospace, pharma, automotive, defense, finance — anyone with "critical spreadsheets"

### Paid: Enterprise Features

- Electronic signatures and audit trails for regulatory compliance
- Approval workflows
- Role-based access control
- Integration connectors to PLM systems (Windchill, Teamcenter), DOORS, Jira
- Training and certification for regulated industries

### Why This Works

The free layer is the moat. Once the format is the standard, the paid tools sell themselves. The natural boundary is clean: individual engineers and the open-source community get everything they need for free. Organizations with compliance requirements and non-technical users pay for the GUI and enterprise features.

The audience isn't just aerospace — it's anyone who has a "critical spreadsheet" checked into Git as an opaque blob. That's a massive latent market.

## Key Risks

- The format not being expressive enough for real-world use cases not anticipated during design
- Adoption stalling because Excel import/export isn't good enough for incremental migration
- Trying to be too much too soon and losing the simplicity that makes the format work
- Microsoft waking up and doing this themselves (unlikely — no incentive)
- Getting the free/paid line wrong (give away too little and nobody adopts; too much and nobody pays)

## Core Principle

**The less custom infrastructure you build, the better.** The whole point of plain text is that git diff, git merge, git blame, and git log already work. Every piece of Git tooling that works with the format is free adoption surface you didn't have to earn. The format doing the heavy lifting is the entire thesis.