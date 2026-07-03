<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>



<!-- PROJECT SHIELDS -->
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]


<!-- PROJECT LOGO -->
<br />
<div align="center">
<h3 align="center">kicad-skill</h3>

  <p align="center">
    A reusable electronics design method for KiCad via MCP — breakdown into subcircuits, spec sheets, generic per-category design guides, and an auditable-assumption autopilot mode. Contains no project-specific data.
    <br />
    <a href="kicad-designer.md"><strong>Read the method »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Synobotix/kicad-skill/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/Synobotix/kicad-skill/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#how-it-works">How it works</a></li>
        <li><a href="#creating-a-spec-sheet-for-a-new-subcircuit">Creating a spec sheet for a new subcircuit</a></li>
        <li><a href="#creating-a-design-guide-for-a-new-subcircuit-category">Creating a design guide for a new subcircuit category</a></li>
      </ul>
    </li>
    <li><a href="#versioning">Versioning</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

Without a shared method, every KiCad session tends to reinvent its
own approach: component values get guessed silently instead of
logged, each subcircuit category is designed ad hoc with no memory
of what worked or failed last time, and there's no forced separation
between "generic electronics knowledge" (how do you design a buck
converter in general) and "this specific project's data" (this
project's converter steps 12V down to 3.3V at 500mA using a specific
IC). That leads to unreviewable assumptions baked directly into a
schematic, and design methods that have to be re-derived from
scratch on every new project.

This skill fixes that by splitting KiCad work into two layers:

- **Generic method + design guides** (this repo, `skills/kicad/`) —
  how to approach a breakdown, how to write a spec sheet, and
  reusable per-category design guides (`resources/`) capturing
  known-good topologies and pitfalls. Versioned and shared across
  every project that uses this skill.
- **Project-specific data** (in the consuming project, not here) —
  actual component values, actual datasheets, actual spec sheets,
  actual KiCad outputs.

On top of that, `kicad-autopilot` adds a set of non-negotiable
invariants (KICAD-01 to KICAD-14) so that autonomous work — filling
in a missing component value without asking the user every time —
stays auditable: every assumption is logged with its method and
confidence level in `assumptions.md`, never silently baked in.
KICAD-05 also forces simulation status to be typed by analysis
(DC / AC-stability / transient / thermal / worst-case) rather than a
single simulated/not-simulated flag; KICAD-09 tracks per-component
supply-chain risk (lifecycle status, single-source); KICAD-10 to
KICAD-13 close four more EDA-specific gaps that have no equivalent
in a purely geometric CAD spec sheet — MCP tool-call coverage,
firmware-owned pin/mux values, symbol/footprint/pinout provenance,
and an electrical bring-up plan before first fabrication, logged
**per assembled unit** (`bringup-log.md`) rather than once per board
revision, since the risk of a bad unit escaping into use is highest
on a repeat build, not the prototype the plan was written against;
and **KICAD-14 is a hard boundary rather than a confidence tier** —
it lets the skill log compliance-adjacent hygiene (RoHS/REACH
status, creepage/clearance design intent, isolation ratings) for
safety-critical subcircuits, but explicitly forbids ever asserting
that a design "passes," "is compliant with," or "is certified to"
any named EMC/safety/RoHS/isolation standard, since this skill has
no way to physically measure a board or run accredited test
equipment and a false positive here is worse than an under-
simulated circuit.

**Contents of this repo:**

- `kicad-designer.md` — breakdown into subcircuits, spec sheets,
  KiCad prompt template
- `kicad-autopilot.md` — invariants KICAD-01 to KICAD-14, generator/
  critic/gate loop, systematic blocking cases
- `_spec-template.md` — template to duplicate in each consuming
  project, once per subcircuit
- `resources/` — generic design guides by subcircuit category
  (KICAD-07), reusable across projects; `_template.md` is the
  template for a new guide. Currently covers: `buck-converter.md`,
  `mcu-decoupling-reset.md`.
- `claude-md-snippet.md` — block to paste into a consuming project's
  `CLAUDE.md` (not `CLAUDE.local.md` — it must apply to every
  session on the project, not just a local override) so any session
  in that project knows to use this skill, respect KICAD-07, and
  delegate to `kicad-agents` automatically (including layout review
  for KICAD-05-relevant subcircuits)

Model pinning per phase (`kicad-architect` = opus, `kicad-builder` =
sonnet) lives in a separate repo, [`kicad-agents`](../kicad-agents)
— kept apart because agent definitions must sit under a project's
`.claude/agents/` to be discovered by the harness, which is a
different consumption path than this skill's `skills/kicad/`
submodule.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

- A project repo with **Git submodules** support
- A **KiCad MCP** server reachable from the Claude session (this
  skill assumes KiCad tool calls — project/schematic creation,
  symbol placement, netlisting, ERC, PCB placement/routing, DRC —
  are available via MCP, not a manual KiCad UI)
- `kicad-cli` available on PATH is a useful fallback/complement for
  scripted ERC/DRC/export checks outside of MCP tool calls
- *Optional but recommended*: the [`kicad-agents`](../kicad-agents)
  repo, if you want the architecture/execution phase split enforced
  with a hard model pin rather than left to the current session's
  model

### Installation

1. Add this repo as a submodule in the consuming project, plus
   `kicad-agents` if you're using the hard model pin:
   ```bash
   git submodule add <kicad-skill-repo-url> skills/kicad
   git submodule add <kicad-agents-repo-url> agents/kicad
   git submodule update --init --recursive
   ```
2. Follow `kicad-agents`' own README to symlink its agent
   definitions into `.claude/agents/` — a submodule path alone isn't
   enough for the harness to discover `kicad-architect`/
   `kicad-builder` as invocable agents.
3. Paste the contents of `claude-md-snippet.md` into the project's
   `CLAUDE.md` (the shared, versioned one — not `CLAUDE.local.md`)
   so the method, KICAD-07, and the agent delegation are picked up
   automatically in every session on that project, rather than
   having to be re-explained each time.
4. Create the project-side folders that `kicad-designer.md` expects:
   ```
   kicad-projects/<project-name>/
     notes.md
     assumptions.md
     bringup-log.md
     specs/
     boards/
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

### How it works

0. **MCP capability audit (KICAD-10)** — once per project, before
   anything else: enumerate which schematic/PCB operations the KiCad
   MCP server actually exposes as tool calls, so a gap is never
   discovered mid-execution and silently papered over with freehand
   file editing.
1. **`notes.md`** — one project-wide brief fixed before the first
   subcircuit: supply voltage(s)/power budget, target application
   and environment, key ICs/component families already fixed,
   manufacturing constraints, regulatory/safety constraints, and
   whether the board is intended for sale (KICAD-14) — which gates
   how much compliance-adjacent hygiene logging is mandatory later.
2. **Breakdown** — list functional blocks (power, processing,
   interfaces, connectors, protection), their electrical
   dependencies, and the resulting design order.
3. **Design guide check (KICAD-07)** — for each subcircuit category,
   verify a guide exists in `resources/`. If not, stop and co-write
   one (see below) before designing anything in that category.
4. **Firmware interface contract (KICAD-11)** — for any MCU-adjacent
   subcircuit, pin mux/boot-strap values are firmware-owned, not
   hardware-derived; source them from the firmware spec or log them
   `TBD — pending firmware spec` rather than picking a hardware-side
   default.
5. **Spec sheet per subcircuit** — one `specs/<subcircuit>.md` per
   subcircuit, duplicated from `_spec-template.md` (see below).
6. **KiCad generation** — schematic capture (and, when in scope, PCB
   layout) built from the locked spec sheet, one subcircuit at a
   time, respecting dependency order.
7. **Verification** — ERC after every schematic change, SPICE
   simulation by named analysis type where relevant (KICAD-05),
   symbol/footprint/pinout provenance check before layout for
   high-pin-count/power/connector/IC parts (KICAD-12), DRC after
   every PCB layout change, netlist/footprint consistency check, a
   lifecycle/single-source BOM check (KICAD-09), a logged bring-up
   plan before first fabrication for any KICAD-05-relevant
   subcircuit with its test points cross-checked against the routed
   PCB (KICAD-04/KICAD-13), one `bringup-log.md` entry per assembled
   unit thereafter, and — for any mains-adjacent/battery-charging/
   high-voltage/user-accessible subcircuit — logged compliance-
   adjacent hygiene (RoHS/REACH, creepage/clearance intent, isolation
   rating) surfaced before any fabrication order if the project is
   intended for sale, never phrased as a compliance assertion
   (KICAD-14).

In autopilot mode, missing values go through a generator → critic →
gate loop instead of blocking on every gap, but every value used is
still logged in `assumptions.md` with its method and confidence
level — see `kicad-autopilot.md` for the full invariant list and the
cases where the gate always blocks regardless of mode.

Architecture decisions (breakdown, dependency graph, guide
authoring, and — for KICAD-05-relevant subcircuits — reviewing the
design guide's layout notes before routing starts) and execution
(schematic capture and PCB layout once a spec and any required
layout review are locked) are split across two agents
(`kicad-architect` / `kicad-builder`, see `kicad-agents`) rather than
done in one session — see `kicad-designer.md` for why: layout
changes electrical behavior (parasitics, noise coupling, thermal
path) in a way that has no equivalent in mechanical CAD, so it isn't
purely an execution-phase concern for a risk-bearing subcircuit.

### Creating a spec sheet for a new subcircuit

A spec sheet is **project-specific** — it lives in the consuming
project, not in this skill.

1. Copy `_spec-template.md` to `<project>/specs/<subcircuit-name>.md`.
2. Fill in function, dependencies (which subcircuits must be locked
   before/after this one), and known values with their source
   (datasheet / calculation / reference design / measurement — never
   blank).
3. If the subcircuit is MCU-adjacent, fill in the firmware interface
   contract (KICAD-11): pin function/mux selection and boot-strap
   intent, sourced from the actual firmware spec — never a hardware-
   side default — or logged `TBD — pending firmware spec`.
4. Fill in the simulation status (KICAD-05): whether the subcircuit
   carries electrical risk or non-trivial dynamic behavior, then the
   per-analysis-type table (DC / AC-stability / transient / thermal
   / worst-case) with a status and model confidence for each row
   that applies — per the category's design guide default — or an
   explicit justification if the whole category is exempt.
5. If the subcircuit includes a high-pin-count, power, connector, or
   IC component, fill in the symbol/footprint/pinout provenance
   table (KICAD-12) pin-by-pin before layout starts — a visual
   spot-check does not satisfy this.
6. Fill in the supply chain / lifecycle table (KICAD-09): lifecycle
   status and single-source flag per component — a component flagged
   single-source with no second source blocks fabrication export
   later (see KICAD-09) unless resolved or explicitly accepted here.
7. If the subcircuit is KICAD-05-relevant, fill in the bring-up plan
   (KICAD-13) before the first fabrication order for this board
   revision: test points, rail sequencing, and expected first-
   power-on measurements — the electrical equivalent of a mechanical
   dry-fit. This is the plan, authored once; log its actual
   execution against each assembled unit separately, in the
   project's `bringup-log.md` — writing the plan once does not
   satisfy KICAD-13 on its own.
8. If the subcircuit is mains-adjacent, battery-charging/protection,
   high voltage, or has a user-accessible connector, fill in the
   regulatory intent table (KICAD-14): RoHS/REACH status, creepage/
   clearance design intent cited against a named standard table, and
   isolation barrier rating. Every field is logged design intent,
   never a compliance claim — mandatory if `notes.md` declares
   `intended for sale: yes`.
9. Attach whatever reference material exists: datasheet(s), a
   reference schematic, or a vendor SPICE model. Prefer a
   vendor-provided SPICE model over a generic behavioral model for
   anything going through KICAD-05 simulation (see
   `kicad-designer.md`, "Using external resources") — a generic
   model can hide the exact non-ideality the simulation was meant to
   catch, and its confidence rating should reflect that.
10. Any value you don't have yet stays a gap to resolve — either ask
   the user, or, in autopilot mode, run it through the generator →
   critic → gate loop and log the result in the project's
   `assumptions.md` before it's used in KiCad.

A spec sheet is considered locked once every value has a source,
dependencies are satisfied, every required KICAD-05 analysis row is
resolved (done / not applicable, with justification if exempt), the
KICAD-09 lifecycle/single-source table has no unresolved component,
any firmware-owned value is sourced or explicitly TBD (KICAD-11),
and provenance is logged for any high-pin-count/power/connector/IC
component (KICAD-12) — only then should schematic generation for
that subcircuit start. A bring-up plan (KICAD-13) is additionally
required before the *first* fabrication order for a given board
revision, with one `bringup-log.md` entry per assembled unit
thereafter, and a regulatory intent table (KICAD-14) is required for
any mains-adjacent/battery-charging/high-voltage/user-accessible
subcircuit whenever the project is intended for sale.

### Creating a design guide for a new subcircuit category

A design guide is **generic and reusable** — it lives in this skill
repo (`resources/`), not in a project. Create one whenever KICAD-07
blocks because no existing guide covers the requested subcircuit
category — never improvise a design method for the gap instead.

1. Copy `resources/_template.md` to `resources/<category>.md`
   (category name, not project or instance name — e.g.
   `buck-converter.md`, not `main-board-5v-rail.md`).
2. Fill in **use cases covered** precisely enough that it's obvious
   whether a new request falls under this guide or needs its own.
3. Fill in the **recommended topology**: component families used,
   typical connections, operation order in schematic capture, and
   why that order matters.
4. Fill in **parameters to always fix explicitly** — the checklist
   of values that must never be silently assumed for this category,
   each with a one-line reason. This is what KICAD-01/the generator
   checks against in autopilot mode.
5. Fill in **known pitfalls** and **category-specific verification**
   from real experience — this is the part that actually saves
   rework on the next project, so favor concrete failure modes
   (e.g. "feedback trace routed near the switching node — verify
   against the actual layout") over generic advice. Category-
   specific verification must also state the category's **default
   analysis set for KICAD-05** (which of DC/AC-stability/transient/
   thermal/worst-case apply by default, or an explicit exemption)
   and, if not exempt, its typical **bring-up checkpoints**
   (KICAD-13) — this is what a project's spec sheet gets populated
   against. If the category is MCU-adjacent or routinely involves a
   high-pin-count/power/connector/IC component, flag which
   parameters are firmware-owned (KICAD-11) and note the pin-by-pin
   provenance requirement (KICAD-12) respectively.
6. Fill in **layout notes** if PCB work is in scope for this
   project — placement/routing guidance specific to the category. If
   the category is KICAD-05-relevant, note that these must be
   reviewed by `kicad-architect` before `kicad-builder` routes (see
   `kicad-designer.md`, Step 3bis) — layout is an architecture
   decision for a risk-bearing subcircuit, not just execution.
7. If the category routinely involves mains proximity, battery
   charging/protection, high voltage, or a user-accessible
   connector, fill in the **compliance reference table** (KICAD-14)
   — named standard *families* as reference only, never a
   calculation or a compliance assertion.
8. Add an **external references** entry if a relevant datasheet,
   app note, or standard reference design exists.
9. Log the **history** entry (date + originating context).
10. Co-write and validate the guide with the user before using it to
    generate any KiCad schematic (KICAD-07) — this step isn't
    optional, even under autopilot.
11. Commit the guide to this repo (bump the version — see below),
    not just to the current project, so every consuming project
    benefits from it on their next submodule update.

`resources/buck-converter.md` and `resources/mcu-decoupling-reset.md`
are good references for the level of detail expected — concrete
parameters and pitfalls, no project-specific values.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- VERSIONING -->
## Versioning

Semantic tags (`v0.1.0`, `v0.2.0`...). A consuming project pins the
submodule to a specific tag rather than the main branch — a change
to an invariant here (e.g. widening KICAD-05) must never silently
change the behavior of an ongoing project. Updating the submodule =
an explicit decision, not a side effect of a `git pull`. The same
applies to adding a new `resources/` guide: it only reaches a
consuming project once that project bumps its pinned tag.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

The main way this skill grows is through new `resources/` design
guides — co-written and validated against a real subcircuit (see
[Creating a design guide](#creating-a-design-guide-for-a-new-subcircuit-category)
above), then committed here so every consuming project benefits. Add
new guides as new subcircuit categories come up (e.g. USB-C power
input, RS-485 transceiver, crystal oscillator, battery
charging/protection).

1. Fork the project
2. Create your branch (`git checkout -b feat/your-guide`)
3. Add or update a guide under `resources/`, following the
   `_template.md` structure
4. Bump the version (see [Versioning](#versioning)) if the change
   affects consuming projects
5. Open a Pull Request targeting `main`

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/Synobotix/kicad-skill/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Synobotix/kicad-skill" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## License

Distributed under the Creative Commons Attribution-ShareAlike 4.0
International License (CC BY-SA 4.0). See `LICENSE` for more
information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Rémi Boivin - remiboivin021@gmail.com

Project Link: [https://github.com/Synobotix/kicad-skill](https://github.com/Synobotix/kicad-skill)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
* [KiCad](https://www.kicad.org/) and its MCP integration
* [`cad-skill`](../cad-skill) — the sibling repo this method was
  adapted from
* [`kicad-agents`](../kicad-agents) — the companion repo enforcing
  the architecture/execution model split

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
[stars-shield]: https://img.shields.io/github/stars/Synobotix/kicad-skill.svg?style=for-the-badge
[stars-url]: https://github.com/Synobotix/kicad-skill/stargazers
[issues-shield]: https://img.shields.io/github/issues/Synobotix/kicad-skill.svg?style=for-the-badge
[issues-url]: https://github.com/Synobotix/kicad-skill/issues
[license-shield]: https://img.shields.io/github/license/Synobotix/kicad-skill.svg?style=for-the-badge
[license-url]: https://github.com/Synobotix/kicad-skill/blob/main/LICENSE
