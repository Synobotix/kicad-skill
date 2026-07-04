#!/usr/bin/env python3
"""SPICE Model Coverage and Sanity Harness.

Three stages: ingestion (component_inventory.yaml) -> resolution (MPN
registry + project spec sheet -> resolved.*) -> execution (ngspice smoke
test -> classification). See kicad-spice-coverage.md for the full design
and docs/brainstorms/2026-07-04-spice-coverage-harness.md for the
rationale behind each decision below.

Usage:
    python3 scripts/check_spice_coverage.py \\
        --component-manifest component_inventory.yaml \\
        --mpn-registry resources/mpn-registry \\
        --smoke-templates resources/spice-smoke-templates \\
        --spec-sheet path/to/project/spec-sheet.md \\
        --report-json artifacts/spice-coverage.json \\
        --report-md artifacts/spice-coverage.md \\
        --mode local
"""

import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

SCHEMA_VERSION = 1

# States decided at ingestion/resolution time, never at execution time.
UPSTREAM_STATES = {
    "not_fitted",
    "blocked_missing_registry",
    "blocked_missing_template",
    "blocked_missing_spec",
    "not_applicable",
}
ALL_STATES = UPSTREAM_STATES | {"passed", "failed"}

# Only these states count toward the CI-blocking summary (never a bare
# "blocked" count, which would conflate waived and non-waived entries).
BLOCKING_STATE_FAMILY = {
    "failed",
    "blocked_missing_registry",
    "blocked_missing_template",
    "blocked_missing_spec",
}


# --------------------------------------------------------------------------
# Stage 1 — ingestion
# --------------------------------------------------------------------------

def load_inventory(path):
    data = yaml.safe_load(pathlib.Path(path).read_text())
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit(
            f"component_inventory schema_version mismatch in {path}: "
            f"expected {SCHEMA_VERSION}, got {data.get('schema_version')!r}"
        )
    return data.get("components", [])


# --------------------------------------------------------------------------
# Stage 2 — resolution
# --------------------------------------------------------------------------

def load_normalization_rules(registry_dir):
    path = pathlib.Path(registry_dir) / "_normalization-rules.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("strip_suffixes", [])


def normalize_mpn(raw_mpn, strip_suffixes):
    """Deterministic, strict normalization — never fuzzy matching.

    strip().upper() -> truncate at first '/' -> strip known suffixes
    (longest first, repeatedly, since a part can carry more than one).
    """
    base = raw_mpn.strip().upper()
    base = base.split("/", 1)[0]
    suffixes = sorted((s.upper() for s in strip_suffixes), key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if suffix and base.endswith(suffix):
                base = base[: -len(suffix)]
                changed = True
    return base


def find_registry_entries(mpn_base, registry_dir):
    """Return every (role, path, entry) whose file name matches mpn_base,
    searched across all role subfolders — a match under more than one
    role is a registry conflict, not a valid dual-role component."""
    matches = []
    registry_dir = pathlib.Path(registry_dir)
    if not registry_dir.is_dir():
        return matches
    for role_dir in sorted(p for p in registry_dir.iterdir() if p.is_dir()):
        candidate = role_dir / f"{mpn_base}.yaml"
        if candidate.exists():
            entry = yaml.safe_load(candidate.read_text()) or {}
            matches.append((role_dir.name, candidate, entry))
    return matches


def load_smoke_template(role, templates_dir):
    path = pathlib.Path(templates_dir) / f"{role}.yaml"
    if not path.exists():
        return None, path
    return yaml.safe_load(path.read_text()) or {}, path


def _extract_spec_sheet_components(path):
    """Extract the 'components: {ref: {field: value}}' fenced YAML block
    under one spec sheet's '## SPICE resolution values' section. Returns
    {} if the section is absent — the resolution step is what turns
    that into blocked_missing_spec for any component that actually
    needed it, not this loader."""
    text = path.read_text()
    heading = re.search(r"^##\s*SPICE resolution values.*$", text, re.MULTILINE)
    if not heading:
        return {}
    fence = re.search(r"```yaml\s*\n(.*?)```", text[heading.end():], re.DOTALL)
    if not fence:
        return {}
    data = yaml.safe_load(fence.group(1)) or {}
    return data.get("components", {}) or {}


def load_project_spec_components(spec_sheet_paths):
    """A real project has one spec sheet per subcircuit, not one for the
    whole board — accept a mix of individual files and directories
    (searched recursively for *.md) and merge their 'components' blocks,
    keyed by ref designator (which must be unique across the project's
    schematic). Later files win on a duplicate ref; this doesn't try to
    detect or reconcile a genuine conflict between two spec sheets
    claiming the same ref."""
    combined = {}
    for raw_path in spec_sheet_paths or []:
        path = pathlib.Path(raw_path)
        if path.is_dir():
            candidates = sorted(path.rglob("*.md"))
        elif path.exists():
            candidates = [path]
        else:
            candidates = []
        for candidate in candidates:
            combined.update(_extract_spec_sheet_components(candidate))
    return combined


def resolve_component(component, strip_suffixes, registry_dir, templates_dir, project_components):
    """Run the full resolution sequence for one inventory component.
    Returns a dict always containing at least {ref, mpn, state, detail}."""
    ref = component["ref"]
    result = {"ref": ref, "mpn": component.get("mpn")}

    if component.get("fitted", True) is False:
        result["state"] = "not_fitted"
        result["detail"] = "Component marked DNP (not fitted)."
        return result

    mpn_status = component.get("mpn_status") or ("present" if component.get("mpn") else "missing")
    if mpn_status != "present":
        result["state"] = "blocked_missing_registry"
        result["detail"] = (
            f"mpn_status={mpn_status} in the inventory — no MPN to resolve a registry "
            "entry against. Needs co-authoring: never improvise a registry entry."
        )
        if component.get("raw_mpn_candidates"):
            result["detail"] += f" Candidates seen: {component['raw_mpn_candidates']}."
        return result

    raw_mpn = component["mpn"]
    mpn_base = normalize_mpn(raw_mpn, strip_suffixes)
    result["mpn_base"] = mpn_base

    matches = find_registry_entries(mpn_base, registry_dir)

    if not matches:
        result["state"] = "blocked_missing_registry"
        result["expected_registry_path"] = f"{registry_dir}/<role>/{mpn_base}.yaml"
        result["detail"] = (
            f"No registry entry for mpn_base={mpn_base!r} (raw MPN: {raw_mpn!r}). "
            "Stop and co-write resources/mpn-registry/<role>/"
            f"{mpn_base}.yaml with the user before continuing — never improvise."
        )
        return result

    if len(matches) > 1:
        roles = ", ".join(role for role, _, _ in matches)
        result["state"] = "blocked_missing_registry"
        result["detail"] = f"Registry conflict: {mpn_base} found under multiple roles ({roles})."
        return result

    role, registry_path, entry = matches[0]
    result["role"] = role
    result["registry_path"] = str(registry_path)

    spice_model = entry.get("spice_model") or {}
    if spice_model.get("source") == "none":
        result["state"] = "not_applicable"
        result["detail"] = "Registry entry declares no usable SPICE model for this component."
        return result

    template, template_path = load_smoke_template(role, templates_dir)
    if template is None:
        result["state"] = "blocked_missing_template"
        result["detail"] = f"No smoke-test template at {template_path}."
        return result

    resolved = {
        "ref": ref,
        "mpn_base": mpn_base,
        "role": role,
        "lifecycle_status": entry.get("lifecycle_status"),
        "single_source": entry.get("single_source"),
        "model_confidence": entry.get("model_confidence"),
        "spice_model_path": spice_model.get("path"),
        "subckt_name": spice_model.get("subckt_name"),
        "pins": entry.get("pins") or {},
    }
    # Author-chosen exact values (never mechanically derived from
    # datasheet_rules — see mpn-registry/_template.md).
    resolved.update(entry.get("smoke_test_values") or {})

    output_adjustable = bool(entry.get("output_adjustable", False))
    resolved["output_adjustable"] = output_adjustable
    if output_adjustable:
        required_fields = template.get("project_specific_fields") or []
        project_values = project_components.get(ref) or {}
        missing = [f for f in required_fields if f not in project_values]
        if missing:
            result["state"] = "blocked_missing_spec"
            result["detail"] = (
                f"output_adjustable=true for role {role!r} but the project spec sheet is "
                f"missing required field(s): {', '.join(missing)}."
            )
            return result
        for field in required_fields:
            resolved[field] = project_values[field]

    result["resolved"] = resolved
    result["smoke_template_path"] = str(template_path)
    result["netlist_template"] = template.get("netlist_template", "")
    return result


# --------------------------------------------------------------------------
# Stage 3 — execution
# --------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\{\{\s*resolved\.([a-zA-Z0-9_]+)\s*\}\}")


def render_netlist(netlist_template, resolved):
    """Substitute every {{resolved.field}} placeholder. Raises if a
    placeholder has no matching resolved.* field — never a silent
    default; that gap belongs in resolution (blocked_missing_spec), not
    a rendering-time surprise."""
    missing = []

    def _sub(match):
        field = match.group(1)
        if field not in resolved:
            missing.append(field)
            return match.group(0)
        return str(resolved[field])

    rendered = PLACEHOLDER_RE.sub(_sub, netlist_template)
    if missing:
        raise ValueError(
            f"netlist_template references resolved.{missing[0]} which isn't "
            "produced by the registry entry, smoke_test_values, or "
            "project_specific_fields for this role."
        )
    return rendered


def check_pin_mismatch(rendered_netlist, pins):
    """Heuristic proxy: count the node arguments on the subcircuit
    instantiation line (X...) and compare against the registry's
    declared pin count. This is not real netlist connectivity checking
    (that needs the ingestion stage's actual KiCad connectivity data,
    out of scope for this smoke test) — it only catches a
    pins/netlist_template drift within this harness's own generated
    netlist."""
    for line in rendered_netlist.splitlines():
        stripped = line.strip()
        if stripped[:1].upper() == "X":
            tokens = stripped.split()
            node_count = len(tokens) - 2  # drop instance name and subckt name
            if node_count != len(pins):
                return False
    return True


def run_ngspice(rendered_netlist, timeout_s):
    """Run one smoke-test netlist under ngspice in batch mode.
    Returns (state, detail, log_text). Raises SystemExit if ngspice
    itself isn't installed — that's an environment problem, not a
    per-component classification."""
    if shutil.which("ngspice") is None:
        raise SystemExit(
            "ngspice is not installed or not on PATH — required to execute smoke "
            "tests. Install it (e.g. `apt-get install ngspice`) before running "
            "this harness in execution mode."
        )

    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as fh:
        fh.write(rendered_netlist)
        netlist_path = fh.name

    try:
        proc = subprocess.run(
            ["ngspice", "-b", netlist_path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return "failed", "convergence_risk", f"ngspice timed out after {timeout_s}s."
    finally:
        pathlib.Path(netlist_path).unlink(missing_ok=True)

    log = proc.stdout + proc.stderr
    log_lower = log.lower()

    if proc.returncode != 0 or "syntax error" in log_lower or "unknown subckt" in log_lower:
        return "failed", "syntax_error", log
    if any(marker in log_lower for marker in ("no convergence", "singular matrix", "iteration limit", "gmin stepping failed")):
        return "failed", "convergence_risk", log
    return "passed", None, log


def execute_component(result, timeout_s, log_dir):
    """Mutate an already-resolved (state not yet set) component result
    in place with its execution outcome."""
    resolved = result["resolved"]
    rendered = render_netlist(result["netlist_template"], resolved)

    if not check_pin_mismatch(rendered, resolved.get("pins") or {}):
        result["state"] = "failed"
        result["detail"] = "pin_mismatch"
        return

    state, detail, log = run_ngspice(rendered, timeout_s)
    result["state"] = state
    result["detail"] = detail or "ngspice .op converged."

    if log_dir is not None:
        log_path = pathlib.Path(log_dir) / f"{result['ref']}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log)
        result["ngspice_log_path"] = str(log_path)
    else:
        result["ngspice_log_path"] = None


# --------------------------------------------------------------------------
# Report — waivers, summary, exit code
# --------------------------------------------------------------------------

def load_waivers(path):
    if not path or not pathlib.Path(path).exists():
        return []
    data = yaml.safe_load(pathlib.Path(path).read_text()) or {}
    return data.get("waivers", []) or []


def apply_waivers(results, waivers, today):
    waiver_index = {(w["mpn_base"], w["state"]): w for w in waivers}
    for result in results:
        result.setdefault("waived", False)
        result.setdefault("waiver", None)
        if result.get("state") not in BLOCKING_STATE_FAMILY:
            continue
        key = (result.get("mpn_base"), result["state"])
        waiver = waiver_index.get(key)
        if waiver is None:
            continue
        expires = waiver.get("expires")
        if expires and str(expires) < today:
            result["waiver_expired"] = True
            continue
        result["waived"] = True
        result["waiver"] = waiver


def build_report(results, mode, git_ref):
    summary = {state: 0 for state in ALL_STATES}
    waived_count = 0
    blocking_ci = 0
    for result in results:
        summary[result["state"]] = summary.get(result["state"], 0) + 1
        if result.get("waived"):
            waived_count += 1
        elif result["state"] in BLOCKING_STATE_FAMILY:
            blocking_ci += 1
    summary["waived"] = waived_count
    summary["blocking_ci"] = blocking_ci
    summary["total"] = len(results)

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "git_ref": git_ref,
        "summary": summary,
        "exit_code": 0 if blocking_ci == 0 else 1,
        "components": results,
    }
    return report


def render_markdown(report):
    lines = [
        "# SPICE coverage report",
        "",
        f"Generated: {report['generated_at']} — mode: `{report['mode']}` — ref: `{report['git_ref']}`",
        "",
        "## Summary",
        "",
        "| State | Count |",
        "|---|---|",
    ]
    for state in sorted(ALL_STATES):
        lines.append(f"| `{state}` | {report['summary'].get(state, 0)} |")
    lines += [
        f"| **waived** | {report['summary']['waived']} |",
        f"| **blocking_ci** | {report['summary']['blocking_ci']} |",
        "",
    ]

    active_waivers = [c for c in report["components"] if c.get("waived")]
    if active_waivers:
        if report["exit_code"] == 0:
            lines.append("> **WARNING** — this run is green only because of active waivers:")
        else:
            lines.append(
                "> **WARNING** — active waivers below are masking some otherwise-blocking "
                "issues, but this run is still failing on unwaived items:"
            )
        for c in active_waivers:
            w = c["waiver"]
            lines.append(
                f"> - `{c['ref']}` (`{c['state']}`): {w.get('reason', 'no reason given')} "
                f"(expires {w.get('expires', 'never')})"
            )
        lines.append("")

    lines += ["## Components", "", "| Ref | MPN | Role | State | Detail |", "|---|---|---|---|---|"]
    for c in report["components"]:
        lines.append(
            f"| {c['ref']} | {c.get('mpn') or '—'} | {c.get('role') or '—'} | "
            f"`{c['state']}`{' (waived)' if c.get('waived') else ''} | {c.get('detail', '')} |"
        )
    return "\n".join(lines) + "\n"


def git_ref():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--component-manifest", required=True, help="component_inventory.yaml (canonical schema)")
    parser.add_argument("--mpn-registry", default="resources/mpn-registry")
    parser.add_argument("--smoke-templates", default="resources/spice-smoke-templates")
    parser.add_argument(
        "--spec-sheet", action="append", default=[], metavar="PATH",
        help="project spec sheet file, or a directory searched recursively for *.md "
             "spec sheets (repeatable) — only needed for output_adjustable components",
    )
    parser.add_argument("--waivers", default="spice-coverage-waivers.yaml")
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--mode", choices=["local", "ci"], required=True)
    parser.add_argument("--timeout", type=float, default=10.0, help="per-component ngspice timeout, in seconds")
    parser.add_argument("--ngspice-log-dir", default=None, help="directory to store raw ngspice logs on failure")
    args = parser.parse_args(argv)

    components = load_inventory(args.component_manifest)
    strip_suffixes = load_normalization_rules(args.mpn_registry)
    project_components = load_project_spec_components(args.spec_sheet)

    results = []
    for component in components:
        result = resolve_component(
            component, strip_suffixes, args.mpn_registry, args.smoke_templates, project_components
        )
        if "state" not in result:
            execute_component(result, args.timeout, args.ngspice_log_dir)
        results.append(result)

    waivers = load_waivers(args.waivers)
    today = datetime.date.today().isoformat()
    apply_waivers(results, waivers, today)

    report = build_report(results, args.mode, git_ref())

    pathlib.Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.report_json).write_text(json.dumps(report, indent=2) + "\n")
    pathlib.Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.report_md).write_text(render_markdown(report))

    print(f"SPICE coverage: {report['summary']['total']} components, "
          f"{report['summary']['blocking_ci']} blocking CI, "
          f"{report['summary']['waived']} waived.")
    if report["summary"]["waived"]:
        if report["exit_code"] == 0:
            print("WARNING: this run is green partly due to active waivers — see the report.")
        else:
            print("NOTE: some active waivers are applied, but this run is still failing on unwaived items.")

    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
