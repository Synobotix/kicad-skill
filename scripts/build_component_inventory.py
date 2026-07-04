#!/usr/bin/env python3
"""Ingestion stage (stage 1) of the SPICE Model Coverage and Sanity
Harness — produces the canonical component_inventory.yaml consumed by
scripts/check_spice_coverage.py, from either a real KiCad schematic
(via kicad-cli) or an MCP-KiCad-agent-produced manifest. See
kicad-spice-coverage.md for the overall architecture.

Usage:
    python3 scripts/build_component_inventory.py \\
        --from-kicad-cli path/to/top_level.kicad_sch \\
        --output component_inventory.yaml

    python3 scripts/build_component_inventory.py \\
        --from-mcp-manifest path/to/manifest.yaml \\
        --output component_inventory.yaml

Exactly one of --from-kicad-cli / --from-mcp-manifest is required —
both adapters converge on the same canonical schema so the resolution
stage never needs to know which one produced its input.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import yaml

SCHEMA_VERSION = 1

# Best-effort keyword heuristic for role_hint, matched against
# "<libsource lib> <libsource part>" lowercased. Never authoritative —
# only the MPN registry's own `role` field (looked up at resolution
# time) decides the functional role. Extend this list freely; a miss
# just means role_hint stays null, which is always a safe fallback.
ROLE_HINT_KEYWORDS = [
    ("regulator", "regulator"),
    ("ldo", "regulator"),
    ("dcdc", "regulator"),
    ("buck", "buck_regulator"),
    ("boost", "boost_regulator"),
    ("conn", "connector"),
    ("usb", "connector"),
    ("crystal", "crystal"),
    ("oscillator", "crystal"),
    ("led", "led"),
    ("mountinghole", "mechanical"),
    ("fiducial", "mechanical"),
    ("testpoint", "test_point"),
]


def _guess_role_hint(lib, part):
    haystack = f"{lib} {part}".lower()
    for keyword, role_hint in ROLE_HINT_KEYWORDS:
        if keyword in haystack:
            return role_hint
    return None


# --------------------------------------------------------------------------
# from_kicad_cli()
# --------------------------------------------------------------------------

def _run_kicad_cli_netlist_export(schematic_path):
    if shutil.which("kicad-cli") is None:
        raise SystemExit(
            "kicad-cli is not installed or not on PATH — required for --from-kicad-cli. "
            "Install KiCad (kicad-cli ships with it) or use --from-mcp-manifest instead."
        )
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as fh:
        xml_path = fh.name
    try:
        proc = subprocess.run(
            ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
             "--output", xml_path, str(schematic_path)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise SystemExit(
                f"kicad-cli sch export netlist failed for {schematic_path}:\n{proc.stderr}"
            )
        return pathlib.Path(xml_path).read_text()
    finally:
        pathlib.Path(xml_path).unlink(missing_ok=True)


def from_kicad_cli(schematic_path):
    """Parse a kicad-cli kicadxml netlist export into the canonical
    component_inventory schema.

    Per-component data available in this format (verified against
    real KiCad 9 exports, not just the format spec):
      - <comp ref="...">: one element per component instance, never
        aggregated/grouped (unlike `kicad-cli sch export bom`, whose
        --group-by does NOT reliably force one row per ref — this is
        why ingestion uses the netlist export, not the BOM export).
      - <value>/<footprint>: direct text content.
      - <fields><field name="MPN">...</field></fields>: the project's
        MPN field, by convention (this skill requires it be named
        exactly "MPN" — see resources/mpn-registry/_template.md).
      - <property name="dnp"/>: a bare, valueless property present
        only when the symbol's real "Do not populate" checkbox (the
        schematic's own `(dnp yes)` flag) is set. Do not confuse this
        with a *custom* field some projects also happen to name "DNP"
        for their own BOM conventions — that's unrelated project data,
        not the fitted/not-fitted signal.
      - <libsource lib="..." part="...">: used only for the
        never-authoritative role_hint heuristic.
      - <sheetpath names="/a/b/">: hierarchical sheet path.
    """
    xml_text = _run_kicad_cli_netlist_export(schematic_path)
    root = ET.fromstring(xml_text)

    components = []
    for comp in root.iter("comp"):
        ref = comp.get("ref")

        value_el = comp.find("value")
        value = value_el.text if value_el is not None else None

        footprint_el = comp.find("footprint")
        footprint = footprint_el.text if footprint_el is not None else None

        fitted = not any(
            prop.get("name") == "dnp" for prop in comp.findall("property")
        )

        mpn = None
        fields_el = comp.find("fields")
        if fields_el is not None:
            for field in fields_el.findall("field"):
                if field.get("name") == "MPN" and (field.text or "").strip():
                    mpn = field.text.strip()
                    break

        # This adapter never emits mpn_status=ambiguous: a single
        # schematic export has exactly one authoritative "MPN" field
        # per component. Other MPN-adjacent fields real projects carry
        # (MPN_ALT, DigikeyPN, JLC, ...) are legitimate distinct
        # metadata (e.g. second-source part numbers, distributor SKUs)
        # — not competing claims about the same MPN — so they are
        # never treated as a conflict here. "ambiguous" is reserved
        # for an ingestion path that could genuinely disagree with
        # itself (e.g. merging two independent data sources).
        mpn_status = "present" if mpn else "missing"

        role_hint = None
        role_hint_source = "none"
        libsource_el = comp.find("libsource")
        if libsource_el is not None:
            role_hint = _guess_role_hint(libsource_el.get("lib", ""), libsource_el.get("part", ""))
            if role_hint:
                role_hint_source = "footprint_heuristic"

        sheet_path = None
        sheetpath_el = comp.find("sheetpath")
        if sheetpath_el is not None:
            sheet_path = sheetpath_el.get("names")

        components.append({
            "ref": ref,
            "source": "kicad_cli",
            "mpn": mpn,
            "mpn_status": mpn_status,
            "raw_mpn_candidates": [],
            "footprint": footprint,
            "value": value,
            "fitted": fitted,
            "role_hint": role_hint,
            "role_hint_source": role_hint_source,
            "sheet_path": sheet_path,
        })

    return components


# --------------------------------------------------------------------------
# from_mcp_manifest()
# --------------------------------------------------------------------------

def from_mcp_manifest(manifest_path):
    """Map an MCP-KiCad-agent-produced manifest into the canonical
    component_inventory schema.

    Expected input contract (documented here since no fixed schema for
    this was settled during design — no live MCP KiCad server was
    available to validate this against, unlike from_kicad_cli() which
    was verified against real kicad-cli output):

        components:
          - ref: "U3"
            mpn: "LM2596S-5.0"       # or omit/null if unknown
            footprint: "..."
            value: "..."
            fitted: true             # defaults to true if omitted
            role_hint: "buck_regulator"  # agent's judgment, optional
            sheet_path: "/power/buck1"

    The agent has already done interpretive work (reading the
    schematic visually, dialogue with the user), so any role_hint it
    supplies is tagged role_hint_source: mcp_agent — distinct from the
    kicad_cli adapter's mechanical footprint_heuristic — but it is
    still never treated as authoritative; only the MPN registry's
    `role` field is, at resolution time.
    """
    data = yaml.safe_load(pathlib.Path(manifest_path).read_text()) or {}
    components = []
    for raw in data.get("components", []):
        mpn = raw.get("mpn") or None
        components.append({
            "ref": raw["ref"],
            "source": "mcp_manifest",
            "mpn": mpn,
            "mpn_status": "present" if mpn else "missing",
            "raw_mpn_candidates": raw.get("raw_mpn_candidates", []),
            "footprint": raw.get("footprint"),
            "value": raw.get("value"),
            "fitted": raw.get("fitted", True),
            "role_hint": raw.get("role_hint"),
            "role_hint_source": "mcp_agent" if raw.get("role_hint") else "none",
            "sheet_path": raw.get("sheet_path"),
        })
    return components


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-kicad-cli", metavar="SCHEMATIC", help="top-level .kicad_sch file")
    source.add_argument("--from-mcp-manifest", metavar="MANIFEST", help="MCP-agent-produced manifest YAML")
    parser.add_argument("--output", required=True, help="where to write the canonical component_inventory.yaml")
    args = parser.parse_args(argv)

    if args.from_kicad_cli:
        components = from_kicad_cli(args.from_kicad_cli)
    else:
        components = from_mcp_manifest(args.from_mcp_manifest)

    inventory = {"schema_version": SCHEMA_VERSION, "components": components}
    pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.output).write_text(yaml.safe_dump(inventory, sort_keys=False))
    print(f"Wrote {len(components)} components to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
