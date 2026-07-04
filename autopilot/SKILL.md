---
name: kicad-autopilot
description: Extension of the kicad-designer skill allowing Claude to fill in missing component values and advance schematic/PCB work without systematic validation, subject to strict invariants and an auditable assumption log.
trigger: Any kicad-designer session where the user wants to delegate decisions on unspecified values rather than being interrupted at every missing value.
version: 0.1
depends_on: kicad-designer
---

# $kicad-autopilot — Autonomous mode for kicad-designer

## Principle

Never block on a missing value if it can be reasonably derived.
Never guess silently either. Any value set without explicit user
instruction follows the generator → critic → gate loop, and is
logged before being used.

## Invariants (non-negotiable, even in autonomous mode)

- **KICAD-01** — Any value not provided and not derivable from an
  existing spec sheet must be chosen by an explicit method
  (datasheet formula, standard design equation, reference design) —
  never a silent estimate.
- **KICAD-02** — Every assumption is logged in the project's
  `assumptions.md` before use: value, method/source, confidence
  level, affected subcircuit/net.
- **KICAD-03** — The subcircuits' dependency order (from the project
  breakdown) is strictly respected: never wire or generate a
  downstream block whose upstream dependency (e.g. its supply rail,
  its reference clock) isn't locked and validated.
- **KICAD-04** — Before calling a subcircuit locked: pass through
  the critic checklist (next section), comparing the produced
  schematic against the spec sheet's values and the project's
  constraints. For any KICAD-05-relevant subcircuit, this includes
  confirming the design guide's "Layout notes" have been reviewed as
  an architecture decision before routing starts, not just executed
  mechanically afterward — layout changes electrical behavior
  (parasitics, noise coupling, thermal path) in a way that has no
  equivalent in geometric CAD, so it does not belong purely to the
  execution phase (see `kicad-designer.md`, Step 3bis). Before Step 4
  closes on a PCB-in-scope subcircuit, the checklist also
  cross-checks every test point named in the subcircuit's bring-up
  plan (KICAD-13) against the routed PCB — each one must exist as an
  accessible, labeled pad, not just as a line in the spec sheet. A
  bring-up plan and a finished board are allowed to diverge
  silently otherwise, which makes the plan worthless at the moment
  it's actually needed. Before Step 4 closes on any KICAD-05-relevant
  subcircuit, the checklist also requires `scripts/check_spice_coverage.py`
  to have been run against that subcircuit's components, with a
  report showing no `failed` state and no non-waived `blocked_*`
  state (see `kicad-spice-coverage.md`) — locking a subcircuit
  without running it is not a shortcut, it is the same silent
  divergence this invariant exists to catch.
- **KICAD-05** — Any subcircuit with electrical risk or non-trivial
  dynamic behavior — power conversion, high current, anything
  user-touchable, protection circuits, loop-stability-dependent
  designs (regulators, op-amp feedback) — never gets a single
  `simulated`/`not simulated` flag. Its required analysis types must
  be named explicitly, from: **DC/operating-point**, **AC/small-
  signal** (loop stability, phase margin), **transient** (load/line
  step), **thermal**, and **worst-case/tolerance** (component and
  temperature variation) — the design guide's "Category-specific
  verification" section sets the default set for the category (e.g.
  a buck converter defaults to DC + AC + transient at minimum). Each
  named analysis gets its own status (`done` / `NOT DONE — validate
  before fabrication` / `not applicable`), and where SPICE was used,
  its own **model confidence** rating (high/medium/low, based on
  whether the model is vendor-provided vs. generic behavioral, and
  whether the operating point is inside the model's stated validity
  range) — "simulated" is not a terminal trust state; a low-
  confidence model run is closer to `NOT DONE` than to a verified
  result. A purely passive or low-risk subcircuit (e.g. a pull-up
  resistor, a status LED) is exempt from all analysis types, but
  this status must be explicitly justified in its spec sheet rather
  than assumed by default. Per-component model identification and a
  minimal executed sanity check (not a substitute for the analyses
  above) are automated by `kicad-spice-coverage.md`, and running it
  to a clean (or explicitly waived) result is mandatory — not
  optional tooling — before a KICAD-05-relevant subcircuit can be
  locked (KICAD-04) or fabricated (KICAD-06); its report feeds the
  `model confidence` rating here, it does not replace it.
- **KICAD-06** — No triggering of a fabrication or assembly order
  (submitting Gerbers/BOM/CPL to a fab/assembly house, or any
  equivalent MCP tool call that commits to a physical build) without
  explicit confirmation — this is the actually irreversible, costly
  action in this domain (money, lead time, physical boards), unlike
  a file overwrite, which git already protects. Overwriting an
  existing `.kicad_sch`/`.kicad_pcb`/`.kicad_pro` or deleting a file
  still warrants flagging before acting, but is a secondary courtesy
  here, not the primary gate. A *repeat* fabrication/assembly order
  of a revision with an unresolved fail/deviation entry in
  `bringup-log.md` (KICAD-13) is blocked the same way — a known-bad
  value must never be silently re-ordered. Any fabrication or
  assembly order covering a KICAD-05-relevant subcircuit is likewise
  blocked if `kicad-spice-coverage.md`'s report for that subcircuit
  shows a `failed` state or a non-waived `blocked_*` state for any
  of its components — see KICAD-05. If `notes.md` declares
  `intended for sale: yes` and any KICAD-14 field is unresolved (no
  RoHS status, no logged creepage/clearance intent on a mains-
  adjacent net, no isolation rating logged) for a subcircuit going
  into this order, the confirmation prompt must surface that gap
  explicitly before the order — this does not block a prototype
  build, but ensures the gap is seen before ordering rather than
  discovered at certification time, which is far more expensive to
  fix post-layout.
- **KICAD-07** — No subcircuit is generated without a corresponding
  design guide in the skill's `resources/` (not to be confused with
  the project's `specs/` — see `_spec-template.md` for the
  per-project instance sheet). If no guide covers the requested
  subcircuit category: STOP, never improvise an undocumented design
  method from general knowledge. Propose a draft guide (using the
  `resources/_template.md` structure, pre-filled as best as
  possible) and ask the user to co-write/validate it before any
  schematic generation for this category. The validated guide is
  added to the skill (so it's versioned and reusable on future
  projects), not just to the current project. The same reactive,
  never-improvise discipline applies at the per-component level to
  the MPN registry and smoke-test templates in
  `kicad-spice-coverage.md` — an unknown component blocks only its
  own coverage entry, not the whole subcircuit.
- **KICAD-08** — Before any export intended for fabrication ordering
  (Gerbers/BOM/CPL, as opposed to a schematic-only prototype or
  simulation pass): ERC must be clean, DRC must be clean (if PCB is
  in scope), and the netlist/footprint set must be verified
  consistent between schematic and PCB. Any unresolved warning
  blocks the export regardless of mode.
- **KICAD-09** — Every component in a locked spec sheet has a logged
  lifecycle status (active / NRND / EOL) and single-source flag —
  mechanical parts don't get discontinued by a distributor the way
  electronic components do, so this has no equivalent in a purely
  geometric spec sheet and must be checked explicitly rather than
  assumed fine. A component flagged single-source with no identified
  second source, or with a non-active lifecycle status, blocks any
  export intended for fabrication ordering — same tier as KICAD-08 —
  until the user explicitly accepts the risk or a substitute is
  logged.
- **KICAD-10** — No Step 3/Step 3bis operation (kicad-designer.md)
  is ever attempted as a silent fallback to freehand
  `.kicad_sch`/`.kicad_pcb` file editing because the MCP server
  doesn't expose it as an atomic tool call. Run the capability audit
  (kicad-designer.md, Step -1) once per project; if an operation
  needed later turns out unsupported/uncomposable, STOP and confirm
  the fallback method with the user explicitly before proceeding —
  never discover the gap mid-execution and paper over it.
- **KICAD-11** — Any value that is firmware-owned rather than
  hardware-derived (pin mux selection, boot-strap pin intent,
  protocol timing requirements) is never filled in by KICAD-01's
  generator using a hardware-side method (datasheet formula,
  reference design) — it must be sourced from an explicit firmware
  spec, or logged as `TBD — pending firmware spec` in the
  subcircuit's firmware interface contract (`_spec-template.md`).
  Neither `kicad-architect` nor `kicad-builder` invents a strap-pin
  state or mux selection on the hardware side alone.
- **KICAD-12** — Before PCB layout begins for any subcircuit
  containing a high-pin-count, power, connector, or IC footprint:
  the symbol-to-footprint-to-datasheet-pinout mapping must be
  verified pin-by-pin and its provenance logged (symbol source,
  footprint source, datasheet pin table reference) — not just
  visually spot-checked. An unverified footprint on this class of
  component blocks layout, same tier as KICAD-07.
- **KICAD-13** — For any KICAD-05-relevant subcircuit, a bring-up
  plan (required test points, expected first-power-on measurement
  and its pass range, rail sequencing order) is logged in the spec
  sheet before the *first* fabrication order for a given board
  revision — the electrical equivalent of "dry-fit before anything
  irreversible" (cad-skill's servo-mount.md), needed because a wrong
  board can power up and fail silently instead of visibly failing to
  fit. Writing the plan once is not the same as running it: the
  actual risk of a bad unit escaping into use is highest on the
  *Nth* assembled board of a revision, not the prototype the plan
  was written against — the same gap KICAD-02 already closed for
  assumptions (logged *before use*, not just documented once).
  Every assembled unit of a KICAD-05-relevant board therefore gets
  its own entry in `bringup-log.md` (format below) before that unit
  is considered usable — the plan is authored once (architecture
  phase, Step 2), but its execution is logged per unit, not per
  revision.
- **KICAD-14** — Compliance-adjacent hygiene only, never compliance
  verification. For any subcircuit already flagged under KICAD-05's
  blocking cases (mains-adjacent, battery-charging/protection, high
  voltage, user-accessible connector): log RoHS/REACH declaration
  status per component, creepage/clearance **design intent** cited
  against a named published standard table (e.g. IEC 60664-1), and
  isolation barrier type with its datasheet-rated withstand voltage
  — in the spec sheet's "Regulatory intent" section. Every one of
  these fields carries the disclaimer "logged design intent, not a
  compliance verification." This skill — and any agent operating
  under it — must never output that a design "passes," "is
  compliant with," "meets," or "is certified to" any named standard
  (EMC, safety, RoHS, isolation): it has no way to physically measure
  a board or run accredited test equipment, and a false positive
  here causes worse harm than an under-simulated circuit, because it
  can make a human skip a professional review they'd otherwise have
  sought. KICAD-05's softer "NOT DONE — validate before fabrication"
  pattern does **not** apply to this invariant — this is a hard
  boundary, not a confidence tier. If `notes.md` declares the
  project `intended for sale: yes` (see kicad-designer.md, Step 0),
  this logging is mandatory for every KICAD-05-flagged subcircuit,
  not merely recommended, and Step 0's output must state once (not
  repeated every turn) that formal certification by an accredited
  lab or qualified engineer is required before sale and nothing in
  this skill substitutes for it.

## Decision loop (generator → critic → gate)

**1. $generator** — proposes a value or topology to fill the gap,
with the method used and a confidence level (high/medium/low).

**2. $critic** — reviews the proposal against: the subcircuit's spec
sheet, the constraints in `notes.md`, and invariants KICAD-01
through KICAD-14. Lists any discrepancies or inconsistencies found.

**3. $gate** — decides:
- **GO**: assumption logged in `assumptions.md`, schematic (and, if
  in scope, PCB) generation launched
- **STOP**: back to the user (see blocking cases below), no
  generation until a response is received

## Cases where the gate always blocks (even in autonomous mode)

- Low confidence on an assumption that impacts an already-fabricated
  or locked board revision
- Two reasonable design methods produce incompatible component
  values or topologies (genuine ambiguity, not simple lack of info)
- The subcircuit carries an electrical safety risk — mains-adjacent,
  battery charging/protection, high voltage, a user-accessible
  connector — always flagged explicitly, never resolved silently
- A component is single-source with no identified second source, or
  carries a non-active lifecycle status (NRND/EOL) — see KICAD-09
- A firmware-owned value (pin mux, boot-strap intent) has no logged
  firmware spec source and is about to be filled in by a hardware-
  side guess — see KICAD-11
- A high-pin-count, power, connector, or IC footprint has no logged
  symbol/footprint/pinout provenance and layout is about to start —
  see KICAD-12
- Before the first fabrication order for a board revision with no
  logged bring-up plan for a KICAD-05-relevant subcircuit — see
  KICAD-13
- A KICAD-05-relevant subcircuit's `kicad-spice-coverage.md` report
  has a `failed` state or a non-waived `blocked_*` state for any of
  its components, or the report was never generated for that
  subcircuit — before it is locked (KICAD-04) or before any
  fabrication order (KICAD-06)
- Any output about to state or imply that a design "passes,"
  "complies with," "meets," or "is certified to" a named EMC/safety/
  RoHS/isolation standard — always rewritten to logged design intent
  with the mandatory disclaimer instead, never phrased as
  verification — see KICAD-14
- Before any export intended for fabrication ordering (as opposed to
  a schematic-only prototype or simulation pass) — see KICAD-08 and
  KICAD-09

## assumptions.md format

One file per project, one line per assumption:

```markdown
## <date> — <affected subcircuit>
- Value used: <value>
- Method: <datasheet formula / standard / calculation / reference design / other>
- Confidence: high / medium / low
- Impact if wrong: <cascading affected subcircuits/nets>
- Status: to validate / implicitly validated (no feedback) / explicitly validated
```

## bringup-log.md format (KICAD-13)

One file per project, one entry per assembled unit (not per
revision — see KICAD-13):

```markdown
## <date> — <board revision> — unit <serial/identifier>
- Subcircuit: <affected subcircuit>
- Test point(s) checked: <list>
- Measurement(s): <value(s) obtained>
- Pass range (from bring-up plan): <expected range>
- Result: pass / fail / deviation from plan
- If fail or deviation: action taken (rework, scrap, deferred) and
  whether it was folded back into the schematic/spec sheet
```

A test failure or deviation recorded here blocks a *repeat*
fabrication/assembly order of the same revision (KICAD-06) until
it's either folded back into the schematic or explicitly accepted
by the user — a known-bad value must never be silently re-ordered.

## What this changes in KiCad prompts

Block 2 of the prompt template (kicad-designer, "wire nets" /
"place symbols") can now contain a value set by Claude rather than
waiting on the user, provided block 1 of the reply message always
starts with: "Assumption made: [value] — [method] — confidence
[level]. Logged in assumptions.md." The user sees the decision
without having had to provide it, and can correct it after the fact
without it blocking progress.
