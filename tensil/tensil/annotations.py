"""
Tensil annotations — reads and writes sidecar .tsl.annotations files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import yaml


@dataclass
class Annotation:
    """A single cell or row annotation."""
    cell: Optional[str] = None    # e.g. "threshold[1002]"
    row: Optional[str] = None     # e.g. "1001" (primary key value)
    color: Optional[str] = None
    note: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None


def read_annotations(source: Union[str, Path]) -> List[Annotation]:
    """
    Read a .tsl.annotations file and return a list of Annotation objects.

    source can be:
      - a path to a .tsl file (will look for .tsl.annotations alongside it)
      - a path directly to a .tsl.annotations file
      - a raw YAML string containing annotations
    """
    path = Path(source)

    # If given the .tsl file path, derive the annotations path
    if path.suffix == ".tsl":
        path = Path(str(path) + ".annotations")
    elif not str(path).endswith(".annotations"):
        path = Path(str(path) + ".annotations")

    if path.exists():
        text = path.read_text(encoding="utf-8")
    elif "\n" in str(source):
        text = str(source)
    else:
        return []

    raw = yaml.safe_load(text)
    if not raw or not isinstance(raw, list):
        return []

    annotations: List[Annotation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        annotations.append(Annotation(
            cell=entry.get("cell"),
            row=str(entry["row"]) if "row" in entry else None,
            color=entry.get("color"),
            note=entry.get("note"),
            author=entry.get("author"),
            date=str(entry["date"]) if "date" in entry else None,
        ))

    return annotations


def write_annotations(
    annotations: List[Annotation],
    dest: Union[str, Path],
) -> None:
    """
    Write a list of Annotations to a .tsl.annotations file.

    dest can be:
      - a path to a .tsl file (will write .tsl.annotations alongside it)
      - a path directly to a .tsl.annotations file
    """
    path = Path(dest)
    if path.suffix == ".tsl":
        path = Path(str(path) + ".annotations")
    elif not str(path).endswith(".annotations"):
        path = Path(str(path) + ".annotations")

    entries: List[dict] = []
    for ann in annotations:
        entry: dict = {}
        if ann.cell:
            entry["cell"] = ann.cell
        elif ann.row:
            entry["row"] = ann.row
        if ann.color:
            entry["color"] = ann.color
        if ann.note:
            entry["note"] = ann.note
        if ann.author:
            entry["author"] = ann.author
        if ann.date:
            entry["date"] = ann.date
        entries.append(entry)

    path.write_text(
        yaml.dump(entries, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
