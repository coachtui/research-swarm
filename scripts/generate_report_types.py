#!/usr/bin/env python3
"""Generate frontend/types/report.ts from the AnalysisReport Pydantic contract.

Phase C: the TypeScript types for the analysis report are GENERATED from the
Python models, never hand-maintained — schema drift becomes a CI failure
instead of a silent "N/A" in the UI.

Usage:
    python scripts/generate_report_types.py            # write the file
    python scripts/generate_report_types.py --check    # exit 1 if out of date

The generator converts the models' JSON Schema (a deliberately small subset:
objects, optionals, lists, string-keyed dicts, enums, datetimes) to TS
interfaces. If a contract change introduces a schema feature this doesn't
handle, it fails loudly rather than emitting wrong types.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUT_PATH = REPO_ROOT / "frontend" / "types" / "report.ts"

HEADER = """\
// GENERATED FILE — DO NOT EDIT.
//
// Source of truth: research_swarm/contracts/report.py (AnalysisReport).
// Regenerate with:  python scripts/generate_report_types.py
// CI fails if this file is out of date with the Python contract.

"""


def _ts_type(schema: dict, defs: dict) -> str:
    """Convert one JSON-schema node to a TS type expression."""
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]

    if "anyOf" in schema:
        parts = [_ts_type(sub, defs) for sub in schema["anyOf"]]
        # de-dup while preserving order
        seen: list[str] = []
        for part in parts:
            if part not in seen:
                seen.append(part)
        return " | ".join(seen)

    if "enum" in schema:
        return " | ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in schema["enum"])

    if "const" in schema:
        v = schema["const"]
        return f'"{v}"' if isinstance(v, str) else str(v)

    schema_type = schema.get("type")
    if schema_type == "string":
        return "string"  # covers date-time format too
    if schema_type in ("number", "integer"):
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "array":
        items = schema.get("items")
        inner = _ts_type(items, defs) if items else "unknown"
        return f"Array<{inner}>" if (" " in inner or "|" in inner) else f"{inner}[]"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if additional not in (None, True, False):
            return f"Record<string, {_ts_type(additional, defs)}>"
        if "properties" not in schema:
            return "Record<string, unknown>"
        raise ValueError(f"Inline object schemas are not supported: {schema}")

    raise ValueError(f"Unsupported schema node: {schema}")


def _emit_definition(name: str, schema: dict, defs: dict) -> str:
    # Enum definition
    if "enum" in schema and schema.get("type") in ("string", None):
        values = " | ".join(f'"{v}"' for v in schema["enum"])
        doc = schema.get("description", "")
        doc_line = f"/** {doc} */\n" if doc else ""
        return f"{doc_line}export type {name} = {values}\n"

    if schema.get("type") != "object":
        raise ValueError(f"Unsupported definition {name}: {schema}")

    required = set(schema.get("required", []))
    lines = []
    doc = schema.get("description", "")
    if doc:
        lines.append(f"/** {doc.splitlines()[0]} */")
    lines.append(f"export interface {name} {{")
    for prop, prop_schema in schema.get("properties", {}).items():
        ts = _ts_type(prop_schema, defs)
        optional = "" if prop in required else "?"
        desc = prop_schema.get("description")
        if desc:
            lines.append(f"  /** {desc} */")
        lines.append(f"  {prop}{optional}: {ts}")
    lines.append("}\n")
    return "\n".join(lines)


def generate() -> str:
    from research_swarm.contracts.report import AnalysisReport

    schema = AnalysisReport.model_json_schema()
    defs = schema.pop("$defs", {})

    parts = [HEADER]
    for name, definition in defs.items():
        parts.append(_emit_definition(name, definition, defs))
    parts.append(_emit_definition(schema.get("title", "AnalysisReport"), schema, defs))
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args()

    content = generate()

    if args.check:
        existing = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
        if existing != content:
            print(
                f"ERROR: {OUTPUT_PATH.relative_to(REPO_ROOT)} is out of date with "
                "research_swarm/contracts/report.py.\n"
                "Run: python scripts/generate_report_types.py",
                file=sys.stderr,
            )
            return 1
        print("report.ts is up to date")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content)
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
