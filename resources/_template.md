# Design guide — <subcircuit-category>

Generic, reusable knowledge on how to design this category of
subcircuit. No project-specific values here (that's the role of the
per-project spec sheet) — only the method: what topology, what
parameters must always be fixed, what pitfalls are known.

## Use cases covered
<What types of subcircuits/needs this guide covers. E.g. "any
non-isolated buck converter from 5-24V input to a single low-voltage
rail below 2A" or "any decoupling + reset network for a Cortex-M
class MCU.">

## Recommended topology
<Schematic-level approach: component families used, typical
connections, and why (e.g. feedback network placement, why a
particular protection diode goes where it goes). Typical order of
operations in schematic capture and why that order matters.>

## Parameters to always fix explicitly
<List of values/choices that must never be silently guessed for
this category — serves as a checklist before launching KICAD-01/the
generator in autopilot mode.>
- <parameter> — <why it's structural>

## Known pitfalls
<Frequent or counter-intuitive errors specific to this category of
subcircuit.>

<If this category is MCU-adjacent (pin muxing, boot-mode/strap
pins): flag which parameters are firmware-owned rather than
hardware-derived — see `_spec-template.md`'s "Firmware interface
contract" (KICAD-11) — so a project never fills them in from a
hardware-side default by mistake.

If this category routinely involves a high-pin-count, power,
connector, or IC footprint: note that symbol/footprint/pinout
provenance (KICAD-12) must be verified pin-by-pin before layout,
not just visually spot-checked.>

## Category-specific verification
<Beyond the generic KICAD-04 checklist: is there a check specific to
this subcircuit family (e.g. loop stability margin for a regulator,
ESD path for a user-facing connector, ground return path for a
sensor)?

**Default analysis set for KICAD-05** (delete this note once
filled in): state which of DC/operating-point, AC/small-signal
(loop stability), transient, thermal, and worst-case/tolerance apply
to this category by default, and which are exempt with a one-line
reason — this is what `_spec-template.md`'s simulation table gets
populated against. E.g. "buck converter: DC + AC + transient
mandatory; thermal recommended above 1A; worst-case recommended if
feedback divider tolerance affects output regulation beyond spec."
If this category is exempt from KICAD-05 entirely (e.g. a static,
low-risk network), say so explicitly here rather than leaving it
implicit. If not exempt, also note the category's typical bring-up
checkpoints (KICAD-13) — the test points and first-power-on
measurements a project's spec sheet should default to for this
category.>

## Layout notes (if PCB in scope)
<Placement/routing guidance specific to this category — e.g. what
must sit close to what, which nets need controlled width/length,
where a ground/thermal plane matters.

If this category is KICAD-05-relevant, this section is not just
execution guidance for `kicad-builder` — per KICAD-04, it must be
reviewed and approved by `kicad-architect` before routing starts,
since layout changes electrical behavior (parasitics, noise
coupling, thermal path) rather than just realizing a fixed
schematic.>

## Compliance reference table (KICAD-14, only if mains-adjacent/safety-critical)
<Only for categories that routinely involve mains proximity, battery
charging/protection, high voltage, or a user-accessible connector —
delete this section otherwise. List the standard *families* that
typically apply, as a pure reference for a human/professional to
confirm applicability — never a calculation or a compliance
assertion. E.g.:
- EMC: FCC Part 15, CISPR 32/35, EN 55032/55035, IEC 61000-4-x as
  applicable
- Safety: IEC/UL 62368-1, IEC 61010-1, IEC 60335, or the relevant
  end-product safety standard for this category
- Materials: RoHS, REACH, Prop 65 if relevant
- Isolation: IEC 60664 (or the chosen end-product safety standard)

State explicitly: "standard family identified here for reference;
applicability to a specific design must be confirmed by a qualified
professional — this table is not a compliance determination.">

## External references
<Datasheets, application notes, standards, generic reference designs
(not specific to one project's exact component).>

## History
- <date> — created, co-written with <origin context/project>
