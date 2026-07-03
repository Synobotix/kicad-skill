---
name: kicad-spice-coverage
description: SPICE Model Coverage and Sanity Harness — binds each schematic component to a functional role via an MPN registry, runs a generated ngspice smoke-test per component, and reports model coverage/confidence. Implements KICAD-05's per-component model confidence requirement and mirrors KICAD-07's reactive-authoring discipline for the MPN registry.
trigger: Any kicad-designer/kicad-autopilot session touching a KICAD-05-relevant subcircuit, before closing Step 4 (KICAD-04) or ordering fabrication (KICAD-06). Also runs standalone via scripts/check_spice_coverage.py, as a local pre-push hook, and in CI.
depends_on: kicad-designer, kicad-autopilot
version: 0.1
---

# $kicad-spice-coverage — SPICE Model Coverage and Sanity Harness

## Principle

A smoke test proves a component's SPICE model loads, its pins wire up
as expected, and a trivial operating point converges. It does **not**
prove the model is electrically accurate, and it is not a substitute
for KICAD-05's real analyses (DC, AC/loop-stability, transient,
thermal, worst-case). This harness answers a narrower, prior question:
*is there even a usable, identified model behind every component this
board depends on* — before anyone spends time on the real analyses
against a model that turns out to be missing, mismatched, or
unidentified.

Design rationale and the sequence of decisions behind this design live
in `docs/brainstorms/2026-07-04-spice-coverage-harness.md` — this file
is the canonical, current-state reference; that one is the historical
record of *why*.

## Architecture (3 stages)

1. **Ingestion** — produces a canonical `component_inventory.yaml` from
   either `kicad-cli` netlist/BOM export or an MCP-generated manifest.
   Never the harness's dependency on MCP being available: CI only ever
   needs `kicad-cli`.
2. **Resolution** — binds each component to an MPN registry entry
   (`resources/mpn-registry/<role>/<mpn_base>.yaml`), normalizes the
   raw MPN (`resources/mpn-registry/_normalization-rules.yaml`, strict
   string matching, never fuzzy), and — for entries with
   `output_adjustable: true` — merges in the consuming project's own
   spec sheet values (`_spec-template.md`'s "SPICE resolution values"
   section) into a flat `resolved.*` dict per component.
3. **Execution** — renders the role's smoke-test template
   (`resources/spice-smoke-templates/<role>.yaml`) with `resolved.*`,
   runs it under ngspice, and classifies the result.

See each directory's own `_template.md` for the exact schema and
authoring rules (both mirror KICAD-07: never pre-seed or improvise an
entry — stop and co-write it with the user from the real datasheet).

## Classification states

| State | Decided at | Meaning | Who must act |
|---|---|---|---|
| `passed` | Execution | Model loads, pins match, converges | — |
| `failed` | Execution | Netlist syntax error, pin mismatch, or non-convergence (see `detail`) | Whoever owns the registry entry or smoke-test template |
| `blocked_missing_registry` | Resolution | MPN unresolved, absent from registry, or a registry conflict | Skill (co-write the registry entry) |
| `blocked_missing_template` | Resolution | Registry entry's `role` has no matching smoke-test template | Skill (co-write the template) |
| `blocked_missing_spec` | Resolution | `output_adjustable: true` but the project spec sheet is missing a required field | Project (complete the spec sheet) |
| `not_fitted` | Ingestion | Component marked DNP | — (informational only) |
| `not_applicable` | Resolution | Registry entry declares `spice_model.source: none` | — (no model expected) |

Only `failed` and non-waived `blocked_*` states count toward
`summary.blocking_ci` in the report — see "CI and local hook" below.

## Running it

```bash
python3 scripts/check_spice_coverage.py \
  --component-manifest component_inventory.yaml \
  --mpn-registry resources/mpn-registry \
  --smoke-templates resources/spice-smoke-templates \
  --spec-sheet specs/ \
  --waivers spice-coverage-waivers.yaml \
  --report-md artifacts/spice-coverage.md \
  --report-json artifacts/spice-coverage.json \
  --mode local|ci
```

`--spec-sheet` is repeatable and accepts either a single spec sheet file
or a directory (searched recursively for `*.md`) — a real project has
one spec sheet per subcircuit, not one for the whole board; their
`components` blocks (see `_spec-template.md`) are merged, keyed by ref
designator.

`component_inventory.yaml` itself is produced by a separate ingestion
step, `scripts/build_component_inventory.py`:

```bash
# from a real KiCad project (verified against kicad-cli 9.0.2 output,
# including a real hierarchical schematic with populated MPN fields):
python3 scripts/build_component_inventory.py \
  --from-kicad-cli path/to/top_level.kicad_sch \
  --output component_inventory.yaml

# from an MCP-KiCad-agent-produced manifest instead (see that script's
# from_mcp_manifest() docstring for the expected manifest shape —
# unverified against a live MCP KiCad server, unlike the kicad-cli path):
python3 scripts/build_component_inventory.py \
  --from-mcp-manifest path/to/manifest.yaml \
  --output component_inventory.yaml
```

Both adapters converge on the same canonical schema — the resolution
stage never knows or cares which one produced its input.

The JSON report is the single source of truth read by both the local
hook and CI; the Markdown report is generated from it for human review
— never authored or read independently, to avoid the kind of
field-naming drift this design already hit once between independently
designed schemas.

## CI and local hook (never trust the client)

- A local **pre-push** git hook (`scripts/install-hooks.sh` installs
  `.githooks/pre-push` into `.git/hooks/`, since the latter isn't
  versionable directly) runs the same command in `--mode local` —
  best-effort, bypassable (`--no-verify`, hook removal), a convenience
  only.
- A **GitHub Action** runs the same command in `--mode ci` and is the
  **sole authority** — it never attempts to verify whether the local
  hook ran or was tampered with (that's undetectable from CI by
  construction); it independently re-executes the same check.
- Both modes apply the same waiver policy: `failed` always fails; a
  `blocked_*` state fails unless listed in a project-committed
  `spice-coverage-waivers.yaml` (MPN, state, reason, added, expires —
  an expired waiver reverts to blocking automatically). A fully-waived
  run still exits 0 but always prints a `WARNING` banner — never
  silent.

## Open items

- **`from_kicad_cli()` design correction (found via real testing)**:
  the original design assumed a competing/second field (e.g.
  `Manufacturer_PN`) could signal `mpn_status: ambiguous`. Testing
  against a real, populated KiCad project (KiCad 9's `tiny_tapeout`
  demo) showed real projects routinely carry several MPN-adjacent
  fields alongside `MPN` — `MPN_ALT`, `DigikeyPN`, `JLC` — that are
  legitimate distinct metadata (second-source part, distributor SKU),
  never a conflicting claim about the same MPN. `from_kicad_cli()`
  therefore never emits `ambiguous`; it only ever reports `present` or
  `missing` from the `MPN` field. `ambiguous` remains in the canonical
  schema for a future ingestion path that could genuinely disagree
  with itself (e.g. merging two independent data sources) — it's just
  not something a single schematic export can produce.
- **`kicad-cli sch export bom` is not a viable ingestion source**:
  its `--group-by` does not reliably force one row per component (it
  still merges components whose displayed fields are otherwise
  identical, even when the differing `Reference` column is explicitly
  included in `--group-by`) — confirmed empirically, not just assumed.
  `from_kicad_cli()` uses `kicad-cli sch export netlist --format
  kicadxml` instead, which is always one `<comp>` element per
  component, never aggregated.
- ~~Execution stage untested against real ngspice~~ — **resolved**:
  verified end-to-end against a real `ngspice 44.2` install. `passed`
  (a converging primitive-only smoke test, no `.include` needed),
  `failed`/`syntax_error` (both a real "unknown subckt" reference and a
  malformed netlist line — ngspice's actual wording for a genuine
  syntax error is "Error on line N or its substitute:", which doesn't
  contain the literal string "syntax error"; it's still caught because
  a real parse/setup error always exits non-zero), and
  `failed`/`convergence_risk` (a floating node — ngspice recovers
  internally via gmin/source stepping and exits **0**, so the "singular
  matrix" / "gmin stepping failed" content markers are what actually
  catch it, not the exit code) were all reproduced and correctly
  classified, including through the full CLI (JSON report, exit code,
  saved `.log` file).
- **No fixture committed to the repo**: verification during
  implementation used both a hand-built fixture and, for the ingestion
  adapters specifically, real KiCad demo projects
  (`/usr/share/kicad/demos/flat_hierarchy`, `.../tiny_tapeout`) —
  none of these live in this repo. Codex's suggestion of a small
  committed fixture (one R, one C, one regulator, a smoke test under
  1s) so CI can validate the harness itself without an external KiCad
  project is still open.

## Relationship to KICAD-05 / KICAD-07

- Every `passed`/`failed` result carries the registry entry's
  `model_confidence` (KICAD-05) — a `passed` smoke test is evidence for
  a `high`/`medium`/`low` rating, never a promotion to a terminal
  "simulated, done" state on its own.
- The MPN registry's pure-reactive population (blocked, never
  improvised, always co-written on first encounter) is a
  finer-grained, per-component instance of KICAD-07's rule for
  subcircuit design guides.
- Running this harness to a clean (or explicitly waived) result is a
  **mandatory gate**, not optional tooling: `kicad-designer.md`'s Step
  4 checklist and `kicad-autopilot.md`'s KICAD-04/KICAD-06 invariants
  and "gate always blocks" list all require it before a
  KICAD-05-relevant subcircuit is locked or fabricated. The local
  pre-push hook and CI enforce this mechanically on push; the
  in-session checklist/gate items exist so the same requirement is
  visible and enforced *before* that point too, not just at push time.

## History
- 2026-07-04 — created, co-written via `/octo:brainstorm` Team mode
  (Codex + Claude); see `docs/brainstorms/2026-07-04-spice-coverage-harness.md`.
- 2026-07-04 — promoted from a cross-referenced, discoverable tool to
  a mandatory gate: added to `kicad-designer.md`'s Step 4 checklist,
  `kicad-autopilot.md`'s KICAD-04/KICAD-05/KICAD-06 invariant text,
  and its "cases where the gate always blocks" list, so an agent
  session (autonomous or not) is actually required to run it, not
  merely aware it exists.
