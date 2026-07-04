# MPN registry entry — <mpn_base>

Generic, reusable knowledge about one specific component (identified
by its base manufacturer part number), consumed by the SPICE Model
Coverage and Sanity Harness. No project-specific values here (feedback
divider values, actual VIN, etc. for adjustable-output parts belong in
the consuming project's own spec sheet) — only facts that are true of
this component regardless of which project uses it.

## When to create this file (pure-reactive population — mirrors KICAD-07)

This registry starts empty and is populated one entry at a time,
strictly on demand: when the harness encounters a component whose MPN
does not resolve to an existing file under
`resources/mpn-registry/<role>/<mpn_base>.yaml`, it stops that
component's smoke-test (and only that one — see the harness doc's
local-blocking rule) and reports a structured "needs co-authoring"
block naming the exact expected path, the raw MPN, and the normalized
`mpn_base`.

**Never pre-seed or improvise an entry from general knowledge.** Stop
and co-write it with the user from the actual datasheet, exactly like
a subcircuit design guide under KICAD-07 — a plausible-looking but
unverified entry is worse than a blocked smoke-test, because it
produces false confidence instead of an explicit gap.

## File location and naming

`resources/mpn-registry/<role>/<mpn_base>.yaml`

- `<role>` must match an existing
  `resources/spice-smoke-templates/<role>.yaml` (create that template
  first — or together — if the role is new; see that directory's own
  `_template.md`).
- `<mpn_base>` is the *normalized* base part number: uppercased,
  truncated at the first `/`, with known packaging/taping/tolerance
  suffixes stripped per the rules in
  `resources/mpn-registry/_normalization-rules.yaml`. If normalization
  doesn't cleanly resolve a raw MPN, resolve that ambiguity with the
  user before picking a file name — never guess.

## Schema

```yaml
mpn_base: "LM2596"            # normalized base part number (see naming above)
role: "buck_regulator"        # must match resources/spice-smoke-templates/<role>.yaml
lifecycle_status: "active"    # active | nrnd | eol — KICAD-09
single_source: false          # KICAD-09

spice_model:
  source: "vendor"            # vendor | generic | none
  path: "models/lm2596.lib"   # relative path the harness can resolve; omit if source: none
  subckt_name: "LM2596"       # .subckt name inside the model file; omit if source: none

pins:
  # KiCad pin name/number -> functional role, used to generate the smoke-test netlist.
  # Keys here must match what the role's smoke-test template expects.
  vin: 1
  gnd: 2
  vout: 3
  fb: 4
  en: 5

datasheet_rules:
  # Component-family-specific sizing constraints from the datasheet.
  # Informational/human-facing only — the harness never derives
  # resolved.* values from this automatically (picking a "representative"
  # point in a range, e.g. an inductor value, is an engineering judgment
  # call, not a safe mechanical default). Shape varies by role — this is
  # the buck_regulator shape as an example, not a fixed schema.
  input_cap:
    min_uf: 100
    voltage_derating: 0.8
  inductor:
    range_uh: [33, 100]
  output_cap:
    min_uf: 100

smoke_test_values:
  # The exact, author-chosen values the role's smoke-test template needs
  # in resolved.* beyond spice_model/pins/output_adjustable-derived
  # fields — copied verbatim into resolved.*, never computed by the
  # harness. Keys here must match every {{resolved.*}} placeholder in
  # resources/spice-smoke-templates/<role>.yaml that isn't already
  # covered by spice_model_path/subckt_name/pins/project_specific_fields.
  # Picking these (e.g. a mid-range inductor value rather than an
  # edge-of-range one) is exactly the kind of judgment call this file
  # exists to make explicit and reviewable.
  input_cap_min: 100
  inductor_mid: 66.5
  output_cap_min: 100

output_adjustable: true       # true: output voltage/behavior depends on
                               # project-specific wiring (feedback divider,
                               # reference, sense resistor, ...) — those
                               # values are NEVER generic and must never be
                               # added here. They come from the consuming
                               # project's spec sheet
                               # ("SPICE resolution values" section), keyed
                               # by ref designator. See the harness doc's
                               # resolution stage for the exact mechanism.

model_confidence: "medium"    # high | medium | low — feeds KICAD-05.
                               # "simulated" is never a terminal trust state;
                               # this rating travels with every result the
                               # harness produces for this component.

notes: "..."                  # anything a future author needs to know:
                               # known model quirks, dialect issues,
                               # convergence hints, datasheet section refs.
```

## Field reference

- **mpn_base / role** — identity and binding key. `role` is the single
  source of truth for which smoke-test template applies; never inferred
  from the KiCad symbol name at resolution time.
- **lifecycle_status / single_source** — KICAD-09 lifecycle tracking,
  carried into the harness report so a `passed` result doesn't silently
  hide an EOL or single-sourced part.
- **spice_model** — set `source: none` for components with no useful
  SPICE representation (e.g. a bare connector). The harness treats this
  as a terminal `not_applicable` classification, not an error.
- **pins** — only the pins the smoke-test netlist actually needs to
  wire up; not a full pinout.
- **datasheet_rules** — sizing constraints for a human to read (design
  guide cross-checks, review context). Not consumed mechanically by the
  harness — keep it to what's useful for review, not a full datasheet
  transcription.
- **smoke_test_values** — the actual numbers the harness plugs into the
  smoke-test netlist. Must cover every `{{resolved.*}}` placeholder the
  role's template uses that isn't already produced by `spice_model`,
  `pins`, or (when applicable) the project's `project_specific_fields`.
  Choose representative values deliberately (e.g. a mid-range inductor,
  not an edge case likely to cause a spurious convergence failure).
- **output_adjustable** — the split point between generic (registry)
  and project-specific (spec sheet) data. Getting this wrong in either
  direction causes real harm: `false` when it should be `true` invites
  a fabricated generic default; `true` when it should be `false` forces
  every project to redundantly restate a fixed value.
- **model_confidence** — an honest assessment of how much to trust this
  specific SPICE model (vendor model quality, known divergence from
  real silicon, etc.), not how well the smoke-test happened to run.

## Known pitfalls

- A raw MPN with a packaging/taping suffix that doesn't match any
  normalization rule will silently fail to resolve — if this happens
  repeatedly for one vendor's naming convention, add the pattern to
  `_normalization-rules.yaml` rather than special-casing it in a single
  entry.
- Two entries under different `<role>` folders that both claim the same
  `mpn_base` is a registry conflict, not a valid dual-role component —
  resolve which role is correct rather than leaving both.
- Marking `output_adjustable: false` for convenience to avoid dealing
  with the project spec sheet split is a false-confidence shortcut —
  the harness has no way to detect this mistake on its own; it depends
  on this entry being written honestly at co-authoring time.

## History
- <date> — created, co-written with <origin context/project>
