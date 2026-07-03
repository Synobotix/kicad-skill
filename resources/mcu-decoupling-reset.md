# Design guide — MCU decoupling and reset network

Generic, reusable knowledge on how to design this category of
subcircuit. No project-specific values here (that's the role of the
per-project spec sheet) — only the method: what topology, what
parameters must always be fixed, what pitfalls are known.

## Use cases covered
The per-power-pin decoupling network and the reset/boot-mode network
for any digital MCU (Cortex-M class, 8-bit AVR/PIC class, or
similar) — not the MCU's application-specific peripheral wiring,
which belongs in its own subcircuit's spec sheet.

## Recommended topology
Follow the MCU datasheet/reference manual's own recommended
decoupling scheme first — most vendors publish an exact
capacitor-per-pin table; do not substitute a generic "one 100nF per
power pin" rule when the datasheet specifies otherwise (e.g. an
additional bulk cap per power domain, or a different value for an
analog supply pin).

Standard block order for schematic capture: identify every distinct
power pin and power domain (core VDD, I/O VDD, analog VDDA if
present, VBAT for RTC/backup domain if present) → place one local
decoupling cap per power pin per the datasheet table → add the
shared bulk capacitor per power domain → reset network (reset pin,
pull-up/pull-down per datasheet polarity, optional external
supervisor/debounce cap) → boot-mode/strap pins (pulled to their
default state unless boot-mode selection is an intended feature) →
crystal/oscillator network, if used, as its own subcircuit rather
than folded into this one.

Treat VDDA (analog supply) decoupling and any recommended ferrite
bead/RC filter between VDD and VDDA as mandatory when the datasheet
specifies it, even if no analog peripheral is used in this design —
removing it changes the part's qualified operating conditions.

## Parameters to always fix explicitly
- Full list of power pins and their domain, taken from the actual
  datasheet pinout — never assumed from a similar-looking part in
  the same family, since pin count and domain split vary even within
  one vendor's product line.
- Decoupling capacitor value and count per pin, per the datasheet
  table (not a flat default) — including any pin the datasheet
  explicitly says can be left unpopulated.
- Reset pin polarity (active-low is the near-universal convention,
  but must be confirmed) and pull resistor value, per datasheet.
- Boot-mode/strap pin default states — must resolve to the intended
  boot behavior (e.g. boot from flash vs. bootloader) and must not
  float. This is a **firmware-owned value, not a hardware default**
  (see KICAD-11) — fill in the spec sheet's firmware interface
  contract from the actual firmware spec rather than picking a
  common convention and moving on; if firmware isn't defined yet,
  log it as `TBD — pending firmware spec`.
- Placement of the analog reference/VDDA decoupling relative to any
  ferrite/RC filter, if the datasheet specifies a filter network
  rather than a direct connection to digital VDD.

## Known pitfalls
- Treating "decoupling" as a single flat rule (e.g. always 100nF)
  instead of checking the datasheet's per-pin table: some power
  pins need a larger or smaller value, or an additional bulk cap
  the flat rule would miss.
- Leaving a strap/boot-mode pin floating because it "isn't used" in
  this design: floating strap pins can sample noise at reset and
  cause intermittent boot failures that don't reproduce on the
  bench.
- Getting reset pin polarity backwards by assuming a convention
  instead of checking the datasheet — an inverted reset network can
  hold the part in permanent reset or leave it unprotected against
  brown-out.
- Omitting VDDA filtering because "no analog peripheral is used
  yet": a later firmware change enabling an ADC/DAC then inherits
  noise the hardware was never built to filter, without an obvious
  schematic-level warning.

## Category-specific verification

**Default analysis set for KICAD-05**: this category is exempt from
the DC/AC/transient/thermal/worst-case analysis set by default —
it's a static, low-risk network, not a dynamic system — *except*
when the design includes a discrete reset supervisor with its own
timing behavior (power-good threshold, debounce delay) worth a
transient check, in which case name that one analysis explicitly in
the spec sheet rather than leaving the whole category silently
exempt.

- Cross-check every power pin in the finished schematic against the
  datasheet pinout table, one row at a time — a missed pin (rather
  than a wrong value) is the most common decoupling error and is
  easy for ERC to miss since an undecoupled-but-connected pin is
  still electrically valid.

## Layout notes (if PCB in scope)

This category is not KICAD-05-relevant by default, so these notes
can be executed directly by `kicad-builder` without a separate
`kicad-architect` layout review — unless a discrete reset supervisor
subcircuit is folded in here, in which case treat that portion under
the buck-converter-style review rule instead.

- Each decoupling capacitor must sit as close as physically possible
  to its power pin, with a short, low-inductance return path to
  ground — not just "nearby on the same net."
- Route the reset line away from high-dv/dt switching nets (e.g. a
  nearby buck converter's switch node) to avoid noise-induced
  spurious resets.

## External references
The MCU's own datasheet/reference manual "power supply scheme" or
"minimum system" section is the primary and near-always-sufficient
reference for this category.

## History
- 2026-07-03 — created generically (not tied to one project's exact
  MCU), pending refinement once a first real design logs its
  datasheet-specific decoupling table in a project's spec sheet.
