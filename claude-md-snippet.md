## KiCad (schematic/PCB via MCP)

This project uses the `kicad-designer` / `kicad-autopilot` skill
(submodule at `skills/kicad`) for any electronics design work, plus
the `kicad-agents` submodule (`agents/kicad`) for the
architecture/execution model split.

- Before any KiCad task: read `skills/kicad/kicad-designer.md` and
  `skills/kicad/kicad-autopilot.md` in full — they define the
  method, the folder layout (`notes.md`, `specs/`, `boards/`), and
  the non-negotiable invariants (KICAD-01 to KICAD-14).
- **Step -1 first**: before Step 0 of any new project, run the MCP
  capability audit (KICAD-10) — never let `kicad-builder` discover a
  missing MCP tool call mid-execution and silently fall back to
  freehand file editing.
- **KICAD-07 in practice**: never invent a design method for a
  subcircuit category not already covered in
  `skills/kicad/resources/`. If no guide exists for the requested
  category, stop and ask to co-write one before generating anything
  in KiCad.
- **Model split is mandatory, not advisory**: delegate the
  architecture phase (breakdown, dependency graph, guide
  authoring/gap resolution, ambiguity resolution, **and reviewing
  the design guide's "Layout notes" for any KICAD-05-relevant
  subcircuit before routing starts**) to the `kicad-architect` agent,
  and the execution phase (schematic capture, footprint assignment,
  PCB layout once a subcircuit's spec — and required layout review —
  is locked) to the `kicad-builder` agent. Do not do either phase
  directly in the main session, and do not ask the user to manually
  switch models — that's only a fallback if the agents aren't set up
  yet (see `kicad-agents`' README for the `.claude/agents/` symlink
  setup).
- Every assumption made on a missing value must be logged in the
  project's `assumptions.md` before use (KICAD-02) — never a silent
  estimate.
- **KICAD-05 in practice**: never log a subcircuit as "simulated" —
  name which analysis type(s) (DC, AC/loop stability, transient,
  thermal, worst-case) were actually run, and log the SPICE model's
  confidence level alongside the result.
- **Firmware-owned values** (pin mux, boot-strap intent) are never
  filled in from a hardware-side default — source them from the
  firmware spec or log `TBD — pending firmware spec` (KICAD-11).
- **Provenance before layout**: any high-pin-count, power, connector,
  or IC footprint needs a pin-by-pin symbol/footprint/pinout
  verification logged before routing starts, not a visual check
  (KICAD-12).
- No export intended for fabrication ordering (Gerbers/BOM/CPL)
  without a clean ERC/DRC pass (KICAD-08), a resolved lifecycle/
  single-source check on every component (KICAD-09), and — for the
  first fab order of a board revision — a logged bring-up plan for
  every KICAD-05-relevant subcircuit (KICAD-13).
- **Bring-up is per-unit, not per-revision**: writing the bring-up
  plan once does not satisfy KICAD-13 — every assembled unit of a
  KICAD-05-relevant board gets its own entry in `bringup-log.md`. A
  fail/deviation there blocks a *repeat* fab/assembly order of the
  same revision (KICAD-06) until resolved. KICAD-04 also cross-checks
  that every planned test point actually exists as an accessible pad
  on the routed PCB, not just as a line in the spec sheet.
- **KICAD-14 is a hard boundary, not a confidence tier**: for any
  mains-adjacent/battery-charging/high-voltage/user-accessible
  subcircuit, log RoHS/REACH status, creepage/clearance design
  intent, and isolation ratings — but never output that a design
  "passes," "is compliant with," "meets," or "is certified to" any
  named standard (EMC, safety, RoHS, isolation). This skill cannot
  physically measure a board or run accredited test equipment; a
  false positive here is worse than an under-simulated circuit. If
  `notes.md` declares `intended for sale: yes`, this logging is
  mandatory, and KICAD-06's fab-order confirmation must surface any
  unresolved field before the order.
