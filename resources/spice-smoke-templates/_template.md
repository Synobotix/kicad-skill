# Smoke-test template — <role>

Generic, reusable ngspice smoke-test for one functional component role,
consumed by the SPICE Model Coverage and Sanity Harness. Not a full
electrical validation — it proves a component's model loads, its pins
wire up as expected, and a trivial operating point converges. It does
not prove the model is electrically accurate; see `model_confidence`
in the matching MPN registry entry for that judgment call.

## When to create this file

One file per functional role (`buck_regulator`, `ldo_regulator`,
`mcu_decoupling`, ...), not per component and not per project. A new
MPN registry entry can only reference a role that already has a
template here — if the role is new, co-write this template alongside
the first registry entry that needs it, the same way a new subcircuit
category needs a design guide under KICAD-07 before generation.

## File location and naming

`resources/spice-smoke-templates/<role>.yaml` — `<role>` must be the
exact string used in the `role` field of matching
`resources/mpn-registry/<role>/*.yaml` entries.

## Schema

```yaml
role: "buck_regulator"

# Fields this role requires from the consuming project's own spec
# sheet (via its "SPICE resolution values" section, keyed by ref
# designator) when a registry entry for this role has
# output_adjustable: true. The resolution stage checks this list
# against the spec sheet — a missing field here is exactly what turns
# into a blocked_missing_spec classification. Omit entirely (or leave
# empty) for roles that are never output_adjustable.
project_specific_fields:
  - nominal_vin
  - fb_divider_r1
  - fb_divider_r2

# ngspice netlist with {{resolved.*}} placeholders, filled in from the
# resolution stage's flat resolved.* dict (registry fields plus, if
# applicable, the project_specific_fields above). Every placeholder
# used here must exist as a resolved.* field — the resolution stage
# fails the component with an explicit reason rather than defaulting
# silently if one is missing.
netlist_template: |
  * smoke test {{resolved.mpn_base}} ({{resolved.ref}})
  .include {{resolved.spice_model_path}}
  Vin vin 0 {{resolved.nominal_vin}}
  Cin vin 0 {{resolved.input_cap_min}}u
  Xreg vin gnd vout fb en {{resolved.subckt_name}}
  L1 vout sw {{resolved.inductor_mid}}u
  Cout vout 0 {{resolved.output_cap_min}}u
  Rfb1 vout fb_node {{resolved.fb_divider_r1}}
  Rfb2 fb_node 0 {{resolved.fb_divider_r2}}
  .op
  .end

# Execution-time classification only. blocked_missing_registry,
# blocked_missing_template, blocked_missing_spec and not_fitted are
# already decided upstream (ingestion/resolution) before a component
# ever reaches this template — by the time netlist_template above is
# rendered, resolved.* is guaranteed complete. This stage only ever
# produces "passed" or "failed" (+ a specific detail reason), never a
# silent default.
classification:
  - condition: "rendered netlist fails to parse"
    result: "failed"
    detail: "syntax_error"
  - condition: "number of connected pins != number of pins the role expects"
    result: "failed"
    detail: "pin_mismatch"
  - condition: "ngspice .op does not converge"
    result: "failed"
    detail: "convergence_risk"
  - condition: "otherwise"
    result: "passed"
```

## Field reference

- **role** — must match the `role` field of every MPN registry entry
  that uses this template; the resolution stage looks templates up by
  this exact string.
- **project_specific_fields** — the authoritative list of what the
  resolution stage must find under `components.<ref>` in the project
  spec sheet when `output_adjustable: true`. This is what lets the
  resolution stage generalize across roles without hardcoded
  per-role logic — keep it in sync with every `{{resolved.*}}`
  placeholder below that isn't sourced from the registry.
- **netlist_template** — write it to be minimal and fast (a smoke test,
  not a real simulation): one `.op` is usually enough. Every
  `{{resolved.*}}` reference must trace back either to a registry field
  (see the matching `mpn-registry/_template.md`) or to
  `project_specific_fields` above — never introduce a placeholder that
  neither side declares.
- **classification** — keep this to `passed`/`failed` with a `detail`
  reason; don't reintroduce upstream states here. If you find yourself
  wanting a new upstream state (something decided before ngspice even
  runs), it belongs in the resolution stage's classification, not here.

## Known pitfalls

- A placeholder used in `netlist_template` that isn't backed by a
  registry field or listed in `project_specific_fields` will only fail
  at render time, for the first component that hits it — declare both
  sides explicitly rather than discovering the gap live.
- Keep the smoke test genuinely minimal. A `.tran`/`.ac` sweep here
  duplicates KICAD-05's real analysis work and turns a fast sanity
  check into a slow one — this template is a coverage gate, not the
  place for loop-stability or transient validation.
- A convergence failure isn't always a bad model — an unrealistic
  operating point picked by the netlist template (e.g. an inductor
  value from the wrong end of `datasheet_rules.inductor.range_uh`) can
  cause a false `convergence_risk`. Prefer representative mid-range
  values over edge-of-range values when filling in the netlist.

## History
- <date> — created, co-written with <origin context/project>
