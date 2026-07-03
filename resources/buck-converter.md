# Design guide — buck converter (non-isolated step-down)

Generic, reusable knowledge on how to design this category of
subcircuit. No project-specific values here (that's the role of the
per-project spec sheet) — only the method: what topology, what
parameters must always be fixed, what pitfalls are known.

## Use cases covered
Any non-isolated synchronous or non-synchronous buck converter
built around an integrated switching regulator IC (internal FET),
stepping a DC input in roughly the 4.5–36V range down to a single
lower-voltage rail, output current in the tens of mA up to a few A.
Does not cover isolated topologies (flyback, forward), multi-phase
converters, or discrete-FET designs with a separate gate driver —
those need their own guide.

## Recommended topology
Follow the IC datasheet's typical application circuit as the
starting topology — do not derive a buck topology from first
principles when the datasheet already publishes one with component
values or sizing formulas for the target input/output/current point.

Standard block order, and why the order matters for schematic
capture: input bulk/bypass capacitor → IC (with its enable, FB/VOUT
sense, and compensation pins per datasheet) → inductor → output
bulk capacitor → feedback divider (if the IC uses an adjustable
output rather than a fixed-voltage variant). Place the feedback
divider and its trace/net last, after the power path is fixed — its
routing is the most noise-sensitive part of the circuit and easy to
get wrong if laid out before the power path is settled.

Include the datasheet's recommended snubber/bootstrap network (for
synchronous designs with an external bootstrap cap) even if it looks
optional at low current — omitting it is a common source of
switching-noise-induced instability that only shows up under load.

## Parameters to always fix explicitly
- Input voltage range (min/max, not just nominal) — the IC's duty
  cycle range and minimum on-time must cover the full range, not
  just a typical bench-supply value.
- Output voltage and output current (continuous and peak/transient)
  — drives inductor saturation current and output cap ripple rating.
- Switching frequency — either fixed by the IC or set by an external
  resistor/cap; affects inductor value selection and EMI filtering
  needs.
- Inductor value, saturation current rating, and DCR — sized from
  the datasheet's inductor selection formula for the actual
  frequency/voltage/current point in use, never copied from an
  unrelated reference design at a different operating point.
- Output capacitor value and ESR — affects loop stability and output
  ripple; check against the datasheet's stability requirement, not
  just "add enough capacitance."
- Feedback divider resistor values (for adjustable-output variants)
  — must be computed from the IC's reference voltage and the target
  output, and use the datasheet's recommended top-resistor range to
  keep divider current in the intended band.

## Known pitfalls
- Undersizing input bulk capacitance: a converter with high input
  ripple current and a long/thin supply trace can brown out or
  oscillate under load transients even though DC operating point
  looks fine in a static check.
- Choosing an inductor by inductance value alone, ignoring saturation
  current: a part that looks correct in simulation at nominal load
  can saturate (and lose regulation, or overheat) at peak/transient
  load if its Isat rating is only marginally above nominal.
- Placing the feedback trace near the switching node (SW pin) or
  inductor: injected switching noise on the feedback node causes
  visible output ripple or instability that isn't present in an
  ideal-wire simulation.
- Omitting or under-rating the bootstrap capacitor on synchronous
  designs: causes incomplete high-side FET turn-on, visible as
  reduced efficiency or excess heat rather than an outright failure,
  making it easy to miss until thermal testing.
- Copying a reference design's component values wholesale without
  re-deriving them for the actual input/output/current point — a
  reference design at 12V→5V/1A does not necessarily hold at
  24V→3.3V/2A even with the same IC.

## Category-specific verification

**Default analysis set for KICAD-05**:
- **DC/operating-point** — mandatory. Confirm regulation at minimum
  load, nominal load, and peak/transient load.
- **AC/small-signal (loop stability)** — mandatory. Check phase
  margin using the IC's small-signal SPICE data or datasheet Bode
  data, not just time-domain ripple — a converter that looks stable
  at one operating point can show right-half-plane-zero-related
  instability at another, and low phase margin can look acceptable
  in a pure time-domain view.
- **Transient (load/line step)** — mandatory. A converter with
  adequate DC regulation can still brown out or oscillate on a fast
  load/line transient if input bulk capacitance or loop compensation
  is marginal.
- **Thermal** — recommended above ~1A continuous output, mandatory
  above the IC's datasheet-stated thermal derating threshold.
- **Worst-case/tolerance** — recommended whenever the feedback
  divider's resistor tolerance could push output regulation outside
  the downstream subcircuits' input tolerance window.
- Verify inductor saturation current against the actual peak current
  the load can demand, not just the nominal average current — this
  check is separate from and in addition to the transient SPICE run,
  since saturation is a component datasheet limit, not something
  every SPICE inductor model enforces.
- The regulator IC is a power/IC-class component: its symbol-to-
  footprint-to-datasheet-pinout mapping needs pin-by-pin provenance
  verification before layout, not a visual check — see KICAD-12.

**Bring-up checkpoints (KICAD-13)**: at minimum, a test point on
VOUT and, if accessible, on the switching node (SW) and feedback
node (FB). First-power-on check: VOUT within the datasheet's
regulation tolerance at no-load before connecting any downstream
subcircuit — never bring up a downstream load on an unverified
rail.

## Layout notes (if PCB in scope)

**This category is KICAD-05-relevant — these notes must be reviewed
and approved by `kicad-architect` before `kicad-builder` starts
routing** (see kicad-designer.md, Step 3bis): the switching loop
geometry below directly sets the converter's EMI and noise behavior,
it is not a mechanical afterthought to a fixed schematic.

- Keep the high-current switching loop (input cap → IC → inductor →
  output cap → return to input cap ground) as physically small as
  possible — this loop is the dominant EMI source in a buck
  converter.
- Route the feedback trace away from the switching node and
  inductor; treat it as a sensitive analog signal, not a power net.
- Give the IC's thermal pad (if present) a proper via array to a
  ground/thermal plane per the datasheet's thermal guidance — do not
  treat it as a purely electrical ground connection.

## External references
IC manufacturer datasheets (typical application circuit and
component selection formulas) and their associated reference-design
app notes are the primary source for this category — always prefer
the specific IC's own datasheet over a generic buck converter
tutorial for actual component sizing.

## History
- 2026-07-03 — created generically (not tied to one project's exact
  IC/operating point), pending refinement once a first real design
  logs its measured efficiency/ripple in a project's spec sheet.
