# Spec sheet — <subcircuit-name>

## Function
<Role of the subcircuit in the board. One sentence.>

## Dependencies
- Must be designed after: <subcircuit(s), or "none">
- Must be designed before: <subcircuit(s), or "none">

## Known values
| Value | Number | Source |
|---|---|---|
| <e.g. input voltage range> | <V/A/Ω/...> | <datasheet §x.y / calculation / reference design / measurement> |

## Electrical constraints
- Supply rail(s) used: <rail name(s) and voltage>
- Current/power budget: <value or "none">
- Interface with neighboring subcircuits: <description>

## Firmware interface contract (KICAD-11)
<Only for MCU-adjacent subcircuits — delete this section otherwise.
Any value here is firmware-owned, not hardware-derived; never fill
a row from a hardware-side method (datasheet formula, reference
design) — source it from the firmware spec or mark it TBD.>

| Pin | Function / mux selection | Boot-strap intent | Source |
|---|---|---|---|
| <e.g. PA9> | <e.g. USART1_TX> | <n/a, or default state + why> | <firmware spec ref, or "TBD — pending firmware spec"> |

## Symbol/footprint/pinout provenance (KICAD-12)
<Only for high-pin-count, power, connector, or IC components on this
subcircuit — delete this section otherwise. A visual spot-check is
not sufficient for this component class.>

| Component (ref designator) | Symbol source | Footprint source | Datasheet pin table verified? |
|---|---|---|---|
| <e.g. U1> | <official lib / vendor / hand-drawn> | <official lib / vendor / hand-drawn> | <yes, pin-by-pin / no — blocks layout> |

## Simulation status (KICAD-05)
- Electrical risk / dynamic behavior: <power conversion / high current / loop-stability-dependent / user-touchable / none>
- If no risk: justification: <text>

| Analysis type | Status | Model used | Model confidence |
|---|---|---|---|
| DC / operating point | <done / NOT DONE — validate before fabrication / not applicable> | <vendor SPICE model / generic behavioral model / none> | <high / medium / low> |
| AC / small-signal (loop stability) | | | |
| Transient (load/line step) | | | |
| Thermal | | | |
| Worst-case / tolerance (component + temperature) | | | |

<Default analysis set for this subcircuit's category is set by its
design guide's "Category-specific verification" section — add/remove
rows to match, don't leave a required row blank.>

- Probable failure point identified: <description, or "none">

## Supply chain / lifecycle (KICAD-09)
| Component (ref designator) | Lifecycle status | Single-source? | Second source identified | Lead time |
|---|---|---|---|---|
| <e.g. U1> | <active / NRND / EOL> | <yes / no> | <part number, or "none"> | <estimate, or "unknown"> |

## Regulatory intent (KICAD-14)
<Only for subcircuits flagged under KICAD-05's blocking cases
(mains-adjacent, battery-charging/protection, high voltage, user-
accessible connector) — delete this section otherwise. Every field
below is **logged design intent, not a compliance verification** —
never phrase any of these as "compliant," "certified," "passes," or
"meets [standard]." Mandatory if the project's `notes.md` declares
`intended for sale: yes`; recommended otherwise.>

| Component / net | RoHS/REACH declared? | Creepage/clearance intent | Isolation barrier type + rated withstand voltage |
|---|---|---|---|
| <e.g. U2, or "mains-side net"> | <yes, per datasheet / no / unknown> | <distance + cited standard table, e.g. "3.2mm per IEC 60664-1 Table F.2"> | <optocoupler / transformer / DC-DC module / none, + datasheet withstand rating, or "n/a"> |

## Bring-up plan (KICAD-13)
<Required for any KICAD-05-relevant subcircuit, before the first
fabrication order for this board revision — the electrical
equivalent of a mechanical dry-fit. Not required for exempt/low-risk
subcircuits. This is the plan, authored once at spec-lock time —
actual execution against each assembled unit is logged separately in
the project's `bringup-log.md`, not here (see kicad-autopilot,
KICAD-13). Every test point listed below must exist as an
accessible, labeled pad on the routed PCB before Step 4 closes — see
KICAD-04.>
- Required test points: <list, or "none">
- Rail/subcircuit sequencing order: <e.g. "verify 3.3V rail before
  enabling MCU reset release">
- Expected first-power-on measurement(s) and pass range: <e.g.
  "VOUT at TP3: 3.3V ± 3%">
- Known likely failure signature(s): <description, or "none
  identified">

## Attached files
- Datasheet(s): <file name/link, or "none">
- Reference schematic: <file name/link, or "none">
- Vendor SPICE model: <file name, or "none">

## Design notes
<Points of attention, footprint/assembly choices, uncertainties to
resolve before locking the subcircuit.>
