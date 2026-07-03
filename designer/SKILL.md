---
name: kicad-designer
description: General skill for turning an electronics idea into a schematic (and, when in scope, a routed PCB) in KiCad via MCP, with resource management (datasheets, SPICE models, reference designs) separated by subcircuit and by project.
trigger: Any request to design, simulate, or lay out an electronic circuit/PCB.
version: 0.1
---

# $kicad-designer — General KiCad design skill

## Principle

The skill is the method, reusable from one project to another.
Resources (component values, datasheets, off-the-shelf reference
designs) are specific to each project and live alongside it, not
inside the skill.

## Recommended folder structure

```
kicad-projects/
  <project-name>/
    notes.md               # project-wide brief
    assumptions.md          # KICAD-02 assumption log
    bringup-log.md          # KICAD-13 per-unit bring-up execution log
    specs/
      <subcircuit-1>.md    # brief + references for this subcircuit
      <subcircuit-1>.pdf   # datasheet(s) for key components
      <subcircuit-1>.lib   # vendor SPICE model, if provided
    boards/                 # KiCad outputs (.kicad_pro/.kicad_sch/
                             # .kicad_pcb, exported netlist/BOM/Gerbers)

skills/kicad/               # this skill, as a submodule
  resources/
    <subcircuit-category>.md   # generic design guide (KICAD-07),
                                 # reusable across projects
```

## Step -1 — MCP capability audit (see kicad-autopilot, KICAD-10)

Once per project, before Step 0: enumerate the KiCad MCP server's
actually available tool calls and mark each Step 3/Step 3bis
operation (place symbol, wire net, assign footprint, run ERC, update
PCB from schematic, place footprint, route net, run DRC, export)
as **supported** (a direct tool call exists), **composable** (can be
built from lower-level tool calls), or **fallback-to-file-edit** (no
tool call exists; would require freehand `.kicad_sch`/`.kicad_pcb`
editing). Log the result once in `notes.md`. Never discover a
missing primitive mid-execution and silently switch to file editing
— see KICAD-10; if an operation is fallback-to-file-edit, confirm
with the user before relying on it, since freehand editing of
KiCad's s-expression files carries real corruption risk this skill
otherwise avoids by design.

## Step 0 — Project brief (notes.md)

To be fixed once for the whole project, before the first subcircuit:

- Supply voltage(s) and overall power budget
- Target application and environment (temperature range, indoor/
  outdoor, battery vs mains-adjacent)
- Key ICs/component families already fixed (MCU, main power
  topology) if any
- Manufacturing constraints: layer count, min trace/space, assembly
  process (THT/SMD/mixed), target fab (its capability rules)
- Regulatory/safety constraints, if any (isolation requirements,
  ESD/EMI targets, mains proximity)
- **Intended for sale: yes / no / unknown** (see kicad-autopilot,
  KICAD-14) — gates whether compliance-adjacent hygiene logging is
  mandatory or merely recommended for KICAD-05-flagged subcircuits.
  If yes, state once here — not repeated every turn — that formal
  certification by an accredited lab or qualified engineer is
  required before sale and that nothing in this skill substitutes
  for it.

## Step 1 — Breakdown into subcircuits

For any non-trivial board: list the functional blocks (power
input/conversion, MCU/processing, sensor/actuator interfaces,
connectors, protection), their mutual electrical dependencies (e.g.
a load block depends on its supply rail being defined; a
communication block depends on the MCU's I/O voltage), and the
resulting design order (blocks others depend on are designed
first). One subcircuit = one spec file.

## Step 1bis — Design guide (see kicad-autopilot, KICAD-07)

Before designing a subcircuit, check that a generic guide exists in
`skills/kicad/resources/` for its category. If no guide covers this
category: do not improvise — raise the gap to the user and co-write
the guide before continuing.

## Step 1ter — Firmware interface contract (see kicad-autopilot, KICAD-11)

For any MCU-adjacent subcircuit (pin muxing, boot-mode/strap pins,
protocol timing that firmware, not hardware, ultimately determines):
fill in the spec sheet's firmware interface contract before treating
the pin assignment as locked. These values are firmware-owned, not
hardware-derived — neither `kicad-architect` nor `kicad-builder`
invents a mux selection or strap-pin intent on the hardware side
alone. If firmware requirements aren't defined yet, log the value as
`TBD — pending firmware spec` rather than picking a default and
moving on; it's a genuine gap, not a hardware assumption KICAD-01's
generator can resolve.

## Step 2 — Spec sheet per subcircuit (see separate template)

Each `specs/<subcircuit>.md` file documents:
- Function of the subcircuit and constraints (voltage/current
  budget, interface with neighboring blocks)
- Known values, with their source (datasheet, calculation,
  measurement, reference design)
- Attached files: datasheets, vendor SPICE models, reference
  schematics
- Dependencies: which other subcircuits must be locked before this
  one

## Step 3 — Schematic capture

Prompt template per subcircuit, built from the spec sheet:

```
Open/create project [project_name].
Create schematic sheet [sheet_name] for [subcircuit].
Place symbols: [components with values, taken from the spec sheet].
Wire nets: [connections / net names, per the design guide's
  recommended topology].
Assign footprints: [footprint per component, per spec sheet or
  design guide default — verified against the datasheet's
  mechanical drawing].
Run ERC.
```

## Step 3bis — PCB layout (when in scope for this project)

Once a sheet's schematic is ERC-clean and its spec sheet is locked —
**and, if the subcircuit is KICAD-05-relevant, once its design
guide's "Layout notes" have been reviewed and approved by
`kicad-architect`** (see kicad-autopilot, KICAD-04). Layout is not a
mechanical realization of an already-fixed schematic: parasitics,
noise coupling, and thermal path are determined by placement and
routing, not by the netlist alone, so for a risk-bearing subcircuit
this is an architecture decision, not just craftsmanship — do not
let `kicad-builder` improvise it unreviewed:

```
Update PCB from schematic (import netlist).
Place footprints for [subcircuit], respecting the design guide's
  placement/clearance guidance (e.g. decoupling next to its IC,
  thermal relief for power parts).
Route [critical nets] per the design guide's constraints (width for
  current, controlled length/impedance where specified).
Run DRC.
```

## Step 4 — Verification

- **ERC** after every schematic change — never leave unresolved ERC
  warnings on a subcircuit before calling it locked.
- **Simulation** (KiCad's built-in ngspice) for subcircuits with
  electrical risk or non-trivial dynamic behavior — run the specific
  analysis types the subcircuit's design guide requires (DC, AC/loop
  stability, transient, thermal, worst-case/tolerance), not a single
  generic pass — see KICAD-05.
- **DRC** after every PCB layout change, if PCB is in scope.
- Netlist/footprint consistency check (schematic and PCB in sync)
  before any export.
- **Symbol/footprint/pinout provenance** pin-by-pin, before layout
  starts, for any high-pin-count, power, connector, or IC footprint
  — see KICAD-12. A visual spot-check is not sufficient for this
  component class.
- BOM check: every part has a confirmed footprint and a known-
  available supplier part number, with lifecycle status and
  single-source risk logged — see KICAD-09. Flag placeholders and
  unresolved single-source parts explicitly rather than leaving them
  silent.
- **Bring-up plan** logged for any KICAD-05-relevant subcircuit
  before the first fabrication order for its board revision — test
  points, expected first-power-on measurement and pass range, rail
  sequencing order — see KICAD-13. Before this step closes on a
  PCB-in-scope subcircuit, cross-check every test point named in the
  plan against the routed PCB — each one must exist as an
  accessible, labeled pad, not just as a line in the spec sheet (see
  KICAD-04).
- **Bring-up execution**, once a unit is actually assembled: log one
  entry per assembled unit in `bringup-log.md`, not just once before
  the first fab order of the revision — see KICAD-13. A fail or
  deviation blocks a repeat fabrication order of the same revision
  (KICAD-06) until resolved.

## Using external resources

### Datasheets and reference designs
The primary source of truth for a subcircuit's known values and
topology. Always cite the datasheet section/page (or reference
design name) in the spec sheet's "source" column rather than a bare
"datasheet" — later review needs to be able to re-check the number.

### Symbols and footprints
Prefer the official KiCad library or the manufacturer-provided
`.kicad_sym`/`.pretty` footprint over hand-drawing one from a
photo — a hand-drawn footprint can be off by a fraction of a mm on
pin pitch, which is invisible in the schematic but fatal at
assembly. If neither is available, verify a hand-drawn footprint's
pad pitch/size directly against the datasheet's mechanical drawing
before it's used in layout, and note that verification in the spec
sheet. For any high-pin-count, power, connector, or IC footprint,
this verification must go further than a visual check: confirm the
symbol-to-footprint-to-datasheet-pinout mapping pin-by-pin and log
its provenance (symbol source, footprint source, datasheet pin table
reference) before layout starts — see KICAD-12. Library provenance
is one of the highest-probability failure modes in EDA precisely
because an unverified footprint can look correct in both the
schematic and the 3D preview while still being wrong.

### SPICE models
Prefer a vendor-provided SPICE model (`.lib`/`.mod`) over a generic
behavioral approximation for anything going through KICAD-05
simulation — a generic op-amp or regulator model can hide the exact
non-ideality (loop stability, dropout behavior) the simulation was
meant to catch. If no vendor model exists, say so explicitly in the
spec sheet rather than silently substituting a similar part's model.
Simulation confidence is bounded by model fidelity: log the model's
source and its stated validity range (temperature, load range) as
the model confidence rating in the spec sheet's simulation table —
treat a "simulated" result run on a generic model outside its
validity range as evidence, not proof, per KICAD-05.

### Model choice by phase — hard-pinned via the kicad-agents repo
- **Architecture phase** (Step 0, Step 1, Step 1bis, ambiguity
  resolution, **plus reviewing/approving the design guide's "Layout
  notes" for any KICAD-05-relevant subcircuit before Step 3bis
  starts**): delegate to the **`kicad-architect`** agent (`model:
  opus` in its frontmatter — pinned by the harness, not a runtime
  choice). Deeper multi-step reasoning is required here — a wrong
  topology, supply-rail decision, or layout approach for a
  risk-bearing subcircuit propagates to every downstream subcircuit
  or degrades electrical behavior in ways execution can't self-
  correct. This agent never generates or exports KiCad files.
- **Execution phase** (Step 3, Step 3bis, Step 4, on a subcircuit
  whose spec sheet — and, if KICAD-05-relevant, whose layout review —
  is already locked): delegate to the **`kicad-builder`** agent
  (`model: sonnet` in its frontmatter). Faster and cheaper, and
  sufficient once the plan is fixed. This agent never makes an
  architectural decision — if the spec sheet, design guide, or
  required layout review is incomplete, it stops and reports back
  rather than improvising.
- **Setup**: these two agents are defined in the separate
  [`kicad-agents`](../kicad-agents) repo, not in this skill — added
  as its own submodule and symlinked into the consuming project's
  `.claude/agents/` (a submodule path alone isn't enough for the
  harness to discover them). See `kicad-agents`' README for the
  exact commands. This skill only documents the phase split; it
  doesn't pin the model itself.
- Do not ask the user to manually switch models (`/model opus` /
  `/model sonnet`) — that's only a fallback if `kicad-agents` isn't
  set up yet in the current project.
